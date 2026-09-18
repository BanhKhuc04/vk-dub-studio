"""VK Dub Studio — Extension Manifest, Packaging, and Side Panel Verification Test Suite.

Verifies:
1. Manifest V3 schema validity, version 2.3.0, sidePanel and YouTube permissions.
2. Deterministic Extension ID preservation via RSA key.
3. Content script registrations (YouTube, ChatGPT, Vbee) and physical file existence.
4. Side Panel HTML/CSS/JS file integrity and Apple design system.
5. Service Worker dual hybrid routing and 100% preservation of ChatGPT/Vbee automation.
6. Native Messaging Host registration for Microsoft Edge and Google Chrome.
7. Developer extension reload tooling (scripts/reload_extension.bat).
8. Node.js execution of sidepanel.js validation engine and timecode parsing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXT_DIR = PROJECT_ROOT / "apps" / "browser-extension"
MANIFEST_PATH = EXT_DIR / "manifest.json"
EXPECTED_EXTENSION_ID = "bnpmffibedppchkljkcaidgijekgfmgl"
EXPECTED_VERSION = "2.3.0"


# ===========================================================================
# 1. Manifest V3 Schema & Permissions Tests
# ===========================================================================


def test_manifest_file_exists():
    """Verify manifest.json exists in apps/browser-extension."""
    assert MANIFEST_PATH.is_file(), f"manifest.json not found at {MANIFEST_PATH}"


def test_manifest_json_valid_syntax():
    """Verify manifest.json is valid parseable JSON."""
    content = MANIFEST_PATH.read_text(encoding="utf-8")
    data = json.loads(content)
    assert isinstance(data, dict)
    assert data.get("manifest_version") == 3


def test_manifest_version_bumped_to_2_3_0():
    """Verify extension version is 2.3.0."""
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert data.get("version") == EXPECTED_VERSION


def test_manifest_rsa_key_deterministic_extension_id():
    """Verify hardcoded RSA key is present to guarantee deterministic ID."""
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    key = data.get("key", "")
    assert len(key) > 100, "Manifest RSA key missing or truncated"
    assert "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCg" in key


def test_manifest_permissions():
    """Verify required permissions including sidePanel and nativeMessaging."""
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    perms = set(data.get("permissions", []))
    required = {
        "nativeMessaging",
        "activeTab",
        "tabs",
        "storage",
        "cookies",
        "downloads",
        "scripting",
        "webNavigation",
        "sidePanel",
    }
    missing = required - perms
    assert not missing, f"Missing required permissions: {missing}"


def test_manifest_host_permissions_include_youtube():
    """Verify host_permissions include YouTube, ChatGPT, and Vbee."""
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    hosts = set(data.get("host_permissions", [])) | set(data.get("optional_host_permissions", []))

    assert any("youtube.com" in h for h in hosts), "Missing YouTube host_permission"
    assert any("chatgpt.com" in h for h in hosts), "Missing ChatGPT host_permission"
    assert any("vbee.vn" in h for h in hosts), "Missing Vbee host_permission"


def test_manifest_youtube_permission_is_scriptable():
    """YouTube must be a required host so Edge permits script injection."""
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    hosts = set(data.get("host_permissions", []))
    assert "*://www.youtube.com/*" in hosts


def test_manifest_side_panel_declaration():
    """Verify side_panel entry points to existing sidepanel/index.html."""
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert "side_panel" in data, "Missing 'side_panel' key in manifest.json"
    side_panel_path = data["side_panel"].get("default_path")
    assert side_panel_path == "sidepanel/index.html"
    assert (EXT_DIR / side_panel_path).is_file(), f"File {side_panel_path} does not exist"


def test_manifest_content_scripts_registration_and_files_exist():
    """Verify content_scripts registers adapters and files exist."""
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    content_scripts = data.get("content_scripts", [])
    assert len(content_scripts) >= 3, "Expected ChatGPT, Vbee and YouTube content_script configurations"

    registered_js = []
    for cs in content_scripts:
        for script in cs.get("js", []):
            registered_js.append(script)
            target_file = EXT_DIR / script
            assert target_file.is_file(), f"Script {script} does not exist on disk"

    assert "content/chatgptAdapter.js" in registered_js
    assert "content/vbeeAdapter.js" in registered_js
    assert "content/youtubeAdapter.js" in registered_js
    worker = (EXT_DIR / "background" / "serviceWorker.js").read_text(encoding="utf-8")
    assert 'files: ["content/youtubeAdapter.js"]' in worker


def test_manifest_icons_exist():
    """Verify all declared icons exist on disk."""
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    icons = data.get("icons", {})
    assert len(icons) >= 4, "Expected 16, 32, 48, 128 icons"
    for _size, icon_rel in icons.items():
        assert (EXT_DIR / icon_rel).is_file(), f"Icon {icon_rel} does not exist"


def test_manifest_background_service_worker():
    """Verify background service worker is declared as module and exists."""
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    bg = data.get("background", {})
    assert bg.get("type") == "module"
    worker_rel = bg.get("service_worker")
    assert worker_rel == "background/serviceWorker.js"
    assert (EXT_DIR / worker_rel).is_file(), f"Background worker {worker_rel} does not exist"


# ===========================================================================
# 2. Side Panel HTML / CSS / JS Integrity Tests
# ===========================================================================


def test_sidepanel_html_structure():
    """Verify index.html contains video card, clip list, empty state, export card, progress card."""
    html_path = EXT_DIR / "sidepanel" / "index.html"
    assert html_path.is_file()
    content = html_path.read_text(encoding="utf-8")

    # Essential UI sections
    assert 'id="video-card"' in content
    assert 'id="video-thumbnail"' in content
    assert 'id="video-title"' in content
    assert 'id="empty-state"' in content
    assert 'id="clips-section"' in content
    assert 'id="clips-list"' in content
    assert 'id="export-card"' in content
    assert 'id="progress-card"' in content
    assert 'id="result-card"' in content
    assert 'id="toast-container"' in content
    assert 'id="youtube-status-badge"' in content
    assert 'id="connection-status-badge"' in content
    assert 'id="btn-retry-youtube"' in content
    assert 'id="youtube-error-detail"' in content
    assert 'id="btn-add-first-manual"' in content

    # Controls
    assert 'id="btn-export-start"' in content
    assert 'id="btn-cancel-export"' in content
    assert 'name="export-mode"' in content
    assert 'name="cut-mode"' in content
    assert 'id="use-cookies-checkbox"' in content
    assert 'src="sidepanel.js"' in content


def test_sidepanel_css_design_system():
    """Verify sidepanel.css implements Apple design system styling."""
    css_path = EXT_DIR / "sidepanel" / "sidepanel.css"
    assert css_path.is_file()
    content = css_path.read_text(encoding="utf-8")

    # Apple design tokens
    assert "--accent-blue" in content
    assert "backdrop-filter: blur" in content
    assert "--transition-spring" in content
    assert ".apple-dark" in content
    assert ".clip-card" in content
    assert ".segmented-control" in content
    assert ".progress-bar-fill" in content
    assert ".apple-toast" in content


def test_sidepanel_js_module_integrity():
    """Verify sidepanel.js includes validation, DnD, telemetry, and protocol imports."""
    js_path = EXT_DIR / "sidepanel" / "sidepanel.js"
    assert js_path.is_file()
    content = js_path.read_text(encoding="utf-8")

    # Protocol imports
    assert "createClipExportRequest" in content
    assert "createClipExportCancel" in content
    assert "createOpenOutputFolder" in content
    assert "Actions" in content
    assert "ExportStage" in content

    # Core logic functions
    assert "function roundMs" in content
    assert "function formatTimecode" in content
    assert "function parseTimecode" in content
    assert "function validateClip" in content
    assert "class SidePanelApp" in content
    assert "setupDnD" in content
    assert "startExport" in content
    assert "cancelExport" in content
    assert "updateYouTubeStatus" in content
    assert "scheduleActiveTabDetection" in content
    assert "requestYouTubeStatus" in content


def test_youtube_toolbar_has_duplicate_cleanup_guard():
    """A reloaded extension or replaced SPA player must still leave one toolbar host."""
    js_path = EXT_DIR / "content" / "youtubeAdapter.js"
    content = js_path.read_text(encoding="utf-8")

    assert "TOOLBAR_HOST_MARKER" in content
    assert "document.querySelectorAll(`#${TOOLBAR_HOST_ID}" in content
    assert "if (node !== existingHost) node.remove()" in content
    assert "isAdoptingExistingHost" in content
    assert "this.shadowRoot.replaceChildren()" in content


def test_youtube_live_detection_does_not_block_vod_or_replays():
    """A hidden persistent live badge must not make ordinary videos uncuttable."""
    js_path = EXT_DIR / "content" / "youtubeAdapter.js"
    content = js_path.read_text(encoding="utf-8")

    assert "videoData.isLive === true" in content
    assert "Number.isFinite(duration) && duration > 0" in content
    assert "liveBadge.getClientRects().length > 0" in content
    assert 'document.querySelector(".ytp-live, .ytp-live-badge")' not in content


# ===========================================================================
# 3. Service Worker Router & R7 Preservation Tests
# ===========================================================================


def test_service_worker_preserves_chatgpt_workflow():
    """Verify serviceWorker.js preserves 100% of ChatGPT translation automation."""
    sw_path = EXT_DIR / "background" / "serviceWorker.js"
    assert sw_path.is_file()
    content = sw_path.read_text(encoding="utf-8")

    assert "handleChatGPTTranslate" in content
    assert "isChatGPTTab" in content
    assert "CHATGPT_TRANSLATE_DONE" in content
    assert "CHATGPT_PROGRESS" in content
    assert "Actions.CHATGPT_TRANSLATE" in content
    assert "content/chatgptAdapter.js" in content


def test_service_worker_preserves_vbee_workflow():
    """Verify serviceWorker.js preserves 100% of Vbee TTS automation."""
    sw_path = EXT_DIR / "background" / "serviceWorker.js"
    content = sw_path.read_text(encoding="utf-8")

    assert "handleVbeeGenerate" in content
    assert "isVbeeTab" in content
    assert "finalizeVbeeResult" in content
    assert "waitForVbeeDownload" in content
    assert "VBEE_GENERATE_DONE" in content
    assert "VBEE_PROGRESS" in content
    assert "Actions.VBEE_GENERATE_VOICE" in content
    assert "content/vbeeAdapter.js" in content


def test_service_worker_routes_youtube_and_clip_actions():
    """Verify serviceWorker.js routes YouTube sync and clip export actions."""
    sw_path = EXT_DIR / "background" / "serviceWorker.js"
    content = sw_path.read_text(encoding="utf-8")

    assert "Actions.YOUTUBE_CONTEXT_SYNC" in content
    assert "Actions.ENSURE_YOUTUBE_ADAPTER" in content
    assert "ensureYouTubeAdapter" in content
    assert 'files: ["content/youtubeAdapter.js"]' in content
    assert "Actions.YOUTUBE_SEEK_TO" in content
    assert "Actions.YOUTUBE_PREVIEW_CLIP" in content
    assert "Actions.CLIP_EXPORT_REQUEST" in content
    assert "Actions.CLIP_EXPORT_CANCEL" in content
    assert "Actions.OPEN_OUTPUT_FOLDER" in content
    assert "Actions.CLIP_EXPORT_ACCEPTED" in content
    assert "Actions.CLIP_EXPORT_PROGRESS" in content
    assert "Actions.CLIP_EXPORT_RESULT" in content
    assert "Actions.CLIP_EXPORT_ERROR" in content
    assert "sidePanel" in content


def test_service_worker_has_single_status_listener_set_and_bounded_timer():
    """Prevent the duplicated zero-delay loop that crashed the MV3 worker."""
    content = (EXT_DIR / "background" / "serviceWorker.js").read_text(encoding="utf-8")

    assert content.count("chrome.tabs.onActivated.addListener") == 1
    assert content.count("chrome.tabs.onUpdated.addListener(() => {") == 1
    assert content.count("chrome.tabs.onRemoved.addListener") == 1
    assert "}, 3000);" in content


def test_sidepanel_queries_bridge_status_directly():
    """Connection badge must not depend only on a lossy broadcast message."""
    content = (EXT_DIR / "sidepanel" / "sidepanel.js").read_text(encoding="utf-8")

    assert "refreshConnectionStatus" in content
    assert "typeof response.connected" in content
    assert "response.transport" in content
    assert "setInterval(() => this.refreshConnectionStatus(), 2000)" in content


def test_native_bridge_reports_real_local_agent_health():
    """Native host availability must not be confused with the desktop app being ready."""
    worker = (EXT_DIR / "background" / "serviceWorker.js").read_text(encoding="utf-8")
    host = (PROJECT_ROOT / "tools" / "native_host" / "vkdub_host.py").read_text(
        encoding="utf-8"
    )

    assert "function isLocalAgentConnected()" in worker
    assert "Actions.GET_AGENT_STATUS" in worker
    assert "nativeAgentConnected" in worker
    assert 'if action == "GET_AGENT_STATUS"' in host
    assert 'action == "CLIP_EXPORT_REQUEST" and not bridge.connected' in host
    assert 'msg.get("action") == "STATUS_REPORT"' in host


# ===========================================================================
# 4. Native Host Registration & Developer Tooling Tests
# ===========================================================================


def test_register_host_manifest_generation():
    """Verify register_host.py generates valid manifest pointing to vkdub_host.bat."""
    from tools.native_host.register_host import (
        EXTENSION_ID,
        HOST_NAME,
        get_manifest_path,
    )

    manifest_path = get_manifest_path()
    assert manifest_path.is_file(), f"Manifest not generated at {manifest_path}"

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data.get("name") == HOST_NAME
    assert data.get("type") == "stdio"
    assert f"chrome-extension://{EXTENSION_ID}/" in data.get("allowed_origins", [])

    host_bat = Path(data.get("path", ""))
    assert host_bat.is_file(), f"Target host executable {host_bat} does not exist"
    assert host_bat.name.lower() == "vkdub_host.bat"


def test_register_host_check_and_register():
    """Verify register_host check and register functions return expected types."""
    from tools.native_host.register_host import is_host_registered, register_host

    status = is_host_registered()
    assert isinstance(status, dict)
    assert "Microsoft Edge" in status
    assert "Google Chrome" in status

    # Registration succeeds
    registered = register_host()
    assert isinstance(registered, list)
    if sys.platform == "win32":
        assert len(registered) >= 1, "Expected at least one browser to be registered on Windows"


def test_reload_extension_batch_exists_and_runs():
    """Verify scripts/reload_extension.bat exists and exits with code 0."""
    bat_path = PROJECT_ROOT / "scripts" / "reload_extension.bat"
    assert bat_path.is_file()

    res = subprocess.run(
        ["cmd.exe", "/c", str(bat_path)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res.returncode == 0, f"reload_extension.bat failed:\n{res.stderr}\n{res.stdout}"
    assert "Developer Mode" in res.stdout
    assert EXPECTED_EXTENSION_ID in res.stdout


# ===========================================================================
# 5. Node.js Dynamic Execution Tests of Sidepanel & YouTube Validation
# ===========================================================================


def test_node_sidepanel_validation_engine():
    """Run Node.js script to verify sidepanel.js validation functions."""
    node_test_script = """
    import {
      roundMs,
      formatTimecode,
      parseTimecode,
      validateClip,
    } from './apps/browser-extension/sidepanel/sidepanel.js';
    import assert from 'assert';

    // 1. Math and timecode formatting
    assert.strictEqual(roundMs(12.3456), 12.346);
    assert.strictEqual(formatTimecode(75.5, false), '01:15.500');
    assert.strictEqual(formatTimecode(3665.25, true), '01:01:05.250');

    // 2. Flexible timecode parsing
    assert.strictEqual(parseTimecode('85.4'), 85.4);
    assert.strictEqual(parseTimecode('01:25.400'), 85.4);
    assert.strictEqual(parseTimecode('01:00:00.000'), 3600);
    assert.strictEqual(parseTimecode('invalid'), null);

    // 3. Clip validation
    // Valid clip
    const v1 = validateClip({ id: 'c1', start: 10, end: 20 }, 100, []);
    assert.strictEqual(v1.valid, true);

    // Invalid: start >= end
    const v2 = validateClip({ id: 'c2', start: 20, end: 10 }, 100, []);
    assert.strictEqual(v2.valid, false);

    // Invalid: duration < 0.5s
    const v3 = validateClip({ id: 'c3', start: 10, end: 10.2 }, 100, []);
    assert.strictEqual(v3.valid, false);

    // Invalid: exceeding video duration
    const v4 = validateClip({ id: 'c4', start: 90, end: 120 }, 100, []);
    assert.strictEqual(v4.valid, false);

    // Invalid: duplicate clip
    const allClips = [{ id: 'c1', start: 10, end: 20 }];
    const v5 = validateClip({ id: 'c5', start: 10.02, end: 20.04 }, 100, allClips);
    assert.strictEqual(v5.valid, false);

    console.log('NODE_SIDEPANEL_TEST_OK');
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", node_test_script],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res.returncode == 0, f"Node sidepanel test failed:\n{res.stderr}"
    assert "NODE_SIDEPANEL_TEST_OK" in res.stdout
