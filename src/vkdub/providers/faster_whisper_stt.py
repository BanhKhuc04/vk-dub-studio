from pathlib import Path
from typing import Any

from vkdub.domain.transcript import SubtitleSegment
from vkdub.providers.base import Progress


class FasterWhisperSTT:
    def __init__(self, model_path: Path, device: str) -> None:
        # Imported only in the isolated worker, never during UI startup.
        from faster_whisper import WhisperModel

        self.model: Any = WhisperModel(
            str(model_path),
            device=device,
            compute_type="int8" if device == "cpu" else "float16",
            local_files_only=True,
            cpu_threads=4,
        )

    def transcribe(
        self, audio: Path, language: str, progress: Progress
    ) -> tuple[tuple[SubtitleSegment, ...], str, float]:
        stream, info = self.model.transcribe(
            str(audio),
            language=None if language == "auto" else language,
            task="transcribe",
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        segments: list[SubtitleSegment] = []
        for item in stream:
            start = max(float(item.start), segments[-1].end if segments else 0.0)
            end = min(float(item.end), float(info.duration))
            text = str(item.text).strip()
            if text and end > start:
                segments.append(SubtitleSegment(len(segments) + 1, start, end, text))
            percent = min(99, round(100 * end / max(float(info.duration), 0.001)))
            progress(percent, f"Đã bóc băng {end:.1f} / {info.duration:.1f} giây")
        return tuple(segments), str(info.language), float(info.duration)
