"""ChatGPT Translation Bridge for VK Dub Studio.

Prepares transcription SRT files, copies context-aware translation prompts to
the system clipboard, launches ChatGPT in the user's default browser (inheriting
their existing authenticated profile), and imports translated SRT files.
"""

from __future__ import annotations

import logging
import os
import subprocess
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

from vkdub.domain.script import ScriptDocument
from vkdub.services.srt_service import parse_srt, write_srt
from vkdub.utils.paths import workspace_root

if TYPE_CHECKING:
    from vkdub.domain.project import Project

logger = logging.getLogger("vkdub.chatgpt")

CHATGPT_URL = "https://chatgpt.com"

CHATGPT_PROMPT_TEMPLATE = (
    "Dịch lại toàn bộ file phụ đề SRT này sang tiếng Việt:\n"
    "- Sát nghĩa, đúng bối cảnh và cảm xúc nhân vật, văn phong tự nhiên.\n"
    "- Giữ nguyên 100% định dạng SRT, số thứ tự từng câu và mốc thời gian (timecode).\n"
    "- Không gộp câu, không tách câu, không bỏ sót bất kỳ dòng nào.\n\n"
    "--- NỘI DUNG PHỤ ĐỀ SRT GỐC ---\n"
    "{content}\n"
    "--- HẾT ---"
)


def export_original_srt(project: Project, output_dir: Path | None = None) -> Path:
    """Export the current transcribed script or draft to an SRT file."""
    target_dir = output_dir or (workspace_root() / "export")
    target_dir.mkdir(parents=True, exist_ok=True)

    base_name = "vid_goc"
    if project.video_path:
        base_name = project.video_path.stem

    srt_path = target_dir / f"{base_name}.srt"

    if project.script and project.script.lines:
        write_srt(srt_path, project.script, project.duration_ms)
    elif project.transcript and project.transcript.segments:
        # Build script from transcript segments directly
        lines = []
        for seg in project.transcript.segments:
            start_ms = (
                int(seg.start * 1000) if hasattr(seg, "start") else getattr(seg, "start_ms", 0)
            )
            end_ms = int(seg.end * 1000) if hasattr(seg, "end") else getattr(seg, "end_ms", 0)
            lines.append(
                f"{seg.id}\n{_format_time(start_ms)} --> {_format_time(end_ms)}\n{seg.text}\n"
            )
        srt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        raise ValueError("Chưa có bản bóc băng phụ đề gốc để xuất SRT.")

    logger.info("Đã xuất file SRT gốc cho ChatGPT: %s", srt_path)
    return srt_path


def copy_to_clipboard(text: str) -> bool:
    """Copy text to Windows clipboard using PySide6 or PowerShell fallback."""
    try:
        from PySide6.QtGui import QGuiApplication

        cb = QGuiApplication.clipboard()
        if cb:
            cb.setText(text)
            return True
    except Exception:
        pass

    if os.name == "nt":
        try:
            # Use PowerShell clip command fallback
            proc = subprocess.Popen(
                ["clip"],
                stdin=subprocess.PIPE,
                creationflags=0x08000000,
            )
            proc.communicate(input=text.encode("utf-16le"))
            return proc.returncode == 0
        except Exception as exc:
            logger.debug("Clipboard fallback failed: %s", exc)
    return False


def open_chatgpt_in_default_browser() -> bool:
    """Open ChatGPT in user's default browser (inherits logged-in company session)."""
    try:
        if os.name == "nt":
            os.startfile(CHATGPT_URL)  # type: ignore[attr-defined]
            return True
    except Exception:
        pass

    try:
        return webbrowser.open(CHATGPT_URL)
    except Exception as exc:
        logger.error("Không thể mở trình duyệt: %s", exc)
        return False


def reveal_in_explorer(file_path: Path) -> None:
    """Highlight the file in Windows Explorer for easy drag-and-drop into ChatGPT."""
    if os.name == "nt" and file_path.is_file():
        try:
            subprocess.Popen(
                ["explorer", f"/select,{file_path}"],
                creationflags=0x08000000,
            )
        except Exception as exc:
            logger.debug("Could not reveal file in Explorer: %s", exc)


def prepare_chatgpt_translation(project: Project) -> tuple[Path, str]:
    """Export original SRT, copy prompt to clipboard, and open ChatGPT in default browser.

    Returns:
        tuple of (exported_srt_path, prompt_text)
    """
    srt_path = export_original_srt(project)
    content = srt_path.read_text(encoding="utf-8", errors="replace")
    prompt = CHATGPT_PROMPT_TEMPLATE.format(content=content)

    # Copy to clipboard
    copy_to_clipboard(prompt)

    # Open ChatGPT in user's default browser
    open_chatgpt_in_default_browser()

    # Reveal in Explorer for easy drag-and-drop
    reveal_in_explorer(srt_path)

    return srt_path, prompt


def import_translated_srt(
    project: Project,
    source: str | Path,
) -> ScriptDocument:
    """Parse translated SRT content or file, and attach it to the project script.

    Args:
        project: Target Project instance.
        source: File Path or raw SRT string content.

    Returns:
        Updated ScriptDocument instance.
    """
    if isinstance(source, Path):
        if not source.is_file():
            raise FileNotFoundError(f"Không tìm thấy file phụ đề: {source}")
        raw_text = source.read_text(encoding="utf-8", errors="replace")
    else:
        raw_text = str(source)

    script_doc = parse_srt(raw_text)
    if not script_doc.lines:
        raise ValueError("Nội dung SRT không hợp lệ hoặc không có câu phụ đề nào.")

    project.script = script_doc
    project.approved_revision_hash = None
    project.target_language = "vi"

    logger.info("Đã nạp thành công %d câu phụ đề dịch từ ChatGPT.", len(script_doc.lines))
    return script_doc


def _format_time(ms: int) -> str:
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    seconds = (ms % 60000) // 1000
    msec = ms % 1000
    return f"{hours:02}:{minutes:02}:{seconds:02},{msec:03}"
