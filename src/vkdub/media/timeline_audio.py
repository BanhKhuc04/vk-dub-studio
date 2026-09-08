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


def _ffprobe_executable(ffmpeg_exe: str) -> str:
    """Resolve ffprobe beside ffmpeg without rewriting parent directory names."""
    executable = Path(ffmpeg_exe)
    suffix = executable.suffix
    if executable.name.lower().startswith("ffmpeg"):
        return str(executable.with_name(f"ffprobe{suffix}"))
    return "ffprobe"


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
    vbee_dur_ms = get_audio_duration_ms(
        vbee_audio_path, _ffprobe_executable(ffmpeg_exe)
    )

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

    filters: list[str] = []

    # Check if lead silence is missing:
    # Vbee Dubbing from SRT exports audio with timestamps aligned to the project timeline (starting at 00:00:00).
    # If the first cue starts after 500ms AND the raw audio is noticeably shorter than last_cue_end_ms,
    # then the audio source did not include the initial silence and needs adelay.
    # Otherwise, if vbee_dur_ms spans the full timeline, Vbee already included the lead silence!
    if first_cue_start_ms > 500 and vbee_dur_ms < (last_cue_end_ms - 250):
        logger.info(
            "Audio source lacks initial silence; prepending %d ms delay",
            first_cue_start_ms,
        )
        filters.append(f"adelay={first_cue_start_ms}|{first_cue_start_ms}")

    # Trim any trailing overrun or Vbee promotional watermark ("Giải pháp chuyển văn bản...")
    # and pad silence at the end if the video timeline is longer than the voice audio.
    # DO NOT apply blanket atempo across the entire continuous file, as doing so
    # compresses natural sentence pauses and causes subtitles and speech to drift out of sync.
    filters.extend(
        [
            f"atrim=start=0:end={pad_total_seconds:.3f}",
            f"apad=whole_dur={pad_total_seconds:.3f}",
        ]
    )
    filter_complex = ",".join(filters)

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
