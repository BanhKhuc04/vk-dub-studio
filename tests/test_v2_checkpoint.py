import json
import threading
from dataclasses import asdict
from uuid import uuid4

import httpx
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from vkdub.domain.mask import MaskItem
from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.domain.voice import VoiceSettings
from vkdub.providers.tts_provider import HealthResult
from vkdub.services.app_settings import AppSettings, load_app_settings, save_app_settings
from vkdub.services.credential_service import CredentialStore
from vkdub.services.health_service import check_capcut_root, check_gemini, check_workspace
from vkdub.services.project_service import load_project, save_project
from vkdub.ui.background_check import BackgroundCheck
from vkdub.ui.main_window import MainWindow
from vkdub.ui.setup_wizard import SetupWizardDialog
from vkdub.utils.paths import data_root, workspace_root


@pytest.mark.parametrize("provider", ["vbee", "elevenlabs"])
def test_schema_five_preserves_legacy_data_without_rewriting(tmp_path, provider):
    project = Project(
        video_path=tmp_path / "old.mp4",
        voice=VoiceSettings(provider=provider),
        script=ScriptDocument((ScriptLine(str(uuid4()), 0, 2000, "Xin chào"),)),
        masks=[MaskItem()],
    )
    project.approve(True)
    path = tmp_path / "old.vkdub"
    save_project(project, path)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["schema_version"] = 5
    document.pop("legacy")
    path.write_text(json.dumps(document), encoding="utf-8")
    original = path.read_bytes()
    loaded = load_project(path)
    assert loaded == project and loaded.is_approved
    assert path.read_bytes() == original
    target = tmp_path / "upgraded.vkdub"
    save_project(loaded, target)
    assert json.loads(target.read_text(encoding="utf-8"))["legacy"] == {"voice_disabled": True}
    assert load_project(target) == loaded


@pytest.mark.parametrize(
    "field,value",
    [
        ("voice_speed", "bad"),
        ("voice_speed", float("nan")),
        ("wizard_completed", "false"),
        ("tts_backend", "unsupported_backend"),
        ("workspace_root", []),
        ("gemini_model", "../../bad"),
        ("auto_update", 1),
    ],
)
def test_invalid_settings_preserve_original_and_allow_repair(field, value):
    path = data_root() / "v2-settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({field: value}), encoding="utf-8")
    original = path.read_bytes()
    assert load_app_settings() == AppSettings()
    assert path.read_bytes() == original
    save_app_settings(AppSettings())
    assert path.with_suffix(".json.bak").read_bytes() == original


def test_workspace_is_used_and_preferences_survive(tmp_path):
    settings = AppSettings(
        source_language="ja",
        voice_speed=1.2,
        auto_update=False,
        workspace_root=str(tmp_path / "workspace"),
        selected_voice="saved-id",
        vieneu_model="user-model",
        wizard_completed=True,
    )
    save_app_settings(settings)
    assert asdict(load_app_settings()) == asdict(settings)
    assert workspace_root() == tmp_path / "workspace"
    assert "API" not in (data_root() / "v2-settings.json").read_text()


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500])
def test_gemini_errors_are_actionable_and_never_echo_secrets(status):
    result = check_gemini(
        "test-model",
        "private-key",
        httpx.MockTransport(
            lambda request: httpx.Response(status, text="private-key provider traceback")
        ),
    )
    assert not result.ok and result.action_id == "open_settings_ai"
    assert "private-key" not in result.message and "traceback" not in result.message


def test_gemini_checks_selected_model_header_timeout_and_structure():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path.endswith("/custom-model")
        assert "key=" not in str(request.url)
        assert request.headers["x-goog-api-key"] == "private-key"
        assert request.extensions["timeout"]["read"] == 8
        return httpx.Response(
            200,
            json={"name": "models/custom-model", "supportedGenerationMethods": ["generateContent"]},
        )

    assert check_gemini("custom-model", "private-key", httpx.MockTransport(handler)).ok

    def timeout(request):
        raise httpx.ReadTimeout("private-key", request=request)

    assert (
        check_gemini("custom-model", "private-key", httpx.MockTransport(timeout)).code
        == "GEMINI_NETWORK_ERROR"
    )
    assert not check_gemini(
        "custom-model",
        "private-key",
        httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    ).ok


def test_directory_probes_never_overwrite_existing_files(tmp_path):
    existing = tmp_path / ".write_test"
    existing.write_text("keep me")
    before = set(tmp_path.iterdir())
    assert check_workspace(str(tmp_path)).ok
    assert check_capcut_root(str(tmp_path)).ok
    assert existing.read_text() == "keep me"
    assert not check_capcut_root(str(existing)).ok
    assert set(tmp_path.iterdir()) == before


