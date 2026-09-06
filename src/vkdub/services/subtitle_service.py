import json
from pathlib import Path

from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument
from vkdub.domain.subtitle import PRESETS, SubtitleStyle, to_ass_script
from vkdub.services.srt_service import write_srt


def load_presets() -> dict[str, SubtitleStyle]:
    """Load subtitle style presets from resources or fallback to built-in presets."""
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    preset_file = root_dir / "resources" / "subtitle_presets.json"
    if preset_file.is_file():
        try:
            data = json.loads(preset_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "presets" in data:
                return {p["name"]: SubtitleStyle.from_dict(p) for p in data["presets"]}
        except Exception:
            pass
    return dict(PRESETS)


def export_srt(project: Project, path: Path) -> None:
    """Export current approved/draft script to an SRT file."""
    if project.script is None or not project.script.lines:
        raise ValueError("Chưa có kịch bản để xuất phụ đề SRT.")
    write_srt(path, project.script, project.video_duration_ms)


def export_ass(
    project: Project,
    path: Path,
    style: SubtitleStyle | None = None,
) -> None:
    """Export ASS on the same 1080p reference canvas used by the live preview."""
    if project.script is None or not project.script.lines:
        raise ValueError("Chưa có kịch bản để xuất phụ đề ASS.")
    chosen_style = style or project.subtitle_style
    content = to_ass_script(project.script, chosen_style)
    path.write_text(content, encoding="utf-8-sig")


def subtitle_for_time(script: ScriptDocument | None, time_ms: int) -> str | None:
    """Find the active subtitle text at the given timestamp in milliseconds."""
    if script is None or not script.lines:
        return None
    for line in script.lines:
        if line.start_ms <= time_ms <= line.end_ms:
            return line.text.strip()
    return None
