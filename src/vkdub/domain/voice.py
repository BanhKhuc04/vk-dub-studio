import hashlib
import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_VOICE = "hn_female_ngochuyen_full_48k-fhg"
DEFAULT_LABEL = "HN - Ngọc Huyền"

DEFAULT_ELEVENLABS_VOICE = "21m00Tcm4TlvDq8ikWAM"
DEFAULT_ELEVENLABS_LABEL = "Rachel (Nữ nhẹ nhàng, truyền cảm)"


def normalized_text(text: str) -> str:
    # Preserve newlines and punctuation: these affect spoken pauses.
    return unicodedata.normalize("NFC", text).strip()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def valid_hash(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


@dataclass(frozen=True)
class VoiceSettings:
    provider: str = "vbee"
    voice_id: str = DEFAULT_VOICE
    display_name: str = DEFAULT_LABEL
    speed: float = 1.0
    volume: float = 1.0

    def __post_init__(self) -> None:
        if self.provider not in ("vbee", "elevenlabs", "vieneu_local", "capcut_tts"):
            raise ValueError("Chưa có adapter cho nhà cung cấp voice này.")
        if not isinstance(self.voice_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,200}", self.voice_id
        ):
            raise ValueError("Mã giọng đọc không hợp lệ.")
        if (
            not isinstance(self.display_name, str)
            or not self.display_name.strip()
            or len(self.display_name) > 200
        ):
            raise ValueError("Tên giọng đọc không hợp lệ.")
        for value, lower, upper in ((self.speed, 0.8, 1.3), (self.volume, 0.0, 1.0)):
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not lower <= value <= upper
            ):
                raise ValueError("Tốc độ/âm lượng voice không hợp lệ.")

    @classmethod
    def from_dict(cls, data: Any) -> "VoiceSettings":
        if not isinstance(data, dict) or set(data) != set(asdict(cls())):
            raise ValueError("Cấu hình voice sai cấu trúc.")
        return cls(**data)


def audio_key(text: str, settings: VoiceSettings) -> str:
    return digest(
        json.dumps(
            [settings.provider, settings.voice_id, float(settings.speed), normalized_text(text)],
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


@dataclass(frozen=True)
class Voice:
    code: str
    name: str
    language: str


POPULAR_ELEVENLABS_VOICES: tuple[Voice, ...] = (
    Voice("21m00Tcm4TlvDq8ikWAM", "Rachel (Nữ nhẹ nhàng, truyền cảm)", "vi"),
    Voice("pNInz6obpgDQGcFmaJgB", "Adam (Nam trầm ấm, tự sự)", "vi"),
    Voice("ErXwobaYiN019PkySvjV", "Antoni (Nam năng động, trẻ trung)", "vi"),
    Voice("EXAVITQu4vr4xnSDxMaL", "Bella (Nữ ngọt ngào, đọc truyện)", "vi"),
    Voice("TxGEqnHWrfWFTfGW9XjX", "Josh (Nam MC, tin tức)", "vi"),
)


@dataclass(frozen=True)
class VoiceAsset:
    cache_key: str
    text_hash: str
    provider: str
    voice_id: str
    speed: float
    duration_ms: int
    output_path: Path
    audio_sha256: str
    generated_at: str

    def __post_init__(self) -> None:
        if not all(valid_hash(v) for v in (self.cache_key, self.text_hash, self.audio_sha256)):
            raise ValueError("Dấu vân tay voice không hợp lệ.")
        VoiceSettings(self.provider, self.voice_id, DEFAULT_LABEL, self.speed)
        if type(self.duration_ms) is not int or not 0 < self.duration_ms <= 86_400_000:
            raise ValueError("Thời lượng voice không hợp lệ.")
        if not isinstance(self.output_path, Path) or self.output_path.suffix.lower() != ".wav":
            raise ValueError("Đường dẫn voice không hợp lệ.")
        if (
            not isinstance(self.generated_at, str)
            or datetime.fromisoformat(self.generated_at).tzinfo is None
        ):
            raise ValueError("Ngày tạo voice không hợp lệ.")

    def matches(self, text: str, settings: VoiceSettings) -> bool:
        return (
            self.cache_key == audio_key(text, settings)
            and self.text_hash == digest(normalized_text(text))
            and self.provider == settings.provider
            and self.voice_id == settings.voice_id
            and self.speed == settings.speed
        )

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "output_path": str(self.output_path)}

    @classmethod
    def from_dict(cls, data: Any, parent: Path) -> "VoiceAsset":
        expected = {
            "cache_key",
            "text_hash",
            "provider",
            "voice_id",
            "speed",
            "duration_ms",
            "output_path",
            "audio_sha256",
            "generated_at",
        }
        if not isinstance(data, dict) or set(data) != expected:
            raise ValueError("Metadata voice sai cấu trúc.")
        path = data["output_path"]
        if not isinstance(path, str) or not path.strip() or "\0" in path:
            raise ValueError("Đường dẫn voice không hợp lệ.")
        return cls(**{**data, "output_path": (parent / path).resolve()})


def timing_warning(duration_ms: int, target_ms: int) -> str:
    if duration_ms <= target_ms:
        return ""
    ratio = duration_ms / max(1, target_ms)
    if ratio <= 1.10:
        return f"Voice dài hơn câu ({duration_ms / 1000:.2f}s); có thể chỉnh nhẹ ≤1.10x khi dựng."
    return (
        f"Voice quá dài ({duration_ms / 1000:.2f}s): "
        "rút gọn câu hoặc chỉnh thời gian/tốc độ rồi duyệt lại."
    )
