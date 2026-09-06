import os
from pathlib import Path


def data_root() -> Path:
    if custom := os.environ.get("VKDUB_DATA_DIR"):
        return Path(custom).expanduser().resolve()
    parent = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share")))
    return parent / "VKDubStudio"


def workspace_root() -> Path:
    from vkdub.services.app_settings import load_app_settings

    return Path(load_app_settings().workspace_root).expanduser().resolve()
