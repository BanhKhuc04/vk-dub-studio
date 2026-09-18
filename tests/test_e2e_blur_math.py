"""Tier 2 E2E Test Suite: Blur Coordinate Transformations & Mathematical Integrity.

Covers:
- Viewport calculation under CSS `object-fit: contain` (Letterbox and Pillarbox)
- Screen/Canvas pixel to normalized `[0.0, 1.0]` coordinate transformations
- Boundary clamping, margin hit rejection, and roundtrip quantization invariance
- 8-handle resizing arithmetic (nw, n, ne, e, se, s, sw, w) with anti-inversion
- Translation/dragging boundary constraints
- Multi-aspect ratio scenarios (16:9, 9:16, 1:1, 21:9, 4:3)
- Multi-mask layering, intersection, and IoU calculations
- FFmpeg filter graph syntax generation (`delogo`, `boxblur`, `drawbox`, `blend`)
- FFmpeg delogo 1-pixel boundary context compliance
- Timing filter expressions (`between`, `gte`)
- Mask validation and adversarial edge cases
"""

import math
import pytest

from vkdub.domain.mask import MaskItem
from vkdub.services.mask_service import (
    build_ffmpeg_mask_filter,
    hex_to_ffmpeg_color,
    validate_mask,
)


# ===========================================================================
# Reference Mathematical Implementations for Interactive Video Canvas
# ===========================================================================

def calculate_video_viewport(
    container_w: float,
    container_h: float,
    video_w: float,
    video_h: float,
) -> tuple[float, float, float, float]:
    """Calculate the rendered video box inside a container using `object-fit: contain`.

    Returns (offset_x, offset_y, render_w, render_h).
    """
    assert container_w > 0 and container_h > 0
    assert video_w > 0 and video_h > 0

    ar_container = container_w / container_h
    ar_video = video_w / video_h

    if ar_video > ar_container:
        # Letterbox: black bars top and bottom
        render_w = container_w
        render_h = container_w / ar_video
        offset_x = 0.0
        offset_y = (container_h - render_h) / 2.0
    elif ar_video < ar_container:
        # Pillarbox: black bars left and right
        render_h = container_h
        render_w = container_h * ar_video
        offset_x = (container_w - render_w) / 2.0
        offset_y = 0.0
    else:
        # Exact aspect ratio match
        render_w = container_w
        render_h = container_h
        offset_x = 0.0
        offset_y = 0.0

    return (offset_x, offset_y, render_w, render_h)


def screen_to_normalized(
    screen_x: float,
    screen_y: float,
    container_w: float,
    container_h: float,
    video_w: float,
    video_h: float,
) -> tuple[float, float, bool]:
    """Convert screen container coordinates to normalized [0.0, 1.0] coordinates.

    Returns (norm_x, norm_y, is_inside_video).
    """
    offset_x, offset_y, render_w, render_h = calculate_video_viewport(
        container_w, container_h, video_w, video_h
    )

    is_inside = (
        offset_x <= screen_x <= offset_x + render_w
        and offset_y <= screen_y <= offset_y + render_h
    )

    norm_x = (screen_x - offset_x) / render_w
    norm_y = (screen_y - offset_y) / render_h

    clamped_x = max(0.0, min(1.0, norm_x))
    clamped_y = max(0.0, min(1.0, norm_y))

    return (clamped_x, clamped_y, is_inside)


def normalized_to_screen(
    norm_x: float,
    norm_y: float,
    container_w: float,
    container_h: float,
    video_w: float,
    video_h: float,
) -> tuple[float, float]:
    """Convert normalized [0.0, 1.0] coordinates back to screen container pixels."""
    offset_x, offset_y, render_w, render_h = calculate_video_viewport(
        container_w, container_h, video_w, video_h
    )
    screen_x = offset_x + norm_x * render_w
    screen_y = offset_y + norm_y * render_h
    return (screen_x, screen_y)


