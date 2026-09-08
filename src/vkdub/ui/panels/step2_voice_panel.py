"""VK Dub Studio — Step 02: Voice Configuration Panel.

Right contextual panel for selecting voice & speed:
- Voice: Ngoc Huyen (default)
- Speed: 1.1x (default)
- Preview voice
- Back / Continue navigation
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Step2VoicePanel(QFrame):
    """Contextual panel for Step 2: Voice & Speed Settings."""

    voice_changed = Signal()
    test_listen_requested = Signal()
    back_requested = Signal()
    continue_requested = Signal()
    manage_voices_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("step2Panel")
        self.setStyleSheet("""
            QFrame#step2Panel {
                background-color: #050810;
            }
            QLabel.eyebrowTag {
                font-size: 9px;
                font-weight: 800;
                color: #06b6d4;
                letter-spacing: 1.2px;
            }
            QLabel.panelHeader {
                font-size: 16px;
                font-weight: 800;
                color: #f8fafc;
                letter-spacing: 0.3px;
            }
            QLabel.panelSub {
                font-size: 11px;
                color: #64748b;
                line-height: 1.4;
            }
            QLabel.fieldLabel {
                font-size: 12px;
                font-weight: 700;
                color: #cbd5e1;
            }
            QComboBox {
                background-color: #070c16;
                color: #f8fafc;
                border: 1px solid #1a283e;
                border-radius: 7px;
                padding: 8px 12px;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #38bdf8;
            }
            QComboBox::drop-down {
                border: none;
            }
            QPushButton.primaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:0.6 #0369a1, stop:1 #06b6d4);
                color: #ffffff;
                font-size: 13px;
                font-weight: 800;
                padding: 11px 18px;
                border: 1px solid #38bdf8;
                border-radius: 7px;
                letter-spacing: 0.3px;
            }
            QPushButton.primaryBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:0.6 #0284c7, stop:1 #22d3ee);
                border-color: #7dd3fc;
                color: #ffffff;
            }
            QPushButton.navBackBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #131d2e, stop:1 #0e1626);
                color: #cbd5e1;
                font-size: 12px;
                font-weight: 600;
                padding: 10px 16px;
                border: 1px solid #1e2f4a;
                border-radius: 7px;
            }
            QPushButton.navBackBtn:hover {
                background: #18263d;
                color: #38bdf8;
                border-color: #0284c7;
            }
            QPushButton.actionBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #101d32, stop:1 #0a1322);
                color: #38bdf8;
                font-size: 12px;
                font-weight: 700;
                padding: 9px 14px;
                border: 1px solid #1a2c47;
                border-radius: 7px;
            }
            QPushButton.actionBtn:hover {
                background: #152540;
                border-color: #38bdf8;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 1. Header
        header_col = QVBoxLayout()
        header_col.setSpacing(3)

        eyebrow = QLabel("PIPELINE · STEP 02")
        eyebrow.setProperty("class", "eyebrowTag")
        header_col.addWidget(eyebrow)

        title = QLabel("02 CẤU HÌNH GIỌNG ĐỌC (VOICE)")
        title.setProperty("class", "panelHeader")
        header_col.addWidget(title)

        subtitle = QLabel("Chọn giọng thuyết minh tự nhiên và tốc độ đọc phù hợp với nhịp video")
        subtitle.setProperty("class", "panelSub")
        header_col.addWidget(subtitle)
        layout.addLayout(header_col)

        # 2. Main Config Card
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0e1627, stop:1 #090f1b);
                border: 1px solid #1a2942;
                border-radius: 10px;
                padding: 14px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(14)

        # Voice Field
        voice_col = QVBoxLayout()
        voice_col.setSpacing(6)
        lbl_voice = QLabel("Giọng đọc (Voice):")
        lbl_voice.setProperty("class", "fieldLabel")
        voice_col.addWidget(lbl_voice)

        self.voice_combo = QComboBox()
        self.voice_combo.addItem("HN - Ngọc Huyền (Nữ miền Bắc • Truyền cảm)", "vbee-ngoc-huyen")
        self.voice_combo.addItem("HN - Phương Trang (Nữ miền Bắc)", "vbee-phuong-trang")
        self.voice_combo.addItem("SG - Minh Hoàng (Nam miền Nam)", "vbee-minh-hoang")
        self.voice_combo.addItem("HN - Mạnh Dũng (Nam miền Bắc)", "vbee-manh-dung")
        self.voice_combo.currentIndexChanged.connect(lambda *_: self.voice_changed.emit())
        voice_col.addWidget(self.voice_combo)
        card_layout.addLayout(voice_col)

        # Speed Field
        speed_col = QVBoxLayout()
        speed_col.setSpacing(6)
        lbl_speed = QLabel("Tốc độ đọc (Speed):")
        lbl_speed.setProperty("class", "fieldLabel")
        speed_col.addWidget(lbl_speed)

        self.speed_combo = QComboBox()
        for label_text, val in (
            ("0.8x (Chậm)", 0.8),
            ("0.9x", 0.9),
            ("1.0x (Tốc độ thường)", 1.0),
            ("1.1x (Khuyên dùng cho Douyin)", 1.1),
            ("1.2x (Nhanh vừa)", 1.2),
            ("1.3x (Nhanh)", 1.3),
        ):
            self.speed_combo.addItem(label_text, val)

        # Default 1.1x
        idx = self.speed_combo.findData(1.1)
        self.speed_combo.setCurrentIndex(idx if idx >= 0 else 3)
        self.speed_combo.currentIndexChanged.connect(lambda *_: self.voice_changed.emit())
        speed_col.addWidget(self.speed_combo)
        card_layout.addLayout(speed_col)

        # Waveform Visualization Placeholder
        wave_box = QFrame()
        wave_box.setStyleSheet("""
            QFrame {
                background-color: #060a12;
                border: 1px solid #131d2e;
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)
        wave_layout = QHBoxLayout(wave_box)
        wave_layout.setContentsMargins(6, 4, 6, 4)
        wave_layout.setSpacing(6)
        wave_tag = QLabel("WAVEFORM")
        wave_tag.setStyleSheet("color: #475569; font-size: 8px; font-weight: 800; letter-spacing: 1px;")
        wave_layout.addWidget(wave_tag)
        wave_bars = QLabel(" ▂▃▅▆▇▆▅▃▂  ▂▃▅▆▇█▇▆▅▃▂  ▂▃▅▆▇▆▅▃ ")
        wave_bars.setStyleSheet("color: #06b6d4; font-size: 12px; font-family: monospace; letter-spacing: 1.5px;")
        wave_layout.addWidget(wave_bars, 1)
        card_layout.addWidget(wave_box)

        # Test Listen Button
        self.btn_test_listen = QPushButton("▶ Nghe thử giọng đọc mẫu")
        self.btn_test_listen.setProperty("class", "actionBtn")
        self.btn_test_listen.clicked.connect(self.test_listen_requested.emit)
        self.btn_listen = self.btn_test_listen
        card_layout.addWidget(self.btn_test_listen)

        layout.addWidget(card)

        # Helper hint
        hint_lbl = QLabel("💡 Mặc định tối ưu: Ngọc Huyền · Tốc độ 1.1x khớp tốt nhất với nhịp video ngắn.")
        hint_lbl.setStyleSheet("color: #72d7c1; font-size: 11px; font-style: italic;")
        hint_lbl.setWordWrap(True)
        layout.addWidget(hint_lbl)

        layout.addStretch(1)

        # 3. Navigation Footer (Back & Continue)
        nav_row = QHBoxLayout()
        nav_row.setSpacing(10)

        self.btn_back = QPushButton("← Quay lại")
        self.btn_back.setProperty("class", "navBackBtn")
        self.btn_back.clicked.connect(self.back_requested.emit)
        nav_row.addWidget(self.btn_back)

        self.btn_continue = QPushButton("Tiếp tục: Khung che mờ →")
        self.btn_continue.setProperty("class", "primaryBtn")
        self.btn_continue.clicked.connect(self.continue_requested.emit)
        nav_row.addWidget(self.btn_continue, 1)

        layout.addLayout(nav_row)

    def voice_summary(self) -> str:
        v_name = self.voice_combo.currentText().split("(")[0].strip()
        spd = self.speed_combo.currentData() or 1.1
        return f"{v_name} · {spd}x"
