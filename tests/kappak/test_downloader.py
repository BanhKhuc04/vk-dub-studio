"""Unit tests for KAPPAK Downloader Module."""

import pytest
from pathlib import Path
from kappak.modules.downloader.service import detect_platform, format_duration


def test_platform_detection():
    assert detect_platform("https://www.tiktok.com/@creator/video/7123456789") == "TikTok"
    assert detect_platform("https://vt.tiktok.com/ZS12345/") == "TikTok"
    assert detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "YouTube"
    assert detect_platform("https://youtu.be/dQw4w9WgXcQ") == "YouTube"
    assert detect_platform("https://www.facebook.com/reel/12345678") == "Facebook"
    assert detect_platform("https://www.instagram.com/reel/C8xyz123/") == "Instagram"
    assert detect_platform("https://www.douyin.com/video/7123456789") == "Douyin"
    assert detect_platform("https://example.com/video.mp4") == "Generic"


def test_format_duration():
    assert format_duration(0) == "--:--"
    assert format_duration(45) == "00:45"
    assert format_duration(125) == "02:05"
    assert format_duration(3665) == "01:01:05"


def test_downloader_deduplication_workflow(tmp_path, monkeypatch):
    """Test URL and SHA-256 deduplication without actual network calls."""
    from unittest.mock import MagicMock
    from kappak.modules.downloader.service import download_media
    from kappak.core.db import db_session, init_db
    from kappak.domain.asset import calculate_sha256

    test_db = tmp_path / "test_isolated.sqlite"
    monkeypatch.setattr("kappak.core.config.get_database_path", lambda: test_db)
    monkeypatch.setattr("kappak.core.db.get_database_path", lambda: test_db)
    init_db(test_db)

    # 1. Create a dummy video file
    dummy_video = tmp_path / "sample_test.mp4"
    dummy_video.write_bytes(b"TEST_VIDEO_CONTENT_12345" * 100)
    expected_hash = calculate_sha256(dummy_video)

    # Mock yt_dlp to simulate downloading dummy_video
    class MockYoutubeDL:
        def __init__(self, opts):
            self.opts = opts
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def extract_info(self, url, download=True):
            # Call progress hook
            for hook in self.opts.get("progress_hooks", []):
                hook({"status": "finished", "filename": str(dummy_video)})
            return {
                "title": "Sample Test Video",
                "uploader": "TestCreator",
                "duration": 15.0,
                "width": 1920,
                "height": 1080,
            }

    monkeypatch.setattr("yt_dlp.YoutubeDL", MockYoutubeDL)

    # First download -> inserts into DB
    asset1 = download_media(
        url="https://www.tiktok.com/@test/video/111",
        output_dir=tmp_path,
        quality_choice="best",
    )
    assert asset1.sha256_hash == expected_hash
    assert asset1.local_path.is_file()

    # Second download with SAME URL -> triggers Pre-check dedup, no yt_dlp call needed
    monkeypatch.setattr("yt_dlp.YoutubeDL", MagicMock(side_effect=RuntimeError("Should not call yt-dlp!")))
    progress_msgs = []
    asset2 = download_media(
        url="https://www.tiktok.com/@test/video/111",
        output_dir=tmp_path,
        quality_choice="best",
        progress_callback=lambda pct, msg: progress_msgs.append(msg),
    )
    assert asset2.id == asset1.id
    assert asset2.sha256_hash == expected_hash
    assert any("đã có trong thư viện" in m for m in progress_msgs)

    # Third download with DIFFERENT URL but SAME FILE CONTENT (SHA-256 Post-check)
    # Simulate downloading a duplicate file
    dup_video = tmp_path / "duplicate_download.mp4"
    dup_video.write_bytes(b"TEST_VIDEO_CONTENT_12345" * 100)

    class MockYoutubeDLDup:
        def __init__(self, opts):
            self.opts = opts
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def extract_info(self, url, download=True):
            for hook in self.opts.get("progress_hooks", []):
                hook({"status": "finished", "filename": str(dup_video)})
            return {"title": "Duplicate Video", "uploader": "Creator2", "duration": 15.0, "width": 1920, "height": 1080}

    monkeypatch.setattr("yt_dlp.YoutubeDL", MockYoutubeDLDup)
    progress_msgs_post = []
    asset3 = download_media(
        url="https://www.youtube.com/watch?v=diff_url_same_content",
        output_dir=tmp_path,
        quality_choice="best",
        progress_callback=lambda pct, msg: progress_msgs_post.append(msg),
    )
    # Post-check should detect identical SHA-256, delete dup_video and point to original file
    assert asset3.sha256_hash == expected_hash
    assert asset3.local_path == dummy_video
    assert not dup_video.is_file(), "Duplicate file should be cleaned up by SHA-256 post-check!"
    assert any("trùng khớp SHA-256" in m for m in progress_msgs_post)


