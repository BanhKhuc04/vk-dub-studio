"""VK Dub Studio — Step 03: Blur Regions & Subtitle Extraction Inspector Panel.

Contextual panel for inspecting and adjusting visual regions:
- Subtitle extraction regions (Red border `#ef4444`, sharp video, multi-selection top/bottom)
- Blur & erase masks (Cyan border, pixel blurring/delogo)
- Quick position presets (Bottom, Top, Full width)
- Inspector fields: Name, Type, X, Y, Width, Height, Blur strength
- Interactive sync with on-video canvas rectangle
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from vkdub.domain.mask import MaskItem
from vkdub.ui.theme import apply_brutalist_shadow


class Step3BlurPanel(QFrame):
    """Contextual panel for Step 3: Blur & Subtitle Extraction Inspector."""

    add_region_requested = Signal()
    add_mask_requested = Signal()
    add_sub_region_requested = Signal(str)  # position: "bottom" | "top" | "custom"
    delete_region_requested = Signal(str)  # mask_id
    region_selected = Signal(str)  # mask_id
    region_changed = Signal(str, float, float, float, float, int)  # mask_id, x, y, w, h, strength
    region_type_changed = Signal(str, str)  # mask_id, new_mask_type
    region_name_changed = Signal(str, str)  # mask_id, new_name
    back_requested = Signal()
    continue_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("step3Panel")
        self.setStyleSheet("""
            QFrame#step3Panel {
                background-color: #ffffff;
            }
            QLabel.panelHeader {
                font-size: 20px;
                font-weight: 900;
                color: #101828;
                letter-spacing: 0.3px;
            }
            QLabel.panelSub {
                font-size: 12px;
                color: #64748b;
                line-height: 1.4;
            }
            QLabel.fieldLabel {
                font-size: 12px;
                font-weight: 800;
                color: #0f172a;
            }
            QListWidget {
                background-color: #ffffff;
                border: 2px solid #0f172a;
                border-radius: 8px;
                color: #0f172a;
                font-size: 11px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px 10px;
                border-radius: 6px;
                margin-bottom: 2px;
            }
            QListWidget::item:selected {
                background-color: #fff0f5;
                color: #0f172a;
                font-weight: 800;
                border: 1px solid #0f172a;
            }
            QDoubleSpinBox, QSpinBox, QLineEdit, QComboBox {
                background-color: #ffffff;
                color: #0f172a;
                border: 2px solid #0f172a;
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QDoubleSpinBox:hover, QSpinBox:hover, QLineEdit:focus, QComboBox:hover {
                background-color: #f8fafc;
            }
            QPushButton.primaryBtn {
                background-color: #b9f227;
                color: #0f172a;
                font-size: 13px;
                font-weight: 900;
                padding: 11px 18px;
                border: 2px solid #0f172a;
                border-radius: 8px;
                letter-spacing: 0.3px;
            }
            QPushButton.primaryBtn:hover {
                background-color: #a7df18;
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
                background-color: #ffffff;
                color: #0f172a;
                font-size: 11px;
                font-weight: 800;
                padding: 7px 12px;
                border: 2px solid #0f172a;
                border-radius: 6px;
            }
            QPushButton.actionBtn:hover {
                background-color: #f8fafc;
            }
            QPushButton.redBtn {
                background-color: #fee2e2;
                color: #b91c1c;
                font-size: 11px;
                font-weight: 800;
                padding: 7px 12px;
                border: 2px solid #0f172a;
                border-radius: 6px;
            }
            QPushButton.redBtn:hover {
                background-color: #fecaca;
            }
            QPushButton.snapBtn {
                background-color: #ffffff;
                color: #0f172a;
                border: 1.5px solid #0f172a;
                border-radius: 5px;
                font-size: 10px;
                font-weight: 700;
                padding: 3px 8px;
            }
            QPushButton.snapBtn:hover {
                background-color: #f1f5f9;
            }
            QPushButton.dangerBtn {
                background-color: #fee2e2;
                color: #b91c1c;
                font-size: 11px;
                font-weight: 800;
                padding: 6px 12px;
                border: 2px solid #0f172a;
                border-radius: 6px;
            }
            QPushButton.dangerBtn:hover {
                background-color: #fca5a5;
            }
        """)

        self._masks: list[MaskItem] = []
        self._current_mask_id: str | None = None
        self._updating_ui = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(13)

        # 1. Header
        header_col = QVBoxLayout()
        header_col.setSpacing(3)
        title = QLabel("03 KHUNG CHE & VÙNG LẤY SUB")
        title.setProperty("class", "panelHeader")
        header_col.addWidget(title)
        subtitle = QLabel("Tách biệt vùng làm mờ xóa chữ và vùng lấy phụ đề (viền đỏ) - hỗ trợ sub ở trên hoặc ở dưới")
        subtitle.setProperty("class", "panelSub")
        subtitle.setWordWrap(True)
        header_col.addWidget(subtitle)
        layout.addLayout(header_col)

        # 2. Add Actions - Đơn giản hóa thành 3 nút trực quan, dễ bấm
        add_buttons_row = QHBoxLayout()
        add_buttons_row.setSpacing(8)

        self.btn_preset_bottom = QPushButton("🔴 Sub ở dưới")
        self.btn_preset_bottom.setProperty("class", "redBtn")
        self.btn_preset_bottom.setToolTip("Thêm khung lấy phụ đề viền đỏ ở cạnh dưới (mặc định)")
        self.btn_preset_bottom.clicked.connect(lambda: self.add_sub_region_requested.emit("bottom"))
        add_buttons_row.addWidget(self.btn_preset_bottom, 1)

        self.btn_preset_top = QPushButton("🔴 Sub ở trên")
        self.btn_preset_top.setProperty("class", "redBtn")
        self.btn_preset_top.setToolTip("Thêm khung lấy phụ đề viền đỏ ở cạnh trên (video sub trên)")
        self.btn_preset_top.clicked.connect(lambda: self.add_sub_region_requested.emit("top"))
        add_buttons_row.addWidget(self.btn_preset_top, 1)

        self.btn_add_region = QPushButton("🌫 Thêm làm mờ")
        self.btn_add_region.setProperty("class", "actionBtn")
        self.btn_add_region.setToolTip("Thêm vùng làm mờ mới để che watermark hoặc phụ đề cũ")
        self.btn_add_region.clicked.connect(self.add_region_requested.emit)
        add_buttons_row.addWidget(self.btn_add_region, 1)

        self.btn_add_sub = self.btn_preset_bottom  # alias for compatibility

        layout.addLayout(add_buttons_row)

        # 3. Region List
        self.lbl_region_list = QLabel("DANH SÁCH CÁC VÙNG:")
        self.lbl_region_list.setStyleSheet("font-size: 11px; font-weight: bold; color: #8b949e; letter-spacing: 0.5px;")
        layout.addWidget(self.lbl_region_list)

        self.region_list = QListWidget()
        self.region_list.setFixedHeight(112)
        self.region_list.currentRowChanged.connect(self._on_list_selection_changed)
        self.regions_list = self.region_list
        layout.addWidget(self.region_list)

        # 4. Selected Region Inspector Card
        self.inspector_card = QFrame()
        self.inspector_card.setObjectName("regionInspector")
        self.inspector_card.setStyleSheet("""
            QFrame#regionInspector {
                background-color: #ffffff;
                border: 3px solid #101828;
                border-radius: 14px;
                padding: 12px;
            }
        """)
        ins_layout = QVBoxLayout(self.inspector_card)
        ins_layout.setContentsMargins(11, 11, 11, 11)
        ins_layout.setSpacing(9)

        # Header: Title & Delete
        ins_header = QHBoxLayout()
        self.lbl_selected_title = QLabel("Chi tiết vùng đang chọn:")
        self.lbl_selected_title.setStyleSheet("font-size: 12px; font-weight: 900; color: #0f172a;")
        ins_header.addWidget(self.lbl_selected_title, 1)

        self.btn_delete_region = QPushButton("🗑 Xóa vùng")
        self.btn_delete_region.setProperty("class", "dangerBtn")
        self.btn_delete_region.clicked.connect(self._on_delete_clicked)
        self.btn_delete = self.btn_delete_region
        ins_header.addWidget(self.btn_delete_region)
        ins_layout.addLayout(ins_header)

        # Name & Type row
        name_type_row = QHBoxLayout()
        name_type_row.setSpacing(8)

        name_box = QVBoxLayout()
        name_box.setSpacing(2)
        lbl_name = QLabel("Tên vùng:")
        lbl_name.setProperty("class", "fieldLabel")
        name_box.addWidget(lbl_name)
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("Ví dụ: Sub ở dưới...")
        self.edit_name.textChanged.connect(self._on_name_edited)
        name_box.addWidget(self.edit_name)
        name_type_row.addLayout(name_box, 1)

        type_box = QVBoxLayout()
        type_box.setSpacing(2)
        lbl_type = QLabel("Loại vùng:")
        lbl_type.setProperty("class", "fieldLabel")
        type_box.addWidget(lbl_type)
        self.combo_type = QComboBox()
        self.combo_type.addItem("🔴 Vùng lấy Sub (Viền đỏ)", "sub_region")
        self.combo_type.addItem("🌫 Làm mờ (Blur)", "blur")
        self.combo_type.addItem("▣ Che chữ hòa nền (Erase)", "erase")
        self.combo_type.currentIndexChanged.connect(self._on_type_changed)
        type_box.addWidget(self.combo_type)
        name_type_row.addLayout(type_box, 1)

        ins_layout.addLayout(name_type_row)

        # Quick snapping position buttons inside inspector
        snap_row = QHBoxLayout()
        snap_row.setSpacing(6)
        lbl_snap = QLabel("Gắn nhanh:")
        lbl_snap.setStyleSheet("font-size: 10px; color: #0f172a; font-weight: 800;")
        snap_row.addWidget(lbl_snap)

        self.btn_snap_bottom = QPushButton("⬇ Ở dưới (76%)")
        self.btn_snap_bottom.setProperty("class", "snapBtn")
        self.btn_snap_bottom.clicked.connect(self._snap_bottom)
        snap_row.addWidget(self.btn_snap_bottom)

        self.btn_snap_top = QPushButton("⬆ Ở trên (6%)")
        self.btn_snap_top.setProperty("class", "snapBtn")
        self.btn_snap_top.clicked.connect(self._snap_top)
        snap_row.addWidget(self.btn_snap_top)

        self.btn_snap_full = QPushButton("↔ Toàn rộng (84%)")
        self.btn_snap_full.setProperty("class", "snapBtn")
        self.btn_snap_full.clicked.connect(self._snap_full_width)
        snap_row.addWidget(self.btn_snap_full)

        snap_row.addStretch(1)
        ins_layout.addLayout(snap_row)

        # Coordinate Grid (X, Y, Width, Height in %)
        coord_grid = QHBoxLayout()
        coord_grid.setSpacing(6)

        # X
        x_box = QVBoxLayout()
        x_box.setSpacing(2)
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
        y_box.setSpacing(2)
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
        w_box.setSpacing(2)
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
        h_box.setSpacing(2)
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

        # Sub Region Contextual Banner (Notice)
        self.sub_banner = QFrame()
        self.sub_banner.setObjectName("subtitleRegionBanner")
        self.sub_banner.setStyleSheet("""
            QFrame#subtitleRegionBanner {
                background-color: #fef2f2;
                border: 2px solid #0f172a;
                border-radius: 6px;
                padding: 6px 8px;
            }
        """)
        sub_banner_layout = QVBoxLayout(self.sub_banner)
        sub_banner_layout.setContentsMargins(4, 4, 4, 4)
        sub_banner_layout.setSpacing(3)
        lbl_sub_info = QLabel("🔴 VÙNG LẤY PHỤ ĐỀ (VIỀN ĐỎ):")
        lbl_sub_info.setStyleSheet("font-size: 11px; font-weight: 900; color: #b91c1c;")
        sub_banner_layout.addWidget(lbl_sub_info)
        lbl_sub_desc = QLabel(
            "• Định vị phụ đề xuất hiện (trên hoặc dưới video).\n"
            "• Video xuất ra GIỮ NGUYÊN ĐỘ NÉT 100%, hoàn toàn không bị làm mờ.\n"
            "• Kéo chuột trực tiếp trên khung video xem trước để chỉnh nhanh cỡ chữ."
        )
        lbl_sub_desc.setStyleSheet("font-size: 10px; color: #7f1d1d; font-weight: 600; line-height: 1.3;")
        lbl_sub_desc.setWordWrap(True)
        sub_banner_layout.addWidget(lbl_sub_desc)
        ins_layout.addWidget(self.sub_banner)

        # Blur Strength Widget (Shown only for Blur / Erase masks)
        self.blur_box_widget = QWidget()
        blur_box = QVBoxLayout(self.blur_box_widget)
        blur_box.setContentsMargins(0, 0, 0, 0)
        blur_box.setSpacing(4)
        blur_row = QHBoxLayout()
        lbl_blur = QLabel("Độ làm mờ (Blur Strength):")
        lbl_blur.setProperty("class", "fieldLabel")
        blur_row.addWidget(lbl_blur, 1)
        self.lbl_blur_val = QLabel("20 px")
        self.lbl_blur_val.setStyleSheet("font-size: 11px; font-weight: 800; color: #0f172a;")
        blur_row.addWidget(self.lbl_blur_val)
        blur_box.addLayout(blur_row)

        self.slider_blur = QSlider(Qt.Orientation.Horizontal)
        self.slider_blur.setRange(5, 50)
        self.slider_blur.setValue(20)
        self.slider_blur.valueChanged.connect(self._on_blur_slider_changed)
        blur_box.addWidget(self.slider_blur)

        ins_layout.addWidget(self.blur_box_widget)
        layout.addWidget(self.inspector_card)
        apply_brutalist_shadow(self.inspector_card, offset=4)

        # Empty state notice
        self.lbl_empty = QLabel(
            "Chưa có vùng làm mờ hoặc vùng lấy sub nào.\n"
            "• Bấm ‘Sub ở dưới’ hoặc ‘Sub ở trên’ để đánh dấu vùng chữ (viền đỏ).\n"
            "• Bấm ‘Thêm làm mờ’ để tạo vùng che chữ cũ hoặc logo."
        )
        self.lbl_empty.setStyleSheet("""
            color: #334155;
            font-size: 11px;
            font-weight: 700;
            padding: 12px;
            background-color: #f8fafc;
            border: 2px dashed #0f172a;
            border-radius: 8px;
        """)
        self.lbl_empty.setWordWrap(True)
        layout.addWidget(self.lbl_empty)

        # Canvas interaction hint
        hint_box = QLabel("💡 Khung chữ nhật hiển thị trực tiếp trên màn hình video xem trước. Bạn có thể nhấp kéo để di chuyển hoặc kéo 4 góc để đổi kích cỡ.")
        hint_box.setStyleSheet("color: #72d7c1; font-size: 11px; font-style: italic;")
        hint_box.setWordWrap(True)
        layout.addWidget(hint_box)

        layout.addStretch(1)

        # 5. Navigation Footer (Back & Continue)
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
        self.set_masks([], None)

    def set_masks(self, masks: list[MaskItem], active_id: str | None = None) -> None:
        self._masks = list(masks)
        self._updating_ui = True
        self.region_list.clear()

        has_masks = len(self._masks) > 0
        self.lbl_region_list.setVisible(has_masks)
        self.region_list.setVisible(has_masks)
        self.inspector_card.setVisible(has_masks)
        self.lbl_empty.setVisible(not has_masks)

        select_row = -1
        for idx, m in enumerate(self._masks):
            size_tag = f"[{round(m.width * 100)}% × {round(m.height * 100)}%]"
            if m.mask_type == "sub_region":
                pos_hint = "Dưới" if m.y >= 0.5 else "Trên"
                display_name = m.name or f"Vùng sub {idx + 1}"
                item = QListWidgetItem(f"🔴 [LẤY SUB]  {display_name} ({pos_hint})   {size_tag}")
                item.setForeground(QColor("#fca5a5"))
            elif m.mask_type == "erase":
                display_name = m.name or f"Vùng che {idx + 1}"
                item = QListWidgetItem(f"▣ [XÓA CHỮ]  {display_name}   {size_tag}")
                item.setForeground(QColor("#38bdf8"))
            else:
                display_name = m.name or f"Vùng mờ {idx + 1}"
                item = QListWidgetItem(f"🌫 [LÀM MỜ]   {display_name}   {size_tag}")
                item.setForeground(QColor("#7dd3fc"))

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

    def select_mask(self, mask_id: str) -> None:
        """Select a mask by ID in the list without triggering extra feedback loops."""
        if self._current_mask_id == mask_id:
            return
        for idx in range(self.region_list.count()):
            item = self.region_list.item(idx)
            if item and item.data(Qt.ItemDataRole.UserRole) == mask_id:
                self._updating_ui = True
                self.region_list.setCurrentRow(idx)
                self._current_mask_id = mask_id
                self._updating_ui = False
                self._sync_inspector_to_active()
                break

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
        self.edit_name.setText(mask.name)

        idx_type = self.combo_type.findData(mask.mask_type)
        if idx_type >= 0:
            self.combo_type.setCurrentIndex(idx_type)

        self.spin_x.setValue(round(mask.x * 100, 1))
        self.spin_y.setValue(round(mask.y * 100, 1))
        self.spin_w.setValue(round(mask.width * 100, 1))
        self.spin_h.setValue(round(mask.height * 100, 1))

        is_sub = mask.mask_type == "sub_region"
        self.sub_banner.setVisible(is_sub)
        self.blur_box_widget.setVisible(not is_sub)

        strength = int(mask.blur_strength or 20)
        self.slider_blur.setValue(strength)
        self.lbl_blur_val.setText(f"{strength} px")
        self._updating_ui = False

    def _on_name_edited(self, new_name: str) -> None:
        if self._updating_ui or not self._current_mask_id:
            return
        mask = next((m for m in self._masks if m.id == self._current_mask_id), None)
        if mask:
            mask.name = new_name
            self.lbl_selected_title.setText(f"Chi tiết: {new_name}")
            row = self.region_list.currentRow()
            if row >= 0:
                item = self.region_list.item(row)
                if item:
                    size_tag = f"[{round(mask.width * 100)}% × {round(mask.height * 100)}%]"
                    if mask.mask_type == "sub_region":
                        pos_hint = "Dưới" if mask.y >= 0.5 else "Trên"
                        item.setText(f"🔴 [LẤY SUB]  {new_name} ({pos_hint})   {size_tag}")
                    elif mask.mask_type == "erase":
                        item.setText(f"▣ [XÓA CHỮ]  {new_name}   {size_tag}")
                    else:
                        item.setText(f"🌫 [LÀM MỜ]   {new_name}   {size_tag}")
            self.region_name_changed.emit(self._current_mask_id, new_name)

    def _on_type_changed(self) -> None:
        if self._updating_ui or not self._current_mask_id:
            return
        new_type = self.combo_type.currentData()
        mask = next((m for m in self._masks if m.id == self._current_mask_id), None)
        if mask and mask.mask_type != new_type:
            mask.mask_type = new_type
            is_sub = new_type == "sub_region"
            self.sub_banner.setVisible(is_sub)
            self.blur_box_widget.setVisible(not is_sub)
            row = self.region_list.currentRow()
            if row >= 0:
                item = self.region_list.item(row)
                if item:
                    size_tag = f"[{round(mask.width * 100)}% × {round(mask.height * 100)}%]"
                    if is_sub:
                        pos_hint = "Dưới" if mask.y >= 0.5 else "Trên"
                        item.setText(f"🔴 [LẤY SUB]  {mask.name} ({pos_hint})   {size_tag}")
                        item.setForeground(QColor("#fca5a5"))
                    elif new_type == "erase":
                        item.setText(f"▣ [XÓA CHỮ]  {mask.name}   {size_tag}")
                        item.setForeground(QColor("#38bdf8"))
                    else:
                        item.setText(f"🌫 [LÀM MỜ]   {mask.name}   {size_tag}")
                        item.setForeground(QColor("#7dd3fc"))
            self.region_type_changed.emit(self._current_mask_id, new_type)

    def _snap_bottom(self) -> None:
        if not self._current_mask_id:
            return
        self.spin_x.setValue(8.0)
        self.spin_y.setValue(76.0)
        self.spin_w.setValue(84.0)
        self.spin_h.setValue(15.0)

    def _snap_top(self) -> None:
        if not self._current_mask_id:
            return
        self.spin_x.setValue(8.0)
        self.spin_y.setValue(6.0)
        self.spin_w.setValue(84.0)
        self.spin_h.setValue(15.0)

    def _snap_full_width(self) -> None:
        if not self._current_mask_id:
            return
        self.spin_x.setValue(8.0)
        self.spin_w.setValue(84.0)

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
        sub_count = sum(1 for m in self._masks if m.mask_type == "sub_region")
        blur_count = count - sub_count
        parts = []
        if sub_count > 0:
            parts.append(f"{sub_count} vùng sub (viền đỏ)")
        if blur_count > 0:
            parts.append(f"{blur_count} vùng làm mờ")
        return ", ".join(parts)
