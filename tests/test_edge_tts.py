"""Unit tests for Edge TTS provider (edge_tts_provider.py)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

# Top-level import is required; monkeypatch needs the module already loaded.
# pytest injects 'src' via pythonpath in pyproject.toml.
from vkdub.providers.edge_tts_provider import (
    EdgeTTSProvider,
    generate_sec_ms_gec,
    speed_to_rate_str,
)
from vkdub.utils.paths import workspace_root


class TestEdgeTTSHelpers:
    """Test pure helper functions that don't require network or FFmpeg."""

    def test_speed_to_rate_str_various_formats(self):
        assert speed_to_rate_str(1.0) == "+0%"
        assert speed_to_rate_str(1.1) == "+10%"
        assert speed_to_rate_str(0.9) == "-10%"
        assert speed_to_rate_str(1.5) == "+50%"
        assert speed_to_rate_str("1.1x") == "+10%"
        assert speed_to_rate_str("1.1X") == "+10%"
        assert speed_to_rate_str(" 1.2 ") == "+20%"
        assert speed_to_rate_str(2.0) == "+100%"
        assert speed_to_rate_str(0.5) == "-50%"
        assert speed_to_rate_str(1) == "+0%"

    def test_speed_to_rate_str_invalid_input_defaults(self):
        assert speed_to_rate_str("abc") == "+0%"
        assert speed_to_rate_str("") == "+0%"

    def test_generate_sec_ms_gec_returns_hex_string(self):
        token = generate_sec_ms_gec()
        assert isinstance(token, str)
        assert len(token) == 64
        assert all(c in "0123456789ABCDEF" for c in token)

    def test_generate_sec_ms_gec_stable_within_window(self):
        assert generate_sec_ms_gec() == generate_sec_ms_gec()


class TestEdgeTTSProvider:
    """Test EdgeTTSProvider class methods."""

    def test_provider_identity(self):
        provider = EdgeTTSProvider()
        assert provider.id == "edge_tts"
        assert provider.display_name == "Microsoft Edge TTS"

    def test_list_voices_returns_vietnamese_voices(self):
        provider = EdgeTTSProvider()
        voices = provider.list_voices()
        assert len(voices) >= 2
        voice_ids = {v.id for v in voices}
        assert "vi-VN-HoaiMyNeural" in voice_ids
        assert "vi-VN-NamMinhNeural" in voice_ids

    def test_list_voices_female_and_male(self):
        provider = EdgeTTSProvider()
        voices = {v.id: v for v in provider.list_voices()}
        hoaimy = voices["vi-VN-HoaiMyNeural"]
        assert hoaimy.gender == "female"
        assert hoaimy.language == "vi"
        assert "Hoài My" in hoaimy.name

        namminh = voices["vi-VN-NamMinhNeural"]
        assert namminh.gender == "male"
        assert namminh.language == "vi"
        assert "Nam Minh" in namminh.name

    def test_health_check_ffmpeg_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KAPPAK_DATA_DIR", str(tmp_path / "kappak"))
        # Redirect workspace_root to tmp so find_tool resolves from there
        monkeypatch.setattr(
            "vkdub.utils.paths.workspace_root",
            lambda: tmp_path / "kappak",
        )
        monkeypatch.setattr(
            "vkdub.media.process.MediaTools.detect",
            lambda self: None,
        )
        from vkdub.providers.edge_tts_provider import find_tool

        provider = EdgeTTSProvider()
        # Temporarily shadow find_tool in the module's namespace
        import vkdub.providers.edge_tts_provider as et_mod

        original = et_mod.find_tool
        et_mod.find_tool = lambda name: None
        try:
            result = provider.health_check()
            assert result.ok is False
            assert result.code == "FFMPEG_MISSING"
            assert "FFmpeg" in result.message
        finally:
            et_mod.find_tool = original

    def test_health_check_ffmpeg_present(self, tmp_path, monkeypatch):
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            pytest.skip("FFmpeg not available")

        monkeypatch.setenv("KAPPAK_DATA_DIR", str(tmp_path / "kappak"))
        monkeypatch.setattr(
            "vkdub.utils.paths.workspace_root",
            lambda: tmp_path / "kappak",
        )

        import vkdub.providers.edge_tts_provider as et_mod

        original = et_mod.find_tool
        et_mod.find_tool = lambda name: ffmpeg if name == "ffmpeg" else None
        try:
            provider = EdgeTTSProvider()
            result = provider.health_check()
            assert result.ok is True
            assert result.code == "EDGE_TTS_READY"
        finally:
            et_mod.find_tool = original


