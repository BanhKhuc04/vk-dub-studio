"""Native TTS acceptance using explicit test-tone HTTP fixtures, never a live Vbee account."""

import argparse
import asyncio
import json
import os
import subprocess
import time
import traceback
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest

from vkdub.app import create_application
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.domain.translation import source_digest
from vkdub.domain.voice import DEFAULT_LABEL, DEFAULT_VOICE
from vkdub.providers.vbee_tts import VbeeTTSProvider
from vkdub.services.credential_service import VbeeAppStore, VbeeTokenStore
from vkdub.services.project_service import load_project
from vkdub.services.tts_service import split_text
from vkdub.ui.main_window import MainWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--hold", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    os.environ["VKDUB_DATA_DIR"] = str(args.output_dir / "fixture-data")
    tone = args.output_dir / "test-tone-NOT-SPEECH.mp3"
    subprocess.run(
        [
            os.environ["FFMPEG_PATH"],
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.5",
            "-c:a",
            "libmp3lame",
            "-y",
            str(tone),
        ],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    audio = tone.read_bytes()
    requests = []
    fail_second = True
    stall = False
    credentials = True

    async def handler(request):
        nonlocal fail_second
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "status": 1,
                    "result": {
                        "voices": [
                            {"code": DEFAULT_VOICE, "name": DEFAULT_LABEL, "language_code": "vi-VN"}
                        ],
                        "pagination": {"has_next_page": False, "next_cursor": None},
                    },
                },
            )
        body = json.loads(request.content)
        requests.append(body)
        assert len(body["text"]) <= 300 and body["mode"] == "sync"
        await asyncio.sleep(10 if stall else 0.15)
        if fail_second and body["text"].startswith("Cảm ơn"):
            fail_second = False
            return httpx.Response(503)
        return httpx.Response(200, headers={"content-type": "audio/mpeg"}, content=audio)

    transport = httpx.MockTransport(handler)
    patches = [
        patch.object(VbeeAppStore, "get", lambda self: "smoke-app" if credentials else None),
        patch.object(VbeeTokenStore, "get", lambda self: "smoke-token" if credentials else None),
        patch(
            "vkdub.ui.tts_controller.VbeeTTSProvider",
            lambda app_id, token, usage: VbeeTTSProvider(app_id, token, usage, transport),
        ),
    ]
    for item in patches:
        item.start()
    app = create_application()
    w = MainWindow()
    w.show()
    timer = QTimer()
    timer.setInterval(50)
    started = time.monotonic()
    stage = 0
    ticks = 0
    request_count = 0
    first_id = ""
    original_script = None
    result = {
        "passed": False,
        "checks": [],
        "live_cloud_requests": 0,
        "fixture": "440 Hz test tone through mocked HTTP, NOT Vbee speech",
    }

    def finish(error=None):
        timer.stop()
        result.update(
            passed=error is None,
            elapsed_seconds=round(time.monotonic() - started, 2),
            responsive_timer_ticks=ticks,
            mocked_synthesis_requests=len(requests),
        )
        if error:
            result["error"] = str(error)
        w.grab().save(
            str(args.output_dir / ("failure.png" if error else "missing-credentials.png"))
        )
        (args.output_dir / "tts-result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=True), flush=True)
        if not args.hold or error:
            w.dirty = False
            w.close()
            app.exit(1 if error else 0)

    def tick():
        nonlocal stage, ticks, request_count, first_id, stall, credentials, original_script
        ticks += 1
        try:
            if time.monotonic() - started > 45:
                raise TimeoutError(f"TTS smoke timed out at stage {stage}")
            assert not w.review.export_button.isEnabled()
            if stage == 0 and w.tools_ready:
                assert w.open_project(args.project)
                stage = 1
            elif stage == 1 and not w.busy:
                assert w.project.transcript
                first_id = str(uuid4())
                script = ScriptDocument(
                    (
                        ScriptLine(first_id, 0, 900, "Xin chào. " * 65, (1,)),
                        ScriptLine(str(uuid4()), 1000, 11000, "Cảm ơn bạn.", (1,)),
                    ),
                    source_digest(w.project.transcript),
                )
                w.review_controller.commit(script, "Explicit test-tone fixture")
                original_script = script
                assert not w.tts.start() and not requests
                result["checks"].append("No synthesis before approval")
                assert w.tts.test_connection()
                stage = 2
            elif stage == 2 and not w.busy:
                assert w.tts.verified_codes == {DEFAULT_VOICE}
                QTest.mouseClick(
                    w.review.review_checkbox,
                    Qt.MouseButton.LeftButton,
                    pos=QPoint(10, w.review.review_checkbox.height() // 2),
                )
                assert w.review.approve_button.isEnabled()
                QTest.mouseClick(w.review.approve_button, Qt.MouseButton.LeftButton)
                assert w.workflow_state == "GENERATING_VOICE"
                stage = 3
            elif stage == 3 and not w.busy:
                assert len(w.project.voice_assets) == 1 and w.tts.errors
                assert not w.project.voice_ready
                assert w.project.script == original_script
                result["checks"].append(
                    "Approved worker: split requests, actual decode/ffprobe, "
                    "one failure preserves success"
                )
                request_count = len(requests)
                assert w.tts.start()
                stage = 4
            elif stage == 4 and not w.busy:
                assert w.project.voice_ready and not w.tts.errors
                assert len(requests) == request_count + 1
                assert "quá dài" in w.review.editor.voice_status.text()
                result["checks"].append(
                    "Retry uses completed cache; all lines ready with actual duration warning"
                )
                assert w.save_to(args.output_dir / "test-tone-fixture.vkdub")
                assert load_project(args.output_dir / "test-tone-fixture.vkdub").voice_ready
                result["checks"].append(
                    "Voice metadata/settings and approved revision survive project roundtrip"
                )
                w.log("SMOKE FIXTURE: audio is a 440 Hz test tone, NOT Vbee speech.")
                w.grab().save(str(args.output_dir / "voice-ready-TEST-TONE.png"))
                w.tts.audio.setMuted(True)
                w.tts.listen()
                stage = 5
            elif stage == 5 and not w.busy and w.tts.player.position() > 50:
                assert w.tts.player.error() == QMediaPlayer.Error.NoError
                result["checks"].append(
                    "Qt voice preview opens real assembled WAV and advances playback"
                )
                request_count = len(requests)
                assert w.tts.start(first_id, force=True)
                stage = 6
            elif stage == 6 and not w.busy:
                assert len(requests) == request_count + len(
                    split_text(original_script.lines[0].text)
                )
                assert w.project.voice_ready
                result["checks"].append(
                    "Per-line regeneration bypasses cache without regenerating other lines"
                )
                stall = True
                request_count = len(requests)
                assert w.tts.start(first_id, force=True)
                stage = 7
            elif stage == 7 and len(requests) > request_count:
                w.tts.stop()
                stage = 8
            elif stage == 8 and not w.busy:
                assert w.project.voice_ready and w.project.script == original_script
                assert not list(
                    (args.output_dir / "fixture-data" / "cache" / "tts").glob("voice-*")
                )
                result["checks"].append(
                    "Cancel interrupts waiting and preserves old audio/script; staging removed"
                )
                w.review.editor.text.setPlainText(w.review.editor.text.toPlainText() + "!")
                assert not w.project.is_approved and not w.project.voice_ready
                assert not w.review.editor.voice_button.isEnabled()
                result["checks"].append("One-character edit revokes approval and voice readiness")
                credentials = False
                w.tts.read_credentials()
                w.project.voice_assets.clear()
                w.project.set_script(
                    replace(
                        original_script,
                        lines=(
                            replace(
                                original_script.lines[0], text="Xin chào. Đây là bản nháp kiểm tra."
                            ),
                            original_script.lines[1],
                        ),
                    )
                )
                w.review_controller.bind_project()
                w._refresh()
                w.left.configuration_scroll.ensureWidgetVisible(w.tts.panel)
                stage = 9
            elif stage == 9:
                assert "Thiếu App ID" in w.tts.panel.status.text()
                assert not w.tts.panel.retry.isEnabled()
                assert w.review.editor.text.isEnabled()
                result["checks"].append(
                    "Missing credentials disables synthesis while script stays editable; "
                    "export always disabled"
                )
                finish()
        except Exception:
            finish(traceback.format_exc())

    timer.timeout.connect(tick)
    timer.start()
    code = app.exec()
    for item in reversed(patches):
        item.stop()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
