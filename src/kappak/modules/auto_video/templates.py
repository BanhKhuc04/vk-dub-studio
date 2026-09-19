"""Visual Layout Templates and FFmpeg Filtergraph generators for 9:16 Vertical Video."""

from __future__ import annotations

from kappak.modules.auto_video.domain import TemplatePreset

# Supported 9:16 Vertical Resolution (Standard 1080x1920)
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
TARGET_FPS = 30


AVAILABLE_TEMPLATES: list[TemplatePreset] = [
    TemplatePreset(
        id="blur_bg",
        name="Cinematic Nền Mờ",
        description="Video gốc căn giữa sắc nét, nền làm mờ chuyển động tự nhiên (chuẩn TikTok/Reels)",
        aspect_ratio="9:16",
        width=TARGET_WIDTH,
        height=TARGET_HEIGHT,
        icon="film",
        features=[
            "Auto Blur Background",
            "Giữ nguyên tỷ lệ gốc",
            "Căn giữa tự động",
            "Phụ đề viền đen",
        ],
    ),
    TemplatePreset(
        id="split_screen",
        name="Màn Hình Kép (Split)",
        description="Chia đôi khung hình dọc 9:16: video tư liệu nửa trên, hiệu ứng/b-roll nửa dưới",
        aspect_ratio="9:16",
        width=TARGET_WIDTH,
        height=TARGET_HEIGHT,
        icon="columns",
        features=[
            "2 khung hình đồng thời",
            "Tối ưu hóa so sánh",
            "Tập trung chú ý cao",
            "Thích hợp reaction/review",
        ],
    ),
    TemplatePreset(
        id="caption_header",
        name="Hook & Headline",
        description="Tiêu đề giật tít cố định trên đỉnh, video ở giữa, phụ đề động phụ đề karaoke ở đáy",
        aspect_ratio="9:16",
        width=TARGET_WIDTH,
        height=TARGET_HEIGHT,
        icon="spark",
        features=[
            "Khung Hook Header nổi bật",
            "Tăng tỷ lệ giữ chân (Retention)",
            "Phụ đề tương phản cao",
            "Chuẩn Viral Shorts",
        ],
    ),
]


def get_template_by_id(template_id: str) -> TemplatePreset:
    """Retrieve template preset by ID or return default."""
    for t in AVAILABLE_TEMPLATES:
        if t.id == template_id:
            return t
    return AVAILABLE_TEMPLATES[0]


def build_template_filtergraph(
    template_id: str,
    input_width: int = 1920,
    input_height: int = 1080,
    target_width: int = TARGET_WIDTH,
    target_height: int = TARGET_HEIGHT,
    hook_text: str = "",
) -> str:
    """Build FFmpeg complex filter string to format input into 9:16 target layout.

    Args:
        template_id: 'blur_bg', 'split_screen', or 'caption_header'
        input_width: Source video width
        input_height: Source video height
        target_width: 1080
        target_height: 1920
        hook_text: Headline text for caption_header template

    Returns:
        FFmpeg filtergraph string for [0:v] -> [outv]
    """
    if template_id == "split_screen":
        # Scale to fit top half 1080x960 with dark pad background
        return (
            f"[0:v]scale={target_width}:{target_height // 2}:force_original_aspect_ratio=decrease,"
            f"pad={target_width}:{target_height // 2}:(ow-iw)/2:(oh-ih)/2:black[top];"
            f"[0:v]scale={target_width}:{target_height // 2}:force_original_aspect_ratio=increase,"
            f"crop={target_width}:{target_height // 2},boxblur=20:5[bottom];"
            f"[top][bottom]vstack[outv]"
        )

    if template_id == "caption_header":
        # Clean blur background + centered video + header hook box
        # Escaping text for drawtext
        clean_text = (
            hook_text.replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")
            if hook_text
            else ""
        )
        text_filter = ""
        if clean_text:
            text_filter = (
                f",drawbox=y=60:color=black@0.65:width=iw:height=160:t=fill,"
                f"drawtext=text='{clean_text}':fontcolor=white:fontsize=48:font='Arial':"
                f"x=(w-text_w)/2:y=110"
            )
        return (
            f"[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=increase,"
            f"crop={target_width}:{target_height},boxblur=25:5[bg];"
            f"[0:v]scale={target_width}:-2:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2{text_filter}[outv]"
        )

    # Default: 'blur_bg'
    return (
        f"[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=increase,"
        f"crop={target_width}:{target_height},boxblur=30:5[bg];"
        f"[0:v]scale={target_width}:-2:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[outv]"
    )
