"""Extract 16kHz mono WAV audio from video files using FFmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path

from vkdub.media.process import find_tool


def extract_audio(video_path: Path, output_wav: Path) -> Path:
    """Extract 16kHz mono WAV from video using FFmpeg."""
    ffmpeg = find_tool("ffmpeg") or "ffmpeg"
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output_wav),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_wav
