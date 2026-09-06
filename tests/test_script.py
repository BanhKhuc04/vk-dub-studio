import json
from dataclasses import replace
from pathlib import Path

import pytest

from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine, draft_from_source, validate_script
from vkdub.domain.transcript import SubtitleSegment, Transcript
from vkdub.domain.translation import Translation, source_digest
from vkdub.services import script_service as edit
from vkdub.services.project_service import VOICE, load_project, save_project
from vkdub.services.srt_service import parse_srt, script_to_srt, write_srt


@pytest.fixture
def project(tmp_path):
    source = Transcript(
        (SubtitleSegment(1, 1, 4, "Hello world"), SubtitleSegment(2, 5, 9, "Thank you")),
        "en",
        "en",
        11,
        "tiny",
        "cpu",
        "a" * 64,
        "b" * 64,
    )
    return Project(
        video_path=tmp_path / "source.mp4",
        transcript=source,
        translation=Translation(source_digest(source), ("Xin chào thế giới", "Cảm ơn bạn")),
    )


def test_translation_stops_for_review_and_confirmation_is_required(project):
    assert project.state == "REVIEW_REQUIRED"
    assert not project.is_approved
    with pytest.raises(ValueError):
        project.approve(False)
    with pytest.raises(ValueError):
        project.require_approval()
    revision = project.approve(True)
    assert len(revision) == 64
    assert project.state == "APPROVED"
    assert project.require_approval() == revision


@pytest.mark.parametrize(
    "change",
    [
        {"text": "Xin chào thế giới!"},
        {"text": "Xin chào thế giới "},
        {"start_ms": 1001},
        {"end_ms": 3999},
        {"source_ids": ()},
    ],
)
def test_every_material_edit_revokes_and_requires_new_approval(project, change):
    source, translation = project.transcript, project.translation
    original = project.script
    project.approve(True)
    project.set_script(edit.edit_line(original, 0, **change))
    assert project.approved_revision_hash is None
    assert project.state == "REVIEW_REQUIRED"
    with pytest.raises(ValueError):
        project.require_approval()
    project.set_script(original)  # Undo does not restore approval.
    assert not project.is_approved
    assert project.transcript is source and project.translation is translation


@pytest.mark.parametrize(
    "change",
    [
        {"start_ms": -1},
        {"end_ms": 1000},
        {"end_ms": 999},
        {"end_ms": 11001},
        {"end_ms": 5001},
        {"text": " "},
        {"text": "a" * 12001},
    ],
)
def test_validation_blocks_approval_but_keeps_draft_saveable(project, tmp_path, change):
    project.set_script(edit.edit_line(project.script, 0, **change))
    assert not project.script_valid
    with pytest.raises(ValueError):
        project.approve(True)
    path = tmp_path / "invalid-draft.vkdub"
    save_project(project, path)
    assert load_project(path).script == project.script


def test_duration_estimate_is_warning_not_fake_voice(project):
    project.set_script(edit.edit_line(project.script, 0, text="một " * 30))
    issues = validate_script(project.script, project.duration_ms)
    assert any(issue.severity == "warning" for issue in issues)
    assert project.script_valid
    assert project.approve(True)


def test_approval_persists_exact_revision_and_tampering_revokes(project, tmp_path):
    original = project.approve(True)
    path = tmp_path / "approved.vkdub"
    save_project(project, path)
    loaded = load_project(path)
    assert loaded.is_approved and loaded.require_approval() == original
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 6
    data["script"]["lines"][0]["text"] += "!"
    path.write_text(json.dumps(data), encoding="utf-8")
    before = path.read_bytes()
    changed = load_project(path)
    assert changed.script.lines[0].text.endswith("!")
    assert changed.approved_revision_hash is None
    assert changed.state == "REVIEW_REQUIRED"
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("video_path", Path("different.mp4")),
        ("target_language", "en"),
        ("video_duration_ms", 12000),
        ("project_id", "another-project"),
    ],
)
def test_context_change_cannot_reuse_approval_even_if_set_outside_ui(project, field, value):
    project.approve(True)
    setattr(project, field, value)
    assert not project.is_approved
    with pytest.raises(ValueError):
        project.require_approval()


