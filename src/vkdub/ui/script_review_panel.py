from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptIssue, validate_script
from vkdub.domain.transcript import Transcript, srt_timestamp
from vkdub.domain.translation import Translation
from vkdub.domain.voice import timing_warning
from vkdub.ui.left_config_panel import label
from vkdub.ui.script_list import ScriptList
from vkdub.ui.script_row_editor import ScriptRowEditor


class ScriptReviewPanel(QFrame):
    seek_requested = Signal(int)
    play_requested = Signal(int, int)
    edit_requested = Signal(str, str, int, int)
    action_requested = Signal(str)
    regenerate_requested = Signal(str)
    voice_requested = Signal(str)
    listen_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("panel")
        self.setMinimumWidth(320)
        self.document: ScriptDocument | None = None
        self.transcript: Transcript | None = None
        self.editor: ScriptRowEditor | None = None
        self._editor_item: QListWidgetItem | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # ---------------------------------------------------------
        # Header: KỊCH BẢN & Trạng thái duyệt
        # ---------------------------------------------------------
        header_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.addWidget(label("KỊCH BẢN", "heading"))
        self.summary = QLabel("0 câu  •  0 lỗi  •  0 cảnh báo")
        self.summary.setStyleSheet("color: #72d7c1; font-weight: 600; font-size: 12px;")
        title_col.addWidget(self.summary)
        header_row.addLayout(title_col, 1)

        self.badge = QLabel("CHƯA DUYỆT")
        self.badge.setObjectName("badge")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setStyleSheet(
            "background: #1e293b; color: #94a3b8; border: 1px solid #475569; "
            "font-weight: bold; padding: 6px 12px; border-radius: 5px; font-size: 11px;"
        )
        header_row.addWidget(self.badge)
        layout.addLayout(header_row)

        self.stage = QLabel("Chưa có bản chép lời.")
        self.stage.setStyleSheet("color: #929fb5; font-size: 11px;")
        layout.addWidget(self.stage)

        # ---------------------------------------------------------
        # Toolbar (Actions)
        # ---------------------------------------------------------
        toolbar = QGridLayout()
        toolbar.setSpacing(4)
        self.buttons: dict[str, QPushButton] = {}
        for index, (action, title) in enumerate(
            (
                ("add", "+ Thêm"),
                ("delete", "✖ Xóa"),
                ("split", "✂ Tách"),
                ("merge_previous", "⇈ Gộp trước"),
                ("merge_next", "⇊ Gộp sau"),
                ("undo", "↶ Hoàn tác"),
                ("redo", "↷ Làm lại"),
                ("search", "🔍 Tìm/Thay"),
                ("load", "📂 Nhập SRT bản dịch"),
                ("save", "⬇ SRT đã dịch"),
                ("import_vbee", "🎵 Nhập Audio Vbee"),
                ("save_source", "⬇ SRT chưa dịch"),
                ("validate", "Kiểm tra"),
                ("prepare", "Tạo bản nháp"),
            )
        ):
            button = QPushButton(title)
            button.setStyleSheet("padding: 5px 3px; font-size: 11px; font-weight: 600;")
            button.clicked.connect(
                lambda checked=False, name=action: self.action_requested.emit(name)
            )
            self.buttons[action] = button
            toolbar.addWidget(button, index // 5, index % 5)
        self.more_button = QToolButton()
        self.more_button.setText("Thêm ⋯")
        self.more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more_menu = QMenu(self)
        self.more_button.setMenu(more_menu)
        overflow = []
        primary = ("load", "save", "save_source", "import_vbee", "validate")
        for name, button in self.buttons.items():
            toolbar.removeWidget(button)
            if name in primary:
                toolbar.addWidget(button, 0, primary.index(name))
            else:
                button.setParent(self)
                button.hide()
                menu_action = more_menu.addAction(button.text())
                menu_action.triggered.connect(button.click)
                overflow.append((menu_action, button))

        def refresh_overflow() -> None:
            for menu_action, hidden_button in overflow:
                menu_action.setEnabled(hidden_button.isEnabled())

        more_menu.aboutToShow.connect(refresh_overflow)
        toolbar.addWidget(self.more_button, 0, len(primary))
        layout.addLayout(toolbar)

        # Search / Replace box
        self.search_box = QWidget()
        search_layout = QGridLayout(self.search_box)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(4)
        self.find_text = QLineEdit()
        self.find_text.setPlaceholderText("Tìm trong tiếng Việt (phân biệt hoa/thường)")
        self.replace_text = QLineEdit()
        self.replace_text.setPlaceholderText("Thay bằng…")
        self.find_next = QPushButton("Tìm tiếp")
        self.replace_all = QPushButton("Thay tất cả")
        search_layout.addWidget(self.find_text, 0, 0)
        search_layout.addWidget(self.find_next, 0, 1)
        search_layout.addWidget(self.replace_text, 1, 0)
        search_layout.addWidget(self.replace_all, 1, 1)
        self.find_next.clicked.connect(lambda: self.action_requested.emit("find"))
        self.replace_all.clicked.connect(lambda: self.action_requested.emit("replace"))
        self.search_box.hide()
        layout.addWidget(self.search_box)

        # Placeholder label
        self.placeholder = label(
            "Tải video và bấm BẮT ĐẦU XỬ LÝ để bóc băng và dịch sang tiếng Việt.\n"
            "Danh sách câu sẽ xuất hiện ở đây để bạn kiểm tra."
        )
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet("color: #69768b; padding: 20px; font-size: 12px;")
        layout.addWidget(self.placeholder)

        # Script cards list
        self.rows = ScriptList()
        self.rows.setWordWrap(True)
        self.rows.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rows.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.rows.setSpacing(8)
        self.rows.setAccessibleName("Danh sách các câu kịch bản")
        self.rows.itemClicked.connect(self._seek)
        self.rows.itemActivated.connect(self._seek)
        self.rows.currentRowChanged.connect(self._select_editor)
        layout.addWidget(self.rows, 1)

        # Bottom Approval Gate Section
        bottom_box = QFrame()
        bottom_box.setStyleSheet(
            "background: #0f141e; border: 1px solid #232d3f; border-radius: 6px; padding: 10px;"
        )
        bottom_layout = QVBoxLayout(bottom_box)
        bottom_layout.setContentsMargins(8, 8, 8, 8)
        bottom_layout.setSpacing(8)

        self.review_checkbox = QCheckBox("Tôi đã kiểm tra toàn bộ kịch bản")
        self.review_checkbox.setEnabled(False)
        self.review_checkbox.setStyleSheet("font-weight: 600; color: #e5eaf4; font-size: 13px;")
        bottom_layout.addWidget(self.review_checkbox)

        self.approve_button = QPushButton("✓ DUYỆT KỊCH BẢN & TẠO VOICE")
        self.approve_button.setObjectName("primary")
        self.approve_button.setEnabled(False)
        self.approve_button.setStyleSheet("font-size: 13px; font-weight: bold; padding: 10px;")
        self.approve_button.setToolTip(
            "Chỉ duyệt khi đã tích xác nhận và không còn lỗi blocking. Lưu revision hash an toàn."
        )
        bottom_layout.addWidget(self.approve_button)

        self.voice_note = QLabel("Sẵn sàng tạo voice Vbee sau khi duyệt kịch bản.")
        self.voice_note.setWordWrap(True)
        self.voice_note.setStyleSheet("color: #929fb5; font-size: 11px;")
        bottom_layout.addWidget(self.voice_note)

        self.export_button = QPushButton("XUẤT VIDEO")
        self.export_button.setEnabled(False)
        self.export_button.setToolTip(
            "Cần hoàn tất kịch bản đã duyệt và tạo voice trước khi render."
        )
        bottom_layout.addWidget(self.export_button)

        layout.addWidget(bottom_box)

    def show_transcript(
        self, transcript: Transcript | None, translation: Translation | None = None
    ) -> None:
        self._remove_editor()
        self.document = None
        self.transcript = transcript
        if translation:
            translation.validate_source(transcript)
        self.rows.clear()
        self.placeholder.setVisible(transcript is None or not transcript.segments)
        if transcript is None:
            self.placeholder.setText(
                "Tải video và bấm BẮT ĐẦU XỬ LÝ để bóc băng và dịch.\nChưa có kịch bản."
            )
            self.stage.setText("Chưa có bản chép lời.")
            self.summary.setText("0 câu  •  Chưa có bản dịch")
            return
        for segment in transcript.segments:
            start_fmt = srt_timestamp(segment.start).replace(",", ".")
            end_fmt = srt_timestamp(segment.end).replace(",", ".")
            item = QListWidgetItem(
                f"#{segment.id:02}   {start_fmt} → {end_fmt}\n\n"
                f"GỐC: {segment.text}"
                + (f"\nVI: {translation.texts[segment.id - 1]}" if translation else "")
                + "\n\n[▶]"
            )
            item.setData(Qt.ItemDataRole.UserRole, round(segment.start * 1000))
            self.rows.addItem(item)
        if not transcript.segments:
            self.placeholder.setText("Không phát hiện lời nói. Thử model hoặc ngôn ngữ khác.")
        self.stage.setText("ĐÃ BÓC BĂNG  •  BẢN GỐC")
        self.summary.setText(
            f"{len(transcript.segments)} câu  •  {transcript.language}  •  "
            f"{transcript.duration:.1f}s  •  Chưa duyệt"
        )
        if translation:
            self.stage.setText("ĐÃ DỊCH  •  CHỜ DUYỆT KỊCH BẢN")
            self.summary.setText(
                f"{len(transcript.segments)} câu  •  {transcript.duration:.1f}s  •  Chờ kiểm tra"
            )

    def _source_text(self, ids: tuple[int, ...]) -> str:
        if not self.transcript:
            return ""
        return " ".join(self.transcript.segments[i - 1].text for i in ids)

    def _remove_editor(self) -> None:
        if self.editor and self._editor_item:
            self.rows.removeItemWidget(self._editor_item)
            self._editor_item.setSizeHint(QSize())
            self.editor.deleteLater()
        self.editor = None
        self._editor_item = None

    def _select_editor(self, index: int) -> None:
        self._remove_editor()
        if self.document is None or not 0 <= index < len(self.document.lines):
            return
        line = self.document.lines[index]
        item = self.rows.item(index)
        self.editor = ScriptRowEditor(line, self._source_text(line.source_ids), index + 1)
        self.editor.changed.connect(self.edit_requested)
        self.editor.play_requested.connect(self.play_requested)
        self.editor.regenerate_requested.connect(self.regenerate_requested)
        self.editor.command_requested.connect(self.action_requested)
        self.editor.voice_button.clicked.connect(lambda: self.voice_requested.emit(line.id))
        self.editor.listen_button.clicked.connect(self.listen_requested)
        self._editor_item = item
        item.setSizeHint(QSize(0, 415))
        self.rows.setItemWidget(item, self.editor)

    def show_project(
        self, project: Project, rebuild: bool = True, selected: int | None = None
    ) -> None:
        if project.script is None:
            if rebuild:
                self.show_transcript(project.transcript, project.translation)
            return
        self.transcript = project.transcript
        self.document = project.script
        if rebuild:
            current = self.rows.currentRow() if selected is None else selected
            self._remove_editor()
            self.rows.blockSignals(True)
            self.rows.clear()
            for _ in project.script.lines:
                self.rows.addItem(QListWidgetItem())
            self.rows.blockSignals(False)
            self.rows.setCurrentRow(min(max(current, 0), len(project.script.lines) - 1))
        self.placeholder.setVisible(not project.script.lines)
        self.placeholder.setText("Kịch bản trống. Thêm câu hoặc mở SRT.")
        issues = list(validate_script(project.script, project.duration_ms))
        current_voices = project.current_voices()
        for line in project.script.lines:
            if asset := current_voices.get(line.id):
                if warning := timing_warning(asset.duration_ms, line.end_ms - line.start_ms):
                    issues.append(ScriptIssue(line.id, "warning", warning))
        by_line: dict[str, list[ScriptIssue]] = {}
        for issue in issues:
            if issue.line_id:
                by_line.setdefault(issue.line_id, []).append(issue)
        for index, line in enumerate(project.script.lines):
            item = self.rows.item(index)
            flags = by_line.get(line.id, [])
            flag_icon = "⚠ " if flags else ""
            start_str = srt_timestamp(line.start_ms / 1000).replace(",", ".")
            end_str = srt_timestamp(line.end_ms / 1000).replace(",", ".")
            src_str = self._source_text(line.source_ids) or "(Câu thêm / nhập SRT)"
            vi_str = line.text or "(chưa nhập tiếng Việt)"
            voice_info = ""
            if asset := current_voices.get(line.id):
                voice_info = f"  •  🎵 {asset.duration_ms / 1000:.2f}s"
            item.setText(
                f"{flag_icon}#{index + 1:02}   {start_str} → {end_str}{voice_info}\n\n"
                f"GỐC: {src_str}\n"
                f"VI: {vi_str}\n\n"
                f"[▶]"
            )
            item.setData(Qt.ItemDataRole.UserRole, max(0, line.start_ms))
            item.setToolTip("\n".join(i.message for i in flags))
        if self.editor and 0 <= self.rows.currentRow() < len(project.script.lines):
            self.editor.update_duration(project.script.lines[self.rows.currentRow()])
            selected_issues = by_line.get(self.editor.line_id, [])
            self.editor.issues.setText(
                f"⚠ {len(selected_issues)} lỗi/cảnh báo — nhấn Kiểm tra"
                if selected_issues
                else "✓ Câu hợp lệ"
            )
            self.editor.issues.setToolTip("\n".join(i.message for i in selected_issues))
        errors = sum(i.severity == "error" for i in issues)
        warnings = sum(i.severity == "warning" for i in issues)
        self.summary.setText(
            f"{len(project.script.lines)} câu  •  {errors} lỗi  •  {warnings} cảnh báo"
        )
        self.summary.setToolTip("\n".join(i.message for i in issues[:100]))

    def _seek(self, item: QListWidgetItem) -> None:
        self.seek_requested.emit(int(item.data(Qt.ItemDataRole.UserRole)))
