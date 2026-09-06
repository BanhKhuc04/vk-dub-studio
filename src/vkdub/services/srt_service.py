import os
import re
import tempfile
from pathlib import Path

from vkdub.domain.script import ScriptDocument, ScriptLine, validate_script
from vkdub.domain.transcript import srt_timestamp

TIMING = re.compile(
    r"(\d{2,3}):([0-5]\d):([0-5]\d)[,.](\d{3})\s+-->\s+"
    r"(\d{2,3}):([0-5]\d):([0-5]\d)[,.](\d{3})"
)


def parse_srt(text: str, source_hash: str | None = None) -> ScriptDocument:
    if len(text.encode("utf-8")) > 8_000_000:
        raise ValueError("SRT vượt 8 MB.")
    blocks = re.split(r"\n[ \t]*\n", text.lstrip("\ufeff").replace("\r\n", "\n").strip())
    rows = []
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit():
            raise ValueError("SRT cần số thứ tự, thời gian và nội dung cho mỗi câu.")
        match = TIMING.fullmatch(lines[1].strip())
        if not match:
            raise ValueError("Thời gian SRT không đúng HH:MM:SS,mmm --> HH:MM:SS,mmm.")
        h, m, s, ms, eh, em, es, ems = map(int, match.groups())
        rows.append(
            ScriptLine.new(
                ((h * 60 + m) * 60 + s) * 1000 + ms,
                ((eh * 60 + em) * 60 + es) * 1000 + ems,
                "\n".join(lines[2:]),
            )
        )
    return ScriptDocument(tuple(rows), source_hash)


def read_srt(path: Path, source_hash: str | None = None) -> ScriptDocument:
    if path.stat().st_size > 8_000_000:
        raise ValueError("SRT vượt 8 MB.")
    try:
        return parse_srt(path.read_text(encoding="utf-8-sig"), source_hash)
    except UnicodeError:
        raise ValueError("Hãy lưu SRT bằng mã hóa UTF-8.") from None


def script_to_srt(script: ScriptDocument, duration_ms: int | None = None) -> str:
    if any(i.severity == "error" for i in validate_script(script, duration_ms)):
        raise ValueError("Sửa lỗi kịch bản trước khi lưu SRT. Có thể lưu bản nháp bằng .vkdub.")
    # Blank physical lines delimit SRT cues. Omit them inside a caption; retain the draft verbatim.
    contents = [
        "\n".join(part for part in row.text.strip().splitlines() if part.strip())
        for row in script.lines
    ]
    return "\n".join(
        f"{i}\n{srt_timestamp(row.start_ms / 1000)} --> "
        f"{srt_timestamp(row.end_ms / 1000)}\n{contents[i - 1]}\n"
        for i, row in enumerate(script.lines, 1)
    )


def write_srt(path: Path, script: ScriptDocument, duration_ms: int | None = None) -> None:
    text = script_to_srt(script, duration_ms)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
