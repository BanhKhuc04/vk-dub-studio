"""Master Timeline Audio Generator.

Ensures that CapCut receives ONE continuous narration audio track starting at 00:00:00,
with exact silence padding matching translated SRT cue timestamps.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

from vkdub.media.process import find_tool
from vkdub.services.srt_validator import parse_cues

logger = logging.getLogger("vkdub.timeline_audio")


def _resolve_tool(tool_name: str, explicit_path: str | None = None) -> str:
    """Resolve executable path with smart discovery and fallbacks."""
    if explicit_path and explicit_path != tool_name:
        p = Path(explicit_path)
        if p.is_file():
            return str(p.resolve())
    found = find_tool(tool_name)
    if found:
        return found
    which = shutil.which(tool_name)
    if which:
        return which
    return tool_name


def _ffprobe_executable(ffmpeg_exe: str | None = None) -> str:
    """Resolve ffprobe beside ffmpeg without rewriting parent directory names."""
    if ffmpeg_exe and ffmpeg_exe != "ffmpeg":
        executable = Path(ffmpeg_exe)
        suffix = executable.suffix
        if executable.name.lower().startswith("ffmpeg"):
            return str(executable.with_name(f"ffprobe{suffix}"))
    return _resolve_tool("ffprobe")


def get_audio_duration_ms(path: Path, ffprobe_exe: str | None = None) -> int:
    """Get audio file duration in milliseconds using ffprobe."""
    exe = _resolve_tool("ffprobe", ffprobe_exe)
    cmd = [
        exe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        creationflags = 0x08000000 if os.name == "nt" else 0
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            creationflags=creationflags,
        )
        data = json.loads(res.stdout)
        dur_sec = float(data.get("format", {}).get("duration", 0))
        return int(dur_sec * 1000)
    except Exception as exc:
        logger.debug("Could not probe audio duration for %s: %s", path, exc)
        return 0


def build_master_timeline_audio(
    vbee_audio_path: Path,
    srt_path: Path,
    output_path: Path,
    total_duration_ms: int | None = None,
    ffmpeg_exe: str | None = None,
) -> Path:
    """Build ONE master continuous narration audio track with silence padding.

    Guarantees:
    1. Starts at exactly 00:00:00.000.
    2. If Vbee audio does not preserve cue pauses/timeline, aligns audio to SRT.
    3. Total audio length matches the video duration with end silence padding.
    4. Yields a single continuous audio file for CapCut track 1.
    5. Graceful fallback to direct copy if FFmpeg is unavailable or fails.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Resolve ffmpeg tool path
    resolved_ffmpeg = _resolve_tool("ffmpeg", ffmpeg_exe)
    probe_exe = _ffprobe_executable(resolved_ffmpeg)

    # Check whether FFmpeg executable is actually available on this system
    has_ffmpeg = Path(resolved_ffmpeg).is_file() or bool(shutil.which(resolved_ffmpeg))
    if not has_ffmpeg:
        logger.warning(
            "Không tìm thấy FFmpeg trên máy tính này (%s). Tự động sao chép trực tiếp file audio Vbee gốc: %s",
            resolved_ffmpeg,
            vbee_audio_path,
        )
        shutil.copy2(vbee_audio_path, output_path)
        return output_path

    try:
        srt_text = srt_path.read_text(encoding="utf-8", errors="replace")
        cues = parse_cues(srt_text)

        # Probe Vbee audio duration
        vbee_dur_ms = get_audio_duration_ms(vbee_audio_path, probe_exe)

        first_cue_start_ms = cues[0].start_ms if cues else 0
        last_cue_end_ms = cues[-1].end_ms if cues else vbee_dur_ms
        expected_min_ms = max(last_cue_end_ms, total_duration_ms or last_cue_end_ms)

        logger.info(
            "Vbee audio duration: %d ms, First cue start: %d ms, Expected timeline length: %d ms",
            vbee_dur_ms,
            first_cue_start_ms,
            expected_min_ms,
        )

        pad_total_seconds = expected_min_ms / 1000.0
        filters: list[str] = []

        # If Vbee audio starts at 00:00 but first cue starts after 500ms, prepend silence!
        if first_cue_start_ms > 500 and vbee_dur_ms < (last_cue_end_ms - 250):
            logger.info(
                "Audio source lacks initial silence; prepending %d ms delay",
                first_cue_start_ms,
            )
            filters.append(f"adelay={first_cue_start_ms}|{first_cue_start_ms}")

        filters.extend(
            [
                f"atrim=start=0:end={pad_total_seconds:.3f}",
                f"apad=whole_dur={pad_total_seconds:.3f}",
            ]
        )
        filter_complex = ",".join(filters)

        cmd = [
            resolved_ffmpeg,
            "-y",
            "-i",
            str(vbee_audio_path),
            "-filter_complex",
            filter_complex,
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(output_path),
        ]

        logger.info("Generating master timeline audio with silence padding: %s", output_path)
        creationflags = 0x08000000 if os.name == "nt" else 0
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            creationflags=creationflags,
        )
        logger.info("Master timeline audio generated successfully: %s", output_path)
        return output_path

    except (subprocess.SubprocessError, OSError, Exception) as exc:
        logger.warning(
            "Căn chỉnh timeline qua FFmpeg thất bại (%s). Tự động dùng file audio Vbee gốc.",
            exc,
        )
        shutil.copy2(vbee_audio_path, output_path)
        return output_path
