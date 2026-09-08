"""VK Dub Studio — Step 01: Source Panel.

Right contextual panel for selecting video source:
- Douyin / Video URL input
- Local video file picker
- Selected video metadata card
- Continue action
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vkdub.media.ffprobe import VideoMetadata


class Step1SourcePanel(QFrame):
    """Contextual panel for Step 1: Video Source."""

    choose_video_requested = Signal()
    download_url_requested = Signal(str)
    continue_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("step1Panel")
        self.setStyleSheet("""
            QFrame#step1Panel {
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
            QPushButton.primaryBtn:pressed {
                background: #0284c7;
            }
            QPushButton.primaryBtn:disabled {
                background: #0a101d;
                color: #475569;
                border: 1px solid #141f32;
            }
            QPushButton.secondaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #131d2e, stop:1 #0e1626);
                color: #cbd5e1;
                font-size: 12px;
                font-weight: 600;
                padding: 8px 15px;
                border: 1px solid #1e2f4a;
                border-radius: 7px;
            }
            QPushButton.secondaryBtn:hover {
                background: #18263d;
                color: #38bdf8;
                border-color: #0284c7;
            }
            QLineEdit.inputField {
                background-color: #070c16;
                color: #f8fafc;
                border: 1px solid #1a283e;
                border-radius: 7px;
                padding: 8px 12px;
                font-size: 12px;
            }
            QLineEdit.inputField:focus {
                border-color: #06b6d4;
                background-color: #0a1220;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 1. Header
        header_col = QVBoxLayout()
        header_col.setSpacing(3)

        eyebrow = QLabel("PIPELINE · STEP 01")
        eyebrow.setProperty("class", "eyebrowTag")
        header_col.addWidget(eyebrow)

        title = QLabel("01 NGUỒN VIDEO (SOURCE)")
        title.setProperty("class", "panelHeader")
        header_col.addWidget(title)

        subtitle = QLabel("Chọn tệp video MP4 từ máy tính hoặc kéo thả trực tiếp để bắt đầu")
        subtitle.setProperty("class", "panelSub")
        header_col.addWidget(subtitle)
        layout.addLayout(header_col)

        # Retain hidden URL input & download button for backwards/test compatibility
        self.url_input = QLineEdit()
        self.url_input.hide()
        self.btn_download = QPushButton("📥 Tải video")
        self.btn_download.hide()
        self.btn_download.clicked.connect(self._on_download_clicked)

        # 2. Local File Chooser & Drop Zone Frame (Hero)
        drop_frame = QFrame()
        drop_frame.setObjectName("dropZone")
        drop_frame.setStyleSheet("""
            QFrame#dropZone {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0d172a, stop:1 #070b14);
                border: 2px dashed #203454;
                border-radius: 14px;
                padding: 24px 16px;
            }
            QFrame#dropZone:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #101e38, stop:1 #0a1120);
                border-color: #06b6d4;
            }
        """)
        drop_layout = QVBoxLayout(drop_frame)
        drop_layout.setContentsMargins(12, 16, 12, 16)
        drop_layout.setSpacing(10)

        drop_icon = QLabel("📥")
        drop_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_icon.setStyleSheet("font-size: 28px; background: transparent;")
        drop_layout.addWidget(drop_icon)

        drop_hint = QLabel("Kéo thả file MP4 vào đây\nhoặc bấm nút bên dưới để chọn từ ổ cứng")
        drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_hint.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: 600; line-height: 1.4; background: transparent;")
        drop_layout.addWidget(drop_hint)

        self.btn_choose_file = QPushButton("📂 CHỌN VIDEO TỪ MÁY (MP4)")
        self.btn_choose_file.setProperty("class", "primaryBtn")
        self.btn_choose_file.clicked.connect(self.choose_video_requested.emit)
        self.btn_choose_video = self.btn_choose_file
        drop_layout.addWidget(self.btn_choose_file)
        layout.addWidget(drop_frame)

        # 5. Selected Video Metadata Inspector Card
        self.info_card = QFrame()
        self.info_card.setStyleSheet("""
            QFrame {
                background-color: #080d17;
                border: 1px dashed #1a283e;
                border-radius: 10px;
                padding: 12px;
            }
        """)
        info_layout = QVBoxLayout(self.info_card)
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setSpacing(8)

        info_header_row = QHBoxLayout()
        info_header = QLabel("THÔNG TIN VIDEO ĐÃ CHỌN")
        info_header.setStyleSheet("font-size: 10px; font-weight: 800; color: #38bdf8; letter-spacing: 0.8px;")
        info_header_row.addWidget(info_header)

        self.lbl_status_pill = QLabel("CHỜ CHỌN")
        self.lbl_status_pill.setStyleSheet("""
            color: #64748b;
            background-color: #0d1524;
            border: 1px solid #1a283e;
            border-radius: 4px;
            padding: 1px 6px;
            font-size: 9px;
            font-weight: 800;
        """)
        info_header_row.addWidget(self.lbl_status_pill)
        info_header_row.addStretch(1)
        info_layout.addLayout(info_header_row)

        self.lbl_file_name = QLabel("Chưa chọn video MP4")
        self.lbl_file_name.setStyleSheet("font-size: 13px; font-weight: 700; color: #94a3b8;")
        self.lbl_file_name.setWordWrap(True)
        info_layout.addWidget(self.lbl_file_name)

        # Spec chips container
        specs_col = QVBoxLayout()
        specs_col.setSpacing(6)

        self.lbl_resolution_dur = QLabel("—")
        self.lbl_resolution_dur.setStyleSheet("""
            font-size: 11px;
            color: #cbd5e1;
            font-family: 'Consolas', 'Segoe UI', monospace;
            background-color: #070c16;
            border: 1px solid #17243a;
            border-radius: 6px;
            padding: 6px 10px;
        """)
        specs_col.addWidget(self.lbl_resolution_dur)

        self.lbl_fps_audio = QLabel("—")
        self.lbl_fps_audio.setStyleSheet("""
            font-size: 11px;
            color: #cbd5e1;
            background-color: #070c16;
            border: 1px solid #17243a;
            border-radius: 6px;
            padding: 6px 10px;
        """)
        specs_col.addWidget(self.lbl_fps_audio)
        info_layout.addLayout(specs_col)

        self.lbl_full_path = QLabel("")
        self.lbl_full_path.setStyleSheet("""
            font-size: 10px;
            color: #64748b;
            font-family: 'Consolas', monospace;
            background-color: #050810;
            border: 1px solid #131b2c;
            border-radius: 5px;
            padding: 4px 8px;
        """)
        self.lbl_full_path.setWordWrap(True)
        info_layout.addWidget(self.lbl_full_path)

        layout.addWidget(self.info_card)

        layout.addStretch(1)

        # 6. Navigation Footer (Continue)
        self.btn_continue = QPushButton("Tiếp tục: Cấu hình giọng đọc →")
        self.btn_continue.setProperty("class", "primaryBtn")
        self.btn_continue.setEnabled(False)
        self.btn_continue.clicked.connect(self.continue_requested.emit)
        layout.addWidget(self.btn_continue)

    def _on_download_clicked(self) -> None:
        url = self.url_input.text().strip()
        if url:
            self.download_url_requested.emit(url)

    def set_video_info(self, path: Path | None, metadata: VideoMetadata | None = None) -> None:
        if path and path.is_file():
            self.lbl_file_name.setText(path.name)
            self.lbl_file_name.setStyleSheet("font-size: 13px; font-weight: 800; color: #ffffff;")
            self.lbl_full_path.setText(str(path))
            self.lbl_status_pill.setText("● SẴN SÀNG")
            self.lbl_status_pill.setStyleSheet("""
                color: #34d399;
                background-color: #064e3b;
                border: 1px solid #059669;
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 9px;
                font-weight: 800;
            """)
            self.btn_continue.setEnabled(True)
            self.info_card.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0f1c30, stop:1 #0a1220);
                    border: 1px solid #0284c7;
                    border-left: 3.5px solid #06b6d4;
                    border-radius: 10px;
                    padding: 12px;
                }
            """)

            if metadata:
                dur_s = int(metadata.duration)
                m, s = divmod(dur_s, 60)
                self.lbl_resolution_dur.setText(
                    f"📐 {metadata.width}x{metadata.height}   •   ⏱ {m:02d}:{s:02d}"
                )
                fps_text = f"{metadata.fps:.2f} fps" if metadata.fps else "30 fps"
                audio_text = "🔊 Có âm thanh" if metadata.audio_codec else "🔇 Không có audio"
                self.lbl_fps_audio.setText(f"🎞 {fps_text}   •   {audio_text}")
            else:
                self.lbl_resolution_dur.setText("📐 Đang đọc thông số media...")
                self.lbl_fps_audio.setText("")
        else:
            self.lbl_file_name.setText("Chưa chọn video MP4")
            self.lbl_file_name.setStyleSheet("font-size: 13px; font-weight: 700; color: #94a3b8;")
            self.lbl_status_pill.setText("CHỜ CHỌN")
            self.lbl_status_pill.setStyleSheet("""
                color: #64748b;
                background-color: #0d1524;
                border: 1px solid #1a283e;
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 9px;
                font-weight: 800;
            """)
            self.lbl_resolution_dur.setText("Vui lòng tải hoặc chọn tệp video từ máy")
            self.lbl_fps_audio.setText("—")
            self.lbl_full_path.setText("")
            self.btn_continue.setEnabled(False)
            self.info_card.setStyleSheet("""
                QFrame {
                    background-color: #080d17;
                    border: 1px dashed #1a283e;
                    border-radius: 10px;
                    padding: 12px;
                }
            """)
