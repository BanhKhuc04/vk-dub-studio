import asyncio
import json
import os
import shutil
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.domain.voice import (
    DEFAULT_VOICE,
    VoiceAsset,
    VoiceSettings,
    audio_key,
    digest,
    normalized_text,
    timing_warning,
)
from vkdub.media.voice_audio import audio_duration, run_audio_command
from vkdub.providers.vbee_tts import VbeeTTSProvider
from vkdub.services.project_service import VOICE, load_project, save_project
from vkdub.services.tts_service import generate_voice, split_text
from vkdub.services.tts_usage import TTSUsage


@pytest.fixture
def project(tmp_path):
    return Project(
        voice=VoiceSettings(),
        video_path=tmp_path / "source.mp4",
        video_duration_ms=20000,
        script=ScriptDocument(
            (
                ScriptLine(str(uuid4()), 0, 10000, "Xin chào"),
                ScriptLine(str(uuid4()), 10000, 20000, "Cảm ơn"),
            )
        ),
    )


@pytest.fixture
def media(tmp_path):
    ffmpeg = os.environ.get("FFMPEG_PATH") or shutil.which("ffmpeg")
    ffprobe = os.environ.get("FFPROBE_PATH") or shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("Real FFmpeg/ffprobe needed for audio integration tests")
    path = tmp_path / "test-tone.mp3"
    subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.3",
            "-c:a",
            "libmp3lame",
            str(path),
        ],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return ffmpeg, ffprobe, path.read_bytes()


@pytest.mark.parametrize("text", ["a" * 1001, "Xin chào. " * 100, "😀" * 301, "Một\nHai\n" * 100])
def test_split_request_limit(text):
    chunks = split_text(text)
    assert all(0 < len(chunk) <= 300 for chunk in chunks)
    assert "".join("".join(chunks).split()) == "".join(normalized_text(text).split())


def test_cache_identity_changes_only_synthesis_inputs():
    settings = VoiceSettings()
    base = audio_key(" Xin chào ", settings)
    assert base == audio_key("Xin chào", settings)
    assert base == audio_key("Xin cha\u0300o", settings)
    assert base == audio_key("Xin chào", replace(settings, volume=0.5))
    assert base != audio_key("Xin chào!", settings)
    assert base != audio_key("Xin chào", replace(settings, speed=1.1))
    assert base != audio_key("Xin chào", replace(settings, voice_id="other"))
    assert audio_key("Xin\nchào", settings) != base


@pytest.mark.parametrize(
    "change",
    [
        {"speed": True},
        {"speed": 1.4},
        {"speed": float("nan")},
        {"volume": -1},
        {"voice_id": "../bad"},
        {"provider": "invented"},
    ],
)
def test_voice_settings_validate(change):
    with pytest.raises(ValueError):
        VoiceSettings(**change)


@pytest.mark.parametrize("actual, expected", [(1000, ""), (1050, "chỉnh nhẹ"), (1500, "quá dài")])
def test_actual_duration_warnings(actual, expected):
    result = timing_warning(actual, 1000)
    assert expected in result if expected else result == ""


def test_schema_four_migration_preserves_approval(project, tmp_path):
    project.approve(True)
    path = tmp_path / "legacy.vkdub"
    save_project(project, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(schema_version=4, voice=VOICE)
    data.pop("legacy", None)
    del data["voice_assets"]
    path.write_text(json.dumps(data), encoding="utf-8")
    before = path.read_bytes()
    migrated = load_project(path)
    assert migrated.is_approved and migrated.voice.voice_id == DEFAULT_VOICE
    assert path.read_bytes() == before


def make_run(project, tmp_path, media, handler):
    ffmpeg, ffprobe, _ = media
    provider = VbeeTTSProvider(
        "test-app", "test-token", TTSUsage(tmp_path / "usage.db"), httpx.MockTransport(handler)
    )
    events = []

    def complete(identifier, asset, error):
        events.append((identifier, asset, error))
        if asset:
            project.voice_assets[identifier] = asset

    async def run(force=False, ids=None, cancel=lambda: None):
        await generate_voice(
            project,
            provider,
            tmp_path / "cache",
            ffmpeg,
            ffprobe,
            lambda *_: None,
            cancel,
            complete,
            ids,
            force,
        )

    return run, events


def test_real_audio_cache_regenerate_roundtrip_and_gate(project, tmp_path, media):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "audio/mpeg"}, content=media[2])

    run, events = make_run(project, tmp_path, media, handler)
    with pytest.raises(ValueError, match="chưa được duyệt"):
        asyncio.run(run())
    assert not calls
    project.approve(True)
    asyncio.run(run())
    assert project.voice_ready and len(calls) == 2 and all(not event[2] for event in events)
    assert all(250 <= a.duration_ms <= 400 for a in project.voice_assets.values())
    asyncio.run(run())
    assert len(calls) == 2  # Both lines reused and re-probed, no paid request.
    first = project.script.lines[0]
    asyncio.run(run(force=True, ids={first.id}))
    assert len(calls) == 3
    path = tmp_path / "voice.vkdub"
    save_project(project, path)
    loaded = load_project(path)
    assert loaded == project and loaded.state == "VOICE_READY"
    assert "test-token" not in path.read_text(encoding="utf-8")
    project.set_script(
        replace(
            project.script, lines=(replace(first, text=first.text + "!"), project.script.lines[1])
        )
    )
    assert not project.voice_ready and project.current_voice(first.id) is None
    with pytest.raises(ValueError):
        asyncio.run(run())
    assert len(calls) == 3
    project.approve(True)
    asyncio.run(run())
    assert len(calls) == 4  # Changed line only; unchanged line reused.


