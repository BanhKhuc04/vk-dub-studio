from dataclasses import asdict, dataclass
from typing import Any

from vkdub.domain.script import ScriptDocument

SUBTITLE_REFERENCE_WIDTH = 1920
SUBTITLE_REFERENCE_HEIGHT = 1080


def color_to_ass(hex_color: str, alpha: float = 1.0) -> str:
    """Convert hex color (#RRGGBB or #AARRGGBB) to ASS color format (&HAABBGGRR)."""
    raw = hex_color.lstrip("#")
    if len(raw) == 6:
        r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
        a_int = round((1.0 - max(0.0, min(1.0, alpha))) * 255)
    elif len(raw) == 8:
        a_int = int(raw[0:2], 16)
        r, g, b = int(raw[2:4], 16), int(raw[4:6], 16), int(raw[6:8], 16)
    else:
        r, g, b, a_int = 255, 255, 255, 0
    return f"&H{a_int:02X}{b:02X}{g:02X}{r:02X}"


def format_ass_time(ms: int) -> str:
    """Format milliseconds to ASS timestamp H:MM:SS.cs (centiseconds)."""
    total_cs = max(0, ms) // 10
    cs = total_cs % 100
    total_seconds = total_cs // 100
    s = total_seconds % 60
    total_minutes = total_seconds // 60
    m = total_minutes % 60
    h = total_minutes // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


@dataclass(frozen=True)
class SubtitleStyle:
    name: str = "YouTube"
    font_family: str = "Arial"
    font_size: int = 42
    bold: bool = True
    italic: bool = False
    text_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    outline_width: float = 3.0
    shadow_offset: float = 1.5
    shadow_color: str = "#000000"
    background_box: bool = False
    background_color: str = "#000000"
    background_opacity: float = 0.5
    alignment: int = 2  # 2: bottom center
    margin_bottom: int = 50
    margin_horizontal: int = 30
    max_width_ratio: float = 0.85
    line_spacing: float = 1.1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubtitleStyle":
        valid_keys = {f for f in cls.__annotations__}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    def to_ass_style_line(self) -> str:
        """Format V4+ Style line for ASS header."""
        primary = color_to_ass(self.text_color, 1.0)
        secondary = "&H000000FF"
        outline = color_to_ass(self.outline_color, 1.0)
        back = color_to_ass(
            self.background_color if self.background_box else self.shadow_color,
            self.background_opacity if self.background_box else 0.5,
        )
        bold_val = -1 if self.bold else 0
        italic_val = -1 if self.italic else 0
        border_style = 3 if self.background_box else 1  # 3 = opaque box, 1 = outline + shadow
        return (
            f"Style: Default,{self.font_family},{self.font_size},{primary},{secondary},"
            f"{outline},{back},{bold_val},{italic_val},0,0,100,100,0,0,{border_style},"
            f"{self.outline_width},{self.shadow_offset},{self.alignment},"
            f"{self.margin_horizontal},{self.margin_horizontal},{self.margin_bottom},1"
        )


PRESETS: dict[str, SubtitleStyle] = {
    "Minimal": SubtitleStyle(
        name="Minimal",
        font_family="Arial",
        font_size=36,
        bold=False,
        italic=False,
        text_color="#FFFFFF",
        outline_color="#000000",
        outline_width=1.5,
        shadow_offset=0.0,
        background_box=False,
        margin_bottom=40,
    ),
    "YouTube": SubtitleStyle(
        name="YouTube",
        font_family="Arial",
        font_size=42,
        bold=True,
        italic=False,
        text_color="#FFFFFF",
        outline_color="#000000",
        outline_width=3.0,
        shadow_offset=1.5,
        background_box=False,
        margin_bottom=50,
    ),
    "TikTok": SubtitleStyle(
        name="TikTok",
        font_family="Arial",
        font_size=48,
        bold=True,
        italic=False,
        text_color="#FFE600",
        outline_color="#000000",
        outline_width=4.0,
        shadow_offset=2.0,
        background_box=False,
        margin_bottom=180,
    ),
    "Movie": SubtitleStyle(
        name="Movie",
        font_family="Times New Roman",
        font_size=38,
        bold=False,
        italic=False,
        text_color="#FEEB75",
        outline_color="#000000",
        outline_width=2.0,
        shadow_offset=1.5,
        background_box=False,
        margin_bottom=45,
    ),
    "Bold Caption": SubtitleStyle(
        name="Bold Caption",
        font_family="Arial",
        font_size=40,
        bold=True,
        italic=False,
        text_color="#FFFFFF",
        outline_color="#000000",
        outline_width=0.0,
        shadow_offset=0.0,
        background_box=True,
        background_color="#000000",
        background_opacity=0.6,
        margin_bottom=50,
    ),
}


def to_ass_script(
    script: ScriptDocument,
    style: SubtitleStyle,
    video_width: int = 1920,
    video_height: int = 1080,
) -> str:
    """Generate complete ASS subtitle content from a ScriptDocument and SubtitleStyle."""
    w = max(320, video_width)
    h = max(240, video_height)
    header = (
        "[Script Info]\n"
        "Title: VK Dub Studio Subtitles\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        f"PlayResX: {w}\n"
        f"PlayResY: {h}\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"{style.to_ass_style_line()}\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    dialogue_lines: list[str] = []
    for line in script.lines:
        text = line.text.strip().replace("\r\n", "\n").replace("\n", r"\N")
        if not text:
            continue
        start_str = format_ass_time(line.start_ms)
        end_str = format_ass_time(line.end_ms)
        dialogue_lines.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}")

    return header + "\n".join(dialogue_lines) + "\n"
