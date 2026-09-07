"""Unit tests for PipelineRunner, checkpoints, and substep state management."""

import pytest
from PySide6.QtCore import QCoreApplication

from vkdub.bridge.local_agent import LocalAgent
from vkdub.domain.project import Project
from vkdub.orchestrator.checkpoint import (
    clear_checkpoint,
    load_checkpoint,
    save_checkpoint,
)
from vkdub.orchestrator.pipeline_runner import PipelineRunner
from vkdub.orchestrator.pipeline_state import (
    ArtifactRegistry,
    PipelineState,
    SubstepInfo,
    SubstepStatus,
)


@pytest.fixture(scope="session")
def qapp():
    app = QCoreApplication.instance()
    if not app:
        app = QCoreApplication([])
    return app


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
