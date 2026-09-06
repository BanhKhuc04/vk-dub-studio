"""Run the real Windows app and exercise one-click text removal on decoded video."""

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtTest import QTest

from vkdub.app import create_application
from vkdub.services.app_settings import AppSettings, save_app_settings
from vkdub.services.credential_service import CredentialStore
from vkdub.ui.main_window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    os.environ["VKDUB_DATA_DIR"] = str(args.output_dir.resolve() / "app-data")
    CredentialStore.service = "VKDubStudio-BlurSmoke-" + str(uuid4())
    save_app_settings(AppSettings(auto_update=False, wizard_completed=True))
    app = create_application()
    window = MainWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    window.show()
    canvas = window.preview.video
    frames = []
    canvas.sink.videoFrameChanged.connect(lambda f: frames.append(1) if f.isValid() else None)
    result = {"passed": False, "checks": [], "qt_ticks": 0, "platform": app.platformName()}
    stage = 0
    started = time.monotonic()
    paused_at = 0.0
    frame_count = 0
    saved_mask = None
    timer = QTimer()
    timer.setInterval(50)

    def capture(name):
        assert window.grab().save(str(args.output_dir / f"{name}.png"))

    def finish(error=None):
        timer.stop()
        result["passed"] = error is None
        result["decoded_frames"] = len(frames)
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
        if error:
            result["failure"] = error
        (args.output_dir / "native-result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=True), flush=True)
        window.dirty = False
        window.close()
        app.exit(1 if error else 0)

    def tick():
        nonlocal stage, paused_at, frame_count, saved_mask
        result["qt_ticks"] += 1
        window.setWindowTitle("VK Dub Studio — Kiểm thử tự động, cửa sổ sẽ tự đóng")
        try:
            if time.monotonic() - started > 45:
                raise TimeoutError(f"Stage {stage}")
            if stage == 0:
                if not window.tools_ready or window.health_job is not None:
                    return
                assert window.import_video(args.video.resolve())
                stage = 1
            elif stage == 1:
                if window.busy or not window.preview.play_button.isEnabled():
                    return
                window.preview.audio.setVolume(0)
                window.preview.player.play()
                stage = 2
            elif stage == 2:
                if len(frames) < 12:
                    return
                window.preview.player.pause()
                paused_at = time.monotonic()
                stage = 3
            elif stage == 3:
                if time.monotonic() - paused_at < 0.3:
                    return
                capture("before")
                QTest.mouseClick(window.preview.btn_mask, Qt.MouseButton.LeftButton)
                assert len(window.project.masks) == 1
                canvas.grab()
                mask = window.project.masks[0]
                assert mask.mask_type == "erase"
                center = canvas._mask_rect(mask).center()
                QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=center)
                QTest.mouseMove(canvas, center + QPoint(-20, -45))
                QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=center + QPoint(-20, -45))
                assert mask.y < 0.74
                canvas.grab()
                corner = canvas._mask_rect(mask).bottomRight()
                QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=corner)
                QTest.mouseMove(canvas, corner + QPoint(25, 20))
                QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=corner + QPoint(25, 20))
                assert mask.width > 0.76 and mask.height > 0.16
                saved_mask = mask.to_dict()
                capture("erase-selected")
                assert canvas.delete_mask_button.isVisible()
                QTest.keyClick(canvas, Qt.Key.Key_Escape)
                capture("erase-clean")
                result["checks"].append("One-click add, body drag, corner resize, Escape deselect")
                frame_count = len(frames)
                window.preview.player.play()
                stage = 4
            elif stage == 4:
                if len(frames) - frame_count < 25:
                    return
                window.preview.player.pause()
                result["playback_frames_with_erase"] = len(frames) - frame_count
                result["checks"].append(
                    "Real video plays with text removal while Qt timer continues"
                )
                path = args.output_dir / "erase-project.vkdub"
                assert window.save_to(path)
                assert window.open_project(path)
                stage = 5
            elif stage == 5:
                if window.busy or not window.preview.play_button.isEnabled():
                    return
                assert window.project.masks[0].to_dict() == saved_mask
                # Some native decoders wait for playback to deliver the first frame
                # after setSource(), even when metadata is already available.
                if canvas.frame_image.isNull():
                    window.preview.player.play()
                    return
                window.preview.player.pause()
                assert canvas.interactive_mask_mode
                canvas.grab()
                center = canvas._mask_rect(window.project.masks[0]).center()
                QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=center)
                canvas.grab()
                assert canvas.delete_mask_button.isVisible()
                QTest.mouseClick(canvas.delete_mask_button, Qt.MouseButton.LeftButton)
                assert not window.project.masks and window.dirty
                assert not canvas.masks
                capture("after-delete")
                assert not canvas.delete_mask_button.isVisible()
                assert window.save_to(args.output_dir / "deleted-project.vkdub")
                result["checks"].append(
                    "Save/reopen preserves geometry; top-right × deletes and saves"
                )
                finish()
        except Exception:
            finish(traceback.format_exc())

    timer.timeout.connect(tick)
    timer.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
