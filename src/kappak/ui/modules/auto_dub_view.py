"""KAPPAK Studio — 🎙️ Auto Dub."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget


class AutoDubView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        # Header
        header = QVBoxLayout()
        header.setSpacing(4)
        t = QLabel("🎙️ Auto Dub")
        t.setProperty("class", "moduleTitle")
        st = QLabel("Lồng tiếng tự động hoàn toàn bằng AI nội bộ (Speech-to-Text → Translate → VieNeu)")
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
