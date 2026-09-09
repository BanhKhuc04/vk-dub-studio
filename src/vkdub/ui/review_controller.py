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
        project = self.window.project
        if project.script and project.duration_ms:
            last_line = project.script.lines[-1] if project.script.lines else None
            if (
                last_line
                and last_line.start_ms < project.duration_ms < last_line.end_ms
                and (last_line.end_ms - project.duration_ms) <= 1500
            ):
                from dataclasses import replace as dc_replace
                lines = list(project.script.lines)
                lines[-1] = dc_replace(last_line, end_ms=project.duration_ms)
                project.script = ScriptDocument(tuple(lines))
        self._check(self.window.project.is_approved)
        self.window.review.show_project(self.window.project)
        self.refresh()
        if hasattr(self.window, "switch_to_step") and (
            self.window.project.script or self.window.project.transcript
        ):
            self.window.switch_to_step(4)

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
        from vkdub.utils.paths import workspace_root
        out_name = project.video_path.stem if project.video_path else "dubbing"
        export_dir = workspace_root() / "export" / out_name
        orig_file_exists = (export_dir / "original.srt").is_file()
        trans_file_exists = (export_dir / "translated.srt").is_file()

        for name, button in panel.buttons.items():
            ready = exists
            if name in ("load", "load_source"):
                ready = project.video_path is not None
            elif name == "save_source":
                ready = (project.transcript is not None) or orig_file_exists
            elif name == "save":
                ready = exists or trans_file_exists
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
        if project.is_approved and project.voice_ready:
            panel.approve_button.setText("✔ ĐÃ DUYỆT KỊCH BẢN & SẴN SÀNG XUẤT")
        elif project.is_approved and not project.voice_ready:
            panel.approve_button.setText("⏳ ĐÃ CHỐT KỊCH BẢN — ĐANG TẠO GIỌNG...")
        else:
            panel.approve_button.setText("✔ BƯỚC 5: CHỐT KỊCH BẢN & TẠO GIỌNG (VBEE)")
        panel.approve_button.setEnabled(
            enabled
            and project.script_valid
            and panel.review_checkbox.isChecked()
            and not project.is_approved
        )
        panel.export_button.setEnabled(enabled and project.voice_ready)
        if hasattr(panel, "export_capcut_button"):
            panel.export_capcut_button.setEnabled(enabled and project.voice_ready)
        if project.voice_ready:
            panel.export_button.setToolTip("Sẵn sàng xuất video hoàn chỉnh.")
            if hasattr(panel, "export_capcut_button"):
                panel.export_capcut_button.setToolTip("Sẵn sàng xuất dự án CapCut.")
        else:
            panel.export_button.setToolTip(
                "Cần duyệt kịch bản và tạo đủ voice cho tất cả các câu trước khi xuất video."
            )
            if hasattr(panel, "export_capcut_button"):
                panel.export_capcut_button.setToolTip(
                    "Cần duyệt kịch bản và tạo đủ voice cho tất cả các câu trước khi xuất CapCut."
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
        project = self.window.project
        # Auto-clamp trailing cue that slightly exceeds video duration by <= 1500ms
        if project.script and project.duration_ms:
            last_line = project.script.lines[-1] if project.script.lines else None
            if (
                last_line
                and last_line.start_ms < project.duration_ms < last_line.end_ms
                and (last_line.end_ms - project.duration_ms) <= 1500
            ):
                from dataclasses import replace as dc_replace
                lines = list(project.script.lines)
                lines[-1] = dc_replace(last_line, end_ms=project.duration_ms)
                project.script = ScriptDocument(tuple(lines))
                self.acknowledged_revision = project.revision_hash
                self.window.review.show_project(project)
        try:
            confirmed = self.window.review.review_checkbox.isChecked()
            revision = project.approve(
                confirmed
                and (self.acknowledged_revision == project.revision_hash or confirmed)
            )
        except ValueError as exc:
            self.window.log(str(exc))
            if hasattr(self.window, "statusBar") and self.window.statusBar():
                self.window.statusBar().showMessage(f"⚠ {exc}", 5000)
            return False
        self.window.dirty = True
        self.edit_epoch += 1
        self.window.log(f"Đã duyệt kịch bản {revision[:12]}.")
        self.window._refresh()
        self.refresh()
        if project.voice_ready:
            self.window.log("✓ Kịch bản và âm thanh đã sẵn sàng. Sẵn sàng xuất MP4 hoặc CapCut.")
            if hasattr(self.window, "statusBar") and self.window.statusBar():
                self.window.statusBar().showMessage("✓ Kịch bản đã duyệt! Sẵn sàng xuất MP4 hoặc CapCut.", 5000)
            if hasattr(self.window, "notify_success"):
                self.window.notify_success(
                    "Sẵn sàng xuất",
                    "Kịch bản và audio timeline đã sẵn sàng. Bạn có thể xuất video MP4 hoặc CapCut ngay."
                )
        elif hasattr(self.window, "_start_vbee_generation"):
            self.window._start_vbee_generation()
        elif getattr(self.window, "legacy_tts_enabled", False):
            self.window.tts.start()
        else:
            self.window.log("Đã lưu phê duyệt kịch bản.")
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
            elif name == "load_source":
                self.choose_source_srt()
            elif name == "import_vbee":
                if hasattr(self.window, "vbee_controller") and self.window.vbee_controller:
                    self.window.vbee_controller.import_manual_audio_dialog()
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
            from vkdub.utils.paths import workspace_root
            transcript = self.window.project.transcript
            result = read_srt(path, source_digest(transcript) if transcript else None)
            self.commit(result, "Mở SRT", selected=0)

            # Copy to export folder as translated.srt
            out_name = self.window.project.video_path.stem or "dubbing"
            output_dir = workspace_root() / "export" / out_name
            output_dir.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(path, output_dir / "translated.srt")

            self.window.log(f"✓ Đã nạp thành công phụ đề dịch: {path.name} ({len(result.lines)} câu)")
            if hasattr(self.window, "notify_success"):
                self.window.notify_success("Nạp SRT dịch thành công", f"Đã nạp {len(result.lines)} câu thoại từ {path.name}.")
            self.window._refresh()
            self.refresh()
            return True
        except Exception as exc:
            self.window._error(f"Không thể nạp file SRT dịch: {exc}")
        return False

    def save_srt_dialog(self) -> None:
        from vkdub.utils.paths import workspace_root
        script = self.window.project.script
        out_name = self.window.project.video_path.stem if self.window.project.video_path else "dubbing"
        trans_file = workspace_root() / "export" / out_name / "translated.srt"

        if script is None and not trans_file.is_file():
            self.window._error("Chưa có kịch bản dịch để tải về.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self.window, "Lưu SRT dịch (Tiếng Việt)", "translated.srt", "SRT (*.srt);;Tất cả tệp (*.*)"
        )
        if path:
            target = Path(path)
            if target.suffix.lower() != ".srt":
                target = Path(f"{target}.srt")
            try:
                if script is not None:
                    write_srt(target, script, self.window.project.duration_ms)
                elif trans_file.is_file():
                    import shutil
                    shutil.copy2(trans_file, target)
                self.window.log(f"Đã lưu SRT tiếng Việt: {target.name}")
                if hasattr(self.window, "notify_success"):
                    self.window.notify_success("Tải SRT dịch thành công", f"Đã lưu: {target.name}")
            except Exception as exc:
                self.window._error(f"Không thể lưu SRT dịch: {exc}")

    def save_source_srt_dialog(self) -> None:
        from vkdub.utils.paths import workspace_root
        transcript = self.window.project.transcript
        out_name = self.window.project.video_path.stem if self.window.project.video_path else "dubbing"
        orig_file = workspace_root() / "export" / out_name / "original.srt"

        if transcript is None and not orig_file.is_file():
            self.window._error("Chưa có kịch bản gốc (original.srt) để tải về.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self.window, "Lưu SRT chưa dịch (gốc)", "original.srt", "SRT (*.srt);;Tất cả tệp (*.*)"
        )
        if path:
            target = Path(path)
            if target.suffix.lower() != ".srt":
                target = Path(f"{target}.srt")
            try:
                if transcript is not None:
                    self.save_source_srt(target)
                elif orig_file.is_file():
                    import shutil
                    shutil.copy2(orig_file, target)
                    self.window.log(f"Đã lưu SRT chưa dịch: {target.name}")
                if hasattr(self.window, "notify_success"):
                    self.window.notify_success("Tải SRT gốc thành công", f"Đã lưu: {target.name}")
            except Exception as exc:
                self.window._error(f"Không thể lưu SRT gốc: {exc}")

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

    def choose_source_srt(self) -> None:
        if self.window.project.video_path is None:
            self.window.log("Vui lòng chọn video trước khi nạp file phụ đề gốc.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self.window, "Mở file phụ đề SRT gốc (chưa dịch)", "", "SRT (*.srt);;Tất cả tệp (*.*)"
        )
        if path:
            self.load_source_srt(Path(path))

    def load_source_srt(self, path: Path) -> bool:
        if self.window.busy or self.window.project.video_path is None:
            return False
        try:
            import shutil
            from vkdub.domain.transcript import SubtitleSegment, Transcript
            from vkdub.services.srt_validator import parse_cues
            from vkdub.utils.paths import workspace_root

            raw_text = path.read_text(encoding="utf-8", errors="replace")
            cues = parse_cues(raw_text)
            if not cues:
                raise ValueError("Tệp phụ đề SRT không chứa câu thoại nào hợp lệ.")

            segments = tuple(
                SubtitleSegment(
                    id=c.index,
                    start=c.start_ms / 1000.0,
                    end=c.end_ms / 1000.0,
                    text=c.text,
                )
                for c in cues
            )
            total_dur = (cues[-1].end_ms / 1000.0) if cues else 0.0
            transcript = Transcript(
                segments=segments,
                language=self.window.project.source_language or "zh",
                requested_language="auto",
                duration=total_dur,
                model="base",
                device="cpu",
                fingerprint="0" * 64,
                cache_key="0" * 64,
            )
            self.window.project.transcript = transcript

            # Copy to export folder as original.srt for pipeline compatibility
            out_name = self.window.project.video_path.stem or "dubbing"
            output_dir = workspace_root() / "export" / out_name
            output_dir.mkdir(parents=True, exist_ok=True)
            dest_orig = output_dir / "original.srt"
            shutil.copy2(path, dest_orig)

            if hasattr(self.window, "step4_panel"):
                from vkdub.orchestrator.pipeline_state import SubstepStatus
                self.window.step4_panel.update_substep(
                    "4.1",
                    SubstepStatus.SUCCESS,
                    100,
                    f"Đã nạp file phụ đề gốc ({len(segments)} câu)",
                    artifact=dest_orig,
                )

            self.window.log(f"✓ Đã nạp thành công phụ đề gốc: {path.name} ({len(segments)} câu)")
            if hasattr(self.window, "notify_success"):
                self.window.notify_success(
                    "Nạp SRT gốc thành công",
                    f"Đã nạp {len(segments)} câu thoại gốc từ {path.name}.",
                )
            self.window._refresh()
            self.refresh()
            return True
        except Exception as exc:
            self.window._error(f"Không thể nạp file SRT gốc: {exc}")
            return False

