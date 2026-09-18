"""yt-dlp discovery, command construction, and single-download caching engine."""

import math
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vkdub.media.process import find_tool

# Format selector mapping based on requested resolution
QUALITY_FORMAT_MAP: dict[str, str] = {
    "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
    "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "best": "bestvideo+bestaudio/best",
    "source_best": "bestvideo+bestaudio/best",
}

# HLS/DVR variants can seek directly to a time range without byte-scanning a
# 20–40 GB DASH object. These selectors are the default for clip downloads.
SEGMENTED_QUALITY_FORMAT_MAP: dict[str, str] = {
    "2160p": (
        "bestvideo[height<=2160][protocol^=m3u8]+bestaudio[protocol^=m3u8]"
        "/best[height<=2160][protocol^=m3u8]"
        "/bestvideo[height<=2160]+bestaudio/best[height<=2160]/best"
    ),
    "1440p": (
        "bestvideo[height<=1440][protocol^=m3u8]+bestaudio[protocol^=m3u8]"
        "/best[height<=1440][protocol^=m3u8]"
        "/bestvideo[height<=1440]+bestaudio/best[height<=1440]/best"
    ),
    "1080p": (
        "bestvideo[height<=1080][protocol^=m3u8]+bestaudio[protocol^=m3u8]"
        "/best[height<=1080][protocol^=m3u8]"
        "/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
    ),
    "720p": (
        "bestvideo[height<=720][protocol^=m3u8]+bestaudio[protocol^=m3u8]"
        "/best[height<=720][protocol^=m3u8]"
        "/bestvideo[height<=720]+bestaudio/best[height<=720]/best"
    ),
    "best": (
        "bestvideo[protocol^=m3u8]+bestaudio[protocol^=m3u8]"
        "/best[protocol^=m3u8]/bestvideo+bestaudio/best"
    ),
}

# Regex patterns for parsing yt-dlp telemetry
DOWNLOAD_PROGRESS_REGEX = re.compile(
    r"\[download\]\s+([\d\.]+)%\s+of\s+~?([\d\.]+\s*[KkMmGg]?i?B)(?:\s+at\s+([\d\.]+[KkMmGg]?i?B/s))?(?:\s+ETA\s+(\S+))?"
)
DOWNLOAD_PCT_ONLY_REGEX = re.compile(r"\[download\]\s+([\d\.]+)%")
MERGER_REGEX = re.compile(r"\[(?:Merger|ffmpeg)\]\s+Merging formats into", re.IGNORECASE)
SAFE_VIDEO_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _inject_and_return(filepath: Path | str) -> str:
    resolved = str(Path(filepath).resolve())
    parent_dir = str(Path(resolved).parent)
    cur_path = os.environ.get("PATH", "")
    paths = [p.lower() for p in cur_path.split(os.pathsep) if p]
    if parent_dir.lower() not in paths:
        os.environ["PATH"] = f"{parent_dir}{os.pathsep}{cur_path}"
    return resolved


