"""SQLite database engine for KAPPAK Studio with WAL mode and robust schema migrations."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Generator
from pathlib import Path

from kappak.core.config import get_database_path


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Create and configure a SQLite connection optimized for local concurrent access."""
    target_path = db_path or get_database_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(target_path),
        timeout=30.0,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    )
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high performance & safe concurrency on single-user local disk
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextlib.contextmanager
def db_session(db_path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for automatic commit and rollback."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    root_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    name TEXT NOT NULL,
    local_path TEXT NOT NULL,
    source_url TEXT DEFAULT '',
    platform TEXT DEFAULT '',
    creator TEXT DEFAULT '',
    duration_sec REAL DEFAULT 0,
    resolution TEXT DEFAULT '',
    file_size INTEGER DEFAULT 0,
    sha256_hash TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    category TEXT DEFAULT '00_Inbox',
    status TEXT DEFAULT 'Unused',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    target_id TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'QUEUED',
    progress_pct REAL DEFAULT 0,
    message TEXT DEFAULT '',
    payload_json TEXT DEFAULT '{}',
    result_json TEXT DEFAULT '{}',
    error TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    title TEXT NOT NULL,
    caption TEXT DEFAULT '',
    platforms TEXT DEFAULT '',
    asset_ids TEXT DEFAULT '[]',
    status TEXT DEFAULT 'Draft',
    scheduled_at TIMESTAMP,
    published_at TIMESTAMP,
    post_url TEXT DEFAULT '',
    error TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    title TEXT NOT NULL,
    notes TEXT DEFAULT '',
    due_date TIMESTAMP,
    priority TEXT DEFAULT 'Medium',
    status TEXT DEFAULT 'Todo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS auto_video_projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    project_id TEXT,
    template_id TEXT DEFAULT 'blur_bg',
    voice_id TEXT DEFAULT 'vi-VN-HoaiMyNeural',
    voice_speed REAL DEFAULT 1.0,
    bgm_asset_id TEXT,
    bgm_volume REAL DEFAULT 0.15,
    script_text TEXT DEFAULT '',
    scenes_json TEXT DEFAULT '[]',
    status TEXT DEFAULT 'DRAFT',
    progress_pct REAL DEFAULT 0,
    output_video_path TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id);
CREATE INDEX IF NOT EXISTS idx_assets_hash ON assets(sha256_hash);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_auto_video_status ON auto_video_projects(status);
"""


def init_db(db_path: Path | None = None) -> None:
    """Initialize database schema."""
    with db_session(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
