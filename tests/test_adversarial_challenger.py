"""Adversarial Challenger Test Suite for KAPPAK Studio Web v2.

Subagent: teamwork_preview_challenger_m3_1
Milestone 3: Adversarial Verification

Covers:
1. Coordinate math stress testing:
   - 9:16 vertical (Shorts/TikTok), 21:9 ultrawide, 1:1 square, 32:9 extreme ultrawide
   - Boundary clamping, margin rejection, sub-pixel roundtrip invariance
   - 8-handle resizing arithmetic anti-inversion and boundary clamping
   - Delogo 1-px context border requirement and tiny area filtering
2. API contract probing:
   - Negative coordinates, out-of-bounds floats, malformed payloads on /api/masks
   - Voice preview invalid voice ID, empty sample text, directory traversal defense
   - Pipeline cancel idempotency while idle
   - Export calls before approval or without voice audio
   - Settings adversarial payloads (string parsing fallback vs Pydantic 422)
3. Production bundle and static assets:
   - dist/index.html existence, title, favicon link
   - GET /, /index.html, /logo.png, /api/logo, /favicon.png, /assets bundle serving
   - run_app.bat sanity verification
"""

import os
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from vkdub.domain.mask import MaskItem
from vkdub.domain.project import Project
from vkdub.services.mask_service import build_ffmpeg_mask_filter, validate_mask
from vkdub.web.server import app, state
from tests.test_e2e_blur_math import (
    calculate_video_viewport,
    screen_to_normalized,
    normalized_to_screen,
    resize_mask,
)


@pytest.fixture(autouse=True)
def reset_server_state():
    """Ensure state isolation before and after every API test."""
    original_project = state.project
    original_metadata = state.video_metadata
    original_subtitles = list(state.subtitles)
    original_approved = state.approved_script

    state.project = Project()
    state.video_metadata = None
    state.subtitles = []
    state.approved_script = False
    state.overall_pct = 0
    state.overall_msg = "Sẵn sàng"
    state.logs.clear()

    yield

    state.project = original_project
    state.video_metadata = original_metadata
    state.subtitles = original_subtitles
    state.approved_script = original_approved


@pytest.fixture
def client():
    return TestClient(app)


# ===========================================================================
# 1. Coordinate Math Stress-Testing
# ===========================================================================

def test_coordinate_math_vertical_shorts_tiktok():
    """Stress test 9:16 vertical video inside various container dimensions."""
    # 1. 9:16 video (1080x1920) inside 16:9 desktop container (1920x1080)
    # Container is much wider -> Pillarbox (huge black bars left and right)
    off_x, off_y, rend_w, rend_h = calculate_video_viewport(
        container_w=1920, container_h=1080, video_w=1080, video_h=1920
    )
    assert off_y == 0.0
    assert rend_h == 1080.0
    expected_w = 1080.0 * (1080.0 / 1920.0)  # 607.5
    assert pytest.approx(rend_w, 0.01) == expected_w
    expected_off_x = (1920.0 - expected_w) / 2.0  # 656.25
    assert pytest.approx(off_x, 0.01) == expected_off_x

    # 2. 9:16 video (1080x1920) inside a tall mobile container (360x780, AR ~ 0.4615 < 0.5625)
    # Container is taller than video -> Letterbox (bars top and bottom)
    off_x2, off_y2, rend_w2, rend_h2 = calculate_video_viewport(
        container_w=360, container_h=780, video_w=1080, video_h=1920
    )
    assert off_x2 == 0.0
    assert rend_w2 == 360.0
    expected_h = 360.0 / (1080.0 / 1920.0)  # 640.0
    assert pytest.approx(rend_h2, 0.01) == expected_h
    expected_off_y = (780.0 - 640.0) / 2.0  # 70.0
    assert pytest.approx(off_y2, 0.01) == expected_off_y

    # 3. Exact 9:16 container match (1080x1920)
    off_x3, off_y3, rend_w3, rend_h3 = calculate_video_viewport(
        container_w=1080, container_h=1920, video_w=1080, video_h=1920
    )
    assert off_x3 == 0.0 and off_y3 == 0.0
    assert rend_w3 == 1080.0 and rend_h3 == 1920.0


