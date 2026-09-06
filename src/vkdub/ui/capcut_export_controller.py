"""Background CapCut export and user-visible result actions."""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QDesktopServices

from vkdub.services.app_settings import load_app_settings
from vkdub.services.capcut_export import CapCutExportResult, export_capcut_project
from vkdub.services.cloud_job import CloudJob

if TYPE_CHECKING:
    from vkdub.ui.main_window import MainWindow


class CapCutExportController(QObject):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self.job: CloudJob | None = None
        self.last_result: CapCutExportResult | None = None

    def start(self) -> bool:
        if self.window.busy or not self.window.project.voice_ready:
            return False
        root = Path(load_app_settings().capcut_draft_root).expanduser()
        ffprobe = self.window.tools.paths.get("ffprobe")
        ffmpeg = self.window.tools.paths.get("ffmpeg")
        if not ffprobe or (self.window.project.masks and not ffmpeg):
            self.window.log("Cần FFmpeg và ffprobe trước khi xuất CapCut.")
            return False
        project = self.window.project

        async def operation() -> CapCutExportResult:
            return await asyncio.to_thread(export_capcut_project, project, root, ffprobe, ffmpeg)

        self.job = CloudJob(operation)
        self.job.succeeded.connect(self._succeeded)
        self.job.failed.connect(self._failed)
        self.job.cancelled.connect(lambda: self._failed("Đã dừng xuất project CapCut."))
        self.job.finished.connect(self._finished)
        self.window.busy = True
        self.window.log("Bắt đầu xuất CapCut: đang kiểm tra video, voice và caption…")
        self.window._refresh()
        self.job.start()
        return True

    def _succeeded(self, value: Any) -> None:
        result: CapCutExportResult = value
        self.last_result = result
        self.window.left.show_capcut_result(True)
        self.window.log(
            f"Đã tạo project CapCut: 1 video, {result.audio_segments} voice tiếng Việt, "
            f"{result.caption_segments} caption."
        )
        if result.applied_mask_count:
            self.window.log(
                f"Đã áp dụng {result.applied_mask_count} vùng xóa chữ vào video trong CapCut."
            )

    def _failed(self, message: str) -> None:
        self.window._error(message)

    def _finished(self) -> None:
        if self.job:
            self.job.deleteLater()
        self.job = None
        self.window.busy = False
        self.window._refresh()

    def stop(self) -> None:
        if self.job:
            self.job.cancel()

    def open_folder(self) -> None:
        if self.last_result:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_result.path)))

    def open_capcut(self) -> None:
        QDesktopServices.openUrl(QUrl("capcut://"))
