"""Unit tests for KAPPAK Data Studio module."""

from pathlib import Path
from kappak.core.db import db_session, SCHEMA_SQL
from kappak.domain.asset import Asset
from kappak.modules.data_studio.service import (
    get_storage_overview,
    list_assets,
    find_duplicate_assets,
    delete_asset,
    get_project_folder_tree,
)

def setup_test_db(tmp_path: Path):
    db_file = tmp_path / "test_data_studio.db"
    with db_session(db_file) as conn:
        conn.executescript(SCHEMA_SQL)
    return db_file

def test_data_studio_overview_and_collections(tmp_path, monkeypatch):
    test_db = setup_test_db(tmp_path)
    monkeypatch.setattr("kappak.core.db.get_database_path", lambda: test_db)

    # Insert sample assets
    with db_session(test_db) as conn:
        conn.execute(
            """
            INSERT INTO assets (id, name, local_path, platform, duration_sec, file_size, sha256_hash, category, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("a1", "video_one.mp4", str(tmp_path / "video_one.mp4"), "YouTube", 60.0, 1024 * 1024, "hash_aaa", "00_Inbox", "Unused")
        )
        conn.execute(
            """
            INSERT INTO assets (id, name, local_path, platform, duration_sec, file_size, sha256_hash, category, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("a2", "audio_voice.mp3", str(tmp_path / "audio_voice.mp3"), "TikTok", 30.0, 512 * 1024, "hash_bbb", "02_AudioVoice", "InUse")
        )
        conn.execute(
            """
            INSERT INTO assets (id, name, local_path, platform, duration_sec, file_size, sha256_hash, category, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("a3", "video_dup.mp4", str(tmp_path / "video_dup.mp4"), "YouTube", 60.0, 1024 * 1024, "hash_aaa", "00_Inbox", "Unused")
        )

    # 1. Test Overview
    overview = get_storage_overview()
    assert overview.total_assets == 3
    assert overview.total_bytes == (1024 * 1024 * 2) + (512 * 1024)
    assert overview.total_duration_sec == 150.0
    assert overview.duplicate_groups_count == 1
    assert overview.category_breakdown.get("00_Inbox") == 2
    assert overview.platform_breakdown.get("YouTube") == 2

    # 2. Test Smart Collections Filtering
    all_items = list_assets(collection="all")
    assert len(all_items) == 3

    videos = list_assets(collection="video")
    assert len(videos) == 2
    assert all(v["name"].endswith(".mp4") for v in videos)

    audios = list_assets(collection="audio")
    assert len(audios) == 1
    assert audios[0]["name"] == "audio_voice.mp3"

    unused = list_assets(collection="unused")
    assert len(unused) == 2

    # 3. Test Search
    searched = list_assets(search="voice")
    assert len(searched) == 1
    assert searched[0]["id"] == "a2"

    # 4. Test Duplicate Detection
    duplicates = find_duplicate_assets()
    assert len(duplicates) == 1
    assert duplicates[0]["sha256_hash"] == "hash_aaa"
    assert duplicates[0]["count"] == 2
    assert duplicates[0]["wasted_mb"] == 1.0

    # 5. Test Delete Asset
    success = delete_asset("a3")
    assert success is True
    assert len(list_assets(collection="all")) == 2
    assert get_storage_overview().duplicate_groups_count == 0


def test_project_folder_tree(tmp_path):
    proj_dir = tmp_path / "MyProject"
    proj_dir.mkdir()
    (proj_dir / "00_Inbox").mkdir()
    (proj_dir / "00_Inbox" / "clip1.mp4").write_bytes(b"content1")
    (proj_dir / "07_FinalExport").mkdir()
    (proj_dir / "07_FinalExport" / "final.mp4").write_bytes(b"content_final")

    tree = get_project_folder_tree(proj_dir)
    assert tree["exists"] is True
    assert len(tree["tiers"]) == 8

    inbox_tier = next(t for t in tree["tiers"] if t["tier"] == "00_Inbox")
    assert inbox_tier["exists"] is True
    assert inbox_tier["file_count"] == 1
    assert inbox_tier["files"][0]["name"] == "clip1.mp4"

    raw_tier = next(t for t in tree["tiers"] if t["tier"] == "01_RawFootage")
    assert raw_tier["exists"] is False
