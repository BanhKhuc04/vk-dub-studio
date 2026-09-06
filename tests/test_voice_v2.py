import asyncio
import json
import wave
from uuid import uuid4

import pytest
from PySide6.QtWidgets import QMessageBox

from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.domain.voice import VoiceSettings
from vkdub.providers.gemini_translation import ProviderError
from vkdub.services.app_settings import load_app_settings, save_app_settings
from vkdub.services.health_service import check_gemini_generation, check_tts_backend
from vkdub.services.voice_catalog import (
    catalog_path,
    delete_voice,
    engine_python,
    engine_root,
    install_presets,
    read_catalog,
    rename_voice,
    save_catalog,
)
from vkdub.ui.add_voice_dialog import AddVoiceDialog
from vkdub.ui.main_window import MainWindow


def test_generation_probe_detects_failure_that_metadata_cannot(monkeypatch):
    async def rejected(self, request):
        raise ProviderError("Gemini HTTP 404: Model không tạo nội dung được.")

    monkeypatch.setattr(
        "vkdub.providers.gemini_translation.GeminiTranslationProvider.translate", rejected
    )
    result = check_gemini_generation("gemini-2.5-flash-lite", "test-key")
    assert not result.ok and "404" in result.message
    assert result.action_id == "open_settings_ai"


def test_generation_probe_rejects_wrong_segment_id(monkeypatch):
    async def invalid(self, request):
        return {"segments": [{"id": 2, "translation": "Sai câu"}]}

    monkeypatch.setattr(
        "vkdub.providers.gemini_translation.GeminiTranslationProvider.translate", invalid
    )
    assert not check_gemini_generation("gemini-3.5-flash", "test-key").ok


def test_voice_catalog_unicode_restart_rename_delete_preserves_source(tmp_path):
    reference = tmp_path / "voice.wav"
    reference.write_bytes(b"owned-original")
    custom = {
        "id": "custom-test",
        "name": "Giọng của tôi",
        "custom": True,
        "reference": str(reference),
        "profile": str(tmp_path / "profile.json"),
    }
    save_catalog([custom])
    rows = install_presets([["Giọng Bắc — Nữ", "upstream_unicode_đ"]])
    assert len(rows) == 2 and read_catalog() == rows
    rename_voice("custom-test", "Tên mới tiếng Việt")
    assert read_catalog()[0]["name"] == "Tên mới tiếng Việt"
    delete_voice("custom-test")
    assert len(read_catalog()) == 1 and reference.read_bytes() == b"owned-original"
    with pytest.raises(ValueError):
        delete_voice(rows[1]["id"])
    assert install_presets([["Giọng Bắc — Nữ", "upstream_unicode_đ"]])[0]["id"] == rows[1]["id"]


def test_broken_catalog_is_not_silently_overwritten():
    path = catalog_path()
    path.parent.mkdir(parents=True)
    path.write_text("broken", encoding="utf-8")
    with pytest.raises(ValueError):
        install_presets([["Voice", "id"]])
    assert path.read_text() == "broken"


def test_voice_add_dialog_requires_name_file_and_rights(qtbot, tmp_path):
    parent = QMessageBox()
    qtbot.addWidget(parent)
    dialog = AddVoiceDialog(parent)
    qtbot.addWidget(dialog)
    ref = tmp_path / "sample.wav"
    ref.write_bytes(b"test")
    dialog.name_input.setText("Giọng của tôi")
    dialog.reference_input.setText(str(ref))
    dialog.validate_and_accept()
    assert dialog.result() != dialog.DialogCode.Accepted
    dialog.rights.setChecked(True)
    dialog.validate_and_accept()
    assert dialog.result() == dialog.DialogCode.Accepted


