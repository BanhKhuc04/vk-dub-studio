from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class Voice:
    id: str
    name: str
    gender: str = "female"
    language: str = "vi"
    is_custom: bool = False
    description: str = ""


@dataclass
class HealthResult:
    ok: bool
    code: str
    title: str
    message: str
    action_label: str | None = None
    action_id: str | None = None


class TTSProvider(Protocol):
    id: str
    display_name: str

    def health_check(self) -> HealthResult: ...

    def list_voices(self) -> list[Voice]: ...

    def preview_voice(self, text: str, voice_id: str, speed: float) -> Path: ...

    def synthesize(self, text: str, voice_id: str, speed: float, output_path: Path) -> Path: ...
