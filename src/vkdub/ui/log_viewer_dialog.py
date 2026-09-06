from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from vkdub.utils.logging import clear_logs, get_log_file_path, read_recent_logs
from vkdub.version import APP_BRANDING


class LogViewerDialog(QDialog):
    """Diagnostic and activity log viewer dialog (Phase 10)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Nhật ký hệ thống (Logs) — {APP_BRANDING}")
        self.resize(760, 520)
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("📋 NHẬT KÝ HOẠT ĐỘNG & CHẨN ĐOÁN HỆ THỐNG")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #38bdf8;")
        hdr.addWidget(title)
        hdr.addStretch()

        self.btn_refresh = QPushButton("Làm mới")
        self.btn_refresh.clicked.connect(self.refresh_logs)
        hdr.addWidget(self.btn_refresh)
        layout.addLayout(hdr)

        # Log content text browser
        self.txt_log = QTextBrowser()
        self.txt_log.setStyleSheet(
            "background-color: #0b0f19; color: #cbd5e1; font-family: Consolas, monospace; "
            "font-size: 12px; border: 1px solid #1e293b; border-radius: 6px; padding: 10px;"
        )
        layout.addWidget(self.txt_log, 1)

        # Action buttons
        btn_row = QHBoxLayout()

        self.btn_copy = QPushButton("Sao chép toàn bộ")
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        btn_row.addWidget(self.btn_copy)

        self.btn_open_folder = QPushButton("Mở thư mục Log")
        self.btn_open_folder.clicked.connect(self._open_log_folder)
        btn_row.addWidget(self.btn_open_folder)

        self.btn_clear = QPushButton("Xóa trắng nhật ký")
        self.btn_clear.clicked.connect(self._clear_logs)
        btn_row.addWidget(self.btn_clear)

        btn_row.addStretch()

        self.btn_close = QPushButton("Đóng")
        self.btn_close.setObjectName("primary")
        self.btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_close)

        layout.addLayout(btn_row)

        self.refresh_logs()

    def refresh_logs(self) -> None:
        content = read_recent_logs()
        self.txt_log.setPlainText(content)
        cursor = self.txt_log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.txt_log.setTextCursor(cursor)

    def _copy_to_clipboard(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.txt_log.toPlainText())
            QMessageBox.information(
                self, "Đã sao chép", "Toàn bộ nội dung nhật ký đã được sao chép vào bộ nhớ đệm."
            )

    def _open_log_folder(self) -> None:
        log_path = get_log_file_path()
        folder = log_path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _clear_logs(self) -> None:
        ans = QMessageBox.question(
            self,
            "Xác nhận xóa",
            "Bạn có chắc muốn xóa toàn bộ nội dung nhật ký hiện tại không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans == QMessageBox.StandardButton.Yes:
            clear_logs()
            self.refresh_logs()