def resize_mask(
    x: float,
    y: float,
    w: float,
    h: float,
    handle: str,
    dx: float = 0.0,
    dy: float = 0.0,
    min_size: float = 0.02,
) -> tuple[float, float, float, float]:
    """Calculate new normalized bounding box after dragging one of 8 handles.

    Handles: 'nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'.
    Enforces minimum dimensions and boundary clamping in [0.0, 1.0].
    Prevents box inversion / negative dimensions.
    """
    new_x, new_y, new_w, new_h = x, y, w, h

    # Horizontal adjustments
    if "w" in handle:
        # Left handles: moving left edge
        target_w = w - dx
        if target_w >= min_size:
            potential_x = x + dx
            if potential_x >= 0:
                new_x = potential_x
                new_w = target_w
            else:
                new_x = 0.0
                new_w = x + w
        else:
            new_x = x + w - min_size
            new_w = min_size
    elif "e" in handle:
        # Right handles: moving right edge
        target_w = w + dx
        if target_w >= min_size:
            new_w = min(1.0 - new_x, target_w)
        else:
            new_w = min_size

    # Vertical adjustments
    if "n" in handle:
        # Top handles: moving top edge
        target_h = h - dy
        if target_h >= min_size:
            potential_y = y + dy
            if potential_y >= 0:
                new_y = potential_y
                new_h = target_h
            else:
                new_y = 0.0
                new_h = y + h
        else:
            new_y = y + h - min_size
            new_h = min_size
    elif "s" in handle:
        # Bottom handles: moving bottom edge
        target_h = h + dy
        if target_h >= min_size:
            new_h = min(1.0 - new_y, target_h)
        else:
            new_h = min_size

    # Final sanity clamping
    new_x = max(0.0, min(1.0 - min_size, new_x))
    new_y = max(0.0, min(1.0 - min_size, new_y))
    new_w = max(min_size, min(1.0 - new_x, new_w))
    new_h = max(min_size, min(1.0 - new_y, new_h))

    return (round(new_x, 6), round(new_y, 6), round(new_w, 6), round(new_h, 6))


def translate_mask(
    x: float, y: float, w: float, h: float, dx: float, dy: float
) -> tuple[float, float]:
    """Translate mask by (dx, dy) and clamp strictly inside [0.0, 1.0]."""
    new_x = max(0.0, min(1.0 - w, x + dx))
    new_y = max(0.0, min(1.0 - h, y + dy))
    return (round(new_x, 6), round(new_y, 6))


# ===========================================================================
# 1. Viewport & Aspect Ratio Math Tests
# ===========================================================================

def test_letterbox_calculation():
    """16:9 video in 4:3 container must letterbox (black bars top & bottom)."""
    # 16:9 video (1920x1080) in 800x600 container
    ox, oy, rw, rh = calculate_video_viewport(800, 600, 1920, 1080)
    assert ox == 0.0
    assert rw == 800.0
    assert round(rh, 2) == 450.0  # 800 / (16/9) = 450
    assert round(oy, 2) == 75.0  # (600 - 450) / 2 = 75


def test_pillarbox_calculation():
    """9:16 portrait video in 16:9 container must pillarbox (bars left & right)."""
    # 9:16 vertical video (1080x1920) in 1600x900 container
    ox, oy, rw, rh = calculate_video_viewport(1600, 900, 1080, 1920)
    assert oy == 0.0
    assert rh == 900.0
    expected_w = 900.0 * (9.0 / 16.0)  # 506.25
    assert round(rw, 2) == 506.25
    assert round(ox, 2) == round((1600.0 - 506.25) / 2.0, 2)  # 546.88


def test_perfect_fit_calculation():
    """Exact aspect ratio match results in zero offsets and full fill."""
    ox, oy, rw, rh = calculate_video_viewport(1280, 720, 1920, 1080)
    assert ox == 0.0
    assert oy == 0.0
    assert rw == 1280.0
    assert rh == 720.0


