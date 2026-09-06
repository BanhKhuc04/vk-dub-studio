from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from vkdub.domain.transcript import SubtitleSegment

Progress = Callable[[int, str], None]


class SpeechToTextProvider(Protocol):
    def transcribe(
        self, audio: Path, language: str, progress: Progress
    ) -> tuple[tuple[SubtitleSegment, ...], str, float]: ...