def test_coordinate_math_ultrawide_21_9_and_extreme_32_9():
    """Stress test 21:9 ultrawide and 32:9 extreme ultrawide inside standard containers."""
    # 21:9 video (2560x1080) inside 1920x1080 container -> Letterbox (bars top/bottom)
    off_x, off_y, rend_w, rend_h = calculate_video_viewport(
        container_w=1920, container_h=1080, video_w=2560, video_h=1080
    )
    assert off_x == 0.0
    assert rend_w == 1920.0
    expected_h = 1920.0 / (2560.0 / 1080.0)  # 810.0
    assert pytest.approx(rend_h, 0.01) == expected_h
    assert pytest.approx(off_y, 0.01) == (1080.0 - 810.0) / 2.0  # 135.0

    # 32:9 extreme ultrawide (5120x1440) inside 1920x1080 container -> Letterbox
    off_x2, off_y2, rend_w2, rend_h2 = calculate_video_viewport(
        container_w=1920, container_h=1080, video_w=5120, video_h=1440
    )
    assert off_x2 == 0.0
    assert rend_w2 == 1920.0
    expected_h2 = 1920.0 / (5120.0 / 1440.0)  # 540.0
    assert pytest.approx(rend_h2, 0.01) == expected_h2
    assert pytest.approx(off_y2, 0.01) == (1080.0 - 540.0) / 2.0  # 270.0


def test_coordinate_math_square_1_1():
    """Stress test 1:1 square video inside landscape and portrait containers."""
    # 1:1 square inside 1920x1080 landscape container -> Pillarbox
    off_x, off_y, rend_w, rend_h = calculate_video_viewport(
        container_w=1920, container_h=1080, video_w=1080, video_h=1080
    )
    assert off_y == 0.0
    assert rend_h == 1080.0
    assert rend_w == 1080.0
    assert off_x == (1920.0 - 1080.0) / 2.0  # 420.0

    # 1:1 square inside 800x1200 portrait container -> Letterbox
    off_x2, off_y2, rend_w2, rend_h2 = calculate_video_viewport(
        container_w=800, container_h=1200, video_w=1080, video_h=1080
    )
    assert off_x2 == 0.0
    assert rend_w2 == 800.0
    assert rend_h2 == 800.0
    assert off_y2 == (1200.0 - 800.0) / 2.0  # 200.0


def test_screen_to_normalized_adversarial_boundaries():
    """Test screen to normalized conversion under extreme adversarial boundary conditions."""
    # 9:16 video in 1920x1080 container: render box is x: [656.25, 1263.75], y: [0, 1080]
    cw, ch, vw, vh = 1920.0, 1080.0, 1080.0, 1920.0

    # 1. Far negative screen coordinates
    nx, ny, inside = screen_to_normalized(-500.0, -200.0, cw, ch, vw, vh)
    assert nx == 0.0
    assert ny == 0.0
    assert inside is False

    # 2. Far positive screen coordinates
    nx, ny, inside = screen_to_normalized(5000.0, 3000.0, cw, ch, vw, vh)
    assert nx == 1.0
    assert ny == 1.0
    assert inside is False

    # 3. Inside left pillarbox margin (screen_x = 100, inside margin)
    nx, ny, inside = screen_to_normalized(100.0, 500.0, cw, ch, vw, vh)
    assert nx == 0.0  # Clamped to 0.0
    assert inside is False

    # 4. Inside right pillarbox margin (screen_x = 1800, inside margin)
    nx, ny, inside = screen_to_normalized(1800.0, 500.0, cw, ch, vw, vh)
    assert nx == 1.0  # Clamped to 1.0
    assert inside is False

    # 5. Exact video center
    nx, ny, inside = screen_to_normalized(960.0, 540.0, cw, ch, vw, vh)
    assert pytest.approx(nx, 0.001) == 0.5
    assert pytest.approx(ny, 0.001) == 0.5
    assert inside is True


def test_roundtrip_subpixel_quantization():
    """Verify subpixel roundtrip quantization invariance across aspect ratios."""
    test_ratios = [
        (1920, 1080, 1080, 1920),  # 9:16 in 16:9
        (1920, 1080, 2560, 1080),  # 21:9 in 16:9
        (1920, 1080, 1080, 1080),  # 1:1 in 16:9
        (360, 780, 1920, 1080),   # 16:9 in tall phone
    ]
    test_points = [(0.0, 0.0), (0.1, 0.2), (0.5, 0.5), (0.85, 0.95), (1.0, 1.0)]

    for cw, ch, vw, vh in test_ratios:
        for orig_x, orig_y in test_points:
            sx, sy = normalized_to_screen(orig_x, orig_y, cw, ch, vw, vh)
            nx, ny, inside = screen_to_normalized(sx, sy, cw, ch, vw, vh)
            assert inside is True
            assert pytest.approx(nx, abs=1e-5) == orig_x
            assert pytest.approx(ny, abs=1e-5) == orig_y


