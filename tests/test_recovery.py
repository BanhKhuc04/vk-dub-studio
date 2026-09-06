from uuid import uuid4

from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.services.recovery_service import (
    clear_recovery_state,
    get_recovery_dir,
    has_recovery_state,
    load_recovery_state,
    save_recovery_state,
)


def test_recovery_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path / "data"))

    # Initial state: no recovery
    assert has_recovery_state() is False
    assert load_recovery_state() is None

    # Create dummy project
    line1 = ScriptLine(id=str(uuid4()), start_ms=0, end_ms=2000, text="Câu một")
    line2 = ScriptLine(id=str(uuid4()), start_ms=2500, end_ms=5000, text="Câu hai")
    script = ScriptDocument(lines=(line1, line2))
    project = Project(
        video_path=tmp_path / "video.mp4",
        script=script,
    )

    # Save recovery state
    saved_path = save_recovery_state(project, original_save_path=tmp_path / "orig.vkdub")
    assert saved_path.is_file()
    assert has_recovery_state() is True

    # Load recovery state
    loaded = load_recovery_state()
    assert loaded is not None
    loaded_proj, meta = loaded
    assert len(loaded_proj.script.lines) == 2
    assert meta.get("script_lines") == 2
    assert "video.mp4" in meta.get("video_name", "")
    assert "orig.vkdub" in meta.get("original_save_path", "")

    # Clear recovery state
    clear_recovery_state()
    assert has_recovery_state() is False
    assert load_recovery_state() is None


def test_recovery_corrupt_file(tmp_path, monkeypatch):
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path / "data"))
    rec_dir = get_recovery_dir()
    rec_file = rec_dir / "recovery_state.vkdub"
    rec_file.write_text("CORRUPT NOT JSON DATA")

    # Should safely return None instead of raising unhandled exception
    assert load_recovery_state() is None
