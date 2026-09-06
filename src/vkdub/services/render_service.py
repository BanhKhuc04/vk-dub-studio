import re
from dataclasses import dataclass
from pathlib import Path

from vkdub.domain.project import Project
from vkdub.services.audio_mix_service import build_audio_mix_filter
from vkdub.services.mask_service import build_ffmpeg_mask_filter


@dataclass
class RenderConfig:
    output_path: Path
    burn_subtitles: bool = True
    apply_masks: bool = True
    original_volume: float = 0.15  # 15% ducking
    voice_volume: float = 1.0  # 100% voice
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 20
    preset: str = "medium"


def escape_ffmpeg_filter_path(path: Path) -> str:
    """Escape Windows file paths for FFmpeg filter arguments."""
    p = str(path.resolve()).replace("\\", "/")
    # Escape colon (e.g. C:/ -> C\\:/)
    p = p.replace(":", "\\:")
    p = p.replace("'", "'\\''")
    return p


def build_render_command(
    project: Project,
    config: RenderConfig,
    speech_wav_path: Path,
    ass_subtitle_path: Path | None,
    ffmpeg_exe: str,
    video_width: int = 1920,
    video_height: int = 1080,
    has_original_audio: bool = True,
) -> list[str]:
    """Assemble complete FFmpeg argument list for final rendering."""
    if not project.video_path or not project.video_path.is_file():
        raise ValueError("Video nguồn không tồn tại.")

    args: list[str] = [
        ffmpeg_exe,
        "-y",
        "-nostdin",
        "-i",
        str(project.video_path),
        "-i",
        str(speech_wav_path),
    ]

    # 1. Video Filter Chain
    vf_items: list[str] = []
    if config.apply_masks and project.masks:
        mask_filter = build_ffmpeg_mask_filter(project.masks, video_width, video_height)
        if mask_filter:
            vf_items.append(mask_filter)

    if config.burn_subtitles and ass_subtitle_path and ass_subtitle_path.is_file():
        esc_path = escape_ffmpeg_filter_path(ass_subtitle_path)
        vf_items.append(f"ass='{esc_path}'")

    if vf_items:
        full_vf = ",".join(vf_items)
        args.extend(["-vf", full_vf])

    # 2. Audio Filter Complex
    af_graph = build_audio_mix_filter(
        original_volume=config.original_volume,
        voice_volume=config.voice_volume,
        has_original_audio=has_original_audio,
    )
    args.extend(["-filter_complex", af_graph, "-map", "0:v:0", "-map", "[aout]"])

    # 3. Codecs & Quality
    args.extend(
        [
            "-c:v",
            config.video_codec,
            "-crf",
            str(config.crf),
            "-preset",
            config.preset,
            "-c:a",
            config.audio_codec,
            "-b:a",
            "192k",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
            str(config.output_path),
        ]
    )

    return args


def parse_ffmpeg_progress(stderr_line: str, total_duration_s: float) -> float | None:
    """Parse FFmpeg stderr output lines to compute rendering percentage (0.0 to 100.0)."""
    match = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", stderr_line)
    if match and total_duration_s > 0:
        h = int(match.group(1))
        m = int(match.group(2))
        s = float(match.group(3))
        current_s = h * 3600 + m * 60 + s
        return min(100.0, max(0.0, (current_s / total_duration_s) * 100.0))
    return None
