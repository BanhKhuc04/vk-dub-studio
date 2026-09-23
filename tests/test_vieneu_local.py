"""Unit tests for VieNeu Local TTS provider (vieneu_local.py) and voice catalog."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vkdub.providers.tts import TTSError
from vkdub.services.voice_catalog import (
    catalog_path,
    delete_voice,
    find_voice,
    install_presets,
    read_catalog,
    rename_voice,
    save_catalog,
)
from vkdub.providers.vieneu_local import VieNeuLocalProvider


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestVoiceCatalogPersistence:
    """Test voice catalog persistence functions."""

    def test_save_and_read_catalog_roundtrip(self, tmp_path, monkeypatch):
        catalog_file = tmp_path / "voices" / "catalog.json"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.services.voice_catalog as vc_mod

            monkeypatch.setattr(vc_mod, "catalog_path", lambda b="vieneu_local": catalog_file)
            rows = [
                {"id": "test-voice-1", "name": "Test Voice 1", "custom": False},
                {"id": "test-voice-2", "name": "Test Voice 2", "custom": True},
            ]
            save_catalog(rows, "vieneu_local")
            loaded = read_catalog("vieneu_local")
            assert len(loaded) == 2
            assert loaded[0]["id"] == "test-voice-1"
            assert loaded[0]["custom"] is False
            assert loaded[1]["custom"] is True

    def test_read_empty_catalog_returns_empty_list(self, tmp_path, monkeypatch):
        catalog_file = tmp_path / "voices" / "catalog.json"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        catalog_file.write_text("[]", encoding="utf-8")
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.services.voice_catalog as vc_mod

            monkeypatch.setattr(vc_mod, "catalog_path", lambda b="vieneu_local": catalog_file)
            assert read_catalog("vieneu_local") == []

    def test_read_corrupt_json_raises(self, tmp_path, monkeypatch):
        catalog_file = tmp_path / "voices" / "catalog.json"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        catalog_file.write_text("not json{", encoding="utf-8")
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.services.voice_catalog as vc_mod

            monkeypatch.setattr(vc_mod, "catalog_path", lambda b="vieneu_local": catalog_file)
            with pytest.raises(ValueError, match="Danh sách giọng bị lỗi"):
                read_catalog("vieneu_local")

    def test_read_malformed_entry_raises(self, tmp_path, monkeypatch):
        catalog_file = tmp_path / "voices" / "catalog.json"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        catalog_file.write_text(
            json.dumps([{"id": "no-name", "name": 123, "custom": False}]),
            encoding="utf-8",
        )
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.services.voice_catalog as vc_mod

            monkeypatch.setattr(vc_mod, "catalog_path", lambda b="vieneu_local": catalog_file)
            with pytest.raises(ValueError, match="Danh sách giọng bị lỗi"):
                read_catalog("vieneu_local")

    def test_read_duplicate_ids_raises(self, tmp_path, monkeypatch):
        catalog_file = tmp_path / "voices" / "catalog.json"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        catalog_file.write_text(
            json.dumps([
                {"id": "dup-id", "name": "Dup 1", "custom": False},
                {"id": "dup-id", "name": "Dup 2", "custom": True},
            ]),
            encoding="utf-8",
        )
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.services.voice_catalog as vc_mod

            monkeypatch.setattr(vc_mod, "catalog_path", lambda b="vieneu_local": catalog_file)
            with pytest.raises(ValueError, match="Danh sách giọng bị lỗi"):
                read_catalog("vieneu_local")

    def test_find_voice_existing(self, tmp_path, monkeypatch):
        catalog_file = tmp_path / "voices" / "catalog.json"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        catalog_file.write_text(
            json.dumps([{"id": "my-voice", "name": "My Voice", "custom": False}]),
            encoding="utf-8",
        )
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.services.voice_catalog as vc_mod

            monkeypatch.setattr(vc_mod, "catalog_path", lambda b="vieneu_local": catalog_file)
            voice = find_voice("my-voice", "vieneu_local")
            assert voice["id"] == "my-voice"
            assert voice["name"] == "My Voice"

    def test_find_voice_missing_raises(self, tmp_path, monkeypatch):
        catalog_file = tmp_path / "voices" / "catalog.json"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        catalog_file.write_text(
            json.dumps([{"id": "existing", "name": "Existing", "custom": False}]),
            encoding="utf-8",
        )
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.services.voice_catalog as vc_mod

            monkeypatch.setattr(vc_mod, "catalog_path", lambda b="vieneu_local": catalog_file)
            with pytest.raises(ValueError, match="Giọng đã bị xóa"):
                find_voice("nonexistent", "vieneu_local")

    def test_rename_voice_custom_only(self, tmp_path, monkeypatch):
        catalog_file = tmp_path / "voices" / "catalog.json"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        catalog_file.write_text(
            json.dumps([
                {"id": "custom-voice", "name": "Old Name", "custom": True},
                {"id": "builtin-voice", "name": "Builtin", "custom": False},
            ]),
            encoding="utf-8",
        )
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.services.voice_catalog as vc_mod

            monkeypatch.setattr(vc_mod, "catalog_path", lambda b="vieneu_local": catalog_file)
            rename_voice("custom-voice", "New Name")
            assert find_voice("custom-voice")["name"] == "New Name"
            assert find_voice("builtin-voice")["name"] == "Builtin"

    def test_rename_voice_builtin_raises(self, tmp_path, monkeypatch):
        catalog_file = tmp_path / "voices" / "catalog.json"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        catalog_file.write_text(
            json.dumps([{"id": "builtin", "name": "Builtin", "custom": False}]),
            encoding="utf-8",
        )
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.services.voice_catalog as vc_mod

            monkeypatch.setattr(vc_mod, "catalog_path", lambda b="vieneu_local": catalog_file)
            with pytest.raises(ValueError, match="Chỉ đổi tên giọng tự thêm"):
                rename_voice("builtin", "New Name")

    def test_delete_voice_custom_only(self, tmp_path, monkeypatch):
        catalog_file = tmp_path / "voices" / "catalog.json"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        catalog_file.write_text(
            json.dumps([
                {"id": "custom-del", "name": "To Delete", "custom": True},
                {"id": "builtin-keep", "name": "Keep", "custom": False},
            ]),
            encoding="utf-8",
        )
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.services.voice_catalog as vc_mod

            monkeypatch.setattr(vc_mod, "catalog_path", lambda b="vieneu_local": catalog_file)
            delete_voice("custom-del")
            assert [v["id"] for v in read_catalog()] == ["builtin-keep"]

    def test_delete_voice_builtin_raises(self, tmp_path, monkeypatch):
        catalog_file = tmp_path / "voices" / "catalog.json"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        catalog_file.write_text(
            json.dumps([{"id": "builtin", "name": "Builtin", "custom": False}]),
            encoding="utf-8",
        )
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.services.voice_catalog as vc_mod

            monkeypatch.setattr(vc_mod, "catalog_path", lambda b="vieneu_local": catalog_file)
            with pytest.raises(ValueError, match="Chỉ xóa giọng tự thêm"):
                delete_voice("builtin")


class TestInstallPresets:
    """Test install_presets catalog integration."""

    def test_install_presets_empty_raises(self, tmp_path, monkeypatch):
        catalog_file = tmp_path / "voices" / "catalog.json"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        catalog_file.write_text("[]", encoding="utf-8")
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.services.voice_catalog as vc_mod

            monkeypatch.setattr(vc_mod, "catalog_path", lambda b="vieneu_local": catalog_file)
            with pytest.raises(ValueError, match="VieNeu chưa trả về giọng mặc định"):
                install_presets([])

    def test_install_presets_adds_rows(self, tmp_path, monkeypatch):
        catalog_file = tmp_path / "voices" / "catalog.json"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        catalog_file.write_text("[]", encoding="utf-8")
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.services.voice_catalog as vc_mod

            monkeypatch.setattr(vc_mod, "catalog_path", lambda b="vieneu_local": catalog_file)
            rows = install_presets([["My Voice", "upstream-id-123"]])
            assert len(rows) == 1
            assert rows[0]["id"].startswith("vieneu-")
            assert rows[0]["name"] == "My Voice"
            assert rows[0]["custom"] is False
            assert "upstream_id" in rows[0]

    def test_install_presets_preserves_existing(self, tmp_path, monkeypatch):
        catalog_file = tmp_path / "voices" / "catalog.json"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        catalog_file.write_text(
            json.dumps([{"id": "keep-me", "name": "Keep Me", "custom": True}]),
            encoding="utf-8",
        )
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.services.voice_catalog as vc_mod

            monkeypatch.setattr(vc_mod, "catalog_path", lambda b="vieneu_local": catalog_file)
            rows = install_presets([["New Voice", "upstream-456"]])
            ids = {r["id"] for r in rows}
            assert "keep-me" in ids
            assert len(rows) == 2


class TestVieNeuLocalProvider:
    """Test VieNeuLocalProvider class methods."""

    def test_provider_identity(self):
        provider = VieNeuLocalProvider()
        assert provider.id == "vieneu_local"
        assert provider.name == "vieneu_local"
        assert provider.display_name == "VieNeu Local"
        assert provider.max_characters == 600
        assert provider.audio_suffix == ".wav"
        assert provider.sample_rate == 48000

    def test_init_defaults(self):
        provider = VieNeuLocalProvider()
        assert provider.ffmpeg == ""
        assert provider.allow_download is False
        assert provider.process is None

    def test_init_with_ffmpeg(self):
        provider = VieNeuLocalProvider(ffmpeg="C:/ffmpeg.exe", allow_download=True)
        assert provider.ffmpeg == "C:/ffmpeg.exe"
        assert provider.allow_download is True

    def test_list_voices_empty_catalog(self, tmp_path, monkeypatch):
        catalog_file = tmp_path / "voices" / "catalog.json"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        catalog_file.write_text("[]", encoding="utf-8")
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.providers.vieneu_local as vl_mod

            monkeypatch.setattr(vl_mod, "read_catalog", lambda b="vieneu_local": [])
            provider = VieNeuLocalProvider()
            voices = run_async(provider.list_voices())
            assert voices == ()

    def test_list_voices_returns_voice_objects(self, tmp_path, monkeypatch):
        catalog_file = tmp_path / "voices" / "catalog.json"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        catalog_file.write_text(
            json.dumps([
                {"id": "v1", "name": "Voice One", "custom": False},
                {"id": "v2", "name": "Voice Two", "custom": False},
            ]),
            encoding="utf-8",
        )
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.providers.vieneu_local as vl_mod

            monkeypatch.setattr(
                vl_mod,
                "read_catalog",
                lambda b="vieneu_local": json.loads(catalog_file.read_text()),
            )
            provider = VieNeuLocalProvider()
            voices = run_async(provider.list_voices())
            assert isinstance(voices, tuple)
            assert len(voices) == 2
            assert voices[0].code == "v1"
            assert voices[0].name == "Voice One"
            assert voices[1].language == "vi"

    def test_synthesize_empty_text_raises(self, tmp_path, monkeypatch):
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.providers.vieneu_local as vl_mod

            monkeypatch.setattr(vl_mod, "read_catalog", lambda b="vieneu_local": [])
            provider = VieNeuLocalProvider()
            with pytest.raises(TTSError, match="Nội dung hoặc tốc độ"):
                run_async(provider.synthesize(
                    text="", voice_id="v1", speed=1.0, output_path=tmp_path / "out.wav",
                ))

    def test_synthesize_whitespace_text_raises(self, tmp_path, monkeypatch):
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.providers.vieneu_local as vl_mod

            monkeypatch.setattr(vl_mod, "read_catalog", lambda b="vieneu_local": [])
            provider = VieNeuLocalProvider()
            with pytest.raises(TTSError, match="Nội dung hoặc tốc độ"):
                run_async(provider.synthesize(
                    text="   ", voice_id="v1", speed=1.0, output_path=tmp_path / "out.wav",
                ))

    def test_synthesize_speed_too_low_raises(self, tmp_path, monkeypatch):
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.providers.vieneu_local as vl_mod

            monkeypatch.setattr(vl_mod, "read_catalog", lambda b="vieneu_local": [])
            provider = VieNeuLocalProvider()
            with pytest.raises(TTSError, match="Nội dung hoặc tốc độ"):
                run_async(provider.synthesize(
                    text="Xin chào", voice_id="v1", speed=0.5, output_path=tmp_path / "out.wav",
                ))

    def test_synthesize_speed_too_high_raises(self, tmp_path, monkeypatch):
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.providers.vieneu_local as vl_mod

            monkeypatch.setattr(vl_mod, "read_catalog", lambda b="vieneu_local": [])
            provider = VieNeuLocalProvider()
            with pytest.raises(TTSError, match="Nội dung hoặc tốc độ"):
                run_async(provider.synthesize(
                    text="Xin chào", voice_id="v1", speed=1.5, output_path=tmp_path / "out.wav",
                ))

    def test_synthesize_voice_not_in_catalog_raises(self, tmp_path, monkeypatch):
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            import vkdub.providers.vieneu_local as vl_mod

            monkeypatch.setattr(vl_mod, "read_catalog", lambda b="vieneu_local": [])
            provider = VieNeuLocalProvider()
            with pytest.raises(ValueError, match="Giọng đã bị xóa"):
                run_async(provider.synthesize(
                    text="Xin chào", voice_id="ghost-voice", speed=1.0,
                    output_path=tmp_path / "out.wav",
                ))

    def test_close_when_no_process(self, tmp_path, monkeypatch):
        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            provider = VieNeuLocalProvider()
            run_async(provider.close())
            assert provider.process is None

    def test_close_when_process_running(self, tmp_path, monkeypatch):
        proc = MagicMock()
        proc.returncode = None
        proc.pid = 12345
        proc.stdin = MagicMock()
        proc.stdout = MagicMock()
        proc.wait = AsyncMock()

        async def mock_stop(p):
            pass

        with monkeypatch.context():
            monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
            with patch("vkdub.providers.vieneu_local.stop_owned_process", new=mock_stop):
                provider = VieNeuLocalProvider()
                provider.process = proc
                run_async(provider.close())
                assert provider.process is None
