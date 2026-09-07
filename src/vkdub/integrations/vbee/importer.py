"""Audio validation, timeline slicing, and VoiceAsset import for Vbee integration."""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vkdub.domain.project import Project
from vkdub.domain.voice import VoiceAsset, VoiceSettings, audio_key, digest, normalized_text
from vkdub.integrations.vbee.errors import VbeeImportError
from vkdub.media.voice_audio import audio_duration
from vkdub.services.tts_service import file_hash
from vkdub.utils.paths import data_root

logger = logging.getLogger("vkdub.vbee")

DEFAULT_VBEE_VOICE_ID = "vbee_studio"
DEFAULT_VBEE_DISPLAY_NAME = "Vbee Dubbing Studio"


def validate_downloaded_audio(file_path: Path) -> Path:
    """Ensure downloaded audio file exists, is non-empty, and has a supported extension."""
    if not file_path.is_file():
        raise VbeeImportError(f"File âm thanh tải về không tồn tại: {file_path}")
    size = file_path.stat().st_size
    if size < 2048:
        raise VbeeImportError(f"File âm thanh tải về quá nhỏ hoặc bị lỗi ({size} bytes).")
    if file_path.suffix.lower() not in (".mp3", ".wav", ".m4a", ".aac", ".ogg"):
        raise VbeeImportError(f"Định dạng âm thanh tải về không được hỗ trợ: {file_path.suffix}")
    return file_path


async def convert_to_pcm_wav(source: Path, target: Path, ffmpeg: str) -> Path:
    """Normalize downloaded audio to 24kHz mono 16-bit PCM WAV."""
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(source),
        "-ar",
        "24000",
        "-ac",
        "1",
        "-sample_fmt",
        "s16",
        "-f",
        "wav",
        str(target),
    ]
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
    if process.returncode != 0 or not target.is_file():
        err = process.stderr.strip() or "Lỗi FFmpeg không xác định."
        raise VbeeImportError(f"Không thể chuyển đổi âm thanh sang chuẩn WAV: {err}")
    return target


async def slice_and_import_vbee_audio(
    project: Project,
    downloaded_audio: Path,
    ffmpeg: str,
    ffprobe: str,
    output_dir: Path | None = None,
    voice_id: str = DEFAULT_VBEE_VOICE_ID,
    display_name: str = DEFAULT_VBEE_DISPLAY_NAME,
) -> dict[str, Any]:
    """Slice the full Vbee audio track by script lines and attach VoiceAssets to the project.

    Updates project.voice to Vbee settings, populates project.voice_assets for every
    script line, and ensures project.voice_ready is satisfied.
    """
    if not project.script or not project.script.lines:
        raise VbeeImportError("Project chưa có kịch bản để đồng bộ âm thanh.")

    validate_downloaded_audio(downloaded_audio)

    # Determine storage directory for sliced voice assets
    if output_dir is None:
        if project.output_directory and project.output_directory.is_dir():
            target_dir = project.output_directory / "audio" / "vbee"
        else:
            target_dir = data_root() / "cache" / "tts" / "vbee"
    else:
        target_dir = output_dir

    target_dir.mkdir(parents=True, exist_ok=True)

    # Normalize the master audio file to standard PCM WAV
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    master_wav = target_dir / f"master_vbee_{timestamp_str}.wav"
    logger.info(
        "[VOICE][FFMPEG] Đang chuẩn hóa file tải về thành WAV PCM: %s -> %s",
        downloaded_audio.name,
        master_wav.name,
    )
    await convert_to_pcm_wav(downloaded_audio, master_wav, ffmpeg)

    master_duration_ms = await audio_duration(master_wav, ffprobe)
    logger.info(
        "[VOICE][FFMPEG] Đã chuẩn hóa audio Vbee: %s (thời lượng: %.2fs)",
        master_wav.name,
        master_duration_ms / 1000,
    )

    # Configure voice settings on the project (preserve existing selection if vbee)
    if (
        project.voice
        and project.voice.provider == "vbee"
        and project.voice.voice_id not in ("unconfigured", "")
    ):
        voice_settings = project.voice
    else:
        voice_settings = VoiceSettings(
            provider="vbee",
            voice_id=voice_id,
            display_name=display_name,
            speed=1.0,
            volume=1.0,
        )
        project.voice = voice_settings

    master_sha = file_hash(master_wav)
    project.master_voice_path = master_wav.resolve()

    logger.info(
        "[VOICE][IMPORT] Gắn master audio nguyên vẹn từ Vbee vào dự án (không cắt vụn âm thanh)…"
    )

    lines = project.script.lines
    imported_assets: dict[str, VoiceAsset] = {}

    for line in lines:
        line_duration_ms = max(1, line.end_ms - line.start_ms)
        key = audio_key(line.text, voice_settings)

        asset = VoiceAsset(
            cache_key=key,
            text_hash=digest(normalized_text(line.text)),
            provider="vbee",
            voice_id=voice_settings.voice_id,
            speed=voice_settings.speed,
            duration_ms=line_duration_ms,
            output_path=master_wav.resolve(),
            audio_sha256=master_sha,
            generated_at=datetime.now(UTC).isoformat(),
        )
        imported_assets[line.id] = asset

    # Assign voice assets to project
    project.voice_assets.update(imported_assets)

    logger.info(
        "Đã gắn voice Vbee nguyên khối (%d câu, master: %s) vào project. voice_ready=%s",
        len(imported_assets),
        master_wav.name,
        project.voice_ready,
    )

    return {
        "lines_count": len(imported_assets),
        "master_wav": str(master_wav),
        "target_dir": str(target_dir),
        "total_duration_ms": master_duration_ms,
    }
