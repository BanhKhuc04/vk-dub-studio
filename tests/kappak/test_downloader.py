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