@pytest.fixture
def ffmpeg_path():
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg not available")
    return ffmpeg


class TestEdgeTTSOfflineSynthesize:
    """Test offline FFmpeg synthesis path (no network dependency)."""

    def test_offline_synthesize_female_voice_creates_file(
        self, tmp_path, ffmpeg_path, monkeypatch
    ):
        monkeypatch.setattr(
            "vkdub.providers.edge_tts_provider.find_tool",
            lambda name: ffmpeg_path,
        )

        provider = EdgeTTSProvider()
        out_path = tmp_path / "edge_female.mp3"
        result = provider._offline_synthesize(
            text="Xin chào các bạn",
            voice_id="vi-VN-HoaiMyNeural",
            speed=1.0,
            output_path=out_path,
        )
        assert result == out_path
        assert out_path.is_file()
        assert out_path.stat().st_size > 1000

    def test_offline_synthesize_male_voice_creates_file(
        self, tmp_path, ffmpeg_path, monkeypatch
    ):
        monkeypatch.setattr(
            "vkdub.providers.edge_tts_provider.find_tool",
            lambda name: ffmpeg_path,
        )

        provider = EdgeTTSProvider()
        out_path = tmp_path / "edge_male.mp3"
        result = provider._offline_synthesize(
            text="Chào buổi sáng",
            voice_id="vi-VN-NamMinhNeural",
            speed=1.0,
            output_path=out_path,
        )
        assert result == out_path
        assert out_path.is_file()
        assert out_path.stat().st_size > 1000

    def test_offline_synthesize_speed_adjustment(self, tmp_path, ffmpeg_path, monkeypatch):
        monkeypatch.setattr(
            "vkdub.providers.edge_tts_provider.find_tool",
            lambda name: ffmpeg_path,
        )

        provider = EdgeTTSProvider()
        out_slow = tmp_path / "slow.mp3"
        out_fast = tmp_path / "fast.mp3"
        provider._offline_synthesize("Xin chào", "vi-VN-HoaiMyNeural", 0.8, out_slow)
        provider._offline_synthesize("Xin chào", "vi-VN-HoaiMyNeural", 1.4, out_fast)
        assert out_slow.stat().st_size > 500
        assert out_fast.stat().st_size > 500

    def test_offline_synthesize_unknown_voice_defaults_to_female(
        self, tmp_path, ffmpeg_path, monkeypatch
    ):
        monkeypatch.setattr(
            "vkdub.providers.edge_tts_provider.find_tool",
            lambda name: ffmpeg_path,
        )

        provider = EdgeTTSProvider()
        out_path = tmp_path / "unknown.mp3"
        result = provider._offline_synthesize(
            text="Test",
            voice_id="unknown-voice",
            speed=1.0,
            output_path=out_path,
        )
        assert result == out_path
        assert out_path.is_file()

    def test_offline_synthesize_creates_parent_dirs(
        self, tmp_path, ffmpeg_path, monkeypatch
    ):
        monkeypatch.setattr(
            "vkdub.providers.edge_tts_provider.find_tool",
            lambda name: ffmpeg_path,
        )

        provider = EdgeTTSProvider()
        out_path = tmp_path / "nested" / "dirs" / "output.mp3"
        assert not out_path.parent.exists()
        provider._offline_synthesize(
            "Test", "vi-VN-HoaiMyNeural", 1.0, out_path
        )
        assert out_path.parent.exists()
        assert out_path.is_file()

    def test_offline_synthesize_ffmpeg_missing_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "vkdub.providers.edge_tts_provider.find_tool",
            lambda name: None,
        )

        provider = EdgeTTSProvider()
        with pytest.raises(RuntimeError, match="FFmpeg không khả dụng"):
            provider._offline_synthesize(
                "Test", "vi-VN-HoaiMyNeural", 1.0, tmp_path / "out.mp3"
            )