def test_background_check_keeps_qt_responsive(qtbot):
    release = threading.Event()
    results, ticks = [], []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(5)
    worker = BackgroundCheck(lambda: release.wait(2))
    worker.succeeded.connect(results.append)
    worker.start()
    try:
        qtbot.waitUntil(lambda: len(ticks) >= 4)
        assert worker.isRunning()
    finally:
        release.set()
    qtbot.waitUntil(lambda: bool(results))
    timer.stop()


@pytest.fixture
def shell(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard)
    save_app_settings(AppSettings(wizard_completed=True, source_language="ja", voice_speed=1.2))
    monkeypatch.setattr("vkdub.media.process.MediaTools.detect", lambda self: None)
    window = MainWindow()
    qtbot.addWidget(window)
    yield window
    window.dirty = False
    window.close()


def test_shell_applies_defaults_and_never_calls_legacy(shell, monkeypatch):
    assert shell.project.source_language == "ja"
    assert shell.left.source_language.currentData() == "ja"
    assert shell.left.speed_combo.currentData() == 1.2
    assert shell.project.voice.provider == "vieneu_local"
    calls = []
    monkeypatch.setattr("vkdub.ui.tts_controller.VbeeTTSProvider", lambda *a: calls.append(a))
    assert not shell.tts.start()
    assert not shell.tts._launch("voice")
    assert calls == []


def test_primary_cta_single_dispatch_and_explicit_review(shell, tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"UI fixture")
    shell.project.video_path = video
    shell.tools_ready = True
    shell.tools.paths["ffmpeg"] = "fixture"
    calls = []
    monkeypatch.setattr(shell.transcription, "start", lambda: calls.append("stt") or True)
    shell._refresh()
    shell.left.process_button.click()
    assert calls == ["stt"]
    shell.busy = True
    shell._refresh()
    assert not shell.left.process_button.isEnabled()
    shell._on_primary_cta_clicked()
    assert calls == ["stt"]
    shell.busy = False
    shell.project.script = ScriptDocument((ScriptLine(str(uuid4()), 0, 2000, "Xin chào"),))
    shell.review_controller.bind_project()
    shell._refresh()
    assert not shell.left.process_button.isEnabled()
    shell._on_primary_cta_clicked()
    assert not shell.project.is_approved and not shell.review.review_checkbox.isChecked()
    shell.review.review_checkbox.setChecked(True)
    assert shell.left.process_button.isEnabled()
    shell.left.process_button.click()
    assert shell.project.is_approved and shell.tts.job is None
    assert not shell.left.process_button.isEnabled()
    assert not shell.review.export_button.isEnabled()
    shell.review.editor.text.setPlainText("Đã sửa")
    assert not shell.project.is_approved and not shell.left.process_button.isEnabled()


def test_first_run_once_restart_silent_and_failure_banner(shell, qtbot, monkeypatch):
    healthy = [HealthResult(True, "TEST_OK", "Test", "Test fixture")]
    monkeypatch.setattr("vkdub.ui.main_window.run_startup_health_checks", lambda *a: healthy)
    settings = load_app_settings()
    settings.wizard_completed = False
    save_app_settings(settings)
    shell._startup_checks()
    assert shell.setup_wizard is not None
    shell.setup_wizard._skip_wizard()
    qtbot.waitUntil(lambda: shell.health_job is None)
    assert load_app_settings().wizard_completed
    assert not shell.health_banner.isVisible()
    shell.setup_wizard = None
    shell._startup_seen = False
    shell._startup_checks()
    qtbot.waitUntil(lambda: shell.health_job is None)
    assert shell.setup_wizard is None
    healthy[:] = [
        HealthResult(False, "INVALID_KEY", "Gemini", "Test failure", "Sửa", "open_settings_ai")
    ]
    shell._startup_checks()
    qtbot.waitUntil(lambda: shell.health_job is None)
    assert not shell.health_banner.isHidden()
    shell.health_banner.action_button.click()
    assert shell.settings_dialog.tabs.currentIndex() == 1


def test_wizard_handles_vault_failure_and_restores_model(qtbot, monkeypatch):
    save_app_settings(AppSettings(gemini_model="gemini-2.5-flash-lite", source_language="ko"))

    def broken(*args):
        raise RuntimeError("vault unavailable")

    monkeypatch.setattr(CredentialStore, "get", broken)
    monkeypatch.setattr(CredentialStore, "save", broken)
    wizard = SetupWizardDialog()
    qtbot.addWidget(wizard)
    assert wizard.gemini_model_combo.currentText() == "gemini-2.5-flash-lite"
    assert wizard.src_lang_combo.currentData() == "ko"
    wizard.gemini_key_input.setText("private-key")
    wizard._next_step()
    assert wizard.stack.currentIndex() == 0
    assert "Không lưu" in wizard.gemini_status_lbl.text()
