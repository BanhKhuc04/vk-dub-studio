import asyncio
import json
import math
import subprocess
import sys
from pathlib import Path


async def run_audio_command(args: list[str], timeout: int = 60) -> bytes:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout)
        if process.returncode:
            raise ValueError("FFmpeg/ffprobe không đọc được voice. Audio cũ được giữ nguyên.")
        return stdout
    finally:
        if process.returncode is None:
            process.kill()
            await process.communicate()


async def audio_duration(path: Path, ffprobe: str) -> int:
    raw = await run_audio_command(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type",
            "-of",
            "json",
            str(path),
        ],
        15,
    )
    try:
        data = json.loads(raw)
        duration = float(data["format"]["duration"])
        if (
            not any(s.get("codec_type") == "audio" for s in data["streams"])
            or not math.isfinite(duration)
            or not 0 < duration <= 86_400
        ):
            raise ValueError
        return max(1, round(duration * 1000))
    except (ValueError, KeyError, TypeError):
        raise ValueError("Audio thiếu thời lượng hợp lệ từ ffprobe.") from None


async def assemble_audio(
    parts: list[Path], directory: Path, ffmpeg: str, ffprobe: str, *, sample_rate: int = 24000
) -> tuple[Path, int]:
    # Convert each chunk to the same PCM format; concatenate samples without lossy re-encoding.
    import wave

    output = directory / "line.wav"
    with wave.open(str(output), "wb") as joined:
        joined.setparams((1, 2, sample_rate, 0, "NONE", "not compressed"))
        for index, part in enumerate(parts):
            pcm = directory / f"decoded-{index}.wav"
            await run_audio_command(
                [
                    ffmpeg,
                    "-nostdin",
                    "-v",
                    "error",
                    "-i",
                    str(part),
                    "-map",
                    "0:a:0",
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    str(sample_rate),
                    "-c:a",
                    "pcm_s16le",
                    "-y",
                    str(pcm),
                ]
            )
            with wave.open(str(pcm), "rb") as source:
                while data := source.readframes(65536):
                    joined.writeframesraw(data)
            pcm.unlink()
    return output, await audio_duration(output, ffprobe)
