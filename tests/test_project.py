import json
from pathlib import Path
from unittest.mock import patch

import pytest

from vkdub.domain.project import Project
from vkdub.services.project_service import load_project, save_project


def test_roundtrip_unicode_and_relative_paths(tmp_path):
    project = Project(video_path=tmp_path / "Tiếng Việt.mp4", output_directory=tmp_path / "Xuất")
    target = tmp_path / "demo.vkdub"
    save_project(project, target)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["video_path"] == "Tiếng Việt.mp4"
    assert data["script_review"]["approved"] is False
    assert data["voice"]["provider"] == "vieneu_local"
    assert load_project(target) == project
    assert project.state == "VIDEO_IMPORTED"


def test_empty_project_roundtrip(tmp_path):
    project = Project()
    target = tmp_path / "empty.vkdub"
    save_project(project, target)
    assert load_project(target) == project
    assert project.state == "IDLE"


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": 7},
        {"schema_version": True},
        {"project_id": "bad"},
        {"video_path": 42},
        {"video_path": "bad.mov"},
        {"target_language": []},
        {"subtitles": [{"text": "preserve me"}]},
        {"api_key": "do-not-store"},
        {"script_review": {"approved": True}},
        {"voice": {"speed": 1.2}},
    ],
)
def test_reject_invalid_or_unsupported_projects(tmp_path, change):
    target = tmp_path / "invalid.vkdub"
    save_project(Project(), target)
    data = json.loads(target.read_text(encoding="utf-8"))
    data.update(change)
    target.write_text(json.dumps(data), encoding="utf-8")
    before = target.read_bytes()
    with pytest.raises(ValueError):
        load_project(target)
    assert target.read_bytes() == before


@pytest.mark.parametrize("content", ["broken JSON", "[]", "null", '{"schema_version":1}'])
def test_bad_json(tmp_path, content):
    target = tmp_path / "bad.vkdub"
    target.write_text(content)
    with pytest.raises(ValueError):
        load_project(target)


def test_atomic_save_preserves_old_file(tmp_path):
    target = tmp_path / "keep.vkdub"
    save_project(Project(), target)
    previous = target.read_bytes()
    with patch("vkdub.services.project_service.os.replace", side_effect=OSError("disk failure")):
        with pytest.raises(OSError):
            save_project(Project(video_path=Path("new.mp4")), target)
    assert target.read_bytes() == previous
    assert list(tmp_path.glob("*.tmp")) == []


def test_oversized_save_preserves_readable_previous_file(tmp_path, monkeypatch):
    target = tmp_path / "keep.vkdub"
    save_project(Project(), target)
    previous = target.read_bytes()
    monkeypatch.setattr("vkdub.services.project_service.MAX_PROJECT_BYTES", 100)
    with pytest.raises(ValueError, match="16 MB"):
        save_project(Project(), target)
    assert target.read_bytes() == previous
