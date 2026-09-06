import json
from dataclasses import replace

import httpx
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QMessageBox

from vkdub.domain.project import Project
from vkdub.domain.script import draft_from_source
from vkdub.domain.transcript import SubtitleSegment, Transcript
from vkdub.domain.translation import Translation, source_digest
from vkdub.providers.gemini_translation import GeminiTranslationProvider
from vkdub.ui.main_window import MainWindow


@pytest.fixture
def window(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("vkdub.media.process.find_tool", lambda _: None)
    monkeypatch.setattr("vkdub.services.credential_service.CredentialStore.get", lambda _: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.No)
    w = MainWindow()
    qtbot.addWidget(w)
    w.show()
    qtbot.waitUntil(lambda: w.tools_ready)
    source = Transcript(
        (SubtitleSegment(1, 1, 4, "Hello world"), SubtitleSegment(2, 5, 9, "Thank you")),
        "en",
        "en",
        11,
        "tiny",
        "cpu",
        "a" * 64,
        "b" * 64,
    )
    w.project = Project(
        video_path=tmp_path / "source.mp4",
        transcript=source,
        translation=Translation(source_digest(source), ("Xin chào thế giới", "Cảm ơn bạn")),
    )
    w.review_controller.bind_project()
    w._refresh()
    yield w
    if w.translation.job:
        w.translation.stop()
        qtbot.waitUntil(lambda: w.translation.job is None)
    w.dirty = False
    w.close()


def test_visible_srt_actions_export_original_and_translation(window, tmp_path):
    for action in ("load", "save", "save_source"):
        assert window.review.buttons[action].isVisible()
    original = tmp_path / "original.srt"
    window.review_controller.save_source_srt(original)
    text = original.read_text(encoding="utf-8")
    assert "Hello world" in text and "Xin chào" not in text
    translated = tmp_path / "translated.srt"
    from vkdub.services.srt_service import write_srt

    write_srt(translated, window.project.script, window.project.duration_ms)
    text = translated.read_text(encoding="utf-8")
    assert "Xin chào thế giới" in text and "Hello world" not in text


def approve(w, qtbot):
    assert not w.review.approve_button.isEnabled()
    qtbot.mouseClick(w.review.review_checkbox, Qt.MouseButton.LeftButton)
    assert w.review.approve_button.isEnabled()
    qtbot.mouseClick(w.review.approve_button, Qt.MouseButton.LeftButton)
    assert w.project.is_approved
    assert w.review.badge.text() == "ĐÃ DUYỆT"
    assert not w.review.export_button.isEnabled()


def test_acceptance_one_character_edit_revokes_and_undo_requires_review(window, qtbot, tmp_path):
    original = window.project.script
    source, translation = window.project.transcript, window.project.translation
    assert window.project.state == "REVIEW_REQUIRED"
    approve(window, qtbot)
    editor = window.review.editor
    editor.text.setFocus()
    editor.text.moveCursor(QTextCursor.MoveOperation.End)
    qtbot.keyClicks(editor.text, "!")
    assert window.project.script.lines[0].text.endswith("!")
    assert window.project.state == "REVIEW_REQUIRED"
    assert window.project.approved_revision_hash is None
    assert not window.review.review_checkbox.isChecked()
    assert not window.review.approve_button.isEnabled()
    assert not window.review.export_button.isEnabled()
    assert window.project.transcript is source and window.project.translation is translation
    window.review_controller.undo()
    assert window.project.script == original
    assert window.review.editor.text.toPlainText() == original.lines[0].text
    assert not window.project.is_approved
    window.review_controller.redo()
    assert window.project.script.lines[0].text.endswith("!")
    assert window.review.editor.text.toPlainText().endswith("!")
    approve(window, qtbot)
    saved_hash = window.project.require_approval()
    path = tmp_path / "approved.vkdub"
    assert window.save_to(path)
    assert window.open_project(path)
    assert window.project.is_approved and window.project.require_approval() == saved_hash
    assert not window.review.export_button.isEnabled()


def test_approval_separates_undo_groups_even_for_rapid_edits(window, qtbot):
    editor = window.review.editor
    editor.text.moveCursor(QTextCursor.MoveOperation.End)
    qtbot.keyClicks(editor.text, "A")
    before = window.project.script
    approve(window, qtbot)
    qtbot.keyClicks(editor.text, "B")
    window.review_controller.undo()
    assert window.project.script == before
    assert not window.project.is_approved


def test_overlap_blank_text_and_invalid_times_block_ui_and_backend(window, qtbot):
    editor = window.review.editor
    editor.end.setValue(6)
    assert not window.review.review_checkbox.isEnabled()
    assert not window.review.approve_button.isEnabled()
    assert "lỗi" in window.review.summary.text()
    assert not window.review_controller.approve()
    editor.end.setValue(4)
    editor.text.setPlainText(" ")
    assert not window.project.script_valid
    editor.text.setPlainText("Câu đã sửa")
    assert window.project.script_valid
    assert window.review.review_checkbox.isEnabled()
    assert not window.review.approve_button.isEnabled()
    approve(window, qtbot)
    editor.start.setValue(-1)
    assert window.project.approved_revision_hash is None
    assert not window.review.review_checkbox.isEnabled()


def test_split_merge_delete_add_and_replace_are_undoable(window):
    controller, panel = window.review_controller, window.review
    original = window.project.script
    cursor = panel.editor.text.textCursor()
    cursor.setPosition(8)
    panel.editor.text.setTextCursor(cursor)
    controller.action("split")
    assert len(window.project.script.lines) == 3
    assert window.project.script.lines[0].end_ms == 2500
    controller.action("merge_next")
    assert window.project.script == original
    controller.action("add")
    assert len(window.project.script.lines) == 3
    assert not window.project.script_valid
    controller.action("delete")
    assert window.project.script == original
    panel.find_text.setText("bạn")
    panel.replace_text.setText("mọi người")
    controller.action("replace")
    assert window.project.script.lines[1].text == "Cảm ơn mọi người"
    controller.undo()
    assert window.project.script == original


def test_timeline_drag_refuses_invalid_order_without_changing_rows(window):
    old = window.project.script
    window.review.rows.move_requested.emit(0, 1)
    assert window.project.script == old
    assert window.review.rows.item(0).data(Qt.ItemDataRole.UserRole) == 1000


def test_srt_load_preserves_source_and_clears_approval(window, qtbot, tmp_path, monkeypatch):
    approve(window, qtbot)
    original_source = window.project.transcript
    path = tmp_path / "manual.srt"
    path.write_text("1\n00:00:02,000 --> 00:00:04,000\nKịch bản nhập tay", encoding="utf-8")
    assert not window.review_controller.load_srt(path)
    assert window.project.is_approved
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    assert window.review_controller.load_srt(path)
    assert window.project.transcript is original_source
    assert window.project.script.lines[0].text == "Kịch bản nhập tay"
    assert not window.project.is_approved
    assert not window.review.review_checkbox.isChecked()
    window.review_controller.undo()
    assert len(window.project.script.lines) == 2
    assert not window.project.is_approved


def test_bad_srt_preserves_previous_draft(window, tmp_path, monkeypatch):
    path = tmp_path / "bad.srt"
    path.write_text("broken")
    old = window.project.script
    errors = []
    monkeypatch.setattr(window, "_error", errors.append)
    assert not window.review_controller.load_srt(path)
    assert window.project.script == old and errors


def test_busy_guard_blocks_edits_approval_and_srt_import(window, tmp_path):
    old = window.project.script
    window.busy = True
    window._refresh()
    assert not window.review.rows.isEnabled()
    assert not window.review.review_checkbox.isEnabled()
    window.review_controller.edit(old.lines[0].id, "Should not apply", 0, 1)
    assert not window.review_controller.approve()
    assert not window.review_controller.load_srt(tmp_path / "unused.srt")
    assert window.project.script == old
    window.busy = False


def test_source_only_can_prepare_manual_translation_without_cloud(window):
    window.project.translation = None
    window.project.set_script(None)
    window.review_controller.bind_project()
    assert window.review.buttons["prepare"].isEnabled()
    window.review_controller.action("prepare")
    assert window.project.script == draft_from_source(window.project.transcript)
    assert not window.project.script_valid
    assert window.translation.job is None


def test_metadata_context_change_requires_fresh_confirmation(window, qtbot):
    qtbot.mouseClick(window.review.review_checkbox, Qt.MouseButton.LeftButton)
    assert window.review.approve_button.isEnabled()
    window.project.video_duration_ms = 12000
    window._refresh()
    assert not window.review.review_checkbox.isChecked()
    assert not window.review_controller.approve()


def test_regenerate_one_line_preserves_others(window, qtbot, monkeypatch):
    approve(window, qtbot)
    before = window.project.script
    calls = []

    def handler(request):
        body = json.loads(request.content)
        payload = json.loads(body["contents"][0]["parts"][0]["text"])
        assert len(payload["segments"]) == 1
        assert payload["segments"][0]["text"] == "Hello world"
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [
                                {"text": '{"segments":[{"id":1,"translation":"Chào thế giới"}]}'}
                            ]
                        },
                    }
                ]
            },
        )

    monkeypatch.setattr(
        "vkdub.services.credential_service.CredentialStore.get", lambda _: "test-key"
    )
    monkeypatch.setattr(
        "vkdub.ui.translation_controller.GeminiTranslationProvider",
        lambda key, recorder, progress, **kwargs: GeminiTranslationProvider(
            key, recorder, progress, httpx.MockTransport(handler), **kwargs
        ),
    )
    assert window.translation.regenerate_line(before.lines[0].id)
    qtbot.waitUntil(lambda: window.translation.job is None)
    assert len(calls) == 1
    assert window.project.script.lines[0].text == "Chào thế giới"
    assert window.project.script.lines[1] == before.lines[1]
    assert not window.project.is_approved
    assert not window.review.export_button.isEnabled()
    window.review_controller.undo()
    assert window.project.script == before
    assert not window.project.is_approved


