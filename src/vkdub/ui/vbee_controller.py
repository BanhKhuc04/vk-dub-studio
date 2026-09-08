"""Thread-safe UI controller for the Vbee voice automation workflow."""

from __future__ import annotations

import asyncio
import logging
import threading
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from vkdub.domain.project import Project
from vkdub.integrations.vbee.errors import VbeeError, VbeeValidationError
from vkdub.integrations.vbee.provider import (
    VbeeBrowserProvider,
    VbeeExtensionProvider,
    VoiceProvider,
)
from vkdub.integrations.vbee.state import WorkflowState
from vkdub.integrations.vbee.workflow import VbeeVoiceWorkflow, validate_project_for_vbee
from vkdub.services.credential_service import redact
from vkdub.ui.vbee_workflow_dialog import VbeeWorkflowDialog
from vkdub.utils.paths import data_root, workspace_root

if TYPE_CHECKING:
    from vkdub.ui.main_window import MainWindow

logger = logging.getLogger("vkdub.vbee")


def map_vbee_error_message(exc: Exception) -> str:
    """Map a Vbee exception to a clear, user-friendly Vietnamese message."""
    if isinstance(exc, VbeeError):
        return str(exc)

    msg = redact(str(exc))
    exc_type = type(exc).__name__

    if any(
        term in msg
        for term in (
            "Target closed",
            "Browser has been closed",
            "Target page, context or browser has been closed",
            "TargetCrashError",
        )
    ):
        return "Cửa sổ trình duyệt Vbee đã bị đóng trước khi hoàn tất."

    if "TimeoutError" in exc_type or "timeout" in msg.lower():
        return "Vbee phản hồi quá thời gian quy định. Vui lòng kiểm tra lại kết nối mạng."

    if isinstance(exc, (FileNotFoundError, PermissionError, OSError)):
        return f"Không thể ghi file hoặc truy cập thư mục dự án ({msg})."

    if "existing browser session" in msg or "ProcessSingleton" in msg:
        return (
            "Cửa sổ trình duyệt Vbee cũ đang bị kẹt. Hệ thống đã tự động "
            "dọn dẹp, vui lòng nhấn Tạo Voice lại."
        )

    if "Executable doesn't exist" in msg:
        return "Không tìm thấy trình duyệt Microsoft Edge hoặc Google Chrome trên máy tính."

    return f"Lỗi xử lý Vbee: {msg}"


