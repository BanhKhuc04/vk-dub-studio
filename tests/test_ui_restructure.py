import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from vkdub.domain.project import Project
from vkdub.domain.transcript import SubtitleSegment, Transcript
from vkdub.domain.translation import Translation, source_digest
from vkdub.media.ffprobe import VideoMetadata
from vkdub.orchestrator.pipeline_state import SubstepStatus
from vkdub.ui.diagnostics_drawer import DiagnosticsDrawer
from vkdub.ui.main_window import MainWindow
from vkdub.ui.panels.step1_source_panel import Step1SourcePanel
from vkdub.ui.panels.step2_voice_panel import Step2VoicePanel
from vkdub.ui.panels.step3_blur_panel import Step3BlurPanel
from vkdub.ui.panels.step4_automation_panel import Step4AutomationPanel
from vkdub.ui.script_review_panel import ScriptReviewPanel
from vkdub.ui.stepper_sidebar import WorkflowStepper
from vkdub.ui.top_bar import TopBar
from vkdub.ui.video_preview import VideoPreview


@pytest.fixture
def window(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("vkdub.media.process.find_tool", lambda _: None)
    monkeypatch.setattr("vkdub.services.credential_service.CredentialStore.get", lambda _: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.No)
    monkeypatch.setattr(QMessageBox, "information", lambda *a: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: None)

    w = MainWindow()
    qtbot.addWidget(w)
    w.show()
    qtbot.waitUntil(lambda: w.tools_ready)
    yield w
    if w.translation.job:
        w.translation.stop()
        qtbot.waitUntil(lambda: w.translation.job is None)
    w.dirty = False
    w.close()


def test_main_layout_structure(window):
    """Verify 3-column layout + TopBar + Bottom Diagnostics Drawer."""
    assert isinstance(window.top_bar, TopBar)
    assert isinstance(window.stepper, WorkflowStepper)
    assert isinstance(window.preview, VideoPreview)
    assert isinstance(window.diagnostics_drawer, DiagnosticsDrawer)

    # 5 step panels in QStackedWidget
    assert window.step_stack.count() == 5
    assert isinstance(window.step_stack.widget(0), Step1SourcePanel)
    assert isinstance(window.step_stack.widget(1), Step2VoicePanel)
    assert isinstance(window.step_stack.widget(2), Step3BlurPanel)
    assert isinstance(window.step_stack.widget(3), Step4AutomationPanel)
    assert isinstance(window.step_stack.widget(4), ScriptReviewPanel)


def test_top_bar_components(window):
    """Verify TopBar elements: branding, project filename, Edge/ChatGPT/Vbee badges, settings."""
    assert "VK Dub Studio" in window.top_bar.lbl_title.text()
    assert "Project mới" in window.top_bar.lbl_project_name.text()
    assert window.top_bar.badge_edge.text().endswith("Edge")
    assert window.top_bar.badge_chatgpt.text().endswith("ChatGPT")
    assert window.top_bar.badge_vbee.text().endswith("Vbee")
    assert window.top_bar.btn_settings.isVisible()


def test_diagnostics_drawer_collapsible(window, qtbot):
    """Verify bottom drawer starts collapsed and toggles expansion."""
    drawer = window.diagnostics_drawer
    assert not drawer.is_expanded
    assert drawer.content_frame.isHidden()

    # Toggle open
    qtbot.mouseClick(drawer.header_btn, Qt.MouseButton.LeftButton)
    assert drawer.is_expanded
    assert not drawer.content_frame.isHidden()

    # Append log message
    window.log("Test log entry for diagnostics drawer")
    assert "Test log entry" in drawer.log_edit.toPlainText()

    # Toggle closed
    qtbot.mouseClick(drawer.header_btn, Qt.MouseButton.LeftButton)
    assert not drawer.is_expanded
    assert drawer.content_frame.isHidden()


def test_stepper_navigation(window, qtbot):
    """Verify clicking stepper cards switches the active step on the right."""
    # Step 0: Source
    assert window.step_stack.currentIndex() == 0

    # Step 1: Voice
    window.switch_to_step(1)
    assert window.step_stack.currentIndex() == 1
    assert window.stepper.current_step == 1

    # Step 2: Blur
    window.switch_to_step(2)
    assert window.step_stack.currentIndex() == 2
    assert window.stepper.current_step == 2

    # Step 3: Automation
    window.switch_to_step(3)
    assert window.step_stack.currentIndex() == 3
    assert window.stepper.current_step == 3

    # Step 4: Review
    window.switch_to_step(4)
    assert window.step_stack.currentIndex() == 4
    assert window.stepper.current_step == 4


def test_step1_source_panel_controls(window):
    """Verify Step 1 contextual panel controls."""
    panel = window.step1_panel
    assert panel.url_input is not None
    assert panel.btn_download is not None
    assert panel.btn_choose_video is not None
    assert panel.btn_continue is not None
    # No video initially
    assert not panel.btn_continue.isEnabled()


def test_imported_video_updates_source_mask_and_duration(window, tmp_path):
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"placeholder")
    metadata = VideoMetadata(63.646, 960, 720, 30.0, "hevc", "aac", 43_300_000)

    window._apply_import(source, metadata)

    assert window.stepper.step_items[0].summary_label.text() == "sample.mp4"
    assert window.stepper.step_items[2].summary_label.text() == "1 vùng che mờ"
    assert window.step1_panel.lbl_resolution_dur.text().endswith("⏱ 01:03")
    assert window.preview.time_label.text().endswith("00:01:03")


