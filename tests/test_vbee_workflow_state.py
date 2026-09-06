"""Tests for Vbee Voice workflow state machine, validation, and duplicate protection."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.integrations.vbee.errors import VbeeValidationError
from vkdub.integrations.vbee.state import CHECKLIST_STEPS, WorkflowState
from vkdub.integrations.vbee.workflow import validate_project_for_vbee
from vkdub.ui.vbee_controller import VbeeController


def test_workflow_state_enum_properties() -> None:
    """Verify all workflow states have appropriate labels, active and terminal flags."""
    assert WorkflowState.IDLE.is_active is False
    assert WorkflowState.IDLE.is_terminal is False
    assert WorkflowState.IDLE.label == "Sẵn sàng"

    assert WorkflowState.EXPORTING_SRT.is_active is True
    assert WorkflowState.EXPORTING_SRT.is_terminal is False

    assert WorkflowState.LOGIN_REQUIRED.is_active is False
    assert WorkflowState.LOGIN_REQUIRED.is_terminal is False

    assert WorkflowState.READY.is_active is False
    assert WorkflowState.READY.is_terminal is True
    assert "sẵn sàng" in WorkflowState.READY.label.lower()

    assert WorkflowState.ERROR.is_active is False
    assert WorkflowState.ERROR.is_terminal is True

    # Checklist steps coverage
    assert len(CHECKLIST_STEPS) == 6
    keys = [k for k, _ in CHECKLIST_STEPS]
    assert keys == ["export", "open", "upload", "process", "download", "import"]


def test_validate_project_missing_video(tmp_path: Path) -> None:
    """Validate project fails when video is missing or invalid."""
    project = Project()
    with pytest.raises(VbeeValidationError, match="video"):
        validate_project_for_vbee(project)

    fake_video = tmp_path / "missing.mp4"
    project.video_path = fake_video
    with pytest.raises(VbeeValidationError, match="video"):
        validate_project_for_vbee(project)


def test_validate_project_target_language(tmp_path: Path) -> None:
    """Validate project fails when target language is not Vietnamese."""
    video = tmp_path / "test.mp4"
    video.write_bytes(b"\x00" * 1024)

    project = Project(
        video_path=video,
        target_language="en",
        script=ScriptDocument((ScriptLine.new(0, 1000, "Hello"),)),
    )
    with pytest.raises(VbeeValidationError, match="tiếng Việt"):
        validate_project_for_vbee(project)


def test_validate_project_unapproved_script(tmp_path: Path) -> None:
    """Validate project fails when script has not been approved."""
    video = tmp_path / "test.mp4"
    video.write_bytes(b"\x00" * 1024)

    project = Project(
        video_path=video,
        target_language="vi",
        script=ScriptDocument((ScriptLine.new(0, 1000, "Xin chào thế giới"),)),
    )
    with pytest.raises(VbeeValidationError, match="chưa được duyệt"):
        validate_project_for_vbee(project)


def test_validate_project_success(tmp_path: Path) -> None:
    """Validate project succeeds when all preconditions are satisfied."""
    video = tmp_path / "test.mp4"
    video.write_bytes(b"\x00" * 1024)

    project = Project(
        video_path=video,
        target_language="vi",
        script=ScriptDocument((ScriptLine.new(0, 1000, "Xin chào các bạn"),)),
    )
    project.approve(True)
    assert project.is_approved is True

    # Should not raise any exception
    validate_project_for_vbee(project)


def test_duplicate_start_protection(tmp_path: Path) -> None:
    """Verify start_workflow returns False and refuses to start if window is busy."""
    mock_window = MagicMock()
    mock_window.busy = True
    controller = VbeeController(mock_window)

    result = controller.start_workflow()
    assert result is False
    mock_window.log.assert_called_once()
    assert "đang bận" in mock_window.log.call_args[0][0]


def test_vbee_workflow_speed_defaults_and_sync() -> None:
    """Verify VbeeVoiceWorkflow defaults to speed 1.1 when unspecified, and respects explicit speed."""
    from vkdub.integrations.vbee.workflow import VbeeVoiceWorkflow

    mock_provider = MagicMock()
    mock_project = MagicMock()
    mock_project.voice = None

    wf = VbeeVoiceWorkflow(
        project=mock_project,
        provider=mock_provider,
        ffmpeg="ffmpeg",
        ffprobe="ffprobe",
    )
    assert wf.speed == 1.1

    # Explicit speed
    wf_custom = VbeeVoiceWorkflow(
        project=mock_project,
        provider=mock_provider,
        ffmpeg="ffmpeg",
        ffprobe="ffprobe",
        speed=1.2,
    )
    assert wf_custom.speed == 1.2
