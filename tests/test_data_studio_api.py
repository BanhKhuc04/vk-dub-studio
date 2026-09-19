"""Integration tests for Data Studio Web API endpoints."""

from fastapi.testclient import TestClient
from vkdub.web.server import app
from kappak.core.db import db_session, SCHEMA_SQL

def test_data_studio_api_endpoints(tmp_path, monkeypatch):
    test_db = tmp_path / "test_api_studio.db"
    with db_session(test_db) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            """
            INSERT INTO assets (id, name, local_path, platform, duration_sec, file_size, sha256_hash, category, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("asset_1", "test_video.mp4", str(tmp_path / "test_video.mp4"), "YouTube", 45.0, 2048, "hash_123", "00_Inbox", "Unused")
        )
        conn.execute(
            """
            INSERT INTO assets (id, name, local_path, platform, duration_sec, file_size, sha256_hash, category, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("asset_2", "test_dup.mp4", str(tmp_path / "test_dup.mp4"), "TikTok", 45.0, 2048, "hash_123", "00_Inbox", "Unused")
        )

    monkeypatch.setattr("kappak.core.db.get_database_path", lambda: test_db)
    client = TestClient(app)

    # 1. Overview
    res_ov = client.get("/api/data-studio/overview")
    assert res_ov.status_code == 200
    data_ov = res_ov.json()
    assert data_ov["total_assets"] == 2
    assert data_ov["duplicate_groups_count"] == 1

    # 2. Assets list
    res_assets = client.get("/api/data-studio/assets?collection=video")
    assert res_assets.status_code == 200
    data_assets = res_assets.json()
    assert data_assets["count"] == 2

    # 3. Duplicates
    res_dup = client.get("/api/data-studio/duplicates")
    assert res_dup.status_code == 200
    data_dup = res_dup.json()
    assert data_dup["groups_count"] == 1
    assert data_dup["duplicates"][0]["sha256_hash"] == "hash_123"

    # 4. Folder tree
    res_tree = client.get("/api/data-studio/folder-tree")
    assert res_tree.status_code == 200
    assert "tiers" in res_tree.json()

    # 5. Delete asset
    res_del = client.post("/api/data-studio/assets/delete", json={"asset_id": "asset_2", "delete_file": False})
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "ok"

    # Verify deleted
    res_ov2 = client.get("/api/data-studio/overview")
    assert res_ov2.json()["total_assets"] == 1
