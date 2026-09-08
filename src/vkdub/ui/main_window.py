import logging
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from vkdub.bridge.local_agent import LocalAgent
from vkdub.domain.mask import MaskItem
from vkdub.domain.project import Project
from vkdub.domain.subtitle import SubtitleStyle
from vkdub.domain.voice import VoiceSettings
from vkdub.media.ffprobe import VideoMetadata
from vkdub.media.process import MediaTools
from vkdub.orchestrator.pipeline_runner import PipelineRunner
from vkdub.orchestrator.pipeline_state import PipelineState, SubstepStatus
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
from vkdub.ui.diagnostics_drawer import DiagnosticsDrawer
from vkdub.ui.health_banner import HealthBanner
from vkdub.ui.left_config_panel import LeftConfigPanel
from vkdub.ui.log_viewer_dialog import LogViewerDialog
from vkdub.ui.panels.step1_source_panel import Step1SourcePanel
from vkdub.ui.panels.step2_voice_panel import Step2VoicePanel
from vkdub.ui.panels.step3_blur_panel import Step3BlurPanel
from vkdub.ui.panels.step4_automation_panel import Step4AutomationPanel
from vkdub.ui.render_controller import RenderController
from vkdub.ui.review_controller import ReviewController
from vkdub.ui.script_review_panel import ScriptReviewPanel
from vkdub.ui.settings_dialog import SettingsDialog
from vkdub.ui.setup_wizard import SetupWizardDialog
from vkdub.ui.stepper_sidebar import WorkflowStepper
from vkdub.ui.studio_voice_controller import StudioVoiceController
from vkdub.ui.toast import ToastManager, ToastType
from vkdub.ui.top_bar import TopBar
from vkdub.ui.transcription_controller import TranscriptionController
from vkdub.ui.translation_controller import TranslationController
from vkdub.ui.tts_controller import TTSController
from vkdub.ui.vbee_controller import VbeeController
from vkdub.ui.video_preview import VideoPreview
from vkdub.utils.paths import workspace_root
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
        self.video_metadata: VideoMetadata | None = None
        self.started_at = time.monotonic()
        self.left = LeftConfigPanel()
        self.top_bar = TopBar(self)
        self.stepper = WorkflowStepper(self)
        self.preview = VideoPreview()

        self.step_stack = QStackedWidget(self)
        self.step1_panel = Step1SourcePanel(self)
        self.step2_panel = Step2VoicePanel(self)
        self.step3_panel = Step3BlurPanel(self)
        self.step4_panel = Step4AutomationPanel(self)
        self.review = ScriptReviewPanel()

        self.step_stack.addWidget(self.step1_panel)  # Index 0
        self.step_stack.addWidget(self.step2_panel)  # Index 1
        self.step_stack.addWidget(self.step3_panel)  # Index 2
        self.step_stack.addWidget(self.step4_panel)  # Index 3
        self.step_stack.addWidget(self.review)       # Index 4

        self.health_banner = HealthBanner()
        self.health_banner.action_requested.connect(self._on_banner_action)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter = self.splitter
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.stepper)
        splitter.addWidget(self.preview)
        splitter.addWidget(self.step_stack)
        splitter.setSizes([220, 560, 600])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)

        self.diagnostics_drawer = DiagnosticsDrawer(self)
        self.diagnostics_drawer.open_log_viewer_requested.connect(self.open_log_viewer)

        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.top_bar)
        central_layout.addWidget(self.health_banner)
        central_layout.addWidget(splitter, 1)
        central_layout.addWidget(self.diagnostics_drawer)
        self.setCentralWidget(central_widget)

        self.resize(1380, 860)
        self.setMinimumSize(1060, 650)
        self.toast_manager = ToastManager(self)

        # Controllers and Subsystems
        self.tools = MediaTools(self)
        self.local_agent = LocalAgent(parent=self)
        self.transcription = TranscriptionController(self)
        self.translation = TranslationController(self)
        self.review_controller = ReviewController(self)
        self.tts = StudioVoiceController(self)
        if hasattr(self.tts, "panel"):
            self.tts.panel.hide()
        self.render_controller = RenderController(self)
        self.capcut_export = CapCutExportController(self)
        self.vbee_controller = VbeeController(self)
        self.pipeline_runner: PipelineRunner | None = None
        self._auto_pipeline: bool = False
        self.settings_dialog: SettingsDialog | None = None
        self.subtitle_dialog: SubtitleStyleDialog | None = None

        # Media tools connections
        self.tools.tool_status.connect(self._tool_status)
        self.tools.detection_finished.connect(self._detection_finished)
        self.tools.metadata_ready.connect(self._metadata_ready)
        self.tools.probe_failed.connect(self._probe_failed)

        # H6 Browser Bridge: Local Agent integration
        self.local_agent.status_updated.connect(self.top_bar.update_bridge_status)
        self.local_agent.status_updated.connect(self.left.browser_bridge.update_status)
        if hasattr(self, "step4_panel"):
            self.local_agent.status_updated.connect(self.step4_panel.update_health)
        self.local_agent.log_emitted.connect(self.log)
        self.local_agent.start()

        # TopBar connections
        self.top_bar.new_requested.connect(self.new_project)
        self.top_bar.settings_requested.connect(self.open_settings)
        self.top_bar.save_requested.connect(self.save)
        self.top_bar.open_requested.connect(self.choose_project)
        self.top_bar.open_edge_requested.connect(
            lambda: self.local_agent.open_browser("https://chatgpt.com")
        )
        self.top_bar.refresh_bridge_requested.connect(self.local_agent.request_status)

        # Stepper connection
        self.stepper.step_selected.connect(self.switch_to_step)

        # Step 1 connections
        self.step1_panel.choose_video_requested.connect(self.choose_video)
        self.step1_panel.download_url_requested.connect(self._on_download_url_requested)
        self.step1_panel.continue_requested.connect(lambda: self.switch_to_step(1))

        # Step 2 connections
        self.step2_panel.voice_changed.connect(self._on_voice_panel_changed)
        self.step2_panel.test_listen_requested.connect(self._test_listen_clicked)
        self.step2_panel.back_requested.connect(lambda: self.switch_to_step(0))
        self.step2_panel.continue_requested.connect(lambda: self.switch_to_step(2))

        # Step 3 connections
        self.step3_panel.add_region_requested.connect(self.add_blur_zone)
        self.step3_panel.add_mask_requested.connect(self.add_blur_mask)
        self.step3_panel.add_sub_region_requested.connect(self.add_sub_region)
        self.step3_panel.delete_region_requested.connect(self._delete_blur_mask)
        self.step3_panel.region_selected.connect(self._on_inspector_region_selected)
        self.step3_panel.region_changed.connect(self._on_inspector_region_changed)
        self.step3_panel.region_type_changed.connect(self._on_inspector_region_type_changed)
        self.step3_panel.region_name_changed.connect(self._on_inspector_region_name_changed)
        self.step3_panel.back_requested.connect(lambda: self.switch_to_step(1))
        self.step3_panel.continue_requested.connect(lambda: self.switch_to_step(3))

        # Step 4 connections
        self.step4_panel.start_requested.connect(self._start_pipeline_runner)
        self.step4_panel.cancel_requested.connect(self._cancel_pipeline_runner)
        self.step4_panel.retry_step_requested.connect(self._retry_pipeline_step)
        self.step4_panel.import_srt_requested.connect(self._on_import_chatgpt_srt_clicked)
        self.step4_panel.continue_requested.connect(lambda: self.switch_to_step(4))
        self.step4_panel.btn_health_check.clicked.connect(self._on_health_check_clicked)

        # Step 5 (Review & Export) connections
        self.review.export_video_requested.connect(self.render_controller.open_export_dialog)
        self.review.export_capcut_requested.connect(self.capcut_export.start)
        self.review.capcut_folder_requested.connect(lambda: self.open_settings(3))
        self.review.open_capcut_requested.connect(self.capcut_export.open_capcut)
        self.review.open_capcut_folder_requested.connect(self.capcut_export.open_folder)
        self.review.seek_requested.connect(self.seek_script_line)
        self.review.play_requested.connect(self.play_script_line)
        self.review.regenerate_requested.connect(self.translation.regenerate_line)

        # Preview connections
        self.preview.playback_error.connect(self.log)
        self.preview.player.positionChanged.connect(self._script_playback_position)
        self.preview.mask_requested.connect(self.add_blur_mask)
        self.preview.blur_requested.connect(lambda: (self.switch_to_step(2), self.add_blur_zone()))
        self.preview.sub_region_requested.connect(lambda: (self.switch_to_step(2), self.add_sub_region("bottom")))
        self.preview.subtitle_requested.connect(self.open_subtitle_settings)
        self.preview.subtitle_box_toggled.connect(self._toggle_subtitle_box)
        self.preview.preview_voice_requested.connect(self._preview_voice_clicked)
        self.preview.video.mask_selected.connect(self._on_canvas_mask_selected)
        self.preview.video.mask_rect_changed.connect(self._on_canvas_mask_rect_changed)
        self.preview.video.mask_delete_requested.connect(self._delete_blur_mask)
        self.preview.video.subtitle_margin_changed.connect(self._on_canvas_subtitle_margin_changed)

        # Legacy facade event forwarding for tests and existing controllers
        self.left.import_button.clicked.connect(self.choose_video)
        self.left.output_button.clicked.connect(self.choose_output)
        self.left.save_button.clicked.connect(self.save)
        self.left.load_button.clicked.connect(self.choose_project)
        self.left.detect_button.clicked.connect(self.detect_tools)
        self.left.process_button.clicked.connect(self._on_primary_cta_clicked)
        self.left.capcut_folder_requested.connect(lambda: self.open_settings(3))
        self.left.voice_settings_changed.connect(self._on_legacy_voice_changed)
        self.left.vbee_voice_requested.connect(self.vbee_controller.start_workflow)
        self.left.vbee_export_srt_requested.connect(self.vbee_controller.export_srt_dialog)
        self.left.vbee_manual_audio_requested.connect(
            self.vbee_controller.import_manual_audio_dialog
        )
        self.left.settings_requested.connect(self.open_settings)
        self.left.test_listen_requested.connect(self._test_listen_clicked)
        self.left.manage_voices_requested.connect(lambda: self.open_settings(2))
        self.left.open_capcut_requested.connect(self.capcut_export.open_capcut)
        self.left.open_capcut_folder_requested.connect(self.capcut_export.open_folder)
        self.left.export_video_requested.connect(self.render_controller.open_export_dialog)
        self.left.export_capcut_requested.connect(self.capcut_export.start)
        self.left.chatgpt_translate_requested.connect(self._on_chatgpt_translate_clicked)
        self.left.import_chatgpt_srt_requested.connect(self._on_import_chatgpt_srt_clicked)
        self.left.approve_script_requested.connect(self._on_approve_script_clicked)
        self.left.toggle_mask_requested.connect(self.add_blur_mask)
        self.left.open_browser_requested.connect(
            lambda: self.local_agent.open_browser("https://chatgpt.com")
        )
        self.left.refresh_bridge_requested.connect(self.local_agent.request_status)
        self.left.pipeline_start_requested.connect(self._start_pipeline_runner)
        self.left.pipeline_cancel_requested.connect(self._cancel_pipeline_runner)
        self.left.pipeline_retry_step_requested.connect(self._retry_pipeline_step)
        self.left.step4_pipeline.view_log_requested.connect(self.open_log_viewer)

        self._shortcut("Project mới", QKeySequence.StandardKey.New, self.new_project)
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
        QTimer.singleShot(1500, self._sync_capcut_drafts_compatibility)

    def _on_autosave_timer(self) -> None:
        if load_app_settings().autosave and self.dirty and not self.busy and self.project.script:
            save_recovery_state(self.project, self.project_file)

    def _check_background_update(self) -> None:
        if not load_app_settings().auto_update:
            return

        def worker() -> None:
            try:
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

    def _sync_capcut_drafts_compatibility(self) -> None:
        def worker() -> None:
            try:
                from vkdub.services.app_settings import load_app_settings
                from vkdub.services.capcut_export import patch_existing_vkdub_drafts

                root_str = load_app_settings().capcut_draft_root
                if root_str:
                    root = Path(root_str).expanduser()
                    if root.is_dir():
                        count = patch_existing_vkdub_drafts(root)
                        if count > 0:
                            self.log(
                                f"🎬 Đã tự động đồng bộ {count} dự án CapCut cũ tương thích với máy tính này."
                            )
            except Exception as e:
                logger.debug("Background CapCut patch error: %s", e)

        import threading

        threading.Thread(target=worker, daemon=True).start()

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

            apply_update_and_restart(target, info.sha256, silent=False)
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

    def switch_to_step(self, step_idx: int) -> None:
        """Switch active step in left stepper and right contextual stack."""
        if 0 <= step_idx <= 4:
            self.stepper.set_current_step(step_idx)
            self.step_stack.setCurrentIndex(step_idx)
            if step_idx == 2:
                # Entering Step 3: Blur inspector mode
                self.preview.video.interactive_mask_mode = True
                active_id = self.step3_panel._current_mask_id or (
                    self.project.masks[0].id if self.project.masks else None
                )
                self.preview.video.set_masks(
                    self.project.masks, active_id, self.preview.player.position()
                )
                self.preview.video.update()
            elif step_idx != 2 and not self.project.masks:
                self.preview.video.interactive_mask_mode = False
                self.preview.video.update()
            if step_idx == 4 and hasattr(self, "splitter"):
                cur = self.splitter.sizes()
                if len(cur) == 3 and cur[2] < 620:
                    tot = sum(cur)
                    self.splitter.setSizes([200, max(420, tot - 200 - 640), 640])

    def _on_download_url_requested(self, url: str) -> None:
        if not url:
            return
        self.log(f"Đang kiểm tra liên kết video: {url}")
        self.statusBar().showMessage(f"Đang kiểm tra liên kết {url}...", 5000)
        QMessageBox.information(
            self,
            "Tải video từ link",
            f"Đang xử lý link video:\n{url}\n\n"
            "Mẹo: Bạn có thể tải video về máy và nhấn '📂 CHỌN VIDEO TỪ MÁY (MP4)' để xử lý ngay.",
        )

    def _on_voice_panel_changed(self) -> None:
        v_id = self.step2_panel.voice_combo.currentData()
        spd = self.step2_panel.speed_combo.currentData() or 1.1
        self.project.voice = replace(
            self.project.voice,
            voice_id=v_id,
            display_name=self.step2_panel.voice_combo.currentText(),
            speed=spd,
        )
        if hasattr(self, "left"):
            idx_v = self.left.voice_combo.findData(v_id)
            if idx_v >= 0 and self.left.voice_combo.currentIndex() != idx_v:
                self.left.voice_combo.blockSignals(True)
                self.left.voice_combo.setCurrentIndex(idx_v)
                self.left.voice_combo.blockSignals(False)
            idx_s = self.left.speed_combo.findData(spd)
            if idx_s >= 0 and self.left.speed_combo.currentIndex() != idx_s:
                self.left.speed_combo.blockSignals(True)
                self.left.speed_combo.setCurrentIndex(idx_s)
                self.left.speed_combo.blockSignals(False)
        self.dirty = True
        self._refresh()

    def _on_legacy_voice_changed(self) -> None:
        v_id = self.left.voice_combo.currentData()
        spd = self.left.speed_combo.currentData() or 1.1
        self.project.voice = replace(
            self.project.voice,
            voice_id=v_id,
            display_name=self.left.voice_combo.currentText(),
            speed=spd,
        )
        if hasattr(self, "step2_panel"):
            idx_v = self.step2_panel.voice_combo.findData(v_id)
            if idx_v >= 0 and self.step2_panel.voice_combo.currentIndex() != idx_v:
                self.step2_panel.voice_combo.blockSignals(True)
                self.step2_panel.voice_combo.setCurrentIndex(idx_v)
                self.step2_panel.voice_combo.blockSignals(False)
            idx_s = self.step2_panel.speed_combo.findData(spd)
            if idx_s >= 0 and self.step2_panel.speed_combo.currentIndex() != idx_s:
                self.step2_panel.speed_combo.blockSignals(True)
                self.step2_panel.speed_combo.setCurrentIndex(idx_s)
                self.step2_panel.speed_combo.blockSignals(False)
        self.dirty = True
        self._refresh()

    def _on_inspector_region_selected(self, mask_id: str) -> None:
        self.preview.video.interactive_mask_mode = True
        self.preview.video.set_masks(
            self.project.masks, mask_id, self.preview.player.position()
        )
        self.preview.video.update()

    def _on_inspector_region_changed(
        self, mask_id: str, x: float, y: float, w: float, h: float, strength: int
    ) -> None:
        mask = next((m for m in self.project.masks if m.id == mask_id), None)
        if mask:
            mask.x, mask.y, mask.width, mask.height = x, y, w, h
            mask.blur_strength = strength
            self.preview.video.set_masks(
                self.project.masks, mask_id, self.preview.player.position()
            )
            self.preview.video.update()
            self.dirty = True
            self.setWindowTitle(self.windowTitle().rstrip(" *") + " *")

    def _on_canvas_mask_selected(self, mask_id: str) -> None:
        if hasattr(self, "step3_panel"):
            self.step3_panel.select_mask(mask_id)

    def _on_inspector_region_type_changed(self, mask_id: str, new_type: str) -> None:
        if self.busy:
            return
        mask = next((m for m in self.project.masks if m.id == mask_id), None)
        if mask:
            mask.mask_type = new_type
            self.preview.video.set_masks(
                self.project.masks, mask_id, self.preview.player.position()
            )
            self.preview.video.update()
            self.dirty = True
            self.setWindowTitle(self.windowTitle().rstrip(" *") + " *")

    def _on_inspector_region_name_changed(self, mask_id: str, new_name: str) -> None:
        if self.busy:
            return
        mask = next((m for m in self.project.masks if m.id == mask_id), None)
        if mask:
            mask.name = new_name
            self.preview.video.set_masks(
                self.project.masks, mask_id, self.preview.player.position()
            )
            self.preview.video.update()
            self.dirty = True
            self.setWindowTitle(self.windowTitle().rstrip(" *") + " *")

    def add_sub_region(self, position: str = "bottom") -> None:
        """Thêm vùng lấy phụ đề (viền đỏ, không làm mờ video, hỗ trợ nhiều vùng)."""
        if self.busy or not self.project.video_path:
            return
        sub_count = sum(1 for m in self.project.masks if m.mask_type == "sub_region")
        pos_label = "Dưới" if position == "bottom" else "Trên"
        name = f"Vùng lấy sub ({pos_label})"
        if sub_count > 0:
            name += f" #{sub_count + 1}"
        y_pos = 0.76 if position == "bottom" else 0.06
        mask = MaskItem(
            name=name,
            mask_type="sub_region",
            x=0.08,
            y=y_pos,
            width=0.84,
            height=0.15,
            blur_strength=1,
        )
        self.project.masks.append(mask)
        self.preview.video.set_masks(self.project.masks, mask.id, self.preview.player.position())
        self.preview.video.interactive_mask_mode = True
        if hasattr(self, "step3_panel"):
            self.step3_panel.set_masks(self.project.masks, mask.id)
        self.dirty = True
        self._refresh()
        self.statusBar().showMessage(
            f"Đã thêm {name} (Viền màu đỏ): Kéo để di chuyển · Kéo góc để đổi kích cỡ",
            10000,
        )

    def add_blur_mask(self) -> None:
        if self.busy or not self.project.video_path:
            return
        erase_mask = next((m for m in self.project.masks if m.mask_type == "erase"), None)
        if erase_mask:
            self.preview.video.set_masks(
                self.project.masks, erase_mask.id, self.preview.player.position()
            )
            self.preview.video.interactive_mask_mode = True
            self.preview.video.update()
            if hasattr(self, "step3_panel"):
                self.step3_panel.set_masks(self.project.masks, erase_mask.id)
            self.statusBar().showMessage(
                "Khung che phụ đề: Kéo để di chuyển · Kéo góc để đổi kích thước bao trọn phụ đề cũ",
                8000,
            )
            return

        erase_count = sum(1 for m in self.project.masks if m.mask_type == "erase")
        name = "Khung che phụ đề" if erase_count == 0 else f"Khung che phụ đề #{erase_count + 1}"
        mask = MaskItem(
            name=name,
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
        if hasattr(self, "step3_panel"):
            self.step3_panel.set_masks(self.project.masks, mask.id)
        self.dirty = True
        self._refresh()
        self.statusBar().showMessage(
            "Đã bật Khung che phụ đề: Kéo để di chuyển · Kéo góc để đổi kích thước "
            "bao trọn phụ đề cũ",
            12000,
        )

    def add_blur_zone(self) -> None:
        """Thêm vùng blur để che watermark, logo hoặc chữ không cần dịch."""
        if self.busy or not self.project.video_path:
            return
        blur_count = sum(1 for m in self.project.masks if m.mask_type == "blur")
        mask = MaskItem(
            name=f"Làm mờ {blur_count + 1}",
            mask_type="blur",
            x=0.10,
            y=0.05,
            width=0.35,
            height=0.12,
            blur_strength=20,
        )
        self.project.masks.append(mask)
        self.preview.video.set_masks(self.project.masks, mask.id, self.preview.player.position())
        self.preview.video.interactive_mask_mode = True
        if hasattr(self, "step3_panel"):
            self.step3_panel.set_masks(self.project.masks, mask.id)
        self.dirty = True
        self._refresh()
        self.statusBar().showMessage(
            "Đã thêm vùng Làm mờ: Kéo để di chuyển · Kéo góc để thay đổi kích thước",
            10000,
        )

    def _on_canvas_mask_rect_changed(
        self, mask_id: str, x: float, y: float, w: float, h: float
    ) -> None:
        if self.busy:
            return
        mask = next((m for m in self.project.masks if m.id == mask_id), None)
        if mask:
            mask.x, mask.y, mask.width, mask.height = x, y, w, h
            if hasattr(self, "step3_panel"):
                self.step3_panel.update_mask_rect(mask_id, x, y, w, h)
            self.dirty = True
            self.setWindowTitle(self.windowTitle().rstrip(" *") + " *")

    def _delete_blur_mask(self, mask_id: str) -> None:
        if self.busy:
            return
        self.project.masks = [m for m in self.project.masks if m.id != mask_id]
        self.preview.video.set_masks(self.project.masks, time_ms=self.preview.player.position())
        if hasattr(self, "step3_panel"):
            self.step3_panel.set_masks(self.project.masks)
        self.dirty = True
        self._refresh()
        self.statusBar().showMessage("Đã xóa vùng xóa chữ.", 4000)

    def _on_chatgpt_translate_clicked(self) -> None:
        if not self.project or not self.project.video_path:
            QMessageBox.warning(self, "Chưa chọn video", "Vui lòng chọn video ở Bước 1 trước.")
            return
        if not (self.project.script or self.project.transcript):
            QMessageBox.warning(
                self,
                "Chưa có phụ đề gốc",
                "Vui lòng nhấn '▶ Bóc băng gốc' ở Bước 1 để tạo phụ đề trước khi gửi sang ChatGPT.",
            )
            return
        try:
            from vkdub.services.chatgpt_bridge import prepare_chatgpt_translation

            srt_path, prompt = prepare_chatgpt_translation(self.project)
            self.log(
                f"Đã mở ChatGPT và sao chép prompt dịch vào Clipboard. File SRT: {srt_path.name}"
            )
            QMessageBox.information(
                self,
                "Đã mở ChatGPT & Copy Prompt",
                f"1. Trình duyệt mặc định đã mở ChatGPT với tài khoản hiện tại của bạn.\n\n"
                f"2. Prompt dịch và nội dung SRT đã được tự động copy vào Clipboard (nhấn Ctrl+V để dán).\n\n"
                f"3. Thư mục chứa file '{srt_path.name}' đã được mở để bạn kéo thả trực tiếp vào chat.\n\n"
                f"Sau khi ChatGPT dịch xong, hãy tải file SRT về và nhấn nút '📥 Nạp file SRT đã dịch'.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi mở ChatGPT", f"Không thể chuẩn bị file SRT dịch: {exc}")

    def _on_import_chatgpt_srt_clicked(self) -> None:
        if not self.project:
            QMessageBox.warning(
                self, "Chưa có dự án", "Vui lòng chọn video trước khi nạp file SRT."
            )
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file SRT tiếng Việt đã dịch từ ChatGPT",
            str(self.project.output_directory or Path.home()),
            "Phụ đề SRT (*.srt);;Tất cả tệp (*.*)",
        )
        if not path:
            return
        try:
            from vkdub.services.chatgpt_bridge import import_translated_srt

            doc = import_translated_srt(self.project, Path(path))
            self.review.set_script(doc, self.project.is_approved)
            if hasattr(self.left, "lbl_review_status"):
                self.left.lbl_review_status.setText(
                    f"Đã nạp {len(doc.lines)} câu từ {Path(path).name}"
                )
                self.left.lbl_review_status.setStyleSheet(
                    "color: #34d399; font-weight: bold; font-size: 11px;"
                )
            self.dirty = True
            self._refresh()
            self.log(f"Đã nạp thành công {len(doc.lines)} câu phụ đề dịch từ {Path(path).name}.")
            QMessageBox.information(
                self,
                "Nạp phụ đề thành công",
                f"Đã nạp {len(doc.lines)} câu phụ đề tiếng Việt.\n"
                f"Vui lòng kiểm tra lại kịch bản ở khung bên phải và nhấn '✔ BƯỚC 3: CHỐT KỊCH BẢN' để tiếp tục.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi nạp phụ đề", f"Không thể nạp file SRT: {exc}")

    # -------------------------------------------------------------------------
    # H6 Step 4: Automated Pipeline Runner Integration
    # -------------------------------------------------------------------------
    def _start_pipeline_runner(self) -> None:
        if self.busy:
            return
        if not self.project.video_path or not self.project.video_path.is_file():
            QMessageBox.warning(
                self,
                "Chưa chọn video",
                "Vui lòng chọn video nguồn (Bước 01) trước khi bắt đầu xử lý tự động.",
            )
            return

        # Pre-flight check: Kiểm tra trước kết nối Extension và ChatGPT trước khi bóc băng
        if self.local_agent and not getattr(self, "_skip_browser_preflight", False):
            if not self.local_agent.status.browser_connected:
                ret = QMessageBox.warning(
                    self,
                    "Chưa kết nối Edge Extension",
                    "Tiện ích 'VK Dub Studio Bridge' trong Microsoft Edge chưa kết nối.\n\n"
                    "👉 Vui lòng mở Microsoft Edge và đảm bảo tiện ích đã được bật tại edge://extensions.\n\n"
                    "Bạn có muốn mở Edge ngay bây giờ không?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                )
                if ret == QMessageBox.StandardButton.Yes:
                    self.local_agent.open_browser("https://chatgpt.com")
                return

            if not self.local_agent.status.chatgpt_logged_in:
                ret = QMessageBox.warning(
                    self,
                    "Chưa đăng nhập ChatGPT",
                    "ChatGPT chưa được đăng nhập trong trình duyệt Edge.\n\n"
                    "👉 Vui lòng mở tab https://chatgpt.com trong Edge và đăng nhập tài khoản trước khi bắt đầu xử lý tự động.\n\n"
                    "Bạn có muốn mở trang ChatGPT ngay bây giờ không?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                )
                if ret == QMessageBox.StandardButton.Yes:
                    self.local_agent.open_browser("https://chatgpt.com")
                return

        # Đảm bảo có khung che phụ đề
        if not self.project.masks:
            self.add_blur_mask()

        # Lấy thông số giọng đọc và tốc độ từ Step 2
        voice_data = self.left.voice_combo.currentText()
        voice_name = "Ngọc Huyền"
        if "Ngọc Huyền" in voice_data:
            voice_name = "Ngọc Huyền"
        elif "Quỳnh Anh" in voice_data:
            voice_name = "Quỳnh Anh"

        speed_str = self.left.speed_combo.currentText().split(" ")[0]
        if not speed_str.endswith("x"):
            speed_str = f"{self.left.speed_combo.currentData()}x"

        self.busy = True
        self.left.step4_pipeline.set_running_state(True)
        if hasattr(self, "step4_panel"):
            self.step4_panel.set_running_state(True)
            self.step4_panel.update_overall("● Đang chạy", "#58a6ff", 10)
            self.switch_to_step(3)

        if hasattr(self, "diagnostics_drawer"):
            self.diagnostics_drawer.set_expanded(True)

        if hasattr(self, "top_bar") and not getattr(self.top_bar, "_timer_running", False):
            self.top_bar.start_timer()

        self.log(
            "🚀 Bắt đầu quy trình xử lý tự động 4 bước (Whisper → ChatGPT → Kịch bản → Vbee)..."
        )

        out_name = self.project.video_path.stem or "dubbing"
        output_dir = workspace_root() / "export" / out_name

        import importlib

        import vkdub.orchestrator.pipeline_runner as pr_mod
        importlib.reload(pr_mod)
        PipelineRunner = pr_mod.PipelineRunner

        auto_voice = (
            self.step4_panel.auto_voice_checked()
            if hasattr(self, "step4_panel")
            else False
        )

        self.pipeline_runner = PipelineRunner(
            project=self.project,
            local_agent=self.local_agent,
            output_dir=output_dir,
            voice_name=voice_name,
            speed=speed_str,
            parent=self,
            auto_voice=auto_voice,
        )

        self.pipeline_runner.state_changed.connect(self._on_pipeline_state_changed)
        self.pipeline_runner.substep_updated.connect(self._on_pipeline_substep_updated)
        self.pipeline_runner.artifact_ready.connect(self._on_pipeline_artifact_ready)
        self.pipeline_runner.log_emitted.connect(self.log)
        self.pipeline_runner.pipeline_completed.connect(self._on_pipeline_completed)
        self.pipeline_runner.pipeline_failed.connect(self._on_pipeline_failed)
        self.pipeline_runner.pipeline_cancelled.connect(self._on_pipeline_cancelled)

        self.pipeline_runner.start()
        self._refresh()

    def _start_vbee_generation(self) -> None:
        """Kích hoạt tạo giọng Vbee (Bước 4.4) sau khi người dùng chốt duyệt kịch bản tại Bước 5."""
        if self.busy:
            return
        if not self.project.video_path or not self.project.video_path.is_file():
            self.log("Chưa có video nguồn hợp lệ để tạo giọng đọc tự động.")
            return
        if not self.project.script or not self.project.script.lines:
            QMessageBox.warning(self, "Chưa có kịch bản", "Dự án chưa có câu thoại nào để đọc.")
            return

        voice_data = self.left.voice_combo.currentText()
        voice_name = "Ngọc Huyền"
        if "Ngọc Huyền" in voice_data:
            voice_name = "Ngọc Huyền"
        elif "Quỳnh Anh" in voice_data:
            voice_name = "Quỳnh Anh"

        speed_str = self.left.speed_combo.currentText().split(" ")[0]
        if not speed_str.endswith("x"):
            speed_str = f"{self.left.speed_combo.currentData()}x"

        self.busy = True
        self.left.step4_pipeline.set_running_state(True)
        if hasattr(self, "step4_panel"):
            self.step4_panel.set_running_state(True)
            self.step4_panel.update_overall("● Đang tạo giọng Vbee...", "#58a6ff", 80)
        if hasattr(self, "stepper"):
            self.stepper.update_step_summary(3, "●", "Đang tạo giọng...", "#58a6ff")

        if hasattr(self, "diagnostics_drawer"):
            self.diagnostics_drawer.set_expanded(True)

        self.log("🎙 Bắt đầu tạo giọng đọc Vbee cho kịch bản đã duyệt...")

        out_name = self.project.video_path.stem if self.project.video_path else "dubbing"
        output_dir = workspace_root() / "export" / out_name

        import importlib
        import vkdub.orchestrator.pipeline_runner as pr_mod
        importlib.reload(pr_mod)
        PipelineRunner = pr_mod.PipelineRunner

        self.pipeline_runner = PipelineRunner(
            project=self.project,
            local_agent=self.local_agent,
            output_dir=output_dir,
            voice_name=voice_name,
            speed=speed_str,
            parent=self,
            auto_voice=True,
            target_step="4.4",
        )

        self.pipeline_runner.state_changed.connect(self._on_pipeline_state_changed)
        self.pipeline_runner.substep_updated.connect(self._on_pipeline_substep_updated)
        self.pipeline_runner.artifact_ready.connect(self._on_pipeline_artifact_ready)
        self.pipeline_runner.log_emitted.connect(self.log)
        self.pipeline_runner.pipeline_completed.connect(self._on_pipeline_completed)
        self.pipeline_runner.pipeline_failed.connect(self._on_pipeline_failed)
        self.pipeline_runner.pipeline_cancelled.connect(self._on_pipeline_cancelled)

        self.pipeline_runner.start()
        self._refresh()

    def _cancel_pipeline_runner(self) -> None:
        if self.pipeline_runner:
            self.log("⏹ Đang yêu cầu dừng quy trình xử lý tự động...")
            self.pipeline_runner.cancel()
            self.busy = False
            self.left.step4_pipeline.set_running_state(False)
            if hasattr(self, "step4_panel"):
                self.step4_panel.set_running_state(False)
                self.step4_panel.update_overall("⏹ Đã dừng", "#d29922")
            self._refresh()

    def _retry_pipeline_step(self, step_id: str) -> None:
        if self.busy:
            return
        self.log(f"🔄 Đang thực hiện lại bước {step_id}...")
        if self.pipeline_runner:
            out_dir = self.pipeline_runner.output_dir
            if step_id == "4.1":
                orig = out_dir / "original.srt"
                if orig.exists():
                    orig.unlink()
            elif step_id == "4.2":
                trans = out_dir / "translated.srt"
                if trans.exists():
                    trans.unlink()
            elif step_id in ("4.3", "4.4"):
                m_raw = out_dir / "vbee_master_raw.mp3"
                m_tl = out_dir / "master_narration_timeline.mp3"
                if m_raw.exists():
                    m_raw.unlink()
                if m_tl.exists():
                    m_tl.unlink()
        self._start_pipeline_runner()

    def _on_import_chatgpt_srt_clicked(self) -> None:
        """Cho phép người dùng nạp trực tiếp file phụ đề SRT đã dịch vào bước 4.2."""
        if not self.project.video_path:
            QMessageBox.warning(
                self,
                "Chưa chọn video",
                "Vui lòng chọn video nguồn (Bước 01) trước khi nạp file phụ đề dịch.",
            )
            return

        out_name = self.project.video_path.stem or "dubbing"
        output_dir = workspace_root() / "export" / out_name
        output_dir.mkdir(parents=True, exist_ok=True)

        orig_srt_path = output_dir / "original.srt"
        if not orig_srt_path.is_file():
            QMessageBox.warning(
                self,
                "Chưa có phụ đề gốc",
                "Chưa tìm thấy file phụ đề gốc (original.srt) để đối soát khớp timecode.\n\n"
                "👉 Vui lòng nhấn 'BẮT ĐẦU XỬ LÝ TOÀN BỘ' để hoàn thành bước 4.1 Bóc băng trước khi nạp file dịch.",
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file phụ đề SRT đã dịch",
            str(output_dir),
            "SubRip Subtitle (*.srt);;Tất cả các tệp (*.*)",
        )
        if not file_path:
            return

        try:
            chosen_path = Path(file_path)
            raw_translated = chosen_path.read_text(encoding="utf-8", errors="replace")
            raw_original = orig_srt_path.read_text(encoding="utf-8", errors="replace")

            from vkdub.services.srt_validator import validate_and_repair_srt

            val_res = validate_and_repair_srt(
                raw_original, raw_translated, auto_repair_timecodes=True
            )
            if not val_res.is_valid:
                errors_str = "\n• ".join(val_res.errors)
                QMessageBox.warning(
                    self,
                    "Phụ đề dịch không hợp lệ",
                    f"File phụ đề dịch không khớp với phụ đề gốc:\n\n• {errors_str}\n\n"
                    "Vui lòng kiểm tra lại số lượng câu thoại trong file.",
                )
                return

            final_content = val_res.repaired_srt or raw_translated
            dest_trans_path = output_dir / "translated.srt"
            dest_trans_path.write_text(final_content, encoding="utf-8")

            self.log(
                f"✓ Đã nạp thành công file phụ đề dịch: {chosen_path.name} ({val_res.cue_count} câu)"
            )
            self.notify_success(
                "Nạp phụ đề dịch thành công",
                f"Đã khớp {val_res.cue_count} câu thoại với file gốc.",
            )

            if hasattr(self, "step4_panel"):
                self.step4_panel.update_substep(
                    "4.2",
                    SubstepStatus.SUCCESS,
                    100,
                    f"Đã nạp file dịch ({val_res.cue_count} câu)",
                    artifact=dest_trans_path,
                )
            self._on_pipeline_artifact_ready("translated_srt", dest_trans_path)

        except Exception as exc:
            self._error(f"Không thể đọc file SRT dịch: {exc}")

    def _on_health_check_clicked(self) -> None:
        self.log("🔍 Đang gửi yêu cầu làm mới và kiểm tra trạng thái tới Edge Extension...")
        if self.local_agent:
            self.local_agent.reload_extension()
            self.local_agent.request_status()
        self.statusBar().showMessage("Đang kiểm tra kết nối Edge, ChatGPT và Vbee...", 3000)

    def _on_pipeline_state_changed(self, state: PipelineState, message: str) -> None:
        self.log(f"[{state.value}] {message}")
        self.statusBar().showMessage(message, 5000)

    def _on_pipeline_substep_updated(
        self,
        step_id: str,
        status: SubstepStatus,
        progress: int,
        message: str,
        artifact: Path | None = None,
        duration_s: float | None = None,
    ) -> None:
        error = None
        if self.pipeline_runner:
            for s in self.pipeline_runner.substeps:
                if s.id == step_id:
                    if duration_s is None:
                        duration_s = s.duration_s
                    if artifact is None:
                        artifact = s.artifact_path
                    error = s.error
                    break
        self.left.step4_pipeline.update_substep(
            step_id=step_id,
            status=status,
            progress=progress,
            message=message,
            artifact=artifact,
            error=error,
            duration_s=duration_s,
        )
        if hasattr(self, "step4_panel"):
            self.step4_panel.update_substep(
                step_id=step_id,
                status=status,
                progress=progress,
                message=message,
                artifact=artifact,
                error=error,
                duration_s=duration_s,
            )
            # Calculate approx overall progress (0-100)
            step_weights = {"4.1": 25, "4.2": 50, "4.3": 70, "4.4": 100}
            base = {"4.1": 0, "4.2": 25, "4.3": 50, "4.4": 70}.get(step_id, 0)
            w = step_weights.get(step_id, 25) - base
            overall_pct = base + int(progress * w / 100)
            self.step4_panel.update_overall("● Đang chạy", "#58a6ff", overall_pct)
        if hasattr(self, "stepper"):
            self.stepper.update_step_summary(3, "●", "Đang chạy...", "#58a6ff")

    def _on_pipeline_artifact_ready(self, key: str, path: Path) -> None:
        self.log(f"✓ Đã tạo artifact [{key}]: {path.name}")
        if key == "translated_srt":
            self.review_controller.bind_project()
        elif key == "master_audio":
            self.project.master_voice_path = path

    def _on_pipeline_completed(self, artifacts: Any) -> None:
        self.busy = False
        self.left.step4_pipeline.set_running_state(False)
        if hasattr(self, "step4_panel"):
            self.step4_panel.set_running_state(False)

        has_voice = bool(
            artifacts.timeline_master_audio and Path(artifacts.timeline_master_audio).is_file()
        )
        if has_voice:
            self.project.master_voice_path = artifacts.timeline_master_audio
            if self.project.script:
                self.project.is_approved = True
                self.project.approved_revision_hash = self.project.revision_hash
            self.left.step4_pipeline.overall_badge.setText("✔ Hoàn thành (4/4)")
            self.left.step4_pipeline.overall_badge.setStyleSheet("color: #3fb950; font-weight: bold;")
            self.left.lbl_review_status.setText(
                "✓ Đã hoàn tất! Kịch bản và audio timeline đã sẵn sàng."
            )
            self.left.lbl_review_status.setStyleSheet("color: #3fb950; font-weight: bold;")
            if hasattr(self, "step4_panel"):
                self.step4_panel.update_overall("✔ Hoàn thành (4/4)", "#3fb950", 100)
                self.step4_panel.btn_continue.setEnabled(True)
            if hasattr(self, "stepper"):
                self.stepper.update_step_summary(3, "✓", "Hoàn tất (4/4)", "#3fb950")
                line_count = len(self.project.script.lines) if self.project.script else 0
                self.stepper.update_step_summary(4, "✓", f"Sẵn sàng xuất ({line_count} câu)", "#3fb950")

            self.review_controller.bind_project()
            self.review_controller.refresh()
            self._refresh()
            self.log("🎉 Quy trình xử lý tự động hoàn tất! Đã có voice Vbee timeline.")
            self.notify_success("Xử lý hoàn tất!", "Kịch bản và audio timeline đã sẵn sàng. Chuyển sang xuất video / CapCut.")

            if hasattr(self, "switch_to_step"):
                self.switch_to_step(4)  # Chuyển ngay sang Bước 05 để xem kịch bản và xuất CapCut
        else:
            # Tạm dừng ở Bước 4.3 để người dùng duyệt kịch bản
            self.left.step4_pipeline.overall_badge.setText("✔ Đã dịch (3/4)")
            self.left.step4_pipeline.overall_badge.setStyleSheet("color: #58a6ff; font-weight: bold;")
            self.left.lbl_review_status.setText(
                "⏳ Đã dịch xong. Vui lòng kiểm tra và duyệt kịch bản tại Bước 05."
            )
            self.left.lbl_review_status.setStyleSheet("color: #d29922; font-weight: bold;")
            if hasattr(self, "step4_panel"):
                self.step4_panel.update_overall("✔ Đã dịch (3/4)", "#58a6ff", 75)
                self.step4_panel.btn_continue.setEnabled(True)
            if hasattr(self, "stepper"):
                self.stepper.update_step_summary(3, "✓", "Đã dịch (3/4)", "#3fb950")
                line_count = len(self.project.script.lines) if self.project.script else 0
                self.stepper.update_step_summary(4, "●", f"{line_count} câu (Cần duyệt)", "#d29922")

            self.review_controller.bind_project()
            self._refresh()
            if hasattr(self, "switch_to_step"):
                self.switch_to_step(4)  # Chuyển sang Bước 5 để người dùng xem kịch bản

            self.log("📋 Đã dịch xong kịch bản (3/4). Dừng lại để người dùng kiểm tra và chốt kịch bản!")
            QMessageBox.information(
                self,
                "Dịch kịch bản hoàn tất — Chờ duyệt",
                "ChatGPT đã dịch xong phụ đề (3/4 bước).\n\n"
                "👉 Hệ thống tạm dừng để bạn kiểm tra và chỉnh sửa nội dung dịch ở Bước 05 (cột bên phải).\n\n"
                "Khi đã ưng ý, hãy nhấn nút:\n"
                "   [ ✔ BƯỚC 5: CHỐT KỊCH BẢN & TẠO GIỌNG (VBEE) ]\n"
                "để hệ thống tự động gửi kịch bản đã chỉnh sửa sang Vbee tạo giọng đọc!",
            )

    def _on_pipeline_failed(self, short_err: str, trace: str) -> None:
        self.busy = False
        self.left.step4_pipeline.set_running_state(False)
        self.left.step4_pipeline.overall_badge.setText("✖ Thất bại")
        self.left.step4_pipeline.overall_badge.setStyleSheet("color: #f85149; font-weight: bold;")
        if hasattr(self, "step4_panel"):
            self.step4_panel.set_running_state(False)
            self.step4_panel.update_overall("✖ Thất bại", "#f85149")
        if hasattr(self, "stepper"):
            self.stepper.update_step_summary(3, "✖", "Lỗi xử lý", "#f85149")
        self._refresh()
        self.log(f"✖ Lỗi quy trình xử lý tự động: {short_err}")
        QMessageBox.critical(
            self,
            "Lỗi xử lý tự động",
            f"Quy trình tự động gặp lỗi:\n\n{short_err}\n\nBạn có thể kiểm tra log chi tiết (F12) hoặc bấm nút 'Thử lại' ở bước gặp sự cố.",
        )

    def _on_pipeline_cancelled(self) -> None:
        self.busy = False
        self.left.step4_pipeline.set_running_state(False)
        self.left.step4_pipeline.overall_badge.setText("⏹ Đã hủy")
        self.left.step4_pipeline.overall_badge.setStyleSheet("color: #d29922; font-weight: bold;")
        if hasattr(self, "step4_panel"):
            self.step4_panel.set_running_state(False)
            self.step4_panel.update_overall("⏹ Đã hủy", "#d29922")
        if hasattr(self, "stepper"):
            self.stepper.update_step_summary(3, "⏹", "Đã hủy", "#d29922")
        self._refresh()
        self.log("⏹ Đã dừng quy trình xử lý tự động theo yêu cầu.")

    def _on_approve_script_clicked(self) -> None:
        if not self.project.script or not self.project.script.lines:
            QMessageBox.warning(self, "Chưa có kịch bản", "Chưa có kịch bản phụ đề dịch để chốt.")
            return
        self.review.review_checkbox.setChecked(True)
        ok = self.review_controller.approve()
        if ok:
            self._refresh()
            if self.project.voice_ready:
                self.log("Đã chốt duyệt kịch bản thành công! Sẵn sàng xuất CapCut.")
                QMessageBox.information(
                    self,
                    "Đã chốt kịch bản",
                    "Kịch bản dịch đã được duyệt thành công!\n\n"
                    "Tiếp theo: Nhấn '🎬 XUẤT PROJECT CAPCUT' để mở dự án CapCut với video, phụ đề và voice.",
                )
            else:
                self.log("Đã chốt kịch bản. Hệ thống đang chuyển sang Vbee để tạo giọng đọc...")
        else:
            QMessageBox.warning(
                self, "Không thể duyệt", "Vui lòng kiểm tra lại lỗi câu kịch bản trước khi duyệt."
            )

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
        formatted = f"{datetime.now():%H:%M:%S}  +{elapsed // 60:02}:{elapsed % 60:02}  {message}"
        self.left.logs.appendPlainText(formatted)
        self.left.activity_header.setText(f"● ĐANG THEO DÕI  •  {message[:34]}")
        self.left.logs.moveCursor(QTextCursor.MoveOperation.End)
        self.left.logs.ensureCursorVisible()
        if hasattr(self, "diagnostics_drawer"):
            self.diagnostics_drawer.append_log(formatted)
        self.statusBar().showMessage(message, 10000)
        logging.getLogger("vkdub").info(message)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "toast_manager"):
            self.toast_manager.reposition()

    def notify_success(self, title: str, message: str = "") -> None:
        if hasattr(self, "toast_manager"):
            self.toast_manager.show_toast(title, message, ToastType.SUCCESS)

    def notify_info(self, title: str, message: str = "") -> None:
        if hasattr(self, "toast_manager"):
            self.toast_manager.show_toast(title, message, ToastType.INFO)

    def notify_warning(self, title: str, message: str = "") -> None:
        if hasattr(self, "toast_manager"):
            self.toast_manager.show_toast(title, message, ToastType.WARNING)

    def notify_error(self, title: str, message: str = "") -> None:
        if hasattr(self, "toast_manager"):
            self.toast_manager.show_toast(title, message, ToastType.ERROR)

    def _error(self, message: str) -> None:
        self.log(message)
        self.notify_error("Lỗi", message)
        QMessageBox.warning(self, "VK Dub Studio", message)

    def _refresh(self) -> None:
        filename = self.project_file.name if self.project_file else "Project mới"
        self.setWindowTitle(
            f"{APP_BRANDING}  |  v{__version__}  |  {filename}{' *' if self.dirty else ''}"
        )

        # Update TopBar project name & status
        if hasattr(self, "top_bar"):
            self.top_bar.set_project_name(filename, self.dirty)

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

        # Update Step 1 Source info
        if hasattr(self, "step1_panel"):
            metadata = self.video_metadata if self.project.video_path else None
            self.step1_panel.set_video_info(self.project.video_path, metadata)

        # Update Stepper 5-stage summaries
        if hasattr(self, "stepper"):
            # 01 Source
            if self.project.video_path:
                self.stepper.update_step_summary(
                    0, "✓", self.project.video_path.name, "#3fb950"
                )
            else:
                self.stepper.update_step_summary(0, "○", "Chưa chọn video", "#8b949e")

            # 02 Voice
            if hasattr(self, "step2_panel"):
                self.stepper.update_step_summary(
                    1, "✓", self.step2_panel.voice_summary(), "#3fb950"
                )

            # 03 Blur Regions
            if hasattr(self, "step3_panel"):
                self.stepper.update_step_summary(
                    2,
                    "✓" if self.project.masks else "○",
                    self.step3_panel.regions_summary(),
                    "#3fb950" if self.project.masks else "#8b949e",
                )

            # 04 Automation
            if hasattr(self, "step4_panel"):
                st4 = self.step4_panel.automation_summary()
                ico = "✓" if "Hoàn tất" in st4 else "●" if "Đang chạy" in st4 else "○"
                col = (
                    "#3fb950"
                    if "Hoàn tất" in st4
                    else "#58a6ff"
                    if "Đang chạy" in st4
                    else "#8b949e"
                )
                self.stepper.update_step_summary(3, ico, st4, col)

            # 05 Review & Export
            if self.project.is_approved:
                self.stepper.update_step_summary(4, "✓", "Đã duyệt kịch bản", "#3fb950")
            elif self.project.script and self.project.script.lines:
                self.stepper.update_step_summary(
                    4, "○", f"Chờ duyệt ({len(self.project.script.lines)} câu)", "#fbbf24"
                )
            else:
                self.stepper.update_step_summary(4, "○", "Chờ kịch bản", "#8b949e")

        busy = self.busy
        enabled = not busy
        self.left.process_button.setEnabled(enabled and self.tools_ready)
        self.left.stop_button.setEnabled(busy)
        self.left.import_button.setEnabled(enabled)
        self.left.load_button.setEnabled(enabled)
        self.left.save_button.setEnabled(not self.busy)
        self.left.output_button.setEnabled(not self.busy)
        self.left.detect_button.setEnabled(enabled)
        has_video = bool(self.project.video_path)
        can_run_pipeline = has_video and not busy
        if hasattr(self.left, "step4_pipeline"):
            if not self.busy:
                self.left.step4_pipeline.btn_primary.setEnabled(can_run_pipeline)
                if not has_video:
                    self.left.step4_pipeline.btn_primary.setToolTip(
                        "Vui lòng chọn video nguồn (Bước 01) trước khi bắt đầu."
                    )
                else:
                    self.left.step4_pipeline.btn_primary.setToolTip(
                        "Bắt đầu quy trình tự động 4 bước: Whisper → ChatGPT → Kịch bản → Vbee"
                    )

        if hasattr(self, "step4_panel"):
            if not self.busy:
                self.step4_panel.btn_start.setEnabled(can_run_pipeline)

        can_approve = bool(self.project.script and self.project.script.lines) and not busy
        self.left.btn_approve_script.setEnabled(can_approve)
        if hasattr(self, "review"):
            self.review.approve_button.setEnabled(can_approve)

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

        # Sync Step 5 CapCut & Export buttons
        if hasattr(self, "review") and hasattr(self.review, "export_video_button"):
            has_ffmpeg = bool(self.tools.paths.get("ffmpeg"))
            has_ffprobe = bool(self.tools.paths.get("ffprobe"))
            tools_ok = has_ffmpeg and has_ffprobe
            self.review.export_video_button.setEnabled(
                has_ffmpeg and not self.busy and self.project.voice_ready
            )
            self.review.export_capcut_button.setEnabled(
                tools_ok and not self.busy and self.project.voice_ready
            )
            settings = load_app_settings()
            dest = settings.capcut_draft_root
            if dest:
                p_dest = Path(dest)
                self.review.capcut_dest_lbl.setText(
                    f"📁 CapCut: {p_dest.name if p_dest.name else dest}"
                )
                self.review.capcut_dest_lbl.setToolTip(dest)
            else:
                self.review.capcut_dest_lbl.setText("📁 CapCut Draft Root: Chưa kết nối")

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
                "Khung khu vực phụ đề đã bật: Bạn có thể kéo di chuyển hoặc kéo góc "
                "để khớp với phụ đề trên video.",
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
        if hasattr(self, "step3_panel"):
            self.step3_panel.set_masks(self.project.masks, default_mask.id)
        if hasattr(self, "step4_panel"):
            self.step4_panel.reset_state()
        if hasattr(self.left, "step4_pipeline") and hasattr(self.left.step4_pipeline, "reset_state"):
            self.left.step4_pipeline.reset_state()
        if hasattr(self, "stepper"):
            self.stepper.update_step_summary(0, "✓", path.name, "#3fb950")
            self.stepper.update_step_summary(1, "○", "Chưa đặt", "#8b949e")
            self.stepper.update_step_summary(2, "✓", "Đã che phụ đề", "#3fb950")
            self.stepper.update_step_summary(3, "○", "Sẵn sàng", "#8b949e")
            self.stepper.update_step_summary(4, "○", "Chờ kịch bản", "#8b949e")
            self.stepper.update_step_summary(5, "○", "Chưa sẵn sàng", "#8b949e")

        self.review_controller.bind_project()
        self.project_file = None
        self.dirty = True
        self.video_metadata = metadata
        self.preview.load(path)
        if metadata:
            self.preview.show_metadata(metadata)
        if hasattr(self, "top_bar"):
            self.top_bar.start_timer()
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
            self.video_metadata = metadata
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
            str(self.project.output_directory or Path.home()),
        )
        if path:
            self.set_output_directory(Path(path))

    def set_output_directory(self, path: Path) -> bool:
        path = path.resolve()
        if not path.is_dir():
            self._error("Thư mục đầu ra không tồn tại.")
            return False
        self.project.output_directory = path
        self.dirty = True
        self._refresh()
        self.log(f"Đã đổi thư mục đầu ra: {path}")
        return True

    def save(self) -> bool:
        if self.busy:
            return False
        if self.project_file is None:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Lưu project",
                str(Path.cwd() / "project.vkdub"),
                "VK Dub project (*.vkdub)",
            )
            if not path:
                return False
            path = Path(path)
            if path.suffix.lower() != ".vkdub":
                path = path.with_suffix(".vkdub")
            if (
                not self.dirty
                or self.project_file != path
            ):
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
        else:
            path = self.project_file
            if not path.is_file():
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
        self.notify_success("Đã lưu dự án", f"Lưu thành công: {path.name}")
        return True

    def new_project(self) -> None:
        """Khởi tạo một dự án mới hoàn toàn."""
        if self.busy:
            return
        if not self._confirm_discard():
            return
        self.project = Project()
        self.project_file = None
        self.dirty = False
        self.video_metadata = None
        self._script_play_end_ms = None
        self.preview.load(None)
        self.preview.video.set_masks([])
        self.preview.video.interactive_mask_mode = False
        if hasattr(self, "step1_panel"):
            self.step1_panel.set_video_info(None, None)
            self.step1_panel.url_input.clear()
        if hasattr(self, "step3_panel"):
            self.step3_panel.set_masks([])
        if hasattr(self, "step4_panel"):
            self.step4_panel.reset_state()
        if hasattr(self.left, "step4_pipeline") and hasattr(self.left.step4_pipeline, "reset_state"):
            self.left.step4_pipeline.reset_state()
        if hasattr(self, "top_bar"):
            self.top_bar.reset_timer()
        self.review_controller.bind_project()
        self.switch_to_step(0)
        self._refresh()
        self.log("✨ Đã tạo dự án mới.")
        self.notify_success("Dự án mới", "Đã khởi tạo dự án mới thành công.")

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
        self._sync_project_voice_controls()
        self.project_file = path.resolve()
        self.dirty = False
        available = project.video_path is not None and project.video_path.is_file()
        self.preview.load(project.video_path if available else None)
        self.preview.video.set_masks(project.masks)
        if hasattr(self, "step3_panel"):
            self.step3_panel.set_masks(project.masks)
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

    def _sync_project_voice_controls(self) -> None:
        """Restore the saved project's Vbee voice and speed without mutating it."""
        voice_combo = self.left.voice_combo
        speed_combo = self.left.speed_combo

        voice_combo.blockSignals(True)
        try:
            voice_index = voice_combo.findData(self.project.voice.voice_id)
            if voice_index < 0:
                voice_index = voice_combo.findText(self.project.voice.display_name)
            if voice_index >= 0:
                voice_combo.setCurrentIndex(voice_index)
        finally:
            voice_combo.blockSignals(False)

        speed_combo.blockSignals(True)
        try:
            speed_index = speed_combo.findData(float(self.project.voice.speed))
            if speed_index >= 0:
                speed_combo.setCurrentIndex(speed_index)
        finally:
            speed_combo.blockSignals(False)

        if hasattr(self, "step2_panel"):
            self.step2_panel.voice_combo.blockSignals(True)
            try:
                v_idx = self.step2_panel.voice_combo.findData(self.project.voice.voice_id)
                if v_idx < 0:
                    v_idx = self.step2_panel.voice_combo.findText(self.project.voice.display_name)
                if v_idx >= 0:
                    self.step2_panel.voice_combo.setCurrentIndex(v_idx)
            finally:
                self.step2_panel.voice_combo.blockSignals(False)

            self.step2_panel.speed_combo.blockSignals(True)
            try:
                s_idx = self.step2_panel.speed_combo.findData(float(self.project.voice.speed))
                if s_idx >= 0:
                    self.step2_panel.speed_combo.setCurrentIndex(s_idx)
            finally:
                self.step2_panel.speed_combo.blockSignals(False)

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
        if (
            hasattr(self, "pipeline_runner")
            and self.pipeline_runner
            and self.pipeline_runner.isRunning()
        ):
            answer = QMessageBox.question(
                self,
                "Dừng quy trình tự động?",
                "Quy trình xử lý tự động đang chạy. Dừng rồi đóng ứng dụng?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.pipeline_runner.cancel()
                self.pipeline_runner.wait(2000)
            else:
                event.ignore()
                return
        if not self._confirm_discard():
            event.ignore()
            return
        if hasattr(self, "local_agent") and self.local_agent:
            try:
                self.local_agent.stop()
            except Exception:
                pass
        self.preview.player.stop()
        self.autosave_timer.stop()
        self.recovery_timer.stop()
        self.tts.player.stop()
        self.tools.shutdown()
        clear_recovery_state()
        event.accept()
