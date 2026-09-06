from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject

from vkdub.domain.script import draft_from_source
from vkdub.domain.transcript import SubtitleSegment, Transcript
from vkdub.domain.translation import Translation
from vkdub.providers.gemini_translation import GeminiTranslationProvider
from vkdub.providers.tts_provider import HealthResult
from vkdub.services.app_settings import load_app_settings
from vkdub.services.cloud_job import CloudJob
from vkdub.services.credential_service import CredentialStore
from vkdub.services.script_service import edit_line
from vkdub.services.translation_service import translate_transcript
from vkdub.services.usage_service import UsageLedger, UsageRecorder
from vkdub.ui.api_cost_dialog import ApiCostDialog
from vkdub.utils.paths import workspace_root

if TYPE_CHECKING:
    from vkdub.ui.main_window import MainWindow


class TranslationController(QObject):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self.job: CloudJob | None = None
        self.dialog: ApiCostDialog | None = None
        self.close_after_job = False
        self.kind = "translation"
        self.line_target: str | None = None
        self.source_snapshot: Transcript | None = None
        self.revision_snapshot: str | None = None
        window.left.api_button.clicked.connect(self.open_manager)
        window.left.translate_button.clicked.connect(self.start)
        window.left.stop_button.clicked.connect(self.stop)

    def refresh(self) -> None:
        panel = self.window.left
        transcript = self.window.project.transcript
        panel.translate_button.setEnabled(
            bool(transcript and transcript.segments)
            and self.window.project.target_language == "vi"
            and not self.window.busy
        )
        panel.translation_cache.setEnabled(not self.window.busy)
        panel.api_button.setEnabled(not self.window.busy)
        if self.job:
            panel.stop_button.setEnabled(not self.job.cancel_event.is_set())

    def open_manager(self) -> None:
        if self.window.busy:
            return
        if self.dialog is None:
            self.dialog = ApiCostDialog(self)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.refresh()

    def start(self) -> bool:
        self.refresh()
        if not self.window.left.translate_button.isEnabled():
            return False
        if not self.window.review_controller.confirm_replace():
            return False
        self.line_target = None
        return self._launch("translation")

    def regenerate_line(self, line_id: str) -> bool:
        project = self.window.project
        if self.window.busy or project.script is None or project.transcript is None:
            return False
        line = next((row for row in project.script.lines if row.id == line_id), None)
        if line is None or not line.source_ids:
            self.window.log("Câu này chưa gắn bản gốc để dịch lại.")
            return False
        sources = [project.transcript.segments[i - 1] for i in line.source_ids]
        text = " ".join(row.text for row in sources)
        self.source_snapshot = Transcript(
            (SubtitleSegment(1, min(s.start for s in sources), max(s.end for s in sources), text),),
            project.transcript.language,
            project.transcript.requested_language,
            project.transcript.duration,
            project.transcript.model,
            project.transcript.device,
            project.transcript.fingerprint,
            project.transcript.cache_key,
        )
        self.line_target = line_id
        self.revision_snapshot = project.revision_hash
        return self._launch("line")

    def test_connection(self) -> bool:
        if self.dialog and self.dialog.key_input.text():
            self.dialog.status.setText("Nhấn Lưu khóa trước khi kiểm tra khóa mới.")
            return False
        return self._launch("test") if not self.window.busy else False

    def _launch(self, kind: str) -> bool:
        if self.window.busy:
            return False
        try:
            key = CredentialStore().get()
            if not key:
                self.window.log("Thiếu Gemini API key. Mở Cài đặt AI để lưu khóa.")
                self.window.open_settings(1)
                return False
            recorder = UsageRecorder(UsageLedger())
        except Exception:
            self.window.log("Không đọc được khóa, bảng giá hoặc thống kê. Kiểm tra API & Chi phí.")
            return False
        transcript = self.source_snapshot if kind == "line" else self.window.project.transcript
        reuse = self.window.left.translation_cache.isChecked() if kind != "line" else False
        selected_model = load_app_settings().gemini_model

        async def operation() -> Any:
            provider = GeminiTranslationProvider(
                key, recorder, job.progress.emit, model=selected_model
            )
            if kind == "test":
                return await provider.test_connection()
            if transcript is None:
                raise ValueError("Chưa có bản gốc.")
            return await translate_transcript(
                transcript,
                provider,
                workspace_root() / "cache" / "translation",
                reuse,
                job.progress.emit,
                job.check_cancel,
            )

        job = CloudJob(operation)
        self.job = job
        self.kind = kind
        job.progress.connect(self._progress)
        job.succeeded.connect(self._succeeded)
        job.failed.connect(self._failed)
        job.cancelled.connect(self._cancelled)
        job.finished.connect(self._finished)
        self.window.busy = True
        self.window.preview.player.pause()
        self.window.left.job_progress.setRange(0, 0)
        self.window.log(
            "Đang kiểm tra Gemini…" if kind == "test" else "Đang dịch sang tiếng Việt qua Gemini…"
        )
        self.window._refresh()
        if self.dialog:
            self.dialog.refresh()
        job.start()
        return True

    def _progress(self, percent: int, message: str) -> None:
        self.window.transcription._progress(percent, message)

    def _succeeded(self, result: Any) -> None:
        if self.job is None or self.job.cancel_event.is_set():
            return
        if self.kind == "test":
            if self.dialog:
                self.dialog.status.setText(result)
                self.dialog.credential_status = "Kết nối đã kiểm tra"
            self.window.log(result)
        elif self.kind == "line":
            project = self.window.project
            if (
                not isinstance(result, Translation)
                or project.script is None
                or project.revision_hash != self.revision_snapshot
            ):
                self._failed("Kịch bản đã đổi. Chưa áp dụng bản dịch câu.")
                return
            try:
                result.validate_source(self.source_snapshot)
                index = next(
                    i for i, row in enumerate(project.script.lines) if row.id == self.line_target
                )
                self.window.review_controller.commit(
                    edit_line(project.script, index, text=result.texts[0]),
                    "Dịch lại câu",
                    selected=index,
                )
                self.window.log("Đã dịch lại câu từ nội dung gốc liên kết. Cần kiểm tra lại.")
            except (ValueError, StopIteration):
                self._failed("Không áp dụng được bản dịch câu.")
                return
        else:
            if not isinstance(result, Translation):
                self._failed("Bản dịch không hợp lệ.")
                return
            try:
                result.validate_source(self.window.project.transcript)
            except ValueError as exc:
                self._failed(str(exc))
                return
            self.window.project.translation = result
            assert self.window.project.transcript is not None
            self.window.project.set_script(
                draft_from_source(self.window.project.transcript, result)
            )
            self.window.project.approved_revision_hash = None
            self.window.dirty = True
            self.window.review_controller.bind_project()
            self.window.log("Đã dịch. Bản gốc được giữ nguyên; kịch bản chưa duyệt.")
        self.window.left.job_progress.setRange(0, 100)
        self.window.left.job_progress.setValue(100)

    def _failed(self, message: str) -> None:
        self.window.log(message + " Dữ liệu trước đó được giữ nguyên.")
        if self.kind != "test":
            self.window.health_banner.set_result(
                HealthResult(
                    False,
                    "TRANSLATION_FAILED",
                    "Chưa dịch được kịch bản",
                    message,
                    "Cài đặt AI",
                    "open_settings_ai",
                )
            )
        if self.dialog:
            self.dialog.status.setText(message)
            if self.kind == "test":
                self.dialog.credential_status = "Kiểm tra thất bại"
        self.window.left.job_progress.setRange(0, 100)
        self.window.left.job_progress.setValue(0)

    def _cancelled(self) -> None:
        self._failed("Đã dừng. Yêu cầu cloud đã gửi vẫn có thể tính phí.")

    def stop(self) -> None:
        if self.job:
            self.job.cancel()
            self.window.log("Đang dừng yêu cầu cloud…")
            self.refresh()

    def _finished(self) -> None:
        if self.job:
            self.job.deleteLater()
        self.job = None
        self.window.busy = False
        self.window._refresh()
        if self.dialog:
            self.dialog.refresh()
            if self.dialog.close_after_job:
                self.dialog.close_after_job = False
                self.dialog.reject()
        if self.close_after_job:
            self.close_after_job = False
            self.window.close()
