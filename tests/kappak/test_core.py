"""Tests for KAPPAK Studio core architecture (Database, Job Manager, Project, Asset)."""

import tempfile
import time
from pathlib import Path

from kappak.core.db import get_connection, init_db
from kappak.domain.asset import Asset, calculate_sha256
from kappak.domain.job import JobStatus
from kappak.domain.project import Project, STANDARD_PROJECT_FOLDERS
from kappak.jobs.manager import LocalJobManager


def test_sqlite_wal_init():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test_kappak.db"
        init_db(db_path)
        assert db_path.is_file()

        conn = get_connection(db_path)
        cur = conn.execute("PRAGMA journal_mode;")
        row = cur.fetchone()
        assert row[0].lower() == "wal"
        conn.close()


def test_project_8_tier_folder_creation():
    with tempfile.TemporaryDirectory() as tmp:
        base_dir = Path(tmp)
        proj = Project.create("Alpha Channel", base_dir, description="Kenh truyen thong")
        assert proj.root_path.is_dir()

        for folder in STANDARD_PROJECT_FOLDERS:
            p = proj.root_path / folder
            assert p.is_dir(), f"Folder {folder} missing from project structure"


def test_asset_deduplication_hash():
    with tempfile.TemporaryDirectory() as tmp:
        file_path = Path(tmp) / "sample_video.mp4"
        file_path.write_bytes(b"kappak_media_content_sample_12345")

        asset = Asset(name="Sample", local_path=file_path)
        asset.refresh_file_metadata()

        assert asset.file_size == len(b"kappak_media_content_sample_12345")
        assert len(asset.sha256_hash) == 64


def test_local_job_manager_execution():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "jobs.db"
        init_db(db_path)

        manager = LocalJobManager(db_path=db_path, max_workers=2)

        def mock_handler(job, progress_cb):
            progress_cb(50.0, "Dang xu ly...")
            time.sleep(0.05)
            return {"output_file": "final.mp4"}

        job = manager.submit("TEST_TASK", {"key": "val"}, mock_handler)
        assert job.status in (JobStatus.QUEUED, JobStatus.RUNNING)

        time.sleep(0.2)
        finished = manager.get_job(job.id)
        assert finished is not None
        assert finished.status == JobStatus.SUCCESS
        assert finished.progress_pct == 100.0
        assert finished.result == {"output_file": "final.mp4"}

        manager.shutdown(wait=True)
