"""Native Windows app smoke: real CapCut/VieNeu audio, approval gate and cache."""

import json
import os
import shutil
import time
import traceback
import wave
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QTimer

from vkdub.app import create_application
from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.providers.capcut_tts import CapCutTTSProvider
from vkdub.services.app_settings import AppSettings, load_app_settings, save_app_settings
from vkdub.services.capcut_setup import capcut_root
from vkdub.services.voice_catalog import read_catalog, save_catalog
from vkdub.ui.main_window import MainWindow


def main() -> int:
    output = Path("docs/evidence/two-voice-engines/native-final").resolve()
    output.mkdir(parents=True, exist_ok=True)
    installed = load_app_settings()
    local, capcut = read_catalog(), read_catalog("capcut_tts")
    sdk = capcut_root()
    os.environ["VKDUB_DATA_DIR"] = str(output / "app-data")
    save_app_settings(
        AppSettings(
            wizard_completed=True,
            auto_update=False,
            vieneu_runtime=installed.vieneu_runtime,
            gemini_model=installed.gemini_model,
            selected_voice=local[0]["id"],
            voice_volume=0,
        )
    )
    save_catalog(local)
    save_catalog(capcut, "capcut_tts")
    shutil.copytree(sdk, capcut_root(), dirs_exist_ok=True)
    calls = []
    original = CapCutTTSProvider.synthesize

    async def measured(self, text, voice_id, speed, path):
        calls.append(text)
        return await original(self, text, voice_id, speed, path)

    CapCutTTSProvider.synthesize = measured
    app = create_application()
    window = MainWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    window.show()
    result = {"passed": False, "platform": app.platformName(), "checks": [], "ticks": 0}
    stage, started = 0, time.monotonic()
    timer = QTimer()

    def audio(path, label):
        with wave.open(str(path)) as wav:
            seconds = wav.getnframes() / wav.getframerate()
            assert seconds > 0.2
            result[label] = {"seconds": seconds, "rate": wav.getframerate()}
        shutil.copyfile(path, output / f"{label}.wav")

    def finish(error=None):
        timer.stop()
        result.update(
            passed=error is None,
            elapsed=round(time.monotonic() - started, 2),
            capcut_synthesis_calls=len(calls),
        )
        if error:
            result["error"] = error
        (output / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=True), flush=True)
        window.dirty = False
        window.close()
        app.exit(1 if error else 0)

    def tick():
        nonlocal stage
        result["ticks"] += 1
        try:
            if time.monotonic() - started > 180:
                raise TimeoutError(f"stage {stage}")
            if window.busy or window.tts.job:
                return
            if stage == 0:
                if not window.tools_ready or window.health_job is not None:
                    return
                window.open_settings(2)
                dialog = window.settings_dialog
                assert dialog.voice_list_combo.count() == 20
                dialog.voice_backend_combo.setCurrentIndex(1)
                assert dialog.voice_list_combo.count() == 24
                assert dialog.btn_voice_preview.isEnabled()
                assert dialog.btn_add_voice.isHidden()
                assert window.project.voice.provider == "capcut_tts"
                dialog.grab().save(str(output / "capcut-settings.png"))
                dialog.btn_voice_preview.click()
                stage = 1
            elif stage == 1:
                audio(window.tts.last_preview_path, "capcut-preview")
                assert not window.project.is_approved
                result["checks"].append("real CapCut preview before approval")
                window.project = Project(
                    video_path=Path("docs/evidence/media/sample.mp4").resolve(),
                    video_duration_ms=6000,
                    script=ScriptDocument(
                        (
                            ScriptLine(
                                str(uuid4()), 0, 5000, "Xin chào, chúc bạn một ngày tốt lành."
                            ),
                        )
                    ),
                    voice=window.project.voice,
                )
                window.review_controller.bind_project()
                assert not window.tts.start()
                window.review.review_checkbox.setChecked(True)
                window.left.process_button.click()
                stage = 2
            elif stage == 2:
                assert window.project.voice_ready, window.tts.errors
                assert len(calls) == 2
                result["checks"].append("real CapCut generation only after approval")
                window.tts.start()
                stage = 3
            elif stage == 3:
                assert len(calls) == 2
                result["checks"].append("repeat generation reuses verified audio cache")
                dialog = window.settings_dialog
                dialog.btn_use_local.click()
                assert window.project.voice.provider == "vieneu_local"
                assert dialog.voice_list_combo.count() == 20
                assert dialog.btn_voice_preview.isEnabled()
                assert load_app_settings().tts_backend == "vieneu_local"
                dialog.grab().save(str(output / "vieneu-settings.png"))
                dialog.btn_voice_preview.click()
                stage = 4
            elif stage == 4:
                audio(window.tts.last_preview_path, "vieneu-preview")
                result["checks"].append(
                    "switch to VieNeu persists and creates real offline preview"
                )
                finish()
        except Exception:
            finish(traceback.format_exc())

    timer.timeout.connect(tick)
    timer.start(50)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
