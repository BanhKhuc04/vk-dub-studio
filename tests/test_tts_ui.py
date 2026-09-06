import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from PySide6.QtWidgets import QMessageBox

from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.domain.voice import (
    DEFAULT_LABEL,
    DEFAULT_VOICE,
    Voice,
    VoiceAsset,
    VoiceSettings,
    audio_key,
    digest,
)
from vkdub.services.credential_service import CredentialStore, VbeeAppStore, VbeeTokenStore
from vkdub.services.tts_service import file_hash
from vkdub.ui.main_window import MainWindow


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("vkdub.media.process.MediaTools.detect", lambda self: None)
    window = MainWindow()
    window.legacy_tts_enabled = True
    window.tts.read_credentials()
    window.tools.paths.update(ffmpeg="ffmpeg", ffprobe="ffprobe")
    window.tools_ready = True
    window.project = Project(
        voice=VoiceSettings(),
        video_path=tmp_path / "source.mp4",
        video_duration_ms=10000,
        script=ScriptDocument((ScriptLine(str(uuid4()), 0, 10000, "Xin chào"),)),
    )
    window.review_controller.bind_project()
    window.show()
    qtbot.addWidget(window)
    yield window
    if window.tts.job:
        window.tts.stop()
        qtbot.waitUntil(lambda: window.tts.job is None)
    window.dirty = False
    window.close()


def configured(window, monkeypatch):
    monkeypatch.setattr(VbeeAppStore, "get", lambda self: "test-app")
    monkeypatch.setattr(VbeeTokenStore, "get", lambda self: "test-token")
    window.tts.read_credentials()
    window._refresh()


def test_missing_credentials_keeps_draft_editable(window):
    assert window.tts.panel.voice.currentText() == DEFAULT_LABEL
    assert window.tts.panel.voice.currentData() == DEFAULT_VOICE
    window.review.review_checkbox.setChecked(True)
    assert window.review_controller.approve()
    assert window.project.is_approved and window.tts.job is None
    assert not window.review.editor.voice_button.isEnabled()
    assert not window.tts.panel.retry.isEnabled()
    assert window.review.editor.text.isEnabled()
    assert "Thiếu App ID" in window.review.voice_note.text()
    assert not window.review.export_button.isEnabled()


def test_backend_approval_gate_never_launches(window, monkeypatch):
    configured(window, monkeypatch)
    assert not window.tts.start()
    assert window.tts.job is None


def test_approve_launches_worker_and_edit_invalidates_audio(window, qtbot, tmp_path, monkeypatch):
    configured(window, monkeypatch)
    observed = []

    async def generate(
        project, provider, root, ffmpeg, ffprobe, progress, cancel, complete, line_ids, force
    ):
        observed.append(project.require_approval())
        await asyncio.sleep(0.05)
        line = project.script.lines[0]
        path = tmp_path / "test.wav"
        path.write_bytes(b"unit fixture only")
        asset = VoiceAsset(
            audio_key(line.text, project.voice),
            digest(line.text),
            "vbee",
            DEFAULT_VOICE,
            1.0,
            12000,
            path,
            file_hash(path),
            datetime.now(UTC).isoformat(),
        )
        complete(line.id, asset, "")

    monkeypatch.setattr("vkdub.ui.tts_controller.generate_voice", generate)
    window.review.review_checkbox.setChecked(True)
    assert window.review_controller.approve()
    assert window.workflow_state == "GENERATING_VOICE"
    assert not window.review.editor.text.isEnabled()
    qtbot.waitUntil(lambda: window.tts.job is None)
    assert observed and window.project.voice_ready
    assert "quá dài" in window.review.editor.voice_status.text()
    assert window.review.editor.listen_button.isEnabled()
    assert window.review.export_button.isEnabled()
    window.review.editor.text.setPlainText("Xin chào!")
    assert not window.project.is_approved and not window.project.voice_ready
    assert not window.review.export_button.isEnabled()
    assert not window.review.editor.voice_button.isEnabled()
    assert not window.review.editor.listen_button.isEnabled()
    window.review_controller.undo()
    assert not window.project.is_approved


def test_cancel_preserves_script_and_unlocks_editor(window, qtbot, monkeypatch):
    configured(window, monkeypatch)
    original = window.project.script

    async def generate(*args):
        await asyncio.sleep(30)

    monkeypatch.setattr("vkdub.ui.tts_controller.generate_voice", generate)
    window.project.approve(True)
    assert window.tts.start()
    window.tts.stop()
    qtbot.waitUntil(lambda: window.tts.job is None)
    assert window.project.script == original and window.project.is_approved
    assert window.review.editor.text.isEnabled()
    assert not window.project.voice_ready


