"""Unit tests for PipelineRunner, checkpoints, and substep state management."""

import pytest
from PySide6.QtWidgets import QApplication

from vkdub.bridge.local_agent import LocalAgent
from vkdub.domain.project import Project
from vkdub.orchestrator.checkpoint import (
    clear_checkpoint,
    load_checkpoint,
    save_checkpoint,
)
from vkdub.orchestrator.pipeline_runner import PipelineRunner, _timeline_audio_is_usable
from vkdub.orchestrator.pipeline_state import (
    ArtifactRegistry,
    PipelineState,
    SubstepInfo,
    SubstepStatus,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_timeline_checkpoint_rebuilds_when_duration_drift_is_measurable(
    monkeypatch, tmp_path
):
    audio = tmp_path / "timeline.mp3"
    audio.write_bytes(b"ID3" + b"x" * 2048)
    monkeypatch.setattr(
        "vkdub.orchestrator.pipeline_runner.get_audio_duration_ms", lambda _path: 66_872
    )

    assert not _timeline_audio_is_usable(audio, 63_646)
    assert _timeline_audio_is_usable(audio, 66_800)


def test_checkpoint_save_and_load(tmp_path):
    artifacts = ArtifactRegistry(
        original_srt=tmp_path / "original.srt",
        translated_srt=tmp_path / "translated.srt",
    )
    artifacts.original_srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    artifacts.translated_srt.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nXin chào\n", encoding="utf-8"
    )

    substeps = [
        SubstepInfo(id="4.1", name="Transcription", status=SubstepStatus.SUCCESS, progress=100),
        SubstepInfo(id="4.2", name="ChatGPT", status=SubstepStatus.SUCCESS, progress=100),
        SubstepInfo(id="4.3", name="ScriptPrep", status=SubstepStatus.PENDING, progress=0),
        SubstepInfo(id="4.4", name="Vbee", status=SubstepStatus.PENDING, progress=0),
    ]

    saved_file = save_checkpoint(tmp_path, PipelineState.TRANSLATED, artifacts, substeps)
    assert saved_file.is_file()

    loaded = load_checkpoint(tmp_path)
    assert loaded is not None
    loaded_state, loaded_artifacts, loaded_substeps = loaded

    assert loaded_state == PipelineState.TRANSLATED
    assert loaded_artifacts.original_srt == artifacts.original_srt
    assert loaded_artifacts.translated_srt == artifacts.translated_srt
    assert len(loaded_substeps) == 4
    assert loaded_substeps[0].status == SubstepStatus.SUCCESS
    assert loaded_substeps[1].status == SubstepStatus.SUCCESS
    assert loaded_substeps[2].status == SubstepStatus.PENDING

    clear_checkpoint(tmp_path)
    assert load_checkpoint(tmp_path) is None


def test_pipeline_runner_initial_state(qapp, tmp_path):
    project = Project()
    agent = LocalAgent()
    runner = PipelineRunner(project=project, local_agent=agent, output_dir=tmp_path)

    assert runner.state == PipelineState.PROJECT_CREATED
    assert len(runner.substeps) == 4
    assert runner.substeps[0].id == "4.1"
    assert runner.substeps[1].id == "4.2"
    assert runner.substeps[2].id == "4.3"
    assert runner.substeps[3].id == "4.4"


