import json
import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Any


@dataclass(frozen=True)
class VideoMetadata:
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str | None
    size_bytes: int


def parse_metadata(raw: str) -> VideoMetadata:
    """Validate ffprobe output; ignore cover art when choosing a video stream."""
    try:
        data = json.loads(raw)
        streams = data["streams"]
        video = next(
            stream
            for stream in streams
            if stream.get("codec_type") == "video"
            and not stream.get("disposition", {}).get("attached_pic", 0)
        )
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        container = data.get("format", {})
        duration = _number(container.get("duration", video.get("duration", 0)))
        width, height = int(video["width"]), int(video["height"])
        if width <= 0 or height <= 0:
            raise ValueError("Invalid video dimensions")
        fps = 0.0
        for key in ("avg_frame_rate", "r_frame_rate"):
            try:
                fps = float(Fraction(str(video.get(key, "0/1"))))
                if fps > 0:
                    break
            except (ValueError, ZeroDivisionError):
                continue
        return VideoMetadata(
            duration=duration,
            width=width,
            height=height,
            fps=max(0, fps),
            video_codec=str(video.get("codec_name", "unknown")),
            audio_codec=str(audio.get("codec_name", "unknown")) if audio else None,
            size_bytes=int(_number(container.get("size", 0))),
        )
    except (ValueError, KeyError, TypeError, StopIteration, AttributeError, OverflowError) as exc:
        raise ValueError("Không đọc được metadata hoặc tệp không có luồng video hợp lệ.") from exc


def _number(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError("Invalid numeric metadata")
    return result
