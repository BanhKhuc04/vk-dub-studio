from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout

from vkdub.services.credential_service import VbeeAppStore, VbeeTokenStore
from vkdub.services.tts_usage import TTSUsage
from vkdub.ui.left_config_panel import label

if TYPE_CHECKING:
    from vkdub.ui.tts_controller import TTSController


class VbeeDialog(QDialog):
    def __init__(self, controller: "TTSController") -> None:
        super().__init__(controller.window)
        self.controller = controller
        self.setWindowTitle("VK Dub Studio — Vbee API")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(600, 400)
        layout = QVBoxLayout(self)
        layout.addWidget(label("VBEE • APP ID & TOKEN", "heading"))
        layout.addWidget(
            label(
                "Lấy App ID và token từ tài khoản Vbee API. "
                "Gói Studio thông thường có thể không có quyền API."
            )
        )
        link = label(
            '<a href="https://api-docs.vbee.vn/tao-ung-dung-app-id-va-token">'
            "Hướng dẫn chính thức Vbee</a>"
        )
        link.setOpenExternalLinks(True)
        layout.addWidget(link)
        self.app_id = QLineEdit()
        self.app_id.setPlaceholderText("App ID mới")
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.token.setPlaceholderText("Access token mới")
        layout.addWidget(self.app_id)
        layout.addWidget(self.token)
        actions = QHBoxLayout()
        self.save_button = QPushButton("Lưu thông tin")
        self.delete_button = QPushButton("Xóa thông tin")
        self.test_button = QPushButton("Kiểm tra / Tải giọng")
        for button in (self.save_button, self.delete_button, self.test_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.status = label(controller.credential_reason)
        layout.addWidget(self.status)
        self.usage = label("")
        layout.addWidget(self.usage)
        layout.addWidget(
            label(
                "Kiểm tra chỉ đọc danh sách giọng; không tổng hợp hay xác nhận credit còn lại. "
                "Giá theo gói/giọng: chưa biết. "
                "Ước tính — hạn mức thực tế do nhà cung cấp quyết định."
            )
        )
        close = QPushButton("Đóng")
        layout.addWidget(close)
        close.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.save)
        self.delete_button.clicked.connect(self.delete)
        self.test_button.clicked.connect(self.test)
        self.refresh()

    def save(self) -> None:
        if self.controller.window.busy:
            return
        try:
            # Validate both before changing either vault entry.
            for value in (self.app_id.text(), self.token.text()):
                if (
                    not value.strip()
                    or len(value.strip()) > 1024
                    or any(c.isspace() for c in value.strip())
                ):
                    raise ValueError("Điền App ID và token hợp lệ (không có khoảng trắng).")
            VbeeTokenStore().save(self.token.text())
            VbeeAppStore().save(self.app_id.text())
            self.app_id.clear()
            self.token.clear()
            self.status.setText("Đã lưu trong Windows Credential Manager; chưa kiểm tra quyền API.")
        except (RuntimeError, ValueError) as exc:
            self.status.setText(str(exc))
        self.controller.read_credentials()
        self.controller.window._refresh()

    def delete(self) -> None:
        if self.controller.window.busy:
            return
        try:
            VbeeTokenStore().delete()
            VbeeAppStore().delete()
            self.token.clear()
            self.app_id.clear()
            self.status.setText("Đã xóa thông tin Vbee trên máy này.")
        except RuntimeError as exc:
            self.status.setText(str(exc))
        self.controller.read_credentials()
        self.controller.window._refresh()

    def test(self) -> None:
        if self.app_id.text() or self.token.text():
            self.status.setText("Lưu thông tin mới trước khi kiểm tra.")
            return
        self.controller.test_connection()

    def refresh(self) -> None:
        for widget in (
            self.app_id,
            self.token,
            self.save_button,
            self.delete_button,
            self.test_button,
        ):
            widget.setEnabled(not self.controller.window.busy)
        try:
            requests, chars, unknown = TTSUsage().monthly()
            self.usage.setText(
                f"Tháng này (UTC, máy này): {requests} lượt, {chars:,} ký tự gửi, "
                f"{unknown} lượt chưa biết kết quả/chi phí. Đối chiếu hóa đơn Vbee."
            )
        except Exception:
            self.usage.setText("Không đọc được thống kê Vbee cục bộ.")

    def reject(self) -> None:
        self.token.clear()
        self.app_id.clear()
        super().reject()