@pytest.fixture
def local_window(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr("vkdub.media.process.MediaTools.detect", lambda self: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard)
    rows = install_presets([["Verified test fixture", "fixture"]])
    python = engine_python()
    python.parent.mkdir(parents=True)
    python.touch()
    (engine_root() / "models").mkdir()
    (engine_root() / "models" / "fixture.onnx").write_bytes(b"test")
    (engine_root() / "ready.json").write_text(
        json.dumps(
            {
                "duration_ms": 1000,
                "version": "3.5.0",
                "model_files": [{"path": "models/fixture.onnx", "size": 4}],
            }
        )
    )
    settings = load_app_settings()
    settings.selected_voice = rows[0]["id"]
    save_app_settings(settings)
    window = MainWindow()
    qtbot.addWidget(window)
    window.tools.paths.update(ffmpeg="test-ffmpeg", ffprobe="test-ffprobe")
    window.project = Project(
        video_path=tmp_path / "source.mp4",
        video_duration_ms=6000,
        script=ScriptDocument((ScriptLine(str(uuid4()), 0, 3000, "Xin chào"),)),
        voice=VoiceSettings(
            provider="vieneu_local", voice_id=rows[0]["id"], display_name=rows[0]["name"]
        ),
    )
    window.review_controller.bind_project()
    window.show()
    yield window
    if window.tts.job:
        window.tts.stop()
        qtbot.waitUntil(lambda: window.tts.job is None)
    window.dirty = False


def test_local_approve_gate_dispatch_and_cancel(local_window, qtbot, monkeypatch):
    entered = []

    async def generation(
        project, provider, root, ffmpeg, ffprobe, progress, check_cancel, completed, *args
    ):
        entered.append(project.require_approval())
        await asyncio.sleep(60)

    monkeypatch.setattr("vkdub.ui.studio_voice_controller.generate_voice", generation)
    assert not local_window.tts.start()
    assert not entered
    local_window.review.review_checkbox.setChecked(True)
    local_window.left.process_button.click()
    qtbot.waitUntil(lambda: bool(entered))
    assert local_window.project.is_approved and local_window.busy
    assert not local_window.left.voice_combo.isEnabled()
    local_window.tts.stop()
    qtbot.waitUntil(lambda: local_window.tts.job is None)
    assert not local_window.busy and not local_window.project.voice_assets


def test_local_preview_without_approval_uses_audio_file(local_window, qtbot, monkeypatch):
    async def synthesize(self, text, voice_id, speed, output_path):
        with wave.open(str(output_path), "wb") as wav:
            wav.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
            wav.writeframes(b"\x01\x00" * 48000)
        return output_path

    async def duration(*args):
        return 1000

    monkeypatch.setattr("vkdub.providers.vieneu_local.VieNeuLocalProvider.synthesize", synthesize)
    monkeypatch.setattr("vkdub.ui.studio_voice_controller.audio_duration", duration)
    assert local_window.tts.preview_voice()
    qtbot.waitUntil(lambda: local_window.tts.job is None)
    assert local_window.tts.last_preview_path.is_file()
    assert not local_window.project.is_approved and not local_window.project.voice_assets
    local_window.tts.player.stop()


def test_missing_runtime_never_reports_ready():
    assert not check_tts_backend("vieneu_local").ok
    assert not check_tts_backend("capcut_tts").ok


def test_missing_model_artifact_invalidates_health(local_window):
    assert check_tts_backend("vieneu_local").ok
    (engine_root() / "models" / "fixture.onnx").unlink()
    assert not check_tts_backend("vieneu_local").ok


def test_selecting_unavailable_capcut_preserves_local_and_can_switch_back(local_window, qtbot):
    local_window.open_settings(2)
    dialog = local_window.settings_dialog
    original = local_window.project.voice
    dialog.voice_backend_combo.setCurrentIndex(1)
    assert dialog.btn_setup_voice.isEnabled()
    assert not dialog.btn_voice_preview.isEnabled()
    assert dialog.voice_list_combo.currentText()  # never an unexplained blank combo
    assert local_window.project.voice == original
    dialog.btn_use_local.click()
    assert dialog.btn_voice_preview.isEnabled()
    assert local_window.tts.can_generate()
    assert load_app_settings().tts_backend == "vieneu_local"
    dialog.close()


def test_saved_capcut_does_not_disable_local_project(local_window):
    settings = load_app_settings()
    settings.tts_backend = "capcut_tts"
    save_app_settings(settings)
    local_window.tts.read_credentials()
    assert local_window.tts.can_generate()


def test_engine_switch_uses_separate_catalog_and_dispatch(local_window, monkeypatch, qtbot):
    from vkdub.providers.capcut_tts import CapCutTTSProvider
    from vkdub.providers.tts_provider import HealthResult

    save_catalog(
        [{"id": "capcut-realfixture", "name": "CapCut fixture", "custom": False}], "capcut_tts"
    )

    def ready(_):
        return HealthResult(True, "TEST", "Fixture", "Ready")

    monkeypatch.setattr("vkdub.ui.settings_dialog.check_tts_backend", ready)
    monkeypatch.setattr("vkdub.ui.studio_voice_controller.check_tts_backend", ready)
    local_window.open_settings(2)
    dialog = local_window.settings_dialog
    dialog.voice_backend_combo.setCurrentIndex(1)
    assert dialog.voice_list_combo.count() == 1
    assert dialog.voice_list_combo.currentText() == "CapCut fixture"
    assert dialog.btn_voice_preview.isEnabled()
    assert dialog.btn_add_voice.isHidden()
    assert local_window.project.voice.provider == "capcut_tts"
    assert load_app_settings().selected_voice == "capcut-realfixture"
    assert isinstance(local_window.tts.provider("capcut_tts"), CapCutTTSProvider)
    entered = []

    async def generation(project, provider, *args):
        entered.append((project.require_approval(), provider.name))

    monkeypatch.setattr("vkdub.ui.studio_voice_controller.generate_voice", generation)
    assert not local_window.tts.start()
    local_window.review.review_checkbox.setChecked(True)
    local_window.left.process_button.click()
    qtbot.waitUntil(lambda: bool(entered) and local_window.tts.job is None)
    assert entered[0][1] == "capcut_tts"
    dialog.btn_use_local.click()
    assert local_window.project.voice.provider == "vieneu_local"
    assert dialog.btn_voice_preview.isEnabled()
    dialog.close()
