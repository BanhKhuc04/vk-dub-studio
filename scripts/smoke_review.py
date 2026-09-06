"""Native review-gate acceptance using a clearly identified, manually authored script.

Use a project containing the public JFK speech fixture (11 seconds). No cloud/voice calls.
"""

import argparse
import json
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QCheckBox

from vkdub.app import create_application
from vkdub.services.srt_service import read_srt, write_srt
from vkdub.ui.main_window import MainWindow

FIRST = "Hỡi đồng bào Mỹ, đừng hỏi đất nước có thể làm gì cho bạn."
SECOND = "Hãy hỏi bạn có thể làm gì cho đất nước."


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--hold", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    app = create_application()
    w = MainWindow()
    w.show()
    timer = QTimer()
    timer.setInterval(100)
    started = time.monotonic()
    stage = 0
    approved_hash = None
    original_source = None
    result = {
        "passed": False,
        "checks": [],
        "fixture": "manually authored Vietnamese review text",
        "cloud_requests": 0,
        "voice_requests": 0,
        "export_available": False,
    }

    def finish(error=None):
        timer.stop()
        result["passed"] = error is None
        if error:
            result["error"] = str(error)
            w.grab().save(str(args.output_dir / "review-failure.png"))
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
        (args.output_dir / "review-result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=True), flush=True)
        if not args.hold or error:
            w.dirty = False
            w.close()
            app.exit(1 if error else 0)

    def click(button):
        position = (
            QPoint(10, button.height() // 2)
            if isinstance(button, QCheckBox)
            else button.rect().center()
        )
        QTest.mouseClick(button, Qt.MouseButton.LeftButton, pos=position)

    def tick():
        nonlocal stage, approved_hash, original_source
        try:
            if time.monotonic() - started > 35:
                raise TimeoutError(f"Review smoke timed out at stage {stage}")
            assert not w.review.export_button.isEnabled()
            assert w.translation.job is None
            if stage == 0 and w.tools_ready:
                assert w.open_project(args.project)
                stage = 1
            elif stage == 1 and not w.busy:
                original_source = w.project.transcript
                assert original_source and len(original_source.segments) == 1
                assert w.project.script is None
                click(w.review.buttons["prepare"])
                assert w.project.state == "REVIEW_REQUIRED"
                assert not w.review.review_checkbox.isEnabled()
                w.review.editor.text.setPlainText(FIRST + " " + SECOND)
                cursor = w.review.editor.text.textCursor()
                cursor.setPosition(len(FIRST))
                w.review.editor.text.setTextCursor(cursor)
                click(w.review.buttons["split"])
                assert len(w.project.script.lines) == 2
                assert w.project.script_valid
                w.review.rows.setCurrentRow(1)
                w.review.rows.scrollToItem(w.review.rows.item(1))
                w.preview.audio.setVolume(0)
                click(w.review.editor.play_button)
                result["checks"].append(
                    "prepare manual draft, inline Vietnamese edit, split and validation"
                )
                stage = 2
            elif stage == 2 and not w.preview.video.frame_image.isNull():
                assert abs(w.preview.player.position() - w.project.script.lines[1].start_ms) < 1000
                w.preview.player.pause()
                result["checks"].append(
                    "selected script line plays actual source video at its timestamp"
                )
                write_srt(
                    args.output_dir / "manual-script.srt", w.project.script, w.project.duration_ms
                )
                exported = read_srt(args.output_dir / "manual-script.srt")
                assert [line.text for line in exported.lines] == [FIRST, SECOND]
                assert not w.review.approve_button.isEnabled()
                click(w.review.review_checkbox)
                assert w.review.approve_button.isEnabled()
                click(w.review.approve_button)
                approved_hash = w.project.require_approval()
                assert w.project.state == "APPROVED"
                assert not w.review.editor.voice_button.isEnabled()
                w.grab().save(str(args.output_dir / "review-approved.png"))
                assert w.save_to(args.output_dir / "approved.vkdub")
                assert w.open_project(args.output_dir / "approved.vkdub")
                result["checks"].append(
                    "SRT roundtrip and explicit approval; voice/export remain unavailable"
                )
                stage = 3
            elif stage == 3 and not w.busy:
                assert w.project.require_approval() == approved_hash
                assert w.project.transcript == original_source
                w.review.editor.text.moveCursor(QTextCursor.MoveOperation.End)
                QTest.keyClicks(w.review.editor.text, "!")
                assert w.project.state == "REVIEW_REQUIRED"
                assert w.project.approved_revision_hash is None
                assert not w.review.review_checkbox.isChecked()
                assert not w.review.approve_button.isEnabled()
                result["checks"].append(
                    "approval survives reload; a single typed character revokes it immediately"
                )
                click(w.review.buttons["undo"])
                assert not w.project.is_approved
                assert w.project.revision_hash == approved_hash
                w.review.editor.text.setPlainText("")
                assert not w.review.review_checkbox.isEnabled()
                assert not w.project.script_valid
                click(w.review.buttons["undo"])
                assert w.project.script_valid
                assert not w.project.is_approved
                assert w.project.transcript == original_source
                assert w.save_to(args.output_dir / "review-required.vkdub")
                w.review.rows.setCurrentRow(0)
                w.review.rows.scrollToItem(w.review.rows.item(0))
                w.preview.player.play()
                result["checks"].append(
                    "undo never restores approval; blank text blocks approval; source preserved"
                )
                stage = 4
            elif stage == 4 and not w.preview.video.frame_image.isNull():
                w.preview.player.pause()
                w.play_script_line(1000, 1300)
                stage = 5
            elif (
                stage == 5
                and w.preview.player.position() >= 1300
                and w.preview.player.playbackState() == QMediaPlayer.PlaybackState.PausedState
            ):
                result["checks"].append("script playback pauses at the selected end time")
                w.grab().save(str(args.output_dir / "review-required.png"))
                finish()
        except Exception:
            finish(traceback.format_exc())

    timer.timeout.connect(tick)
    timer.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