class TestEdgeTTSSyncEntryPoint:
    """Test synchronous synthesize() entry point."""

    def test_synthesize_sync_returns_path(self, tmp_path, ffmpeg_path, monkeypatch):
        monkeypatch.setattr(
            "vkdub.providers.edge_tts_provider.find_tool",
            lambda name: ffmpeg_path,
        )

        provider = EdgeTTSProvider()
        out_path = tmp_path / "sync_out.mp3"
        result = provider.synthesize(
            text="Tôi là KAPPAK",
            voice_id="vi-VN-HoaiMyNeural",
            speed=1.0,
            output_path=out_path,
        )
        assert result == out_path
        assert out_path.is_file()
        assert out_path.stat().st_size > 500

    def test_synthesize_sync_speed_string(self, tmp_path, ffmpeg_path, monkeypatch):
        monkeypatch.setattr(
            "vkdub.providers.edge_tts_provider.find_tool",
            lambda name: ffmpeg_path,
        )

        provider = EdgeTTSProvider()
        result = provider.synthesize(
            text="Test", speed="1.2x", output_path=tmp_path / "speed.mp3"
        )
        assert result.is_file()


class TestEdgeTTSPreviewVoice:
    """Test preview_voice caching behavior."""

    def test_preview_returns_path_and_creates_file(
        self, tmp_path, ffmpeg_path, monkeypatch
    ):
        monkeypatch.setattr(
            "vkdub.providers.edge_tts_provider.find_tool",
            lambda name: ffmpeg_path,
        )
        monkeypatch.setattr(
            "vkdub.providers.edge_tts_provider.workspace_root",
            lambda: tmp_path,
        )

        provider = EdgeTTSProvider()
        result = provider.preview_voice(
            text="Xin chào từ KAPPAK",
            voice_id="vi-VN-HoaiMyNeural",
            speed=1.0,
        )
        assert result.is_file()
        assert result.stat().st_size > 500

    def test_preview_uses_voice_and_speed_in_filename(
        self, tmp_path, ffmpeg_path, monkeypatch
    ):
        monkeypatch.setattr(
            "vkdub.providers.edge_tts_provider.find_tool",
            lambda name: ffmpeg_path,
        )
        monkeypatch.setattr(
            "vkdub.providers.edge_tts_provider.workspace_root",
            lambda: tmp_path,
        )

        provider = EdgeTTSProvider()
        p1 = provider.preview_voice("Test", "vi-VN-HoaiMyNeural", 1.0)
        p2 = provider.preview_voice("Test", "vi-VN-NamMinhNeural", 1.0)
        p3 = provider.preview_voice("Test", "vi-VN-HoaiMyNeural", 1.2)
        assert p1 != p2
        assert p1 != p3

    def test_preview_returns_cached_file_on_second_call(
        self, tmp_path, ffmpeg_path, monkeypatch
    ):
        monkeypatch.setattr(
            "vkdub.providers.edge_tts_provider.find_tool",
            lambda name: ffmpeg_path,
        )
        monkeypatch.setattr(
            "vkdub.providers.edge_tts_provider.workspace_root",
            lambda: tmp_path,
        )

        provider = EdgeTTSProvider()
        first = provider.preview_voice("Cached test", "vi-VN-HoaiMyNeural", 1.0)
        first_mtime = first.stat().st_mtime
        second = provider.preview_voice("Cached test", "vi-VN-HoaiMyNeural", 1.0)
        assert first == second
        assert second.stat().st_mtime == first_mtime
