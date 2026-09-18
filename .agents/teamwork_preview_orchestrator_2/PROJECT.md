# Project: VK Dub Studio — YouTube Clip Mode & Extension Tooling

## Architecture
```
Browser (YouTube Tab)                    Side Panel UI
  │                                           │
  ├─ content/youtubeAdapter.js (Shadow DOM)  ├─ apps/browser-extension/sidepanel/
  │  (Hotkeys I/O/Enter/Esc, Timecode)       │  (Clip Manager, Reorder, Validation,
  │                                           │   Export Settings, Progress Telemetry)
  ▼                                           ▼
apps/browser-extension/background/serviceWorker.js
  │ (Dual Hybrid: WebSocket 127.0.0.1:49814 / Native Messaging com.vkdub.bridge)
  ▼
Python Backend (VK Dub Studio)
  ├─ tools/native_host/vkdub_host.py (Stdio Framer)
  ├─ src/vkdub/bridge/local_agent.py (Protocol Dispatcher & WebSocket RFC 6455)
  ├─ src/vkdub/bridge/protocol.py (Actions & Schemas)
  ├─ src/vkdub/services/clip_export_service.py (Job Lifecycle & Progress Streaming)
  ├─ src/vkdub/media/ytdlp.py (Discovery & Single-Download Caching)
  ├─ src/vkdub/media/hardware.py (Active 1-Frame HW Probe: NVENC/QSV/AMF/CPU)
  └─ src/vkdub/media/clip_engine.py (Stream-Copy, Frame-Accurate Re-encode, Concat Demuxer)
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | In-Player Toolbar Shadow DOM Mount | Mount non-intrusive toolbar in `#movie_player` with Shadow DOM isolation | M4 | Survey Ext |
| F2 | In-Player Hotkeys (I, O, Enter, Esc) | Capturing phase hotkey intercept overriding YouTube Miniplayer shortcut | M4 | Survey Ext |
| F3 | YouTube SPA Navigation & Singleton | Single controller `window.__vkdubYoutubeAdapter` handling `yt-navigate-finish` | M4 | Survey Ext |
| F4 | Manifest V3 & Side Panel Setup | Update `manifest.json` with `sidePanel`, YouTube host permissions, and sidepanel assets | M5 | Survey Ext |
| F5 | Side Panel Video Card & Clip List | Video info display, DnD reordering, inline name and timecode edit, delete | M5 | Survey Ext |
| F6 | Client-Side Clip Validation | Reject `start >= end`, exceeding duration, <0.5s clips, and duplicate segments | M5 | Survey Ext |
| F7 | Interactive Preview & Seek | Seek YouTube player to clip start and auto-pause at clip end | M4, M5 | Survey Ext |
| F8 | Realtime Protocol Actions & Schemas | Expand protocol actions in JS and Python for all 10 YouTube and Clip actions | M1 | Survey Bridge |
| F9 | yt-dlp Discovery Engine | 5-step search order: `YTDLP_PATH` -> `tools/yt-dlp/` -> `tools/` -> PATH -> WinGet | M2 | Survey Video |
| F10 | Single Download & Remux Cache | Cache by `(video_id, quality)` in `cache/youtube/{video_id}`, opt-in cookies only | M2 | Survey Video |
| F11 | Active Hardware Encoder Prober | Active 1-frame probe for NVENC/QSV/AMF with fallback to libx264/libx265 CRF 17-18 | M2 | Survey Video |
| F12 | Stream-Copy & Frame-Accurate Engine | `-c copy` with keyframe snap vs frame-accurate re-encode with detected HW encoder | M2 | Survey Video |
| F13 | Multi-Clip Concat & Merge Engine | Concat demuxer manifest generation and lossless stream-copy merge | M2 | Survey Video |
| F14 | Job Execution & Process Cancellation | Safe argv arrays, Windows path sanitization, `taskkill /F /T /PID` tree kill | M3 | Survey Video |
| F15 | Realtime Progress Streaming & Telemetry | Stream download %, stage, speed, size, and file path to side panel via Native Bridge | M3 | Survey Bridge |
| F16 | ToolVideo Timeline & Pipeline Import | Direct import of cut/merged clips into ToolVideo timeline/state | M3 | Survey Video |
| F17 | Extension Registration & Update Tooling | Registry check/register for Chrome & Edge, reload script, and UI status widget | M5 | Survey Bridge |
| F18 | Full Preservation of ChatGPT & Vbee | 100% regression-free isolation of existing translation and TTS bridge workflows | M1 | Survey Bridge |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Bridge Protocol & Compatibility Layer | Expand `protocol.py`, `protocol.js`, `LocalAgent` actions, fix `server.py` missing methods, guarantee R7 preservation | none | DONE (26/26 bridge & 607/607 full suite pass) |
| M2 | Video Engine (yt-dlp, HW Accel, Trimming) | Implement `ytdlp.py`, `hardware.py`, `clip_engine.py`, Windows path sanitization, stream-copy & frame-accurate cuts | none | DONE (40/40 tests pass, 0 lint) |
| M3 | Job Execution & Export Service | Implement `clip_export_service.py`, cancel & tree kill, progress streaming, ToolVideo timeline import | M1, M2 | DONE (22/22 unit & 233/233 clip mode suite pass) |
| M4 | YouTube In-Player Toolbar | Implement `apps/browser-extension/content/youtubeAdapter.js`, Shadow DOM, hotkeys, SPA navigation | M1 | DONE (10/10 node & 138/138 pytest pass) |
| M5 | Side Panel Clip Manager & Extension Packaging | Implement `apps/browser-extension/sidepanel/` (HTML/CSS/JS), update `manifest.json`, installation scripts | M1, M4 | DONE (158/158 tests pass, 0 lint) |
| M6 | Dual Track E2E Test Suite & Final Hardening | 100% pass on comprehensive E2E test suite (Tiers 1-4), followed by Tier 5 adversarial hardening | M1, M2, M3, M4, M5 | IN_PROGRESS (Gate verification active) |