def test_connection_does_not_synthesize(window, qtbot, monkeypatch):
    configured(window, monkeypatch)
    calls = []

    async def voices(self):
        calls.append("voices")
        return (Voice(DEFAULT_VOICE, DEFAULT_LABEL, "vi-VN"),)

    monkeypatch.setattr("vkdub.providers.vbee_tts.VbeeTTSProvider.list_voices", voices)
    window.tts.open_manager()
    assert window.tts.test_connection()
    qtbot.waitUntil(lambda: window.tts.job is None)
    assert calls == ["voices"] and not window.project.voice_assets
    assert "Kết nối đã kiểm tra" in window.tts.dialog.status.text()


def test_voice_speed_and_volume_controls(window):
    window.tts.panel.speed.setValue(1.25)
    window.tts.panel.volume.setValue(35)
    assert window.project.voice.speed == 1.25 and window.project.voice.volume == 0.35
    assert abs(window.tts.audio.volume() - 0.35) < 0.001


def test_vbee_vault_accounts_do_not_replace_gemini():
    class Vault:
        def __init__(self):
            self.values = {}

        def get_password(self, service, account):
            return self.values.get((service, account))

        def set_password(self, service, account, value):
            self.values[service, account] = value

        def delete_password(self, service, account):
            del self.values[service, account]

    vault = Vault()
    gemini, app, token = CredentialStore(vault), VbeeAppStore(vault), VbeeTokenStore(vault)
    gemini.save("gemini-test")
    app.save("app-test")
    token.save("token-test")
    # Call base getter explicitly because autouse fixture blocks live Vbee reads.
    assert CredentialStore.get(app) == "app-test"
    assert CredentialStore.get(token) == "token-test"
    assert gemini.get() == "gemini-test"


def test_missing_tools_never_synthesizes(window, monkeypatch):
    configured(window, monkeypatch)
    window.project.approve(True)
    window.tools.paths["ffprobe"] = None
    window._refresh()
    assert not window.tts.start()
    assert not window.review.editor.voice_button.isEnabled()
    assert "ffprobe" in window.tts.panel.status.text()


def test_left_panel_voice_and_speed_sync(window):
    window.left.speed_combo.setCurrentIndex(0)  # 0.8x
    assert window.project.voice.speed == 0.8
    assert window.tts.panel.speed.value() == 0.8

    window.tts.panel.speed.setValue(1.2)
    assert window.project.voice.speed == 1.2
    assert abs(window.left.speed_combo.currentData() - 1.2) < 0.01


def test_pipeline_status_reflects_voice_generation(window, qtbot, tmp_path, monkeypatch):
    configured(window, monkeypatch)

    async def generate(
        project, provider, root, ffmpeg, ffprobe, progress, cancel, complete, line_ids, force
    ):
        await asyncio.sleep(0.05)
        line = project.script.lines[0]
        path = tmp_path / "test.wav"
        path.write_bytes(b"unit fixture only")
        asset = VoiceAsset(
            audio_key(line.text, project.voice),
            digest(line.text),
            "vbee",
            DEFAULT_VOICE,
            1.0,
            10000,
            path,
            file_hash(path),
            datetime.now(UTC).isoformat(),
        )
        complete(line.id, asset, "")

    monkeypatch.setattr("vkdub.ui.tts_controller.generate_voice", generate)
    window.review.review_checkbox.setChecked(True)
    assert window.review_controller.approve()
    assert window.workflow_state == "GENERATING_VOICE"
    assert "● Voice" in window.left.status_voice.text()

    qtbot.waitUntil(lambda: window.tts.job is None)
    assert window.project.voice_ready
    assert "✓ Voice" in window.left.status_voice.text()


def test_preview_voice_button_triggers_listen(window, monkeypatch):
    called = []
    monkeypatch.setattr(window.tts, "listen", lambda: called.append("listen"))
    window.preview.preview_voice_requested.emit()
    assert called == ["listen"]


def test_listen_plays_when_editor_not_open(window, qtbot, tmp_path):
    window.review._remove_editor()
    assert window.review.editor is None

    line = window.project.script.lines[0]
    path = tmp_path / "dummy.wav"
    path.write_bytes(b"audio content")
    asset = VoiceAsset(
        audio_key(line.text, window.project.voice),
        digest(line.text),
        "vbee",
        DEFAULT_VOICE,
        1.0,
        5000,
        path,
        file_hash(path),
        datetime.now(UTC).isoformat(),
    )
    window.project.voice_assets[line.id] = asset
    window.project.approve(True)

    window.tts.listen()
    qtbot.waitUntil(lambda: window.tts.job is None)
    assert "dummy.wav" in window.tts.player.source().toString()
