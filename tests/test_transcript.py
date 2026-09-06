import json
from dataclasses import replace

import pytest

from vkdub.domain.project import Project
from vkdub.domain.transcript import (
    SubtitleSegment,
    Transcript,
    TranscriptionSettings,
    srt_timestamp,
    to_srt,
)
from vkdub.services.cache_service import atomic_json, cache_key, read_cached
from vkdub.services.project_service import VOICE, load_project, save_project


@pytest.fixture
def transcript():
    return Transcript(
        (SubtitleSegment(1, 0.2, 1.9, "Hello world."), SubtitleSegment(2, 2.0, 3.5, "Xin chào.")),
        "en",
        "auto",
        4.0,
        "tiny",
        "cpu",
        "a" * 64,
        "b" * 64,
    )


def test_transcript_roundtrip_and_srt(transcript):
    assert Transcript.from_dict(transcript.to_dict()) == transcript
    assert to_srt(transcript) == (
        "1\n00:00:00,200 --> 00:00:01,900\nHello world.\n\n"
        "2\n00:00:02,000 --> 00:00:03,500\nXin chào.\n"
    )
    assert srt_timestamp(59.9996) == "00:01:00,000"
    assert srt_timestamp(3661.234) == "01:01:01,234"


@pytest.mark.parametrize(
    "args",
    [
        (0, 0, 1, "a"),
        (True, 0, 1, "a"),
        (1, -1, 1, "a"),
        (1, 2, 1, "a"),
        (1, 1, 1, "a"),
        (1, 0, float("inf"), "a"),
        (1, float("nan"), 1, "a"),
        (1, 0, 1, ""),
        (1, 0, 1, None),
        (1, True, 2, "a"),
    ],
)
def test_invalid_segments(args):
    with pytest.raises(ValueError):
        SubtitleSegment(*args)


def test_transcript_rejects_overlap_and_beyond_duration(transcript):
    with pytest.raises(ValueError):
        replace(transcript, segments=(SubtitleSegment(1, 0, 2, "a"), SubtitleSegment(2, 1, 3, "b")))
    with pytest.raises(ValueError):
        replace(transcript, duration=0.5)


@pytest.mark.parametrize("payload", [None, [], {}, {"segments": [None]}, {"segments": 1}])
def test_invalid_transcript_document(payload):
    with pytest.raises(ValueError):
        Transcript.from_dict(payload)


def test_no_speech_is_completed(transcript):
    empty = replace(transcript, segments=())
    assert Project(transcript=empty).state == "TRANSCRIBED"
    assert to_srt(empty) == ""


def test_save_transcript_and_settings(tmp_path, transcript):
    project = Project(
        video_path=tmp_path / "speech.mp4",
        transcript=transcript,
        transcription_settings=TranscriptionSettings("tiny", "cpu"),
    )
    target = tmp_path / "transcript.vkdub"
    save_project(project, target)
    assert load_project(target) == project
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["schema_version"] == 6
    assert len(data["transcript"]) == 2
    assert data["subtitles"] == []
    assert data["script_review"]["approved"] is False


def test_migrate_schema_one_without_modifying_source(tmp_path):
    target = tmp_path / "legacy.vkdub"
    save_project(Project(), target)
    data = json.loads(target.read_text(encoding="utf-8"))
    data["schema_version"] = 1
    data["voice"] = VOICE
    data.pop("legacy", None)
    del data["voice_assets"]
    del data["transcription"]
    target.write_text(json.dumps(data), encoding="utf-8")
    before = target.read_bytes()
    loaded = load_project(target)
    assert loaded.transcription_settings == TranscriptionSettings()
    assert loaded.transcript is None
    assert target.read_bytes() == before


def test_invalid_transcript_project_is_not_modified(tmp_path, transcript):
    target = tmp_path / "bad.vkdub"
    save_project(Project(video_path=tmp_path / "source.mp4", transcript=transcript), target)
    data = json.loads(target.read_text(encoding="utf-8"))
    data["transcript"][0]["end"] = -5
    target.write_text(json.dumps(data), encoding="utf-8")
    before = target.read_bytes()
    with pytest.raises(ValueError):
        load_project(target)
    assert target.read_bytes() == before


def test_cache_roundtrip_and_key_validation(tmp_path, transcript):
    target = tmp_path / "cache.json"
    atomic_json(target, transcript.to_dict())
    assert read_cached(target, transcript.cache_key) == transcript
    with pytest.raises(ValueError):
        read_cached(target, "c" * 64)


def test_cache_invalidates_every_material_input():
    args = ["fingerprint", "tiny", "auto", "cpu", "1.2.1", "revision"]
    initial = cache_key(*args)
    for index in range(len(args)):
        changed = args.copy()
        changed[index] += "changed"
        assert cache_key(*changed) != initial


def test_settings_reject_unknown_model_and_device():
    with pytest.raises(ValueError):
        TranscriptionSettings("../outside", "cpu")
    with pytest.raises(ValueError):
        TranscriptionSettings("tiny", "invalid")
