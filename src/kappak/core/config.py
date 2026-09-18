"""Configuration and path resolutions for KAPPAK Studio."""

from __future__ import annotations

import os
from pathlib import Path


def get_kappak_home() -> Path:
    """Resolve the local-first root storage for KAPPAK Studio."""
    env_home = os.environ.get("KAPPAK_HOME")
    if env_home:
        path = Path(env_home).resolve()
    else:
        path = Path.home() / ".kappak"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_database_path() -> Path:
    """Return the absolute path to the persistent SQLite database."""
    return get_kappak_home() / "kappak.db"


def get_default_projects_root() -> Path:
    """Return the default projects directory."""
    projects_dir = get_kappak_home() / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    return projects_dir
