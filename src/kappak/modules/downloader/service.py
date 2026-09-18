"""Downloader service for KAPPAK Studio — TikTok, YouTube, Douyin, Facebook, Instagram."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import yt_dlp

from kappak.core.config import get_default_projects_root
from kappak.core.db import db_session
from kappak.domain.asset import Asset, calculate_sha256

logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    """Extracted metadata before downloading."""

    url: str
    title: str
    creator: str
    duration_sec: float
    duration_str: str
    thumbnail_url: str
    platform: str
    formats: list[str]
    description: str = ""


def detect_platform(url: str) -> str:
    """Detect platform name from URL."""
    domain = urlparse(url).netloc.lower()
    if "tiktok.com" in domain:
        return "TikTok"
    if "youtube.com" in domain or "youtu.be" in domain:
        return "YouTube"
    if "facebook.com" in domain or "fb.watch" in domain:
        return "Facebook"
    if "instagram.com" in domain:
        return "Instagram"
    if "douyin.com" in domain:
        return "Douyin"
    return "Generic"


def format_duration(seconds: float | int | None) -> str:
    """Format duration in seconds into MM:SS or HH:MM:SS."""
    if not seconds or seconds <= 0:
        return "--:--"
    sec = int(seconds)
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def fetch_video_metadata(url: str) -> VideoMetadata:
    """Extract metadata for preview without downloading."""
    platform = detect_platform(url)
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
        "extract_flat": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    title = info.get("title") or "Video không tiêu đề"
    creator = info.get("uploader") or info.get("channel") or info.get("creator") or platform
    duration_sec = float(info.get("duration") or 0.0)
    duration_str = format_duration(duration_sec)
    thumbnail = info.get("thumbnail") or ""
    description = info.get("description") or ""

    formats_list = ["Chất lượng tốt nhất (Best Video+Audio)", "1080p Full HD", "720p HD", "Chỉ lấy âm thanh (Audio MP3)"]

    return VideoMetadata(
        url=url,
        title=title,
        creator=creator,
        duration_sec=duration_sec,
        duration_str=duration_str,
        thumbnail_url=thumbnail,
        platform=platform,
        formats=formats_list,
        description=description[:200],
    )


def download_media(
    url: str,
    output_dir: Path,
    quality_choice: str = "best",
    project_id: str | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
) -> Asset:
    """Download video or audio using yt-dlp, compute SHA-256, and register asset in DB."""
    output_dir.mkdir(parents=True, exist_ok=True)
    platform = detect_platform(url)

    # 1. Pre-check: Deduplication by source_url if file still exists on disk
    with db_session() as conn:
        existing = conn.execute(
            """
            SELECT id, project_id, name, local_path, source_url, platform,
                   creator, duration_sec, resolution, file_size, sha256_hash,
                   category, status, created_at, updated_at
            FROM assets WHERE source_url = ?
            """,
            (url,),
        ).fetchone()
        if existing and existing["local_path"] and Path(existing["local_path"]).is_file():
            logger.info("URL already downloaded: %s -> Reusing %s", url, existing["local_path"])
            if progress_callback:
                progress_callback(100.0, "Phát hiện video đã có trong thư viện, tái sử dụng tài nguyên...")
            return Asset(
                id=existing["id"],
                name=existing["name"],
                local_path=Path(existing["local_path"]),
                project_id=project_id or existing["project_id"],
                source_url=existing["source_url"],
                platform=existing["platform"],
                creator=existing["creator"],
                duration_sec=existing["duration_sec"],
                resolution=existing["resolution"],
                file_size=existing["file_size"],
                sha256_hash=existing["sha256_hash"],
                category=existing["category"],
                status=existing["status"],
            )

    # Format selector
    if "Audio" in quality_choice or "MP3" in quality_choice:
        ydl_format = "bestaudio/best"
        postprocessors = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
        out_template = str(output_dir / "%(title).80s.%(ext)s")
    elif "1080" in quality_choice:
        ydl_format = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
        postprocessors = []
        out_template = str(output_dir / "%(title).80s.%(ext)s")
    elif "720" in quality_choice:
        ydl_format = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
        postprocessors = []
        out_template = str(output_dir / "%(title).80s.%(ext)s")
    else:
        ydl_format = "bestvideo+bestaudio/best"
        postprocessors = []
        out_template = str(output_dir / "%(title).80s.%(ext)s")

    downloaded_filepath: Path | None = None

    def _hook(d: dict) -> None:
        nonlocal downloaded_filepath
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            pct = (downloaded / total * 100) if total > 0 else 0
            speed = d.get("speed") or 0
            speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed else ""
            msg = f"Đang tải: {pct:.1f}% ({speed_str})"
            if progress_callback:
                progress_callback(pct, msg)
        elif status == "finished":
            downloaded_filepath = Path(d.get("filename", ""))
            if progress_callback:
                progress_callback(100.0, "Đang xử lý sau tải...")

    ydl_opts = {
        "format": ydl_format,
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_hook],
    }
    if postprocessors:
        ydl_opts["postprocessors"] = postprocessors

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        meta = ydl.extract_info(url, download=True)

    # Resolve the final file on disk
    if downloaded_filepath and downloaded_filepath.is_file():
        final_file = downloaded_filepath
    else:
        # Fallback find latest created file in output_dir
        files = list(output_dir.glob("*.*"))
        if files:
            final_file = max(files, key=lambda f: f.stat().st_mtime)
        else:
            raise RuntimeError("Không tìm thấy tệp tải về sau khi hoàn tất.")

    # Calculate SHA-256 for deduplication
    sha256 = calculate_sha256(final_file)
    file_size = final_file.stat().st_size
    title = meta.get("title") or final_file.stem
    creator = meta.get("uploader") or meta.get("channel") or platform
    duration_sec = float(meta.get("duration") or 0.0)
    resolution = f"{meta.get('width', 0)}x{meta.get('height', 0)}"

    # 2. Post-check: If identical SHA-256 already exists in DB from another download, reuse it
    with db_session() as conn:
        dup = conn.execute(
            """
            SELECT id, project_id, name, local_path, source_url, platform,
                   creator, duration_sec, resolution, file_size, sha256_hash,
                   category, status
            FROM assets WHERE sha256_hash = ? AND local_path != ?
            """,
            (sha256, str(final_file)),
        ).fetchone()
        if dup and dup["local_path"] and Path(dup["local_path"]).is_file():
            logger.info(
                "Duplicate file content detected by SHA-256 (%s). Reusing original %s",
                sha256[:8],
                dup["name"],
            )
            # Remove redundant duplicate file to save disk space
            try:
                final_file.unlink(missing_ok=True)
            except Exception:
                pass
            final_file = Path(dup["local_path"])

    # Create Asset Entity
    asset = Asset(
        name=final_file.name,
        local_path=final_file,
        project_id=project_id,
        source_url=url,
        platform=platform,
        creator=creator,
        duration_sec=duration_sec,
        resolution=resolution,
        file_size=file_size,
        sha256_hash=sha256,
        category="00_Inbox",
        status="Unused",
    )

    # Save to SQLite database
    with db_session() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO assets (
                id, project_id, name, local_path, source_url, platform,
                creator, duration_sec, resolution, file_size, sha256_hash,
                tags, category, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset.id,
                asset.project_id,
                asset.name,
                str(asset.local_path),
                asset.source_url,
                asset.platform,
                asset.creator,
                asset.duration_sec,
                asset.resolution,
                asset.file_size,
                asset.sha256_hash,
                "",
                asset.category,
                asset.status,
                asset.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(asset.created_at, "strftime") else str(asset.created_at),
                asset.updated_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(asset.updated_at, "strftime") else str(asset.updated_at),
            ),
        )

    logger.info("Asset registered successfully: %s (hash: %s)", asset.name, sha256[:8])
    return asset
