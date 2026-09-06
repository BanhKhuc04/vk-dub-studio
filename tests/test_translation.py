import asyncio
import json
from dataclasses import replace

import pytest

from vkdub.domain.project import Project
from vkdub.domain.transcript import SubtitleSegment, Transcript
from vkdub.domain.translation import GEMINI_MODEL, Translation, source_digest, validate_response
from vkdub.services.project_service import VOICE, load_project, save_project
from vkdub.services.translation_service import batches, translate_transcript, translation_key


@pytest.fixture
def source():
    return Transcript(
        (SubtitleSegment(1, 0.2, 1.9, "Hello world."), SubtitleSegment(2, 2.0, 3.5, "Thank you.")),
        "en",
        "auto",
        4.0,
        "tiny",
        "cpu",
        "a" * 64,
        "b" * 64,
    )


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        {},
        {"segments": []},
        {"segments": [{"id": 1, "translation": ""}]},
        {"segments": [{"id": True, "translation": "text"}]},
        {"segments": [{"id": "1", "translation": "text"}]},
        {"segments": [{"id": 2, "translation": "text"}]},
        {"segments": [{"id": 1, "translation": "text", "extra": True}]},
        {"segments": [{"id": 1, "translation": "text"}], "extra": True},
        {"segments": [{"id": 1, "translation": "\0"}]},
        {"segments": [{"id": 1, "translation": "a" * 12001}]},
    ],
)
def test_strict_response_validation(bad):
    with pytest.raises(ValueError):
        validate_response(bad, [1])


def test_duplicate_and_reordered_ids_rejected():
    for ids in ([1, 1], [2, 1]):
        with pytest.raises(ValueError):
            validate_response({"segments": [{"id": i, "translation": "a"} for i in ids]}, [1, 2])


def test_translation_roundtrip_preserves_source_and_never_approves(source, tmp_path):
    draft = Translation(source_digest(source), ("Xin chào thế giới.", "Cảm ơn."))
    project = Project(video_path=tmp_path / "source.mp4", transcript=source, translation=draft)
    path = tmp_path / "draft.vkdub"
    save_project(project, path)
    loaded = load_project(path)
    assert loaded == project
    assert loaded.transcript == source
    assert loaded.state == "REVIEW_REQUIRED"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 6
    assert data["script_review"] == {"approved": False, "approved_revision_hash": None}
    assert "api_key" not in data
    data["transcript"][0]["text"] = "Different source."
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="khớp"):
        load_project(path)


def test_schema_two_migrates_without_writing(source, tmp_path):
    path = tmp_path / "old.vkdub"
    project = Project(video_path=tmp_path / "source.mp4", transcript=source)
    save_project(project, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema_version"] = 2
    data["voice"] = VOICE
    data.pop("legacy", None)
    del data["voice_assets"]
    del data["translation"]
    path.write_text(json.dumps(data), encoding="utf-8")
    before = path.read_bytes()
    from vkdub.domain.voice import VoiceSettings

    project.voice = VoiceSettings()
    assert load_project(path) == project
    assert path.read_bytes() == before


def test_cache_identity_changes_with_prompt_inputs():
    request = {
        "segments": [{"id": 1, "start": 0, "end": 1, "text": "hello"}],
        "source_language": "en",
        "target_language": "vi",
    }
    old = translation_key(request, "gemini", GEMINI_MODEL)
    for field, value in (("source_language", "zh"), ("target_language", "ja"), ("segments", [])):
        assert translation_key({**request, field: value}, "gemini", GEMINI_MODEL) != old
    assert translation_key(request, "other", GEMINI_MODEL) != old
    assert translation_key(request, "gemini", "other") != old


class FixtureProvider:
    """Test-only deterministic provider. Never imported into the application."""

    name = "gemini"
    model = GEMINI_MODEL

    def __init__(self):
        self.calls = 0
        self.fail_at = None

    async def translate(self, request):
        self.calls += 1
        if self.calls == self.fail_at:
            raise ValueError("test failure")
        return {
            "segments": [
                {"id": row["id"], "translation": f"Bản thử {row['id']}"}
                for row in request["segments"]
            ]
        }


def run_translate(source, provider, directory, reuse=True, check=lambda: None):
    return asyncio.run(
        translate_transcript(source, provider, directory, reuse, lambda *a: None, check)
    )


def test_batches_partial_failure_reuses_only_valid_completed_batches(source, tmp_path):
    long = replace(
        source,
        segments=tuple(SubtitleSegment(i, i, i + 0.5, "Sentence") for i in range(1, 62)),
        duration=63,
    )
    assert [len(g) for g in batches(long)] == [30, 30, 1]
    provider = FixtureProvider()
    provider.fail_at = 2
    with pytest.raises(ValueError, match="test failure"):
        run_translate(long, provider, tmp_path)
    assert len(list(tmp_path.glob("*.json"))) == 1
    provider.fail_at = None
    draft = run_translate(long, provider, tmp_path)
    assert provider.calls == 4  # Retry skipped the already-paid first group.
    assert len(draft.texts) == 61
    assert run_translate(long, provider, tmp_path) == draft
    assert provider.calls == 4
    run_translate(long, provider, tmp_path, reuse=False)
    assert provider.calls == 7


def test_bad_cache_never_silently_makes_paid_request(source, tmp_path):
    provider = FixtureProvider()
    run_translate(source, provider, tmp_path)
    next(tmp_path.glob("*.json")).write_text("{}")
    with pytest.raises(ValueError, match="Cache"):
        run_translate(source, provider, tmp_path)
    assert provider.calls == 1


def test_cancel_before_first_request(source, tmp_path):
    provider = FixtureProvider()

    def stop():
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        run_translate(source, provider, tmp_path, check=stop)
    assert provider.calls == 0


def test_empty_and_oversized_source_never_sent(source, tmp_path):
    provider = FixtureProvider()
    for invalid in (
        replace(source, segments=()),
        replace(source, segments=(SubtitleSegment(1, 0, 1, "a" * 6001),)),
    ):
        with pytest.raises(ValueError):
            run_translate(invalid, provider, tmp_path)
    assert provider.calls == 0
