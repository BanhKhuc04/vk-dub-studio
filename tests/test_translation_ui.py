import asyncio
import json

import httpx
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from vkdub.domain.transcript import SubtitleSegment, Transcript
from vkdub.domain.translation import Translation, source_digest
from vkdub.providers.gemini_translation import GeminiTranslationProvider
from vkdub.services.cloud_job import CloudJob
from vkdub.ui.main_window import MainWindow


@pytest.fixture
def window(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("vkdub.media.process.find_tool", lambda _: None)
    monkeypatch.setattr("vkdub.services.credential_service.CredentialStore.get", lambda _: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard)
    widget = MainWindow()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitUntil(lambda: widget.tools_ready)
    widget.project.video_path = tmp_path / "source.mp4"
    widget.project.transcript = Transcript(
        (SubtitleSegment(1, 1.5, 3, "Hello world"),),
        "en",
        "en",
        4,
        "tiny",
        "cpu",
        "a" * 64,
        "b" * 64,
    )
    widget.review.show_transcript(widget.project.transcript)
    widget._refresh()
    yield widget
    if widget.translation.job:
        widget.translation.stop()
        qtbot.waitUntil(lambda: widget.translation.job is None)
    if widget.translation.dialog:
        widget.translation.dialog.reject()
    widget.dirty = False
    widget.close()


def mock_transport(monkeypatch, handler):
    def factory(key, recorder, progress, **kwargs):
        return GeminiTranslationProvider(
            key, recorder, progress, httpx.MockTransport(handler), **kwargs
        )

    monkeypatch.setattr("vkdub.ui.translation_controller.GeminiTranslationProvider", factory)
    monkeypatch.setattr(
        "vkdub.services.credential_service.CredentialStore.get", lambda _: "test-key"
    )


def test_no_key_opens_manager_without_fake_success(window):
    assert not window.translation.start()
    dialog = window.settings_dialog
    assert dialog.isVisible()
    assert dialog.tabs.currentIndex() == 1
    assert not window.busy and window.project.translation is None
    assert not window.review.approve_button.isEnabled()
    assert not window.review.export_button.isEnabled()


def test_connection_does_not_test_old_key_while_new_key_is_unsaved(window):
    window.translation.open_manager()
    dialog = window.translation.dialog
    dialog.key_input.setText("unsaved-new-key")
    assert not window.translation.test_connection()
    assert window.translation.job is None
    assert "Lưu khóa" in dialog.status.text()


def test_new_transcription_invalidates_previous_translation(window):
    import threading
    from types import SimpleNamespace

    old_source = window.project.transcript
    window.project.translation = Translation(source_digest(old_source), ("Bản dịch cũ",))
    window.transcription.job = SimpleNamespace(
        cancel_event=threading.Event(), request={"kind": "transcript"}
    )
    try:
        window.transcription._succeeded({"kind": "transcript", "transcript": old_source.to_dict()})
        assert window.project.translation is None
        assert "VI:" not in window.review.rows.item(0).text()
    finally:
        window.transcription.job = None


def test_translates_through_real_adapter_mock_http_then_reuses_cache(
    window, qtbot, monkeypatch, tmp_path
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [
                                {
                                    "text": '{"segments":[{"id":1,'
                                    '"translation":"Xin chào thế giới"}]}'
                                }
                            ]
                        },
                    }
                ],
                "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 30},
            },
        )

    mock_transport(monkeypatch, handler)
    source = window.project.transcript
    assert window.translation.start()
    qtbot.waitUntil(lambda: window.translation.job is None)
    assert len(calls) == 1
    assert window.project.transcript is source
    assert window.project.translation.texts == ("Xin chào thế giới",)
    assert "GỐC: Hello world" in window.review.rows.item(0).text()
    assert "VI: Xin chào" in window.review.rows.item(0).text()
    with qtbot.waitSignal(window.review.seek_requested) as signal:
        window.review.rows.itemClicked.emit(window.review.rows.item(0))
    assert signal.args == [1500]
    path = tmp_path / "translated.vkdub"
    assert window.save_to(path)
    draft = window.project.translation
    assert window.open_project(path)
    assert window.project.translation == draft
    assert not window.review.approve_button.isEnabled()
    assert not window.review.export_button.isEnabled()
    assert window.translation.start()
    qtbot.waitUntil(lambda: window.translation.job is None)
    assert len(calls) == 1
    assert "test-key" not in path.read_text(encoding="utf-8")
    assert "test-key" not in window.left.logs.toPlainText()


def test_bad_ids_do_not_replace_previous_translation(window, qtbot, monkeypatch):
    old = Translation(source_digest(window.project.transcript), ("Bản cũ",))
    window.project.translation = old
    mock_transport(
        monkeypatch,
        lambda _: httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {"segments": [{"id": 9, "translation": "Wrong ID"}]}
                                    )
                                }
                            ]
                        },
                    }
                ]
            },
        ),
    )
    assert window.translation.start()
    qtbot.waitUntil(lambda: window.translation.job is None)
    assert window.project.translation is old
    assert "ID" in window.left.logs.toPlainText()


def test_cancel_active_request_is_responsive_preserves_old_draft(window, qtbot, monkeypatch):
    old = Translation(source_digest(window.project.transcript), ("Bản cũ",))
    window.project.translation = old

    async def handler(request):
        await asyncio.sleep(30)
        return httpx.Response(200, json={})

    mock_transport(monkeypatch, handler)
    ticks = []
    timer = QTimer(window)
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start(20)
    assert window.translation.start()
    qtbot.waitUntil(lambda: len(ticks) >= 5)
    assert window.left.stop_button.isEnabled()
    window.translation.stop()
    qtbot.waitUntil(lambda: window.translation.job is None, timeout=2000)
    assert window.project.translation is old
    assert not window.busy
    assert not window.review.export_button.isEnabled()
    timer.stop()


def test_closing_manager_cancels_test_then_releases_thread(window, qtbot, monkeypatch):
    async def handler(request):
        await asyncio.sleep(30)
        return httpx.Response(200, json={})

    mock_transport(monkeypatch, handler)
    window.translation.open_manager()
    assert window.translation.test_connection()
    dialog = window.translation.dialog
    assert not dialog.test_key.isEnabled()
    dialog.reject()
    qtbot.waitUntil(lambda: window.translation.job is None, timeout=2000)
    assert not dialog.isVisible()
    assert not window.busy


def test_generic_worker_failure_does_not_leak_exception(qtbot):
    async def fail():
        raise RuntimeError("unknown-secret-from-provider")

    job = CloudJob(fail)
    with qtbot.waitSignal(job.failed) as signal:
        job.start()
    job.wait(2000)
    assert "unknown-secret" not in signal.args[0]
