from dataclasses import replace
from typing import Any

from vkdub.domain.script import ScriptDocument, ScriptLine


def edit_line(script: ScriptDocument, index: int, **changes: Any) -> ScriptDocument:
    rows = list(script.lines)
    rows[index] = replace(rows[index], **changes)
    return replace(script, lines=tuple(rows))


def add_line(script: ScriptDocument, after: int, position_ms: int) -> ScriptDocument:
    rows = list(script.lines)
    if rows and after >= 0:
        start = max(0, rows[after].end_ms)
        end = rows[after + 1].start_ms if after + 1 < len(rows) else start + 2000
        if end <= start:
            raise ValueError("Không có khoảng trống. Điều chỉnh thời gian trước khi thêm câu.")
    else:
        start = max(0, position_ms)
        end = rows[0].start_ms if rows else start + 2000
        if end <= start:
            raise ValueError("Không có khoảng trống trước câu đầu.")
    rows.insert(after + 1, ScriptLine.new(start, min(end, start + 2000)))
    return replace(script, lines=tuple(rows))


def delete_line(script: ScriptDocument, index: int) -> ScriptDocument:
    return replace(script, lines=script.lines[:index] + script.lines[index + 1 :])


def split_line(script: ScriptDocument, index: int, cursor: int, at_ms: int) -> ScriptDocument:
    old = script.lines[index]
    if not old.start_ms < at_ms < old.end_ms:
        raise ValueError("Điểm tách phải nằm trong thời gian câu.")
    if not 0 < cursor < len(old.text):
        raise ValueError("Đặt con trỏ giữa nội dung tiếng Việt để tách câu.")
    first = replace(old, end_ms=at_ms, text=old.text[:cursor].rstrip())
    second = ScriptLine.new(at_ms, old.end_ms, old.text[cursor:].lstrip(), old.source_ids)
    return replace(script, lines=script.lines[:index] + (first, second) + script.lines[index + 1 :])


def merge_lines(script: ScriptDocument, index: int) -> ScriptDocument:
    if not 0 <= index < len(script.lines) - 1:
        raise ValueError("Cần hai câu liền nhau để gộp.")
    first, second = script.lines[index : index + 2]
    if first.end_ms > second.start_ms or first.start_ms >= second.end_ms:
        raise ValueError("Sửa thời gian chồng lấn hoặc thứ tự trước khi gộp.")
    merged = replace(
        first,
        end_ms=second.end_ms,
        text=" ".join(text.strip() for text in (first.text, second.text) if text.strip()),
        source_ids=tuple(dict.fromkeys(first.source_ids + second.source_ids)),
    )
    return replace(script, lines=script.lines[:index] + (merged,) + script.lines[index + 2 :])


def move_line(script: ScriptDocument, index: int, destination: int) -> ScriptDocument:
    rows = list(script.lines)
    rows.insert(destination, rows.pop(index))
    changed = replace(script, lines=tuple(rows))
    if any(
        row.start_ms < 0
        or row.end_ms <= row.start_ms
        or (i > 0 and changed.lines[i - 1].end_ms > row.start_ms)
        for i, row in enumerate(changed.lines)
    ):
        raise ValueError("Chỉ đổi thứ tự khi thời gian và nội dung vẫn hợp lệ.")
    return changed


def replace_text(script: ScriptDocument, find: str, replacement: str) -> ScriptDocument:
    if not find:
        raise ValueError("Nhập nội dung cần tìm.")
    return replace(
        script,
        lines=tuple(replace(row, text=row.text.replace(find, replacement)) for row in script.lines),
    )
