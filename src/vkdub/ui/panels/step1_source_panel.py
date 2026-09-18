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
from vkdub.ui.theme import apply_brutalist_shadow


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
                color: #101828;
                letter-spacing: 0.3px;
            }
            QLabel.panelSub {
                font-size: 12px;
                color: #64748b;
                line-height: 1.4;
            }
            QPushButton.primaryBtn {
                background-color: #b9f227;
                color: #101828;
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
            QPushButton.primaryBtn:disabled {
                background-color: #f1f5f9;
                color: #94a3b8;
                border: 2px solid #cbd5e1;
            }
            QPushButton.secondaryBtn {
                background-color: #ffffff;
                color: #0f172a;
                font-size: 12px;
                font-weight: 800;
                padding: 8px 15px;
                border: 2px solid #0f172a;
                border-radius: 8px;
            }
            QPushButton.secondaryBtn:hover {
                background-color: #f8fafc;
            }
            QLineEdit.inputField {
                background-color: #ffffff;
                color: #0f172a;
                border: 2px solid #0f172a;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QLineEdit.inputField:focus {
                border-color: #2563eb;
                background-color: #f8fafc;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(18)

        # 1. Header
        header_col = QVBoxLayout()
        header_col.setSpacing(3)

        eyebrow = QLabel("QUY TRÌNH · BƯỚC 01")
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
                background-color: #eef4ff;
                border: 3px dashed #101828;
                border-radius: 18px;
                padding: 28px 18px;
            }
            QFrame#dropZone:hover {
                background-color: #f6ffd9;
                border-color: #101828;
            }
        """)
        drop_layout = QVBoxLayout(drop_frame)
        drop_layout.setContentsMargins(16, 22, 16, 22)
        drop_layout.setSpacing(13)

        drop_icon = QLabel("📁")
        drop_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_icon.setStyleSheet("font-size: 42px; background: transparent;")
        drop_layout.addWidget(drop_icon)

        drop_hint = QLabel("Kéo thả file MP4 vào đây\nhoặc bấm nút bên dưới để chọn từ ổ cứng")
        drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_hint.setStyleSheet("font-size: 13px; color: #344054; font-weight: 700; line-height: 1.4; background: transparent;")
        drop_layout.addWidget(drop_hint)

        self.btn_choose_file = QPushButton("📂 CHỌN VIDEO TỪ MÁY")
        self.btn_choose_file.setProperty("class", "primaryBtn")
        self.btn_choose_file.clicked.connect(self.choose_video_requested.emit)
        self.btn_choose_video = self.btn_choose_file
        drop_layout.addWidget(self.btn_choose_file)
        layout.addWidget(drop_frame)
        apply_brutalist_shadow(drop_frame, offset=4)

        # 5. Selected Video Metadata Inspector Card
        self.info_card = QFrame()
        self.info_card.setObjectName("sourceInfoCard")
        self.info_card.setStyleSheet("""
            QFrame#sourceInfoCard {
                background-color: #ffffff;
                border: 3px solid #101828;
                border-radius: 16px;
                padding: 14px;
            }
        """)
        info_layout = QVBoxLayout(self.info_card)
        info_layout.setContentsMargins(14, 14, 14, 14)
        info_layout.setSpacing(10)

        info_header_row = QHBoxLayout()
        info_header = QLabel("THÔNG TIN VIDEO ĐÃ CHỌN")
        info_header.setStyleSheet("font-size: 11px; font-weight: 900; color: #101828; letter-spacing: 0.8px;")
        info_header_row.addWidget(info_header)

        self.lbl_status_pill = QLabel("CHỜ CHỌN")
        self.lbl_status_pill.setStyleSheet("""
            color: #64748b;
            background-color: #f1f5f9;
            border: 1.5px solid #0f172a;
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 9px;
            font-weight: 800;
        """)
        info_header_row.addWidget(self.lbl_status_pill)
        info_header_row.addStretch(1)
        info_layout.addLayout(info_header_row)

        self.lbl_file_name = QLabel("Chưa chọn video")
        self.lbl_file_name.setStyleSheet("font-size: 15px; font-weight: 900; color: #101828;")
        self.lbl_file_name.setWordWrap(True)
        info_layout.addWidget(self.lbl_file_name)

        # Spec chips container
        specs_col = QVBoxLayout()
        specs_col.setSpacing(6)

        self.lbl_resolution_dur = QLabel("—")
        self.lbl_resolution_dur.setStyleSheet("""
            font-size: 11px;
            font-weight: 700;
            color: #0f172a;
            font-family: 'Consolas', 'Segoe UI', monospace;
            background-color: #f8fafc;
            border: 1.5px solid #0f172a;
            border-radius: 6px;
            padding: 6px 10px;
        """)
        specs_col.addWidget(self.lbl_resolution_dur)

        self.lbl_fps_audio = QLabel("—")
        self.lbl_fps_audio.setStyleSheet("""
            font-size: 11px;
            font-weight: 700;
            color: #0f172a;
            background-color: #f8fafc;
            border: 1.5px solid #0f172a;
            border-radius: 6px;
            padding: 6px 10px;
        """)
        specs_col.addWidget(self.lbl_fps_audio)
        info_layout.addLayout(specs_col)

        self.lbl_full_path = QLabel("")
        self.lbl_full_path.setStyleSheet("""
            font-size: 10px;
            color: #475569;
            font-family: 'Consolas', monospace;
            background-color: #f1f5f9;
            border: 1.5px solid #cbd5e1;
            border-radius: 5px;
            padding: 4px 8px;
        """)
        self.lbl_full_path.setWordWrap(True)
        info_layout.addWidget(self.lbl_full_path)

        layout.addWidget(self.info_card)
        apply_brutalist_shadow(self.info_card, offset=4)

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
            self.lbl_file_name.setStyleSheet("font-size: 15px; font-weight: 900; color: #101828;")
            self.lbl_full_path.setText(str(path))
            self.lbl_status_pill.setText("● SẴN SÀNG")
            self.lbl_status_pill.setStyleSheet("""
                color: #15803d;
                background-color: #dcfce7;
                border: 1.5px solid #0f172a;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 9px;
                font-weight: 900;
            """)
            self.btn_continue.setEnabled(True)
            self.info_card.setStyleSheet("""
                QFrame#sourceInfoCard {
                    background-color: #f0fdf4;
                    border: 3px solid #101828;
                    border-radius: 16px;
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
            self.lbl_file_name.setText("Chưa chọn video")
            self.lbl_file_name.setStyleSheet("font-size: 13px; font-weight: 700; color: #64748b;")
            self.lbl_status_pill.setText("CHỜ CHỌN")
            self.lbl_status_pill.setStyleSheet("""
                color: #64748b;
                background-color: #f1f5f9;
                border: 1.5px solid #cbd5e1;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 9px;
                font-weight: 800;
            """)
            self.lbl_resolution_dur.setText("Vui lòng tải hoặc chọn tệp video từ máy")
            self.lbl_fps_audio.setText("—")
            self.lbl_full_path.setText("")
            self.btn_continue.setEnabled(False)
            self.info_card.setStyleSheet("""
                QFrame#sourceInfoCard {
                    background-color: #ffffff;
                    border: 2px solid #0f172a;
                    border-radius: 10px;
                    padding: 12px;
                }
            """)