def test_ultrawide_and_square_aspect_ratios():
    """Test 21:9 ultrawide and 1:1 square media in diverse containers."""
    # 21:9 in 16:9 container -> Letterbox
    ox, oy, rw, rh = calculate_video_viewport(1920, 1080, 2560, 1080)
    assert ox == 0.0
    assert rw == 1920.0
    assert rh < 1080.0
    assert oy > 0.0

    # 1:1 in 16:9 container -> Pillarbox
    ox2, oy2, rw2, rh2 = calculate_video_viewport(1920, 1080, 1000, 1000)
    assert oy2 == 0.0
    assert rh2 == 1080.0
    assert rw2 == 1080.0
    assert ox2 == (1920.0 - 1080.0) / 2.0


# ===========================================================================
# 2. Coordinate Transformation & Roundtrip Invariance Tests
# ===========================================================================

def test_screen_to_normalized_inside():
    """Coordinates clicked directly on video map precisely to [0.0, 1.0]."""
    # 16:9 video in 800x600 container (letterbox: oy=75, rh=450)
    # Center click: x=400, y=300
    nx, ny, inside = screen_to_normalized(400, 300, 800, 600, 1920, 1080)
    assert inside is True
    assert nx == 0.5
    assert ny == 0.5


def test_screen_to_normalized_margin_rejection_and_clamping():
    """Clicks in the letterbox/pillarbox margins are detected as outside and clamped."""
    # 16:9 video in 800x600 container (letterbox: bars at y < 75 and y > 525)
    # Click in top black bar: x=400, y=20
    nx, ny, inside = screen_to_normalized(400, 20, 800, 600, 1920, 1080)
    assert inside is False
    assert nx == 0.5
    assert ny == 0.0  # Clamped to top edge of video

    # Click in bottom black bar: x=400, y=580
    nx2, ny2, inside2 = screen_to_normalized(400, 580, 800, 600, 1920, 1080)
    assert inside2 is False
    assert nx2 == 0.5
    assert ny2 == 1.0  # Clamped to bottom edge of video


def test_normalized_roundtrip_quantization_invariance():
    """Transforming norm -> screen -> norm must preserve coordinates within float epsilon."""
    container_w, container_h = 1024, 768
    video_w, video_h = 1920, 1080

    for test_x, test_y in [(0.0, 0.0), (0.25, 0.75), (0.5, 0.5), (0.88, 0.12), (1.0, 1.0)]:
        sx, sy = normalized_to_screen(test_x, test_y, container_w, container_h, video_w, video_h)
        rx, ry, inside = screen_to_normalized(sx, sy, container_w, container_h, video_w, video_h)
        assert inside is True
        assert math.isclose(rx, test_x, abs_tol=1e-5)
        assert math.isclose(ry, test_y, abs_tol=1e-5)


def test_normalized_to_video_pixel_rect():
    """Normalized mask correctly scales to discrete intrinsic video pixels."""
    mask = MaskItem(x=0.10, y=0.80, width=0.80, height=0.15)
    px_x, px_y, px_w, px_h = mask.to_pixel_rect(1920, 1080)
    assert px_x == 192
    assert px_y == 864
    assert px_w == 1536
    assert px_h == 162
    assert px_x + px_w <= 1920
    assert px_y + px_h <= 1080


# ===========================================================================
# 3. 8-Handle Resizing Arithmetic & Anti-Inversion Tests
# ===========================================================================

def test_resize_se_bottom_right():
    """Dragging SE handle increases width and height."""
    # Start at x=0.2, y=0.2, w=0.4, h=0.4
    nx, ny, nw, nh = resize_mask(0.2, 0.2, 0.4, 0.4, "se", dx=0.1, dy=0.1)
    assert nx == 0.2
    assert ny == 0.2
    assert round(nw, 2) == 0.5
    assert round(nh, 2) == 0.5


def test_resize_nw_top_left():
    """Dragging NW handle adjusts origin and reduces/increases dimensions."""
    nx, ny, nw, nh = resize_mask(0.2, 0.2, 0.4, 0.4, "nw", dx=0.05, dy=0.05)
    assert round(nx, 2) == 0.25
    assert round(ny, 2) == 0.25
    assert round(nw, 2) == 0.35
    assert round(nh, 2) == 0.35


