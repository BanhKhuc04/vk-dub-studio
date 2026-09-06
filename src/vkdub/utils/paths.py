import os
import sys
from pathlib import Path


def data_root() -> Path:
    if custom := os.environ.get("VKDUB_DATA_DIR"):
        return Path(custom).expanduser().resolve()
    parent = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share")))
    return parent / "VKDubStudio"


def workspace_root() -> Path:
    from vkdub.services.app_settings import load_app_settings

    return Path(load_app_settings().workspace_root).expanduser().resolve()


def resource_path(relative: str | Path) -> Path:
    """Resolve static resource path for development, PyInstaller, and installed environments."""
    rel = Path(relative)
    # 1. PyInstaller temporary extraction directory (onefile or MEIPASS)
    if hasattr(sys, "_MEIPASS"):
        base = Path(getattr(sys, "_MEIPASS"))
        for candidate in (
            base / rel,
            base / "resources" / rel,
            base / "vkdub" / "resources" / rel,
        ):
            if candidate.exists():
                return candidate

    # 2. Next to executable or in app root (onedir distribution)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        for candidate in (
            exe_dir / rel,
            exe_dir / "resources" / rel,
            exe_dir / "_internal" / rel,
            exe_dir / "_internal" / "resources" / rel,
        ):
            if candidate.exists():
                return candidate

    # 3. Development workspace root
    repo_root = Path(__file__).resolve().parents[3]
    for candidate in (
        repo_root / "resources" / rel,
        repo_root / rel,
        repo_root / "src" / "vkdub" / "resources" / rel,
    ):
        if candidate.exists():
            return candidate

    return repo_root / "resources" / rel
