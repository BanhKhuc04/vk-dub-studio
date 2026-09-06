from pathlib import Path
from typing import Protocol

from vkdub.domain.voice import Voice


class TTSError(ValueError):
    """Actionable, credential-free provider error."""


class TextToSpeechProvider(Protocol):
    name: str
    max_characters: int

    async def list_voices(self) -> tuple[Voice, ...]: ...

    async def synthesize(
        self, text: str, voice_id: str, speed: float, output_path: Path
    ) -> Path: ...