def test_pipeline_runner_step_4_3_execution(qapp, tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    # Prepare existing original.srt and translated.srt
    orig_file = tmp_path / "original.srt"
    orig_file.write_text("1\n00:00:00,000 --> 00:00:02,000\nHello world\n", encoding="utf-8")
    trans_file = tmp_path / "translated.srt"
    trans_file.write_text("1\n00:00:00,000 --> 00:00:02,000\nXin chào thế giới\n", encoding="utf-8")

    project = Project()
    agent = LocalAgent()

    # Mock agent.generate_vbee_sync to simulate 4.4 without real browser
    mock_audio = tmp_path / "mock_vbee.mp3"
    mock_audio.write_bytes(b"FAKE_MP3_DATA")
    agent.generate_vbee_sync = MagicMock(return_value=mock_audio)

    # Mock build_master_timeline_audio to avoid ffmpeg call
    import vkdub.orchestrator.pipeline_runner as pr_mod
    monkeypatch.setattr(
        pr_mod,
        "build_master_timeline_audio",
        lambda **kwargs: tmp_path / "master_narration_timeline.mp3",
    )

    runner = PipelineRunner(project=project, local_agent=agent, output_dir=tmp_path)
    # Run synchronously in test
    runner.run()

    # Verify Step 4.3 succeeded
    s43 = next(s for s in runner.substeps if s.id == "4.3")
    assert s43.status == SubstepStatus.SUCCESS
    assert project.script is not None
    assert len(project.script.lines) == 1
    assert project.script.lines[0].text == "Xin chào thế giới"
    assert project.target_language == "vi"

    # Verify voice_script.txt was written
    voice_txt = tmp_path / "voice_script.txt"
    assert voice_txt.is_file()
    assert voice_txt.read_text(encoding="utf-8").strip() == "Xin chào thế giới"

    # Verify Step 4.4 and overall pipeline completion
    s44 = next(s for s in runner.substeps if s.id == "4.4")
    assert s44.status == SubstepStatus.SUCCESS
    assert runner.state == PipelineState.REVIEW_READY


def test_pipeline_runner_auto_voice_false_pauses_for_review(qapp, tmp_path):
    orig_file = tmp_path / "original.srt"
    orig_file.write_text("1\n00:00:00,000 --> 00:00:02,000\nHello world\n", encoding="utf-8")
    trans_file = tmp_path / "translated.srt"
    trans_file.write_text("1\n00:00:00,000 --> 00:00:02,000\nXin chào thế giới\n", encoding="utf-8")

    project = Project()
    agent = LocalAgent()

    runner = PipelineRunner(
        project=project, local_agent=agent, output_dir=tmp_path, auto_voice=False
    )
    runner.run()

    s43 = next(s for s in runner.substeps if s.id == "4.3")
    assert s43.status == SubstepStatus.SUCCESS
    assert project.script is not None
    assert project.approved_revision_hash is None

    s44 = next(s for s in runner.substeps if s.id == "4.4")
    assert s44.status == SubstepStatus.WAITING
    assert "Chờ duyệt kịch bản" in s44.message
    assert runner.state == PipelineState.SCRIPT_READY


def test_pipeline_runner_voice_only_step_4_4(qapp, tmp_path, monkeypatch):
    import uuid
    from unittest.mock import MagicMock
    from vkdub.domain.script import ScriptDocument, ScriptLine

    project = Project()
    project.script = ScriptDocument(
        lines=(ScriptLine(id=str(uuid.uuid4()), start_ms=0, end_ms=2000, text="Câu thoại đã được người dùng sửa"),)
    )
    agent = LocalAgent()

    mock_audio = tmp_path / "mock_vbee.mp3"
    mock_audio.write_bytes(b"FAKE_MP3_DATA")
    agent.generate_vbee_sync = MagicMock(return_value=mock_audio)

    import vkdub.orchestrator.pipeline_runner as pr_mod
    monkeypatch.setattr(
        pr_mod,
        "build_master_timeline_audio",
        lambda **kwargs: tmp_path / "master_narration_timeline.mp3",
    )

    runner = PipelineRunner(
        project=project, local_agent=agent, output_dir=tmp_path, target_step="4.4"
    )
    runner.run()

    s44 = next(s for s in runner.substeps if s.id == "4.4")
    assert s44.status == SubstepStatus.SUCCESS
    assert runner.state == PipelineState.REVIEW_READY


def test_pipeline_runner_chunked_chatgpt_translation(qapp, tmp_path):
    """Test that a 140-cue original SRT is automatically chunked into batches of 35 cues."""
    from unittest.mock import MagicMock
    from vkdub.domain.transcript import srt_timestamp
    from vkdub.services.srt_validator import parse_cues

    # Create 140 cues with valid timestamps
    lines = []
    for i in range(1, 141):
        s_sec = (i - 1) * 2.0
        e_sec = s_sec + 1.5
        s_tc = srt_timestamp(s_sec)
        e_tc = srt_timestamp(e_sec)
        lines.append(f"{i}\n{s_tc} --> {e_tc}\nOriginal sentence #{i}\n")
    orig_content = "\n".join(lines)
    orig_file = tmp_path / "original.srt"
    orig_file.write_text(orig_content, encoding="utf-8")

    project = Project()
    agent = LocalAgent()

    # Mock translate_srt_sync to simulate ChatGPT translating each chunk cleanly
    def mock_translate(chunk_srt, prompt_instruction="", timeout_s=360.0):
        chunk_cues = parse_cues(chunk_srt)
        trans_lines = []
        for c in chunk_cues:
            trans_lines.append(f"{c.index}\n{c.start_raw} --> {c.end_raw}\nCâu dịch tiếng Việt #{c.index}\n")
        return "\n".join(trans_lines)

    agent.translate_srt_sync = MagicMock(side_effect=mock_translate)

    runner = PipelineRunner(
        project=project,
        local_agent=agent,
        output_dir=tmp_path,
        auto_voice=False,
    )
    runner.run()

    s42 = next(s for s in runner.substeps if s.id == "4.2")
    assert s42.status == SubstepStatus.SUCCESS
    assert "140" in s42.message

    # 140 cues divided by CHUNK_SIZE (35) must equal exactly 4 calls
    assert agent.translate_srt_sync.call_count == 4

    # Verify final translated.srt
    trans_file = tmp_path / "translated.srt"
    assert trans_file.is_file()
    final_cues = parse_cues(trans_file.read_text(encoding="utf-8"))
    assert len(final_cues) == 140
    assert final_cues[0].text == "Câu dịch tiếng Việt #1"
    assert final_cues[139].text == "Câu dịch tiếng Việt #140"
    assert final_cues[139].index == 140