## Interface Contracts
### Protocol Actions
- `YOUTUBE_CONTEXT_SYNC`: Extension -> Bridge. Payload: `{ videoId, title, duration, url, timestamp }`.
- `YOUTUBE_SEEK_TO`: Sidepanel -> Content Script. Payload: `{ seconds: number }`.
- `YOUTUBE_PREVIEW_CLIP`: Sidepanel -> Content Script. Payload: `{ start: number, end: number }`.
- `CLIP_EXPORT_REQUEST`: Sidepanel -> Bridge. Payload: `{ requestId, videoId, videoUrl, videoTitle, clips: [{ id, name, start, end }], exportMode: "SEPARATE"|"MERGED"|"IMPORT", outputDir, container: "mp4"|"mkv", quality: "best"|"2160p"|"1440p"|"1080p"|"720p", cutMode: "STREAM_COPY"|"FRAME_ACCURATE", useCookies: boolean, browser: string }`.
- `CLIP_EXPORT_ACCEPTED`: Bridge -> Sidepanel. Payload: `{ requestId, jobId, status: "QUEUED" }`.
- `CLIP_EXPORT_PROGRESS`: Bridge -> Sidepanel. Payload: `{ requestId, jobId, stage: "PROBING"|"DOWNLOADING"|"REMUXING"|"TRIMMING"|"MERGING"|"COMPLETE", percent: number, speed: string, downloadedBytes: number, totalBytes: number, currentClip: number, totalClips: number, message: string }`.
- `CLIP_EXPORT_RESULT`: Bridge -> Sidepanel. Payload: `{ requestId, jobId, status: "SUCCESS", files: [string], mergedFile?: string, outputDir: string, elapsedSeconds: number }`.
- `CLIP_EXPORT_ERROR`: Bridge -> Sidepanel. Payload: `{ requestId, jobId, status: "ERROR", error: string, stage: string }`.
- `CLIP_EXPORT_CANCEL`: Sidepanel -> Bridge. Payload: `{ requestId, jobId }`.
- `OPEN_OUTPUT_FOLDER`: Sidepanel -> Bridge. Payload: `{ path: string }`.

## Code Layout
- `apps/browser-extension/manifest.json` — MV3 declarations, permissions, sidePanel
- `apps/browser-extension/content/youtubeAdapter.js` — YouTube In-Player Toolbar & Clip Marker
- `apps/browser-extension/sidepanel/` — Side Panel Clip Manager (index.html, sidepanel.css, sidepanel.js)
- `apps/browser-extension/bridge/protocol.js` — Shared protocol action constants
- `apps/browser-extension/background/serviceWorker.js` — Extension background coordinator
- `src/vkdub/bridge/protocol.py` — Python protocol action constants and schemas
- `src/vkdub/bridge/local_agent.py` — Native bridge server and message router
- `src/vkdub/media/ytdlp.py` — yt-dlp discovery, download, and caching
- `src/vkdub/media/hardware.py` — FFmpeg hardware encoder active 1-frame probe
- `src/vkdub/media/clip_engine.py` — FFmpeg stream-copy, frame-accurate trimming, and concat demuxer
- `src/vkdub/services/clip_export_service.py` — Background job execution, cancellation, and progress streaming
- `tools/native_host/register_host.py` — Windows registry host checker and installer
- `tests/test_youtube_clip_mode.py` — Comprehensive unit and integration test suite
