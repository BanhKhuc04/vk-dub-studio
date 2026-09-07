"""Pipeline states, sub-step statuses, and artifact tracking models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class PipelineState(StrEnum):
    PROJECT_CREATED = "PROJECT_CREATED"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSCRIBED = "TRANSCRIBED"
    TRANSLATING = "TRANSLATING"
    TRANSLATED = "TRANSLATED"
    SCRIPT_READY = "SCRIPT_READY"
    VOICE_GENERATING = "VOICE_GENERATING"
    VOICE_READY = "VOICE_READY"
    REVIEW_READY = "REVIEW_READY"
    EXPORTED = "EXPORTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SubstepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    VALIDATING = "VALIDATING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass
class SubstepInfo:
    id: str  # e.g. "4.1", "4.2", "4.3", "4.4"
    name: str
    status: SubstepStatus = SubstepStatus.PENDING
    progress: int = 0
    message: str = "Đang chờ..."
    duration_s: float = 0.0
    error: str | None = None
    artifact_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["artifact_path"] = str(self.artifact_path) if self.artifact_path else None
        return d


@dataclass
class ArtifactRegistry:
    source_video: Path | None = None
    original_srt: Path | None = None
    translated_srt: Path | None = None
    voice_script: Path | None = None
    vbee_master_audio: Path | None = None
    timeline_master_audio: Path | None = None
    project_json: Path | None = None
    capcut_draft_dir: Path | None = None
    export_artifacts: list[Path] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_video": str(self.source_video) if self.source_video else None,
            "original_srt": str(self.original_srt) if self.original_srt else None,
            "translated_srt": (str(self.translated_srt) if self.translated_srt else None),
            "voice_script": str(self.voice_script) if self.voice_script else None,
            "vbee_master_audio": (str(self.vbee_master_audio) if self.vbee_master_audio else None),
            "timeline_master_audio": (
                str(self.timeline_master_audio) if self.timeline_master_audio else None
            ),
            "project_json": str(self.project_json) if self.project_json else None,
            "capcut_draft_dir": (str(self.capcut_draft_dir) if self.capcut_draft_dir else None),
            "export_artifacts": [str(p) for p in self.export_artifacts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtifactRegistry:
        def p(val: str | None) -> Path | None:
            return Path(val) if val else None

        return cls(
            source_video=p(data.get("source_video")),
            original_srt=p(data.get("original_srt")),
            translated_srt=p(data.get("translated_srt")),
            voice_script=p(data.get("voice_script")),
            vbee_master_audio=p(data.get("vbee_master_audio")),
            timeline_master_audio=p(data.get("timeline_master_audio")),
            project_json=p(data.get("project_json")),
            capcut_draft_dir=p(data.get("capcut_draft_dir")),
            export_artifacts=[Path(x) for x in data.get("export_artifacts", []) if x],
        )
