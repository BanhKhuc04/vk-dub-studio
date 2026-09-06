import json
from datetime import UTC, datetime
from pathlib import Path

from vkdub.domain.project import Project
from vkdub.services.project_service import load_project, save_project
from vkdub.utils.paths import data_root

RECOVERY_FILENAME = "recovery_state.vkdub"
META_FILENAME = "recovery_meta.json"


def get_recovery_dir() -> Path:
    """Return the directory path for autosave/recovery files."""
    path = data_root() / "recovery"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_recovery_state(project: Project, original_save_path: Path | None = None) -> Path:
    """Autosave the current project state to the recovery directory."""
    rec_dir = get_recovery_dir()
    rec_file = rec_dir / RECOVERY_FILENAME
    meta_file = rec_dir / META_FILENAME

    save_project(project, rec_file)

    meta = {
        "timestamp": datetime.now(UTC).isoformat(),
        "video_name": project.video_path.name if project.video_path else "Không có video",
        "original_save_path": str(original_save_path.resolve()) if original_save_path else None,
        "script_lines": len(project.script.lines) if project.script else 0,
        "is_approved": project.is_approved,
    }
    meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return rec_file


def has_recovery_state() -> bool:
    """Return True if a valid recovery file exists."""
    rec_dir = get_recovery_dir()
    rec_file = rec_dir / RECOVERY_FILENAME
    return rec_file.is_file() and rec_file.stat().st_size > 0


def load_recovery_state() -> tuple[Project, dict] | None:
    """Load the recovered project and its metadata."""
    rec_dir = get_recovery_dir()
    rec_file = rec_dir / RECOVERY_FILENAME
    meta_file = rec_dir / META_FILENAME

    if not rec_file.is_file():
        return None

    try:
        project = load_project(rec_file)
        meta = {}
        if meta_file.is_file():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return project, meta
    except Exception:
        return None


def clear_recovery_state() -> None:
    """Clear recovery files after safe save or explicit user dismissal."""
    rec_dir = get_recovery_dir()
    for fname in (RECOVERY_FILENAME, META_FILENAME):
        p = rec_dir / fname
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
