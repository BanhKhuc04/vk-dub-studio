import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from fastapi.testclient import TestClient
from vkdub.web.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_downloader_inspect_empty_url(client):
    res = client.post("/api/downloader/inspect", json={"url": ""})
    assert res.status_code == 400
    assert "Vui lòng nhập đường link" in res.json()["detail"]


@patch("kappak.modules.downloader.service.fetch_video_metadata")
def test_downloader_inspect_success(mock_fetch, client):
    from kappak.modules.downloader.service import VideoMetadata
    mock_fetch.return_value = VideoMetadata(
        url="https://www.tiktok.com/@test/video/123",
        title="Tiêu đề thử nghiệm",
        creator="Tác giả A",
        duration_sec=30.0,
        duration_str="00:30",
        thumbnail_url="https://example.com/thumb.jpg",
        platform="TikTok",
        formats=["1080p", "720p", "MP3"],
        description="Mô tả video",
    )

    res = client.post("/api/downloader/inspect", json={"url": "https://www.tiktok.com/@test/video/123"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["metadata"]["title"] == "Tiêu đề thử nghiệm"
    assert data["metadata"]["platform"] == "TikTok"
    assert data["metadata"]["duration_str"] == "00:30"


@patch("kappak.modules.downloader.service.download_media")
def test_downloader_download_success(mock_dl, client, tmp_path):
    from kappak.domain.asset import Asset
    sample_file = tmp_path / "sample.mp4"
    sample_file.write_bytes(b"DATA")

    mock_dl.return_value = Asset(
        id="asset_123",
        name="sample.mp4",
        local_path=sample_file,
        project_id=None,
        source_url="https://www.tiktok.com/@test/video/123",
        platform="TikTok",
        creator="Tác giả A",
        duration_sec=15.0,
        resolution="1080x1920",
        file_size=1024,
        sha256_hash="abcdef1234567890",
        category="00_Inbox",
        status="Unused",
    )

    res = client.post("/api/downloader/download", json={"url": "https://www.tiktok.com/@test/video/123", "quality": "best"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["asset"]["id"] == "asset_123"
    assert data["asset"]["sha256_hash"] == "abcdef1234567890"


def test_downloader_history(client):
    res = client.get("/api/downloader/history")
    assert res.status_code == 200
    data = res.json()
    assert "assets" in data
    assert isinstance(data["assets"], list)


def test_projects_recent(client):
    res = client.get("/api/projects/recent")
    assert res.status_code == 200
    data = res.json()
    assert "projects" in data
    assert isinstance(data["projects"], list)


def test_projects_load_missing_path(client):
    res = client.post("/api/projects/load", json={})
    assert res.status_code == 400

