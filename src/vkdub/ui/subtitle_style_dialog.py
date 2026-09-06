from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from vkdub.domain.subtitle import SubtitleStyle
from vkdub.services.subtitle_service import export_ass, export_srt, load_presets

if TYPE_CHECKING:
    from vkdub.ui.main_window import MainWindow


class SubtitleStyleDialog(QDialog):
    """Subtitle Styling and Preset Dialog (Phase 6).

    Allows real-time customization of subtitle fonts, colors, borders,
    background boxes, margins, and exporting to .srt or .ass.
    """

    style_changed = Signal(SubtitleStyle)

    def __init__(self, parent: "MainWindow | None" = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tùy biến Phụ đề (Subtitle Styles & Presets)")
        self.setMinimumWidth(540)
        self.presets = load_presets()
        self._updating_ui = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Preset Selector
        preset_group = QGroupBox("Mẫu kiểu dáng phụ đề (Preset)")
        preset_layout = QHBoxLayout(preset_group)
        preset_layout.addWidget(QLabel("Chọn kiểu mẫu:"))
        self.preset_combo = QComboBox()
        for name in self.presets:
            self.preset_combo.addItem(name)
        self.preset_combo.currentTextChanged.connect(self._on_preset_selected)
        preset_layout.addWidget(self.preset_combo, 1)
        layout.addWidget(preset_group)

        # Typography Group
        typo_group = QGroupBox("Phông chữ & Định dạng")
        typo_layout = QFormLayout(typo_group)
        typo_layout.setSpacing(10)

        self.font_combo = QFontComboBox()
        self.font_combo.currentFontChanged.connect(self._on_style_input_changed)
        typo_layout.addRow("Phông chữ:", self.font_combo)

        size_row = QHBoxLayout()
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(16, 100)
        self.size_slider.setValue(42)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(16, 100)
        self.size_spin.setValue(42)
        self.size_slider.valueChanged.connect(self.size_spin.setValue)
        self.size_spin.valueChanged.connect(self.size_slider.setValue)
        self.size_spin.valueChanged.connect(self._on_style_input_changed)
        size_row.addWidget(self.size_slider, 1)
        size_row.addWidget(self.size_spin)
        typo_layout.addRow("Cỡ chữ (px):", size_row)

        style_checks = QHBoxLayout()
        self.check_bold = QCheckBox("In đậm (Bold)")
        self.check_italic = QCheckBox("In nghiêng (Italic)")
        self.check_bold.toggled.connect(self._on_style_input_changed)
        self.check_italic.toggled.connect(self._on_style_input_changed)
        style_checks.addWidget(self.check_bold)
        style_checks.addWidget(self.check_italic)
        style_checks.addStretch()
        typo_layout.addRow("Kiểu chữ:", style_checks)

        layout.addWidget(typo_group)

        # Colors & Effects Group
        effects_group = QGroupBox("Màu sắc, Viền & Đổ bóng")
        effects_layout = QFormLayout(effects_group)
        effects_layout.setSpacing(10)

        # Color buttons
        colors_row = QHBoxLayout()
        self.btn_text_color = QPushButton("Màu chữ")
        self.btn_text_color.clicked.connect(self._pick_text_color)
        self.current_text_color = "#FFFFFF"

        self.btn_outline_color = QPushButton("Màu viền")
        self.btn_outline_color.clicked.connect(self._pick_outline_color)
        self.current_outline_color = "#000000"

        self.btn_shadow_color = QPushButton("Màu bóng")
        self.btn_shadow_color.clicked.connect(self._pick_shadow_color)
        self.current_shadow_color = "#000000"

        colors_row.addWidget(self.btn_text_color)
        colors_row.addWidget(self.btn_outline_color)
        colors_row.addWidget(self.btn_shadow_color)
        effects_layout.addRow("Màu sắc:", colors_row)

        # Outline width
        outline_row = QHBoxLayout()
        self.outline_slider = QSlider(Qt.Orientation.Horizontal)
        self.outline_slider.setRange(0, 10)
        self.outline_slider.setValue(3)
        self.outline_label = QLabel("3 px")
        self.outline_slider.valueChanged.connect(lambda v: self.outline_label.setText(f"{v} px"))
        self.outline_slider.valueChanged.connect(self._on_style_input_changed)
        outline_row.addWidget(self.outline_slider, 1)
        outline_row.addWidget(self.outline_label)
        effects_layout.addRow("Độ dày viền:", outline_row)

        # Shadow offset
        shadow_row = QHBoxLayout()
        self.shadow_slider = QSlider(Qt.Orientation.Horizontal)
        self.shadow_slider.setRange(0, 10)
        self.shadow_slider.setValue(2)
        self.shadow_label = QLabel("2 px")
        self.shadow_slider.valueChanged.connect(lambda v: self.shadow_label.setText(f"{v} px"))
        self.shadow_slider.valueChanged.connect(self._on_style_input_changed)
        shadow_row.addWidget(self.shadow_slider, 1)
        shadow_row.addWidget(self.shadow_label)
        effects_layout.addRow("Độ lệch bóng:", shadow_row)

        # Background box
        bg_row = QHBoxLayout()
        self.check_bg_box = QCheckBox("Hộp nền (Background box)")
        self.check_bg_box.toggled.connect(self._on_style_input_changed)
        self.btn_bg_color = QPushButton("Màu nền")
        self.btn_bg_color.clicked.connect(self._pick_bg_color)
        self.current_bg_color = "#000000"
        self.bg_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.bg_opacity_slider.setRange(10, 100)
        self.bg_opacity_slider.setValue(60)
        self.bg_opacity_label = QLabel("60%")
        self.bg_opacity_slider.valueChanged.connect(
            lambda v: self.bg_opacity_label.setText(f"{v}%")
        )
        self.bg_opacity_slider.valueChanged.connect(self._on_style_input_changed)

        bg_row.addWidget(self.check_bg_box)
        bg_row.addWidget(self.btn_bg_color)
        bg_row.addWidget(self.bg_opacity_slider, 1)
        bg_row.addWidget(self.bg_opacity_label)
        effects_layout.addRow("Khung nền:", bg_row)

        layout.addWidget(effects_group)

        # Position & Layout Group
        pos_group = QGroupBox("Vị trí & Lề")
        pos_layout = QFormLayout(pos_group)
        pos_layout.setSpacing(10)

        margin_row = QHBoxLayout()
        self.margin_slider = QSlider(Qt.Orientation.Horizontal)
        self.margin_slider.setRange(10, 300)
        self.margin_slider.setValue(50)
        self.margin_label = QLabel("50 px")
        self.margin_slider.valueChanged.connect(lambda v: self.margin_label.setText(f"{v} px"))
        self.margin_slider.valueChanged.connect(self._on_style_input_changed)
        margin_row.addWidget(self.margin_slider, 1)
        margin_row.addWidget(self.margin_label)
        pos_layout.addRow("Lề đáy (Bottom Margin):", margin_row)

        layout.addWidget(pos_group)

        # Export & Close Actions
        action_bar = QHBoxLayout()
        self.btn_export_srt = QPushButton("📄 Xuất file .SRT")
        self.btn_export_srt.clicked.connect(self._export_srt)
        self.btn_export_ass = QPushButton("🎬 Xuất file .ASS")
        self.btn_export_ass.clicked.connect(self._export_ass)

        action_bar.addWidget(self.btn_export_srt)
        action_bar.addWidget(self.btn_export_ass)
        action_bar.addStretch()

        self.btn_close = QPushButton("Áp dụng & Đóng")
        self.btn_close.setDefault(True)
        self.btn_close.clicked.connect(self.accept)
        action_bar.addWidget(self.btn_close)

        layout.addLayout(action_bar)

        self._update_color_buttons()

    def set_current_style(self, style: SubtitleStyle) -> None:
        """Populate dialog widgets from a SubtitleStyle object."""
        self._updating_ui = True
        try:
            if style.name in self.presets:
                self.preset_combo.setCurrentText(style.name)
            else:
                self.preset_combo.setCurrentIndex(-1)

            self.font_combo.setCurrentFont(style.font_family)
            self.size_slider.setValue(style.font_size)
            self.check_bold.setChecked(style.bold)
            self.check_italic.setChecked(style.italic)
            self.current_text_color = style.text_color
            self.current_outline_color = style.outline_color
            self.outline_slider.setValue(int(style.outline_width))
            self.current_shadow_color = style.shadow_color
            self.shadow_slider.setValue(int(style.shadow_offset))
            self.check_bg_box.setChecked(style.background_box)
            self.current_bg_color = style.background_color
            self.bg_opacity_slider.setValue(int(style.background_opacity * 100))
            self.margin_slider.setValue(style.margin_bottom)
            self._update_color_buttons()
        finally:
            self._updating_ui = False

    def get_style(self) -> SubtitleStyle:
        """Construct SubtitleStyle from current dialog input values."""
        preset_name = self.preset_combo.currentText() or "Custom"
        return SubtitleStyle(
            name=preset_name,
            font_family=self.font_combo.currentFont().family(),
            font_size=self.size_slider.value(),
            bold=self.check_bold.isChecked(),
            italic=self.check_italic.isChecked(),
            text_color=self.current_text_color,
            outline_color=self.current_outline_color,
            outline_width=float(self.outline_slider.value()),
            shadow_offset=float(self.shadow_slider.value()),
            shadow_color=self.current_shadow_color,
            background_box=self.check_bg_box.isChecked(),
            background_color=self.current_bg_color,
            background_opacity=self.bg_opacity_slider.value() / 100.0,
            alignment=2,
            margin_bottom=self.margin_slider.value(),
        )

    def _update_color_buttons(self) -> None:
        self.btn_text_color.setStyleSheet(
            f"background-color: {self.current_text_color}; border-radius: 4px; padding: 4px 8px;"
        )
        self.btn_outline_color.setStyleSheet(
            f"background-color: {self.current_outline_color}; border-radius: 4px; padding: 4px 8px;"
        )
        self.btn_shadow_color.setStyleSheet(
            f"background-color: {self.current_shadow_color}; border-radius: 4px; padding: 4px 8px;"
        )
        self.btn_bg_color.setStyleSheet(
            f"background-color: {self.current_bg_color}; border-radius: 4px; padding: 4px 8px;"
        )

    def _pick_text_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.current_text_color), self, "Chọn màu chữ")
        if color.isValid():
            self.current_text_color = color.name().upper()
            self._update_color_buttons()
            self._on_style_input_changed()

    def _pick_outline_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.current_outline_color), self, "Chọn màu viền")
        if color.isValid():
            self.current_outline_color = color.name().upper()
            self._update_color_buttons()
            self._on_style_input_changed()

    def _pick_shadow_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.current_shadow_color), self, "Chọn màu bóng")
        if color.isValid():
            self.current_shadow_color = color.name().upper()
            self._update_color_buttons()
            self._on_style_input_changed()

    def _pick_bg_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.current_bg_color), self, "Chọn màu hộp nền")
        if color.isValid():
            self.current_bg_color = color.name().upper()
            self._update_color_buttons()
            self._on_style_input_changed()

    def _on_preset_selected(self, preset_name: str) -> None:
        if self._updating_ui:
            return
        preset = self.presets.get(preset_name)
        if preset:
            self.set_current_style(preset)
            self.style_changed.emit(self.get_style())

    def _on_style_input_changed(self) -> None:
        if self._updating_ui:
            return
        style = self.get_style()
        self.style_changed.emit(style)

    def _export_srt(self) -> None:
        main_window = self.parent()
        project = getattr(main_window, "project", None)
        if not project or not project.script:
            QMessageBox.warning(self, "Xuất SRT", "Chưa có kịch bản để xuất file SRT.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu file phụ đề SRT", "subtitles.srt", "SubRip Subtitle (*.srt)"
        )
        if path:
            try:
                export_srt(project, Path(path))
                QMessageBox.information(self, "Xuất SRT", f"Đã xuất phụ đề SRT thành công:\n{path}")
            except Exception as exc:
                QMessageBox.critical(self, "Lỗi xuất SRT", str(exc))

    def _export_ass(self) -> None:
        main_window = self.parent()
        project = getattr(main_window, "project", None)
        if not project or not project.script:
            QMessageBox.warning(self, "Xuất ASS", "Chưa có kịch bản để xuất file ASS.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu file phụ đề ASS", "subtitles.ass", "Advanced SubStation Alpha (*.ass)"
        )
        if path:
            try:
                style = self.get_style()
                export_ass(project, Path(path), style)
                QMessageBox.information(self, "Xuất ASS", f"Đã xuất phụ đề ASS thành công:\n{path}")
            except Exception as exc:
                QMessageBox.critical(self, "Lỗi xuất ASS", str(exc))
