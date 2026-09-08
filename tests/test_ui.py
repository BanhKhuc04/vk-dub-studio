from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtMultimedia import QVideoFrame
from PySide6.QtWidgets import QMessageBox

from vkdub.domain.project import Project
from vkdub.domain.transcript import SubtitleSegment, Transcript, TranscriptionSettings
from vkdub.domain.voice import VoiceSettings
from vkdub.services.project_service import save_project
from vkdub.ui.main_window import MainWindow
from vkdub.ui.video_canvas import VideoCanvas
from vkdub.ui.video_preview import clock_text
from vkdub.version import __version__


@pytest.fixture
def window(qtbot, monkeypatch):
    monkeypatch.setattr("vkdub.media.process.find_tool", lambda _: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard)
    widget = MainWindow()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitUntil(lambda: widget.tools_ready)
    yield widget
    widget.dirty = False
    widget.close()


def test_shell_branding_and_workflow_gate(window):
    assert "VK Dub Studio — by vanhkhuc.dev" in window.windowTitle()
    assert f"v{__version__}" in window.windowTitle()
    assert "Sản phẩm được tạo bởi vanhkhuc.dev" in window.left.credit_label.text()
    assert "Dành tặng em bé Trang Vũ <3" in window.left.credit_label.text()
    assert not window.review.approve_button.isEnabled()
    assert not window.review.export_button.isEnabled()
    assert not window.review.review_checkbox.isEnabled()
    assert not window.left.process_button.isEnabled()
    assert window.left.import_button.isEnabled()
    assert "Chưa sẵn sàng" in window.left.ffprobe_status.text()


def test_output_and_project_roundtrip_in_window(window, tmp_path):
    assert window.set_output_directory(tmp_path)
    identifier = window.project.project_id
    assert window.dirty
    path = tmp_path / "example.vkdub"
    assert window.save_to(path)
    assert not window.dirty
    window.project = Project()
    assert window.open_project(path)
    assert window.project.project_id == identifier
    assert window.project.output_directory == tmp_path
    assert not window.review.export_button.isEnabled()


def test_open_project_restores_vbee_voice_controls(window, tmp_path):
    project = Project(
        voice=VoiceSettings(
            provider="vbee",
            voice_id="vbee-ngoc-huyen",
            display_name="Ngọc Huyền (Nữ miền Bắc)",
            speed=1.1,
        )
    )
    target = tmp_path / "voice-settings.vkdub"
    save_project(project, target)

    window.left.speed_combo.setCurrentIndex(window.left.speed_combo.findData(1.0))
    assert window.open_project(target)

    assert window.left.voice_combo.currentData() == "vbee-ngoc-huyen"
    assert window.left.speed_combo.currentData() == 1.1
    assert window.project.voice.speed == 1.1


def test_missing_video_preserves_reference(window, tmp_path):
    project = Project(video_path=tmp_path / "moved.mp4")
    target = tmp_path / "missing.vkdub"
    save_project(project, target)
    assert window.open_project(target)
    assert window.project == project
    assert "Không tìm thấy" in window.left.logs.toPlainText()
    assert not window.preview.play_button.isEnabled()


def test_invalid_import_preserves_existing_project(window, tmp_path, monkeypatch):
    messages = []
    monkeypatch.setattr(window, "_error", messages.append)
    current = window.project
    assert not window.import_video(tmp_path / "missing.mp4")
    assert window.project is current
    assert messages


def test_probe_failure_preserves_existing_project(window, tmp_path, monkeypatch):
    messages = []
    monkeypatch.setattr(window, "_error", messages.append)
    source = tmp_path / "bad.mp4"
    source.write_bytes(b"not mp4")
    current = window.project
    window.tools.paths["ffprobe"] = "unused"
    monkeypatch.setattr(window.tools, "probe", lambda path: None)
    assert window.import_video(source)
    assert window.busy
    window._probe_failed(str(source), "invalid media")
    assert not window.busy
    assert window.project is current
    assert messages


