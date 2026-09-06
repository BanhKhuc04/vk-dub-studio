"""Native Phase 3 smoke: no network requests, no real API credentials required.

Credential persistence uses a disposable, non-secret marker in a unique Windows vault
entry and a second interpreter, then removes that entry. No production key is changed.
"""

import argparse
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QTimer

from vkdub.app import create_application
from vkdub.services.credential_service import CredentialStore
from vkdub.ui.main_window import MainWindow


def verify_vault():
    store = CredentialStore()
    store.service = f"VKDubStudio-Smoke-{uuid.uuid4()}"
    marker = "non-secret-smoke-marker"
    try:
        store.save(marker)
        code = (
            "import sys; from vkdub.services.credential_service import CredentialStore; "
            "s=CredentialStore(); s.service=sys.argv[1]; "
            "sys.exit(0 if s.get() == 'non-secret-smoke-marker' else 1)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code, store.service],
            timeout=20,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        assert result.returncode == 0, "Credential restart test failed"
    finally:
        store.delete()
    assert store.get() is None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--hold", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    verify_vault()
    app = create_application()
    window = MainWindow()
    window.show()
    timer = QTimer()
    timer.setInterval(100)
    started = time.monotonic()
    stage = 0
    result = {
        "passed": False,
        "live_gemini_called": False,
        "windows_credential_restart_and_cleanup": True,
        "checks": [],
    }

    def finish(error=None):
        timer.stop()
        result["passed"] = error is None
        if error:
            result["error"] = str(error)
        (args.output_dir / "api-smoke-result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=True), flush=True)
        if not args.hold or error:
            if window.translation.dialog:
                window.translation.dialog.reject()
            window.dirty = False
            window.close()
            app.exit(1 if error else 0)

    def tick():
        nonlocal stage
        try:
            if time.monotonic() - started > 30:
                raise TimeoutError("API smoke timed out")
            if stage == 0 and window.tools_ready:
                assert window.open_project(args.project)
                stage = 1
            elif stage == 1 and not window.busy:
                assert window.project.transcript and window.project.transcript.segments
                assert window.project.translation is None
                assert window.left.translate_button.isEnabled()
                assert not window.review.approve_button.isEnabled()
                assert not window.review.export_button.isEnabled()
                window.left.configuration_scroll.verticalScrollBar().setValue(
                    window.left.configuration_scroll.verticalScrollBar().maximum()
                )
                result["checks"].append(
                    "legacy source project opened; translation available; approval/export disabled"
                )
                window.preview.audio.setVolume(0)
                window.preview.player.play()
                stage = 2
            elif stage == 2 and not window.preview.video.frame_image.isNull():
                window.preview.player.pause()
                window.grab().save(str(args.output_dir / "phase3-window.png"))
                window.translation.open_manager()
                stage = 3
            elif stage == 3:
                dialog = window.translation.dialog
                assert dialog and dialog.isVisible()
                assert dialog.table.rowCount() == 4
                assert dialog.table.columnCount() == 7
                assert not dialog.key_input.text()
                assert "Chưa triển khai" in dialog.table.item(2, 6).text()
                assert "Tháng" in dialog.usage.text()
                dialog.grab().save(str(args.output_dir / "api-manager.png"))
                result["checks"].append(
                    "native API/cost dialog, usage, pricing, password field; deferred stages"
                )
                result["credential_status"] = dialog.credential_status
                finish()
        except Exception as exc:
            finish(exc)

    timer.timeout.connect(tick)
    timer.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