def test_step2_voice_panel_defaults(window):
    """Verify Step 2 contextual panel defaults to Ngoc Huyen and 1.1x."""
    panel = window.step2_panel
    assert "Ngọc Huyền" in panel.voice_combo.currentText()
    assert "1.1x" in panel.speed_combo.currentText()
    assert panel.btn_listen is not None
    assert panel.btn_back is not None
    assert panel.btn_continue is not None
    assert "Ngọc Huyền" in panel.voice_summary()
    assert "1.1x" in panel.voice_summary()


def test_step3_blur_inspector(window, tmp_path):
    """Verify Step 3 Blur Inspector adds, selects, and adjusts regions."""
    window.project.video_path = tmp_path / "video.mp4"
    window.switch_to_step(2)
    panel = window.step3_panel
    assert panel.btn_add_region is not None
    assert panel.btn_delete is not None

    # Add a blur region
    window.add_blur_zone()
    assert len(window.project.masks) >= 1
    assert panel.regions_list.count() >= 1

    # Select region and edit coordinates
    panel.regions_list.setCurrentRow(0)
    panel.spin_w.setValue(45)
    panel.spin_h.setValue(20)
    assert window.project.masks[0].width == pytest.approx(0.45, 0.01)
    assert window.project.masks[0].height == pytest.approx(0.20, 0.01)


def test_step4_automation_console(window):
    """Verify Step 4 Automation Console substeps and error expansion."""
    window.switch_to_step(3)
    panel = window.step4_panel
    assert "4.1" in panel.substep_cards
    assert "4.2" in panel.substep_cards
    assert "4.3" in panel.substep_cards
    assert "4.4" in panel.substep_cards

    # Simulate substep 4.1 running
    panel.update_substep(
        step_id="4.1",
        status=SubstepStatus.RUNNING,
        progress=50,
        message="Đang bóc băng âm thanh...",
    )
    card41 = panel.substep_cards["4.1"]
    assert card41.status_badge.text() == "RUNNING"
    assert "Đang bóc băng" in card41.msg.text()

    # Simulate substep 4.2 success
    panel.update_substep(
        step_id="4.2",
        status=SubstepStatus.SUCCESS,
        progress=100,
        message="translated.srt",
        duration_s=19.8,
    )
    card42 = panel.substep_cards["4.2"]
    assert card42.status_badge.text() == "SUCCESS"
    assert "19.8s" in card42.lbl_duration.text()

    # Simulate substep 4.3 failure with traceback
    panel.update_substep(
        step_id="4.3",
        status=SubstepStatus.FAILED,
        progress=0,
        message="Lỗi định dạng kịch bản",
        error="Traceback (most recent call last):\n  ValueError: Invalid timeline alignment",
    )
    card43 = panel.substep_cards["4.3"]
    assert card43.status_badge.text() == "FAILED"
    assert "Lỗi định dạng kịch bản" in card43.msg.text()
    assert card43.error_btn.isVisible()


def test_step5_review_and_export_outputs(window, tmp_path):
    """Verify Step 5 Review header, More menu, and primary export buttons."""
    source = Transcript(
        (SubtitleSegment(1, 1, 4, "Hello world"), SubtitleSegment(2, 5, 9, "Thank you")),
        "en",
        "en",
        11,
        "tiny",
        "cpu",
        "a" * 64,
        "b" * 64,
    )
    window.project = Project(
        video_path=tmp_path / "source.mp4",
        transcript=source,
        translation=Translation(source_digest(source), ("Xin chào thế giới", "Cảm ơn bạn")),
    )
    window.review_controller.bind_project()
    window._refresh()

    assert window.step_stack.currentIndex() == 4
    review = window.review
    assert "KỊCH BẢN" in review.findChildren(object)[0].__class__.__name__ or review.summary.text().startswith("2 câu")
    assert review.btn_search_toggle.isVisible()
    assert review.buttons["add"].isVisible()
    assert review.more_button.isVisible()

    # Primary export outputs at bottom
    assert review.export_video_button.isVisible()
    assert review.export_capcut_button.isVisible()
