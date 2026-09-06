"""Open the actual desktop app, optionally exercise a real MP4, and capture evidence.

Use a disposable directory outside the repository for --output-dir.
"""

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest

from vkdub.app import create_application
from vkdub.ui.main_window import MainWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--hold", action="store_true", help="Leave window open for visual inspection"
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    app = create_application()
    window = MainWindow()
    window.show()
    result = {"checks": [], "passed": False}
    started = time.monotonic()
    stage = 0
    frames = []
    errors = []
    window.preview.video.sink.videoFrameChanged.connect(
        lambda frame: frames.append((frame.width(), frame.height())) if frame.isValid() else None
    )
    window.preview.playback_error.connect(errors.append)
    timer = QTimer()
    timer.setInterval(100)

    def check_gates():
        assert not window.review.approve_button.isEnabled()
        assert not window.review.export_button.isEnabled()

    def finish(error=None):
        timer.stop()
        result["passed"] = error is None
        result["errors"] = errors
        if error:
            result["failure"] = error
        result["tools"] = window.tools.paths
        result["decoded_frames"] = len(frames)
        screenshot = args.output_dir / "smoke-window.png"
        window.grab().save(str(screenshot))
        (args.output_dir / "smoke-result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=True), flush=True)
        if not args.hold or error:
            window.dirty = False
            window.close()
            app.exit(1 if error else 0)

    def tick():
        nonlocal stage
        try:
            if time.monotonic() - started > 35:
                raise TimeoutError(f"Smoke timed out in stage {stage}")
            check_gates()
            if errors:
                raise AssertionError(errors)
            if stage == 0 and window.tools_ready:
                result["checks"].append(
                    "visible branded shell; detection finished; workflow disabled"
                )
                if args.video is None:
                    finish()
                    return
                assert all(window.tools.paths.values()), (
                    "Real-media smoke requires FFmpeg + ffprobe"
                )
                assert window.import_video(args.video)
                stage = 1
            elif stage == 1 and not window.busy and window.preview.play_button.isEnabled():
                assert "Video:" in window.preview.metadata_label.text()
                result["metadata"] = window.preview.metadata_label.text()
                result["checks"].append("MP4 import and real ffprobe metadata")
                window.preview.audio.setMuted(True)
                QTest.mouseClick(window.preview.play_button, Qt.MouseButton.LeftButton)
                stage = 2
            elif stage == 2 and window.preview.player.position() >= 600 and frames:
                assert (
                    window.preview.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                )
                QTest.mouseClick(window.preview.play_button, Qt.MouseButton.LeftButton)
                assert (
                    window.preview.player.playbackState() == QMediaPlayer.PlaybackState.PausedState
                )
                result["checks"].append("play advances clock and decodes video frames; pause works")
                window.preview.seek.setValue(2000)
                stage = 3
            elif stage == 3 and abs(window.preview.player.position() - 2000) < 300:
                result["checks"].append("seek to 2 seconds via slider")
                assert window.set_output_directory(args.output_dir)
                assert window.save_to(args.output_dir / "smoke.vkdub")
                project = window.project
                assert window.open_project(args.output_dir / "smoke.vkdub")
                assert window.project == project
                stage = 4
            elif stage == 4 and not window.busy and window.preview.play_button.isEnabled():
                assert "Video:" in window.preview.metadata_label.text()
                result["checks"].append("output selection and .vkdub save/reload preserve project")
                window.preview.player.setPosition(2000)
                frames.clear()
                QTest.mouseClick(window.preview.play_button, Qt.MouseButton.LeftButton)
                stage = 5
            elif stage == 5 and frames and window.preview.player.position() >= 2100:
                QTest.mouseClick(window.preview.play_button, Qt.MouseButton.LeftButton)
                assert not window.preview.video.frame_image.isNull()
                result["checks"].append("reloaded media decodes and paints a visible preview frame")
                result["checks"].append("approval/export remain disabled after reload")
                finish()
        except Exception:
            finish(traceback.format_exc())

    timer.timeout.connect(tick)
    timer.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
