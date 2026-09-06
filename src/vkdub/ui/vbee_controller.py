"""Controller wiring MainWindow, Project, and Vbee Voice automation workflow."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Signal

from vkdub.integrations.vbee.errors import VbeeValidationError
from vkdub.integrations.vbee.provider import VbeeBrowserProvider
from vkdub.integrations.vbee.state import WorkflowState
from vkdub.integrations.vbee.workflow import VbeeVoiceWorkflow, validate_project_for_vbee
from vkdub.services.cloud_job import CloudJob
from vkdub.ui.vbee_workflow_dialog import VbeeWorkflowDialog
from vkdub.utils.paths import data_root

if TYPE_CHECKING:
    from vkdub.ui.main_window import MainWindow

logger = logging.getLogger("vkdub.vbee")


class VbeeController(QObject):
    """Coordinates UI state and background execution for Vbee Voice automation."""

    workflow_started = Signal()
    workflow_finished = Signal(bool, str)

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window if isinstance(window, QObject) else None)
        self.window = window
        self.job: CloudJob | None = None
        self.dialog: VbeeWorkflowDialog | None = None

    def start_workflow(self) -> bool:
        """Validate preconditions and launch the Vbee Dubbing workflow in background."""
        # 1. Duplicate start protection
        if self.window.busy or self.job is not None:
            self.window.log("Hệ thống đang bận thực hiện một tác vụ khác. Vui lòng chờ.")
            return False

        project = self.window.project

        # 2. Preconditions check
        try:
            validate_project_for_vbee(project)
        except VbeeValidationError as exc:
            self.window._error(str(exc))
            return False

        ffmpeg = self.window.tools.paths.get("ffmpeg")
        ffprobe = self.window.tools.paths.get("ffprobe")
        if not ffmpeg or not ffprobe:
            self.window._error("Cần cài đặt FFmpeg và FFprobe để xử lý âm thanh Vbee.")
            return False

        # 3. Create & show workflow progress dialog
        self.dialog = VbeeWorkflowDialog(self)
        self.dialog.show()

        # 4. Create and start background job
        provider = VbeeBrowserProvider(
            downloads_dir=data_root() / "vbee_staging" / "downloads",
            headless=False,  # Allow user to see browser and interact during login if needed
        )

        staging_dir = data_root() / "vbee_staging"

        def on_state(state: WorkflowState, msg: str) -> None:
            if self.dialog:
                self.dialog.update_state(state, msg)
            self.window.log(f"Vbee: {msg}")

        def on_progress(pct: int, msg: str) -> None:
            if self.dialog:
                self.dialog.set_progress(pct, msg)
            self.window.left.job_progress.setValue(pct)

        async def run_operation() -> dict[str, Any]:
            assert self.job is not None
            workflow = VbeeVoiceWorkflow(
                project=project,
                provider=provider,
                ffmpeg=str(ffmpeg),
                ffprobe=str(ffprobe),
                state_callback=on_state,
                progress_callback=on_progress,
                check_cancel=self.job.check_cancel,
                working_dir=staging_dir,
            )
            return await workflow.run()

        job = CloudJob(run_operation)
        self.job = job

        self.dialog.cancel_requested.connect(self.stop_workflow)
        job.progress.connect(self.window.transcription._progress)
        job.succeeded.connect(self._on_succeeded)
        job.failed.connect(self._on_failed)
        job.cancelled.connect(lambda: self._on_failed("Đã dừng tiến trình tạo voice Vbee."))
        job.finished.connect(self._on_finished)

        self.window.busy = True
        self.window.left.stop_button.setEnabled(True)
        self.window.left.stop_button.clicked.connect(self.stop_workflow)
        self.window.left.job_progress.setValue(0)
        self.window._refresh()

        self.workflow_started.emit()
        job.start()
        return True

    def stop_workflow(self) -> None:
        """Cancel the running Vbee Voice job."""
        if self.job and not self.job.cancel_event.is_set():
            self.job.cancel()
            self.window.log("Đang yêu cầu dừng tiến trình Vbee…")
            if self.dialog:
                self.dialog.append_log("Đang dừng tiến trình…")

    def _on_succeeded(self, result: Any) -> None:
        logger.info("Vbee workflow finished successfully: %s", result)
        count = result.get("lines_count", 0)
        msg = f"Đã hoàn thành tạo voice bằng Vbee cho {count} câu thoại!"
        self.window.dirty = True
        self.window.log(msg)
        if self.dialog:
            self.dialog.update_state(WorkflowState.READY, msg)
        self.workflow_finished.emit(True, msg)

    def _on_failed(self, error_message: str) -> None:
        logger.warning("Vbee workflow failed: %s", error_message)
        self.window.log(f"Lỗi Vbee: {error_message}")
        if self.dialog:
            self.dialog.update_state(WorkflowState.ERROR, error_message)
        self.workflow_finished.emit(False, error_message)

    def _on_finished(self) -> None:
        if self.job:
            self.job.deleteLater()
        self.job = None
        self.window.busy = False
        self.window.left.job_progress.setValue(100)
        self.window.left.stop_button.setEnabled(False)
        self.window._refresh()
