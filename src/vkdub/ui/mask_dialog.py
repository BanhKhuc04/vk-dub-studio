from typing import TYPE_CHECKING
from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vkdub.domain.mask import MaskItem

if TYPE_CHECKING:
    from vkdub.ui.main_window import MainWindow


class MaskEditorDialog(QDialog):
    """Mask Editor Dialog (Phase 7).

    Allows users to manage rectangular blur or solid-fill masks,
    set normalized bounding coordinates, and set start/end timestamps.
    """

    masks_updated = Signal(list)  # list[MaskItem]

    def __init__(self, parent: "MainWindow | None" = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Quản lý Vùng che Video (Mask Editor)")
        self.setMinimumSize(780, 520)
        self._updating_ui = False
        self.masks: list[MaskItem] = []
        self.current_mask_id: str | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: List of masks
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        left_header = QHBoxLayout()
        left_header.addWidget(QLabel("<b>Danh sách vùng che:</b>"))
        left_header.addStretch()
        left_layout.addLayout(left_header)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Tên", "Loại", "Thời gian"])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        left_layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("+ Thêm vùng che")
        self.btn_add.clicked.connect(self._add_mask)
        self.btn_duplicate = QPushButton("Nhân bản")
        self.btn_duplicate.clicked.connect(self._duplicate_mask)
        self.btn_delete = QPushButton("Xóa")
        self.btn_delete.clicked.connect(self._delete_mask)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_duplicate)
        btn_row.addWidget(self.btn_delete)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left_widget)

        # Right: Detail Config
        self.right_widget = QWidget()
        right_layout = QVBoxLayout(self.right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        # Basic properties
        basic_group = QGroupBox("Thông số vùng che")
        basic_form = QFormLayout(basic_group)
        basic_form.setSpacing(10)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Xóa chữ — hòa nền (Khuyên dùng)", "erase")
        self.type_combo.addItem("Làm mờ mạnh", "blur")
        self.type_combo.addItem("Màu đặc", "solid")
        self.type_combo.addItem("🔴 Vùng lấy Sub (Viền đỏ, không mờ)", "sub_region")
        self.type_combo.currentIndexChanged.connect(self._on_input_changed)
        basic_form.addRow("Kiểu che:", self.type_combo)

        # Coordinates
        coord_group = QGroupBox("Tọa độ & Kích thước (% khung hình)")
        coord_layout = QFormLayout(coord_group)
        coord_layout.setSpacing(8)

        # X
        x_row = QHBoxLayout()
        self.spin_x = QDoubleSpinBox()
        self.spin_x.setRange(0.0, 100.0)
        self.spin_x.setSuffix(" %")
        self.slider_x = QSlider(Qt.Orientation.Horizontal)
        self.slider_x.setRange(0, 1000)
        self.slider_x.valueChanged.connect(lambda v: self.spin_x.setValue(v / 10.0))
        self.spin_x.valueChanged.connect(lambda v: self.slider_x.setValue(int(v * 10)))
        self.spin_x.valueChanged.connect(self._on_input_changed)
        x_row.addWidget(self.slider_x, 1)
        x_row.addWidget(self.spin_x)
        coord_layout.addRow("Vị trí X (Trái):", x_row)

        # Y
        y_row = QHBoxLayout()
        self.spin_y = QDoubleSpinBox()
        self.spin_y.setRange(0.0, 100.0)
        self.spin_y.setSuffix(" %")
        self.slider_y = QSlider(Qt.Orientation.Horizontal)
        self.slider_y.setRange(0, 1000)
        self.slider_y.valueChanged.connect(lambda v: self.spin_y.setValue(v / 10.0))
        self.spin_y.valueChanged.connect(lambda v: self.slider_y.setValue(int(v * 10)))
        self.spin_y.valueChanged.connect(self._on_input_changed)
        y_row.addWidget(self.slider_y, 1)
        y_row.addWidget(self.spin_y)
        coord_layout.addRow("Vị trí Y (Trên):", y_row)

        # Width
        w_row = QHBoxLayout()
        self.spin_w = QDoubleSpinBox()
        self.spin_w.setRange(1.0, 100.0)
        self.spin_w.setSuffix(" %")
        self.slider_w = QSlider(Qt.Orientation.Horizontal)
        self.slider_w.setRange(10, 1000)
        self.slider_w.valueChanged.connect(lambda v: self.spin_w.setValue(v / 10.0))
        self.spin_w.valueChanged.connect(lambda v: self.slider_w.setValue(int(v * 10)))
        self.spin_w.valueChanged.connect(self._on_input_changed)
        w_row.addWidget(self.slider_w, 1)
        w_row.addWidget(self.spin_w)
        coord_layout.addRow("Chiều rộng:", w_row)

        # Height
        h_row = QHBoxLayout()
        self.spin_h = QDoubleSpinBox()
        self.spin_h.setRange(1.0, 100.0)
        self.spin_h.setSuffix(" %")
        self.slider_h = QSlider(Qt.Orientation.Horizontal)
        self.slider_h.setRange(10, 1000)
        self.slider_h.valueChanged.connect(lambda v: self.spin_h.setValue(v / 10.0))
        self.spin_h.valueChanged.connect(lambda v: self.slider_h.setValue(int(v * 10)))
        self.spin_h.valueChanged.connect(self._on_input_changed)
        h_row.addWidget(self.slider_h, 1)
        h_row.addWidget(self.spin_h)
        coord_layout.addRow("Chiều cao:", h_row)

        right_layout.addWidget(basic_group)
        right_layout.addWidget(coord_group)

        # Appearance Group
        appear_group = QGroupBox("Màu sắc & Hiệu ứng")
        appear_form = QFormLayout(appear_group)
        appear_form.setSpacing(8)

        color_row = QHBoxLayout()
        self.btn_color = QPushButton("Chọn màu")
        self.btn_color.clicked.connect(self._pick_color)
        self.current_color = "#000000"
        self._update_color_button_style(self.current_color)
        color_row.addWidget(self.btn_color)
        appear_form.addRow("Màu nền đặc:", color_row)

        # Opacity
        op_row = QHBoxLayout()
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(10, 100)
        self.slider_opacity.setValue(100)
        self.label_opacity = QLabel("100%")
        self.slider_opacity.valueChanged.connect(lambda v: self.label_opacity.setText(f"{v}%"))
        self.slider_opacity.valueChanged.connect(self._on_input_changed)
        op_row.addWidget(self.slider_opacity, 1)
        op_row.addWidget(self.label_opacity)
        appear_form.addRow("Độ mờ đục:", op_row)

        # Blur strength
        blur_row = QHBoxLayout()
        self.slider_blur = QSlider(Qt.Orientation.Horizontal)
        self.slider_blur.setRange(1, 40)
        self.slider_blur.setValue(15)
        self.label_blur = QLabel("15")
        self.slider_blur.valueChanged.connect(lambda v: self.label_blur.setText(str(v)))
        self.slider_blur.valueChanged.connect(self._on_input_changed)
        blur_row.addWidget(self.slider_blur, 1)
        blur_row.addWidget(self.label_blur)
        appear_form.addRow("Độ mờ (Blur):", blur_row)

        right_layout.addWidget(appear_group)

        # Time range group
        time_group = QGroupBox("Thời gian áp dụng")
        time_form = QFormLayout(time_group)
        time_form.setSpacing(8)

        start_row = QHBoxLayout()
        self.spin_start = QSpinBox()
        self.spin_start.setRange(0, 36000000)
        self.spin_start.setSuffix(" ms")
        self.spin_start.valueChanged.connect(self._on_input_changed)
        self.btn_get_start = QPushButton("Lấy từ video")
        self.btn_get_start.clicked.connect(self._set_start_from_video)
        start_row.addWidget(self.spin_start, 1)
        start_row.addWidget(self.btn_get_start)
        time_form.addRow("Bắt đầu:", start_row)

        end_row = QHBoxLayout()
        self.spin_end = QSpinBox()
        self.spin_end.setRange(0, 36000000)
        self.spin_end.setSuffix(" ms (0 = hết video)")
        self.spin_end.valueChanged.connect(self._on_input_changed)
        self.btn_get_end = QPushButton("Lấy từ video")
        self.btn_get_end.clicked.connect(self._set_end_from_video)
        end_row.addWidget(self.spin_end, 1)
        end_row.addWidget(self.btn_get_end)
        time_form.addRow("Kết thúc:", end_row)

        right_layout.addWidget(time_group)
        right_layout.addStretch()

        # Bottom actions
        action_bar = QHBoxLayout()
        action_bar.addStretch()
        self.btn_close = QPushButton("Xong & Đóng")
        self.btn_close.setDefault(True)
        self.btn_close.clicked.connect(self.accept)
        action_bar.addWidget(self.btn_close)
        right_layout.addLayout(action_bar)

        splitter.addWidget(self.right_widget)
        layout.addWidget(splitter)

    def _update_color_button_style(self, hex_color: str) -> None:
        self.btn_color.setStyleSheet(
            f"background-color: {hex_color}; color: #FFF; padding: 4px 10px;"
        )

    def load_masks(self, masks: list[MaskItem]) -> None:
        self._updating_ui = True
        try:
            self.masks = [
                MaskItem.from_dict(m.to_dict())
                if isinstance(m, MaskItem)
                else MaskItem.from_dict(m)
                for m in masks
            ]
            self._rebuild_table()
            if self.masks:
                self.table.selectRow(0)
            else:
                self.current_mask_id = None
                self.right_widget.setEnabled(False)
        finally:
            self._updating_ui = False

    def _rebuild_table(self) -> None:
        self.table.setRowCount(len(self.masks))
        for row, mask in enumerate(self.masks):
            item_name = QTableWidgetItem(mask.name)
            type_labels = {"erase": "Xóa chữ", "blur": "Làm mờ", "solid": "Màu đặc", "sub_region": "🔴 Lấy Sub"}
            item_type = QTableWidgetItem(type_labels.get(mask.mask_type, "Làm mờ"))
            if mask.start_ms == 0 and mask.end_ms == 0:
                time_str = "Toàn bộ video"
            else:
                end_s = f"{mask.end_ms / 1000:.1f}s" if mask.end_ms > 0 else "Hết"
                time_str = f"{mask.start_ms / 1000:.1f}s - {end_s}"
            item_time = QTableWidgetItem(time_str)
            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_type)
            self.table.setItem(row, 2, item_time)

    def _on_table_selection_changed(self) -> None:
        selected = self.table.selectedIndexes()
        if not selected:
            self.current_mask_id = None
            self.right_widget.setEnabled(False)
            return

        row = selected[0].row()
        if 0 <= row < len(self.masks):
            self.current_mask_id = self.masks[row].id
            self.right_widget.setEnabled(True)
            self._populate_editor(self.masks[row])
            self._notify_update()

    def _populate_editor(self, mask: MaskItem) -> None:
        self._updating_ui = True
        try:
            index = self.type_combo.findData(mask.mask_type)
            self.type_combo.setCurrentIndex(max(0, index))
            self.spin_x.setValue(mask.x * 100.0)
            self.spin_y.setValue(mask.y * 100.0)
            self.spin_w.setValue(mask.width * 100.0)
            self.spin_h.setValue(mask.height * 100.0)
            self.current_color = mask.color
            self._update_color_button_style(mask.color)
            self.slider_opacity.setValue(int(mask.opacity * 100))
            self.slider_blur.setValue(mask.blur_strength)
            self.spin_start.setValue(mask.start_ms)
            self.spin_end.setValue(mask.end_ms)
        finally:
            self._updating_ui = False

    def _add_mask(self) -> None:
        new_mask = MaskItem(
            name=f"Xóa chữ {len(self.masks) + 1}",
            mask_type="erase",
            x=0.1,
            y=0.8,
            width=0.8,
            height=0.15,
        )
        self.masks.append(new_mask)
        self._rebuild_table()
        self.table.selectRow(len(self.masks) - 1)
        self._notify_update()

    def _duplicate_mask(self) -> None:
        if not self.current_mask_id:
            return
        orig = next((m for m in self.masks if m.id == self.current_mask_id), None)
        if not orig:
            return
        copied = MaskItem.from_dict(orig.to_dict())
        copied.id = str(uuid4())
        copied.name = f"{orig.name} (Bản sao)"
        self.masks.append(copied)
        self._rebuild_table()
        self.table.selectRow(len(self.masks) - 1)
        self._notify_update()

    def _delete_mask(self) -> None:
        if not self.current_mask_id:
            return
        self.masks = [m for m in self.masks if m.id != self.current_mask_id]
        self._rebuild_table()
        if self.masks:
            self.table.selectRow(min(len(self.masks) - 1, 0))
        else:
            self.current_mask_id = None
            self.right_widget.setEnabled(False)
        self._notify_update()

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.current_color), self, "Chọn màu vùng che")
        if color.isValid():
            self.current_color = color.name().upper()
            self._update_color_button_style(self.current_color)
            self._on_input_changed()

    def _set_start_from_video(self) -> None:
        main_win = self.parent()
        preview = getattr(main_win, "preview", None)
        if preview and getattr(preview, "player", None):
            pos = preview.player.position()
            self.spin_start.setValue(pos)

    def _set_end_from_video(self) -> None:
        main_win = self.parent()
        preview = getattr(main_win, "preview", None)
        if preview and getattr(preview, "player", None):
            pos = preview.player.position()
            self.spin_end.setValue(pos)

    def _on_input_changed(self) -> None:
        if self._updating_ui or not self.current_mask_id:
            return
        mask = next((m for m in self.masks if m.id == self.current_mask_id), None)
        if not mask:
            return

        mask.mask_type = self.type_combo.currentData() or "erase"
        mask.x = self.spin_x.value() / 100.0
        mask.y = self.spin_y.value() / 100.0
        mask.width = self.spin_w.value() / 100.0
        mask.height = self.spin_h.value() / 100.0
        mask.color = self.current_color
        mask.opacity = self.slider_opacity.value() / 100.0
        mask.blur_strength = self.slider_blur.value()
        mask.start_ms = self.spin_start.value()
        mask.end_ms = self.spin_end.value()

        # Update row title/time in table without changing selection
        row = next((i for i, m in enumerate(self.masks) if m.id == mask.id), None)
        if row is not None:
            type_label = {"erase": "Xóa chữ", "blur": "Làm mờ", "solid": "Màu đặc"}.get(
                mask.mask_type, "Làm mờ"
            )
            self.table.setItem(row, 1, QTableWidgetItem(type_label))
            if mask.start_ms == 0 and mask.end_ms == 0:
                time_str = "Toàn bộ video"
            else:
                end_s = f"{mask.end_ms / 1000:.1f}s" if mask.end_ms > 0 else "Hết"
                time_str = f"{mask.start_ms / 1000:.1f}s - {end_s}"
            self.table.setItem(row, 2, QTableWidgetItem(time_str))

        self._notify_update()

    def update_rect_from_canvas(self, mask_id: str, x: float, y: float, w: float, h: float) -> None:
        """Called when user drags or resizes the mask directly on VideoCanvas."""
        mask = next((m for m in self.masks if m.id == mask_id), None)
        if mask and mask.id == self.current_mask_id:
            self._updating_ui = True
            try:
                self.spin_x.setValue(x * 100.0)
                self.spin_y.setValue(y * 100.0)
                self.spin_w.setValue(w * 100.0)
                self.spin_h.setValue(h * 100.0)
            finally:
                self._updating_ui = False

    def _notify_update(self) -> None:
        self.masks_updated.emit(self.masks)
