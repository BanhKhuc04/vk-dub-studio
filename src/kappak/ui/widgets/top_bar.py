"""Top Bar navigation component for KAPPAK Studio V2."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from kappak.ui.icons import get_icon, get_pixmap


class TopBar(QFrame):
    """Elegant Apple Glass Top Bar with search pill and status indicators."""

    ask_kappak_requested = Signal()
    search_triggered = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setFixedHeight(72)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(16)

        # 1. Left: Brand Logo & Title
        brand_widget = QWidget()
        brand_layout = QHBoxLayout(brand_widget)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(10)

        logo_path = Path(r"D:\Work\Project_AI\ToolVideo\logo\logo_symbol.png")
        if logo_path.is_file():
            logo_lbl = QLabel()
            logo_lbl.setPixmap(
                QPixmap(str(logo_path)).scaled(
                    32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            )
            brand_layout.addWidget(logo_lbl)

        brand_text_box = QWidget()
        brand_text_layout = QVBoxLayout(brand_text_box)
        brand_text_layout.setContentsMargins(0, 0, 0, 0)
        brand_text_layout.setSpacing(1)

        title_lbl = QLabel("KAPPAK")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 900; color: #0A1738; letter-spacing: 0.5px;")
        brand_text_layout.addWidget(title_lbl)

        sub_lbl = QLabel("STUDIO V2")
        sub_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #66779C; letter-spacing: 1px;")
        brand_text_layout.addWidget(sub_lbl)

        brand_layout.addWidget(brand_text_box)
        layout.addWidget(brand_widget)

        layout.addSpacing(24)

        # 2. Center: Large Search Bar Pill
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchPill")
        self.search_input.setPlaceholderText("Tìm kiếm công cụ, dự án, mẫu... (Ctrl + K)")
        self.search_input.setFixedSize(580, 42)
        self.search_input.returnPressed.connect(self._on_search_enter)

        # Search icon positioned inside
        search_icon_lbl = QLabel(self.search_input)
        search_icon_lbl.setPixmap(get_pixmap("search", color="#66779C", size=18))
        search_icon_lbl.move(14, 12)
        search_icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        search_layout.addWidget(self.search_input)
        layout.addWidget(search_container)

        layout.addStretch()

        # 3. Right: Status Pill, Notifications, User Chip & Ask KAPPAK
        # 3a. AI Status Pill
        self.status_pill = QFrame()
        self.status_pill.setObjectName("statusPill")
        status_layout = QHBoxLayout(self.status_pill)
        status_layout.setContentsMargins(10, 4, 10, 4)
        status_layout.setSpacing(6)

        dot = QLabel("●")
        dot.setStyleSheet("color: #10B981; font-size: 10px;")
        status_layout.addWidget(dot)

        status_text = QLabel("AI Sẵn sàng")
        status_text.setStyleSheet("color: #065F46; font-size: 12px; font-weight: 700;")
        status_layout.addWidget(status_text)

        chevron = QLabel()
        chevron.setPixmap(get_pixmap("chevron_down", color="#065F46", size=12))
        status_layout.addWidget(chevron)

        layout.addWidget(self.status_pill)

        # 3b. Notification Bell
        self.btn_bell = QPushButton()
        self.btn_bell.setProperty("class", "railTab")
        self.btn_bell.setFixedSize(38, 38)
        self.btn_bell.setIcon(get_icon("bell", color="#66779C", active_color="#2777FF", size=20))
        self.btn_bell.setIconSize(QSize(20, 20))
        self.btn_bell.setToolTip("Thông báo")
        self.btn_bell.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.btn_bell)

        # 3c. User Profile Chip
        user_chip = QFrame()
        user_chip.setObjectName("userProfileChip")
        user_layout = QHBoxLayout(user_chip)
        user_layout.setContentsMargins(6, 4, 10, 4)
        user_layout.setSpacing(8)

        # Avatar circle
        avatar_lbl = QLabel("VK")
        avatar_lbl.setFixedSize(30, 30)
        avatar_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_lbl.setStyleSheet(
            "background-color: #2777FF; color: #FFFFFF; border-radius: 15px; font-size: 11px; font-weight: 800;"
        )
        user_layout.addWidget(avatar_lbl)

        user_name = QLabel("Văn Khúc")
        user_name.setStyleSheet("color: #0A1738; font-size: 13px; font-weight: 700;")
        user_layout.addWidget(user_name)

        user_chev = QLabel()
        user_chev.setPixmap(get_pixmap("chevron_down", color="#66779C", size=12))
        user_layout.addWidget(user_chev)

        layout.addWidget(user_chip)

        # 3d. ✦ Ask KAPPAK Global Trigger Button
        self.btn_ask_kappak = QPushButton("✦ Ask KAPPAK")
        self.btn_ask_kappak.setProperty("class", "askKappakTrigger")
        self.btn_ask_kappak.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ask_kappak.clicked.connect(self.ask_kappak_requested.emit)
        layout.addWidget(self.btn_ask_kappak)

    def _on_search_enter(self) -> None:
        text = self.search_input.text().strip()
        if text:
            self.search_triggered.emit(text)
