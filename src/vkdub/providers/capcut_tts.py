"""CapCut SDK in an owned, cancellable worker; shares the existing audio/cache pipeline."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from vkdub.domain.voice import Voice
from vkdub.media.voice_audio import run_audio_command
from vkdub.providers.tts import TTSError
from vkdub.providers.vieneu_local import VieNeuLocalProvider
from vkdub.services.capcut_setup import capcut_root
from vkdub.services.voice_catalog import find_voice, read_catalog


class CapCutTTSProvider(VieNeuLocalProvider):
    id = name = "capcut_tts"
    display_name = "CapCut TTS"
    max_characters = 500
    sample_rate = 48000

    async def _start(self) -> None:
        if self.process is not None:
            return
        root = capcut_root()
        if not (root / "capcut_tts_api" / "client.py").is_file():
            raise TTSError("Bấm Kết nối CapCut trong Cài đặt Voice để chuẩn bị giọng đọc.")
        self.process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-u",
            str(Path(__file__).with_name("capcut_worker.py")),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=dict(os.environ, PYTHONPATH=str(root), PYTHONUTF8="1"),
            creationflags=0x08000000 if os.name == "nt" else 0,
        )

    async def request(self, operation: str, **arguments: Any) -> dict[str, Any]:
        try:
            async with asyncio.timeout(150):
                return await super().request(operation, **arguments)
        except TimeoutError:
            raise TTSError("CapCut chờ quá lâu. Thử lại hoặc dùng VieNeu offline.") from None

    async def list_voices(self) -> tuple[Voice, ...]:
        return tuple(Voice(r["id"], r["name"], "vi") for r in read_catalog(self.name))

    async def synthesize(self, text: str, voice_id: str, speed: float, output_path: Path) -> Path:
        if not text.strip() or not 0.8 <= speed <= 1.3:
            raise TTSError("Nội dung hoặc tốc độ đọc không hợp lệ.")
        voice = find_voice(voice_id, self.name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="capcut-", dir=output_path.parent) as folder:
            raw = Path(folder) / "source.mp3"
            await self.request("synthesize", text=text, voice=voice, output=str(raw))
            await run_audio_command(
                [
                    self.ffmpeg,
                    "-y",
                    "-nostdin",
                    "-v",
                    "error",
                    "-i",
                    str(raw),
                    "-af",
                    f"atempo={speed}",
                    "-ar",
                    str(self.sample_rate),
                    "-c:a",
                    "pcm_s16le",
                    str(output_path),
                ]
            )
        return output_path
