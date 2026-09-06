from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vkdub.domain.script import ScriptLine, estimated_voice_ms


class ScriptTextEdit(QPlainTextEdit):
    command_requested = Signal(str)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.matches(QKeySequence.StandardKey.Undo):
            self.command_requested.emit("undo")
            event.accept()
        elif event.matches(QKeySequence.StandardKey.Redo):
            self.command_requested.emit("redo")
            event.accept()
        else:
            super().keyPressEvent(event)


class ScriptRowEditor(QWidget):
    changed = Signal(str, str, int, int)
    play_requested = Signal(int, int)
    regenerate_requested = Signal(str)
    command_requested = Signal(str)

    def __init__(self, line: ScriptLine, source_text: str, index: int) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("scriptCard")
        self.setStyleSheet("#scriptCard { background: #14231f; border-radius: 5px; }")
        self.line_id = line.id
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        hdr = QLabel(f"#{index:02}  •  CHỈNH SỬA CÂU")
        hdr.setStyleSheet("font-weight: 700; color: #72d7c1; font-size: 13px;")
        layout.addWidget(hdr)
        times = QHBoxLayout()
        self.start = QDoubleSpinBox()
        self.end = QDoubleSpinBox()
        for title, spin, value in (
            ("Bắt đầu", self.start, line.start_ms),
            ("Kết thúc", self.end, line.end_ms),
        ):
            spin.setRange(-3_600_000, 3_600_000)
            spin.setDecimals(3)
            spin.setSingleStep(0.1)
            spin.setSuffix(" s")
            spin.setPrefix("Từ " if spin is self.start else "Đến ")
            spin.setValue(value / 1000)
            spin.setAccessibleName(title)
            spin.setToolTip(title + " (giây)")
            times.addWidget(spin)
        layout.addLayout(times)
        lbl_source = QLabel("Gốc:")
        lbl_source.setStyleSheet("color: #929fb5; font-size: 11px; font-weight: 600;")
        layout.addWidget(lbl_source)
        self.source = QPlainTextEdit(source_text or "Câu thêm / nhập SRT — chưa gắn câu nguồn")
        self.source.setReadOnly(True)
        self.source.setMaximumHeight(65)
        self.source.setAccessibleName("Bản gốc chỉ đọc")
        layout.addWidget(self.source)
        lbl_vi = QLabel("Tiếng Việt:")
        lbl_vi.setStyleSheet("color: #72d7c1; font-size: 11px; font-weight: 600;")
        layout.addWidget(lbl_vi)
        self.text = ScriptTextEdit(line.text)
        self.text.command_requested.connect(self.command_requested)
        self.text.setPlaceholderText("Nhập nội dung tiếng Việt…")
        self.text.setMinimumHeight(75)
        self.text.setMaximumHeight(100)
        self.text.setAccessibleName("Nội dung tiếng Việt")
        self.text.setUndoRedoEnabled(False)  # All edits use the shared document undo stack.
        layout.addWidget(self.text)
        self.duration = QLabel()
        layout.addWidget(self.duration)
        self.issues = QLabel()
        layout.addWidget(self.issues)
        buttons = QHBoxLayout()
        self.play_button = QPushButton("▶ Phát câu này")
        self.regenerate = QPushButton("🔄 Dịch lại câu")
        self.regenerate.setToolTip(
            "Gửi toàn bộ câu gốc liên kết tới Gemini; có thể tính phí. "
            "Sau khi tách, câu con vẫn liên kết với toàn bộ câu gốc."
        )
        self.regenerate.setEnabled(bool(line.source_ids))
        self.voice_button = QPushButton("Tạo lại voice")
        self.voice_button.setEnabled(False)
        self.voice_button.setToolTip("Chưa triển khai nhà cung cấp voice.")
        for button in (self.play_button, self.regenerate, self.voice_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.voice_status = QLabel("Chưa có voice.")
        self.voice_status.setWordWrap(True)
        layout.addWidget(self.voice_status)
        self.listen_button = QPushButton("Nghe voice")
        self.listen_button.setEnabled(False)
        layout.addWidget(self.listen_button)
        self.play_button.clicked.connect(
            lambda: self.play_requested.emit(
                round(self.start.value() * 1000), round(self.end.value() * 1000)
            )
        )
        self.regenerate.clicked.connect(lambda: self.regenerate_requested.emit(self.line_id))
        self.text.textChanged.connect(self._changed)
        self.start.valueChanged.connect(self._changed)
        self.end.valueChanged.connect(self._changed)
        self.update_duration(line)

    def update_duration(self, line: ScriptLine) -> None:
        self.duration.setText(
            f"Câu: {(line.end_ms - line.start_ms) / 1000:.2f}s • "
            f"Lời đọc ước tính: {estimated_voice_ms(line.text) / 1000:.2f}s"
        )

    def _changed(self) -> None:
        self.changed.emit(
            self.line_id,
            self.text.toPlainText(),
            round(self.start.value() * 1000),
            round(self.end.value() * 1000),
        )

    def cursor_index(self) -> int:
        # QTextCursor positions are UTF-16 units; Python split indexes are Unicode codepoints.
        raw = self.text.toPlainText().encode("utf-16-le")
        return len(raw[: self.text.textCursor().position() * 2].decode("utf-16-le"))
