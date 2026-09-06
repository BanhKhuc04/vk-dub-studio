import asyncio
import json
from pathlib import Path

import httpx
import pytest

from vkdub.domain.voice import (
    DEFAULT_ELEVENLABS_LABEL,
    DEFAULT_ELEVENLABS_VOICE,
    POPULAR_ELEVENLABS_VOICES,
    VoiceSettings,
)
from vkdub.providers.elevenlabs_tts import (
    ELEVENLABS_API_BASE,
    ElevenLabsTTSProvider,
)
from vkdub.providers.tts import TTSError
from vkdub.services.credential_service import ElevenLabsKeyStore, redact
from vkdub.services.tts_usage import TTSUsage


def provider(tmp_path: Path, handler):
    return ElevenLabsTTSProvider(
        "secret-elevenlabs-key",
        TTSUsage(tmp_path / "usage.db"),
        httpx.MockTransport(handler),
    )


class MockKeyring:
    def __init__(self):
        self.vault: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, account: str) -> str | None:
        return self.vault.get((service, account))

    def set_password(self, service: str, account: str, value: str) -> None:
        self.vault[(service, account)] = value

    def delete_password(self, service: str, account: str) -> None:
        self.vault.pop((service, account), None)


# -------------------------------------------------------------
# 1. KeyStore Tests
# -------------------------------------------------------------
def test_elevenlabs_keystore_save_and_retrieve():
    backend = MockKeyring()
    store = ElevenLabsKeyStore(backend=backend)
    assert store.get() is None

    store.save("el-key-1234567890abcdef")
    assert store.get() == "el-key-1234567890abcdef"
    assert "el-key-1234567890abcdef" not in redact("api error with el-key-1234567890abcdef inside")

    store.delete()
    assert store.get() is None


def test_elevenlabs_keystore_invalid_values():
    backend = MockKeyring()
    store = ElevenLabsKeyStore(backend=backend)
    with pytest.raises(ValueError):
        store.save("")
    with pytest.raises(ValueError):
        store.save("   ")
    with pytest.raises(ValueError):
        store.save("key with spaces")


# -------------------------------------------------------------
# 2. Domain VoiceSettings Tests
# -------------------------------------------------------------
def test_voice_settings_elevenlabs():
    settings = VoiceSettings(
        provider="elevenlabs",
        voice_id=DEFAULT_ELEVENLABS_VOICE,
        display_name=DEFAULT_ELEVENLABS_LABEL,
        speed=1.0,
    )
    assert settings.provider == "elevenlabs"
    assert settings.voice_id == DEFAULT_ELEVENLABS_VOICE

    # Invalid provider raises ValueError
    with pytest.raises(ValueError, match="Chưa có adapter"):
        VoiceSettings(provider="invalid_tts")


# -------------------------------------------------------------
# 3. Provider Init & Request Tests
# -------------------------------------------------------------
def test_elevenlabs_init_validation():
    with pytest.raises(TTSError, match="Thiếu ElevenLabs API Key"):
        ElevenLabsTTSProvider("")
    with pytest.raises(TTSError, match="Thiếu ElevenLabs API Key"):
        ElevenLabsTTSProvider("   ")

    p = ElevenLabsTTSProvider("my-test-key")
    assert p.headers["xi-api-key"] == "my-test-key"
    assert p.max_characters == 1000


def test_elevenlabs_synthesize_success(tmp_path: Path):
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        expected_url = f"{ELEVENLABS_API_BASE}/text-to-speech/{DEFAULT_ELEVENLABS_VOICE}"
        assert str(request.url) == expected_url
        assert request.headers["xi-api-key"] == "secret-elevenlabs-key"
        payload = json.loads(request.content)
        assert payload["text"] == "Xin chào thế giới"
        assert payload["model_id"] == "eleven_multilingual_v2"
        assert payload["voice_settings"]["speed"] == 1.1
        return httpx.Response(
            200, headers={"Content-Type": "audio/mpeg"}, content=b"elevenlabs audio data"
        )

    api = provider(tmp_path, handler)
    target = tmp_path / "out.mp3"
    result = asyncio.run(api.synthesize("Xin chào thế giới", DEFAULT_ELEVENLABS_VOICE, 1.1, target))

    assert result == target
    assert target.read_bytes() == b"elevenlabs audio data"
    assert len(requests) == 1
    assert api.usage.monthly() == (1, 17, 0)
    assert "secret-elevenlabs-key" not in redact("request secret-elevenlabs-key done")