def test_schema_three_translation_migrates_to_editable_unapproved_script(project, tmp_path):
    path = tmp_path / "legacy.vkdub"
    save_project(project, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema_version"] = 3
    data["voice"] = VOICE
    data.pop("legacy", None)
    del data["voice_assets"]
    del data["script"]
    del data["video_duration_ms"]
    path.write_text(json.dumps(data), encoding="utf-8")
    before = path.read_bytes()
    migrated = load_project(path)
    assert migrated.script == project.script
    assert migrated.transcript == project.transcript
    assert not migrated.is_approved
    assert path.read_bytes() == before


def test_source_only_manual_draft_has_blank_vietnamese(project):
    draft = draft_from_source(project.transcript)
    assert [line.text for line in draft.lines] == ["", ""]
    assert all(line.source_ids for line in draft.lines)


def test_split_merge_add_delete_replace_preserve_source_lineage(project):
    initial = project.script
    split = edit.split_line(initial, 0, 8, 2500)
    assert [s.start_ms for s in split.lines] == [1000, 2500, 5000]
    assert split.lines[0].source_ids == split.lines[1].source_ids == (1,)
    merged = edit.merge_lines(split, 0)
    assert merged == initial
    combined = edit.merge_lines(initial, 0)
    assert combined.lines[0].source_ids == (1, 2)
    assert combined.lines[0].end_ms == 9000
    added = edit.add_line(initial, 0, 0)
    assert added.lines[1].start_ms == 4000 and added.lines[1].end_ms == 5000
    assert added.lines[1].text == ""
    assert edit.delete_line(added, 1) == initial
    replaced = edit.replace_text(initial, "bạn", "mọi người")
    assert replaced.lines[1].text == "Cảm ơn mọi người"
    assert project.transcript.segments[1].text == "Thank you"


def test_reordering_refuses_overlap_but_allows_repairing_timeline_order(project):
    with pytest.raises(ValueError):
        edit.move_line(project.script, 0, 1)
    reversed_draft = replace(project.script, lines=tuple(reversed(project.script.lines)))
    assert edit.move_line(reversed_draft, 0, 1) == project.script


@pytest.mark.parametrize("point,cursor", [(1000, 3), (4000, 3), (2500, 0), (2500, 100)])
def test_invalid_split_is_rejected(project, point, cursor):
    with pytest.raises(ValueError):
        edit.split_line(project.script, 0, cursor, point)


def test_srt_multiline_unicode_roundtrip_is_unapproved_and_atomic(project, tmp_path, monkeypatch):
    project.set_script(edit.edit_line(project.script, 0, text="Xin chào!\nTiếng Việt 😀"))
    output = script_to_srt(project.script, project.duration_ms)
    loaded = parse_srt("\ufeff" + output.replace("\n", "\r\n"))
    assert [s.text for s in loaded.lines] == [s.text for s in project.script.lines]
    assert [s.start_ms for s in loaded.lines] == [1000, 5000]
    path = tmp_path / "script.srt"
    path.write_text("keep", encoding="utf-8")

    def fail(*args):
        raise OSError("disk failure")

    monkeypatch.setattr("vkdub.services.srt_service.os.replace", fail)
    with pytest.raises(OSError):
        write_srt(path, project.script)
    assert path.read_text() == "keep"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize(
    "text",
    [
        "",
        "junk",
        "1\n00:61:00,000 --> 00:62:00,000\nHi",
        "1\n00:00:00,000 --> 00:00:01,000\n",
        "1\ninvalid --> invalid\nHi",
    ],
)
def test_malformed_srt_rejected(text):
    with pytest.raises(ValueError):
        parse_srt(text)


def test_srt_invalid_timing_can_be_loaded_for_repair_but_not_exported():
    script = parse_srt("1\n00:00:02,000 --> 00:00:01,000\nCần sửa")
    assert any(i.severity == "error" for i in validate_script(script))
    with pytest.raises(ValueError):
        script_to_srt(script)


def test_no_script_empty_script_and_no_video_never_approve():
    for project in (
        Project(),
        Project(script=ScriptDocument(())),
        Project(script=ScriptDocument((ScriptLine.new(0, 1000, "Chào"),))),
    ):
        with pytest.raises(ValueError):
            project.approve(True)


def test_srt_blank_lines_normalize_without_modifying_draft():
    draft = ScriptDocument((ScriptLine.new(0, 4000, "Dòng một\n\nDòng hai"),))
    reloaded = parse_srt(script_to_srt(draft))
    assert reloaded.lines[0].text == "Dòng một\nDòng hai"
    assert draft.lines[0].text == "Dòng một\n\nDòng hai"
