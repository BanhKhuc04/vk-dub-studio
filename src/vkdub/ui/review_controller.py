import time
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QAction, QKeySequence, QUndoCommand, QUndoStack
from PySide6.QtWidgets import QFileDialog, QMessageBox

from vkdub.domain.script import ScriptDocument, ScriptLine, draft_from_source, validate_script
from vkdub.domain.translation import source_digest
from vkdub.services import script_service as editing
from vkdub.services.srt_service import read_srt, write_srt

if TYPE_CHECKING:
    from vkdub.ui.main_window import MainWindow


class ScriptEdit(QUndoCommand):
    def __init__(
        self,
        controller: "ReviewController",
        before: ScriptDocument,
        after: ScriptDocument,
        title: str,
        merge_key: str = "",
        selected: int | None = None,
    ) -> None:
        super().__init__(title)
        self.controller, self.before, self.after = controller, before, after
        self.merge_key, self.selected = merge_key, selected
        self.updated_at = time.monotonic()

    def id(self) -> int:
        return 1 if self.merge_key else -1

    def mergeWith(self, other: QUndoCommand) -> bool:
        if (
            isinstance(other, ScriptEdit)
            and self.merge_key == other.merge_key
            and other.updated_at - self.updated_at < 1
        ):
            self.after, self.updated_at = other.after, other.updated_at
            return True
        return False

    def redo(self) -> None:
        self.controller._apply(self.after, rebuild=not bool(self.merge_key), selected=self.selected)

    def undo(self) -> None:
        self.controller._apply(self.before, rebuild=True)