def find_ytdlp(search_roots: list[Path] | None = None) -> str | None:
    """Find the yt-dlp executable following the strict 5-step search order:

    1. YTDLP_PATH environment variable (authoritative override)
    2. Bundled tool subdirectory: tools/yt-dlp/yt-dlp.exe
    3. Bundled tool root: tools/yt-dlp.exe
    4. System PATH: shutil.which("yt-dlp")
    5. Windows package managers & shims (WinGet, Scoop, Chocolatey)
    """
    exe_name = "yt-dlp.exe" if os.name == "nt" else "yt-dlp"

    # 1. Explicit environment override (authoritative)
    configured = os.environ.get("YTDLP_PATH")
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return _inject_and_return(path)
        # Authoritative override principle: if configured but file doesn't exist,
        # return None to prevent silent fallback to an unexpected binary.
        return None

    # Base search directories for bundled tools. ``search_roots`` provides an
    # explicit discovery boundary for diagnostics/tests so a real developer
    # installation cannot accidentally satisfy an isolated probe.
    if search_roots is not None:
        base_dirs = [Path(root) for root in search_roots]
    else:
        base_dirs: list[Path] = []
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).parent
            base_dirs.extend([exe_dir, exe_dir / "_internal"])
            if hasattr(sys, "_MEIPASS"):
                base_dirs.append(Path(sys._MEIPASS))
        else:
            repo_root = Path(__file__).resolve().parents[3]
            base_dirs.extend([repo_root, repo_root / "resources"])

        try:
            base_dirs.append(Path.cwd())
            if sys.argv and sys.argv[0]:
                base_dirs.append(Path(sys.argv[0]).resolve().parent)
        except Exception:
            pass

    # 2. Bundled tool subdirectory (tools/yt-dlp/yt-dlp.exe)
    for b in base_dirs:
        for sub in [
            "tools/yt-dlp",
            "tools/ytdlp",
            "_internal/tools/yt-dlp",
            "resources/tools/yt-dlp",
        ]:
            candidate = b / sub / exe_name
            if candidate.is_file():
                return _inject_and_return(candidate)

    # 3. Bundled tool root (tools/yt-dlp.exe)
    for b in base_dirs:
        for sub in ["tools", "bin", "_internal/tools", "resources/tools", ""]:
            candidate = b / sub / exe_name
            if candidate.is_file():
                return _inject_and_return(candidate)

    # 4. System PATH
    found = shutil.which("yt-dlp") or (shutil.which(exe_name) if os.name == "nt" else None)
    if found:
        return _inject_and_return(found)

    # 5. Windows package managers & shims
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            winget_links = Path(local_app_data) / "Microsoft" / "WinGet" / "Links" / exe_name
            if winget_links.is_file():
                return _inject_and_return(winget_links)
            pkg_dir = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
            if pkg_dir.is_dir():
                for cand in pkg_dir.glob(f"**/{exe_name}"):
                    if cand.is_file():
                        return _inject_and_return(cand)

        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            scoop_candidate = Path(user_profile) / "scoop" / "shims" / exe_name
            if scoop_candidate.is_file():
                return _inject_and_return(scoop_candidate)

        all_users = os.environ.get("ALLUSERSPROFILE")
        if all_users:
            choco_candidate = Path(all_users) / "chocolatey" / "bin" / exe_name
            if choco_candidate.is_file():
                return _inject_and_return(choco_candidate)

        common_candidates = [
            Path("C:/yt-dlp") / exe_name,
            Path("C:/tools/yt-dlp") / exe_name,
            Path("C:/tools") / exe_name,
        ]
        for cand in common_candidates:
            if cand.is_file():
                return _inject_and_return(cand)

    return None


def get_youtube_cache_dir(video_id: str, custom_base: Path | None = None) -> Path:
    """Return cache directory for a given YouTube video ID."""
    if not SAFE_VIDEO_ID_REGEX.fullmatch(video_id):
        raise ValueError("Invalid YouTube video ID.")
    if custom_base is not None:
        base = custom_base
    else:
        try:
            from vkdub.utils.paths import workspace_root

            base = workspace_root()
        except Exception:
            try:
                from vkdub.utils.paths import data_root

                base = data_root()
            except Exception:
                base = Path.cwd()

    cache_dir = base / "cache" / "youtube" / video_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def build_ytdlp_download_command(
    ytdlp_exe: str,
    video_url: str,
    target_output: Path,
    ffmpeg_location: str | Path | None = None,
    quality: str = "1080p",
    use_cookies: bool = False,
    cookie_browser: str | None = None,
    section_start: float | None = None,
    section_end: float | None = None,
    force_keyframes_at_cuts: bool = False,
    prefer_segmented: bool = False,
) -> list[str]:
    """Construct safe argv list for yt-dlp download and remuxing.

    Opt-in cookie policy: Public videos NEVER pass cookie parameters.
    Only when use_cookies is True and cookie_browser is non-empty will
    --cookies-from-browser be appended.
    """
    quality_key = quality.lower()
    if prefer_segmented and quality_key != "source_best":
        format_spec = SEGMENTED_QUALITY_FORMAT_MAP.get(
            quality_key, SEGMENTED_QUALITY_FORMAT_MAP["best"]
        )
    else:
        format_spec = QUALITY_FORMAT_MAP.get(quality_key, QUALITY_FORMAT_MAP["1080p"])

    cmd: list[str] = [
        ytdlp_exe,
        "--no-playlist",
        "--no-warnings",
        "--newline",
        "--concurrent-fragments",
        "4",
        "-f",
        format_spec,
        "--merge-output-format",
        "mp4",
    ]

    if ffmpeg_location:
        cmd.extend(["--ffmpeg-location", str(ffmpeg_location)])

    if section_start is not None or section_end is not None:
        if section_start is None or section_end is None:
            raise ValueError("Both section_start and section_end are required.")
        start = float(section_start)
        end = float(section_end)
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
            raise ValueError("Invalid yt-dlp download section.")
        cmd.extend(["--download-sections", f"*{start:.3f}-{end:.3f}"])
        cmd.extend(["--no-continue", "--no-part"])
        if force_keyframes_at_cuts:
            cmd.append("--force-keyframes-at-cuts")

    cmd.extend(["-o", str(target_output)])

    # Strictly opt-in cookies
    if use_cookies and cookie_browser and cookie_browser.strip():
        cmd.extend(["--cookies-from-browser", cookie_browser.strip()])

    cmd.append(video_url)
    return cmd