def test_8_handle_anti_inversion_adversarial_stress():
    """Exhaustively stress-test anti-inversion for all 8 handles with adversarial deltas."""
    x, y, w, h = 0.4, 0.4, 0.2, 0.2
    min_size = 0.02

    # 1. East handle dragged violently to the left (dx = -0.5, past left edge)
    nx, ny, nw, nh = resize_mask(x, y, w, h, handle="e", dx=-0.5, dy=0, min_size=min_size)
    assert nw == min_size
    assert nx == x

    # 2. West handle dragged violently to the right (dx = +0.5, past right edge)
    nx, ny, nw, nh = resize_mask(x, y, w, h, handle="w", dx=+0.5, dy=0, min_size=min_size)
    assert nw == min_size
    assert pytest.approx(nx, abs=1e-4) == x + w - min_size

    # 3. South handle dragged violently upwards (dy = -0.5, past top edge)
    nx, ny, nw, nh = resize_mask(x, y, w, h, handle="s", dx=0, dy=-0.5, min_size=min_size)
    assert nh == min_size
    assert ny == y

    # 4. North handle dragged violently downwards (dy = +0.5, past bottom edge)
    nx, ny, nw, nh = resize_mask(x, y, w, h, handle="n", dx=0, dy=+0.5, min_size=min_size)
    assert nh == min_size
    assert pytest.approx(ny, abs=1e-4) == y + h - min_size

    # 5. Corner handles (nw, ne, se, sw) with opposing diagonal movements
    # NW dragged bottom-right
    nx, ny, nw, nh = resize_mask(x, y, w, h, handle="nw", dx=+0.5, dy=+0.5, min_size=min_size)
    assert nw == min_size and nh == min_size
    assert pytest.approx(nx, abs=1e-4) == x + w - min_size
    assert pytest.approx(ny, abs=1e-4) == y + h - min_size

    # SE dragged top-left
    nx, ny, nw, nh = resize_mask(x, y, w, h, handle="se", dx=-0.5, dy=-0.5, min_size=min_size)
    assert nw == min_size and nh == min_size
    assert nx == x and ny == y

    # NE dragged bottom-left
    nx, ny, nw, nh = resize_mask(x, y, w, h, handle="ne", dx=-0.5, dy=+0.5, min_size=min_size)
    assert nw == min_size and nh == min_size
    assert nx == x
    assert pytest.approx(ny, abs=1e-4) == y + h - min_size

    # SW dragged top-right
    nx, ny, nw, nh = resize_mask(x, y, w, h, handle="sw", dx=+0.5, dy=-0.5, min_size=min_size)
    assert nw == min_size and nh == min_size
    assert pytest.approx(nx, abs=1e-4) == x + w - min_size
    assert ny == y


def test_8_handle_boundary_clamping_adversarial_stress():
    """Drag handles far beyond [0.0, 1.0] boundaries and verify clamping."""
    x, y, w, h = 0.5, 0.5, 0.3, 0.3

    # Drag SE far beyond bottom-right (+5.0, +5.0)
    nx, ny, nw, nh = resize_mask(x, y, w, h, handle="se", dx=5.0, dy=5.0)
    assert nx + nw <= 1.0001
    assert ny + nh <= 1.0001
    assert pytest.approx(nw, abs=1e-4) == 0.5
    assert pytest.approx(nh, abs=1e-4) == 0.5

    # Drag NW far beyond top-left (-5.0, -5.0)
    nx, ny, nw, nh = resize_mask(x, y, w, h, handle="nw", dx=-5.0, dy=-5.0)
    assert nx == 0.0
    assert ny == 0.0
    assert pytest.approx(nw, abs=1e-4) == x + w
    assert pytest.approx(nh, abs=1e-4) == y + h


def test_ffmpeg_delogo_1px_context_border_enforcement():
    """Delogo requires 1-px context border around logo area; must clamp safely."""
    # 1. Full-screen mask covering (0, 0, 1.0, 1.0) on 1920x1080 video
    mask_fullscreen = MaskItem(id="m_full", mask_type="erase", x=0.0, y=0.0, width=1.0, height=1.0)
    flt = build_ffmpeg_mask_filter([mask_fullscreen], 1920, 1080)
    assert flt.startswith("delogo=")
    # Must be inset to x=1, y=1, w=1918, h=1078 (not touching 0 or 1920/1080)
    assert "x=1" in flt
    assert "y=1" in flt
    assert "w=1918" in flt
    assert "h=1078" in flt

    # 2. Mask touching bottom-right boundary
    mask_br = MaskItem(id="m_br", mask_type="erase", x=0.5, y=0.5, width=0.5, height=0.5)
    flt_br = build_ffmpeg_mask_filter([mask_br], 1920, 1080)
    assert "x=960" in flt_br
    assert "y=540" in flt_br
    assert "w=959" in flt_br  # 1920 - 1 - 960 = 959
    assert "h=539" in flt_br  # 1080 - 1 - 540 = 539

    # 3. Tiny mask resulting in < 2 interior pixels is skipped to prevent delogo crash
    mask_tiny = MaskItem(id="m_tiny", mask_type="erase", x=0.0, y=0.0, width=0.02, height=0.02)
    flt_tiny = build_ffmpeg_mask_filter([mask_tiny], 100, 100)
    assert flt_tiny == ""  # Safely omitted since erase_w < 2


