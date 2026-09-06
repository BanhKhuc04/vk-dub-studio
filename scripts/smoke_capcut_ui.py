"""Run the native app through its CapCut export CTA and capture the simplified UI."""

import json
import os
import time
import traceback
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QTimer

from vkdub.app import create_application
from vkdub.domain.mask import MaskItem
from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.domain.voice import VoiceAsset, VoiceSettings
from vkdub.services.app_settings import AppSettings, load_app_settings, save_app_settings
from vkdub.ui.main_window import MainWindow


def main() -> int:
    output = Path("docs/evidence/capcut-export/native-ui").resolve()
    output.mkdir(parents=True, exist_ok=True)
    installed = load_app_settings()
    voice_meta = json.loads(
        next(
            Path("docs/evidence/two-voice-engines/native-final/app-data/cache/tts").glob("*.json")
        ).read_text(encoding="utf-8")
    )
    os.environ["VKDUB_DATA_DIR"] = str(output / "app-data")
    draft_root = output / "drafts"
    draft_root.mkdir(exist_ok=True)
    save_app_settings(
        AppSettings(
            wizard_completed=True,
            auto_update=False,
            gemini_model=installed.gemini_model,
            vieneu_runtime=installed.vieneu_runtime,
            capcut_draft_root=str(draft_root),
            selected_voice=voice_meta["voice_id"],
        )
    )
    app = create_application()
    window = MainWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    window.show()
    result = {"passed": False, "platform": app.platformName(), "ticks": 0}
    stage, started = 0, time.monotonic()
    timer = QTimer()

    def finish(error=None):
        timer.stop()
        result["passed"] = error is None
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
        result["steps"] = [
            widget.text()
            for widget in (
                window.left.status_video,
                window.left.status_stt,
                window.left.status_trans,
                window.left.status_review,
                window.left.status_voice,
                window.left.status_export,
            )
        ]
        result["log"] = window.left.logs.toPlainText().splitlines()[-5:]
        if error:
            result["error"] = error
        (output / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        window.grab().save(str(output / "final.png"))
        print(json.dumps(result, ensure_ascii=True), flush=True)
        window.dirty = False
        window.close()
        app.exit(1 if error else 0)

    def tick():
        nonlocal stage
        result["ticks"] += 1
        try:
            if time.monotonic() - started > 60:
                raise TimeoutError(f"stage {stage}")
            if stage == 0:
                if not window.tools_ready or window.health_job is not None:
                    return
                line = ScriptLine(str(uuid4()), 0, 5000, "Xin chào, chúc bạn một ngày tốt lành.")
                voice = VoiceSettings(
                    voice_meta["provider"], voice_meta["voice_id"], "Nhỏ Ngọt Ngào", 1, 1
                )
                project = Project(
                    video_path=Path("docs/evidence/media/sample.mp4").resolve(),
                    video_duration_ms=7908,
                    script=ScriptDocument((line,)),
                    voice=voice,
                    masks=[MaskItem(x=0.2, y=0.7, width=0.5, height=0.15)],
                )
                project.approve(True)
                project.voice_assets[line.id] = VoiceAsset(
                    voice_meta["cache_key"],
                    voice_meta["text_hash"],
                    voice_meta["provider"],
                    voice_meta["voice_id"],
                    voice_meta["speed"],
                    voice_meta["duration_ms"],
                    Path(voice_meta["output_path"]),
                    voice_meta["audio_sha256"],
                    voice_meta["generated_at"],
                )
                window.project = project
                window.review_controller.bind_project()
                window._refresh()
                assert window.workflow_state == "VOICE_READY"
                assert window.left.export_video_button.isVisible()
                assert window.left.export_capcut_button.isVisible()
                assert window.left.logs.isVisible()
                window.grab().save(str(output / "before.png"))
                window.left.export_capcut_button.click()
                assert window.capcut_export.job is not None
                stage = 1
            elif stage == 1 and window.capcut_export.job is None:
                exported = window.capcut_export.last_result
                assert exported and exported.path.is_dir()
                assert exported.omitted_blur_count == 0
                assert exported.applied_mask_count == 1
                assert window.left.open_capcut_button.isVisible()
                assert "Đã tạo project CapCut" in window.left.logs.toPlainText()
                result["draft"] = str(exported.path)
                finish()
        except Exception:
            finish(traceback.format_exc())

    timer.timeout.connect(tick)
    timer.start(50)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
