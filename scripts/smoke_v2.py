"""Native M1–M3 acceptance smoke with isolated settings and real local media.

--restart verifies the settings from a preceding run. No cloud generation is called.
"""

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QTimer

from vkdub.app import create_application
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.services.app_settings import AppSettings, load_app_settings, save_app_settings
from vkdub.services.credential_service import CredentialStore
from vkdub.ui.main_window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--hold", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    os.environ["VKDUB_DATA_DIR"] = str(args.output_dir.resolve() / "app-data")
    # A separate, empty Windows vault namespace keeps production credentials untouched.
    CredentialStore.service = "VKDubStudio-Checkpoint-" + str(uuid4())
    if not args.restart:
        save_app_settings(AppSettings(auto_update=False))
    app = create_application()
    window = MainWindow()
    window.show()
    result = {"checks": [], "passed": False, "restart": args.restart, "qt_ticks": 0}
    stage = 0
    started = time.monotonic()
    timer = QTimer()
    timer.setInterval(50)
    frames = []
    window.preview.video.sink.videoFrameChanged.connect(
        lambda f: frames.append(1) if f.isValid() else None
    )
    tag = "restart" if args.restart else "first-run"

    def capture(name):
        window.grab().save(str(args.output_dir / f"{tag}-{name}.png"))

    def finish(error=None):
        timer.stop()
        result["passed"] = error is None
        result["decoded_frames"] = len(frames)
        result["tools"] = window.tools.paths
        result["health"] = [r.code for r in getattr(window, "health_results", [])]
        if error:
            result["failure"] = error
        capture("window")
        (args.output_dir / f"{tag}-result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=True), flush=True)
        if not args.hold or error:
            window.dirty = False
            window.close()
            app.exit(1 if error else 0)

    def tick():
        nonlocal stage
        result["qt_ticks"] += 1
        try:
            if time.monotonic() - started > 45:
                raise TimeoutError(f"Smoke timed out at stage {stage}")
            if stage == 0:
                if not window.tools_ready:
                    return
                if args.restart:
                    assert window.setup_wizard is None
                    settings = load_app_settings()
                    assert settings.wizard_completed and settings.source_language == "en"
                    assert settings.voice_speed == 1.2 and not settings.auto_update
                    assert window.left.source_language.currentData() == "en"
                    result["checks"].append(
                        "Separate process restart restores settings and does not open wizard"
                    )
                else:
                    wizard = window.setup_wizard
                    assert wizard is not None and wizard.isVisible()
                    wizard.grab().save(str(args.output_dir / "wizard-step-1.png"))
                    wizard.src_lang_combo.setCurrentIndex(wizard.src_lang_combo.findData("en"))
                    for _ in range(4):
                        wizard._next_step()
                    assert wizard.stack.currentIndex() == 4
                    stage = 1
                    return
                stage = 2
            if stage == 1:
                if window.setup_wizard.check_job is not None:
                    return
                window.setup_wizard.grab().save(str(args.output_dir / "wizard-step-5.png"))
                window.setup_wizard._finish_wizard()
                settings = load_app_settings()
                settings.voice_speed = 1.2
                save_app_settings(settings)
                window._settings_applied()
                result["checks"].append(
                    "First-run 5-step wizard completes and persists without requiring a key"
                )
                stage = 2
            if stage == 2:
                if window.health_job is not None:
                    return
                assert window.health_banner.isVisible()
                assert any(
                    r.code == "TTS_NOT_INTEGRATED" and not r.ok for r in window.health_results
                )
                assert window.tts.panel.isHidden()
                assert not window.left.voice_combo.isEnabled()
                assert not window.left.listen_test_button.isEnabled()
                assert not window.left.process_button.isEnabled()
                result["checks"].append(
                    "Missing Gemini/TTS produce truthful health results; legacy controls hidden"
                )
                assert window.import_video(args.video)
                stage = 3
                return
            if stage == 3:
                if window.busy or not window.preview.play_button.isEnabled():
                    return
                assert window.project.duration_ms > 0
                window.preview.audio.setVolume(0)
                window.preview.player.play()
                stage = 4
                return
            if stage == 4:
                if window.preview.player.position() < 650 or not frames:
                    return
                window.preview.player.pause()
                window.preview.player.setPosition(2000)
                result["checks"].append("Real MP4 probed, decoded, played, paused and sought")
                window.project.script = ScriptDocument(
                    (ScriptLine(str(uuid4()), 0, 3000, "Kịch bản kiểm thử cục bộ."),)
                )
                window.review_controller.bind_project()
                window._refresh()
                assert not window.left.process_button.isEnabled()
                assert not window.review.review_checkbox.isChecked()
                window._on_primary_cta_clicked()
                assert not window.project.is_approved
                window.review.review_checkbox.setChecked(True)
                assert window.left.process_button.isEnabled()
                window.left.process_button.click()
                assert window.project.is_approved and window.tts.job is None
                assert not window.review.export_button.isEnabled()
                assert not window.left.process_button.isEnabled()
                project_path = args.output_dir / "checkpoint.vkdub"
                assert window.save_to(project_path)
                assert window.open_project(project_path)
                stage = 5
                return
            if stage == 5:
                if window.busy:
                    return
                assert window.project.is_approved
                window.review.editor.text.setPlainText("Kịch bản đã chỉnh sửa.")
                assert not window.project.is_approved
                assert not window.review.review_checkbox.isChecked()
                assert not window.left.process_button.isEnabled()
                result["checks"].append(
                    "Explicit review, schema-6 save/reopen, edit revocation; "
                    "no TTS or CapCut dispatch"
                )
                window.open_settings(2)
                dialog = window.settings_dialog
                assert [dialog.tabs.tabText(i) for i in range(6)] == [
                    "Chung",
                    "AI",
                    "Voice",
                    "CapCut",
                    "Cập nhật",
                    "Nâng cao",
                ]
                dialog.grab().save(str(args.output_dir / f"{tag}-settings-voice.png"))
                dialog.close()
                result["checks"].append(
                    "Six settings tabs; voice catalog and preview honestly unavailable"
                )
                stage = 6
                return
            if stage == 6:
                if window.health_job is not None:
                    return
                finish()
        except Exception:
            finish(traceback.format_exc())

    timer.timeout.connect(tick)
    timer.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
