import os
import sys
import time
from pathlib import Path

repo_root = Path(r"D:\Work\Project_AI\ToolVideo")
src_dir = repo_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vkdub.domain.mask import MaskItem
from vkdub.domain.project import Project
from vkdub.domain.transcript import SubtitleSegment, Transcript
from vkdub.domain.translation import Translation, source_digest
from vkdub.media.ffprobe import VideoMetadata
from vkdub.orchestrator.pipeline_state import SubstepStatus
from vkdub.ui.api_cost_dialog import ApiCostDialog
from vkdub.ui.export_dialog import ExportDialog
from vkdub.ui.log_viewer_dialog import LogViewerDialog
from vkdub.ui.main_window import MainWindow
from vkdub.ui.mask_dialog import MaskEditorDialog
from vkdub.ui.settings_dialog import SettingsDialog
from vkdub.ui.setup_wizard import SetupWizardDialog
from vkdub.ui.subtitle_style_dialog import SubtitleStyleDialog
from vkdub.ui.theme import apply_widget_theme, set_application_theme

def capture_all():
    print("Initializing application...", flush=True)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    set_application_theme(app, "light")
    output_dir = repo_root / "docs" / "screenshots"
    output_dir.mkdir(parents=True, exist_ok=True)

    real_video = repo_root / "docs" / "evidence" / "media" / "sample.mp4"
    if not real_video.exists():
        real_video = repo_root / "sample_short_drama.mp4"
        if not real_video.exists():
            real_video.write_bytes(b"dummy")

    print("Creating MainWindow...", flush=True)
    window = MainWindow()
    set_application_theme(app, "light")
    window.top_bar.set_theme("light")
    apply_widget_theme(window, "light")
    window.resize(1440, 900)
    window.show()
    app.processEvents()

    # 1. Apply real video import
    metadata = VideoMetadata(12.5, 720, 1280, 30.0, "h264", "aac", 2_000_000)
    window._apply_import(real_video, metadata)
    app.processEvents()

    # Setup realistic bilingual script
    source = Transcript(
        (
            SubtitleSegment(1, 0.5, 2.8, "如果你觉得生活太累，就停下来歇一歇。"),
            SubtitleSegment(2, 3.2, 5.5, "人生本就是一场漫长的旅程，不必太急。"),
            SubtitleSegment(3, 6.0, 8.2, "偶尔看看路边的风景，吹吹晚风，也挺好。"),
            SubtitleSegment(4, 8.8, 10.5, "给时光一份从容，给自己一份释怀。"),
            SubtitleSegment(5, 11.0, 12.4, "愿你历经千帆，归来仍是少年！"),
        ),
        "zh",
        "zh",
        12.5,
        "large-v3",
        "cuda",
        "a" * 64,
        "b" * 64,
    )
    vietnamese_lines = (
        "Nếu bạn cảm thấy cuộc sống quá mệt mỏi, hãy dừng lại nghỉ ngơi một chút.",
        "Cuộc đời vốn là một chuyến hành trình dài, không cần quá vội vã.",
        "Thi thoảng ngắm nhìn phong cảnh bên đường, đón làn gió chiều cũng thật tuyệt.",
        "Hãy dành cho thời gian sự thong dong, và cho bản thân một chút nhẹ nhõm.",
        "Chúc bạn đi qua ngàn trùng sóng gió, trở về vẫn giữ vẹn nét tươi trẻ ban đầu!",
    )
    window.project.transcript = source
    window.project.translation = Translation(source_digest(source), vietnamese_lines)
    window.project.masks = [
        MaskItem(
            name="Che Sub Gốc",
            mask_type="erase",
            x=0.08,
            y=0.76,
            width=0.84,
            height=0.15,
            blur_strength=24,
        )
    ]
    window.preview.video.set_masks(window.project.masks, window.project.masks[0].id, 0)
    window.step3_panel.set_masks(window.project.masks, window.project.masks[0].id)
    window.review_controller.bind_project()
    window._refresh()
    app.processEvents()

    # Step 1
    window.switch_to_step(0)
    app.processEvents()
    time.sleep(0.1)
    window.grab().save(str(output_dir / "01_main_step1_source.png"))
    print("[1/20] Saved 01_main_step1_source.png", flush=True)

    # Step 2
    window.switch_to_step(1)
    app.processEvents()
    time.sleep(0.1)
    window.grab().save(str(output_dir / "02_main_step2_voice.png"))
    print("[2/20] Saved 02_main_step2_voice.png", flush=True)

    # Step 3
    window.switch_to_step(2)
    app.processEvents()
    time.sleep(0.1)
    window.grab().save(str(output_dir / "03_main_step3_blur.png"))
    print("[3/20] Saved 03_main_step3_blur.png", flush=True)

    # Step 4
    window.switch_to_step(3)
    panel4 = window.step4_panel
    panel4.update_substep("4.1", SubstepStatus.SUCCESS, 100, "whisper-large-v3 • 5 câu", duration_s=4.2)
    panel4.update_substep("4.2", SubstepStatus.SUCCESS, 100, "gemini-2.0-flash • 5 câu", duration_s=2.8)
    panel4.update_substep("4.3", SubstepStatus.SUCCESS, 100, "Đã căn chỉnh timeline 100%", duration_s=0.5)
    panel4.update_substep("4.4", SubstepStatus.RUNNING, 65, "Đang lồng tiếng Vbee: Ngọc Huyền (3/5 câu)...", duration_s=6.1)
    app.processEvents()
    time.sleep(0.1)
    window.grab().save(str(output_dir / "04_main_step4_automation.png"))
    print("[4/20] Saved 04_main_step4_automation.png", flush=True)

    # Step 5
    window.switch_to_step(4)
    app.processEvents()
    time.sleep(0.1)
    window.grab().save(str(output_dir / "05_main_step5_review.png"))
    print("[5/20] Saved 05_main_step5_review.png", flush=True)

    # Diagnostics Drawer
    window.diagnostics_drawer.toggle_drawer()
    window.log("INFO: Khởi chạy VK Dub Studio v2.1.17")
    window.log("INFO: Tải video nguồn mẫu: sample.mp4 (720x1280, 12.5s)")
    window.log("SUCCESS: Trình duyệt Edge đã kết nối cổng gỡ lỗi 9222")
    window.log("SUCCESS: Phiên đăng nhập ChatGPT & Vbee hoạt động bình thường")
    app.processEvents()
    time.sleep(0.1)
    window.grab().save(str(output_dir / "06_main_diagnostics_expanded.png"))
    print("[6/20] Saved 06_main_diagnostics_expanded.png", flush=True)
    window.diagnostics_drawer.toggle_drawer()
    app.processEvents()

    # Settings Dialog
    print("Opening Settings Dialog...", flush=True)
    settings = SettingsDialog(window)
    settings.set_theme_value("light")
    settings.resize(1040, 720)
    settings.show()
    app.processEvents()

    settings_tabs = [
        ("07_settings_tab1_chung.png", 0, "[7/20]"),
        ("08_settings_tab2_ai.png", 1, "[8/20]"),
        ("09_settings_tab3_voice.png", 2, "[9/20]"),
        ("10_settings_tab4_capcut.png", 3, "[10/20]"),
        ("11_settings_tab5_capnhat.png", 4, "[11/20]"),
        ("12_settings_tab6_nangcao.png", 5, "[12/20]"),
    ]
    for filename, idx, tag in settings_tabs:
        settings.tabs.setCurrentIndex(idx)
        app.processEvents()
        time.sleep(0.1)
        settings.grab().save(str(output_dir / filename))
        print(f"{tag} Saved {filename}", flush=True)
    settings.close()
    app.processEvents()

    # Subtitle Style Dialog
    sub_dlg = SubtitleStyleDialog(window)
    sub_dlg.show()
    app.processEvents()
    time.sleep(0.1)
    sub_dlg.grab().save(str(output_dir / "13_dialog_subtitle_style.png"))
    print("[13/20] Saved 13_dialog_subtitle_style.png", flush=True)
    sub_dlg.close()
    app.processEvents()

    # Mask Editor Dialog
    mask_dlg = MaskEditorDialog(window)
    mask_dlg.show()
    app.processEvents()
    time.sleep(0.1)
    mask_dlg.grab().save(str(output_dir / "14_dialog_mask_editor.png"))
    print("[14/20] Saved 14_dialog_mask_editor.png", flush=True)
    mask_dlg.close()
    app.processEvents()

    # Export Dialog
    export_dlg = ExportDialog(window)
    export_dlg.update_checklist(window.project, ffmpeg_available=True)
    export_dlg.show()
    app.processEvents()
    time.sleep(0.1)
    export_dlg.grab().save(str(output_dir / "15_dialog_export.png"))
    print("[15/20] Saved 15_dialog_export.png", flush=True)
    export_dlg.close()
    app.processEvents()

    # Log Viewer Dialog
    log_dlg = LogViewerDialog(window)
    log_dlg.show()
    app.processEvents()
    time.sleep(0.1)
    log_dlg.grab().save(str(output_dir / "16_dialog_log_viewer.png"))
    print("[16/20] Saved 16_dialog_log_viewer.png", flush=True)
    log_dlg.close()
    app.processEvents()

    # API Cost Dialog
    cost_dlg = ApiCostDialog(window.translation)
    cost_dlg.show()
    app.processEvents()
    time.sleep(0.1)
    cost_dlg.grab().save(str(output_dir / "17_dialog_api_cost.png"))
    print("[17/20] Saved 17_dialog_api_cost.png", flush=True)
    cost_dlg.close()
    app.processEvents()

    # Setup Wizard Dialog - pages 0, 1, 2
    wizard = SetupWizardDialog()
    wizard.show()
    app.processEvents()

    wizard.stack.setCurrentIndex(0)
    wizard._update_step_ui()
    app.processEvents()
    time.sleep(0.1)
    wizard.grab().save(str(output_dir / "18_dialog_wizard_step1_gemini.png"))
    print("[18/20] Saved 18_dialog_wizard_step1_gemini.png", flush=True)

    wizard.stack.setCurrentIndex(1)
    wizard._update_step_ui()
    app.processEvents()
    time.sleep(0.1)
    wizard.grab().save(str(output_dir / "19_dialog_wizard_step2_voice.png"))
    print("[19/20] Saved 19_dialog_wizard_step2_voice.png", flush=True)

    wizard.stack.setCurrentIndex(2)
    wizard._update_step_ui()
    app.processEvents()
    time.sleep(0.1)
    wizard.grab().save(str(output_dir / "20_dialog_wizard_step3_capcut.png"))
    print("[20/20] Saved 20_dialog_wizard_step3_capcut.png", flush=True)
    wizard.close()
    app.processEvents()

    # Dark-mode proof: capture the five main workflow contexts plus Settings.
    dark_dir = output_dir / "dark"
    dark_dir.mkdir(parents=True, exist_ok=True)
    set_application_theme(app, "dark")
    apply_widget_theme(window, "dark")
    for index, filename in enumerate(
        (
            "01_main_step1_source_dark.png",
            "02_main_step2_voice_dark.png",
            "03_main_step3_blur_dark.png",
            "04_main_step4_automation_dark.png",
            "05_main_step5_review_dark.png",
        )
    ):
        window.switch_to_step(index)
        apply_widget_theme(window, "dark")
        app.processEvents()
        time.sleep(0.1)
        window.grab().save(str(dark_dir / filename))

    dark_settings = SettingsDialog(window)
    dark_settings.resize(1040, 720)
    dark_settings.show()
    apply_widget_theme(dark_settings, "dark")
    app.processEvents()
    time.sleep(0.1)
    dark_settings.grab().save(str(dark_dir / "06_settings_dark.png"))
    dark_settings.close()
    app.processEvents()

    # Wide-desktop proof: exercise every workflow at the 1920x1080 target.
    wide_dir = output_dir / "wide_1920x1080"
    wide_dir.mkdir(parents=True, exist_ok=True)
    set_application_theme(app, "light")
    window.top_bar.set_theme("light")
    window.resize(1920, 1080)
    apply_widget_theme(window, "light")
    for index, filename in enumerate(
        (
            "01_main_step1_source_1920.png",
            "02_main_step2_voice_1920.png",
            "03_main_step3_blur_1920.png",
            "04_main_step4_automation_1920.png",
            "05_main_step5_review_1920.png",
        )
    ):
        window.switch_to_step(index)
        app.processEvents()
        time.sleep(0.1)
        window.grab().save(str(wide_dir / filename))

    wide_settings = SettingsDialog(window)
    wide_settings.resize(1240, 840)
    wide_settings.show()
    app.processEvents()
    time.sleep(0.1)
    wide_settings.grab().save(str(wide_dir / "06_settings_1920_workspace.png"))
    wide_settings.close()
    app.processEvents()

    window.dirty = False
    window.close()
    app.processEvents()
    print(
        "SUCCESS: 20 light screens, 6 dark proofs and 6 wide-desktop proofs exported cleanly!",
        flush=True,
    )

if __name__ == "__main__":
    capture_all()
    os._exit(0)
