"""Comprehensive unit and integration tests for KAPPAK Auto Video Generator module."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kappak.core.db import init_db
from kappak.modules.auto_video.domain import AutoVideoProject, SceneSegment
from kappak.modules.auto_video.renderer import generate_ass_subtitles
from kappak.modules.auto_video.service import AutoVideoService
from kappak.modules.auto_video.templates import (
    AVAILABLE_TEMPLATES,
    build_template_filtergraph,
    get_template_by_id,
)
from vkdub.web.server import app


@pytest.fixture(autouse=True)
def setup_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Setup isolated test database for each test."""
    db_file = tmp_path / "test_kappak.db"
    monkeypatch.setenv("KAPPAK_DB_PATH", str(db_file))
    init_db(db_file)
    yield db_file


def test_domain_serialization():
    """Verify SceneSegment and AutoVideoProject serialize and deserialize losslessly."""
    scene = SceneSegment(
        id="scene_1",
        order_index=0,
        text="Xin chào các bạn",
        start_sec=0.0,
        end_sec=3.5,
        duration_sec=3.5,
        transition="fade",
    )
    data = scene.to_dict()
    assert data["id"] == "scene_1"
    assert data["text"] == "Xin chào các bạn"

    restored_scene = SceneSegment.from_dict(data)
    assert restored_scene.id == scene.id
    assert restored_scene.duration_sec == 3.5

    project = AutoVideoProject(
        id="proj_100",
        name="Test Auto Video",
        template_id="split_screen",
        voice_id="vi-VN-NamMinhNeural",
        voice_speed=1.1,
        script_text="Dong 1\nDong 2",
        scenes=[scene],
    )
    proj_dict = project.to_dict()
    assert proj_dict["id"] == "proj_100"
    assert len(proj_dict["scenes"]) == 1

    restored_proj = AutoVideoProject.from_dict(proj_dict)
    assert restored_proj.id == "proj_100"
    assert restored_proj.template_id == "split_screen"
    assert restored_proj.voice_speed == 1.1
    assert len(restored_proj.scenes) == 1
    assert restored_proj.scenes[0].text == "Xin chào các bạn"


def test_template_presets_and_filtergraph():
    """Verify layout templates and FFmpeg filter generation."""
    assert len(AVAILABLE_TEMPLATES) == 3
    t_ids = {t.id for t in AVAILABLE_TEMPLATES}
    assert "blur_bg" in t_ids
    assert "split_screen" in t_ids
    assert "caption_header" in t_ids

    # Test template retrieval
    t1 = get_template_by_id("blur_bg")
    assert t1.id == "blur_bg"
    assert t1.aspect_ratio == "9:16"

    # Test filtergraphs
    fg_blur = build_template_filtergraph("blur_bg", 1920, 1080)
    assert "boxblur=" in fg_blur
    assert "overlay=" in fg_blur

    fg_split = build_template_filtergraph("split_screen", 1920, 1080)
    assert "vstack" in fg_split

    fg_header = build_template_filtergraph("caption_header", 1920, 1080, hook_text="TIEU DE VIRAL")
    assert "drawtext=" in fg_header
    assert "TIEU DE VIRAL" in fg_header


def test_script_parsing_logic():
    """Verify script text correctly breaks into discrete scene segments."""
    svc = AutoVideoService()

    raw_script = """
    1. Đừng bỏ lỡ mẹo tăng tương tác video này!
    2. Sử dụng phụ đề màu sắc bắt mắt và chuyển động nhanh.
    3. Hãy thử nghiệm ngay hôm nay nhé.
    """
    scenes = svc.parse_script_to_scenes(raw_script)
    assert len(scenes) == 3
    assert scenes[0].order_index == 0
    assert "Đừng bỏ lỡ" in scenes[0].text
    assert scenes[0].duration_sec >= 2.0
    assert "Hôm nay" in scenes[2].text or "hôm nay" in scenes[2].text


def test_project_crud_in_database(tmp_path: Path):
    """Verify SQLite persistence for AutoVideoService."""
    svc = AutoVideoService(output_dir=tmp_path)

    proj = svc.create_project(
        name="Dự án Tiktok Top 1",
        template_id="caption_header",
        voice_id="vi-VN-HoaiMyNeural",
        script_text="Câu 1 xuất hiện.\nCâu 2 tiếp nối.",
    )
    assert proj.id is not None
    assert len(proj.scenes) == 2

    # Fetch from db
    fetched = svc.get_project(proj.id)
    assert fetched is not None
    assert fetched.name == "Dự án Tiktok Top 1"
    assert fetched.template_id == "caption_header"
    assert len(fetched.scenes) == 2

    # List projects
    plist = svc.list_projects()
    assert any(p["id"] == proj.id for p in plist)

    # Delete
    ok = svc.delete_project(proj.id)
    assert ok is True
    assert svc.get_project(proj.id) is None


def test_ass_subtitle_generation(tmp_path: Path):
    """Verify ASS subtitle generation formatted for 9:16 mobile canvas."""
    scenes = [
        SceneSegment(id="s1", text="Đây là câu thoại đầu tiên", duration_sec=3.0),
        SceneSegment(id="s2", text="Và đây là câu thoại thứ hai", duration_sec=4.0),
    ]
    out_ass = tmp_path / "test_captions.ass"
    generate_ass_subtitles(scenes, out_ass)

    assert out_ass.is_file()
    content = out_ass.read_text(encoding="utf-8")
    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content
    assert "TikTokStyle" in content
    assert "Đây là câu thoại đầu tiên" in content
    assert "Và đây là câu thoại thứ hai" in content


def test_auto_video_api_endpoints():
    """Verify FastAPI REST endpoints for Auto Video."""
    client = TestClient(app)

    # 1. Templates
    r_tmpl = client.get("/api/auto-video/templates")
    assert r_tmpl.status_code == 200
    assert len(r_tmpl.json()["templates"]) >= 3

    # 2. Assets list
    r_assets = client.get("/api/auto-video/assets")
    assert r_assets.status_code == 200
    assert "assets" in r_assets.json()

    # 3. Parse script
    r_parse = client.post(
        "/api/auto-video/script/parse",
        json={"script_text": "Đoạn 1 thoại.\nĐoạn 2 thoại hay."},
    )
    assert r_parse.status_code == 200
    parsed = r_parse.json()["scenes"]
    assert len(parsed) == 2

    # 4. Create project
    r_create = client.post(
        "/api/auto-video/projects",
        json={
            "name": "API Test Proj",
            "template_id": "blur_bg",
            "voice_id": "vi-VN-HoaiMyNeural",
            "script_text": "Đoạn 1 thoại.\nĐoạn 2 thoại hay.",
            "scenes": parsed,
        },
    )
    assert r_create.status_code == 200
    proj_data = r_create.json()["project"]
    proj_id = proj_data["id"]

    # 5. Get project detail
    r_detail = client.get(f"/api/auto-video/projects/{proj_id}")
    assert r_detail.status_code == 200
    assert r_detail.json()["project"]["name"] == "API Test Proj"

    # 6. List projects
    r_list = client.get("/api/auto-video/projects")
    assert r_list.status_code == 200
    assert any(p["id"] == proj_id for p in r_list.json()["projects"])

    # 7. Delete project
    r_del = client.delete(f"/api/auto-video/projects/{proj_id}")
    assert r_del.status_code == 200
