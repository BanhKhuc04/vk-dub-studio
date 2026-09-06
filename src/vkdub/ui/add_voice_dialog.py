from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class AddVoiceDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Thêm giọng của bạn")
        self.resize(530, 260)
        layout = QVBoxLayout(self)
        hint = QLabel(
            "Chọn mẫu giọng rõ, ít tạp âm, dài 3–30 giây. VieNeu dùng tối đa 8 giây; "
            "không cần nhập lời mẫu. Âm thanh được xử lý trên máy này."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setMaxLength(100)
        self.reference_input = QLineEdit()
        self.reference_input.setReadOnly(True)
        form.addRow("Tên giọng", self.name_input)
        row = QHBoxLayout()
        row.addWidget(self.reference_input, 1)
        choose = QPushButton("Chọn WAV/MP3")
        choose.clicked.connect(self.choose)
        row.addWidget(choose)
        form.addRow("Âm thanh mẫu", row)
        layout.addLayout(form)
        self.rights = QCheckBox("Tôi có quyền sử dụng mẫu giọng này.")
        layout.addWidget(self.rights)
        self.status = QLabel()
        layout.addWidget(self.status)
        self.submit = QPushButton("Lưu giọng")
        self.submit.clicked.connect(self.validate_and_accept)
        layout.addWidget(self.submit)

    def choose(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Chọn mẫu giọng", "", "Âm thanh (*.wav *.mp3 *.m4a *.flac *.ogg)"
        )
        if filename:
            self.reference_input.setText(filename)

    def validate_and_accept(self) -> None:
        if not self.name_input.text().strip() or not Path(self.reference_input.text()).is_file():
            self.status.setText("Nhập tên và chọn mẫu giọng trước khi lưu.")
        elif not self.rights.isChecked():
            self.status.setText("Xác nhận quyền sử dụng mẫu giọng trước khi lưu.")
        else:
            self.accept()
