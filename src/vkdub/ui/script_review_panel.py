from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction
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
    export_video_requested = Signal()
    export_capcut_requested = Signal()
    capcut_folder_requested = Signal()
    open_capcut_requested = Signal()
    open_capcut_folder_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("panel")
        self.setMinimumWidth(480)
        self.document: ScriptDocument | None = None
        self.transcript: Transcript | None = None
        self.editor: ScriptRowEditor | None = None
        self._editor_item: QListWidgetItem | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        # ---------------------------------------------------------
        # Header: KỊCH BẢN & Trạng thái duyệt
        # ---------------------------------------------------------
        header_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        eyebrow = QLabel("PIPELINE · STEP 05")
        eyebrow.setStyleSheet("font-size: 9px; font-weight: 800; color: #06b6d4; letter-spacing: 1.2px;")
        title_col.addWidget(eyebrow)
        title_col.addWidget(label("KỊCH BẢN", "heading"))
        self.summary = QLabel("0 câu")
        self.summary.setStyleSheet("color: #72d7c1; font-weight: 600; font-size: 12px;")
        title_col.addWidget(self.summary)
        header_row.addLayout(title_col, 1)

        self.badge = QLabel("CHƯA DUYỆT")
        self.badge.setObjectName("badge")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setStyleSheet(
            "background: #090f1b; color: #64748b; border: 1px solid #1a273e; "
            "font-weight: 800; padding: 4px 10px; border-radius: 5px; font-size: 10px; letter-spacing: 0.5px;"
        )
        header_row.addWidget(self.badge)
        layout.addLayout(header_row)

        self.stage = QLabel("Chưa có bản chép lời.")
        self.stage.setStyleSheet("color: #475569; font-size: 11px;")
        layout.addWidget(self.stage)

        # ---------------------------------------------------------
        # Toolbar: Tinh giản tối đa theo yêu cầu
        # Giữ: Tìm kiếm, Nạp/Tải SRT dịch, Nạp/Tải SRT gốc
        # Loại bỏ: Thêm câu, Thao tác khác (...)
        # ---------------------------------------------------------
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.buttons: dict[str, QPushButton] = {}
        for action, title in (
            ("add", "➕ Thêm câu"),
            ("delete", "✖ Xóa câu"),
            ("split", "✂ Tách câu"),
            ("merge_previous", "⇈ Gộp trước"),
            ("merge_next", "⇊ Gộp sau"),
            ("undo", "↶ Hoàn tác"),
            ("redo", "↷ Làm lại"),
            ("search", "🔍 Tìm/Thay"),
            ("load", "📂 Nạp SRT dịch"),
            ("save", "⬇ Tải SRT dịch"),
            ("load_source", "📂 Nạp SRT gốc"),
            ("save_source", "⬇ Tải SRT gốc"),
            ("import_vbee", "🎵 Nhập Audio Vbee"),
            ("validate", "✔ Kiểm tra SRT"),
            ("prepare", "🔄 Tạo lại voice"),
        ):
            btn = QPushButton(title)
            btn.clicked.connect(lambda checked=False, name=action: self.action_requested.emit(name))
            self.buttons[action] = btn

        # 1. Nút tìm kiếm (duy nhất trong nhóm thao tác)
        self.btn_search_toggle = QPushButton("🔍 Tìm kiếm")
        self.btn_search_toggle.setStyleSheet("""
            QPushButton {
                background: #0f172a; color: #94a3b8; border: 1px solid #1e293b;
                border-radius: 5px; padding: 5px 12px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background: #1e293b; color: #38bdf8; border-color: #0284c7; }
        """)
        self.btn_search_toggle.clicked.connect(self._toggle_search_box)
        toolbar.addWidget(self.btn_search_toggle)

        # 2. Nạp/Tải SRT dịch (Tiếng Việt)
        self.btn_load_trans = self.buttons["load"]
        self.btn_load_trans.setStyleSheet("""
            QPushButton {
                background: #0c1a2d; color: #38bdf8; border: 1px solid #1e3a5f;
                border-radius: 5px; padding: 5px 10px; font-size: 11px; font-weight: 700;
            }
            QPushButton:hover { background: #132742; border-color: #38bdf8; color: #ffffff; }
        """)
        self.btn_load_trans.setToolTip("Nạp file phụ đề SRT tiếng Việt đã dịch vào kịch bản")
        toolbar.addWidget(self.btn_load_trans)

        self.btn_save_trans = self.buttons["save"]
        self.btn_save_trans.setStyleSheet("""
            QPushButton {
                background: #0c1a2d; color: #38bdf8; border: 1px solid #1e3a5f;
                border-radius: 5px; padding: 5px 10px; font-size: 11px; font-weight: 700;
            }
            QPushButton:hover { background: #132742; border-color: #38bdf8; color: #ffffff; }
        """)
        self.btn_save_trans.setToolTip("Tải/xuất file phụ đề SRT tiếng Việt hoàn chỉnh về máy")
        toolbar.addWidget(self.btn_save_trans)

        # 3. Nạp/Tải SRT gốc (Chưa dịch)
        self.btn_load_source = self.buttons["load_source"]
        self.btn_load_source.setStyleSheet("""
            QPushButton {
                background: #181126; color: #c084fc; border: 1px solid #3b2057;
                border-radius: 5px; padding: 5px 10px; font-size: 11px; font-weight: 700;
            }
            QPushButton:hover { background: #241738; border-color: #a855f7; color: #ffffff; }
        """)
        self.btn_load_source.setToolTip("Nạp file phụ đề SRT gốc chưa dịch")
        toolbar.addWidget(self.btn_load_source)

        self.btn_save_source = self.buttons["save_source"]
        self.btn_save_source.setStyleSheet("""
            QPushButton {
                background: #181126; color: #c084fc; border: 1px solid #3b2057;
                border-radius: 5px; padding: 5px 10px; font-size: 11px; font-weight: 700;
            }
            QPushButton:hover { background: #241738; border-color: #a855f7; color: #ffffff; }
        """)
        self.btn_save_source.setToolTip("Tải/xuất file phụ đề SRT gốc chưa dịch về máy")
        toolbar.addWidget(self.btn_save_source)

        toolbar.addStretch(1)

        # Compatibility dummies
        self.more_button = QToolButton()
        self.more_button.hide()
        self._overflow_actions = []

        layout.addLayout(toolbar)

        # Search / Replace box (toggleable)
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
        self.rows.setSpacing(6)
        self.rows.setStyleSheet("""
            QListWidget#scriptList {
                background-color: #06090f;
                border: 1px solid #162032;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget#scriptList::item {
                background-color: #0b101b;
                border: 1px solid #162032;
                border-radius: 6px;
                padding: 8px 10px;
                margin-bottom: 4px;
                color: #f1f5f9;
            }
            QListWidget#scriptList::item:hover {
                background-color: #121a2c;
                border-color: #24334f;
            }
            QListWidget#scriptList::item:selected {
                background-color: #0f1c30;
                border: 1px solid #0284c7;
                border-left: 3px solid #06b6d4;
            }
        """)
        self.rows.setAccessibleName("Danh sách các câu kịch bản")
        self.rows.itemClicked.connect(self._seek)
        self.rows.itemActivated.connect(self._seek)
        self.rows.currentRowChanged.connect(self._select_editor)
        layout.addWidget(self.rows, 1)

        # Bottom Approval Gate & Primary Export Section
        bottom_box = QFrame()
        bottom_box.setStyleSheet("""
            QFrame {
                background-color: #080d16;
                border: 1px solid #151d2e;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        bottom_layout = QVBoxLayout(bottom_box)
        bottom_layout.setContentsMargins(12, 12, 12, 12)
        bottom_layout.setSpacing(10)

        # Approval Gate
        self.review_checkbox = QCheckBox("Tôi đã kiểm tra toàn bộ kịch bản")
        self.review_checkbox.setEnabled(False)
        self.review_checkbox.setStyleSheet("font-weight: 600; color: #e5eaf4; font-size: 12px;")
        bottom_layout.addWidget(self.review_checkbox)

        self.approve_button = QPushButton("✔ BƯỚC 5: CHỐT KỊCH BẢN (DUYỆT)")
        self.approve_button.setObjectName("primary")
        self.approve_button.setEnabled(False)
        self.approve_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                color: #ffffff;
                font-weight: 800;
                font-size: 12px;
                padding: 10px;
                border-radius: 6px;
                border: 1px solid #34d399;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
            }
            QPushButton:disabled {
                background: #0f172a;
                color: #475569;
                border: 1px solid #1e293b;
            }
        """)
        self.approve_button.setToolTip(
            "Chỉ duyệt khi đã tích xác nhận và không còn lỗi blocking. Lưu revision hash an toàn."
        )
        bottom_layout.addWidget(self.approve_button)

        # Primary Outputs: Export Video MP4 & Export CapCut Project
        export_row = QHBoxLayout()
        export_row.setSpacing(8)

        self.export_video_button = QPushButton("🎞 XUẤT VIDEO MP4")
        self.export_video_button.setEnabled(False)
        self.export_video_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
                color: #ffffff;
                font-weight: 800;
                font-size: 12px;
                padding: 10px;
                border-radius: 6px;
                border: 1px solid #818cf8;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #4f46e5);
            }
            QPushButton:disabled {
                background: #0f172a;
                color: #475569;
                border: 1px solid #1e293b;
            }
        """)
        self.export_video_button.setToolTip("Tạo video MP4 hoàn chỉnh kèm xóa chữ, voice và phụ đề")
        export_row.addWidget(self.export_video_button)

        self.export_capcut_button = QPushButton("🎬 XUẤT DỰ ÁN CAPCUT")
        self.export_capcut_button.setEnabled(False)
        self.export_capcut_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #06b6d4);
                color: #ffffff;
                font-weight: 800;
                font-size: 12px;
                padding: 10px;
                border-radius: 6px;
                border: 1px solid #38bdf8;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:1 #0891b2);
                border-color: #7dd3fc;
            }
            QPushButton:disabled {
                background: #0f172a;
                color: #475569;
                border: 1px solid #1e293b;
            }
        """)
        self.export_capcut_button.setToolTip("Tạo project CapCut có video đã xóa chữ và âm thanh giọng đọc")
        export_row.addWidget(self.export_capcut_button)

        bottom_layout.addLayout(export_row)

        # Compatibility alias
        self.export_button = self.export_video_button
        self.voice_note = QLabel("")
        self.voice_note.hide()

        # CapCut Studio Actions Container Card
        capcut_panel = QFrame()
        capcut_panel.setStyleSheet("""
            QFrame {
                background-color: #070c14;
                border: 1px solid #151f30;
                border-radius: 8px;
                padding: 6px;
            }
        """)
        capcut_col = QVBoxLayout(capcut_panel)
        capcut_col.setContentsMargins(8, 6, 8, 6)
        capcut_col.setSpacing(6)

        # Row 1: Destination path & Change folder button
        capcut_path_row = QHBoxLayout()
        capcut_path_row.setSpacing(6)

        self.capcut_dest_lbl = QLabel("📁 CapCut: com.lveditor.draft")
        self.capcut_dest_lbl.setStyleSheet("color: #8b9bb4; font-size: 11px; font-weight: 500;")
        capcut_path_row.addWidget(self.capcut_dest_lbl, 1)

        self.btn_capcut_folder = QPushButton("Đổi…")
        self.btn_capcut_folder.setStyleSheet("""
            QPushButton {
                padding: 3px 10px;
                font-size: 11px;
                background: #0f1624;
                color: #8b9bb4;
                border: 1px solid #1e2b40;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #182337;
                color: #38bdf8;
                border-color: #0284c7;
            }
        """)
        self.btn_capcut_folder.setToolTip("Thay đổi thư mục lưu project CapCut (com.lveditor.draft)")
        capcut_path_row.addWidget(self.btn_capcut_folder)
        capcut_col.addLayout(capcut_path_row)

        # Row 2: Action buttons (Open Folder & Launch CapCut)
        capcut_act_row = QHBoxLayout()
        capcut_act_row.setSpacing(8)

        self.open_capcut_folder_button = QPushButton("📂 Mở Thư Mục CapCut")
        self.open_capcut_folder_button.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 700;
                background: #0c1424;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: #102038;
                color: #ffffff;
                border-color: #38bdf8;
            }
        """)
        self.open_capcut_folder_button.setToolTip("Mở thư mục lưu trữ project CapCut trong File Explorer")
        capcut_act_row.addWidget(self.open_capcut_folder_button, 1)

        self.open_capcut_button = QPushButton("🚀 Mở CapCut")
        self.open_capcut_button.setStyleSheet("""
            QPushButton {
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 800;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                color: #ffffff;
                border: 1px solid #34d399;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
                border-color: #6ee7b7;
            }
        """)
        self.open_capcut_button.setToolTip("Khởi chạy trực tiếp phần mềm CapCut trên máy tính")
        capcut_act_row.addWidget(self.open_capcut_button, 1)

        capcut_col.addLayout(capcut_act_row)
        bottom_layout.addWidget(capcut_panel)

        self.export_video_button.clicked.connect(self.export_video_requested.emit)
        self.export_capcut_button.clicked.connect(self.export_capcut_requested.emit)
        self.btn_capcut_folder.clicked.connect(self.capcut_folder_requested.emit)
        self.open_capcut_button.clicked.connect(self.open_capcut_requested.emit)
        self.open_capcut_folder_button.clicked.connect(self.open_capcut_folder_requested.emit)

        layout.addWidget(bottom_box)

    def _toggle_search_box(self) -> None:
        vis = not self.search_box.isVisible()
        self.search_box.setVisible(vis)
        if vis:
            self.find_text.setFocus()

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
