"""Editable drafts retain invalid semantic values so users can save and repair them."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from vkdub.domain.transcript import Transcript
from vkdub.domain.translation import Translation, source_digest


@dataclass(frozen=True)
class ScriptLine:
    id: str
    start_ms: int
    end_ms: int
    text: str
    source_ids: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        try:
            UUID(self.id)
        except (ValueError, TypeError, AttributeError):
            raise ValueError("ID câu không hợp lệ.") from None
        if any(type(t) is not int or abs(t) > 3_600_000_000 for t in (self.start_ms, self.end_ms)):
            raise ValueError("Thời gian câu ngoài phạm vi hỗ trợ.")
        if not isinstance(self.text, str) or "\0" in self.text or len(self.text) > 1_000_000:
            raise ValueError("Nội dung câu không hợp lệ hoặc quá lớn.")
        if (
            not isinstance(self.source_ids, tuple)
            or any(type(i) is not int or i < 1 for i in self.source_ids)
            or len(set(self.source_ids)) != len(self.source_ids)
        ):
            raise ValueError("Tham chiếu câu nguồn không hợp lệ.")

    @classmethod
    def new(
        cls, start_ms: int, end_ms: int, text: str = "", source_ids: tuple[int, ...] = ()
    ) -> "ScriptLine":
        return cls(str(uuid4()), start_ms, end_ms, text, source_ids)


@dataclass(frozen=True)
class ScriptDocument:
    lines: tuple[ScriptLine, ...]
    source_hash: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.lines, tuple) or len(self.lines) > 50000:
            raise ValueError("Kịch bản vượt 50.000 câu hoặc sai cấu trúc.")
        if any(not isinstance(line, ScriptLine) for line in self.lines):
            raise ValueError("Cấu trúc câu không hợp lệ.")
        if len({line.id for line in self.lines}) != len(self.lines):
            raise ValueError("ID câu bị trùng.")
        if self.source_hash is not None and (
            not isinstance(self.source_hash, str)
            or not re.fullmatch("[0-9a-f]{64}", self.source_hash)
        ):
            raise ValueError("Dấu vân tay nguồn không hợp lệ.")

    def validate_source(self, transcript: Transcript | None) -> None:
        if self.source_hash is not None:
            if transcript is None or source_digest(transcript) != self.source_hash:
                raise ValueError("Kịch bản không khớp bản chép lời nguồn.")
        limit = len(transcript.segments) if transcript and self.source_hash else 0
        if any(i > limit for line in self.lines for i in line.source_ids):
            raise ValueError("Câu nguồn không tồn tại.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_hash": self.source_hash,
            "lines": [{**asdict(line), "source_ids": list(line.source_ids)} for line in self.lines],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ScriptDocument":
        try:
            if not isinstance(data, dict) or set(data) != {"source_hash", "lines"}:
                raise ValueError
            if not isinstance(data["lines"], list) or len(data["lines"]) > 50000:
                raise ValueError
            rows = []
            for row in data["lines"]:
                if not isinstance(row, dict) or not isinstance(row.get("source_ids"), list):
                    raise ValueError
                rows.append(ScriptLine(**{**row, "source_ids": tuple(row["source_ids"])}))
            return cls(tuple(rows), data["source_hash"])
        except (ValueError, TypeError):
            raise ValueError("Kịch bản sai cấu trúc; project được giữ nguyên.") from None


def draft_from_source(source: Transcript, translation: Translation | None = None) -> ScriptDocument:
    if translation:
        translation.validate_source(source)
    digest = source_digest(source)
    return ScriptDocument(
        tuple(
            ScriptLine(
                str(uuid5(NAMESPACE_URL, f"vkdub:{digest}:{s.id}")),
                round(s.start * 1000),
                round(s.end * 1000),
                translation.texts[s.id - 1] if translation else "",
                (s.id,),
            )
            for s in source.segments
        ),
        digest,
    )


def script_hash(script: ScriptDocument, context: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            ["vkdub-review-v1", context, script.to_dict()],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class ScriptIssue:
    line_id: str | None
    severity: str
    message: str


def estimated_voice_ms(text: str) -> int:
    # Vietnamese whitespace-delimited syllables at ~4 per second. A warning heuristic only.
    return len(text.split()) * 250


def validate_script(
    script: ScriptDocument, duration_ms: int | None = None
) -> tuple[ScriptIssue, ...]:
    issues = []
    if not script.lines:
        issues.append(ScriptIssue(None, "error", "Kịch bản chưa có câu."))
    furthest_end = 0
    previous_start = -1
    for line in script.lines:

        def issue(severity: str, message: str, identifier: str = line.id) -> None:
            issues.append(ScriptIssue(identifier, severity, message))

        if line.start_ms < 0:
            issue("error", "Thời gian bắt đầu phải ≥ 0.")
        if line.end_ms <= line.start_ms:
            issue("error", "Kết thúc phải sau bắt đầu.")
        if line.start_ms < previous_start:
            issue("error", "Thứ tự câu không theo thời gian.")
        if line.start_ms < furthest_end:
            issue("error", "Câu chồng thời gian với câu trước.")
        if duration_ms is not None and line.end_ms > duration_ms:
            issue("error", "Câu vượt thời lượng video.")
        if not line.text.strip():
            issue("error", "Nội dung tiếng Việt còn trống.")
        if len(line.text) > 12000:
            issue("error", "Câu vượt 12.000 ký tự; hãy tách thành các câu ngắn hơn.")
        if estimated_voice_ms(line.text) > max(0, line.end_ms - line.start_ms):
            issue("warning", "Ước tính lời đọc dài hơn thời lượng câu.")
        if (line.end_ms - line.start_ms) > 20000:
            issue("warning", "Thời lượng câu quá dài (> 20s); nên tách nhỏ.")
        furthest_end = max(furthest_end, line.end_ms)
        previous_start = line.start_ms
    return tuple(issues)
