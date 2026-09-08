from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from vkdub.domain.mask import MaskItem
from vkdub.domain.project import Project
from vkdub.services.mask_service import (
    build_ffmpeg_mask_filter,
    hex_to_ffmpeg_color,
    validate_mask,
)
from vkdub.services.project_service import load_project, save_project
from vkdub.ui.mask_dialog import MaskEditorDialog
from vkdub.ui.video_canvas import VideoCanvas


def test_mask_item_defaults_and_clamping():
    mask = MaskItem(
        x=-0.5,
        y=1.5,
        width=2.0,
        height=0.001,
        opacity=0.01,
        blur_strength=100,
        start_ms=-50,
        end_ms=-10,
    )
    assert mask.id != ""
    assert mask.mask_type == "erase"
    assert mask.x == 0.0
    assert mask.y == 1.0
    assert 0.01 <= mask.width <= 1.0
    assert 0.01 <= mask.height <= 1.0
    assert mask.opacity == 0.1
    assert mask.blur_strength == 50
    assert mask.start_ms == 0
    assert mask.end_ms == 0


def test_mask_item_is_active_at():
    # Full duration mask (0, 0)
    m_full = MaskItem(start_ms=0, end_ms=0)
    assert m_full.is_active_at(0) is True
    assert m_full.is_active_at(100000) is True

    # Range mask (5000 to 10000)
    m_range = MaskItem(start_ms=5000, end_ms=10000)
    assert m_range.is_active_at(4999) is False
    assert m_range.is_active_at(5000) is True
    assert m_range.is_active_at(7500) is True
    assert m_range.is_active_at(10000) is True
    assert m_range.is_active_at(10001) is False

    # Open-ended mask (start 3000, end 0)
    m_open = MaskItem(start_ms=3000, end_ms=0)
    assert m_open.is_active_at(2000) is False
    assert m_open.is_active_at(3000) is True
    assert m_open.is_active_at(99999) is True


def test_to_pixel_rect():
    mask = MaskItem(x=0.1, y=0.8, width=0.8, height=0.15)
    x, y, w, h = mask.to_pixel_rect(1920, 1080)
    assert x == 192
    assert y == 864
    assert w == 1536
    assert h == 162


def test_hex_to_ffmpeg_color():
    assert hex_to_ffmpeg_color("#000000", 1.0) == "0x000000@1.00"
    assert hex_to_ffmpeg_color("#FFFFFF", 0.5) == "0xFFFFFF@0.50"
    assert hex_to_ffmpeg_color("invalid", 0.8) == "black@0.80"


def test_build_ffmpeg_mask_filter():
    m1 = MaskItem(
        name="Bottom subtitle blur",
        mask_type="blur",
        x=0.1,
        y=0.8,
        width=0.8,
        height=0.15,
        start_ms=1000,
        end_ms=5000,
    )
    m2 = MaskItem(
        name="Top logo solid",
        mask_type="solid",
        x=0.8,
        y=0.05,
        width=0.15,
        height=0.1,
        color="#000000",
        opacity=0.9,
        start_ms=0,
        end_ms=0,
    )
    filter_chain = build_ffmpeg_mask_filter([m1, m2], 1920, 1080)
    assert "boxblur=15:3" in filter_chain
    assert "blend=all_expr=" in filter_chain
    assert ":enable='between(t,1.000,5.000)'" in filter_chain
    assert "drawbox=x=1536:y=54:w=288:h=108:color=0x000000@0.90:t=fill" in filter_chain


def test_build_ffmpeg_erase_filter_is_edge_safe():
    mask = MaskItem(mask_type="erase", x=0, y=0.8, width=1, height=0.2)
    filter_chain = build_ffmpeg_mask_filter([mask], 1920, 1080)
    assert filter_chain == "delogo=x=1:y=864:w=1918:h=215:show=0"


def test_validate_mask():
    valid_mask = MaskItem(x=0.1, y=0.1, width=0.5, height=0.5, start_ms=0, end_ms=2000)
    assert validate_mask(valid_mask) == []

    invalid_mask = MaskItem()
    invalid_mask.start_ms = 5000
    invalid_mask.end_ms = 2000
    errors = validate_mask(invalid_mask)
    assert any("Thời gian kết thúc" in e for e in errors)


