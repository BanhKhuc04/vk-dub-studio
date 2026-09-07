"""Regression test specifically verifying Qt thread safety for Vbee automation.

Proves:
1. VbeeWorkflowJob runs on a background QThread (worker_thread != main_thread).
2. Signals emitted from the worker thread (state_changed, progress_changed, succeeded, failed)
   are marshalled via Qt Queued Connection to the GUI/main thread.
3. UI widgets (VbeeWorkflowDialog, QProgressBar, QLabel) are only mutated on the main thread.
4. The legacy pattern of direct worker callbacks executed directly on the worker thread,
   which led to Qt6Gui.dll STATUS_ACCESS_VIOLATION (0xc0000005).
"""

from unittest.mock import MagicMock

from PySide6.QtCore import QObject, QThread, Slot
from PySide6.QtWidgets import QApplication

from vkdub.integrations.vbee.state import WorkflowState
from vkdub.ui.vbee_controller import VbeeController, VbeeWorkflowJob, map_vbee_error_message
from vkdub.ui.vbee_workflow_dialog import VbeeWorkflowDialog


class DummyMainWindow(QObject):
    """Dummy MainWindow for testing."""

    def __init__(self) -> None:
        super().__init__()
        self.busy = False
        self.dirty = False
        self.project = MagicMock()
        self.tools = MagicMock()
        self.tools.paths = {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"}
        self.left = MagicMock()
        self.review = MagicMock()
        self.transcription = MagicMock()
        self.logged_messages: list[str] = []

    def log(self, msg: str) -> None:
        self.logged_messages.append(msg)

    def _error(self, msg: str) -> None:
        self.logged_messages.append(f"ERROR: {msg}")

    def _refresh(self) -> None:
        pass


def test_vbee_worker_signals_dispatched_to_gui_thread(qtbot) -> None:
    """Verify worker thread signals are handled strictly on the Qt main GUI thread."""
    main_thread = QThread.currentThread()
    assert main_thread == QApplication.instance().thread()

    execution_threads = {
        "worker_run": None,
        "state_slot": None,
        "progress_slot": None,
        "succeeded_slot": None,
    }

    # Custom worker action that records its thread and emits signals
    def mock_workflow(on_state, on_progress):
        execution_threads["worker_run"] = QThread.currentThread()
        on_state(WorkflowState.OPENING_VBEE, "Đang mở Edge...")
        on_progress(35, "35%")
        return "result_voice_file.wav"

    job = VbeeWorkflowJob(operation=mock_workflow)

    class Receiver(QObject):
        @Slot(object, str)
        def handle_state(self, state, msg):
            execution_threads["state_slot"] = QThread.currentThread()

        @Slot(int, str)
        def handle_progress(self, val, msg):
            execution_threads["progress_slot"] = QThread.currentThread()

        @Slot(object)
        def handle_succeeded(self, res):
            execution_threads["succeeded_slot"] = QThread.currentThread()

    receiver = Receiver()
    # Ensure receiver belongs to main thread
    assert receiver.thread() == main_thread

    job.state_changed.connect(receiver.handle_state)
    job.progress_changed.connect(receiver.handle_progress)
    job.succeeded.connect(receiver.handle_succeeded)

    with qtbot.waitSignal(job.succeeded, timeout=3000):
        job.start()

    job.wait(2000)

    # 1. Assert worker thread was indeed a separate background thread
    assert execution_threads["worker_run"] is not None
    assert execution_threads["worker_run"] != main_thread
    assert execution_threads["worker_run"] == job

    # 2. Assert all receiving slots executed strictly on the main thread
    assert execution_threads["state_slot"] == main_thread
    assert execution_threads["progress_slot"] == main_thread
    assert execution_threads["succeeded_slot"] == main_thread


def test_legacy_direct_callback_violation_demonstration() -> None:
    """Demonstrate that direct invocation from a worker thread executes on the worker thread,

    proving the old unsafe architecture violated Qt thread safety rules.
    """
    main_thread = QThread.currentThread()
    callback_executed_thread = None

    def unsafe_direct_callback(state, msg):
        nonlocal callback_executed_thread
        callback_executed_thread = QThread.currentThread()

    class LegacyWorker(QThread):
        def __init__(self, callback):
            super().__init__()
            self.callback = callback

        def run(self):
            # Worker directly calls Python callback (old bug)
            self.callback(WorkflowState.UPLOADING_SRT, "Direct call")

    worker = LegacyWorker(unsafe_direct_callback)
    worker.start()
    worker.wait(2000)

    # In the old code, callback ran on worker thread -> NOT main thread!
    # Direct QWidget manipulation here caused 0xc0000005 crash.
    assert callback_executed_thread is not None
    assert callback_executed_thread != main_thread
    assert callback_executed_thread == worker


def test_vbee_controller_gui_thread_updates(qtbot) -> None:
    """Verify VbeeController safely updates VbeeWorkflowDialog from worker thread signals."""
    window = DummyMainWindow()
    controller = VbeeController(window)
    dialog = VbeeWorkflowDialog(controller)
    controller.dialog = dialog
    qtbot.addWidget(dialog)

    def mock_workflow(on_state, on_progress):
        # Emitted from worker thread
        on_state(WorkflowState.UPLOADING_SRT, "Tải lên SRT...")
        on_progress(50, "50%")
        on_state(WorkflowState.READY, "Hoàn tất")
        on_progress(100, "100%")
        return "voice.wav"

    job = VbeeWorkflowJob(operation=mock_workflow)
    controller.job = job

    # Connect controller slots
    job.state_changed.connect(controller._on_state_changed)
    job.progress_changed.connect(controller._on_progress_changed)
    job.succeeded.connect(controller._on_succeeded)
    job.failed.connect(controller._on_failed)

    with qtbot.waitSignal(job.succeeded, timeout=3000):
        job.start()

    job.wait(2000)

    # Check dialog updated properly on main thread without crash
    assert dialog.progress_bar.value() == 100
    assert "✓" in dialog.step_labels["upload"].text()
    assert dialog.close_button.isEnabled() is True


def test_vbee_error_mapping_preserves_technical_details() -> None:
    """Keep friendly Vietnamese error messages without swallowing technical details."""
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    # 1. Timeout
    timeout_err = PlaywrightTimeoutError("Timeout 30000ms exceeded while waiting for selector")
    msg1 = map_vbee_error_message(timeout_err)
    assert "quá thời gian" in msg1
    assert "API" not in msg1

    # 2. Closed
    closed_err = PlaywrightError("Target page, context or browser has been closed")
    msg2 = map_vbee_error_message(closed_err)
    assert "đã bị đóng" in msg2
    assert "API" not in msg2

    # 3. File / OS Error
    os_err = OSError("No space left on device")
    msg3 = map_vbee_error_message(os_err)
    assert "thư mục" in msg3 or "bộ nhớ" in msg3
    assert "API" not in msg3

    # 4. Generic error includes original str representation
    gen_err = ValueError("Custom unexpected failure")
    msg4 = map_vbee_error_message(gen_err)
    assert "Custom unexpected failure" in msg4
    assert "API" not in msg4
