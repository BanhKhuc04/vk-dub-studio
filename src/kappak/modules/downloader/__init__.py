"""Downloader module package for KAPPAK Studio."""

from kappak.modules.downloader.service import (
    VideoMetadata,
    detect_platform,
    download_media,
    fetch_video_metadata,
)

__all__ = [
    "VideoMetadata",
    "detect_platform",
    "download_media",
    "fetch_video_metadata",
]