class VbeeWorkflowJob(QThread):
    """Background worker QThread executing VbeeVoiceWorkflow safely isolated from GUI thread."""

    state_changed = Signal(object, str)
    progress_changed = Signal(int, str)
    succeeded = Signal(object)
    failed = Signal(str, str)  # (friendly_message, technical_traceback)
    cancelled = Signal()

    def __init__(
        self,
        project: Project | None = None,
        provider: VoiceProvider | None = None,
        ffmpeg: str = "ffmpeg",
        ffprobe: str = "ffprobe",
        staging_dir: Path | None = None,
        speed: float | None = None,
        operation: Any = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.provider = provider
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.staging_dir = staging_dir
        self.speed = speed
        self.operation = operation
        self.cancel_event = threading.Event()
        self._workflow: VbeeVoiceWorkflow | None = None

    def cancel(self) -> None:
        self.cancel_event.set()

    def check_cancel(self) -> None:
        if self.cancel_event.is_set():
            raise asyncio.CancelledError

    def _on_state(self, state: WorkflowState, msg: str) -> None:
        # Cross-thread signal emission: Qt safely queues this to the GUI thread!
        self.state_changed.emit(state, msg)

    def _on_progress(self, pct: int, msg: str) -> None:
        # Cross-thread signal emission: Qt safely queues this to the GUI thread!
        self.progress_changed.emit(pct, msg)

    async def _execute(self) -> Any:
        self.check_cancel()
        if self.operation is not None:
            if asyncio.iscoroutinefunction(self.operation):
                return await self.operation(self._on_state, self._on_progress)
            return self.operation(self._on_state, self._on_progress)

        assert self.project is not None
        assert self.provider is not None
        self._workflow = VbeeVoiceWorkflow(
            project=self.project,
            provider=self.provider,
            ffmpeg=self.ffmpeg,
            ffprobe=self.ffprobe,
            state_callback=self._on_state,
            progress_callback=self._on_progress,
            check_cancel=self.check_cancel,
            working_dir=self.staging_dir,
            speed=self.speed,
        )
        return await self._workflow.run()

    def run(self) -> None:
        try:
            result = asyncio.run(self._execute())
            self.check_cancel()
            self.succeeded.emit(result)
        except asyncio.CancelledError:
            logger.info("Vbee workflow cancelled by user.")
            self.cancelled.emit()
        except Exception as exc:
            tb = redact(traceback.format_exc())
            logger.error("Vbee workflow execution error: %s\n%s", exc, tb)
            friendly_msg = map_vbee_error_message(exc)
            self.failed.emit(friendly_msg, tb)
        finally:
            self._workflow = None


class VbeeController(QObject):
    """Coordinates UI state and background execution for Vbee Voice automation."""

    workflow_started = Signal()
    workflow_finished = Signal(bool, str)

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window if isinstance(window, QObject) else None)
        self.window = window
        self.job: VbeeWorkflowJob | None = None
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

        # Check Vbee mode (Browser vs API)
        from vkdub.services.app_settings import load_app_settings

        settings = load_app_settings()
        vbee_mode = getattr(settings, "vbee_mode", "browser")

        app_id: str | None = None
        token: str | None = None
        if vbee_mode == "api":
            from vkdub.services.credential_service import VbeeAppStore, VbeeTokenStore

            app_id = VbeeAppStore().get()
            token = VbeeTokenStore().get()
            if not app_id or not token:
                self.window._error(
                    "Chưa cấu hình App ID hoặc Access Token cho Vbee API.\n"
                    "Vui lòng vào 'Cài đặt' -> tab 'Voice' để nhập thông tin tài khoản Vbee API."
                )
                self.window.open_settings(2)
                return False

        # 3. Create & show workflow progress dialog
        self.dialog = VbeeWorkflowDialog(self)
        self.dialog.show()

        # 4. Synchronize speed: UI speed_combo -> project.voice.speed -> default 1.1
        speed = 1.1
        if hasattr(self.window, "left") and hasattr(self.window.left, "speed_combo"):
            combo_val = self.window.left.speed_combo.currentData()
            if combo_val is not None:
                speed = float(combo_val)
        elif project.voice and getattr(project.voice, "speed", None) is not None:
            speed = float(project.voice.speed)

        if project.voice:
            from dataclasses import is_dataclass, replace

            if is_dataclass(project.voice):
                project.voice = replace(project.voice, speed=speed)
            else:
                project.voice.speed = speed

        # 5. Create provider and staging directory
        staging_dir = data_root() / "vbee_staging"
        if vbee_mode == "api" and app_id and token:
            from vkdub.integrations.vbee.provider import VbeeApiProvider

            provider: VoiceProvider = VbeeApiProvider(
                app_id=app_id,
                token=token,
                ffmpeg=str(ffmpeg),
                ffprobe=str(ffprobe),
            )
        elif vbee_mode == "standalone_browser":
            provider = VbeeBrowserProvider(
                downloads_dir=staging_dir / "downloads",
                headless=False,
            )
        else:
            # Mặc định sử dụng tiện ích mở rộng Edge Bridge (theo yêu cầu người dùng)
            local_agent = getattr(self.window, "local_agent", None)
            provider = VbeeExtensionProvider(
                local_agent=local_agent,
                downloads_dir=staging_dir / "downloads",
            )

        # 6. Create thread-safe worker job
        job = VbeeWorkflowJob(
            project=project,
            provider=provider,
            ffmpeg=str(ffmpeg),
            ffprobe=str(ffprobe),
            staging_dir=staging_dir,
            speed=speed,
            parent=self,
        )
        self.job = job

        # 7. Wire Qt Signals - All slots are guaranteed to execute on the GUI thread
        self.dialog.cancel_requested.connect(self.stop_workflow)
        job.state_changed.connect(self._on_state_changed)
        job.progress_changed.connect(self._on_progress_changed)
        job.succeeded.connect(self._on_succeeded)
        job.failed.connect(self._on_failed)
        job.cancelled.connect(lambda: self._on_failed("Đã dừng tiến trình tạo voice Vbee.", ""))
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

    @Slot(object, str)
    def _on_state_changed(self, state: WorkflowState, msg: str) -> None:
        """Slot executed strictly on the Qt main GUI thread."""
        if self.dialog:
            self.dialog.update_state(state, msg)
        self.window.log(f"Vbee: {msg}")

    @Slot(int, str)
    def _on_progress_changed(self, pct: int, msg: str) -> None:
        """Slot executed strictly on the Qt main GUI thread."""
        if self.dialog:
            self.dialog.set_progress(pct, msg)
        self.window.left.job_progress.setValue(pct)
        if hasattr(self.window, "transcription") and hasattr(
            self.window.transcription, "_progress"
        ):
            self.window.transcription._progress(pct, msg)

    @Slot(object)
    def _on_succeeded(self, result: Any) -> None:
        """Slot executed strictly on the Qt main GUI thread."""
        logger.info("Vbee workflow finished successfully: %s", result)
        count = result.get("lines_count", 0) if isinstance(result, dict) else 0
        msg = f"Đã hoàn thành tạo voice bằng Vbee cho {count} câu thoại!"
        self.window.dirty = True
        self.window.log(msg)
        if self.dialog:
            self.dialog.update_state(WorkflowState.READY, msg)
        self.window._refresh()
        self.workflow_finished.emit(True, msg)

    @Slot(str, str)
    def _on_failed(self, error_message: str, technical_traceback: str = "") -> None:
        """Slot executed strictly on the Qt main GUI thread."""
        logger.warning("Vbee workflow failed: %s", error_message)
        self.window.log(f"Lỗi Vbee: {error_message}")
        if self.dialog:
            self.dialog.update_state(WorkflowState.ERROR, error_message)
            if technical_traceback:
                self.dialog.append_log(f"Chi tiết kỹ thuật:\n{technical_traceback.strip()}")
        self.window._refresh()
        self.workflow_finished.emit(False, error_message)

    @Slot()
    def _on_finished(self) -> None:
        """Slot executed strictly on the Qt main GUI thread."""
        if self.job:
            self.job.deleteLater()
        self.job = None
        self.window.busy = False
        self.window.left.job_progress.setValue(100)
        self.window.left.stop_button.setEnabled(False)
        self.window._refresh()

    def export_srt_dialog(self) -> Path | None:
        """Export approved or translated Vietnamese SRT file for manual Vbee dubbing."""
        project = self.window.project
        if not project.script or not project.script.lines:
            self.window._error(
                "Dự án chưa có kịch bản tiếng Việt. Vui lòng bóc băng và dịch "
                "kịch bản trước khi xuất SRT."
            )
            return None

        import re
        from datetime import datetime

        from vkdub.services.srt_service import write_srt

        slug = (
            re.sub(
                r"[^a-zA-Z0-9_-]", "_", project.video_path.stem if project.video_path else "project"
            ).strip("_")[:30]
            or "project"
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_dir = workspace_root() / "export"
        default_dir.mkdir(parents=True, exist_ok=True)
        default_path = default_dir / f"vkdub_{slug}_{timestamp}.srt"

        chosen, _ = QFileDialog.getSaveFileName(
            self.window if isinstance(self.window, QWidget) else None,
            "Lưu file phụ đề SRT tiếng Việt (Dùng tạo Voice trên Vbee)",
            str(default_path),
            "SubRip Subtitles (*.srt);;Tất cả tệp (*.*)",
        )
        if not chosen:
            return None

        target = Path(chosen)
        write_srt(target, project.script, project.duration_ms)
        self.window.log(f"✓ Đã xuất file phụ đề SRT cho Vbee: {target.name}")

        box = QMessageBox(
            QMessageBox.Icon.Information,
            "Xuất file SRT thành công",
            f"Đã lưu file SRT tiếng Việt thành công tại:\n{target}\n\n"
            "Các bước thực hiện thủ công:\n"
            "1. Tải file SRT này lên Vbee Studio (vbee.vn) để tạo giọng đọc.\n"
            "2. Sau khi Vbee chuyển đổi xong, tải file âm thanh (MP3/WAV) về máy tính.\n"
            "3. Bấm nút '📁 Nhập Audio Vbee (Thủ công)' trên VK Dub Studio "
            "để tự động cắt ghép vào video!",
            parent=self.window if isinstance(self.window, QWidget) else None,
        )
        btn_open = box.addButton("Mở thư mục chứa file", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Đã hiểu", QMessageBox.ButtonRole.AcceptRole)
        box.exec()
        if box.clickedButton() == btn_open:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.parent)))

        return target

    def import_manual_audio_dialog(self, audio_path: Path | None = None) -> bool:
        """Import a downloaded Vbee audio file manually and slice per subtitle line."""
        if self.window.busy or self.job is not None:
            self.window.log("Hệ thống đang bận thực hiện tác vụ khác. Vui lòng chờ.")
            return False

        project = self.window.project
        if not project.script or not project.script.lines:
            self.window._error(
                "Dự án chưa có kịch bản để đồng bộ âm thanh. Vui lòng dịch kịch bản trước."
            )
            return False

        from vkdub.integrations.vbee.importer import slice_and_import_vbee_audio

        if audio_path is None:
            chosen, _ = QFileDialog.getOpenFileName(
                self.window if isinstance(self.window, QWidget) else None,
                "Chọn file Audio đã tạo và tải về từ Vbee",
                "",
                "Audio Files (*.mp3 *.wav *.m4a *.aac *.ogg);;Tất cả tệp (*.*)",
            )
            if not chosen:
                return False
            audio_path = Path(chosen)

        if not audio_path.is_file() or audio_path.stat().st_size < 2048:
            self.window._error("File âm thanh đã chọn không tồn tại hoặc dung lượng quá nhỏ.")
            return False

        ffmpeg = self.window.tools.paths.get("ffmpeg")
        ffprobe = self.window.tools.paths.get("ffprobe")
        if not ffmpeg or not ffprobe:
            self.window._error("Cần FFmpeg và FFprobe để xử lý cắt ghép âm thanh.")
            return False

        # Auto approve script if valid and not yet approved
        if not project.is_approved and project.script_valid:
            project.approve(True)

        async def manual_import_op(state_cb: Any, prog_cb: Any) -> dict[str, Any]:
            prog_cb(10, "Đang chuẩn hóa âm thanh Vbee thủ công...")
            res = await slice_and_import_vbee_audio(
                project=project,
                downloaded_audio=audio_path,
                ffmpeg=str(ffmpeg),
                ffprobe=str(ffprobe),
                voice_id="vbee_manual",
                display_name="Vbee (Thủ công)",
            )
            prog_cb(100, "Đã hoàn thành cắt ghép âm thanh Vbee theo kịch bản!")
            return res

        job = VbeeWorkflowJob(
            project=project,
            operation=manual_import_op,
            parent=self,
        )
        self.job = job
        job.progress_changed.connect(self._on_progress_changed)
        job.succeeded.connect(self._on_manual_succeeded)
        job.failed.connect(self._on_failed)
        job.finished.connect(self._on_finished)

        self.window.busy = True
        self.window.left.stop_button.setEnabled(True)
        self.window.left.stop_button.clicked.connect(self.stop_workflow)
        self.window.left.job_progress.setValue(10)
        self.window.log(
            f"Đang phân tích và cắt ghép file âm thanh Vbee ({audio_path.name}) "
            f"theo {len(project.script.lines)} câu kịch bản…"
        )
        self.window._refresh()
        job.start()
        return True

    @Slot(object)
    def _on_manual_succeeded(self, result: Any) -> None:
        count = result.get("lines_count", 0) if isinstance(result, dict) else 0
        msg = f"✓ Đã nhập và đồng bộ thành công {count} câu thoại từ file Vbee thủ công!"
        self.window.dirty = True
        self.window.log(msg)
        self.window._refresh()
        QMessageBox.information(
            self.window if isinstance(self.window, QWidget) else None,
            "Nhập Audio Vbee thành công",
            f"{msg}\n\n"
            "Tất cả các câu thoại đã sẵn sàng. Bạn có thể nghe thử từng câu "
            "trên danh sách kịch bản "
            "và bấm 'BẮT ĐẦU XỬ LÝ' (hoặc Xuất CapCut) để hoàn tất video!",
        )
        self.workflow_finished.emit(True, msg)
