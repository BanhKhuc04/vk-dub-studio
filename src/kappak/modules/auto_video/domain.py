"""Domain models for KAPPAK Auto Video Generator module."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime


@dataclass
class SceneSegment:
    """Represents an individual scene in the auto-video timeline."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    order_index: int = 0
    text: str = ""
    asset_id: str | None = None
    asset_path: str | None = None
    start_sec: float = 0.0
    end_sec: float = 0.0
    duration_sec: float = 0.0
    voice_audio_path: str | None = None
    voice_duration_sec: float = 0.0
    transition: str = "none"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SceneSegment:
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            order_index=data.get("order_index", 0),
            text=data.get("text", ""),
            asset_id=data.get("asset_id"),
            asset_path=data.get("asset_path"),
            start_sec=float(data.get("start_sec", 0.0)),
            end_sec=float(data.get("end_sec", 0.0)),
            duration_sec=float(data.get("duration_sec", 0.0)),
            voice_audio_path=data.get("voice_audio_path"),
            voice_duration_sec=float(data.get("voice_duration_sec", 0.0)),
            transition=data.get("transition", "none"),
        )


@dataclass
class TemplatePreset:
    """Pre-configured visual layout templates for 9:16 vertical short videos."""

    id: str
    name: str
    description: str
    aspect_ratio: str = "9:16"
    width: int = 1080
    height: int = 1920
    icon: str = "spark"
    features: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AutoVideoProject:
    """Represents an auto-video generation project."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Video Ngắn Mới"
    project_id: str | None = None
    template_id: str = "blur_bg"
    voice_id: str = "vi-VN-HoaiMyNeural"
    voice_speed: float = 1.0
    bgm_asset_id: str | None = None
    bgm_volume: float = 0.15
    script_text: str = ""
    scenes: list[SceneSegment] = field(default_factory=list)
    status: str = "DRAFT"  # DRAFT, COMPOSING, RENDERING, COMPLETED, FAILED
    progress_pct: float = 0.0
    output_video_path: str | None = None
    error_message: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["scenes"] = [s.to_dict() if isinstance(s, SceneSegment) else s for s in self.scenes]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> AutoVideoProject:
        scenes_raw = data.get("scenes", [])
        if isinstance(scenes_raw, str):
            try:
                scenes_raw = json.loads(scenes_raw)
            except Exception:
                scenes_raw = []
        scenes = [SceneSegment.from_dict(s) if isinstance(s, dict) else s for s in scenes_raw]
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "Video Ngắn Mới"),
            project_id=data.get("project_id"),
            template_id=data.get("template_id", "blur_bg"),
            voice_id=data.get("voice_id", "vi-VN-HoaiMyNeural"),
            voice_speed=float(data.get("voice_speed", 1.0)),
            bgm_asset_id=data.get("bgm_asset_id"),
            bgm_volume=float(data.get("bgm_volume", 0.15)),
            script_text=data.get("script_text", ""),
            scenes=scenes,
            status=data.get("status", "DRAFT"),
            progress_pct=float(data.get("progress_pct", 0.0)),
            output_video_path=data.get("output_video_path"),
            error_message=data.get("error_message"),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            updated_at=data.get("updated_at", datetime.now(UTC).isoformat()),
        )
