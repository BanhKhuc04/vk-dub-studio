from uuid import uuid4

from PySide6.QtWidgets import QMessageBox

from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.services.credential_service import CredentialStore
from vkdub.ui.left_config_panel import LeftConfigPanel
from vkdub.ui.main_window import MainWindow
from vkdub.ui.settings_dialog import SettingsDialog


def test_left_config_panel_v2(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path / "data"))
    panel = LeftConfigPanel()
    qtbot.addWidget(panel)

    # Check CapCut destination display
    assert panel.capcut_dest_lbl is not None

    # Check dynamic CTA texts
    panel.update_cta_for_state("IDLE", has_video=False)
    assert panel.process_button.text().replace("&&", "&") == "📂 HÃY CHỌN VIDEO"
    assert panel.process_button.isEnabled() is False

    panel.update_cta_for_state("IDLE", has_video=True)
    assert panel.process_button.text().replace("&&", "&") == "🚀 BẮT ĐẦU XỬ LÝ"
    assert panel.process_button.isEnabled() is True

    panel.update_cta_for_state("TRANSCRIBED", has_video=True)
    assert panel.process_button.text().replace("&&", "&") == "🚀 BẮT ĐẦU XỬ LÝ"

    panel.update_cta_for_state("REVIEW_REQUIRED", has_video=True)
    assert panel.process_button.text().replace("&&", "&") == "✓ DUYỆT & TẠO VOICE"

    panel.update_cta_for_state("APPROVED", has_video=True)
    assert panel.process_button.text().replace("&&", "&") == "✓ DUYỆT & TẠO VOICE"

    panel.update_cta_for_state("VOICE_READY", has_video=True)
    assert panel.process_button.text().replace("&&", "&") == "🎬 XUẤT PROJECT CAPCUT"
    assert panel.process_button.isHidden()
    assert not panel.export_actions.isHidden()

    # Check 6-stage status indicators
    panel.set_pipeline_status(1, done=True)
    assert "✓ Video" in panel.status_video.text()
    assert "○ Bóc băng" in panel.status_stt.text()

    panel.set_pipeline_status(2, active=True)
    assert "● Bóc băng (Đang chạy…)" in panel.status_stt.text()

    panel.set_pipeline_status(3, done=True)
    assert "✓ Bóc băng" in panel.status_stt.text()
    assert "✓ Dịch" in panel.status_trans.text()


def test_settings_dialog_v2_tabs(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(QMessageBox, "information", lambda *a: None)
    monkeypatch.setattr("vkdub.media.process.MediaTools.detect", lambda self: None)
    dummy_window = MainWindow()
    qtbot.addWidget(dummy_window)

    dialog = SettingsDialog(dummy_window)
    qtbot.addWidget(dialog)

    # Verify exactly 6 standardized V2 tabs
    tab_titles = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
    assert tab_titles == ["Chung", "AI", "Voice", "CapCut", "Cập nhật", "Nâng cao"]

    # Verify HWID and TikTok Session ID are NOT present in any input field
    all_text = ""
    for widget in dialog.findChildren(object):
        if hasattr(widget, "text") and callable(widget.text):
            all_text += " " + str(widget.text())

    assert "HWID" not in all_text
    assert "TikTok Session" not in all_text

    # Test CapCut tab auto-detect and save
    dialog.capcut_root_input.setText(str(tmp_path / "Drafts"))
    dialog._save_capcut_settings()
    assert dialog.app_settings.capcut_draft_root == str(tmp_path / "Drafts")


def test_main_window_v2_shell_and_cta(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("vkdub.media.process.find_tool", lambda _: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard)
    monkeypatch.setattr(CredentialStore, "get", lambda self: "fake-test-key")

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.tools_ready)

    # Health banner exists
    assert window.health_banner is not None

    # One-click text removal is the primary canvas action.
    assert "Xóa chữ" in window.preview.btn_mask.text()

    # Legacy TTS panel is hidden from main view
    assert hasattr(window.tts, "panel")
    assert window.tts.panel.isHidden()

    # Initial state without video: CTA disabled
    assert window.left.process_button.isEnabled() is False

    # Simulate video imported
    window.project = Project(
        video_path=tmp_path / "video.mp4",
        video_duration_ms=5000,
    )
    window._refresh()
    assert window.left.process_button.isEnabled() is False
    assert window.left.process_button.text().replace("&&", "&") == "🚀 BẮT ĐẦU XỬ LÝ"
    assert not window.project.subtitle_style.background_box
    window.preview.btn_sub_box.click()
    assert window.project.subtitle_style.background_box
    assert window.dirty

    # Simulate review required
    window.project.script = ScriptDocument((ScriptLine(str(uuid4()), 0, 5000, "Xin chào"),))
    window._refresh()
    assert window.left.process_button.text().replace("&&", "&") == "✓ DUYỆT & TẠO VOICE"

    # Banner action test
    window._on_banner_action("open_settings_capcut")
    assert window.settings_dialog is not None
    assert window.settings_dialog.tabs.currentIndex() == 3

    window.dirty = False
    window.close()