def test_resize_anti_inversion_minimum_size():
    """Dragging right handle past left origin prevents inversion and clamps to min size."""
    # Try to drag E handle left by 0.5 (larger than w=0.4)
    nx, ny, nw, nh = resize_mask(0.2, 0.2, 0.4, 0.4, "e", dx=-0.5, min_size=0.05)
    assert nw >= 0.05
    assert nw == 0.05


def test_resize_anti_inversion_top_handle():
    """Dragging N handle down past bottom edge clamps to min size without inversion."""
    nx, ny, nw, nh = resize_mask(0.2, 0.2, 0.4, 0.4, "n", dy=0.6, min_size=0.05)
    assert nh >= 0.05
    assert ny + nh <= 1.0


def test_resize_boundary_clamping():
    """Handles cannot drag edges past [0.0, 1.0] container boundaries."""
    # Drag SE handle beyond right and bottom edges
    nx, ny, nw, nh = resize_mask(0.7, 0.7, 0.2, 0.2, "se", dx=0.5, dy=0.5)
    assert nx + nw <= 1.0
    assert ny + nh <= 1.0


# ===========================================================================
# 4. Translation & Dragging Boundary Tests
# ===========================================================================

def test_translation_inside_boundaries():
    """Normal translation correctly shifts origin."""
    nx, ny = translate_mask(0.2, 0.3, 0.4, 0.2, dx=0.1, dy=0.1)
    assert round(nx, 2) == 0.3
    assert round(ny, 2) == 0.4


def test_translation_clamping_at_edges():
    """Translating mask outside boundaries clamps strictly within [0.0, 1.0]."""
    # Push past top-left
    nx1, ny1 = translate_mask(0.1, 0.1, 0.3, 0.2, dx=-0.5, dy=-0.5)
    assert nx1 == 0.0
    assert ny1 == 0.0

    # Push past bottom-right (must not exceed 1.0 - w, 1.0 - h)
    nx2, ny2 = translate_mask(0.5, 0.5, 0.4, 0.3, dx=0.8, dy=0.8)
    assert round(nx2, 2) == 0.6  # 1.0 - 0.4
    assert round(ny2, 2) == 0.7  # 1.0 - 0.3


# ===========================================================================
# 5. Multi-Mask Layering, Overlaps, and IoU Math Tests
# ===========================================================================

def calculate_iou(
    box1: tuple[float, float, float, float],
    box2: tuple[float, float, float, float],
) -> float:
    """Calculate Intersection over Union (IoU) between two bounding boxes."""
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    xi1 = max(x1, x2)
    yi1 = max(y1, y2)
    xi2 = min(x1 + w1, x2 + w2)
    yi2 = min(y1 + h1, y2 + h2)

    inter_w = max(0.0, xi2 - xi1)
    inter_h = max(0.0, yi2 - yi1)
    intersection = inter_w * inter_h

    area1 = w1 * h1
    area2 = w2 * h2
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0.0


def test_mask_overlap_and_iou():
    """Verify IoU calculation for disjoint, identical, and partially overlapping masks."""
    b1 = (0.1, 0.1, 0.4, 0.4)
    b2 = (0.6, 0.6, 0.3, 0.3)  # Disjoint
    assert calculate_iou(b1, b2) == 0.0

    # Identical
    assert calculate_iou(b1, b1) == 1.0

    # Half overlap along x
    b3 = (0.3, 0.1, 0.4, 0.4)
    iou = calculate_iou(b1, b3)
    assert 0.0 < iou < 1.0
    assert round(iou, 2) == 0.33  # (0.2*0.4) / (0.16 + 0.16 - 0.08) = 0.08/0.24 = 0.333


# ===========================================================================
# 6. FFmpeg Filter Graph Syntax & Delogo Edge Compliance Tests
# ===========================================================================