class ReviewController(QObject):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self.history = QUndoStack(self)
        self.history.setUndoLimit(100)
        self.edit_epoch = 0
        self.acknowledged_revision: str | None = None
        self.was_changed_after_approval = False
        panel = window.review
        panel.edit_requested.connect(self.edit)
        panel.action_requested.connect(self.action)
        panel.rows.move_requested.connect(self.move)
        panel.review_checkbox.toggled.connect(self.acknowledge)
        panel.approve_button.clicked.connect(self.approve)
        panel.rows.currentRowChanged.connect(self.refresh)
        self.history.indexChanged.connect(self.refresh)
        for name, key, callback in (
            ("Hoàn tác", QKeySequence.StandardKey.Undo, self.undo),
            ("Làm lại", QKeySequence.StandardKey.Redo, self.redo),
        ):
            shortcut = QAction(name, panel)
            shortcut.setShortcut(QKeySequence(key))
            shortcut.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.triggered.connect(callback)
            panel.addAction(shortcut)

    def bind_project(self) -> None:
        self.history.clear()
        self.was_changed_after_approval = False
        self._check(self.window.project.is_approved)
        self.window.review.show_project(self.window.project)
        self.refresh()

    def _check(self, checked: bool) -> None:
        self.acknowledged_revision = self.window.project.revision_hash if checked else None
        checkbox = self.window.review.review_checkbox
        checkbox.blockSignals(True)
        checkbox.setChecked(checked)
        checkbox.blockSignals(False)

    def acknowledge(self, checked: bool) -> None:
        self.acknowledged_revision = self.window.project.revision_hash if checked else None
        self.refresh()

    def refresh(self) -> None:
        project, panel = self.window.project, self.window.review
        if self.acknowledged_revision != project.revision_hash:
            self._check(False)
        if project.approved_revision_hash and not project.is_approved:
            project.approved_revision_hash = None
            self._check(False)
            self.window.dirty = True
        enabled = not self.window.busy
        script = project.script
        if panel.document is not script:
            panel.show_project(project)
        selected = panel.rows.currentRow()
        exists = script is not None
        selected_ok = bool(script and 0 <= selected < len(script.lines))
        for name, button in panel.buttons.items():
            ready = exists
            if name == "load":
                ready = project.video_path is not None
            elif name == "prepare":
                ready = project.video_path is not None and script is None
            elif name == "undo":
                ready = self.history.canUndo()
            elif name == "redo":
                ready = self.history.canRedo()
            elif name in ("delete", "split"):
                ready = selected_ok
            elif name == "merge_previous":
                ready = selected_ok and selected > 0
            elif name == "merge_next":
                ready = bool(selected_ok and script and selected < len(script.lines) - 1)
            button.setEnabled(enabled and ready)
        panel.search_box.setEnabled(enabled and exists)
        panel.rows.setEnabled(enabled)
        panel.rows.setDragEnabled(enabled and exists)
        if panel.editor:
            panel.editor.setEnabled(enabled)
        if script is not None:
            panel.show_project(project, rebuild=False)
            panel.stage.setText(
                "APPROVED • Phê duyệt đã lưu"
                if project.is_approved
                else "REVIEW_REQUIRED • Cần kiểm tra kịch bản"
            )
        if project.is_approved:
            panel.badge.setText("ĐÃ DUYỆT")
            panel.badge.setStyleSheet(
                "background: #0f382c; color: #34d399; border: 1px solid #10b981; "
                "font-weight: bold; padding: 6px 12px; border-radius: 5px; font-size: 11px;"
            )
        elif getattr(self, "was_changed_after_approval", False):
            panel.badge.setText("⚠ KỊCH BẢN ĐÃ THAY ĐỔI\nCần duyệt lại.")
            panel.badge.setStyleSheet(
                "background: #451a03; color: #fbbf24; border: 1px solid #d97706; "
                "font-weight: bold; padding: 6px 12px; border-radius: 5px; font-size: 11px;"
            )
        else:
            panel.badge.setText("CHƯA DUYỆT")
            panel.badge.setStyleSheet(
                "background: #1e293b; color: #94a3b8; border: 1px solid #475569; "
                "font-weight: bold; padding: 6px 12px; border-radius: 5px; font-size: 11px;"
            )
        if self.window.workflow_state in ("TRANSCRIBING", "TRANSLATING"):
            panel.stage.setText(f"{self.window.workflow_state} • Đang xử lý…")
        if not project.script_valid:
            self._check(False)
        panel.review_checkbox.setEnabled(
            enabled and project.script_valid and not project.is_approved
        )
        panel.approve_button.setEnabled(
            enabled
            and project.script_valid
            and panel.review_checkbox.isChecked()
            and not project.is_approved
        )
        panel.export_button.setEnabled(enabled and project.voice_ready)
        if project.voice_ready:
            panel.export_button.setToolTip("Sẵn sàng xuất video hoàn chỉnh.")
        else:
            panel.export_button.setToolTip(
                "Cần duyệt kịch bản và tạo đủ voice cho tất cả các câu trước khi xuất video."
            )
        if project.is_approved:
            panel.voice_note.setText("Đã lưu phê duyệt kịch bản.")
        else:
            panel.voice_note.setText("Nút duyệt lưu phê duyệt. Cần duyệt trước khi tạo voice.")
        if hasattr(self.window, "tts"):
            self.window.tts.refresh()
        if hasattr(self.window, "_refresh_primary_cta"):
            self.window._refresh_primary_cta()

    def _apply(
        self, script: ScriptDocument, rebuild: bool = True, selected: int | None = None
    ) -> None:
        revoked = self.window.project.is_approved
        if revoked:
            self.was_changed_after_approval = True
        self.window.project.set_script(script)
        if hasattr(self.window, "tts"):
            self.window.tts.player.stop()
            self.window.tts.errors.clear()
            self.window.tts.force_retry_ids.clear()
        self._check(False)
        self.window.dirty = True
        self.window.review.show_project(self.window.project, rebuild, selected)
        if revoked:
            self.window.log("Kịch bản đã đổi — hủy phê duyệt. Cần kiểm tra và duyệt lại.")
        self.window._refresh()

    def commit(
        self, script: ScriptDocument, title: str, merge_key: str = "", selected: int | None = None
    ) -> None:
        before = self.window.project.script
        if script == before:
            return
        if before is None:
            self._apply(script, selected=selected)
        else:
            self.history.push(ScriptEdit(self, before, script, title, merge_key, selected))

    def edit(self, line_id: str, text: str, start_ms: int, end_ms: int) -> None:
        script = self.window.project.script
        if self.window.busy or script is None:
            return
        try:
            index = next(i for i, row in enumerate(script.lines) if row.id == line_id)
            changed = editing.edit_line(script, index, text=text, start_ms=start_ms, end_ms=end_ms)
            self.commit(changed, "Sửa câu", f"{line_id}:{self.edit_epoch}")
        except (ValueError, StopIteration) as exc:
            self.window.log(f"Không sửa được câu: {exc}")
            self.window.project.approved_revision_hash = None
            self._check(False)
            self.window.dirty = True
            self.window.review.show_project(self.window.project)
            self.window._refresh()

    def undo(self) -> None:
        if not self.window.busy:
            self.history.undo()

    def redo(self) -> None:
        if not self.window.busy:
            self.history.redo()
            # Redo commands originally produced by typing must update their visible editor too.
            self.window.review.show_project(self.window.project)
            self.refresh()

    def approve(self) -> bool:
        if self.window.busy:
            return False
        try:
            revision = self.window.project.approve(
                self.window.review.review_checkbox.isChecked()
                and self.acknowledged_revision == self.window.project.revision_hash
            )
        except ValueError as exc:
            self.window.log(str(exc))
            return False
        self.window.dirty = True
        self.edit_epoch += 1
        self.window.log(f"Đã duyệt kịch bản {revision[:12]}.")
        self.window._refresh()
        if getattr(self.window, "legacy_tts_enabled", False) or self.window.tts.can_generate():
            self.window.tts.start()
        else:
            self.window.log("Đã lưu phê duyệt. Mở Cài đặt Voice để chọn và cấu hình giọng đọc.")
        return True

    def confirm_replace(self) -> bool:
        project = self.window.project
        if project.script is None:
            return True
        automatic = (
            draft_from_source(project.transcript, project.translation)
            if project.transcript
            else None
        )
        if project.script == automatic and not project.is_approved:
            return True
        return (
            QMessageBox.question(
                self.window,
                "Thay bản nháp?",
                "Kết quả mới sẽ thay các chỉnh sửa và hủy phê duyệt hiện tại. Tiếp tục?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )

    def action(self, name: str) -> None:
        if self.window.busy:
            return
        project, panel = self.window.project, self.window.review
        script = project.script
        index = panel.rows.currentRow()
        try:
            if name == "prepare" and project.video_path is not None and script is None:
                self.commit(
                    draft_from_source(project.transcript, project.translation)
                    if project.transcript
                    else ScriptDocument(()),
                    "Tạo bản nháp",
                )
            elif name == "load":
                self.choose_srt()
            elif script is None:
                return
            elif name == "save":
                self.save_srt_dialog()
            elif name == "save_source":
                self.save_source_srt_dialog()
            elif name == "undo":
                self.undo()
            elif name == "redo":
                self.redo()
            elif name == "search":
                panel.search_box.setVisible(not panel.search_box.isVisible())
            elif name == "find":
                query = panel.find_text.text()
                candidates = list(range(index + 1, len(script.lines))) + list(range(0, index + 1))
                found = next(
                    (i for i in candidates if query and query in script.lines[i].text), None
                )
                if found is not None:
                    panel.rows.setCurrentRow(found)
                    panel.rows.scrollToItem(panel.rows.item(found))
                else:
                    self.window.log("Không tìm thấy nội dung tiếng Việt.")
            elif name == "replace":
                self.commit(
                    editing.replace_text(script, panel.find_text.text(), panel.replace_text.text()),
                    "Thay nội dung",
                )
            elif name == "validate":
                issues = validate_script(script, project.duration_ms)
                first = next((i for i in issues if i.line_id), None)
                if first:
                    row = next(i for i, line in enumerate(script.lines) if line.id == first.line_id)
                    panel.rows.setCurrentRow(row)
                    panel.rows.scrollToItem(panel.rows.item(row))
                self.window.log(
                    "Kiểm tra: "
                    + ("; ".join(i.message for i in issues[:5]) or "Không có lỗi/cảnh báo.")
                )
            elif name == "add":
                self.commit(
                    editing.add_line(script, index, self.window.preview.player.position()),
                    "Thêm câu",
                    selected=index + 1,
                )
            elif not 0 <= index < len(script.lines):
                return
            elif name == "delete":
                self.commit(editing.delete_line(script, index), "Xóa câu", selected=index)
            elif name == "split" and panel.editor:
                selected_line = script.lines[index]
                position = self.window.preview.player.position()
                if not selected_line.start_ms < position < selected_line.end_ms:
                    position = (selected_line.start_ms + selected_line.end_ms) // 2
                self.commit(
                    editing.split_line(script, index, panel.editor.cursor_index(), position),
                    "Tách câu",
                    selected=index,
                )
            elif name in ("merge_previous", "merge_next"):
                at = index - 1 if name == "merge_previous" else index
                self.commit(editing.merge_lines(script, at), "Gộp câu", selected=at)
        except (ValueError, OSError) as exc:
            self.window._error(str(exc))
        self.refresh()

    def move(self, source: int, destination: int) -> None:
        if self.window.busy or self.window.project.script is None:
            return
        try:
            self.commit(
                editing.move_line(self.window.project.script, source, destination),
                "Đổi thứ tự",
                selected=destination,
            )
        except (ValueError, IndexError) as exc:
            self.window.log(str(exc))

    def choose_srt(self) -> None:
        if self.window.project.video_path is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self.window, "Mở bản tiếng Việt SRT", "", "SRT (*.srt)"
        )
        if path:
            self.load_srt(Path(path))

    def load_srt(self, path: Path) -> bool:
        if self.window.busy or self.window.project.video_path is None:
            return False
        try:
            transcript = self.window.project.transcript
            result = read_srt(path, source_digest(transcript) if transcript else None)
            if self.confirm_replace():
                self.commit(result, "Mở SRT", selected=0)
                self.window.log("Đã mở SRT tiếng Việt. Bản gốc được giữ nguyên; cần duyệt lại.")
                return True
        except (ValueError, OSError) as exc:
            self.window._error(str(exc))
        return False

    def save_srt_dialog(self) -> None:
        script = self.window.project.script
        if script is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self.window, "Lưu SRT tiếng Việt", "script.srt", "SRT (*.srt)"
        )
        if path:
            target = Path(path)
            if target.suffix.lower() != ".srt":
                target = Path(f"{target}.srt")
                if (
                    target.exists()
                    and QMessageBox.question(
                        self.window, "Ghi đè SRT?", f"{target.name} đã tồn tại. Ghi đè?"
                    )
                    != QMessageBox.StandardButton.Yes
                ):
                    return
            write_srt(target, script, self.window.project.duration_ms)
            self.window.log("Đã lưu SRT tiếng Việt.")

    def save_source_srt_dialog(self) -> None:
        if self.window.project.transcript is None:
            self.window.log("Chưa có kịch bản gốc để xuất SRT.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self.window, "Lưu SRT chưa dịch", "script-goc.srt", "SRT (*.srt)"
        )
        if path:
            target = Path(path)
            if target.suffix.lower() != ".srt":
                target = Path(f"{target}.srt")
            self.save_source_srt(target)

    def save_source_srt(self, path: Path) -> None:
        transcript = self.window.project.transcript
        if transcript is None:
            raise ValueError("Chưa có kịch bản gốc để xuất SRT.")
        source = ScriptDocument(
            tuple(
                ScriptLine.new(round(item.start * 1000), round(item.end * 1000), item.text)
                for item in transcript.segments
            )
        )
        write_srt(path, source, self.window.project.duration_ms)
        self.window.log("Đã lưu SRT chưa dịch.")