def test_failed_chunk_retry_reuses_completed_chunks(project, tmp_path, media):
    project.script = ScriptDocument((replace(project.script.lines[0], text="a" * 500),))
    project.approve(True)
    seen = []
    fail = True

    def handler(request):
        seen.append(json.loads(request.content)["text"])
        if fail and len(seen) == 2:
            return httpx.Response(500)
        return httpx.Response(200, headers={"content-type": "audio/mpeg"}, content=media[2])

    run, events = make_run(project, tmp_path, media, handler)
    asyncio.run(run())
    assert events[-1][2] and not project.voice_ready
    fail = False
    asyncio.run(run())
    assert len(seen) == 3 and len(seen[-1]) == 200
    assert (
        project.voice_ready and 500 <= next(iter(project.voice_assets.values())).duration_ms <= 800
    )
    assert not list((tmp_path / "cache").glob("voice-*"))


def test_one_failure_preserves_other_lines(project, tmp_path, media):
    project.approve(True)

    def handler(request):
        if json.loads(request.content)["text"] == "Cảm ơn":
            return httpx.Response(400)
        return httpx.Response(200, headers={"content-type": "audio/mpeg"}, content=media[2])

    run, events = make_run(project, tmp_path, media, handler)
    asyncio.run(run())
    assert len(project.voice_assets) == 1 and not project.voice_ready
    assert events[0][1] and events[1][2]


def test_tampered_cache_never_automatically_rebills(project, tmp_path, media):
    project.approve(True)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "audio/mpeg"}, content=media[2])

    run, events = make_run(project, tmp_path, media, handler)
    asyncio.run(run())
    next(iter(project.voice_assets.values())).output_path.write_bytes(b"corrupt")
    asyncio.run(run())
    assert len(calls) == 2 and any("Cache voice hỏng" in e[2] for e in events)


def test_approval_change_between_requests_stops_job(project, tmp_path, media):
    project.approve(True)
    calls = []

    def handler(request):
        calls.append(request)
        project.approved_revision_hash = None
        return httpx.Response(200, headers={"content-type": "audio/mpeg"}, content=media[2])

    run, events = make_run(project, tmp_path, media, handler)
    with pytest.raises(ValueError):
        asyncio.run(run())
    assert len(calls) == 1 and not events and not project.voice_assets
    assert not list((tmp_path / "cache").glob("voice-*"))


def test_cancel_cleans_download_and_preserves_script(project, tmp_path, media):
    project.approve(True)
    source = project.script

    def handler(request):
        raise asyncio.CancelledError

    run, events = make_run(project, tmp_path, media, handler)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())
    assert project.script == source and project.is_approved and not events
    assert not list((tmp_path / "cache").glob("voice-*"))


def test_media_command_timeout_reaps_process(media):
    import sys

    async def run():
        with pytest.raises(TimeoutError):
            await run_audio_command([sys.executable, "-c", "import time; time.sleep(10)"], 0.1)

    asyncio.run(run())


def test_probe_rejects_non_audio(tmp_path, media):
    path = tmp_path / "bad.mp3"
    path.write_bytes(b"not audio")
    with pytest.raises(ValueError):
        asyncio.run(audio_duration(path, media[1]))


def test_missing_audio_prevents_ready(project, tmp_path):
    project.approve(True)
    line = project.script.lines[0]
    path = tmp_path / "missing.wav"
    asset = VoiceAsset(
        audio_key(line.text, project.voice),
        digest(normalized_text(line.text)),
        "vbee",
        DEFAULT_VOICE,
        1,
        1000,
        path,
        "a" * 64,
        datetime.now(UTC).isoformat(),
    )
    project.voice_assets[line.id] = asset
    assert project.current_voice(line.id) is None and not project.voice_ready
    data = asset.to_dict()
    data["duration_ms"] = -1
    with pytest.raises(ValueError):
        VoiceAsset.from_dict(data, tmp_path)
