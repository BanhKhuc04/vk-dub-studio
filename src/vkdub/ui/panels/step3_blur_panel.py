"""VK Dub Studio — Step 03: Blur Regions Inspector Panel.

Right contextual panel for inspecting and adjusting blur & erase masks:
- Region list
- Add region action
- Inspector fields: X, Y, Width, Height, Blur strength
- Delete region action
- Interactive sync with on-video canvas rectangle
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from vkdub.domain.mask import MaskItem


class Step3BlurPanel(QFrame):
    """Contextual panel for Step 3: Blur Regions Inspector."""

    add_region_requested = Signal()
    add_mask_requested = Signal()
    delete_region_requested = Signal(str)  # mask_id
    region_selected = Signal(str)  # mask_id
    region_changed = Signal(str, float, float, float, float, int)  # mask_id, x, y, w, h, strength
    back_requested = Signal()
    continue_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("step3Panel")
        self.setStyleSheet("""
            QFrame#step3Panel {
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
                font-size: 11px;
                font-weight: 700;
                color: #94a3b8;
            }
            QListWidget {
                background-color: #070c16;
                border: 1px solid #1a283e;
                border-radius: 7px;
                color: #f1f5f9;
                font-size: 12px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px 10px;
                border-radius: 5px;
            }
            QListWidget::item:selected {
                background-color: #10243d;
                color: #38bdf8;
                font-weight: bold;
            }
            QDoubleSpinBox, QSpinBox {
                background-color: #070c16;
                color: #f8fafc;
                border: 1px solid #1a283e;
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 11px;
            }
            QDoubleSpinBox:hover, QSpinBox:hover {
                border-color: #38bdf8;
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
                font-size: 11px;
                font-weight: 700;
                padding: 6px 14px;
                border: 1px solid #1a2c47;
                border-radius: 6px;
            }
            QPushButton.actionBtn:hover {
                background: #152540;
                border-color: #38bdf8;
                color: #ffffff;
            }
            QPushButton.dangerBtn {
                background-color: #450a0a;
                color: #fca5a5;
                font-size: 11px;
                font-weight: 700;
                padding: 6px 12px;
                border: 1px solid #991b1b;
                border-radius: 6px;
            }
            QPushButton.dangerBtn:hover {
                background-color: #7f1d1d;
                color: #ffffff;
            }
        """)

        self._masks: list[MaskItem] = []
        self._current_mask_id: str | None = None
        self._updating_ui = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 1. Header
        header_col = QVBoxLayout()
        header_col.setSpacing(4)
        title = QLabel("03 KHUNG CHE MỜ (BLUR INSPECTOR)")
        title.setProperty("class", "panelHeader")
        header_col.addWidget(title)
        subtitle = QLabel("Tạo và căn chỉnh vùng xóa phụ đề cũ hoặc che watermark trên video")
        subtitle.setProperty("class", "panelSub")
        header_col.addWidget(subtitle)
        layout.addLayout(header_col)

        # 2. Region List & Add Button
        list_header = QHBoxLayout()
        lbl_list = QLabel("DANH SÁCH VÙNG")
        lbl_list.setStyleSheet("font-size: 11px; font-weight: bold; color: #8b949e; letter-spacing: 0.5px;")
        list_header.addWidget(lbl_list, 1)

        self.btn_add_region = QPushButton("➕ Thêm vùng")
        self.btn_add_region.setProperty("class", "actionBtn")
        self.btn_add_region.setToolTip("Thêm vùng làm mờ mới (che logo hoặc chữ)")
        self.btn_add_region.clicked.connect(self.add_region_requested.emit)
        list_header.addWidget(self.btn_add_region)
        layout.addLayout(list_header)

        self.region_list = QListWidget()
        self.region_list.setFixedHeight(100)
        self.region_list.currentRowChanged.connect(self._on_list_selection_changed)
        self.regions_list = self.region_list
        layout.addWidget(self.region_list)

        # 3. Selected Region Inspector Card
        self.inspector_card = QFrame()
        self.inspector_card.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 1px solid #28303d;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        ins_layout = QVBoxLayout(self.inspector_card)
        ins_layout.setContentsMargins(8, 8, 8, 8)
        ins_layout.setSpacing(10)

        ins_header = QHBoxLayout()
        self.lbl_selected_title = QLabel("Chi tiết vùng đang chọn:")
        self.lbl_selected_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #ffffff;")
        ins_header.addWidget(self.lbl_selected_title, 1)

        self.btn_delete_region = QPushButton("🗑 Xóa vùng")
        self.btn_delete_region.setProperty("class", "dangerBtn")
        self.btn_delete_region.clicked.connect(self._on_delete_clicked)
        self.btn_delete = self.btn_delete_region
        ins_header.addWidget(self.btn_delete_region)
        ins_layout.addLayout(ins_header)

        # Coordinate Grid (X, Y, Width, Height in %)
        coord_grid = QHBoxLayout()
        coord_grid.setSpacing(8)

        # X
        x_box = QVBoxLayout()
        lbl_x = QLabel("Tọa độ X:")
        lbl_x.setProperty("class", "fieldLabel")
        x_box.addWidget(lbl_x)
        self.spin_x = QDoubleSpinBox()
        self.spin_x.setRange(0.0, 100.0)
        self.spin_x.setSingleStep(0.5)
        self.spin_x.setSuffix("%")
        self.spin_x.valueChanged.connect(self._on_coords_edited)
        x_box.addWidget(self.spin_x)
        coord_grid.addLayout(x_box)

        # Y
        y_box = QVBoxLayout()
        lbl_y = QLabel("Tọa độ Y:")
        lbl_y.setProperty("class", "fieldLabel")
        y_box.addWidget(lbl_y)
        self.spin_y = QDoubleSpinBox()
        self.spin_y.setRange(0.0, 100.0)
        self.spin_y.setSingleStep(0.5)
        self.spin_y.setSuffix("%")
        self.spin_y.valueChanged.connect(self._on_coords_edited)
        y_box.addWidget(self.spin_y)
        coord_grid.addLayout(y_box)

        # Width
        w_box = QVBoxLayout()
        lbl_w = QLabel("Rộng (W):")
        lbl_w.setProperty("class", "fieldLabel")
        w_box.addWidget(lbl_w)
        self.spin_w = QDoubleSpinBox()
        self.spin_w.setRange(1.0, 100.0)
        self.spin_w.setSingleStep(0.5)
        self.spin_w.setSuffix("%")
        self.spin_w.valueChanged.connect(self._on_coords_edited)
        w_box.addWidget(self.spin_w)
        coord_grid.addLayout(w_box)

        # Height
        h_box = QVBoxLayout()
        lbl_h = QLabel("Cao (H):")
        lbl_h.setProperty("class", "fieldLabel")
        h_box.addWidget(lbl_h)
        self.spin_h = QDoubleSpinBox()
        self.spin_h.setRange(1.0, 100.0)
        self.spin_h.setSingleStep(0.5)
        self.spin_h.setSuffix("%")
        self.spin_h.valueChanged.connect(self._on_coords_edited)
        h_box.addWidget(self.spin_h)
        coord_grid.addLayout(h_box)

        ins_layout.addLayout(coord_grid)

        # Blur Strength Slider
        blur_box = QVBoxLayout()
        blur_box.setSpacing(4)
        blur_row = QHBoxLayout()
        lbl_blur = QLabel("Độ làm mờ (Blur Strength):")
        lbl_blur.setProperty("class", "fieldLabel")
        blur_row.addWidget(lbl_blur, 1)
        self.lbl_blur_val = QLabel("20 px")
        self.lbl_blur_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #72d7c1;")
        blur_row.addWidget(self.lbl_blur_val)
        blur_box.addLayout(blur_row)

        self.slider_blur = QSlider(Qt.Orientation.Horizontal)
        self.slider_blur.setRange(5, 50)
        self.slider_blur.setValue(20)
        self.slider_blur.valueChanged.connect(self._on_blur_slider_changed)
        blur_box.addWidget(self.slider_blur)

        ins_layout.addLayout(blur_box)
        layout.addWidget(self.inspector_card)

        # Empty state notice
        self.lbl_empty = QLabel("Chưa có vùng làm mờ. Bấm nút '➕ Thêm vùng' để tạo vùng che trên video.")
        self.lbl_empty.setStyleSheet("color: #8b949e; font-size: 11px; padding: 12px; background: #161b22; border-radius: 6px;")
        self.lbl_empty.setWordWrap(True)
        layout.addWidget(self.lbl_empty)

        # Canvas interaction hint
        hint_box = QLabel("💡 Khung hình chữ nhật hiển thị trực tiếp trên màn hình video xem trước. Bạn có thể nhấp kéo để di chuyển hoặc kéo góc để đổi kích thước nhanh.")
        hint_box.setStyleSheet("color: #72d7c1; font-size: 11px; font-style: italic;")
        hint_box.setWordWrap(True)
        layout.addWidget(hint_box)

        layout.addStretch(1)

        # 4. Navigation Footer (Back & Continue)
        nav_row = QHBoxLayout()
        nav_row.setSpacing(10)

        self.btn_back = QPushButton("← Quay lại")
        self.btn_back.setProperty("class", "navBackBtn")
        self.btn_back.clicked.connect(self.back_requested.emit)
        nav_row.addWidget(self.btn_back)

        self.btn_continue = QPushButton("Tiếp tục: Xử lý tự động →")
        self.btn_continue.setProperty("class", "primaryBtn")
        self.btn_continue.clicked.connect(self.continue_requested.emit)
        nav_row.addWidget(self.btn_continue, 1)

        layout.addLayout(nav_row)

    def set_masks(self, masks: list[MaskItem], active_id: str | None = None) -> None:
        self._masks = list(masks)
        self._updating_ui = True
        self.region_list.clear()

        has_masks = len(self._masks) > 0
        self.inspector_card.setVisible(has_masks)
        self.lbl_empty.setVisible(not has_masks)

        select_row = -1
        for idx, m in enumerate(self._masks):
            kind_icon = "▣" if m.mask_type == "erase" else "🌫"
            size_tag = f"[{round(m.width * 100)}% × {round(m.height * 100)}%]"
            item = QListWidgetItem(f"{kind_icon}  {m.name or f'Vùng {idx + 1}'}   {size_tag}")
            item.setData(Qt.ItemDataRole.UserRole, m.id)
            self.region_list.addItem(item)
            if active_id and m.id == active_id:
                select_row = idx

        if select_row >= 0:
            self.region_list.setCurrentRow(select_row)
        elif has_masks:
            self.region_list.setCurrentRow(0)

        self._updating_ui = False
        self._sync_inspector_to_active()

    def update_mask_rect(self, mask_id: str, x: float, y: float, w: float, h: float) -> None:
        """Called when user drags/resizes rect on video canvas."""
        for m in self._masks:
            if m.id == mask_id:
                m.x, m.y, m.width, m.height = x, y, w, h
                break
        if self._current_mask_id == mask_id:
            self._updating_ui = True
            self.spin_x.setValue(round(x * 100, 1))
            self.spin_y.setValue(round(y * 100, 1))
            self.spin_w.setValue(round(w * 100, 1))
            self.spin_h.setValue(round(h * 100, 1))
            self._updating_ui = False

    def _on_list_selection_changed(self, row: int) -> None:
        if self._updating_ui or row < 0 or row >= len(self._masks):
            return
        mask = self._masks[row]
        self._current_mask_id = mask.id
        self.region_selected.emit(mask.id)
        self._sync_inspector_to_active()

    def _sync_inspector_to_active(self) -> None:
        mask = next((m for m in self._masks if m.id == self._current_mask_id), None)
        if not mask and self._masks:
            mask = self._masks[0]
            self._current_mask_id = mask.id

        if not mask:
            self.inspector_card.hide()
            self.lbl_empty.show()
            return

        self.inspector_card.show()
        self.lbl_empty.hide()
        self.lbl_selected_title.setText(f"Chi tiết: {mask.name}")

        self._updating_ui = True
        self.spin_x.setValue(round(mask.x * 100, 1))
        self.spin_y.setValue(round(mask.y * 100, 1))
        self.spin_w.setValue(round(mask.width * 100, 1))
        self.spin_h.setValue(round(mask.height * 100, 1))
        strength = int(mask.blur_strength or 20)
        self.slider_blur.setValue(strength)
        self.lbl_blur_val.setText(f"{strength} px")
        self._updating_ui = False

    def _on_coords_edited(self) -> None:
        if self._updating_ui or not self._current_mask_id:
            return
        x = self.spin_x.value() / 100.0
        y = self.spin_y.value() / 100.0
        w = self.spin_w.value() / 100.0
        h = self.spin_h.value() / 100.0
        strength = self.slider_blur.value()
        self.region_changed.emit(self._current_mask_id, x, y, w, h, strength)

    def _on_blur_slider_changed(self, val: int) -> None:
        self.lbl_blur_val.setText(f"{val} px")
        if not self._updating_ui and self._current_mask_id:
            self._on_coords_edited()

    def _on_delete_clicked(self) -> None:
        if self._current_mask_id:
            self.delete_region_requested.emit(self._current_mask_id)

    def regions_summary(self) -> str:
        count = len(self._masks)
        if count == 0:
            return "Chưa tạo vùng"
        return f"{count} vùng che mờ"
