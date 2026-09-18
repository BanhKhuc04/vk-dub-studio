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

from vkdub.ui.theme import apply_brutalist_shadow


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
                background-color: #ffffff;
            }
            QLabel.eyebrowTag {
                font-size: 11px;
                font-weight: 900;
                color: #2457f5;
                letter-spacing: 1.2px;
            }
            QLabel.panelHeader {
                font-size: 21px;
                font-weight: 900;
                color: #0f172a;
                letter-spacing: 0.3px;
            }
            QLabel.panelSub {
                font-size: 12px;
                color: #64748b;
                line-height: 1.4;
            }
            QLabel.fieldLabel {
                font-size: 13px;
                font-weight: 800;
                color: #0f172a;
            }
            QComboBox {
                background-color: #ffffff;
                color: #0f172a;
                border: 2px solid #0f172a;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QComboBox:hover {
                background-color: #f8fafc;
            }
            QComboBox::drop-down {
                border: none;
            }
            QPushButton.primaryBtn {
                background-color: #b9f227;
                color: #0f172a;
                font-size: 14px;
                font-weight: 900;
                padding: 11px 18px;
                border: 3px solid #101828;
                border-radius: 12px;
                letter-spacing: 0.3px;
            }
            QPushButton.primaryBtn:hover {
                background-color: #a7df18;
            }
            QPushButton.primaryBtn:pressed {
                background-color: #95c916;
            }
            QPushButton.navBackBtn {
                background-color: #ffffff;
                color: #0f172a;
                font-size: 12px;
                font-weight: 800;
                padding: 10px 16px;
                border: 2px solid #0f172a;
                border-radius: 8px;
            }
            QPushButton.navBackBtn:hover {
                background-color: #f1f5f9;
            }
            QPushButton.actionBtn {
                background-color: #dbeafe;
                color: #1e40af;
                font-size: 12px;
                font-weight: 800;
                padding: 9px 14px;
                border: 2px solid #0f172a;
                border-radius: 8px;
            }
            QPushButton.actionBtn:hover {
                background-color: #bfdbfe;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(18)

        # 1. Header
        header_col = QVBoxLayout()
        header_col.setSpacing(3)

        eyebrow = QLabel("QUY TRÌNH · BƯỚC 02")
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
        card.setObjectName("voiceConfigCard")
        card.setStyleSheet("""
            QFrame#voiceConfigCard {
                background-color: #ffffff;
                border: 3px solid #101828;
                border-radius: 16px;
                padding: 16px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(17)

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
        wave_box.setObjectName("waveformPreview")
        wave_box.setStyleSheet("""
            QFrame#waveformPreview {
                background-color: #f8fafc;
                border: 1.5px solid #0f172a;
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)
        wave_layout = QHBoxLayout(wave_box)
        wave_layout.setContentsMargins(6, 4, 6, 4)
        wave_layout.setSpacing(6)
        wave_tag = QLabel("WAVEFORM")
        wave_tag.setStyleSheet("color: #0f172a; font-size: 9px; font-weight: 900; letter-spacing: 1px;")
        wave_layout.addWidget(wave_tag)
        wave_bars = QLabel(" ▂▃▅▆▇▆▅▃▂  ▂▃▅▆▇█▇▆▅▃▂  ▂▃▅▆▇▆▅▃ ")
        wave_bars.setStyleSheet("color: #2563eb; font-size: 12px; font-family: monospace; font-weight: bold; letter-spacing: 1.5px;")
        wave_layout.addWidget(wave_bars, 1)
        card_layout.addWidget(wave_box)

        # Test Listen Button
        self.btn_test_listen = QPushButton("▶ Nghe thử giọng đọc mẫu")
        self.btn_test_listen.setProperty("class", "actionBtn")
        self.btn_test_listen.clicked.connect(self.test_listen_requested.emit)
        self.btn_listen = self.btn_test_listen
        card_layout.addWidget(self.btn_test_listen)

        layout.addWidget(card)
        apply_brutalist_shadow(card, offset=4)

        # Helper hint
        hint_lbl = QLabel("💡 Mặc định tối ưu: Ngọc Huyền · Tốc độ 1.1x khớp tốt nhất với nhịp video ngắn Douyin/TikTok.")
        hint_lbl.setStyleSheet("""
            color: #854d0e;
            background-color: #fff0f5;
            border: 2px solid #101828;
            border-radius: 10px;
            padding: 10px 12px;
            font-size: 12px;
            font-weight: 700;
        """)
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