def parse_ytdlp_progress_line(line: str) -> dict[str, Any] | None:
    """Parse a single output line from yt-dlp to extract download/remuxing progress."""
    line = line.strip()
    if not line:
        return None

    if MERGER_REGEX.search(line):
        return {
            "stage": "REMUXING",
            "percent": 100.0,
            "speed": "",
            "eta": "",
            "total_size": "",
            "message": "Merging video and audio streams...",
        }

    m = DOWNLOAD_PROGRESS_REGEX.search(line)
    if m:
        pct = float(m.group(1))
        size = m.group(2) if m.group(2) else ""
        speed = m.group(3) if m.group(3) else ""
        eta = m.group(4) if m.group(4) else ""
        msg = f"Downloading: {pct:.1f}% ({speed})" if speed else f"Downloading: {pct:.1f}%"
        return {
            "stage": "DOWNLOADING",
            "percent": pct,
            "speed": speed,
            "eta": eta,
            "total_size": size,
            "message": msg,
        }

    m2 = DOWNLOAD_PCT_ONLY_REGEX.search(line)
    if m2:
        pct = float(m2.group(1))
        return {
            "stage": "DOWNLOADING",
            "percent": pct,
            "speed": "",
            "eta": "",
            "total_size": "",
            "message": f"Downloading: {pct:.1f}%",
        }

    return None


def validate_media_integrity(file_path: Path, ffprobe_exe: str | None = None) -> bool:
    """Validate that a downloaded MP4 file is complete and readable by ffprobe."""
    if not file_path.is_file():
        return False
    try:
        if file_path.stat().st_size < 1024:  # Under 1 KB is certainly invalid
            return False
    except OSError:
        return False

    probe = ffprobe_exe or find_tool("ffprobe")
    if probe and Path(probe).is_file():
        try:
            creationflags = 0x08000000 if os.name == "nt" else 0
            res = subprocess.run(
                [
                    probe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(file_path),
                ],
                capture_output=True,
                text=True,
                timeout=5.0,
                creationflags=creationflags,
            )
            if res.returncode == 0 and res.stdout.strip():
                try:
                    dur = float(res.stdout.strip())
                    return dur > 0
                except ValueError:
                    return False
            return False
        except Exception:
            return False

    return True


