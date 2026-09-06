import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from vkdub.domain.transcript import Transcript

GEMINI_MODEL = "gemini-3.5-flash"
SUPPORTED_MODELS = (
    GEMINI_MODEL,
    "gemini-3.6-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
)
PROMPT_VERSION = "vi-dub-v1"


def source_digest(transcript: Transcript) -> str:
    return hashlib.sha256(
        json.dumps(transcript.to_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def validate_response(data: Any, ids: list[int]) -> tuple[str, ...]:
    """Reject missing, extra, duplicate or reordered IDs before touching the script."""
    if not isinstance(data, dict) or set(data) != {"segments"}:
        raise ValueError("Bản dịch không đúng cấu trúc JSON.")
    rows = data["segments"]
    if not isinstance(rows, list) or len(rows) != len(ids):
        raise ValueError("Bản dịch thiếu hoặc thừa câu.")
    texts = []
    for row, identifier in zip(rows, ids, strict=True):
        if (
            not isinstance(row, dict)
            or set(row) != {"id", "translation"}
            or type(row["id"]) is not int
            or row["id"] != identifier
        ):
            raise ValueError("ID bản dịch không khớp bản gốc.")
        value = row["translation"]
        if not isinstance(value, str) or not value.strip() or "\0" in value or len(value) > 12000:
            raise ValueError("Câu dịch trống hoặc không hợp lệ.")
        texts.append(value.strip())
    return tuple(texts)


@dataclass(frozen=True)
class Translation:
    source_hash: str
    texts: tuple[str, ...]
    provider: str = "gemini"
    model: str = GEMINI_MODEL
    target_language: str = "vi"
    prompt_version: str = PROMPT_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.source_hash, str) or not re.fullmatch(
            "[0-9a-f]{64}", self.source_hash
        ):
            raise ValueError("Bản dịch thiếu dấu vân tay nguồn.")
        if (
            self.provider != "gemini"
            or self.model not in SUPPORTED_MODELS
            or self.target_language != "vi"
            or self.prompt_version != PROMPT_VERSION
        ):
            raise ValueError("Chưa hỗ trợ cấu hình bản dịch này.")
        if not isinstance(self.texts, tuple) or not 1 <= len(self.texts) <= 50000:
            raise ValueError("Bản dịch phải có câu.")
        validate_response(
            {"segments": [{"id": i, "translation": t} for i, t in enumerate(self.texts, 1)]},
            list(range(1, len(self.texts) + 1)),
        )

    def validate_source(self, transcript: Transcript | None) -> None:
        if (
            transcript is None
            or self.source_hash != source_digest(transcript)
            or len(self.texts) != len(transcript.segments)
        ):
            raise ValueError("Bản dịch không khớp bản chép lời nguồn.")

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "texts": list(self.texts)}

    @classmethod
    def from_dict(cls, data: Any) -> "Translation":
        try:
            if not isinstance(data, dict) or not isinstance(data.get("texts"), list):
                raise ValueError("Dữ liệu bản dịch không hợp lệ.")
            return cls(**{**data, "texts": tuple(data["texts"])})
        except TypeError as exc:
            raise ValueError("Dữ liệu bản dịch không hợp lệ.") from exc
