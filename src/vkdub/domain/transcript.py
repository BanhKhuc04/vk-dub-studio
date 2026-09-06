import math
from dataclasses import asdict, dataclass
from typing import Any

MODELS = ("tiny", "base", "small", "medium", "large-v3")
DEVICES = ("auto", "cpu", "cuda")


@dataclass(frozen=True)
class TranscriptionSettings:
    model: str = "base"
    device: str = "auto"

    def __post_init__(self) -> None:
        if self.model not in MODELS or self.device not in DEVICES:
            raise ValueError("Model hoặc thiết bị bóc băng không được hỗ trợ.")


@dataclass(frozen=True)
class SubtitleSegment:
    id: int
    start: float
    end: float
    text: str

    def __post_init__(self) -> None:
        if type(self.id) is not int or self.id < 1:
            raise ValueError("Số thứ tự câu không hợp lệ.")
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (self.start, self.end)):
            raise ValueError("Thời gian câu phải là số hữu hạn.")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("Khoảng thời gian câu không hợp lệ.")
        if not isinstance(self.text, str) or not self.text.strip() or "\0" in self.text:
            raise ValueError("Nội dung câu trống hoặc không hợp lệ.")


@dataclass(frozen=True)
class Transcript:
    segments: tuple[SubtitleSegment, ...]
    language: str
    requested_language: str
    duration: float
    model: str
    device: str
    fingerprint: str
    cache_key: str

    def __post_init__(self) -> None:
        if type(self.duration) not in (float, int) or not math.isfinite(self.duration):
            raise ValueError("Thời lượng bản chép lời không hợp lệ.")
        if self.duration < 0 or self.model not in MODELS or self.device not in ("cpu", "cuda"):
            raise ValueError("Thông tin model/thời lượng không hợp lệ.")
        for language in (self.language, self.requested_language):
            if not isinstance(language, str) or not language or len(language) > 20:
                raise ValueError("Ngôn ngữ bản chép lời không hợp lệ.")
        for digest in (self.fingerprint, self.cache_key):
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)
            ):
                raise ValueError("Dấu vân tay bản chép lời không hợp lệ.")
        previous_end = 0.0
        for index, segment in enumerate(self.segments, 1):
            if segment.id != index or segment.start < previous_end - 0.001:
                raise ValueError("Các câu phải đúng thứ tự và không chồng thời gian.")
            if segment.end > self.duration + 0.1:
                raise ValueError("Câu vượt quá thời lượng nguồn.")
            previous_end = segment.end

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["segments"] = [asdict(segment) for segment in self.segments]
        return result

    @classmethod
    def from_dict(cls, data: Any) -> "Transcript":
        try:
            if not isinstance(data, dict) or not isinstance(data.get("segments"), list):
                raise ValueError("Bản chép lời không hợp lệ.")
            if len(data["segments"]) > 50000:
                raise ValueError("Bản chép lời vượt giới hạn 50.000 câu.")
            values = dict(data)
            values["segments"] = tuple(SubtitleSegment(**s) for s in data["segments"])
            return cls(**values)
        except (TypeError, KeyError, AttributeError) as exc:
            raise ValueError("Dữ liệu bản chép lời không đúng cấu trúc.") from exc


def srt_timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{whole_seconds:02},{milliseconds:03}"


def to_srt(transcript: Transcript) -> str:
    """Source transcript serialization; subtitle editing/styling remains a later phase."""
    return "\n".join(
        f"{s.id}\n{srt_timestamp(s.start)} --> {srt_timestamp(s.end)}\n{s.text.strip()}\n"
        for s in transcript.segments
    )
