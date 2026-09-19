"""KAPPAK Studio — ✂️ Auto Video Desktop View (PySide6)."""

from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from kappak.modules.auto_video.renderer import AutoVideoRenderer
from kappak.modules.auto_video.service import AutoVideoService


class RenderWorkerSignals(QObject):
    progress = Signal(float, str)
    finished = Signal(str)
    error = Signal(str)


class AutoVideoView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = AutoVideoService()
        self.current_output_file: str | None = None
        self.signals = RenderWorkerSignals()
        self.signals.progress.connect(self._on_progress)
        self.signals.finished.connect(self._on_finished)
        self.signals.error.connect(self._on_error)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        # Header
        header = QVBoxLayout()
        header.setSpacing(4)
        t = QLabel("✂️ Auto Video Generator (9:16)")
        t.setProperty("class", "moduleTitle")
        st = QLabel(
            "Tự động cắt ghép, căn chỉnh khung hình dọc Shorts/Reels/TikTok, lồng tiếng AI và phụ đề"
        )
        st.setProperty("class", "moduleSubtitle")
        header.addWidget(t)
        header.addWidget(st)
        layout.addLayout(header)

        # Main Card Container
        card = QFrame()
        card.setProperty("class", "glassCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(14)

        # Form: Project Name
        name_row = QHBoxLayout()
        name_lbl = QLabel("Tên video:")
        name_lbl.setFixedWidth(110)
        self.name_input = QLineEdit("Short Video Mới")
        name_row.addWidget(name_lbl)
        name_row.addWidget(self.name_input)
        card_layout.addLayout(name_row)

        # Form: Template & Voice Selection
        opt_row = QHBoxLayout()

        tmpl_lbl = QLabel("Bố cục 9:16:")
        tmpl_lbl.setFixedWidth(110)
        self.tmpl_combo = QComboBox()
        self.tmpl_combo.addItem("Cinematic Nền Mờ (blur_bg)", "blur_bg")
        self.tmpl_combo.addItem("Màn Hình Kép (split_screen)", "split_screen")
        self.tmpl_combo.addItem("Hook & Headline (caption_header)", "caption_header")
        opt_row.addWidget(tmpl_lbl)
        opt_row.addWidget(self.tmpl_combo, 1)

        voice_lbl = QLabel("Giọng đọc AI:")
        voice_lbl.setFixedWidth(90)
        self.voice_combo = QComboBox()
        self.voice_combo.addItem("Hoài My (Nữ - Edge TTS)", "vi-VN-HoaiMyNeural")
        self.voice_combo.addItem("Nam Minh (Nam - Edge TTS)", "vi-VN-NamMinhNeural")
        opt_row.addWidget(voice_lbl)
        opt_row.addWidget(self.voice_combo, 1)

        card_layout.addLayout(opt_row)

        # Form: Script Text
        script_lbl = QLabel("Kịch bản văn bản (Mỗi câu thoại sẽ tự động phân thành 1 cảnh 9:16):")
        card_layout.addWidget(script_lbl)

        self.script_edit = QTextEdit()
        self.script_edit.setPlaceholderText("Nhập nội dung kịch bản tại đây...")
        self.script_edit.setText(
            "Bạn muốn video triệu view? Đừng bỏ qua mẹo này.\n"
            "Giữ chân người xem trong 3 giây đầu tiên bằng hình ảnh bất ngờ.\n"
            "Áp dụng ngay hôm nay để thấy sự khác biệt!"
        )
        self.script_edit.setFixedHeight(120)
        card_layout.addWidget(self.script_edit)

        # Progress Bar & Status
        self.status_lbl = QLabel("Sẵn sàng tạo video ngắn.")
        self.status_lbl.setStyleSheet("color: #64748B; font-size: 13px;")
        card_layout.addWidget(self.status_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(12)
        card_layout.addWidget(self.progress_bar)

        # Action Buttons
        btn_row = QHBoxLayout()
        self.create_btn = QPushButton("🚀 Bắt đầu Tạo Video 9:16")
        self.create_btn.setFixedHeight(38)
        self.create_btn.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5CF6, stop:1 #6D28D9); "
            "color: white; font-weight: bold; border-radius: 8px; padding: 0 20px;"
        )
        self.create_btn.clicked.connect(self._on_start_create)

        self.open_btn = QPushButton("📂 Mở Thư Mục Kết Quả")
        self.open_btn.setFixedHeight(38)
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self._on_open_folder)

        btn_row.addWidget(self.create_btn)
        btn_row.addWidget(self.open_btn)
        btn_row.addStretch()

        card_layout.addLayout(btn_row)
        card_layout.addStretch()

        layout.addWidget(card, 1)

    def _on_start_create(self) -> None:
        script = self.script_edit.toPlainText().strip()
        if not script:
            self.status_lbl.setText("⚠️ Vui lòng nhập nội dung kịch bản.")
            return

        self.create_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        self.progress_bar.setValue(5)
        self.status_lbl.setText("Đang khởi tạo dự án...")

        name = self.name_input.text().strip() or "Video Ngắn Mới"
        template_id = self.tmpl_combo.currentData()
        voice_id = self.voice_combo.currentData()

        def worker():
            try:
                # Create project
                proj = self.service.create_project(
                    name=name,
                    template_id=template_id,
                    voice_id=voice_id,
                    script_text=script,
                )

                def on_progress(pct: float, msg: str):
                    self.signals.progress.emit(pct, msg)

                on_progress(15.0, "Đang sinh giọng đọc AI...")
                self.service.generate_scene_voiceovers(proj, on_progress)

                on_progress(45.0, "Đang render khung hình 9:16 và phụ đề...")
                renderer = AutoVideoRenderer()
                out_path = renderer.render_project(proj, on_progress)

                self.signals.finished.emit(str(out_path))
            except Exception as exc:
                self.signals.error.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_progress(self, pct: float, msg: str) -> None:
        self.progress_bar.setValue(int(pct))
        self.status_lbl.setText(msg)

    def _on_finished(self, out_file: str) -> None:
        self.current_output_file = out_file
        self.progress_bar.setValue(100)
        self.status_lbl.setText(f"🎉 Hoàn thành! Tệp: {Path(out_file).name}")
        self.create_btn.setEnabled(True)
        self.open_btn.setEnabled(True)

    def _on_error(self, err: str) -> None:
        self.status_lbl.setText(f"❌ Lỗi: {err}")
        self.create_btn.setEnabled(True)

    def _on_open_folder(self) -> None:
        if self.current_output_file and Path(self.current_output_file).is_file():
            folder = Path(self.current_output_file).parent
            if os.name == "nt":
                subprocess.run(["explorer", str(folder)])
            else:
                subprocess.run(["xdg-open", str(folder)])