def test_project_masks_roundtrip(tmp_path):
    masks = [
        MaskItem(name="Mask 1", mask_type="blur", x=0.05, y=0.85, width=0.9, height=0.1),
        MaskItem(name="Mask 2", mask_type="solid", color="#FF0000", opacity=0.8),
    ]
    project = Project(masks=masks)
    target = tmp_path / "project_with_masks.vkdub"
    save_project(project, target)

    loaded = load_project(target)
    assert len(loaded.masks) == 2
    assert loaded.masks[0].name == "Mask 1"
    assert loaded.masks[0].mask_type == "blur"
    assert loaded.masks[1].name == "Mask 2"
    assert loaded.masks[1].color == "#FF0000"


def test_video_canvas_mask_rendering_and_interaction(qtbot):
    canvas = VideoCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(640, 360)

    img = QImage(640, 360, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.white)
    canvas.frame_image = img

    m = MaskItem(
        id="mask-1",
        name="Test Blur",
        mask_type="blur",
        x=0.2,
        y=0.7,
        width=0.6,
        height=0.2,
    )
    canvas.set_masks([m], active_id="mask-1", time_ms=0)
    canvas.repaint()

    assert len(canvas.masks) == 1
    assert canvas.active_mask_id == "mask-1"


def test_mask_editor_dialog_actions(qtbot):
    dialog = MaskEditorDialog()
    qtbot.addWidget(dialog)

    initial_masks = [
        MaskItem(name="Mask A", mask_type="blur", x=0.1, y=0.8, width=0.8, height=0.15),
    ]
    dialog.load_masks(initial_masks)
    assert dialog.table.rowCount() == 1

    # Add mask
    dialog._add_mask()
    assert dialog.table.rowCount() == 2
    assert len(dialog.masks) == 2
    assert dialog.masks[-1].mask_type == "erase"

    # Duplicate mask
    dialog._duplicate_mask()
    assert dialog.table.rowCount() == 3
    assert len(dialog.masks) == 3

    # Delete mask
    dialog._delete_mask()
    assert dialog.table.rowCount() == 2
    assert len(dialog.masks) == 2


def test_sub_region_skips_ffmpeg_filter():
    sub_mask = MaskItem(
        id="sub-1",
        name="Vùng lấy sub",
        mask_type="sub_region",
        x=0.08,
        y=0.76,
        width=0.84,
        height=0.15,
    )
    # sub_region masks must not generate blur or delogo filters
    filter_chain = build_ffmpeg_mask_filter([sub_mask], 1920, 1080)
    assert filter_chain == ""


def test_step3_panel_sub_region_operations(qtbot):
    from vkdub.ui.panels.step3_blur_panel import Step3BlurPanel

    panel = Step3BlurPanel()
    qtbot.addWidget(panel)

    m1 = MaskItem(
        id="sub-bottom",
        name="Sub dưới",
        mask_type="sub_region",
        x=0.08,
        y=0.76,
        width=0.84,
        height=0.15,
    )
    m2 = MaskItem(
        id="blur-1",
        name="Logo mờ",
        mask_type="blur",
        x=0.1,
        y=0.05,
        width=0.2,
        height=0.1,
    )
    panel.set_masks([m1, m2], active_id="sub-bottom")
    panel.show()
    assert panel.region_list.count() == 2
    assert "🔴 [LẤY SUB]" in panel.region_list.item(0).text()
    assert "🌫 [LÀM MỜ]" in panel.region_list.item(1).text()

    # Sub banner is visible, blur box is hidden for sub_region
    assert panel.sub_banner.isVisible() is True
    assert panel.blur_box_widget.isVisible() is False

    # Snap presets
    panel._snap_top()
    assert panel.spin_y.value() == 6.0
    assert panel.spin_h.value() == 15.0

    panel._snap_bottom()
    assert panel.spin_y.value() == 76.0

    # Summary
    summary = panel.regions_summary()
    assert "1 vùng sub (viền đỏ)" in summary
    assert "1 vùng làm mờ" in summary