def test_ffmpeg_erase_delogo_edge_compliance():
    """FFmpeg delogo filter MUST preserve 1-pixel context on all video borders.

    If a user draws a mask spanning to x=0 or w=1.0, the generated delogo filter
    must inset by 1 pixel (x>=1, w<=video_w-2) so FFmpeg's delogo doesn't crash.
    """
    full_span_mask = MaskItem(
        mask_type="erase",
        x=0.0,
        y=0.80,
        width=1.0,
        height=0.20,
    )
    filter_graph = build_ffmpeg_mask_filter([full_span_mask], 1920, 1080)
    assert filter_graph.startswith("delogo=")
    assert "x=1" in filter_graph
    assert "w=1918" in filter_graph  # 1920 - 2 = 1918
    assert "h=215" in filter_graph  # 1080 - 864 - 1 = 215
    assert "show=0" in filter_graph


def test_ffmpeg_boxblur_filter_syntax():
    """Blur type mask generates format=gbrp, boxblur, and blend filter chain."""
    blur_mask = MaskItem(
        mask_type="blur",
        x=0.1,
        y=0.8,
        width=0.8,
        height=0.15,
        blur_strength=25,
    )
    filter_graph = build_ffmpeg_mask_filter([blur_mask], 1920, 1080)
    assert "format=gbrp" in filter_graph
    assert "boxblur=" in filter_graph
    assert "blend=all_expr=" in filter_graph


def test_ffmpeg_solid_drawbox_filter_syntax():
    """Solid color mask generates drawbox with hex color and opacity."""
    solid_mask = MaskItem(
        mask_type="solid",
        x=0.8,
        y=0.05,
        width=0.15,
        height=0.1,
        color="#FF0000",
        opacity=0.85,
    )
    filter_graph = build_ffmpeg_mask_filter([solid_mask], 1920, 1080)
    assert "drawbox=" in filter_graph
    assert "color=0xFF0000@0.85" in filter_graph
    assert "t=fill" in filter_graph


def test_sub_region_is_excluded_from_ffmpeg_filter():
    """`sub_region` masks (used for OCR / subtitle detection) must not blur video."""
    sub_mask = MaskItem(
        mask_type="sub_region",
        x=0.05,
        y=0.75,
        width=0.9,
        height=0.2,
    )
    filter_graph = build_ffmpeg_mask_filter([sub_mask], 1920, 1080)
    assert filter_graph == ""


def test_ffmpeg_timing_expressions():
    """Masks with start_ms and end_ms generate accurate between/gte enable expressions."""
    # 1. Ranged mask
    m_range = MaskItem(
        mask_type="solid",
        start_ms=1500,
        end_ms=4500,
        x=0.1,
        y=0.1,
        width=0.2,
        height=0.2,
    )
    f_range = build_ffmpeg_mask_filter([m_range], 1280, 720)
    assert ":enable='between(t,1.500,4.500)'" in f_range

    # 2. Open-ended mask (start only)
    m_open = MaskItem(
        mask_type="solid",
        start_ms=3000,
        end_ms=0,
        x=0.1,
        y=0.1,
        width=0.2,
        height=0.2,
    )
    f_open = build_ffmpeg_mask_filter([m_open], 1280, 720)
    assert ":enable='gte(t,3.000)'" in f_open


# ===========================================================================
# 7. Mask Validation & Adversarial Inputs
# ===========================================================================

def test_validate_mask_valid():
    """Valid mask returns zero validation errors."""
    valid_mask = MaskItem(
        x=0.1, y=0.2, width=0.5, height=0.3, start_ms=0, end_ms=5000
    )
    errors = validate_mask(valid_mask)
    assert len(errors) == 0


def test_validate_mask_adversarial_coordinates():
    """Out of bound or inverted masks produce specific validation errors."""
    # Out of bounds
    bad_mask = MaskItem()
    bad_mask.x = -0.5
    bad_mask.y = 1.5
    bad_mask.width = 1.5
    bad_mask.height = -0.1
    bad_mask.start_ms = 5000
    bad_mask.end_ms = 2000  # Inverted

    errors = validate_mask(bad_mask)
    assert any("Tọa độ X" in e for e in errors)
    assert any("Tọa độ Y" in e for e in errors)
    assert any("Thời gian kết thúc" in e for e in errors)
