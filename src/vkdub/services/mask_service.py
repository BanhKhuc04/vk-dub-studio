from vkdub.domain.mask import MaskItem


def hex_to_ffmpeg_color(hex_color: str, opacity: float = 1.0) -> str:
    """Format hex color to FFmpeg color expression, e.g. 'black@0.9' or '0xRRGGBB@0.9'."""
    raw = hex_color.lstrip("#")
    if len(raw) == 6:
        color_str = f"0x{raw}"
    else:
        color_str = "black"
    return f"{color_str}@{opacity:.2f}"


def build_ffmpeg_mask_filter(
    masks: list[MaskItem],
    video_width: int,
    video_height: int,
) -> str:
    """Generate FFmpeg filter chain for all configured masks.

    ``erase`` reconstructs selected pixels from their surroundings with FFmpeg's
    delogo filter. Legacy blur and solid masks retain their saved behavior. Each
    stage has one input/output, so it composes with the subtitle filter.
    """
    filters: list[str] = []
    for index, mask in enumerate(masks):
        if mask.mask_type == "sub_region":
            continue
        px_x, px_y, px_w, px_h = mask.to_pixel_rect(video_width, video_height)

        # Build enable expression
        if mask.start_ms == 0 and mask.end_ms == 0:
            enable_expr = ""
        elif mask.end_ms > 0:
            start_s = mask.start_ms / 1000.0
            end_s = mask.end_ms / 1000.0
            enable_expr = f":enable='between(t,{start_s:.3f},{end_s:.3f})'"
        else:
            start_s = mask.start_ms / 1000.0
            enable_expr = f":enable='gte(t,{start_s:.3f})'"

        if mask.mask_type == "solid":
            color_arg = hex_to_ffmpeg_color(mask.color, mask.opacity)
            filter_item = (
                f"drawbox=x={px_x}:y={px_y}:w={px_w}:h={px_h}:color={color_arg}:t=fill{enable_expr}"
            )
            filters.append(filter_item)
        elif mask.mask_type == "erase":
            # delogo needs one context pixel on every side. Inset edge-touching
            # selections to the largest valid rectangle instead of failing render.
            erase_x = max(1, px_x)
            erase_y = max(1, px_y)
            erase_right = min(video_width - 1, px_x + px_w)
            erase_bottom = min(video_height - 1, px_y + px_h)
            erase_w = erase_right - erase_x
            erase_h = erase_bottom - erase_y
            if erase_w >= 2 and erase_h >= 2:
                filters.append(
                    f"delogo=x={erase_x}:y={erase_y}:w={erase_w}:h={erase_h}:show=0{enable_expr}"
                )
        else:
            radius = max(1, round(mask.blur_strength * video_height / 1080))
            radius = min(radius, max(1, min(video_width, video_height) // 2))
            feather = max(1.0, min(px_w, px_h) * 0.16)
            # RGB planes have equal dimensions. The same smoothstep feather is used
            # in the preview, with zero weight outside the rectangle and at its edge.
            weight = (
                f"clip(min(min(X-{px_x},{px_x + px_w - 1}-X),"
                f"min(Y-{px_y},{px_y + px_h - 1}-Y))/{feather:.4f},0,1)"
            )
            blend = f"st(0,{weight});A+(B-A)*ld(0)*ld(0)*(3-2*ld(0))"
            filter_item = (
                f"format=gbrp,split[vkbase{index}][vkblur{index}];"
                f"[vkblur{index}]boxblur={radius}:3[vksoft{index}];"
                f"[vkbase{index}][vksoft{index}]blend=all_expr='{blend}'{enable_expr}"
            )
            filters.append(filter_item)

    return ",".join(filters)


def validate_mask(mask: MaskItem) -> list[str]:
    """Validate mask configuration and return list of error messages if invalid."""
    errors: list[str] = []
    if not 0.0 <= mask.x <= 1.0:
        errors.append("Tọa độ X phải nằm trong khoảng 0.0 đến 1.0.")
    if not 0.0 <= mask.y <= 1.0:
        errors.append("Tọa độ Y phải nằm trong khoảng 0.0 đến 1.0.")
    if not 0.0 < mask.width <= 1.0:
        errors.append("Chiều rộng phải lớn hơn 0 và tối đa 1.0.")
    if not 0.0 < mask.height <= 1.0:
        errors.append("Chiều cao phải lớn hơn 0 và tối đa 1.0.")
    if mask.x + mask.width > 1.001:
        errors.append("Vùng che vượt quá chiều rộng khung hình.")
    if mask.y + mask.height > 1.001:
        errors.append("Vùng che vượt quá chiều cao khung hình.")
    if mask.end_ms > 0 and mask.end_ms < mask.start_ms:
        errors.append("Thời gian kết thúc không thể nhỏ hơn thời gian bắt đầu.")
    return errors
