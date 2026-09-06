import logging
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from vkdub.domain.mask import MaskItem
from vkdub.domain.project import Project
from vkdub.domain.subtitle import SubtitleStyle
from vkdub.domain.voice import VoiceSettings
from vkdub.media.ffprobe import VideoMetadata
from vkdub.media.process import MediaTools
from vkdub.providers.tts_provider import HealthResult
from vkdub.services.app_settings import load_app_settings
from vkdub.services.credential_service import redact
from vkdub.services.health_service import run_startup_health_checks
from vkdub.services.project_service import load_project, save_project
from vkdub.services.recovery_service import (
    clear_recovery_state,
    has_recovery_state,
    load_recovery_state,
    save_recovery_state,
)
from vkdub.services.subtitle_service import subtitle_for_time
from vkdub.ui.background_check import BackgroundCheck
from vkdub.ui.capcut_export_controller import CapCutExportController
from vkdub.ui.health_banner import HealthBanner
from vkdub.ui.left_config_panel import LeftConfigPanel
from vkdub.ui.log_viewer_dialog import LogViewerDialog
from vkdub.ui.render_controller import RenderController
from vkdub.ui.review_controller import ReviewController
from vkdub.ui.script_review_panel import ScriptReviewPanel
from vkdub.ui.settings_dialog import SettingsDialog
from vkdub.ui.setup_wizard import SetupWizardDialog
from vkdub.ui.studio_voice_controller import StudioVoiceController
from vkdub.ui.subtitle_style_dialog import SubtitleStyleDialog
from vkdub.ui.transcription_controller import TranscriptionController
from vkdub.ui.translation_controller import TranslationController
from vkdub.ui.tts_controller import TTSController
from vkdub.ui.vbee_controller import VbeeController
from vkdub.ui.video_preview import VideoPreview
from vkdub.version import APP_BRANDING, __version__


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        defaults = load_app_settings()
        self.project = Project(
            source_language=defaults.source_language,
            target_language=defaults.target_language,
            output_directory=Path(defaults.default_output) if defaults.default_output else None,
            voice=VoiceSettings(
                provider=defaults.tts_backend,
                voice_id=defaults.selected_voice or "unconfigured",
                display_name="Chưa chọn giọng",
                speed=defaults.voice_speed,
                volume=min(1, defaults.voice_volume / 100),
            ),
        )
        self.health_job: BackgroundCheck | None = None
        self.setup_wizard: SetupWizardDialog | None = None
        self._startup_seen = False
        self._health_pending = False
        self.project_file: Path | None = None
        self.dirty = False
        self.busy = False
        self.tools_ready = False
        self._script_play_end_ms: int | None = None
        self._pending_import: Path | None = None
        self.started_at = time.monotonic()
        self.left = LeftConfigPanel()
        self.preview = VideoPreview()
        self.review = ScriptReviewPanel()
        self.health_banner = HealthBanner()
        self.health_banner.action_requested.connect(self._on_banner_action)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.left.setMinimumWidth(280)
        splitter.addWidget(self.left)
        splitter.addWidget(self.preview)
        splitter.addWidget(self.review)
        splitter.setSizes([285, 605, 490])
        splitter.setStretchFactor(1, 1)

        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.health_banner)
        central_layout.addWidget(splitter, 1)
        self.setCentralWidget(central_widget)

        self.resize(1380, 860)
        self.setMinimumSize(1060, 650)
        self.tools = MediaTools(self)
        self.tools.tool_status.connect(self._tool_status)
        self.tools.detection_finished.connect(self._detection_finished)
        self.tools.metadata_ready.connect(self._metadata_ready)
        self.tools.probe_failed.connect(self._probe_failed)
        self.left.import_button.clicked.connect(self.choose_video)
        self.left.output_button.clicked.connect(self.choose_output)
        self.left.save_button.clicked.connect(self.save)
        self.left.load_button.clicked.connect(self.choose_project)
        self.left.detect_button.clicked.connect(self.detect_tools)
        self.left.process_button.clicked.connect(self._on_primary_cta_clicked)
        self.left.capcut_folder_requested.connect(lambda: self.open_settings(3))
        self.preview.playback_error.connect(self.log)
        self.review.seek_requested.connect(self.seek_script_line)
        self.preview.player.positionChanged.connect(self._script_playback_position)
        self.transcription = TranscriptionController(self)
        self.translation = TranslationController(self)
        self.review_controller = ReviewController(self)
        self.tts = StudioVoiceController(self)
        if hasattr(self.tts, "panel"):
            self.tts.panel.hide()
        self.render_controller = RenderController(self)
        self.capcut_export = CapCutExportController(self)
        self.vbee_controller = VbeeController(self)
        self.left.vbee_voice_requested.connect(self.vbee_controller.start_workflow)
        self.review.export_button.hide()
        self.review.approve_button.hide()
        self._auto_pipeline: bool = False
        self.settings_dialog: SettingsDialog | None = None
        self.subtitle_dialog: SubtitleStyleDialog | None = None
        self.left.settings_requested.connect(self.open_settings)
        self.left.test_listen_requested.connect(self._test_listen_clicked)
        self.left.manage_voices_requested.connect(lambda: self.open_settings(2))
        self.left.open_capcut_requested.connect(self.capcut_export.open_capcut)
        self.left.open_capcut_folder_requested.connect(self.capcut_export.open_folder)
        self.left.export_video_requested.connect(self.render_controller.open_export_dialog)
        self.left.export_capcut_requested.connect(self.capcut_export.start)
        self.preview.mask_requested.connect(self.add_blur_mask)
        self.preview.subtitle_requested.connect(self.open_subtitle_settings)
        self.preview.subtitle_box_toggled.connect(self._toggle_subtitle_box)
        self.preview.preview_voice_requested.connect(self._preview_voice_clicked)
        self.preview.video.mask_rect_changed.connect(self._on_canvas_mask_rect_changed)
        self.preview.video.mask_delete_requested.connect(self._delete_blur_mask)
        self.preview.video.subtitle_margin_changed.connect(
            self._on_canvas_subtitle_margin_changed
        )
        self.review.play_requested.connect(self.play_script_line)
        self.review.regenerate_requested.connect(self.translation.regenerate_line)
        self._shortcut("Lưu project", QKeySequence.StandardKey.Save, self.save)
        self._shortcut("Mở project", QKeySequence.StandardKey.Open, self.choose_project)
        self._shortcut("Xem log hệ thống", QKeySequence("F12"), self.open_log_viewer)

        # Phase 10: Autosave project state every 30 seconds when dirty
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(30000)
        self.autosave_timer.timeout.connect(self._on_autosave_timer)
        self.autosave_timer.start()

        self._refresh()
        self.log("Sẵn sàng — VK Dub Studio 2.1.")
        QTimer.singleShot(0, self.detect_tools)
        self.recovery_timer = QTimer(self)
        self.recovery_timer.setSingleShot(True)
        self.recovery_timer.timeout.connect(self._check_crash_recovery)
        self.recovery_timer.start(500)
        QTimer.singleShot(2500, self._check_background_update)

    def _on_autosave_timer(self) -> None:
        if load_app_settings().autosave and self.dirty and not self.busy and self.project.script:
            save_recovery_state(self.project, self.project_file)

    def _check_background_update(self) -> None:
        if not load_app_settings().auto_update:
            return

        def worker() -> None:
            try:
                import threading
                from pathlib import Path
                from vkdub.services.update_service import (
                    DEFAULT_UPDATE_FEED_STABLE,
                    download_installer,
                    fetch_update_info,
                    is_newer_version,
                    verify_sha256,
                )
                from vkdub.utils.paths import data_root
                from vkdub.version import __version__

                info = fetch_update_info(DEFAULT_UPDATE_FEED_STABLE, timeout_sec=6.0)
                if not info or not is_newer_version(info.version, __version__):
                    return

                cache_dir = data_root() / "updates"
                cache_dir.mkdir(parents=True, exist_ok=True)
                target = cache_dir / f"VKDubStudio-Setup-v{info.version}.exe"

                if target.is_file() and verify_sha256(target, info.sha256):
                    QTimer.singleShot(0, lambda: self._prompt_update_ready(info, target))
                    return

                downloaded = download_installer(
                    url=info.installer_url,
                    target_path=target,
                    expected_sha256=info.sha256,
                    timeout_sec=120.0,
                )
                if downloaded and target.is_file():
                    QTimer.singleShot(0, lambda: self._prompt_update_ready(info, target))
            except Exception:
                pass

        import threading

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _prompt_update_ready(self, info: Any, target: Path) -> None:
        from vkdub.services.update_service import apply_update_and_restart

        msg = (
            f"🎉 Đã có bản cập nhật mới v{info.version}!\n\n"
            f"Bản cài đặt đã được tải ngầm về máy và xác thực toàn vẹn (SHA-256).\n"
            f"Bạn có muốn đóng ứng dụng để nâng cấp và khởi động lại ngay không?"
        )
        ret = QMessageBox.question(
            self,
            "Cập nhật sẵn sàng — VK Dub Studio",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if ret == QMessageBox.StandardButton.Yes:
            if self.dirty and self.project.script:
                ans = QMessageBox.question(
                    self,
                    "Lưu dự án",
                    "Dự án có thay đổi chưa lưu. Bạn có muốn lưu trước khi cập nhật không?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if ans == QMessageBox.StandardButton.Yes:
                    self.save()

            apply_update_and_restart(target, silent=False)
            app = QApplication.instance()
            if app is not None:
                app.quit()

    def _check_crash_recovery(self) -> None:
        if not self.isVisible():
            return
        if self.setup_wizard is not None and self.setup_wizard.isVisible():
            self.recovery_timer.start(500)
            return
        if not has_recovery_state():
            return
        state = load_recovery_state()
        if not state:
            return
        project, meta = state
        ts = meta.get("timestamp", "Trước đó")
        vid_name = meta.get("video_name", "Không có video")
        lines = meta.get("script_lines", 0)

        ans = QMessageBox.question(
            self,
            "Khôi phục phiên làm việc",
            f"Phát hiện phiên làm việc chưa lưu trước đó ({ts}):\n\n"
            f"• Video: {vid_name}\n"
            f"• Kịch bản: {lines} câu thoại\n\n"
            "Bạn có muốn khôi phục lại phiên làm việc này không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if ans == QMessageBox.StandardButton.Yes:
            self.project = project
            self.review_controller.bind_project()
            if project.video_path and project.video_path.is_file():
                self.preview.load(project.video_path)
            self.preview.video.set_masks(project.masks)
            self.dirty = True
            self._refresh()
            self.log("✓ Đã khôi phục phiên làm việc trước đó thành công.")
        else:
            clear_recovery_state()

    def open_log_viewer(self) -> None:
        dlg = LogViewerDialog(self)
        dlg.exec()

    def open_settings(self, tab_index: int | None = None) -> None:
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self)
            self.settings_dialog.finished.connect(self._settings_applied)
        self.settings_dialog.refresh()
        if tab_index is not None:
            self.settings_dialog.tabs.setCurrentIndex(tab_index)
        self.settings_dialog.show()
        self.settings_dialog.raise_()

    def add_blur_mask(self) -> None:
        if self.busy or not self.project.video_path:
            return
        # Giữ duy nhất 1 khung chọn khu vực phụ đề có thể điều chỉnh phạm vi
        if self.project.masks:
            mask = self.project.masks[0]
            self.preview.video.set_masks(self.project.masks, mask.id, self.preview.player.position())
            self.preview.video.interactive_mask_mode = True
            self.preview.video.update()
            self.statusBar().showMessage(
                "Khung che phụ đề: Kéo để di chuyển · Kéo góc để đổi kích thước bao trọn phụ đề cũ",
                8000,
            )
            return

        mask = MaskItem(
            name="Khung che phụ đề",
            mask_type="erase",
            x=0.08,
            y=0.76,
            width=0.84,
            height=0.15,
            blur_strength=24,
        )
        self.project.masks.append(mask)
        self.preview.video.set_masks(self.project.masks, mask.id, self.preview.player.position())
        self.preview.video.interactive_mask_mode = True
        self.dirty = True
        self._refresh()
        self.statusBar().showMessage(
            "Đã bật Khung che phụ đề: Kéo để di chuyển · Kéo góc để đổi kích thước bao trọn phụ đề cũ",
            12000,
        )

    def _on_canvas_mask_rect_changed(
        self, mask_id: str, x: float, y: float, w: float, h: float
    ) -> None:
        if self.busy:
            return
        mask = next((m for m in self.project.masks if m.id == mask_id), None)
        if mask:
            mask.x, mask.y, mask.width, mask.height = x, y, w, h
            self.dirty = True
            self.setWindowTitle(self.windowTitle().rstrip(" *") + " *")

    def _delete_blur_mask(self, mask_id: str) -> None:
        if self.busy:
            return
        self.project.masks = [m for m in self.project.masks if m.id != mask_id]
        self.preview.video.set_masks(self.project.masks, time_ms=self.preview.player.position())
        self.dirty = True
        self._refresh()
        self.statusBar().showMessage("Đã xóa vùng xóa chữ.", 4000)

    def open_subtitle_settings(self) -> None:
        if self.subtitle_dialog is None:
            self.subtitle_dialog = SubtitleStyleDialog(self)
            self.subtitle_dialog.style_changed.connect(self._on_subtitle_style_changed)
            self.subtitle_dialog.accepted.connect(self._on_subtitle_dialog_accepted)
            self.subtitle_dialog.finished.connect(self._on_subtitle_dialog_finished)
        self.subtitle_dialog.set_current_style(self.project.subtitle_style)
        self.preview.video.subtitle_edit_mode = True
        self._on_subtitle_style_changed(self.project.subtitle_style)
        self.subtitle_dialog.show()
        self.subtitle_dialog.raise_()

    def _on_canvas_subtitle_margin_changed(self, margin_bottom: int) -> None:
        if self.busy:
            return
        style = replace(
            self.project.subtitle_style,
            name="Custom",
            margin_bottom=margin_bottom,
        )
        self.project.subtitle_style = style
        if self.subtitle_dialog and self.subtitle_dialog.isVisible():
            self.subtitle_dialog.margin_slider.setValue(margin_bottom)
        self._on_subtitle_style_changed(style)
        self.dirty = True
        self.setWindowTitle(self.windowTitle().rstrip(" *") + " *")

    def _on_subtitle_dialog_finished(self, _result: int) -> None:
        self.preview.video.subtitle_edit_mode = False
        self.preview.video.update()
        self._script_playback_position(self.preview.player.position())

    def _toggle_subtitle_box(self, checked: bool) -> None:
        if self.busy:
            self.preview.set_subtitle_box_checked(self.project.subtitle_style.background_box)
            return
        self.project.subtitle_style = replace(
            self.project.subtitle_style,
            name="Custom",
            background_box=checked,
        )
        self.dirty = True
        self._on_subtitle_style_changed(self.project.subtitle_style)
        self.statusBar().showMessage(
            "Đã bật khung nền phụ đề." if checked else "Đã tắt khung nền phụ đề.", 4000
        )

    def _on_subtitle_style_changed(self, style: SubtitleStyle) -> None:
        self.project.subtitle_style = style
        # Update current overlay preview immediately
        pos = self.preview.player.position()
        sub = subtitle_for_time(self.project.script, pos)
        if not sub and self.project.script and self.project.script.lines:
            sub = self.project.script.lines[0].text
        self.preview.video.set_subtitle(sub or "", style)

    def _on_subtitle_dialog_accepted(self) -> None:
        if self.subtitle_dialog:
            self.project.subtitle_style = self.subtitle_dialog.get_style()
            self.dirty = True
            self._refresh()

    def _test_listen_clicked(self) -> None:
        if hasattr(self, "tts"):
            self.tts.preview_voice()

    def _preview_voice_clicked(self) -> None:
        if hasattr(self, "tts"):
            self.tts.listen()

    def _shortcut(
        self,
        title: str,
        key: QKeySequence.StandardKey | str | QKeySequence,
        callback: object,
    ) -> None:
        action = QAction(title, self)
        action.setShortcut(QKeySequence(key))
        action.triggered.connect(callback)
        self.addAction(action)

    def log(self, message: str) -> None:
        message = redact(message)
        elapsed = int(time.monotonic() - self.started_at)
        self.left.logs.appendPlainText(
            f"{datetime.now():%H:%M:%S}  +{elapsed // 60:02}:{elapsed % 60:02}  {message}"
        )
        self.left.activity_header.setText(f"● ĐANG THEO DÕI  •  {message[:34]}")
        self.left.logs.moveCursor(QTextCursor.MoveOperation.End)
        self.left.logs.ensureCursorVisible()
        self.statusBar().showMessage(message, 10000)
        logging.getLogger("vkdub").info(message)

    def _error(self, message: str) -> None:
        self.log(message)
        QMessageBox.warning(self, "VK Dub Studio", message)

    def _refresh(self) -> None:
        filename = self.project_file.name if self.project_file else "Project mới"
        self.setWindowTitle(
            f"{APP_BRANDING}  |  v{__version__}  |  {filename}{' *' if self.dirty else ''}"
        )
        if self.project.video_path:
            dur_str = ""
            if self.project.duration_ms:
                s = self.project.duration_ms // 1000
                dur_str = f" • {s // 60:02}:{s % 60:02}"
            self.left.video_path.setText(f"{self.project.video_path.name}{dur_str}")
        else:
            self.left.video_path.setText("Chưa chọn video MP4")
        self.left.video_path.setToolTip(str(self.project.video_path or ""))
        self.left.output_path.setText(
            (self.project.output_directory.name or str(self.project.output_directory))
            if self.project.output_directory
            else "Chưa chọn thư mục"
        )
        self.left.output_path.setToolTip(str(self.project.output_directory or ""))
        languages = {"auto": "Tự động", "vi": "Tiếng Việt", "en": "Tiếng Anh", "zh": "Tiếng Trung"}
        source = languages.get(self.project.source_language, self.project.source_language)
        target = languages.get(self.project.target_language, self.project.target_language)
        self.left.language_voice.setText(
            f"Nguồn: {source}  →  {target}\nGiọng mặc định: HN - Ngọc Huyền"
        )

        busy = self.busy
        enabled = not busy
        self.left.process_button.setEnabled(enabled and self.tools_ready)
        self.left.stop_button.setEnabled(busy)
        self.left.import_button.setEnabled(enabled)
        self.left.load_button.setEnabled(enabled)
        self.left.save_button.setEnabled(not self.busy)
        self.left.output_button.setEnabled(not self.busy)
        self.left.detect_button.setEnabled(enabled)
        can_vbee = enabled and bool(self.project.script) and self.project.is_approved
        self.left.btn_vbee_voice.setEnabled(can_vbee)
        if not self.project.script:
            self.left.btn_vbee_voice.setToolTip("Cần có kịch bản trước khi tạo voice bằng Vbee.")
        elif not self.project.is_approved:
            self.left.btn_vbee_voice.setToolTip("Duyệt kịch bản trước khi tạo voice bằng Vbee.")
        else:
            self.left.btn_vbee_voice.setToolTip(
                "Tự động xuất SRT tiếng Việt, mở Vbee Dubbing Studio, "
                "tạo voice và đồng bộ vào project."
            )

        self.transcription.refresh()
        self.translation.refresh()
        self.review_controller.refresh()

        has_video = bool(self.project.video_path)
        self._refresh_primary_cta()

        stages = [
            (self.left.status_video, "Video", has_video, False),
            (
                self.left.status_stt,
                "Bóc băng",
                self.project.transcript is not None,
                self.workflow_state == "TRANSCRIBING",
            ),
            (
                self.left.status_trans,
                "Dịch",
                self.project.translation is not None,
                self.workflow_state == "TRANSLATING",
            ),
            (
                self.left.status_review,
                "Chờ duyệt",
                self.project.is_approved,
                self.project.script is not None and not self.project.is_approved,
            ),
            (
                self.left.status_voice,
                "Voice",
                self.project.voice_ready,
                self.workflow_state == "GENERATING_VOICE",
            ),
            (
                self.left.status_export,
                "CapCut",
                self.capcut_export.last_result is not None,
                self.capcut_export.job is not None,
            ),
        ]
        for number, (widget, title, done, active) in enumerate(stages, 1):
            widget.setText(
                f"{'✓' if done else '●' if active else '○'} {title}  •  BƯỚC {number}"
                + (" — đang chạy…" if active else "")
            )
            widget.setStyleSheet(
                f"color: {'#34d399' if done else '#fbbf24' if active else '#69768b'};"
            )

    def _refresh_primary_cta(self) -> None:
        state = self.workflow_state
        self.left.update_cta_for_state(state, has_video=bool(self.project.video_path))
        available = False
        if state in ("IDLE", "VIDEO_IMPORTED"):
            from vkdub.services.model_service import dependency_ready

            available = bool(
                self.project.video_path
                and self.project.video_path.is_file()
                and self.tools_ready
                and self.tools.paths.get("ffmpeg")
                and dependency_ready()
            )
        elif state == "TRANSCRIBED":
            available = bool(self.project.transcript and self.project.transcript.segments)
        elif state == "REVIEW_REQUIRED":
            available = self.review.approve_button.isEnabled()
            self.left.process_button.setToolTip(
                "Tích xác nhận đã kiểm tra toàn bộ kịch bản trước khi duyệt."
            )
        elif state == "APPROVED":
            available = self.tts.can_generate()
            if self.project.voice.provider == "vbee":
                self.left.process_button.setToolTip("Tự động tạo voice qua Vbee Dubbing Studio.")
            elif self.project.voice.provider == "capcut_tts":
                self.left.process_button.setToolTip("Tạo voice bằng CapCut TTS.")
            else:
                self.left.process_button.setToolTip("Tạo voice bằng VieNeu Local.")
        elif state == "VOICE_READY":
            has_ffmpeg = bool(self.tools.paths.get("ffmpeg"))
            has_ffprobe = bool(self.tools.paths.get("ffprobe"))
            available = has_ffmpeg and has_ffprobe
            self.left.export_video_button.setEnabled(has_ffmpeg and not self.busy)
            capcut_enabled = available and not self.busy
            self.left.export_capcut_button.setEnabled(capcut_enabled)
            # Tooltip rõ ràng giải thích vì sao nút bị mờ
            if not has_ffprobe and not has_ffmpeg:
                self.left.export_capcut_button.setToolTip(
                    "Cần cài FFmpeg và FFprobe trước. Mở Cài đặt → Nâng cao."
                )
            elif not has_ffprobe:
                self.left.export_capcut_button.setToolTip(
                    "Cần FFprobe để đọc thông tin video. Cài FFmpeg (kèm FFprobe) "
                    "hoặc kiểm tra Cài đặt → Nâng cao."
                )
            elif not has_ffmpeg:
                self.left.export_capcut_button.setToolTip(
                    "Cần FFmpeg để xử lý video. Mở Cài đặt → Nâng cao."
                )
            elif self.busy:
                self.left.export_capcut_button.setToolTip(
                    "Đang xử lý tác vụ khác, vui lòng đợi hoàn thành."
                )
            else:
                self.left.export_capcut_button.setToolTip(
                    "Tạo project CapCut có video đã xóa chữ và voice"
                )
        self.left.process_button.setEnabled(available and not self.busy)
        self.left.speed_combo.setEnabled(not self.busy)
        self.preview.set_subtitle_box_checked(self.project.subtitle_style.background_box)
        can_edit_masks = bool(self.project.video_path) and not self.busy
        self.preview.btn_mask.setEnabled(can_edit_masks)
        self.preview.video.interactive_mask_mode = can_edit_masks
        self.preview.video.update()
        self.left.stop_button.setVisible(self.busy)
        self.left.job_progress.setVisible(self.busy)
        self.left.listen_test_button.setEnabled(self.tts.can_generate() and not self.busy)
        self.left.listen_test_button.setToolTip(
            "Nghe mẫu giọng đang chọn; chưa tạo voice cả kịch bản."
        )
        self.preview.btn_preview_voice.setEnabled(
            bool(self.project.current_voices()) and not self.busy
        )
        if not getattr(self, "legacy_tts_enabled", False):
            self.review.export_button.setEnabled(False)

    def _on_primary_cta_clicked(self) -> None:
        if self.busy or not self.project.video_path:
            return
        state = self.workflow_state
        if state in ("IDLE", "VIDEO_IMPORTED"):
            # Đảm bảo hiển thị 1 khung che phụ đề trên video để người dùng căn chỉnh
            if not self.project.masks:
                self.add_blur_mask()
            else:
                self.preview.video.set_masks(
                    self.project.masks, self.project.masks[0].id, self.preview.player.position()
                )
                self.preview.video.interactive_mask_mode = True
                self.preview.video.update()
            self.statusBar().showMessage(
                "Khung khu vực phụ đề đã bật: Bạn có thể kéo di chuyển hoặc kéo góc để khớp với phụ đề trên video.",
                10000,
            )
            self._auto_pipeline = True
            if not self.transcription.start():
                self._auto_pipeline = False
        elif state == "TRANSCRIBED":
            self.translation.start()
        elif state == "REVIEW_REQUIRED":
            self.review_controller.approve()
        elif state == "APPROVED":
            if (
                self.project.voice.provider == "vbee"
                and hasattr(self, "vbee_controller")
                and self.vbee_controller
            ):
                self.vbee_controller.start_workflow()
            else:
                self.tts.start()
        elif state == "VOICE_READY":
            self.capcut_export.start()

    def _on_banner_action(self, action_id: str) -> None:
        if action_id == "open_settings_ai":
            self.open_settings(1)
        elif action_id == "open_settings_voice":
            self.open_settings(2)
        elif action_id == "open_settings_capcut":
            self.open_settings(3)
        elif action_id == "open_settings_advanced":
            self.open_settings(5)
        elif action_id == "open_settings_update":
            self.open_settings(4)
        elif action_id == "open_settings_general":
            self.open_settings(0)
        else:
            self.open_settings()

    def _startup_checks(self) -> None:
        app_settings = load_app_settings()
        if not self._startup_seen:
            self._startup_seen = True
            if not app_settings.wizard_completed:
                self.setup_wizard = SetupWizardDialog(self)
                self.setup_wizard.finished.connect(self._settings_applied)
                self.setup_wizard.open()
        if self.health_job is not None:
            return
        paths = dict(self.tools.paths)
        self.health_job = BackgroundCheck(lambda: run_startup_health_checks(app_settings, paths))
        self.health_job.succeeded.connect(self._health_results)
        self.health_job.finished.connect(self._health_finished)
        self.health_job.start()

    def _health_finished(self) -> None:
        self.health_job = None
        if self._health_pending:
            self._health_pending = False
            self._startup_checks()

    def _settings_applied(self) -> None:
        self._health_pending = self.health_job is not None
        defaults = load_app_settings()
        self.tts.read_credentials()
        if self.project.video_path is None:
            self.project.source_language = defaults.source_language
            self.project.target_language = defaults.target_language
            self.project.voice = VoiceSettings(
                provider=defaults.tts_backend,
                voice_id=defaults.selected_voice or "unconfigured",
                display_name="Chưa chọn giọng",
                speed=defaults.voice_speed,
                volume=min(1, defaults.voice_volume / 100),
            )
        else:
            if defaults.tts_backend and self.project.voice.provider != defaults.tts_backend:
                self.project.voice = replace(
                    self.project.voice,
                    provider=defaults.tts_backend,
                    voice_id=defaults.selected_voice or self.project.voice.voice_id,
                )
                self.dirty = True
        self.left.speed_combo.blockSignals(True)
        self.left.speed_combo.setCurrentIndex(self.left.speed_combo.findData(defaults.voice_speed))
        self.left.speed_combo.blockSignals(False)
        self.left.refresh_capcut_destination()
        self._refresh()
        self._startup_checks()

    def _health_results(self, results: list[HealthResult]) -> None:
        self.health_results = results
        failed = [r for r in results if not r.ok and r.action_id]
        if failed:
            self.health_banner.set_result(failed[0])
        else:
            self.health_banner.hide()

    def seek_script_line(self, position_ms: int) -> None:
        self._script_play_end_ms = None
        self.preview.player.setPosition(max(0, position_ms))

    def play_script_line(self, position_ms: int, end_ms: int) -> None:
        if end_ms <= position_ms or position_ms < 0:
            self.log("Sửa thời gian câu trước khi phát.")
            return
        self._script_play_end_ms = None
        self.preview.player.setPosition(max(0, position_ms))
        self._script_play_end_ms = end_ms
        self.preview.player.play()

    def _script_playback_position(self, position_ms: int) -> None:
        if self._script_play_end_ms is not None and position_ms >= self._script_play_end_ms:
            self._script_play_end_ms = None
            self.preview.player.pause()
        self.preview.video.set_current_time(position_ms)
        sub = subtitle_for_time(self.project.script, position_ms)
        self.preview.video.set_subtitle(sub or "", self.project.subtitle_style)

    @property
    def workflow_state(self) -> str:
        if hasattr(self, "tts") and self.tts.job is not None and self.tts.kind == "voice":
            return "GENERATING_VOICE"
        if self.translation.job is not None and self.translation.kind != "test":
            return "TRANSLATING"
        if (
            self.transcription.job is not None
            and self.transcription.job.request["kind"] == "transcript"
        ):
            return "TRANSCRIBING"
        return self.project.state

    def detect_tools(self) -> None:
        if self.busy:
            return
        self.tools_ready = False
        self._refresh()
        self.tools.detect()

    def _tool_status(self, name: str, available: bool, message: str) -> None:
        widget = self.left.ffmpeg_status if name == "ffmpeg" else self.left.ffprobe_status
        widget.setText(f"{name}  •  {'Sẵn sàng' if available else 'Chưa sẵn sàng'}")
        widget.setToolTip(message)
        if not available:
            self.log(f"Thiếu công cụ xử lý video ({name}). Mở Cài đặt để kiểm tra.")

    def _detection_finished(self) -> None:
        self.tools_ready = True
        if all(self.tools.paths.values()):
            self.log("Đã kiểm tra công cụ video — sẵn sàng.")
        self._refresh()
        self._startup_checks()

    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Lưu thay đổi?",
            "Project có thay đổi chưa lưu. Bạn có muốn lưu trước khi tiếp tục?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return answer == QMessageBox.StandardButton.Discard

    def choose_video(self) -> None:
        if self.busy or not self.tools_ready:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Tải video MP4", "", "Video MP4 (*.mp4)")
        if path and self._confirm_discard():
            self.import_video(Path(path))

    def import_video(self, path: Path) -> bool:
        if self.busy or not self.tools_ready:
            return False
        path = path.resolve()
        if not path.is_file() or path.suffix.lower() != ".mp4":
            self._error("Hãy chọn một tệp MP4 cục bộ đang tồn tại.")
            return False
        if self.tools.paths["ffprobe"] is None:
            self._apply_import(path, None)
            self.preview.metadata_label.setText("Chưa có ffprobe. Cài FFmpeg để đọc metadata.")
            self.log("Đã mở xem trước; metadata chưa được xác minh vì thiếu ffprobe.")
            return True
        self._pending_import = path
        self.busy = True
        self._refresh()
        self.log("Đang kiểm tra video bằng ffprobe…")
        self.tools.probe(path)
        return True

    def _apply_import(self, path: Path, metadata: VideoMetadata | None) -> None:
        self._script_play_end_ms = None
        self.project = Project(
            video_path=path,
            output_directory=self.project.output_directory,
            transcription_settings=self.project.transcription_settings,
            source_language=self.project.source_language,
            target_language=self.project.target_language,
            voice=self.project.voice,
            video_duration_ms=round(metadata.duration * 1000)
            if metadata and metadata.duration > 0
            else None,
        )
        # Tự động tạo sẵn 1 khung che phụ đề ở chân video
        default_mask = MaskItem(
            name="Khung che phụ đề",
            mask_type="erase",
            x=0.08,
            y=0.76,
            width=0.84,
            height=0.15,
            blur_strength=24,
        )
        self.project.masks = [default_mask]
        self.preview.video.set_masks(self.project.masks, default_mask.id, 0)
        self.preview.video.interactive_mask_mode = True

        self.review_controller.bind_project()
        self.project_file = None
        self.dirty = True
        self.preview.load(path)
        if metadata:
            self.preview.show_metadata(metadata)
        self._refresh()
        self.log(f"Đã nhập video: {path.name} (đã tạo Khung che phụ đề)")

    def _metadata_ready(self, path_text: str, metadata: VideoMetadata) -> None:
        path = Path(path_text)
        if self._pending_import == path:
            self._pending_import = None
            self.busy = False
            self._apply_import(path, metadata)
        elif self.project.video_path == path:
            self.busy = False
            self.project.video_duration_ms = (
                round(metadata.duration * 1000) if metadata.duration > 0 else None
            )
            if self.project.approved_revision_hash and not self.project.is_approved:
                self.project.approved_revision_hash = None
                self.dirty = True
                self.log("Metadata nguồn đã đổi. Cần duyệt lại kịch bản.")
            self.preview.show_metadata(metadata)
            self._refresh()
        self.log("Đã đọc metadata video.")

    def _probe_failed(self, path_text: str, message: str) -> None:
        self.busy = False
        if self._pending_import == Path(path_text):
            self._pending_import = None
            self._refresh()
            self._error(f"Không nhập video. Project hiện tại được giữ nguyên. {message}")
        else:
            self.preview.metadata_label.setText(message)
            self._refresh()
            self.log(message)

    def choose_output(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Chọn thư mục đầu ra",
            str(self.project.output_directory or ""),
        )
        if path:
            self.set_output_directory(Path(path))

    def set_output_directory(self, path: Path) -> bool:
        if not path.is_dir():
            self._error("Thư mục đầu ra không tồn tại. Hãy chọn thư mục khác.")
            return False
        self.project.output_directory = path.resolve()
        self.dirty = True
        self._refresh()
        self.log("Đã chọn thư mục đầu ra.")
        return True

    def save(self) -> bool:
        if self.busy:
            return False
        path = self.project_file
        if path is None:
            name, _ = QFileDialog.getSaveFileName(
                self, "Lưu project", "project.vkdub", "VK Dub project (*.vkdub)"
            )
            if not name:
                return False
            path = Path(name)
            if path.suffix.lower() != ".vkdub":
                path = Path(f"{path}.vkdub")
                if (
                    path.exists()
                    and QMessageBox.question(
                        self,
                        "Ghi đè project?",
                        f"{path.name} đã tồn tại. Ghi đè?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    != QMessageBox.StandardButton.Yes
                ):
                    return False
        return self.save_to(path)

    def save_to(self, path: Path) -> bool:
        try:
            save_project(self.project, path)
        except (OSError, ValueError) as exc:
            self._error(f"Không lưu được project. Kiểm tra quyền ghi và dung lượng đĩa. {exc}")
            return False
        self.project_file = path.resolve()
        self.dirty = False
        clear_recovery_state()
        self._refresh()
        self.log(f"Đã lưu project: {path.name}")
        return True

    def choose_project(self) -> None:
        if self.busy or not self.tools_ready:
            return
        name, _ = QFileDialog.getOpenFileName(self, "Mở project", "", "VK Dub project (*.vkdub)")
        if name and self._confirm_discard():
            self.open_project(Path(name))

    def open_project(self, path: Path) -> bool:
        if self.busy:
            return False
        try:
            project = load_project(path)
        except (OSError, ValueError) as exc:
            self._error(f"Không mở được project: {exc}")
            return False
        self.project = project
        self._script_play_end_ms = None
        self.review_controller.bind_project()
        self.project_file = path.resolve()
        self.dirty = False
        available = project.video_path is not None and project.video_path.is_file()
        self.preview.load(project.video_path if available else None)
        self.preview.video.set_masks(project.masks)
        self._refresh()
        self.log(f"Đã mở project: {path.name}")
        if project.video_path is not None and not available:
            self.preview.empty_hint.setText(
                "Không tìm thấy video nguồn. Khôi phục tệp tại đường dẫn đã lưu."
            )
            self.log(f"Không tìm thấy video nguồn: {project.video_path}. Project được giữ nguyên.")
        elif project.video_path is not None:
            self.busy = True
            self._refresh()
            self.tools.probe(project.video_path)
        if project.output_directory is not None and not project.output_directory.is_dir():
            self.log("Thư mục đầu ra không còn tồn tại. Hãy chọn lại thư mục.")
        return True

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.capcut_export.job is not None:
            QMessageBox.information(
                self,
                "Đang xuất CapCut",
                "Đợi tạo project CapCut xong rồi đóng ứng dụng để tránh draft dang dở.",
            )
            event.ignore()
            return
        active: TranscriptionController | TranslationController | TTSController
        active = self.transcription if self.transcription.job is not None else self.translation
        if self.tts.job is not None:
            active = self.tts
        if active.job is not None:
            answer = QMessageBox.question(
                self,
                "Dừng công việc?",
                "Công việc đang chạy. Dừng rồi đóng ứng dụng?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                active.close_after_job = True
                active.stop()
            event.ignore()
            return
        if not self._confirm_discard():
            event.ignore()
            return
        self.preview.player.stop()
        self.autosave_timer.stop()
        self.recovery_timer.stop()
        self.tts.player.stop()
        self.tools.shutdown()
        clear_recovery_state()
        event.accept()
