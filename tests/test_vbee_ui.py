"""UI unit tests for VbeeWorkflowDialog and VbeeController."""

from unittest.mock import MagicMock

from PySide6.QtCore import QObject

from vkdub.integrations.vbee.state import WorkflowState
from vkdub.ui.vbee_controller import VbeeController
from vkdub.ui.vbee_workflow_dialog import VbeeWorkflowDialog


class DummyMainWindow(QObject):
    """Dummy MainWindow mimicking the interface required by VbeeController."""

    def __init__(self) -> None:
        super().__init__()
        self.busy = False
        self.dirty = False
        self.project = MagicMock()
        self.tools = MagicMock()
        self.tools.paths = {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"}
        self.left = MagicMock()
        self.transcription = MagicMock()

    def log(self, msg: str) -> None:
        pass

    def _error(self, msg: str) -> None:
        pass

    def _refresh(self) -> None:
        pass


def test_vbee_workflow_dialog_initial_state(qtbot) -> None:
    """Verify dialog initializes with correct widgets, checklist items and disabled buttons."""
    window = DummyMainWindow()
    controller = VbeeController(window)
    dialog = VbeeWorkflowDialog(controller)
    qtbot.addWidget(dialog)

    assert dialog.isVisible() is False
    assert len(dialog.step_labels) == 6
    assert dialog.close_button.isEnabled() is False
    assert dialog.stop_button.isEnabled() is True
    assert dialog.progress_bar.value() == 0


def test_vbee_workflow_dialog_state_transitions(qtbot) -> None:
    """Verify dialog checklist icons update appropriately on state transitions."""
    window = DummyMainWindow()
    controller = VbeeController(window)
    dialog = VbeeWorkflowDialog(controller)
    qtbot.addWidget(dialog)

    # Transition to EXPORTING_SRT
    dialog.update_state(WorkflowState.EXPORTING_SRT, "Đang xuất SRT…")
    assert "●" in dialog.step_labels["export"].text()

    # Transition to OPENING_VBEE
    dialog.update_state(WorkflowState.OPENING_VBEE, "Đang mở Vbee…")
    assert "✓" in dialog.step_labels["export"].text()
    assert "●" in dialog.step_labels["open"].text()

    # Transition to LOGIN_REQUIRED
    dialog.update_state(WorkflowState.LOGIN_REQUIRED, "Vui lòng đăng nhập…")
    assert "⚠" in dialog.step_labels["open"].text()

    # Transition to READY
    dialog.update_state(WorkflowState.READY, "Hoàn tất!")
    for lbl in dialog.step_labels.values():
        assert "✓" in lbl.text()
    assert dialog.close_button.isEnabled() is True
    assert dialog.stop_button.isEnabled() is False
    assert dialog.progress_bar.value() == 100


def test_vbee_workflow_dialog_cancel_emitted(qtbot) -> None:
    """Verify clicking stop_button emits cancel_requested signal."""
    window = DummyMainWindow()
    controller = VbeeController(window)
    dialog = VbeeWorkflowDialog(controller)
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.cancel_requested, timeout=1000):
        dialog.stop_button.click()

    assert dialog.stop_button.isEnabled() is False