class YtDlpDownloader:
    """Manages yt-dlp execution and caching per (video_id, quality)."""

    def __init__(
        self,
        ytdlp_path: str | None = None,
        ffmpeg_location: str | None = None,
        cache_root: Path | None = None,
    ) -> None:
        self.ytdlp_path = ytdlp_path or find_ytdlp()
        if ffmpeg_location:
            self.ffmpeg_location = ffmpeg_location
        else:
            ffmpeg_exe = find_tool("ffmpeg")
            self.ffmpeg_location = str(Path(ffmpeg_exe).parent) if ffmpeg_exe else None
        self.cache_root = cache_root

    def get_cached_source(self, video_id: str, quality: str = "1080p") -> Path | None:
        """Return cached file path if it exists and is structurally valid; otherwise None."""
        cache_dir = get_youtube_cache_dir(video_id, self.cache_root)
        candidate = cache_dir / f"source_{video_id}_{quality}.mp4"
        if candidate.is_file():
            if validate_media_integrity(candidate):
                return candidate
            # File is corrupt or incomplete; delete it so it can be re-downloaded
            try:
                candidate.unlink(missing_ok=True)
            except OSError:
                pass
        return None

    def get_cached_section(
        self,
        video_id: str,
        quality: str,
        start_sec: float,
        end_sec: float,
    ) -> Path | None:
        """Return a cached time-range download for an exact clip selection."""
        cache_dir = get_youtube_cache_dir(video_id, self.cache_root)
        start_ms = max(0, round(float(start_sec) * 1000))
        end_ms = max(0, round(float(end_sec) * 1000))
        candidate = cache_dir / f"section_{video_id}_{quality}_{start_ms}_{end_ms}.mp4"
        if candidate.is_file():
            if validate_media_integrity(candidate):
                return candidate
            try:
                candidate.unlink(missing_ok=True)
            except OSError:
                pass
        return None

    def download(
        self,
        video_url: str,
        video_id: str,
        quality: str = "1080p",
        use_cookies: bool = False,
        cookie_browser: str | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
        on_process_start: Callable[[subprocess.Popen], None] | None = None,
        section_start: float | None = None,
        section_end: float | None = None,
        force_keyframes_at_cuts: bool = False,
        prefer_segmented: bool = False,
    ) -> Path:
        """Download a full video or only one selected time range using yt-dlp."""
        is_section = section_start is not None or section_end is not None
        if is_section:
            if section_start is None or section_end is None:
                raise ValueError("Both section_start and section_end are required.")
            start_value = float(section_start)
            end_value = float(section_end)
            if (
                not math.isfinite(start_value)
                or not math.isfinite(end_value)
                or start_value < 0
                or end_value <= start_value
            ):
                raise ValueError("Invalid yt-dlp download section.")
        else:
            start_value = 0.0
            end_value = 0.0

        # 1. Check existing cache
        cached = (
            self.get_cached_section(video_id, quality, start_value, end_value)
            if is_section
            else self.get_cached_source(video_id, quality)
        )
        if cached:
            if progress_callback:
                progress_callback({
                    "stage": "COMPLETE",
                    "percent": 100.0,
                    "speed": "",
                    "eta": "",
                    "total_size": "",
                    "message": (
                        "Using cached selected section."
                        if is_section
                        else "Using cached source video."
                    ),
                    "cached": True,
                })
            return cached

        if not self.ytdlp_path:
            raise FileNotFoundError(
                "yt-dlp executable was not found. Please install yt-dlp or set YTDLP_PATH."
            )

        cache_dir = get_youtube_cache_dir(video_id, self.cache_root)
        if is_section:
            start_ms = round(start_value * 1000)
            end_ms = round(end_value * 1000)
            target_stem = f"section_{video_id}_{quality}_{start_ms}_{end_ms}"
        else:
            target_stem = f"source_{video_id}_{quality}"
        target_output = cache_dir / f"{target_stem}.mp4"

        # A killed downloader may leave format-specific .part/.ytdl files.
        # Remove only artifacts for this exact video/quality/time-range before
        # starting; stale byte offsets are a common source of HTTP 416 errors.
        if is_section:
            for stale in cache_dir.glob(f"{target_stem}.*"):
                if stale.is_file():
                    try:
                        stale.unlink(missing_ok=True)
                    except OSError:
                        pass

        # Build download command
        cmd = build_ytdlp_download_command(
            ytdlp_exe=self.ytdlp_path,
            video_url=video_url,
            target_output=target_output,
            ffmpeg_location=self.ffmpeg_location,
            quality=quality,
            use_cookies=use_cookies,
            cookie_browser=cookie_browser,
            section_start=start_value if is_section else None,
            section_end=end_value if is_section else None,
            force_keyframes_at_cuts=force_keyframes_at_cuts,
            prefer_segmented=prefer_segmented,
        )

        creationflags = 0x08000000 if os.name == "nt" else 0
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            creationflags=creationflags,
        )

        if on_process_start:
            on_process_start(proc)

        error_lines: list[str] = []

        try:
            assert proc.stdout is not None
            for raw_line in iter(proc.stdout.readline, ""):
                if cancel_check and cancel_check():
                    proc.terminate()
                    raise RuntimeError("Download cancelled by user.")

                line = raw_line.strip()
                if not line:
                    continue

                parsed = parse_ytdlp_progress_line(line)
                if parsed and progress_callback:
                    progress_callback(parsed)
                elif "ERROR" in line or "error" in line.lower():
                    error_lines.append(line)

            proc.wait()
            if proc.returncode != 0:
                err_msg = (
                    "\n".join(error_lines[-5:])
                    if error_lines
                    else f"Exit code {proc.returncode}"
                )
                if is_section and "HTTP Error 416" in err_msg:
                    raise RuntimeError(
                        "YouTube CDN từ chối lấy đoạn của luồng chất lượng tuyệt đối "
                        "(HTTP 416). Hãy chọn 'Cao nhất cắt nhanh' hoặc mức 4K/1080p."
                    )
                raise RuntimeError(f"yt-dlp download failed: {err_msg}")

        except Exception:
            # Clean up partial artifacts if download failed or was cancelled
            if proc.poll() is None:
                proc.kill()
            try:
                target_output.unlink(missing_ok=True)
                for part in cache_dir.glob(f"{target_stem}.*.part"):
                    part.unlink(missing_ok=True)
                for ytdl in cache_dir.glob(f"{target_stem}.*.ytdl"):
                    ytdl.unlink(missing_ok=True)
            except OSError:
                pass
            raise

        if not target_output.is_file():
            # Check if yt-dlp left another extension
            candidates = list(cache_dir.glob(f"{target_stem}.*"))
            if candidates and candidates[0].is_file():
                return candidates[0]
            raise FileNotFoundError(f"Expected output file not found: {target_output}")

        return target_output
