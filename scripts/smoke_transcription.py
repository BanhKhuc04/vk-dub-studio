"""Real offline CPU transcription, cache, cancellation and persistence smoke test."""

import argparse
import json
import time
import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest

from vkdub.app import create_application
from vkdub.domain.transcript import to_srt
from vkdub.ui.main_window import MainWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default="tiny")
    parser.add_argument("--language", default="en")
    parser.add_argument("--expect-text", default="")
    parser.add_argument("--hold", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    app = create_application()
    window = MainWindow()
    window.show()
    started = time.monotonic()
    stage = 0
    ticks_during_job = 0
    previous = None
    cached = []
    cancelled = []
    failures = []
    result = {"checks": [], "passed": False}
    timer = QTimer()
    timer.setInterval(50)

    def finish(error=None):
        timer.stop()
        result["passed"] = error is None
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
        result["responsive_timer_ticks"] = ticks_during_job
        if error:
            result["failure"] = error
        window.grab().save(str(args.output_dir / "transcription-window.png"))
        (args.output_dir / "transcription-result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=True), flush=True)
        if not args.hold or error:
            if window.transcription.job:
                window.transcription.stop()
                window.transcription.job.wait(7000)
                app.processEvents()
            window.dirty = False
            window.close()
            app.exit(1 if error else 0)

    def monitor():
        job = window.transcription.job
        assert job is not None
        job.failed.connect(failures.append)
        return job

    def cancel_on_inference(percent, message):
        if "Đang nạp model" in message:
            window.transcription.stop()

    def tick():
        nonlocal stage, ticks_during_job, previous
        try:
            assert not window.review.approve_button.isEnabled()
            assert not window.review.export_button.isEnabled()
            if failures:
                raise RuntimeError(failures)
            if time.monotonic() - started > 240:
                raise TimeoutError(f"Transcription smoke timed out in stage {stage}")
            if window.transcription.job:
                ticks_during_job += 1
            if stage == 0 and window.tools_ready:
                assert all(window.tools.paths.values())
                assert window.import_video(args.video)
                stage = 1
            elif stage == 1 and not window.busy:
                window.left.model_selector.setCurrentText(args.model)
                window.left.configuration_scroll.ensureWidgetVisible(window.left.model_selector)
                window.left.device_selector.setCurrentIndex(
                    window.left.device_selector.findData("cpu")
                )
                index = window.left.source_language.findData(args.language)
                assert index >= 0
                window.left.source_language.setCurrentIndex(index)
                window.left.reuse_cache.setChecked(False)
                assert window.transcription.start(), "Install the requested model first"
                monitor()
                stage = 2
            elif stage == 2 and not window.busy:
                transcript = window.project.transcript
                assert transcript is not None and transcript.segments
                text = " ".join(segment.text for segment in transcript.segments)
                assert args.expect_text.casefold() in text.casefold()
                assert window.project.state == "TRANSCRIBED"
                assert window.review.rows.count() == len(transcript.segments)
                assert ticks_during_job >= 3
                result["checks"].append(
                    "real offline CPU inference; responsive GUI; source transcript rows"
                )
                result["transcript"] = transcript.to_dict()
                (args.output_dir / "source-transcript.srt").write_text(
                    to_srt(transcript), encoding="utf-8"
                )
                previous = transcript
                window.left.reuse_cache.setChecked(True)
                assert window.transcription.start()
                monitor().succeeded.connect(lambda data: cached.append(data.get("reused")))
                stage = 3
            elif stage == 3 and not window.busy:
                assert cached == [True]
                assert window.project.transcript == previous
                result["checks"].append("cache reuse returns identical transcript")
                window.left.reuse_cache.setChecked(False)
                assert window.transcription.start()
                job = monitor()
                job.cancelled.connect(lambda: cancelled.append(True))
                job.progress.connect(cancel_on_inference)
                stage = 4
            elif stage == 4 and not window.busy:
                assert cancelled == [True]
                assert window.project.transcript == previous
                result["checks"].append("cancel at model loading preserves previous transcript")
                assert window.set_output_directory(args.output_dir)
                project_file = args.output_dir / "transcription.vkdub"
                assert window.save_to(project_file)
                assert window.open_project(project_file)
                stage = 5
            elif stage == 5 and not window.busy and window.preview.play_button.isEnabled():
                assert window.project.transcript == previous
                assert window.review.rows.count() == len(previous.segments)
                result["checks"].append("project save/load preserves transcript and settings")
                window.preview.audio.setMuted(True)
                window.preview.player.play()
                stage = 6
            elif stage == 6 and not window.preview.video.frame_image.isNull():
                window.preview.player.pause()
                item = window.review.rows.item(min(1, window.review.rows.count() - 1))
                window.review.rows.scrollToItem(item)
                QTest.mouseClick(
                    window.review.rows.viewport(),
                    Qt.MouseButton.LeftButton,
                    pos=window.review.rows.visualItemRect(item).center(),
                )
                result["seek_target_ms"] = item.data(Qt.ItemDataRole.UserRole)
                stage = 7
            elif (
                stage == 7
                and abs(window.preview.player.position() - result["seek_target_ms"]) < 250
            ):
                result["checks"].append(
                    "clicking a transcript row seeks video; approval/export remain disabled"
                )
                finish()
        except Exception:
            finish(traceback.format_exc())

    timer.timeout.connect(tick)
    timer.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
