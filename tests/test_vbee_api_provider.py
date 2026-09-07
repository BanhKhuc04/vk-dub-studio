"""Unit tests for VbeeApiProvider, dual-mode settings, and Vbee API workflow integration."""

import json
import wave
from pathlib import Path

import httpx
import pytest

from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.domain.voice import VoiceSettings
from vkdub.integrations.vbee.provider import VbeeApiProvider
from vkdub.integrations.vbee.workflow import VbeeVoiceWorkflow
from vkdub.services.app_settings import AppSettings, load_app_settings, save_app_settings
from vkdub.services.health_service import check_tts_backend


def _create_synthetic_wav(
    path: Path, duration_seconds: float = 1.0, sample_rate: int = 24000
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    num_frames = int(duration_seconds * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_frames)
    return path


def test_app_settings_vbee_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AppSettings properly manages and validates vbee_mode."""
    monkeypatch.setattr("vkdub.services.app_settings.data_root", lambda: tmp_path)

    settings = AppSettings()
    assert settings.vbee_mode == "browser"

    settings.vbee_mode = "api"
    save_app_settings(settings)

    loaded = load_app_settings()
    assert loaded.vbee_mode == "api"

    with pytest.raises(ValueError, match="Chế độ Vbee"):
        AppSettings(vbee_mode="invalid_mode")


def test_health_check_vbee_modes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """check_tts_backend behaves correctly for both browser and api modes."""
    monkeypatch.setattr("vkdub.services.app_settings.data_root", lambda: tmp_path)

    # 1. Browser mode
    save_app_settings(AppSettings(vbee_mode="browser"))
    res_browser = check_tts_backend("vbee")
    assert res_browser.title == "Vbee Dubbing Studio"

    # 2. API mode without credentials
    save_app_settings(AppSettings(vbee_mode="api"))
    monkeypatch.setattr("vkdub.services.credential_service.VbeeAppStore.get", lambda self: None)
    monkeypatch.setattr("vkdub.services.credential_service.VbeeTokenStore.get", lambda self: None)
    res_api_missing = check_tts_backend("vbee")
    assert res_api_missing.title == "Vbee API"
    assert not res_api_missing.ok
    assert res_api_missing.code == "VBEE_API_KEY_MISSING"

    # 3. API mode with credentials
    monkeypatch.setattr(
        "vkdub.services.credential_service.VbeeAppStore.get", lambda self: "app-123"
    )
    monkeypatch.setattr(
        "vkdub.services.credential_service.VbeeTokenStore.get", lambda self: "tok-456"
    )
    res_api_ready = check_tts_backend("vbee")
    assert res_api_ready.ok
    assert res_api_ready.code == "VBEE_API_READY"


@pytest.mark.anyio
async def test_vbee_api_provider_execute_dubbing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Synthesize lines through the API, build VoiceAssets, and assemble master WAV."""
    sent_requests: list[dict] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        sent_requests.append(
            {
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": json.loads(request.content.decode("utf-8")),
            }
        )
        return httpx.Response(
            200,
            headers={"content-type": "audio/mpeg"},
            content=b"ID3\x03\x00\x00\x00\x00\x00\x00fake-mp3-audio-bytes" * 100,
        )

    transport = httpx.MockTransport(mock_handler)

    async def fake_convert(source: Path, target: Path, ffmpeg: str) -> Path:
        return _create_synthetic_wav(target, duration_seconds=1.0)

    async def fake_duration(path: Path, ffprobe: str) -> int:
        return 1000

    monkeypatch.setattr("vkdub.integrations.vbee.provider.convert_to_pcm_wav", fake_convert)
    monkeypatch.setattr("vkdub.integrations.vbee.importer.convert_to_pcm_wav", fake_convert)
    monkeypatch.setattr("vkdub.media.voice_audio.audio_duration", fake_duration)
    monkeypatch.setattr("vkdub.integrations.vbee.provider.audio_duration", fake_duration)

    video = tmp_path / "sample.mp4"
    video.write_bytes(b"\x00" * 1024)

    line0 = ScriptLine.new(0, 1500, "Xin chào các bạn.")
    line1 = ScriptLine.new(1600, 3000, "Đây là thử nghiệm.")
    lines = (line0, line1)
    doc = ScriptDocument(lines=lines)
    project = Project(
        video_path=video,
        target_language="vi",
        script=doc,
        voice=VoiceSettings(provider="vbee", voice_id="vbee-ngoc-huyen", speed=1.1),
    )
    project.approve(True)

    output_dir = tmp_path / "output_api_vbee"
    provider = VbeeApiProvider(
        app_id="my-app-id",
        token="my-token",
        output_dir=output_dir,
        transport=transport,
    )

    progress_events: list[tuple[int, str]] = []

    def progress_cb(pct: int, msg: str) -> None:
        progress_events.append((pct, msg))

    master_path = await provider.execute_dubbing(
        project=project,
        srt_path=tmp_path / "dummy.srt",
        progress_callback=progress_cb,
        check_cancel=lambda: None,
        speed=1.1,
    )

    assert len(sent_requests) == 2
    for req in sent_requests:
        assert req["headers"]["app-id"] == "my-app-id"
        assert req["headers"]["authorization"] == "Bearer my-token"
        assert req["body"]["speed"] == 1.1
        assert req["body"]["voiceCode"] == "hn_female_ngochuyen_full_48k-fhg"

    assert len(project.voice_assets) == 2
    assert line0.id in project.voice_assets
    assert line1.id in project.voice_assets
    asset0 = project.voice_assets[line0.id]
    assert asset0.provider == "vbee"
    assert asset0.voice_id == "hn_female_ngochuyen_full_48k-fhg"
    assert asset0.speed == 1.1
    assert asset0.output_path.is_file()

    assert project.voice_ready
    assert master_path.is_file()
    assert master_path.stat().st_size > 0

    await provider.close()


@pytest.mark.anyio
async def test_vbee_voice_workflow_with_api_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """VbeeVoiceWorkflow orchestrates VbeeApiProvider smoothly through all states."""
    vid = tmp_path / "vid.mp4"
    vid.write_bytes(b"\x00" * 1024)

    line0 = ScriptLine.new(500, 2000, "Câu thứ nhất.")
    lines = (line0,)
    doc = ScriptDocument(lines=lines)
    project = Project(
        video_path=vid,
        target_language="vi",
        script=doc,
        voice=VoiceSettings(
            provider="vbee", voice_id="hn_female_ngochuyen_full_48k-fhg", speed=1.1
        ),
    )
    project.approve(True)

    fake_master = _create_synthetic_wav(tmp_path / "fake_master.wav")

    class MockApiProvider:
        name = "vbee_api"

        async def execute_api_dubbing(
            self, project, ffmpeg, ffprobe, progress_callback, check_cancel, speed=None
        ):
            progress_callback(50, "Đang tạo voice Vbee API câu 1/1…")
            from datetime import UTC, datetime

            from vkdub.domain.voice import VoiceAsset, audio_key, digest, normalized_text
            from vkdub.services.tts_service import file_hash

            wav_file = _create_synthetic_wav(tmp_path / "line_asset.wav")
            key = audio_key(line0.text, project.voice)
            asset = VoiceAsset(
                cache_key=key,
                text_hash=digest(normalized_text(line0.text)),
                provider="vbee",
                voice_id="hn_female_ngochuyen_full_48k-fhg",
                speed=1.1,
                duration_ms=1000,
                output_path=wav_file,
                audio_sha256=file_hash(wav_file),
                generated_at=datetime.now(UTC).isoformat(),
            )
            project.voice_assets[line0.id] = asset
            return {
                "status": "success",
                "lines_count": 1,
                "master_wav": str(fake_master),
                "assets": {line0.id: asset},
            }

        async def close(self):
            pass

    states: list[str] = []
    workflow = VbeeVoiceWorkflow(
        project=project,
        provider=MockApiProvider(),
        ffmpeg="ffmpeg",
        ffprobe="ffprobe",
        state_callback=lambda st, msg: states.append(st.value),
        working_dir=tmp_path / "staging",
        speed=1.1,
    )

    res = await workflow.run()
    assert res["status"] == "success"
    assert res["lines_count"] == 1
    assert "READY" in states
    assert project.voice_ready