def test_invalid_project_does_not_replace_current(window, tmp_path, monkeypatch):
    monkeypatch.setattr(window, "_error", lambda _: None)
    source = tmp_path / "bad.vkdub"
    source.write_text("[]")
    current = window.project
    assert not window.open_project(source)
    assert window.project is current


def test_cancel_close_keeps_dirty_project(window, monkeypatch):
    window.dirty = True
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Cancel)
    assert not window.close()
    assert window.dirty
    assert window.isVisible()
    window.dirty = False


def test_save_failure_keeps_dirty_project(window, monkeypatch):
    window.dirty = True
    monkeypatch.setattr(window, "_error", lambda _: None)

    def fail(*args):
        raise OSError("read only")

    monkeypatch.setattr("vkdub.ui.main_window.save_project", fail)
    assert not window.save_to(Path("readonly.vkdub"))
    assert window.dirty


def test_seek_time_supports_long_videos():
    assert clock_text(3_661_000) == "01:01:01"
    assert clock_text(-1) == "00:00:00"


def test_canvas_displays_decoded_frame_without_stretching(qtbot):
    canvas = VideoCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(400, 400)
    frame = QImage(160, 90, QImage.Format.Format_RGB32)
    frame.fill(QColor("red"))
    canvas.sink.setVideoFrame(QVideoFrame(frame))
    canvas.show()
    qtbot.waitUntil(lambda: not canvas.frame_image.isNull())
    screenshot = canvas.grab().toImage()
    assert screenshot.pixelColor(200, 200) == QColor("red")
    assert screenshot.pixelColor(200, 10) == QColor("#05070b")
    canvas.clear()
    assert canvas.frame_image.isNull()


def test_transcript_row_seeks_nonzero_and_does_not_enable_approval(window, qtbot):
    transcript = Transcript(
        (SubtitleSegment(1, 1.5, 3.0, "A source sentence."),),
        "en",
        "auto",
        4,
        "tiny",
        "cpu",
        "a" * 64,
        "b" * 64,
    )
    window.review.show_transcript(transcript)
    with qtbot.waitSignal(window.review.seek_requested) as result:
        window.review.rows.itemClicked.emit(window.review.rows.item(0))
    assert result.args == [1500]
    assert not window.review.approve_button.isEnabled()
    assert not window.review.export_button.isEnabled()


def test_new_video_keeps_model_and_language_settings(window, tmp_path, monkeypatch):
    window.project.transcription_settings = TranscriptionSettings("tiny", "cpu")
    window.project.source_language = "zh"
    monkeypatch.setattr(window.preview, "load", lambda _: None)
    window._apply_import(tmp_path / "new.mp4", None)
    assert window.project.transcription_settings == TranscriptionSettings("tiny", "cpu")
    assert window.project.source_language == "zh"
    assert window.project.transcript is None


def test_failed_and_cancelled_jobs_preserve_source_transcript(window):
    old = Transcript((), "en", "auto", 4, "tiny", "cpu", "a" * 64, "b" * 64)
    window.project.transcript = old
    window.transcription._failed("test failure")
    assert window.project.transcript is old
    window.transcription._cancelled()
    assert window.project.transcript is old
    assert not window.review.export_button.isEnabled()


def test_close_during_job_cancels_then_closes(window, qtbot, monkeypatch, tmp_path):
    from vkdub.services.transcription_service import JobCancelled

    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))

    def wait_for_cancel(args, directory, cancel, report, **kwargs):
        cancel.wait(3)
        raise JobCancelled

    monkeypatch.setattr("vkdub.services.transcription_service.run_process", wait_for_cancel)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    assert window.transcription._launch({"kind": "model", "model": "tiny"})
    assert window.busy
    assert not window.close()
    qtbot.waitUntil(lambda: window.transcription.job is None, timeout=5000)
    assert not window.isVisible()
    assert not window.busy