def test_full_retranslation_protects_manual_edits(window):
    before = replace(
        window.project.script,
        lines=(
            replace(window.project.script.lines[0], text="Edited manually"),
            window.project.script.lines[1],
        ),
    )
    window.project.set_script(before)
    window.review_controller.bind_project()
    assert not window.translation.start()
    assert window.project.script == before
    assert window.translation.job is None


def test_keyboard_undo_uses_shared_history(window, qtbot):
    original = window.project.script
    editor = window.review.editor
    editor.text.setFocus()
    qtbot.keyClicks(editor.text, "A")
    qtbot.keyClick(editor.text, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert window.project.script == original


def test_rejected_control_character_cannot_leave_visible_uncommitted_approved_text(window, qtbot):
    approve(window, qtbot)
    original = window.project.script
    window.review.editor.text.setPlainText("bad\0text")
    assert not window.project.is_approved
    assert window.project.script == original
    assert window.review.editor.text.toPlainText() == original.lines[0].text


def test_translation_stops_at_review_required(window):
    """Workflow stops at REVIEW_REQUIRED after translation. Never auto-creates voice or renders."""
    assert window.project.state == "REVIEW_REQUIRED"
    assert window.workflow_state == "REVIEW_REQUIRED"
    if hasattr(window, "tts"):
        assert window.tts.job is None
    assert not window.review.export_button.isEnabled()


def test_render_disabled_before_approval(window):
    """Render/export button must strictly stay disabled before script approval."""
    assert not window.project.is_approved
    assert not window.review.export_button.isEnabled()


def test_approve_script_sets_revision_hash(window, qtbot):
    """Explicit script approval freezes the approved revision hash."""
    assert window.project.approved_revision_hash is None
    approve(window, qtbot)
    assert window.project.is_approved
    assert window.project.approved_revision_hash is not None
    assert window.project.approved_revision_hash == window.project.revision_hash
    assert window.review.badge.text() == "ĐÃ DUYỆT"


def test_edit_after_approval_revokes_approval(window, qtbot):
    """Modifying even 1 character after approval immediately revokes approval."""
    approve(window, qtbot)
    assert window.project.is_approved
    editor = window.review.editor
    editor.text.setFocus()
    editor.text.moveCursor(QTextCursor.MoveOperation.End)
    qtbot.keyClicks(editor.text, "x")
    assert not window.project.is_approved
    assert window.project.approved_revision_hash is None
    assert not window.review.review_checkbox.isChecked()
    assert not window.review.approve_button.isEnabled()
    assert not window.review.export_button.isEnabled()
    assert "⚠ KỊCH BẢN ĐÃ THAY ĐỔI" in window.review.badge.text()


def test_empty_translation_blocks_approval(window):
    """Empty or whitespace-only translation blocks approval and UI checkbox."""
    editor = window.review.editor
    editor.text.setPlainText("   ")
    assert not window.project.script_valid
    assert not window.review.review_checkbox.isEnabled()
    assert not window.review.approve_button.isEnabled()
    with pytest.raises(ValueError):
        window.project.approve(True)


def test_invalid_timestamp_blocks_approval(window):
    """Invalid timing (start < 0, end <= start, overlapping intervals) blocks approval."""
    editor = window.review.editor
    editor.end.setValue(0.5)  # end <= start (start is 1.0)
    assert not window.project.script_valid
    assert not window.review.review_checkbox.isEnabled()
    assert not window.review.approve_button.isEnabled()
    with pytest.raises(ValueError):
        window.project.approve(True)
