"""Unit tests for Vbee rollback, cache invalidation, and re-generation on script changes."""

from uuid import uuid4
import pytest
from PySide6.QtWidgets import QApplication

from vkdub.bridge.local_agent import LocalAgent
from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.orchestrator.pipeline_runner import PipelineRunner
from vkdub.orchestrator.pipeline_state import PipelineState


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_script_edit_invalidates_voice_ready_and_clears_cache(tmp_path):
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"dummy mp4")

    id1, id2 = str(uuid4()), str(uuid4())
    line1 = ScriptLine(id=id1, start_ms=0, end_ms=2000, text="Chào bạn")
    line2 = ScriptLine(id=id2, start_ms=2000, end_ms=4000, text="Hôm nay thời tiết đẹp")
    script = ScriptDocument((line1, line2))

    audio_file = tmp_path / "master_narration_timeline.mp3"
    audio_file.write_bytes(b"ID3" + b"\0" * 2000)

    project = Project(
        video_path=video_path,
        output_directory=tmp_path,
        video_duration_ms=4000,
        script=script,
        master_voice_path=audio_file,
    )
    project.approved_revision_hash = project.revision_hash
    assert project.voice_ready is True

    # User modifies script (edit text of line 1)
    new_line1 = ScriptLine(id=id1, start_ms=0, end_ms=2000, text="Xin chào bạn nhé")
    new_script = ScriptDocument((new_line1, line2))
    project.set_script(new_script)

    # Verify voice is completely invalidated
    assert project.is_approved is False
    assert project.voice_ready is False
    assert project.master_voice_path is None
    assert project.master_voice_script_hash is None


def test_probe_master_voice_rejects_stale_audio_on_script_change(tmp_path):
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"dummy mp4")

    id1 = str(uuid4())
    script1 = ScriptDocument((ScriptLine(id=id1, start_ms=0, end_ms=2000, text="Bản dịch cũ"),))
    audio_file = tmp_path / "master_narration_timeline.mp3"
    audio_file.write_bytes(b"ID3" + b"\0" * 2000)

    hash_file = tmp_path / ".vbee_script_hash"
    hash_file.write_text("old_hash_12345", encoding="utf-8")

    project = Project(
        video_path=video_path,
        output_directory=tmp_path,
        video_duration_ms=2000,
        script=script1,
    )
    # The current revision hash does NOT match "old_hash_12345"
    assert project.revision_hash != "old_hash_12345"

    # _probe_master_voice must reject the stale audio on disk
    probed = project._probe_master_voice()
    assert probed is None
    assert project.voice_ready is False


def test_pipeline_runner_target_step_4_4_forces_regeneration(qapp, tmp_path, monkeypatch):
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"dummy")

    id1 = str(uuid4())
    script = ScriptDocument((ScriptLine(id=id1, start_ms=0, end_ms=2000, text="Kịch bản mới cần đọc"),))
    project = Project(video_path=video_path, output_directory=tmp_path, video_duration_ms=2000, script=script)
    project.approved_revision_hash = project.revision_hash

    # Simulate existing stale audio files
    stale_raw = tmp_path / "vbee_master_raw.mp3"
    stale_raw.write_bytes(b"ID3" + b"old_raw" * 100)
    stale_timeline = tmp_path / "master_narration_timeline.mp3"
    stale_timeline.write_bytes(b"ID3" + b"old_timeline" * 100)
    hash_file = tmp_path / ".vbee_script_hash"
    hash_file.write_text("old_digest", encoding="utf-8")

    agent = LocalAgent()
    generated_call = {"count": 0}

    def fake_generate_vbee(srt_content, target_path, **kwargs):
        generated_call["count"] += 1
        target_path.write_bytes(b"ID3" + b"new_vbee_audio" * 200)
        return target_path

    monkeypatch.setattr(agent, "generate_vbee_sync", fake_generate_vbee)
    monkeypatch.setattr(
        "vkdub.orchestrator.pipeline_runner.build_master_timeline_audio",
        lambda **kwargs: kwargs["output_path"].write_bytes(b"ID3" + b"new_timeline" * 200),
    )

    runner = PipelineRunner(
        project=project,
        local_agent=agent,
        output_dir=tmp_path,
        target_step="4.4",
    )
    runner.run()

    # Must have called generate_vbee_sync instead of reusing stale files
    assert generated_call["count"] == 1
    assert runner.state == PipelineState.REVIEW_READY
    assert hash_file.is_file()
    assert hash_file.read_text(encoding="utf-8") != "old_digest"
