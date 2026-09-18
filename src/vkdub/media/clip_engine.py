"""Clip trimming, merging, timecode parsing, and Windows path sanitization engine."""

import os
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Final

from vkdub.media.hardware import HardwareEncoderDetector
from vkdub.media.process import find_tool

# Reserved Windows file stems (case-insensitive)
WINDOWS_RESERVED: Final[set[str]] = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def kill_process_tree(pid: int) -> None:
    """Safely terminate a process and all of its child processes."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,
        )
    else:
        import signal

        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def sanitize_filename(name: str, max_length: int = 100, replacement: str = "_") -> str:
    """Sanitize arbitrary strings (such as YouTube video titles) for Windows filesystems.

    Guarantees:
    - Replaces path separators and traversal indicators.
    - Strips Windows illegal characters: < > : " / \\ | ? * and ASCII controls 0x00-0x1F.
    - Strips leading and trailing dots and spaces.
    - Prevents collision with Windows reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9).
    - Truncates to max_length without leaving trailing dots or spaces.
    - Fallback for empty strings to 'clip'.
    """
    if not name:
        return "clip"

    # 1. Replace slashes and path traversal
    clean = name.replace("\\", replacement).replace("/", replacement)

    # 2. Strip Windows illegal characters and control characters
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', replacement, clean)

    # 3. Strip leading and trailing dots and spaces
    clean = clean.strip(" .")

    # 4. Check against Windows reserved device names
    stem = clean.split(".")[0].upper()
    if stem in WINDOWS_RESERVED:
        clean = f"_{clean}"

    # 5. Fallback if empty after sanitization
    if not clean:
        clean = "clip"

    # 6. Truncate to max_length to avoid Windows MAX_PATH limits
    if len(clean) > max_length:
        clean = clean[:max_length].rstrip(" .")
        if not clean:
            clean = "clip"

    return clean


def format_timecode_for_filename(seconds: float) -> str:
    """Format seconds into a Windows filename-safe time string (e.g. '01m30s' or '45s')."""
    s = max(0.0, float(seconds))
    hrs = int(s // 3600)
    mins = int((s % 3600) // 60)
    secs = s % 60

    if hrs > 0:
        return f"{hrs:02d}h{mins:02d}m{secs:04.1f}s".replace(".0s", "s")
    if mins > 0:
        return f"{mins:02d}m{secs:04.1f}s".replace(".0s", "s")
    return f"{secs:.1f}s".replace(".0s", "s")


def build_clip_filename(
    video_title: str,
    clip_index: int,
    start_sec: float | str,
    end_sec: float | str,
    container: str = "mp4",
) -> str:
    """Build a sanitized filename for an individual exported clip segment."""
    start_val = parse_timecode(start_sec) if isinstance(start_sec, str) else float(start_sec)
    end_val = parse_timecode(end_sec) if isinstance(end_sec, str) else float(end_sec)

    start_str = format_timecode_for_filename(start_val)
    end_str = format_timecode_for_filename(end_val)

    clean_title = sanitize_filename(video_title, max_length=60)
    clean_ext = container.lstrip(".").lower()
    return f"{clean_title}_clip_{clip_index}_{start_str}-{end_str}.{clean_ext}"


def build_merged_filename(video_title: str, container: str = "mp4") -> str:
    """Build a sanitized filename for merged clips."""
    clean_title = sanitize_filename(video_title, max_length=60)
    clean_ext = container.lstrip(".").lower()
    return f"{clean_title}_selected_clips.{clean_ext}"


def parse_timecode(value: str | int | float) -> float:
    """Parse timecode into seconds as float.

    Accepts:
    - Numeric seconds: 45, 120.5
    - HH:MM:SS or HH:MM:SS.mmm: '01:23:45.678'
    - MM:SS or MM:SS.mmm: '05:30.500'
    - Formatted string seconds: '45s', '120.5S'
    """
    if isinstance(value, (int, float)):
        val = float(value)
        if val < 0:
            raise ValueError(f"Timecode cannot be negative: {value}")
        return val

    if not isinstance(value, str):
        raise TypeError(f"Expected str, int, or float for timecode, got {type(value).__name__}")

    s = value.strip()
    if not s:
        raise ValueError("Timecode string cannot be empty")

    if s.endswith(("s", "S")):
        s = s[:-1].strip()

    if s.startswith("-"):
        raise ValueError(f"Timecode cannot be negative: {value}")

    if ":" in s:
        parts = s.split(":")
        if any(p.strip().startswith("-") for p in parts):
            raise ValueError(f"Timecode parts cannot be negative: {value}")
        if len(parts) == 3:
            h, m, sec = float(parts[0]), float(parts[1]), float(parts[2])
            if h < 0 or m < 0 or sec < 0:
                raise ValueError(f"Timecode parts cannot be negative: {value}")
            return h * 3600.0 + m * 60.0 + sec
        elif len(parts) == 2:
            m, sec = float(parts[0]), float(parts[1])
            if m < 0 or sec < 0:
                raise ValueError(f"Timecode parts cannot be negative: {value}")
            return m * 60.0 + sec
        else:
            raise ValueError(f"Invalid timecode format: {value}")

    try:
        val = float(s)
        if val < 0:
            raise ValueError(f"Timecode cannot be negative: {value}")
        return val
    except ValueError as e:
        raise ValueError(f"Cannot parse timecode '{value}': {e}") from e


def format_timecode(seconds: float, include_ms: bool = True) -> str:
    """Format seconds into HH:MM:SS.mmm or HH:MM:SS format."""
    s = max(0.0, float(seconds))
    hrs = int(s // 3600)
    mins = int((s % 3600) // 60)
    rem_secs = s % 60
    if include_ms:
        secs_int = int(rem_secs)
        ms = int(round((rem_secs - secs_int) * 1000))
        if ms >= 1000:
            secs_int += 1
            ms = 0
        return f"{hrs:02d}:{mins:02d}:{secs_int:02d}.{ms:03d}"
    else:
        secs_int = int(round(rem_secs))
        if secs_int >= 60:
            mins += 1
            secs_int = 0
        return f"{hrs:02d}:{mins:02d}:{secs_int:02d}"


def build_stream_copy_trim_command(
    ffmpeg_exe: str,
    source_path: Path,
    output_path: Path,
    start_sec: float,
    end_sec: float,
) -> list[str]:
    """Construct FFmpeg stream-copy trimming command.

    -ss {start} -to {end} -i {src} -c copy -avoid_negative_ts make_zero
    """
    cmd = [
        ffmpeg_exe,
        "-y",
        "-nostdin",
        "-ss",
        f"{start_sec:.3f}",
        "-to",
        f"{end_sec:.3f}",
        "-i",
        str(source_path),
        "-c",
        "copy",
        "-avoid_negative_ts",
        "make_zero",
    ]
    if output_path.suffix.lower() == ".mp4":
        cmd.extend(["-movflags", "+faststart"])
    cmd.append(str(output_path))
    return cmd


def build_frame_accurate_trim_command(
    ffmpeg_exe: str,
    source_path: Path,
    output_path: Path,
    start_sec: float,
    end_sec: float,
    encoder_name: str,
    encoder_args: list[str] | None = None,
    audio_codec: str = "aac",
    audio_bitrate: str = "192k",
) -> list[str]:
    """Construct FFmpeg frame-accurate re-encoding trim command.

    -ss {start} -to {end} -i {src} -c:v {encoder} {encoder_args} -c:a aac -b:a 192k
    """
    cmd = [
        ffmpeg_exe,
        "-y",
        "-nostdin",
        "-ss",
        f"{start_sec:.3f}",
        "-to",
        f"{end_sec:.3f}",
        "-i",
        str(source_path),
        "-c:v",
        encoder_name,
    ]
    if encoder_args:
        cmd.extend(encoder_args)
    else:
        cmd.extend(["-crf", "18", "-pix_fmt", "yuv420p"])

    cmd.extend([
        "-c:a",
        audio_codec,
        "-b:a",
        audio_bitrate,
    ])
    if output_path.suffix.lower() == ".mp4":
        cmd.extend(["-movflags", "+faststart"])
    cmd.append(str(output_path))
    return cmd


def create_concat_manifest(clip_paths: list[Path], manifest_path: Path) -> Path:
    """Create FFmpeg concat demuxer manifest file.

    Format:
    ffconcat version 1.0
    file 'path/to/clip.mp4'
    """
    if not clip_paths:
        raise ValueError("clip_paths cannot be empty for concat manifest")

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["ffconcat version 1.0\n"]
    for clip in clip_paths:
        # Use forward slashes and escape single quotes for cross-platform compatibility
        clean_path = str(clip.resolve().as_posix()).replace("'", "\\'")
        lines.append(f"file '{clean_path}'\n")

    manifest_path.write_text("".join(lines), encoding="utf-8")
    return manifest_path


def build_concat_command(
    ffmpeg_exe: str,
    manifest_path: Path,
    output_path: Path,
) -> list[str]:
    """Construct FFmpeg concat demuxer command for lossless merge.

    ffmpeg -f concat -safe 0 -i manifest.txt -c copy {output}
    """
    cmd = [
        ffmpeg_exe,
        "-y",
        "-nostdin",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(manifest_path),
        "-c",
        "copy",
    ]
    if output_path.suffix.lower() == ".mp4":
        cmd.extend(["-movflags", "+faststart"])
    cmd.append(str(output_path))
    return cmd


class ClipEngine:
    """Executes trimming and multi-clip concatenation using FFmpeg."""

    def __init__(
        self,
        ffmpeg_exe: str | None = None,
        hw_detector: HardwareEncoderDetector | None = None,
    ) -> None:
        self.ffmpeg_exe = ffmpeg_exe or find_tool("ffmpeg")
        self.hw_detector = hw_detector or HardwareEncoderDetector(self.ffmpeg_exe)

    def trim_clip(
        self,
        source_path: Path,
        output_path: Path,
        start_sec: float | str,
        end_sec: float | str,
        cut_mode: str = "STREAM_COPY",
        encoder_override: str | None = None,
        encoder_args: list[str] | None = None,
        timeout: float = 300.0,
        on_process_start: Callable[[subprocess.Popen], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Path:
        """Trim a segment from source_path and write to output_path.

        cut_mode: 'STREAM_COPY' (lossless, near keyframe) or 'FRAME_ACCURATE' (re-encode)
        """
        if not self.ffmpeg_exe:
            raise FileNotFoundError("FFmpeg executable not found.")

        start_val = parse_timecode(start_sec) if isinstance(start_sec, str) else float(start_sec)
        end_val = parse_timecode(end_sec) if isinstance(end_sec, str) else float(end_sec)

        if start_val >= end_val:
            raise ValueError(
                f"Start time ({start_val}s) must be strictly less than end time ({end_val}s)"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)

        mode_upper = cut_mode.upper()
        if mode_upper == "STREAM_COPY":
            cmd = build_stream_copy_trim_command(
                ffmpeg_exe=self.ffmpeg_exe,
                source_path=source_path,
                output_path=output_path,
                start_sec=start_val,
                end_sec=end_val,
            )
        else:
            if encoder_override:
                enc_name = encoder_override
                enc_flags = encoder_args or self.hw_detector.get_params(enc_name)
            else:
                enc_name, enc_flags = self.hw_detector.detect()

            cmd = build_frame_accurate_trim_command(
                ffmpeg_exe=self.ffmpeg_exe,
                source_path=source_path,
                output_path=output_path,
                start_sec=start_val,
                end_sec=end_val,
                encoder_name=enc_name,
                encoder_args=enc_flags,
            )

        creationflags = 0x08000000 if os.name == "nt" else 0
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creationflags,
        )

        if on_process_start:
            on_process_start(proc)

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            if cancel_check and cancel_check():
                kill_process_tree(proc.pid)
                raise RuntimeError("Trimming cancelled by user.")

            if proc.returncode != 0:
                raise RuntimeError(
                    f"FFmpeg trim failed with exit code {proc.returncode}: {stderr[-1000:]}"
                )

        except subprocess.TimeoutExpired as exc:
            kill_process_tree(proc.pid)
            raise TimeoutError(f"FFmpeg trim timed out after {timeout} seconds.") from exc
        except Exception:
            if proc.poll() is None:
                kill_process_tree(proc.pid)
            raise

        if not output_path.is_file():
            raise FileNotFoundError(f"Expected trimmed output was not created: {output_path}")

        return output_path

    def merge_clips(
        self,
        clip_paths: list[Path],
        output_path: Path,
        manifest_path: Path | None = None,
        timeout: float = 300.0,
        on_process_start: Callable[[subprocess.Popen], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Path:
        """Concatenate multiple clip files into a single output file using the concat demuxer."""
        if not self.ffmpeg_exe:
            raise FileNotFoundError("FFmpeg executable not found.")

        if not clip_paths:
            raise ValueError("clip_paths cannot be empty for merge_clips")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if manifest_path is None:
            manifest_path = output_path.parent / f"{output_path.stem}_concat_manifest.txt"

        create_concat_manifest(clip_paths, manifest_path)
        cmd = build_concat_command(
            ffmpeg_exe=self.ffmpeg_exe,
            manifest_path=manifest_path,
            output_path=output_path,
        )

        creationflags = 0x08000000 if os.name == "nt" else 0
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creationflags,
        )

        if on_process_start:
            on_process_start(proc)

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            if cancel_check and cancel_check():
                kill_process_tree(proc.pid)
                raise RuntimeError("Merge cancelled by user.")

            if proc.returncode != 0:
                raise RuntimeError(
                    f"FFmpeg concat merge failed with exit code {proc.returncode}: {stderr[-1000:]}"
                )

        except subprocess.TimeoutExpired as exc:
            kill_process_tree(proc.pid)
            raise TimeoutError(f"FFmpeg merge timed out after {timeout} seconds.") from exc
        except Exception:
            if proc.poll() is None:
                kill_process_tree(proc.pid)
            raise

        if not output_path.is_file():
            raise FileNotFoundError(f"Expected merged output was not created: {output_path}")

        return output_path
