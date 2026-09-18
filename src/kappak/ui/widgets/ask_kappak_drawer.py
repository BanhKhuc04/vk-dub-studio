"""Ask KAPPAK AI assistant slide-over drawer widget."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from kappak.ui.icons import get_icon, get_pixmap


class AskKappakDrawer(QFrame):
    """Slide-over glass panel providing AI assistant interface."""

    close_requested = Signal()
    prompt_submitted = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("askKappakDrawer")
        self.setFixedWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 1. Header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_box = QWidget()
        title_layout = QVBoxLayout(title_box)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        title = QLabel("✦ KAPPAK Assistant")
        title.setStyleSheet("font-size: 17px; font-weight: 800; color: #0A1738;")
        title_layout.addWidget(title)

        subtitle = QLabel("Trợ lý sáng tạo & tự động hóa nội dung")
        subtitle.setStyleSheet("font-size: 11px; color: #66779C; font-weight: 500;")
        title_layout.addWidget(subtitle)

        header_layout.addWidget(title_box)
        header_layout.addStretch()

        btn_close = QPushButton()
        btn_close.setProperty("class", "railTab")
        btn_close.setFixedSize(32, 32)
        btn_close.setIcon(get_icon("close", color="#66779C", active_color="#0A1738", size=16))
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.close_requested.emit)
        header_layout.addWidget(btn_close)

        layout.addWidget(header)

        # 2. Messages / Suggestions Body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.chat_layout = QVBoxLayout(scroll_content)
        self.chat_layout.setContentsMargins(0, 8, 0, 8)
        self.chat_layout.setSpacing(12)

        # Welcome Card
        welcome_card = QFrame()
        welcome_card.setStyleSheet(
            "background-color: #F8FAFC; border: 1px solid rgba(76, 104, 153, 0.12); "
            "border-radius: 16px; padding: 14px;"
        )
        w_layout = QVBoxLayout(welcome_card)
        w_layout.setSpacing(8)

        msg = QLabel(
            "Chào <b>Văn Khúc</b>! Tôi là trợ lý AI tích hợp của <b>KAPPAK Studio</b>.<br><br>"
            "Tôi có thể hỗ trợ bạn điều khiển quy trình sản xuất nội dung, tìm kiếm tài nguyên, "
            "hoặc tự động hóa tác vụ chỉ bằng một câu lệnh."
        )
        msg.setWordWrap(True)
        msg.setStyleSheet("color: #0A1738; font-size: 13px; line-height: 1.5;")
        w_layout.addWidget(msg)
        self.chat_layout.addWidget(welcome_card)

        # Prompt Suggestions Title
        sugg_title = QLabel("GỢI Ý THỰC HIỆN NHANH")
        sugg_title.setStyleSheet("color: #66779C; font-size: 11px; font-weight: 800; letter-spacing: 0.5px; margin-top: 10px;")
        self.chat_layout.addWidget(sugg_title)

        # Suggestion Chips
        chips = [
            "📥 Tải toàn bộ video kênh TikTok theo hashtag",
            "🎙️ Dịch video sang tiếng Việt & lồng giọng AI",
            "✂️ Tự động lọc khoảng lặng & cắt video 9:16",
            "📁 Quét và chống trùng lặp tài nguyên trong thư viện",
        ]
        for chip_text in chips:
            chip_btn = QPushButton(chip_text)
            chip_btn.setStyleSheet(
                "background-color: #FFFFFF; border: 1px solid rgba(76, 104, 153, 0.15); "
                "border-radius: 12px; padding: 10px 14px; text-align: left; "
                "color: #0A1738; font-size: 12px; font-weight: 600;"
            )
            chip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            chip_btn.clicked.connect(lambda _, t=chip_text: self._on_chip_clicked(t))
            self.chat_layout.addWidget(chip_btn)

        self.chat_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # 3. Prompt Input Box at Bottom
        input_container = QFrame()
        input_container.setStyleSheet(
            "background-color: #FFFFFF; border: 1.5px solid rgba(76, 104, 153, 0.20); "
            "border-radius: 22px; padding: 4px 6px;"
        )
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(12, 4, 6, 4)
        input_layout.setSpacing(8)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Nhập yêu cầu cho trợ lý KAPPAK...")
        self.input_field.setStyleSheet("border: none; background: transparent; font-size: 13px; color: #0A1738;")
        self.input_field.returnPressed.connect(self._send_prompt)
        input_layout.addWidget(self.input_field)

        self.btn_send = QPushButton()
        self.btn_send.setFixedSize(34, 34)
        self.btn_send.setStyleSheet(
            "background-color: #2777FF; border: none; border-radius: 17px;"
        )
        self.btn_send.setIcon(get_icon("send", color="#FFFFFF", active_color="#FFFFFF", size=16))
        self.btn_send.setIconSize(QSize(16, 16))
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.clicked.connect(self._send_prompt)
        input_layout.addWidget(self.btn_send)

        layout.addWidget(input_container)

    def _on_chip_clicked(self, text: str) -> None:
        self.input_field.setText(text)
        self._send_prompt()

    def _send_prompt(self) -> None:
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()

        # Add user prompt bubble
        user_bubble = QLabel(f"<b>Bạn:</b> {text}")
        user_bubble.setWordWrap(True)
        user_bubble.setStyleSheet(
            "background-color: #E7F1FF; color: #0A1738; border-radius: 12px; padding: 10px 14px; font-size: 12px;"
        )
        self.chat_layout.addWidget(user_bubble)

        # AI response simulation / dispatch
        ai_bubble = QLabel("<b>KAPPAK:</b> Đang xử lý yêu cầu thông qua Local Job Manager...")
        ai_bubble.setWordWrap(True)
        ai_bubble.setStyleSheet(
            "background-color: #F8FAFC; color: #2777FF; border-radius: 12px; padding: 10px 14px; font-size: 12px; font-style: italic;"
        )
        self.chat_layout.addWidget(ai_bubble)

        self.prompt_submitted.emit(text)
