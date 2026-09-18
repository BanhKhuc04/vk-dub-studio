"""KAPPAK Studio — 📱 Social."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget


class SocialView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        # Header
        header = QVBoxLayout()
        header.setSpacing(4)
        t = QLabel("📱 Social")
        t.setProperty("class", "moduleTitle")
        st = QLabel("Quản lý lịch nội dung, soạn bài và xuất bản đa nền tảng")
        st.setProperty("class", "moduleSubtitle")
        header.addWidget(t)
        header.addWidget(st)
        layout.addLayout(header)

        # Main Card Container
        card = QFrame()
        card.setProperty("class", "glassCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        
        info = QLabel("✨ Module đang sẵn sàng theo kiến trúc KAPPAK Local-First.")
        info.setStyleSheet("font-size: 14px; color: #475569;")
        card_layout.addWidget(info)
        card_layout.addStretch()

        layout.addWidget(card, 1)
