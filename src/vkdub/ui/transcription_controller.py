from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject

from vkdub.domain.transcript import Transcript, TranscriptionSettings
from vkdub.services.model_service import dependency_ready, model_ready
from vkdub.services.transcription_service import LocalJob

if TYPE_CHECKING:
    from vkdub.ui.main_window import MainWindow


class TranscriptionController(QObject):
    """Coordinates Phase 2 only. Completion never dispatches translation/TTS/render."""

    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self.job: LocalJob | None = None
        self.close_after_job = False
        panel = window.left
        panel.model_selector.currentTextChanged.connect(self.settings_changed)
        panel.device_selector.currentIndexChanged.connect(self.settings_changed)
        panel.source_language.currentIndexChanged.connect(self.settings_changed)
        panel.download_button.clicked.connect(self.download)
        panel.stop_button.clicked.connect(self.stop)

    def _on_process_clicked(self) -> None:
        project = self.window.project
        if project.transcript is not None and project.script is None:
            self.window.log("Bắt đầu dịch sang tiếng Việt bằng Gemini AI…")
            self.window.translation.start()
            return
        if project.script is not None and not project.is_approved:
            self.window.log(
                "👉 Kịch bản tiếng Việt đã sẵn sàng! Hãy kiểm tra ở cột bên phải, "
                "tích chọn 'Tôi đã kiểm tra toàn bộ kịch bản' và bấm 'DUYỆT KỊCH BẢN TẠO VOICE'."
            )
            return
        if project.is_approved and not project.voice_ready:
            self.window.tts.start()
            return
        if project.voice_ready:
            self.window.render_controller.open_export_dialog()
            return
        self.window._auto_pipeline = True
        self.start()

    def refresh(self) -> None:
        window, panel = self.window, self.window.left
        settings = window.project.transcription_settings
        for combo, value in (
            (panel.model_selector, settings.model),
            (panel.device_selector, settings.device),
            (panel.source_language, window.project.source_language),
        ):
            combo.blockSignals(True)
            index = (
                combo.findData(value) if combo != panel.model_selector else combo.findText(value)
            )
            if index < 0:
                combo.addItem(value, value)
                index = combo.count() - 1
            combo.setCurrentIndex(index)
            combo.blockSignals(False)
            combo.setEnabled(not window.busy)
        installed = model_ready(settings.model)
        dependency = dependency_ready()
        panel.model_status.setText(
            "Chưa cài faster-whisper; xem README."
            if not dependency
            else f"{settings.model}: "
            + ("Đã tải • dùng được offline" if installed else "Chưa tải model")
        )
        panel.download_button.setEnabled(not window.busy and dependency and not installed)
        video = window.project.video_path
        has_video = bool(video and video.is_file())
        has_ffmpeg = bool(window.tools.paths.get("ffmpeg"))
        tools_ready = window.tools_ready
        ready = bool(has_video and has_ffmpeg and tools_ready and dependency)
        panel.process_button.setEnabled(ready and not window.busy)
        if not has_video:
            panel.process_button.setText("🚀 BẮT ĐẦU XỬ LÝ")
            panel.process_button.setToolTip("Hãy chọn một tệp video MP4 trước khi bắt đầu xử lý.")
        elif not has_ffmpeg:
            panel.process_button.setText("🚀 BẮT ĐẦU XỬ LÝ")
            panel.process_button.setToolTip("Chưa tìm thấy FFmpeg trên máy tính để đọc âm thanh.")
        elif not dependency:
            panel.process_button.setText("🚀 BẮT ĐẦU XỬ LÝ")
            panel.process_button.setToolTip("Chưa cài đặt thư viện faster-whisper.")
        elif window.project.transcript is not None and window.project.script is None:
            panel.process_button.setText("🌐 DỊCH SANG TIẾNG VIỆT")
            panel.process_button.setToolTip(
                "Bấm để dịch các câu thoại bóc băng sang tiếng Việt qua Gemini AI."
            )
        elif window.project.script is not None and not window.project.is_approved:
            panel.process_button.setText("👉 DUYỆT KỊCH BẢN BÊN PHẢI")
            panel.process_button.setToolTip(
                "Hãy kiểm tra cột bên phải, tích chọn 'Tôi đã kiểm tra...' và bấm DUYỆT."
            )
        elif window.project.is_approved and not window.project.voice_ready:
            panel.process_button.setText("🎙 TẠO VOICE LỒNG TIẾNG")
            panel.process_button.setToolTip("Bấm để tạo giọng đọc thuyết minh tiếng Việt.")
        elif window.project.voice_ready:
            panel.process_button.setText("🎬 XUẤT VIDEO HOÀN CHỈNH")
            panel.process_button.setToolTip("Voice đã sẵn sàng! Bấm để xuất video MP4 hoàn thiện.")
        elif not installed:
            panel.process_button.setText("🚀 BẮT ĐẦU XỬ LÝ")
            panel.process_button.setToolTip(
                f"Nhấn để tải mô hình Faster-Whisper '{settings.model}' và bắt đầu xử lý."
            )
        else:
            panel.process_button.setText("🚀 BẮT ĐẦU XỬ LÝ")
            panel.process_button.setToolTip(
                "Bắt đầu quy trình: Bóc băng và dịch tự động sang tiếng Việt."
            )
        panel.reuse_cache.setEnabled(not window.busy)
        panel.stop_button.setEnabled(self.job is not None and not self.job.cancel_event.is_set())

    def settings_changed(self) -> None:
        if self.window.busy:
            return
        panel = self.window.left
        self.window.project.transcription_settings = TranscriptionSettings(
            panel.model_selector.currentText(),
            panel.device_selector.currentData(),
        )
        self.window.project.source_language = panel.source_language.currentData()
        from vkdub.services.app_settings import load_app_settings, save_app_settings

        settings = load_app_settings()
        settings.source_language = self.window.project.source_language
        save_app_settings(settings)
        self.window.dirty = True
        self.window._refresh()

    def download(self) -> bool:
        if self.window.busy or not dependency_ready():
            return False
        name = self.window.project.transcription_settings.model
        if model_ready(name):
            return False
        return self._launch({"kind": "model", "model": name})

    def start(self) -> bool:
        self.refresh()
        if not self.window.left.process_button.isEnabled():
            self.window.log("Cần video và FFmpeg sẵn sàng trước khi bóc băng.")
            return False
        project = self.window.project
        name = project.transcription_settings.model
        if not model_ready(name):
            self.window.log(f"Đang tải mô hình Faster-Whisper '{name}' về máy...")
            return self.download()
        if not self.window.review_controller.confirm_replace():
            return False
        self.window.preview.player.pause()
        return self._launch(
            {
                "kind": "transcript",
                "video": str(project.video_path),
                "ffmpeg": self.window.tools.paths["ffmpeg"],
                "settings": asdict(project.transcription_settings),
                "language": project.source_language,
                "reuse_cache": self.window.left.reuse_cache.isChecked(),
            }
        )

    def _launch(self, request: dict[str, Any]) -> bool:
        self.window.busy = True
        self.job = LocalJob(request)
        self.job.progress.connect(self._progress)
        self.job.succeeded.connect(self._succeeded)
        self.job.failed.connect(self._failed)
        self.job.cancelled.connect(self._cancelled)
        self.job.finished.connect(self._finished)
        self.window.left.job_progress.setRange(0, 0)
        self.window.review.stage.setText(
            "Đang tải model…" if request["kind"] == "model" else "ĐANG BÓC BĂNG…"
        )
        self.window._refresh()
        self.job.start()
        return True

    def stop(self) -> None:
        if self.job is not None:
            self.job.cancel()
            self.window.log("Đang dừng công việc…")
            self.refresh()

    def _progress(self, percent: int, message: str) -> None:
        bar = self.window.left.job_progress
        bar.setRange(0, 0 if percent < 0 else 100)
        if percent >= 0:
            bar.setValue(percent)
        self.window.log(message)

    def _succeeded(self, result: dict[str, Any]) -> None:
        if self.job is None or self.job.cancel_event.is_set():
            return
        if result["kind"] == "model":
            self.window.review.stage.setText("Model đã tải. Sẵn sàng bóc băng cục bộ.")
            self.window.log(f"Đã tải xong model {result['model']}. Đang bắt đầu bóc băng...")
            if getattr(self.window, "_auto_pipeline", False):
                self._pending_auto_transcribe = True
        else:
            try:
                transcript = Transcript.from_dict(result["transcript"])
            except ValueError as exc:
                self._failed(str(exc))
                return
            self.window.project.transcript = transcript
            self.window.project.translation = None
            self.window.project.set_script(None)
            self.window.dirty = True
            self.window.review_controller.bind_project()
            cache_note = " (dùng cache)" if result.get("reused") else ""
            self.window.log(
                f"Đã bóc băng {len(transcript.segments)} câu{cache_note}. "
                "Đã dừng; chưa dịch hoặc tạo voice."
            )
            if getattr(self.window, "_auto_pipeline", False):
                self.window._auto_pipeline = False
                try:
                    from vkdub.services.credential_service import CredentialStore

                    if CredentialStore().get():
                        self.window.log(
                            "Bóc băng thành công! Đang chuẩn bị dịch tự động sang tiếng Việt…"
                        )
                        self._pending_auto_translate = True
                    else:
                        self.window.log(
                            "Bóc băng thành công! Chưa có Gemini API Key để dịch tự động. "
                            "Bạn có thể mở ⚙ Cài đặt để nhập key."
                        )
                except Exception:
                    pass
        self.window.left.job_progress.setRange(0, 100)
        self.window.left.job_progress.setValue(100)

    def _failed(self, message: str) -> None:
        self.window._auto_pipeline = False
        self.window.review.stage.setText("Không hoàn thành. Dữ liệu trước đó được giữ nguyên.")
        self.window.log(f"Lỗi: {message} Có thể thử lại; chọn CPU nếu CUDA không sẵn sàng.")
        self.window.left.job_progress.setRange(0, 100)
        self.window.left.job_progress.setValue(0)

    def _cancelled(self) -> None:
        self.window._auto_pipeline = False
        self.window.review.stage.setText("ĐÃ DỪNG  •  Dữ liệu trước đó được giữ nguyên")
        self.window.log("Đã dừng; bản chép lời trước đó được giữ nguyên.")
        self.window.left.job_progress.setRange(0, 100)
        self.window.left.job_progress.setValue(0)

    def _finished(self) -> None:
        if self.job:
            self.job.deleteLater()
        self.job = None
        self.window.busy = False
        self.window._refresh()
        if self.close_after_job:
            self.close_after_job = False
            self.window.close()
            return
        if getattr(self, "_pending_auto_transcribe", False):
            self._pending_auto_transcribe = False
            from PySide6.QtCore import QTimer

            QTimer.singleShot(0, self.start)
        if getattr(self, "_pending_auto_translate", False):
            self._pending_auto_translate = False
            from PySide6.QtCore import QTimer

            QTimer.singleShot(150, self.window.translation.start)
