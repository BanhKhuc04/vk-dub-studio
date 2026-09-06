"""Native app, real Gemini + local VieNeu; uses a small labelled transcript fixture."""

import argparse
import json
import os
import sys
import time
import traceback
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest

from vkdub.app import create_application
from vkdub.domain.transcript import SubtitleSegment, Transcript
from vkdub.providers.vieneu_local import VieNeuLocalProvider
from vkdub.services.app_settings import AppSettings, load_app_settings, save_app_settings
from vkdub.services.project_service import load_project
from vkdub.services.script_service import edit_line
from vkdub.services.voice_catalog import read_catalog, save_catalog
from vkdub.ui.main_window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    installed = load_app_settings()
    presets = [r for r in read_catalog() if not r["custom"]]
    assert presets, "Run real VieNeu setup first"
    os.environ["VKDUB_DATA_DIR"] = str(args.output_dir.resolve() / "app-data")
    save_app_settings(
        AppSettings(
            wizard_completed=True,
            auto_update=False,
            gemini_model=installed.gemini_model,
            vieneu_runtime=installed.vieneu_runtime,
            selected_voice=presets[0]["id"],
            voice_volume=0,
        )
    )
    save_catalog(presets)
    calls = []
    original_synthesize = VieNeuLocalProvider.synthesize

    async def measured(self, text, voice_id, speed, output_path):
        calls.append(text)
        return await original_synthesize(self, text, voice_id, speed, output_path)

    VieNeuLocalProvider.synthesize = measured
    app = create_application()
    window = MainWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    window.show()
    window.project.voice = replace(window.project.voice, volume=0)
    result = {"passed": False, "platform": app.platformName(), "checks": [], "qt_ticks": 0}
    stage = 0
    initial_calls = 0
    preserved_asset = None
    started = time.monotonic()
    timer = QTimer()
    timer.setInterval(50)

    def capture(name):
        window.grab().save(str(args.output_dir / f"{name}.png"))

    def finish(error=None):
        timer.stop()
        result["passed"] = error is None
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
        result["synthesize_calls"] = len(calls)
        if error:
            result["failure"] = error
        (args.output_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        capture("final")
        print(json.dumps(result, ensure_ascii=True), flush=True)
        window.dirty = False
        window.close()
        app.exit(1 if error else 0)

    def tick():
        nonlocal stage, initial_calls, preserved_asset
        result["qt_ticks"] += 1
        try:
            if time.monotonic() - started > 240:
                raise TimeoutError(f"Native voice smoke stage {stage}")
            if stage == 0:
                if not window.tools_ready or window.health_job is not None:
                    return
                assert window.import_video(args.video.resolve())
                stage = 1
            elif stage == 1:
                if window.busy or not window.preview.play_button.isEnabled():
                    return
                window.preview.audio.setVolume(0)
                window.project.transcript = Transcript(
                    (
                        SubtitleSegment(1, 0, 3, "Hello everyone."),
                        SubtitleSegment(2, 3, 7.5, "Thank you for watching this video."),
                    ),
                    "en",
                    "en",
                    7.908,
                    "tiny",
                    "cpu",
                    "a" * 64,
                    "a" * 64,
                )
                window._refresh()
                assert not window.tts.start()
                assert window.translation.start()
                stage = 2
            elif stage == 2:
                if window.busy:
                    return
                assert window.project.translation and len(window.project.script.lines) == 2
                assert not window.project.is_approved and not calls
                assert [(r.start_ms, r.end_ms) for r in window.project.script.lines] == [
                    (0, 3000),
                    (3000, 7500),
                ]
                result["translation"] = list(window.project.translation.texts)
                result["checks"].append(
                    "Real Gemini structured translation preserves timing and stops at review"
                )
                capture("review-required")
                window.review.review_checkbox.setChecked(True)
                QTest.mouseClick(window.left.process_button, Qt.MouseButton.LeftButton)
                assert window.project.is_approved and window.tts.job is not None
                stage = 3
            elif stage == 3:
                if window.busy:
                    return
                assert window.project.voice_ready, window.tts.errors
                assert len(calls) == 2
                preserved_asset = window.project.voice_assets[window.project.script.lines[1].id]
                result["checks"].append("Approve CTA synthesizes both lines with real local VieNeu")
                capture("voice-ready")
                assert window.save_to(args.output_dir / "voice-project.vkdub")
                assert load_project(args.output_dir / "voice-project.vkdub").voice_ready
                initial_calls = len(calls)
                assert window.tts.start()
                stage = 4
            elif stage == 4:
                if window.busy:
                    return
                assert len(calls) == initial_calls
                result["checks"].append(
                    "Second generation reuses validated audio cache without synthesis"
                )
                script = edit_line(
                    window.project.script, 0, text="Xin chào, chúc bạn một ngày vui vẻ."
                )
                window.review_controller.commit(script, "Native smoke edit")
                assert not window.project.is_approved and not window.tts.start()
                window.review.review_checkbox.setChecked(True)
                QTest.mouseClick(window.left.process_button, Qt.MouseButton.LeftButton)
                stage = 5
            elif stage == 5:
                if window.busy:
                    return
                assert window.project.voice_ready, window.tts.errors
                assert len(calls) == initial_calls + 1
                assert (
                    window.project.voice_assets[window.project.script.lines[1].id]
                    == preserved_asset
                )
                result["checks"].append(
                    "Edit revokes approval; reapprove regenerates only the changed line"
                )
                assert window.tts.preview_voice()
                stage = 6
            elif stage == 6:
                if window.busy:
                    return
                assert window.tts.last_preview_path.is_file()
                result["preview_audio"] = str(window.tts.last_preview_path)
                window.tts.player.stop()
                window.open_settings(2)
                window.settings_dialog.grab().save(str(args.output_dir / "voice-settings.png"))
                window.settings_dialog.close()
                result["checks"].append(
                    "Voice preview creates real WAV; settings list actual SDK presets"
                )
                assert window.left.process_button.isEnabled()
                assert window.left.process_button.text() == "🎬 XUẤT PROJECT CAPCUT"
                result["checks"].append("CapCut export CTA is enabled only after voice is ready")
                assert window.save_to(args.output_dir / "edited-voice-project.vkdub")
                finish()
        except Exception:
            finish(traceback.format_exc())

    timer.timeout.connect(tick)
    timer.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
