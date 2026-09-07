from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from vkdub.domain.mask import MaskItem
from vkdub.domain.script import ScriptDocument, draft_from_source, script_hash, validate_script
from vkdub.domain.subtitle import SubtitleStyle
from vkdub.domain.transcript import Transcript, TranscriptionSettings
from vkdub.domain.translation import Translation
from vkdub.domain.voice import VoiceAsset, VoiceSettings


@dataclass
class Project:
    project_id: str = field(default_factory=lambda: str(uuid4()))
    video_path: Path | None = None
    output_directory: Path | None = None
    source_language: str = "auto"
    target_language: str = "vi"
    transcription_settings: TranscriptionSettings = field(default_factory=TranscriptionSettings)
    transcript: Transcript | None = None
    translation: Translation | None = None
    script: ScriptDocument | None = None
    approved_revision_hash: str | None = None
    video_duration_ms: int | None = None
    voice: VoiceSettings = field(
        default_factory=lambda: VoiceSettings(
            provider="vieneu_local", voice_id="unconfigured", display_name="Chưa chọn giọng"
        )
    )
    voice_assets: dict[str, VoiceAsset] = field(default_factory=dict)
    master_voice_path: Path | None = None
    subtitle_style: SubtitleStyle = field(default_factory=SubtitleStyle)
    masks: list[MaskItem] = field(default_factory=list)

    def current_voice(self, line_id: str) -> VoiceAsset | None:
        return self.current_voices().get(line_id)

    def current_voices(self) -> dict[str, VoiceAsset]:
        if self.script is None or not self.is_approved:
            return {}
        res = {
            line.id: asset
            for line in self.script.lines
            if (asset := self.voice_assets.get(line.id))
            and asset.matches(line.text, self.voice)
            and asset.output_path.is_file()
        }
        if not res and self.master_voice_path and self.master_voice_path.is_file():
            # Provide synthesized master asset for compatibility
            for line in self.script.lines:
                res[line.id] = VoiceAsset(
                    audio_key=f"master_{line.id}",
                    output_path=self.master_voice_path,
                    duration_ms=line.end_ms - line.start_ms,
                    sample_rate_hz=24000,
                    voice=self.voice,
                    text_hash=line.text,
                )
        return res

    @property
    def voice_ready(self) -> bool:
        if not (self.is_approved and self.script and self.script.lines):
            return False
        if self.master_voice_path and self.master_voice_path.is_file():
            return True
        return len(self.current_voices()) == len(self.script.lines)

    def __post_init__(self) -> None:
        if self.script is None and self.translation and self.transcript:
            self.script = draft_from_source(self.transcript, self.translation)

    @property
    def duration_ms(self) -> int | None:
        if self.video_duration_ms is not None:
            return self.video_duration_ms
        return round(self.transcript.duration * 1000) if self.transcript else None

    @property
    def revision_hash(self) -> str | None:
        if self.script is None:
            return None
        return script_hash(
            self.script,
            {
                "project_id": self.project_id,
                "video": str(self.video_path.resolve()) if self.video_path else None,
                "target_language": self.target_language,
                "duration_ms": self.duration_ms,
            },
        )

    @property
    def script_valid(self) -> bool:
        if self.script is None or self.video_path is None or self.target_language != "vi":
            return False
        try:
            self.script.validate_source(self.transcript)
        except ValueError:
            return False
        return not any(
            i.severity == "error" for i in validate_script(self.script, self.duration_ms)
        )

    @property
    def is_approved(self) -> bool:
        return bool(
            self.script_valid
            and self.approved_revision_hash
            and self.approved_revision_hash == self.revision_hash
        )

    def set_script(self, script: ScriptDocument | None) -> None:
        if script != self.script:
            self.script = script
            self.approved_revision_hash = None

    def approve(self, confirmed: bool) -> str:
        if confirmed is not True or not self.script_valid:
            raise ValueError("Phải kiểm tra toàn bộ kịch bản và sửa mọi lỗi trước khi duyệt.")
        self.approved_revision_hash = self.revision_hash
        assert self.approved_revision_hash is not None
        return self.approved_revision_hash

    def require_approval(self) -> str:
        if not self.is_approved:
            raise ValueError("Kịch bản chưa được duyệt cho phiên bản hiện tại.")
        assert self.approved_revision_hash is not None
        return self.approved_revision_hash

    @property
    def state(self) -> str:
        if self.script is not None:
            if self.voice_ready:
                return "VOICE_READY"
            return "APPROVED" if self.is_approved else "REVIEW_REQUIRED"
        if self.translation is not None:
            return "REVIEW_REQUIRED"
        if self.transcript is not None:
            return "TRANSCRIBED"
        return "VIDEO_IMPORTED" if self.video_path else "IDLE"
