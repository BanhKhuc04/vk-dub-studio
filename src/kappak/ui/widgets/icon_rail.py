"""Left Icon Rail navigation component for KAPPAK Studio V2."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from kappak.ui.icons import get_icon, get_pixmap


class IconRail(QFrame):
    """Slim 74px vertical icon rail navigation."""

    module_selected = Signal(int)
    help_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("iconRail")
        self.setFixedWidth(74)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(12)

        # 1. macOS Style Traffic Dots at Top
        dots_widget = QWidget()
        dots_widget.setFixedHeight(16)
        dots_layout = QVBoxLayout(dots_widget)
        dots_layout.setContentsMargins(0, 0, 0, 0)
        dots_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        dots_lbl = QLabel()
        dots_pixmap = QPixmap(48, 12)
        dots_pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(dots_pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FF5F56"))
        p.drawEllipse(4, 1, 10, 10)
        p.setBrush(QColor("#FFBD2E"))
        p.drawEllipse(19, 1, 10, 10)
        p.setBrush(QColor("#27C93F"))
        p.drawEllipse(34, 1, 10, 10)
        p.end()
        dots_lbl.setPixmap(dots_pixmap)
        dots_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(dots_lbl)

        layout.addSpacing(6)

        # 2. Main Navigation Buttons
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        # Map icon names to indices:
        # 0: Home, 1: Data Studio, 2: Downloader, 3: Auto Video, 4: Auto Dub, 5: Social, 6: Today
        self.items = [
            ("home", "Trang chủ (Home)", 0),
            ("folder", "Data Studio (Dữ liệu & Dự án)", 1),
            ("sparkles", "Auto Video (Sáng tạo Video)", 3),
            ("video", "Downloader (Tải nội dung)", 2),
            ("mic", "Auto Dub (Lồng tiếng AI)", 4),
            ("share", "Social (Kênh & Phân phối)", 5),
            ("calendar", "Today (Lịch & Nhiệm vụ)", 6),
        ]

        self.buttons: dict[int, QPushButton] = {}

        for icon_name, tooltip, idx in self.items:
            btn = QPushButton()
            btn.setProperty("class", "railTab")
            btn.setCheckable(True)
            btn.setFixedSize(50, 50)
            btn.setIcon(get_icon(icon_name, color="#66779C", active_color="#2777FF", size=22))
            btn.setIconSize(QSize(22, 22))
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            if idx == 0:
                btn.setChecked(True)

            self.button_group.addButton(btn, idx)
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
            self.buttons[idx] = btn

        self.button_group.idClicked.connect(self._on_item_clicked)

        layout.addStretch()

        # 3. Bottom Utility Buttons: Help & Settings
        self.btn_help = QPushButton()
        self.btn_help.setProperty("class", "railTab")
        self.btn_help.setFixedSize(46, 46)
        self.btn_help.setIcon(get_icon("help", color="#8595B2", active_color="#2777FF", size=20))
        self.btn_help.setIconSize(QSize(20, 20))
        self.btn_help.setToolTip("Trợ giúp & Hướng dẫn")
        self.btn_help.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_help.clicked.connect(self.help_requested.emit)
        layout.addWidget(self.btn_help, alignment=Qt.AlignmentFlag.AlignCenter)

        self.btn_sun = QPushButton()
        self.btn_sun.setProperty("class", "railTab")
        self.btn_sun.setFixedSize(46, 46)
        self.btn_sun.setIcon(get_icon("sun", color="#8595B2", active_color="#2777FF", size=20))
        self.btn_sun.setIconSize(QSize(20, 20))
        self.btn_sun.setToolTip("Chế độ hiển thị")
        self.btn_sun.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.btn_sun, alignment=Qt.AlignmentFlag.AlignCenter)

        # 4. Brand Mark at the very bottom
        logo_path = Path(r"D:\Work\Project_AI\ToolVideo\logo\logo_symbol.png")
        if logo_path.is_file():
            logo_lbl = QLabel()
            logo_lbl.setPixmap(
                QPixmap(str(logo_path)).scaled(
                    28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            )
            logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_lbl.setToolTip("KAPPAK Studio")
            layout.addWidget(logo_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

    def select_module(self, idx: int) -> None:
        """Select a module programmatically."""
        if idx in self.buttons:
            self.buttons[idx].setChecked(True)

    def _on_item_clicked(self, idx: int) -> None:
        self.module_selected.emit(idx)
