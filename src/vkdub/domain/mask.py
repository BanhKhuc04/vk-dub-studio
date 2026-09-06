from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4


@dataclass
class MaskItem:
    """Represents a rectangular mask to obscure old subtitles or watermarks."""

    id: str = ""
    name: str = "Vùng che mới"
    mask_type: str = "erase"  # 'erase', 'blur', or 'solid'
    x: float = 0.1  # Normalized 0.0 to 1.0 relative to video width
    y: float = 0.8  # Normalized 0.0 to 1.0 relative to video height
    width: float = 0.8  # Normalized 0.0 to 1.0
    height: float = 0.15  # Normalized 0.0 to 1.0
    color: str = "#000000"  # Hex color for solid fill
    opacity: float = 1.0  # 0.0 to 1.0
    blur_strength: int = 15  # 1 to 50
    start_ms: int = 0  # 0 means start of video
    end_ms: int = 0  # 0 means end of video / entire duration

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid4())
        # Clamp coordinates into normalized range [0.0, 1.0]
        self.x = max(0.0, min(1.0, float(self.x)))
        self.y = max(0.0, min(1.0, float(self.y)))
        self.width = max(0.01, min(1.0 - self.x, float(self.width)))
        self.height = max(0.01, min(1.0 - self.y, float(self.height)))
        self.opacity = max(0.1, min(1.0, float(self.opacity)))
        self.blur_strength = max(1, min(50, int(self.blur_strength)))
        self.start_ms = max(0, int(self.start_ms))
        self.end_ms = max(0, int(self.end_ms))

    def is_active_at(self, timestamp_ms: int) -> bool:
        """Check if this mask should be rendered at the given millisecond timestamp."""
        if self.start_ms == 0 and self.end_ms == 0:
            return True
        if self.end_ms > 0 and self.end_ms >= self.start_ms:
            return self.start_ms <= timestamp_ms <= self.end_ms
        if self.end_ms == 0:
            return timestamp_ms >= self.start_ms
        return False

    def to_pixel_rect(self, video_width: int, video_height: int) -> tuple[int, int, int, int]:
        """Convert normalized (0.0-1.0) coordinates to integer pixel (x, y, w, h)."""
        px_x = max(0, min(video_width - 1, round(self.x * video_width)))
        px_y = max(0, min(video_height - 1, round(self.y * video_height)))
        px_w = max(1, min(video_width - px_x, round(self.width * video_width)))
        px_h = max(1, min(video_height - px_y, round(self.height * video_height)))
        return px_x, px_y, px_w, px_h

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MaskItem":
        valid_keys = {f for f in cls.__annotations__}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)
