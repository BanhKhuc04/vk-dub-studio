"""VieNeu v3 Turbo adapter, isolated from Qt and the app's STT dependencies."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from vkdub.domain.voice import Voice
from vkdub.providers.tts import TTSError
from vkdub.services.voice_catalog import engine_python, engine_root, find_voice, read_catalog


async def stop_owned_process(process: asyncio.subprocess.Process) -> None:
    """Windows venv launchers spawn a child: stop only this owned process tree."""
    if process.returncode is None:
        if os.name == "nt":
            killer = await asyncio.create_subprocess_exec(
                "taskkill.exe",
                "/PID",
                str(process.pid),
                "/T",
                "/F",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                creationflags=0x08000000,
            )
            await killer.wait()
        elif process.returncode is None:
            process.kill()
    await process.wait()


class VieNeuLocalProvider:
    id = name = "vieneu_local"
    display_name = "VieNeu Local"
    max_characters = 600
    audio_suffix = ".wav"
    sample_rate = 48000

    def __init__(self, ffmpeg: str = "", *, allow_download: bool = False) -> None:
        self.ffmpeg = ffmpeg
        self.allow_download = allow_download
        self.process: asyncio.subprocess.Process | None = None

    async def _start(self) -> None:
        if self.process is not None:
            return
        python = engine_python()
        if not python.is_file():
            raise TTSError("VieNeu chưa được cài. Mở Cài đặt → Voice → Cài VieNeu.")
        root = engine_root()
        env = dict(
            os.environ,
            PYTHONUTF8="1",
            HF_HOME=str(root / "models"),
            HF_HUB_DISABLE_TELEMETRY="1",
            HF_HUB_DISABLE_PROGRESS_BARS="1",
        )
        if not self.allow_download:
            env["HF_HUB_OFFLINE"] = "1"
        else:
            env.pop("HF_HUB_OFFLINE", None)
        log = root / "voice-worker.log"
        if log.is_file() and log.stat().st_size > 2_000_000:
            log.replace(root / "voice-worker.previous.log")
        with log.open("ab") as errors:
            self.process = await asyncio.create_subprocess_exec(
                str(python),
                "-u",
                str(Path(__file__).with_name("vieneu_worker.py")),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=errors,
                env=env,
                creationflags=0x08000000 if os.name == "nt" else 0,
            )

    async def request(self, operation: str, **arguments: Any) -> dict[str, Any]:
        try:
            await self._start()
            assert self.process and self.process.stdin and self.process.stdout
            self.process.stdin.write(
                (json.dumps({"operation": operation, **arguments}) + "\n").encode()
            )
            await self.process.stdin.drain()
            async with asyncio.timeout(1800 if self.allow_download else 600):
                while line := await self.process.stdout.readline():
                    if not line.startswith(b"VKDUB_RESULT "):
                        continue
                    response = json.loads(line[len(b"VKDUB_RESULT ") :])
                    if not response["ok"]:
                        raise TTSError(response["error"])
                    return dict(response["result"])
            raise TTSError("Tiến trình VieNeu đã dừng. Xem log Voice rồi thử lại.")
        except asyncio.CancelledError:
            await self.close()
            raise
        except TimeoutError:
            await self.close()
            raise TTSError(
                "VieNeu quá thời gian xử lý. Thử câu ngắn hơn hoặc kiểm tra log Voice."
            ) from None
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            raise TTSError("Không kết nối được Voice Engine cục bộ. Hãy kiểm tra cài đặt.") from exc

    async def close(self) -> None:
        if self.process is not None:
            process, self.process = self.process, None
            await stop_owned_process(process)

    async def list_voices(self) -> tuple[Voice, ...]:
        return tuple(Voice(r["id"], r["name"], "vi") for r in read_catalog())

    async def synthesize(self, text: str, voice_id: str, speed: float, output_path: Path) -> Path:
        if not text.strip() or not 0.8 <= speed <= 1.3:
            raise TTSError("Nội dung hoặc tốc độ đọc không hợp lệ.")
        voice = find_voice(voice_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="vieneu-", dir=output_path.parent) as folder:
            raw = Path(folder) / "source.wav"
            await self.request("synthesize", text=text, voice=voice, output=str(raw))
            if not raw.is_file() or raw.stat().st_size < 100:
                raise TTSError("VieNeu chưa tạo được âm thanh hợp lệ.")
            # Reuse the existing cache/assembly path while preserving pitch at user speed.
            from vkdub.media.voice_audio import run_audio_command

            codec = (
                ["-c:a", "pcm_s16le"]
                if output_path.suffix.lower() == ".wav"
                else ["-c:a", "libmp3lame", "-b:a", "192k"]
            )
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
                    *codec,
                    str(output_path),
                ]
            )
        return output_path
