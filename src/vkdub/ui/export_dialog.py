from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from vkdub.services.render_service import RenderConfig

if TYPE_CHECKING:
    from vkdub.domain.project import Project
    from vkdub.ui.main_window import MainWindow


class ExportDialog(QDialog):
    """Pre-render checklist and export dialog (Phase 8)."""

    start_render_requested = Signal(RenderConfig)
    cancel_render_requested = Signal()

    def __init__(self, parent: "MainWindow | None" = None) -> None:
        super().__init__(parent)
        self._main_window = parent
        self.setWindowTitle("Kiểm tra & Xuất Video (Final Export)")
        self.setMinimumWidth(560)
        self.rendering: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # 1. Checklist Box
        check_group = QGroupBox("KIỂM TRA TRƯỚC KHI XUẤT")
        check_layout = QVBoxLayout(check_group)
        check_layout.setSpacing(6)

        self.lbl_video = QLabel("• Video: Đang kiểm tra…")
        self.lbl_script = QLabel("• Kịch bản: Đang kiểm tra…")
        self.lbl_voice = QLabel("• Voice: Đang kiểm tra…")
        self.lbl_sub = QLabel("• Subtitle: Sẵn sàng")
        self.lbl_mask = QLabel("• Vùng che: 0 vùng che")
        self.lbl_ffmpeg = QLabel("• FFmpeg: Đang kiểm tra…")

        for lbl in (
            self.lbl_video,
            self.lbl_script,
            self.lbl_voice,
            self.lbl_sub,
            self.lbl_mask,
            self.lbl_ffmpeg,
        ):
            lbl.setStyleSheet("font-size: 12px; font-weight: 500;")
            check_layout.addWidget(lbl)

        layout.addWidget(check_group)

        # 2. Render Options
        opt_group = QGroupBox("Tùy chọn Xuất & Hòa trộn Âm thanh")
        opt_form = QFormLayout(opt_group)
        opt_form.setSpacing(10)

        self.check_burn_sub = QCheckBox("Gắn phụ đề trực tiếp vào video (Hardcode Subtitles)")
        self.check_burn_sub.setChecked(True)
        opt_form.addRow(self.check_burn_sub)

        self.check_apply_masks = QCheckBox("Áp dụng vùng che xóa chữ gốc (Apply Masks)")
        self.check_apply_masks.setChecked(True)
        opt_form.addRow(self.check_apply_masks)

        # Voice volume
        voice_row = QHBoxLayout()
        self.slider_voice_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_voice_vol.setRange(0, 150)
        self.slider_voice_vol.setValue(100)
        self.lbl_voice_vol = QLabel("100%")
        self.slider_voice_vol.valueChanged.connect(lambda v: self.lbl_voice_vol.setText(f"{v}%"))
        voice_row.addWidget(self.slider_voice_vol, 1)
        voice_row.addWidget(self.lbl_voice_vol)
        opt_form.addRow("Âm lượng giọng đọc (TTS):", voice_row)

        # Original audio ducking volume
        orig_row = QHBoxLayout()
        self.slider_orig_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_orig_vol.setRange(0, 100)
        self.slider_orig_vol.setValue(15)
        self.lbl_orig_vol = QLabel("15% (Hạ nhỏ nền)")
        self.slider_orig_vol.valueChanged.connect(self._on_orig_vol_changed)
        orig_row.addWidget(self.slider_orig_vol, 1)
        orig_row.addWidget(self.lbl_orig_vol)
        opt_form.addRow("Âm lượng video gốc (Ducking):", orig_row)

        # Output destination path
        dest_row = QHBoxLayout()
        self.lbl_dest_path = QLabel("Chưa chọn đường dẫn xuất")
        self.lbl_dest_path.setStyleSheet("font-family: Consolas; font-size: 11px; color: #34d399;")
        self.btn_browse = QPushButton("Đổi vị trí lưu…")
        self.btn_browse.clicked.connect(self._browse_output)
        dest_row.addWidget(self.lbl_dest_path, 1)
        dest_row.addWidget(self.btn_browse)
        opt_form.addRow("Tệp xuất ra:", dest_row)

        layout.addWidget(opt_group)

        # 3. Progress Section
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 11px; color: #94a3b8;")
        self.status_label.hide()
        layout.addWidget(self.status_label)

        # 4. Action Buttons
        action_row = QHBoxLayout()
        action_row.addStretch()

        self.btn_cancel = QPushButton("Hủy")
        self.btn_cancel.clicked.connect(self._on_cancel)
        action_row.addWidget(self.btn_cancel)

        self.btn_start = QPushButton("BẮT ĐẦU XUẤT VIDEO")
        self.btn_start.setObjectName("primary")
        self.btn_start.setStyleSheet(
            "font-weight: bold; padding: 8px 16px; background-color: #0284c7; color: white;"
        )
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._on_start)
        action_row.addWidget(self.btn_start)

        layout.addLayout(action_row)
        self.custom_output_path: Path | None = None

    def _on_orig_vol_changed(self, v: int) -> None:
        if v == 0:
            self.lbl_orig_vol.setText("0% (Tắt hoàn toàn tiếng gốc)")
        else:
            self.lbl_orig_vol.setText(f"{v}% (Hạ nhỏ tiếng gốc)")

    def update_checklist(
        self,
        project: "Project | None" = None,
        ffmpeg_available: bool | None = None,
    ) -> None:
        main_win = self._main_window
        proj = project or (main_win.project if main_win else None)
        if not proj:
            self.btn_start.setEnabled(False)
            return

        # Video
        v_ok = bool(proj.video_path and proj.video_path.is_file())
        meta = main_win.preview._last_metadata if main_win else None
        v_info = f"{meta.width}x{meta.height}" if meta else ""
        v_name = proj.video_path.name if proj.video_path else "Chưa có"
        self.lbl_video.setText(f"{'✓' if v_ok else '✗'} Video nguồn: {v_name} {v_info}")
        self.lbl_video.setStyleSheet(f"color: {'#34d399' if v_ok else '#ef4444'};")

        # Script
        s_ok = proj.is_approved
        n_lines = len(proj.script.lines) if proj.script else 0
        s_tag = "(ĐÃ DUYỆT)" if s_ok else "(CHƯA DUYỆT)"
        self.lbl_script.setText(f"{'✓' if s_ok else '✗'} Kịch bản đã duyệt: {n_lines} câu {s_tag}")
        self.lbl_script.setStyleSheet(f"color: {'#34d399' if s_ok else '#ef4444'};")

        # Voice
        voice_ready = proj.voice_ready
        v_count = len(proj.current_voices())
        v_tag = "(ĐẦY ĐỦ)" if voice_ready else "(THIẾU VOICE)"
        self.lbl_voice.setText(
            f"{'✓' if voice_ready else '✗'} Voice đã tạo: {v_count}/{n_lines} câu {v_tag}"
        )
        self.lbl_voice.setStyleSheet(f"color: {'#34d399' if voice_ready else '#ef4444'};")

        # Subtitle
        sub_name = proj.subtitle_style.name
        self.lbl_sub.setText(f"✓ Phụ đề: Style '{sub_name}' hợp lệ")
        self.lbl_sub.setStyleSheet("color: #34d399;")

        # Mask
        m_count = len(proj.masks)
        self.lbl_mask.setText(f"✓ Vùng che: {m_count} vùng che được cấu hình")
        self.lbl_mask.setStyleSheet("color: #34d399;")

        # FFmpeg
        if ffmpeg_available is not None:
            ffmpeg_ok = ffmpeg_available
        else:
            ffmpeg_ok = bool(main_win.tools.paths.get("ffmpeg")) if main_win else False
        ff_tag = "Sẵn sàng" if ffmpeg_ok else "Chưa cài đặt"
        self.lbl_ffmpeg.setText(f"{'✓' if ffmpeg_ok else '✗'} FFmpeg: {ff_tag}")
        self.lbl_ffmpeg.setStyleSheet(f"color: {'#34d399' if ffmpeg_ok else '#ef4444'};")

        # Ready condition
        all_ready = v_ok and s_ok and voice_ready and ffmpeg_ok
        self.btn_start.setEnabled(all_ready)
        if not all_ready:
            self.btn_start.setToolTip("Cần thỏa mãn đầy đủ các mục kiểm tra để xuất video.")
        else:
            self.btn_start.setToolTip("")

        # Default output path
        if not self.custom_output_path and proj.video_path:
            out_dir = proj.output_directory or proj.video_path.parent
            def_name = f"{proj.video_path.stem}_dubbed.mp4"
            self.custom_output_path = out_dir / def_name
        self.lbl_dest_path.setText(str(self.custom_output_path) if self.custom_output_path else "")

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Chọn tệp xuất video MP4",
            str(self.custom_output_path or "output_dubbed.mp4"),
            "Video MP4 (*.mp4)",
        )
        if path:
            self.custom_output_path = Path(path)
            self.lbl_dest_path.setText(str(self.custom_output_path))

    def _on_start(self) -> None:
        if not self.custom_output_path:
            QMessageBox.warning(self, "Xuất Video", "Vui lòng chọn đường dẫn lưu tệp xuất.")
            return

        if self.custom_output_path.is_file():
            ans = QMessageBox.question(
                self,
                "Ghi đè tệp?",
                f"Tệp đã tồn tại:\n{self.custom_output_path}\n\nBạn có chắc chắn muốn ghi đè?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return

        config = RenderConfig(
            output_path=self.custom_output_path,
            burn_subtitles=self.check_burn_sub.isChecked(),
            apply_masks=self.check_apply_masks.isChecked(),
            original_volume=self.slider_orig_vol.value() / 100.0,
            voice_volume=self.slider_voice_vol.value() / 100.0,
        )

        self.rendering = True
        self.btn_start.setEnabled(False)
        self.btn_browse.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.status_label.setText("Đang chuẩn bị luồng âm thanh và bộ lọc render…")
        self.status_label.show()
        self.start_render_requested.emit(config)

    def _on_cancel(self) -> None:
        if self.rendering:
            ans = QMessageBox.question(
                self,
                "Hủy xuất video?",
                "Tiến trình render đang chạy. Bạn có chắc chắn muốn hủy?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ans == QMessageBox.StandardButton.Yes:
                self.cancel_render_requested.emit()
                self.reject()
        else:
            self.reject()

    def set_progress(self, percent: float, message: str) -> None:
        self.progress_bar.setValue(round(percent))
        self.status_label.setText(message)

    def render_finished(self, success: bool, message: str) -> None:
        self.rendering = False
        self.btn_start.setEnabled(True)
        self.btn_browse.setEnabled(True)
        self.status_label.setText(message)
        if success:
            self.progress_bar.setValue(100)
            QMessageBox.information(
                self,
                "Xuất video hoàn tất",
                f"Video thuyết minh đã được tạo thành công:\n{self.custom_output_path}",
                QMessageBox.StandardButton.Ok,
            )
            self.accept()
        else:
            QMessageBox.critical(self, "Lỗi Render", message)
