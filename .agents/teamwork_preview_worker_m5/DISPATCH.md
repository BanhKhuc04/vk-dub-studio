# Milestone M5 Implementation: Side Panel Clip Manager & Extension Installation/Update Tooling

Read `D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md` (specifically ## 2026-09-15T04:12:10Z), `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_2\PROJECT.md`, Explorer 1's report in `.agents/teamwork_preview_explorer_survey_bridge/report.md`, and Explorer 2's report in `.agents/teamwork_preview_spec_miner_survey_ext/report.md`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Write Ownership
You exclusively own:
- `apps/browser-extension/manifest.json`
- `apps/browser-extension/sidepanel/index.html`
- `apps/browser-extension/sidepanel/sidepanel.css`
- `apps/browser-extension/sidepanel/sidepanel.js`
- `apps/browser-extension/background/serviceWorker.js`
- `tools/native_host/register_host.py` (verify/enhance host registration for Chrome & Edge)
- `tools/reload_extension.bat` / extension reload & dev mode helper scripts
- `tests/test_manifest_and_packaging.py`

## Objective & Tasks
1. **Manifest V3 Updates (`apps/browser-extension/manifest.json`)**:
   - Update version to `2.2.0`.
   - Add `"sidePanel"` to permissions.
   - Add `"*://*.youtube.com/*"` to host_permissions.
   - Add `"side_panel": { "default_path": "sidepanel/index.html" }`.
   - Register `content/youtubeAdapter.js` in `content_scripts` with matches `["*://*.youtube.com/watch*"]`.
   - Ensure hardcoded RSA `key` remains intact so extension ID remains `bnpmffibedppchkljkcaidgijekgfmgl`.
   - Ensure 100% preservation of ChatGPT and Vbee content scripts and permissions.
2. **Side Panel Clip Manager (`apps/browser-extension/sidepanel/`)**:
   - Create Apple-inspired sleek UI (`index.html`, `sidepanel.css`, `sidepanel.js`):
     * Video info card: thumbnail, title, video ID, total duration badge.
     * Clip List: draggable list (HTML5 DnD) with inline name editing, inline timecode editor/parser (`HH:MM:SS.mmm`, `MM:SS`, seconds), duration pill, delete button, toggle select per clip and "Select All".
     * Client-side validation: reject `start >= end`, exceeding video duration, clips <0.5s, and duplicate segments.
     * Preview seek: "Xem thử" button sending `YOUTUBE_PREVIEW_CLIP` or `YOUTUBE_SEEK_TO` to YouTube content script.
     * Export drawer/modal:
       - Export mode: Separate clips, Merged clip, Import to ToolVideo.
       - Output folder picker/path with "Mở thư mục" button.
       - Container: `mp4` or `mkv`.
       - Source Quality: Best, 2160p, 1440p, 1080p, 720p.
       - Cut Mode: "Siêu nhanh - giữ nguyên chất lượng" (stream copy `-c copy`) vs "Chính xác từng khung hình" (frame-accurate hardware acceleration).
       - Optional Cookies opt-in toggle (public videos strictly zero cookies).
     * Realtime progress telemetry: display stage, % progress bar, speed, downloaded bytes, file paths via `CLIP_EXPORT_PROGRESS`.
     * Job cancellation: "Hủy" button sending `CLIP_EXPORT_CANCEL`.
     * Session restoration: save clips to `chrome.storage.local` keyed by `videoId` so reopening side panel recovers clips.
     * Post-export buttons: "Mở thư mục" (`OPEN_OUTPUT_FOLDER`) and "Đưa vào ToolVideo".
3. **Background Service Worker (`serviceWorker.js`)**:
   - Route sidepanel communication to NativeMessagingBridge (`sendNativeCommand`).
   - Relay `YOUTUBE_CONTEXT_SYNC` to sidepanel and storage.
   - Forward `CLIP_EXPORT_*` messages from NativeBridge to sidepanel.
   - Relay seek/preview commands from sidepanel to active YouTube tab.
   - Strictly preserve all existing ChatGPT and Vbee handlers and bridges.
4. **Extension Registration & Developer Reloading Tooling**:
   - Verify `tools/native_host/register_host.py` checks and registers both Microsoft Edge (`HKCU\Software\Microsoft\Edge\NativeMessagingHosts`) and Google Chrome (`HKCU\Software\Google\Chrome\NativeMessagingHosts`).
   - Create `tools/reload_extension.bat` (or PowerShell script) with clear developer instructions for loading unpacked extension and reloading without browser restart.
5. **Validation & Tests**:
   - Verify `manifest.json` validity.
   - Run unit tests in `tests/test_manifest_and_packaging.py` checking manifest schema, registry scripts, and protocol action coverage.
   - Run full test suite:
     `cmd.exe /c "set PYTHONPATH=src&& D:\Work\Project_AI\ToolVideo\.venv\Scripts\python.exe -m pytest tests/test_manifest_and_packaging.py tests/test_youtube_clip_mode.py tests/test_bridge_protocol.py -v"`
6. Deliver `handoff.md` and message parent when complete.