@pytest.mark.parametrize(
    "status,expected_substr",
    [
        (401, "xác thực"),
        (429, "hết hạn mức"),
        (400, "từ chối yêu cầu"),
        (500, "HTTP 500"),
    ],
)
def test_elevenlabs_http_errors(tmp_path: Path, status: int, expected_substr: str):
    def handler(request: httpx.Request):
        return httpx.Response(status, content=b"error detail")

    api = provider(tmp_path, handler)
    with pytest.raises(TTSError) as exc_info:
        asyncio.run(api.synthesize("Xin chào", DEFAULT_ELEVENLABS_VOICE, 1.0, tmp_path / "a.mp3"))

    assert expected_substr in str(exc_info.value)
    assert api.usage.monthly() == (1, 8, 1)


@pytest.mark.parametrize("text", ["", "   ", "x" * 1001])
def test_elevenlabs_invalid_text_rejected(tmp_path: Path, text: str):
    api = provider(tmp_path, lambda req: httpx.Response(200))
    with pytest.raises(TTSError):
        asyncio.run(api.synthesize(text, DEFAULT_ELEVENLABS_VOICE, 1.0, tmp_path / "a.mp3"))


def test_elevenlabs_list_voices_success(tmp_path: Path):
    sample_response = {
        "voices": [
            {"voice_id": "v1", "name": "Custom Voice", "category": "cloned"},
            {"voice_id": "v2", "name": "Default Rachel", "category": "premade"},
        ]
    }

    def handler(request: httpx.Request):
        assert str(request.url) == f"{ELEVENLABS_API_BASE}/voices"
        return httpx.Response(200, json=sample_response)

    api = provider(tmp_path, handler)
    voices = asyncio.run(api.list_voices())
    assert len(voices) == 2
    assert voices[0].code == "v1"
    assert "Custom Voice" in voices[0].name
    assert voices[1].code == "v2"


def test_elevenlabs_list_voices_error_fallback(tmp_path: Path):
    def handler(request: httpx.Request):
        return httpx.Response(500, content=b"server error")

    api = provider(tmp_path, handler)
    voices = asyncio.run(api.list_voices())
    assert voices == POPULAR_ELEVENLABS_VOICES


def test_ui_provider_switching_and_credential_flow(qtbot, tmp_path: Path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from vkdub.ui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("vkdub.media.process.MediaTools.detect", lambda self: None)

    backend = MockKeyring()
    monkeypatch.setattr(ElevenLabsKeyStore, "_get_backend", lambda self: backend)

    window = MainWindow()
    window.legacy_tts_enabled = True
    window.project.voice = VoiceSettings()
    window.tts.read_credentials()
    qtbot.addWidget(window)
    try:
        # Default is Vbee
        assert window.project.voice.provider == "vbee"
        assert "Vbee" in window.tts.panel.settings.text()

        # Switch to ElevenLabs
        idx = window.tts.panel.provider.findData("elevenlabs")
        assert idx >= 0
        window.tts.panel.provider.setCurrentIndex(idx)

        assert window.project.voice.provider == "elevenlabs"
        assert window.project.voice.voice_id == DEFAULT_ELEVENLABS_VOICE
        assert "ElevenLabs" in window.tts.panel.settings.text()
        assert not window.tts.configured
        assert "Thiếu ElevenLabs API Key" in window.tts.credential_reason

        # Configure ElevenLabs API Key
        backend.set_password(
            ElevenLabsKeyStore.service, ElevenLabsKeyStore.account, "valid-elevenlabs-key"
        )
        window.tts.read_credentials()
        assert window.tts.configured
        assert "Đã cấu hình ElevenLabs" in window.tts.credential_reason
    finally:
        window.dirty = False
        window.close()
