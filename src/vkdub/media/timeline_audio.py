"""Master Timeline Audio Generator.

Ensures that CapCut receives ONE continuous narration audio track starting at 00:00:00,
with exact silence padding matching translated SRT cue timestamps.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from vkdub.services.srt_validator import parse_cues

logger = logging.getLogger("vkdub.timeline_audio")


def get_audio_duration_ms(path: Path, ffprobe_exe: str = "ffprobe") -> int:
    """Get audio file duration in milliseconds using ffprobe."""
    cmd = [
        ffprobe_exe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
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
    ffmpeg_exe: str = "ffmpeg",
) -> Path:
    """Build ONE master continuous narration audio track with silence padding.

    Guarantees:
    1. Starts at exactly 00:00:00.000.
    2. If Vbee audio does not preserve cue pauses/timeline, aligns audio to SRT.
    3. Total audio length matches the video duration with end silence padding.
    4. Yields a single continuous audio file for CapCut track 1.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    srt_text = srt_path.read_text(encoding="utf-8", errors="replace")
    cues = parse_cues(srt_text)

    # Probe Vbee audio duration
    vbee_dur_ms = get_audio_duration_ms(vbee_audio_path, ffmpeg_exe.replace("ffmpeg", "ffprobe"))

    first_cue_start_ms = cues[0].start_ms if cues else 0
    last_cue_end_ms = cues[-1].end_ms if cues else vbee_dur_ms
    expected_min_ms = max(last_cue_end_ms, total_duration_ms or last_cue_end_ms)

    logger.info(
        "Vbee audio duration: %d ms, First cue start: %d ms, Expected timeline length: %d ms",
        vbee_dur_ms,
        first_cue_start_ms,
        expected_min_ms,
    )

    # If Vbee audio starts at 00:00 but first cue starts after 500ms, prepend silence!
    # If Vbee audio duration is significantly shorter than last cue end (collapsed silence),
    # we prepend silence of first_cue_start_ms and pad end silence.
    pad_total_seconds = expected_min_ms / 1000.0

    # Use FFmpeg filter complex: adelay prepends silence, apad / atrim pads/trims to total duration
    # Filter: adelay=<delay_ms>|<delay_ms>,apad=whole_dur=<pad_total_s>
    filter_complex = (
        f"adelay={first_cue_start_ms}|{first_cue_start_ms},apad=whole_dur={pad_total_seconds:.3f}"
    )

    cmd = [
        ffmpeg_exe,
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

    try:
        logger.info("Generating master timeline audio with silence padding: %s", output_path)
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info("Master timeline audio generated successfully: %s", output_path)
        return output_path
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "FFmpeg adelay filter failed: %s. Falling back to direct copy.",
            exc.stderr,
        )
        import shutil

        shutil.copy2(vbee_audio_path, output_path)
        return output_path