# ===========================================================================
# 2. API Contract Edge Cases
# ===========================================================================

def test_api_masks_boundary_clamping_and_adversarial_floats(client: TestClient):
    """POST /api/masks must safely clamp negative/excessive floats in domain."""
    payload = {
        "masks": [
            {
                "id": "adv_mask_1",
                "mask_type": "erase",
                "x": -0.85,          # Negative coordinate
                "y": 1.5,            # Beyond 1.0
                "width": 2.5,        # Excessive width
                "height": 3.0,       # Excessive height
                "opacity": 5.0,      # Excessive opacity
                "blur_strength": 999 # Excessive blur
            }
        ]
    }
    resp = client.post("/api/masks", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    m = data["masks"][0]
    # Verify clamping via MaskItem.__post_init__
    assert m["x"] == 0.0
    assert m["y"] == 1.0
    assert m["width"] <= 1.0
    assert m["opacity"] == 1.0
    assert m["blur_strength"] == 50


def test_api_masks_malformed_json_and_types(client: TestClient):
    """POST /api/masks with malformed structures must return 422 Unprocessable Entity."""
    # 1. Invalid data type for coordinates (string instead of float)
    resp1 = client.post("/api/masks", json={"masks": [{"x": "not_a_number"}]})
    assert resp1.status_code == 422

    # 2. Invalid structure (object instead of list)
    resp2 = client.post("/api/masks", json={"masks": "this_should_be_a_list"})
    assert resp2.status_code == 422

    # 3. Nonexistent mask delete returns 404
    resp3 = client.delete("/api/masks/non_existent_mask_uuid_12345")
    assert resp3.status_code == 404


def test_api_voices_preview_invalid_voice_id(client: TestClient):
    """POST /api/voices/preview with unknown voice ID falls back to offline harmonic synthesis."""
    payload = {
        "voice_id": "non-existent-voice-id-xyz",
        "provider": "edge_tts",
        "sample_text": "Thử nghiệm giọng đọc không tồn tại"
    }
    resp = client.post("/api/voices/preview", json=payload)
    # EdgeTTSProvider sanitizes ID and falls back to FFmpeg offline audio preview gracefully
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    assert "audio_url" in data

    # Verify that when provider genuinely fails, server returns 500 with detail
    with patch("vkdub.providers.edge_tts_provider.EdgeTTSProvider.preview_voice") as mock_preview:
        mock_preview.side_effect = RuntimeError("FFmpeg offline audio synthesis failure")
        resp_err = client.post("/api/voices/preview", json=payload)
        assert resp_err.status_code == 500
        assert "Không thể tạo mẫu âm thanh" in resp_err.json()["detail"]


def test_api_voices_preview_empty_text_uses_default(client: TestClient):
    """POST /api/voices/preview with empty text uses fallback text without crashing."""
    payload = {
        "voice_id": "vi-VN-HoaiMyNeural",
        "provider": "edge_tts",
        "sample_text": ""
    }
    with patch("vkdub.providers.edge_tts_provider.EdgeTTSProvider.preview_voice") as mock_preview:
        from vkdub.utils.paths import workspace_root
        mock_file = workspace_root() / "cache" / "mock_preview.mp3"
        mock_file.parent.mkdir(parents=True, exist_ok=True)
        mock_file.write_bytes(b"ID3" + b"\x00" * 100)
        mock_preview.return_value = mock_file

        resp = client.post("/api/voices/preview", json=payload)
        assert resp.status_code == 200
        # Check that preview_voice was called with non-empty default text
        call_kwargs = mock_preview.call_args[1]
        assert len(call_kwargs["text"]) > 0


def test_api_voices_preview_directory_traversal_defense(client: TestClient):
    """GET /api/voices/preview/stream must reject directory traversal attempts."""
    resp = client.get("/api/voices/preview/stream?cache_id=../../../../Windows/System32/drivers/etc/hosts")
    # Path(cache_id).name strips '../', so it safely resolves to cache/hosts which is missing -> 404
    assert resp.status_code == 404


def test_api_pipeline_cancel_idempotency_when_idle(client: TestClient):
    """POST /api/pipeline/cancel while idle must be safely idempotent."""
    for _ in range(5):
        resp = client.post("/api/pipeline/cancel")
        assert resp.status_code == 200
        assert resp.json() == {"status": "idle"}


def test_api_export_rejects_missing_video_source(client: TestClient):
    """Export endpoints must reject requests when video source is not set."""
    state.project.video_path = None

    # 1. MP4 export
    resp_mp4 = client.post("/api/export/mp4", json={"burn_subtitles": True, "apply_masks": True})
    assert resp_mp4.status_code == 400
    assert "video nguồn" in resp_mp4.json()["detail"].lower()

    # 2. CapCut export
    resp_capcut = client.post("/api/export/capcut")
    assert resp_capcut.status_code == 400
    assert "video nguồn" in resp_capcut.json()["detail"].lower()


def test_api_settings_adversarial_inputs(client: TestClient):
    """POST /api/settings handles invalid strings without internal server error."""
    # 1. String fallback for voice_speed
    payload_speed = {
        "voice_speed": "super_fast_invalid",
        "voice_volume": 80
    }
    resp1 = client.post("/api/settings", json=payload_speed)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert "1.0x" in data1["settings"]["voice_speed"]

    # 2. Pydantic validation rejects invalid types with 422
    payload_bad_type = {
        "voice_volume": "not_an_int"
    }
    resp2 = client.post("/api/settings", json=payload_bad_type)
    assert resp2.status_code == 422


# ===========================================================================
# 3. Production Bundle and Static Assets Verification
# ===========================================================================

def test_production_bundle_dist_index_html_integrity():
    """Verify frontend/dist/index.html exists and is properly structured."""
    dist_dir = Path("frontend/dist")
    assert dist_dir.is_dir(), "frontend/dist must exist"

    index_html = dist_dir / "index.html"
    assert index_html.is_file(), "frontend/dist/index.html must exist"
    assert index_html.stat().st_size > 500, "dist/index.html should be valid non-empty HTML"

    content = index_html.read_text(encoding="utf-8")
    assert "<!doctype html>" in content.lower()
    assert "KAPPAK Studio Web v2" in content
    assert '<link rel="icon" type="image/png" href="/logo.png"' in content
    assert '<script type="module" crossorigin src="/assets/' in content


def test_production_assets_serving_and_branding(client: TestClient):
    """Verify FastAPI server serves dist/index.html and authentic KAPPAK branding logo."""
    # 1. Root / must serve SPA index.html
    resp_root = client.get("/")
    assert resp_root.status_code == 200
    assert "text/html" in resp_root.headers.get("content-type", "")
    assert "KAPPAK Studio Web v2" in resp_root.text

    # 2. /index.html
    resp_index = client.get("/index.html")
    assert resp_index.status_code == 200
    assert "KAPPAK Studio Web v2" in resp_index.text

    # 3. Official logo via /logo.png
    resp_logo = client.get("/logo.png")
    assert resp_logo.status_code == 200
    assert resp_logo.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(resp_logo.content) > 10000

    # 4. Official logo via /api/logo
    resp_api_logo = client.get("/api/logo")
    assert resp_api_logo.status_code == 200
    assert resp_api_logo.content == resp_logo.content, "/api/logo and /logo.png must match exactly"

    # 5. Favicon endpoints
    resp_fav_png = client.get("/favicon.png")
    assert resp_fav_png.status_code == 200
    assert resp_fav_png.content == resp_logo.content

    resp_fav_ico = client.get("/favicon.ico")
    assert resp_fav_ico.status_code == 200
    assert resp_fav_ico.content == resp_logo.content


def test_run_app_bat_script_configuration():
    """Verify run_app.bat has valid paths, UTF-8 codepage, and environment setup."""
    bat_path = Path("run_app.bat")
    assert bat_path.is_file()
    bat_content = bat_path.read_text(encoding="utf-8", errors="replace")

    assert "chcp 65001" in bat_content, "Must use UTF-8 codepage"
    assert "PYTHONPATH=src" in bat_content, "Must add src to PYTHONPATH"
    assert ".venv\\Scripts\\python.exe" in bat_content, "Must target .venv python"
    assert "app.py" in bat_content, "Must execute app.py"
