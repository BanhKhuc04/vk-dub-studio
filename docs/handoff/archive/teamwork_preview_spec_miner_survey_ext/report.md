# Comprehensive Technical Specification: Extension UI, YouTube In-Player Toolbar & Side Panel Clip Manager

**Project**: VK Dub Studio (ToolVideo)  
**Authoritative Reference**: `D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md` (specifically `## 2026-09-15T04:12:10Z`)  
**Target Path**: `apps/browser-extension/`  
**Mining Agent**: Explorer 2 (`teamwork_preview_spec_miner_survey_ext`)  
**Date**: 2026-09-15  

---

## 1. Executive Summary & Architecture Overview

The VK Dub Studio Browser Extension (currently `apps/browser-extension/`, version 2.1.17) is an enterprise Chromium Manifest V3 extension deployed identically across **Microsoft Edge** and **Google Chrome**. It currently provides dual hybrid communication (WebSocket direct port `49814` with automatic Native Messaging fallback `com.vkdub.bridge`) to coordinate automation workflows for ChatGPT translation and Vbee voice dubbing.

The **YouTube Clip Mode** expansion introduces two major UI/UX systems:
1. **YouTube In-Player Toolbar (`content/youtubeAdapter.js`)**: An in-player overlay mounted directly onto YouTube watch pages (`https://www.youtube.com/watch*`), providing hotkey-driven clipping (`I`, `O`, `Enter`, `Escape`), high-precision timecode tracking, and SPA navigation resilience without duplicating controls or obstructing YouTube's native player controls.
2. **Side Panel Clip Manager (`sidepanel/`)**: A dedicated Chromium MV3 Side Panel (`apps/browser-extension/sidepanel/index.html`) implementing Apple-style design ergonomics, interactive clip list management, inline timecode editing, drag-and-drop reordering, client-side validation, seek/preview synchronization, and realtime export telemetry.

Both systems operate with strict isolation, preserving 100% of existing ChatGPT translation and Vbee TTS features without regressions.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CHROME / EDGE BROWSER                               │
│                                                                                        │
│  ┌───────────────────────────────┐               ┌──────────────────────────────────┐  │
│  │   YouTube Watch Page Tab      │               │     Side Panel Clip Manager      │  │
│  │  ┌─────────────────────────┐  │               │   (sidepanel/index.html & js)    │  │
│  │  │ YouTube Player Native   │  │               │  ┌─────────────────────────────┐ │  │
│  │  │ Controls & Video Elem   │  │               │  │ Video Info & Thumbnail Card │ │  │
│  │  └────────────▲────────────┘  │               │  ├─────────────────────────────┤ │  │
│  │               │               │               │  │ Draggable Clip List Items   │ │  │
│  │  ┌────────────▼────────────┐  │  chrome.tabs  │  │  - Start / End / Duration   │ │  │
│  │  │ YouTube In-Player Bar   │◄─┼───────────────┼─►│  - Inline Timecode Editing  │ │  │
│  │  │ (youtubeAdapter.js)     │  │  .sendMessage│  │  - Seek / Preview Button    │ │  │
│  │  │  - Hotkeys I, O, Enter  │  │               │  ├─────────────────────────────┤ │  │
│  │  │  - Shadow DOM Isolated  │  │               │  │ Export Config & Progress UI │ │  │
│  │  └─────────────────────────┘  │               │  └──────────────▲──────────────┘ │  │
│  └───────────────▲───────────────┘               └─────────────────┼────────────────┘  │
│                  │                                                 │                   │
│                  │ runtime.sendMessage                             │ runtime.sendMsg   │
│                  ▼                                                 ▼                   │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │                   Background Service Worker (serviceWorker.js)                   │  │
│  │    - chrome.sidePanel API manager & active YouTube tab tracker                   │  │
│  │    - Job state persistence in chrome.storage.local                               │  │
│  │    - Dual Hybrid Client: WebSocket (49814) -> Native Host (com.vkdub.bridge)    │  │
│  └─────────────────────────────────────────▲────────────────────────────────────────┘  │
└────────────────────────────────────────────┼───────────────────────────────────────────┘
                                             │ WebSocket / Stdio IPC
                                             ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                         VK DUB STUDIO DESKTOP APPLICATION                              │
│                                                                                        │
│  ┌───────────────────────────────┐               ┌──────────────────────────────────┐  │
│  │ Local Agent / Native Host     │               │ Job Execution Engine             │  │
│  │ (local_agent.py / host.py)    ├──────────────►│ (yt-dlp download & cache,        │  │
│  │ Port 49814 / Stdio Framed JSON│               │  FFmpeg Stream Copy & NVENC)     │  │
│  └───────────────────────────────┘               └──────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Manifest V3 Specification & Extension Permissions

### 2.1 Manifest Updates (`manifest.json`)
The extension manifest must be updated from `2.1.17` to `2.2.0` with the following schema specifications:

```json
{
  "manifest_version": 3,
  "name": "VK Dub Studio Bridge",
  "version": "2.2.0",
  "description": "Microsoft Edge & Chrome Bridge for VK Dub Studio Automation & YouTube Clip Mode",
  "key": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0rUwetRNAsoPBo0o0hVtgMJJL0bQfOUs5LiCdDlMg242irjOt4L75Qr3+322+SHDUEA/lYcQglaEHKD3tSlE/pwUIhekHHadAAZnYladqLEApp9Lk1587C82LnfK9K+qmI1PM7jviNJxFdFHtHttF3O00eFYrPWw0P9ygtL92mEFFxcV1qh3lG8zWiJtRe1Ph2oOw5YjWuDFm+5WrtgfFA0xJgn9hK76Y8aCtTK+oQXGhBnzrb5p9wSDC7s6NRHUjBytONPXD1o1OonDmnfLi7ZnUjJjzHx8GX54tBcZ/7F/tBWqvUoZEwN/xIiERxxjvh4WFhnRcAu1r6yo5i5QjQIDAQAB",
  "permissions": [
    "nativeMessaging",
    "tabs",
    "storage",
    "cookies",
    "downloads",
    "scripting",
    "webNavigation",
    "sidePanel"
  ],
  "host_permissions": [
    "*://chatgpt.com/*",
    "*://*.chatgpt.com/*",
    "*://chat.openai.com/*",
    "*://*.openai.com/*",
    "*://vbee.vn/*",
    "*://*.vbee.vn/*",
    "*://studio.vbee.vn/*",
    "*://*.studio.vbee.vn/*",
    "*://*.youtube.com/*",
    "*://youtube.com/*",
    "*://127.0.0.1/*",
    "*://localhost/*"
  ],
  "side_panel": {
    "default_path": "sidepanel/index.html"
  },
  "background": {
    "service_worker": "background/serviceWorker.js",
    "type": "module"
  },
  "content_scripts": [
    {
      "matches": [
        "*://chatgpt.com/*",
        "*://*.chatgpt.com/*",
        "*://chat.openai.com/*",
        "*://*.openai.com/*"
      ],
      "js": ["content/chatgptAdapter.js"],
      "run_at": "document_end"
    },
    {
      "matches": [
        "*://vbee.vn/*",
        "*://*.vbee.vn/*",
        "*://studio.vbee.vn/*",
        "*://*.studio.vbee.vn/*"
      ],
      "js": ["content/vbeeAdapter.js"],
      "run_at": "document_end"
    },
    {
      "matches": [
        "*://*.youtube.com/*",
        "*://youtube.com/*"
      ],
      "js": ["content/youtubeAdapter.js"],
      "run_at": "document_end"
    }
  ],
  "action": {
    "default_title": "VK Dub Studio Bridge",
    "default_icon": {
      "16": "icons/icon16.png",
      "32": "icons/icon32.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },
  "icons": {
    "16": "icons/icon16.png",
    "32": "icons/icon32.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}
```

### 2.2 Security & Deterministic Extension ID
1. **Public Key Guarantee**: The inclusion of the hardcoded `"key"` parameter ensures the extension receives the deterministic ID:
   `bnpmffibedppchkljkcaidgijekgfmgl` across all environments (both Chrome and Edge).
2. **Native Messaging Allowed Origins**: This deterministic ID matches `allowed_origins` in `tools/native_host/com.vkdub.bridge.json` and `src/vkdub/bridge/registry.py` exactly:
   `"allowed_origins": ["chrome-extension://bnpmffibedppchkljkcaidgijekgfmgl/"]`
3. **Cross-Origin Isolation**: Content script is restricted strictly to YouTube watch URLs, while native messaging permissions allow stdio communication only with registered binary host `com.vkdub.bridge`.

---

## 3. YouTube In-Player Toolbar Specification (`content/youtubeAdapter.js`)

### 3.1 YouTube Player DOM Anatomy
YouTube watch pages use a Polymer custom web component structure:
- Top-level page container: `ytd-watch-flexy`
- Player outer wrapper: `#player-container-outer` / `#player-container`
- Primary HTML5 Player container: `#movie_player` (has classes `html5-video-player`, `ytp-autohide`, `ytp-fullscreen`)
- Video element: `#movie_player video.html5-main-video`
- Native bottom control bar: `.ytp-chrome-bottom` (height ~48-56px, containing play/pause, volume, time display, chapter markings, subtitles, settings, theater mode, fullscreen)
- Native top header bar: `.ytp-chrome-top` (video title in fullscreen/embed)
- Timeline scrubber: `.ytp-progress-bar-container` -> `.ytp-progress-bar`

### 3.2 Non-Interfering Mounting Strategy
To satisfy **R1** ("không mở trang trung gian hay thay thế controls gốc của YouTube, không làm đè hay hỏng controls gốc Play, Volume, Settings, Fullscreen"):
1. **Mount Anchor**:
   The toolbar root element `<div id="vkdub-yt-clip-toolbar">` is mounted inside `#movie_player`.
   - In Normal Mode: Positioned floating at top-left/top-center (e.g., `top: 14px; left: 16px;`) or docked immediately above the native control bar (`bottom: 58px; left: 16px; right: 16px;`) with a maximum height of 38px.
   - In Fullscreen Mode: Because `#movie_player` enters native fullscreen (`z-index: 2147483647`), mounting inside `#movie_player` ensures the toolbar remains fully interactive in fullscreen without exiting.
2. **Shadow DOM Encapsulation**:
   ```javascript
   const host = document.createElement("div");
   host.id = "vkdub-yt-clip-toolbar";
   const shadow = host.attachShadow({ mode: "open" });
   ```
   Shadow DOM guarantees complete CSS style isolation:
   - YouTube styles (e.g. typography, reset rules, flex layouts) cannot leak into or distort toolbar buttons.
   - Extension CSS cannot leak into YouTube page or distort YouTube controls.
3. **Event Propagation Termination**:
   Clicks on YouTube's player area normally toggle play/pause or focus player controls. Every interactive element inside the toolbar shadow root MUST bind:
   ```javascript
   element.addEventListener("click", (e) => e.stopPropagation());
   element.addEventListener("mousedown", (e) => e.stopPropagation());
   element.addEventListener("mouseup", (e) => e.stopPropagation());
   ```
4. **Pointer Events Discipline**:
   - Toolbar container: `pointer-events: none;`
   - Toolbar interactive pill/buttons: `pointer-events: auto;`
   This allows transparent background areas of the player to register standard YouTube clicks and scrubs uninterrupted.

### 3.3 SPA Navigation & Duplicate Prevention Lifecycle
YouTube is a Single Page Application that navigates between videos without full page reloads.
1. **Lifecycle Event Hooks**:
   ```javascript
   window.addEventListener("yt-navigate-finish", handleYoutubeNavigation);
   window.addEventListener("yt-page-data-updated", handleYoutubeNavigation);
   window.addEventListener("popstate", handleYoutubeNavigation);
   ```
2. **Navigation State Machine**:
   - **Singleton Guard**: `window.__vkdubYoutubeAdapter` stores the active controller instance.
   - **Watch Page Detection**: Check `window.location.pathname === "/watch"` and presence of `v` query param. If not on a watch page (e.g. home feed, channel, search results), set toolbar visibility to `display: none` and pause tracking.
   - **Video Change Detection**: Compare `currentVideoId` with `new URLSearchParams(window.location.search).get("v")`.
     - When `videoId` changes:
       1. Clear active selection points: `clipStart = null; clipEnd = null;`.
       2. Rebind `<video>` element event listeners (`timeupdate`, `loadedmetadata`, `ended`). Old listeners are detached to avoid memory leaks.
       3. Extract fresh metadata: `title`, `duration`, `canonicalUrl`, `thumbnailUrl`.
       4. Dispatch `YOUTUBE_CONTEXT_SYNC` to background service worker and side panel.
       5. Update toolbar badges to idle state `--:--:--`.
       6. **Zero Duplicate Nodes**: If `#vkdub-yt-clip-toolbar` already exists in DOM, it is re-initialized in-place; no new DOM node is inserted.

### 3.4 In-Player Hotkeys Specification
The adapter registers a capturing-phase keyboard listener:
```javascript
window.addEventListener("keydown", handleKeydown, true);
```
**Pre-Flight Guard**:
```javascript
const activeEl = document.activeElement;
const isInput = activeEl && (
  ["INPUT", "TEXTAREA", "SELECT"].includes(activeEl.tagName) ||
  activeEl.isContentEditable ||
  activeEl.getAttribute("role") === "textbox"
);
if (isInput || e.ctrlKey || e.altKey || e.metaKey) return;
```

**Hotkey Definitions**:
| Key | Action | Technical Behavior | Conflict Handling |
|---|---|---|---|
| `I` / `i` | Set In-Point (Điểm đầu) | Sets `clipStart = video.currentTime`. Formats timecode badge. Updates timeline visual marker. If `clipEnd !== null && clipStart >= clipEnd`, resets `clipEnd = null`. | **Crucial YouTube Conflict**: YouTube natively binds `i` to toggle Miniplayer. Adapter MUST execute `e.preventDefault()` and `e.stopImmediatePropagation()` to intercept `i`. |
| `O` / `o` | Set Out-Point (Điểm cuối) | Sets `clipEnd = video.currentTime`. Formats timecode badge. Updates timeline visual marker. | Intercepts `e.preventDefault()`, `e.stopImmediatePropagation()`. |
| `Enter` | Add Clip (Thêm đoạn) | Validates clip boundaries (`start < end <= duration`, duration `>= 0.5s`). If valid, dispatches `YOUTUBE_CLIP_ADDED` to background/side panel, triggers in-player animated success toast, and resets `clipStart = null; clipEnd = null;`. | Intercepts `e.preventDefault()`. |
| `Escape` | Cancel / Reset (Hủy chọn) | Only triggers if `clipStart !== null` or `clipEnd !== null`. Resets `clipStart = null; clipEnd = null;` and clears timeline marker. | If no clip selection is active, passes `Escape` through so native YouTube fullscreen exit operates normally. |

### 3.5 Realtime Timecode Display & Scrubber Overlay
1. **Timecode Format Engine**:
   Standardized `HH:MM:SS.mmm` (e.g. `00:02:15.650`). If video duration is under 1 hour, display may omit hours `MM:SS.mmm` on compact displays, but full 3-decimal millisecond precision is preserved.
2. **60fps Render Throttling**:
   Rather than executing heavy DOM manipulations on every microsecond `timeupdate`, the adapter uses `requestAnimationFrame`:
   ```javascript
   function onTimeUpdate() {
     if (rafId) return;
     rafId = requestAnimationFrame(() => {
       updateTimecodeDisplays(video.currentTime);
       rafId = null;
     });
   }
   ```
3. **Timeline Highlight Overlay**:
   An overlay `div.vkdub-timeline-range` is injected into `.ytp-progress-bar`:
   - `left: (clipStart / duration * 100)%`
   - `width: ((clipEnd - clipStart) / duration * 100)%`
   - Styled with VK Dub brand blue accent gradient and rounded end caps.

---

## 4. Side Panel Clip Manager Specification (`apps/browser-extension/sidepanel/`)

### 4.1 Component File Hierarchy
```
apps/browser-extension/sidepanel/
├── index.html          # HTML5 Shell, Apple Dark/Light Layout, SVG Icons
├── sidepanel.css       # SF Pro / Apple Frosted Glass Styles, Spring Transitions
└── sidepanel.js        # State Controller, DnD, Inline Edit, Validation, IPC Bridge
```

### 4.2 Apple-Inspired Visual Architecture
The Side Panel adheres to modern macOS / iOS design guidelines:
- **Typography**: `-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Segoe UI", Roboto, sans-serif`
- **Color Palette**:
  - Dark Surface: `rgba(28, 28, 30, 0.85)` with `backdrop-filter: blur(25px)`
  - Card Background: `rgba(44, 44, 46, 0.75)` with subtle 1px border `rgba(255, 255, 255, 0.08)`
  - Accent Primary: `#0A84FF` (Apple System Blue)
  - Success Green: `#30D158`
  - Warning Amber: `#FFD60A`
  - Destructive Red: `#FF453A`
- **Motion**: 200ms - 300ms cubic-bezier springs (`cubic-bezier(0.16, 1, 0.3, 1)`) for list reordering, drawer expansion, and toast notifications.

### 4.3 UI Functional Layout & Subsystems
1. **Header & Context Card**:
   - Connection Badge: Live indicator of Local Agent status (`Đã kết nối` / `Mất kết nối`).
   - Current Video Card:
     - 16:9 Thumbnail image (`https://i.ytimg.com/vi/${videoId}/mqdefault.jpg`)
     - Truncated Video Title with full title tooltip
     - Video ID Monospace Tag (`v=...`)
     - Total Duration badge (`HH:MM:SS`)
2. **Clip Manager Toolbar**:
   - Counter: `N đoạn đã chọn / Tổng thời lượng`
   - Batch Checkbox: Select All / Deselect All
   - Sort & Reorder actions
   - Clear All action with confirmation
3. **Draggable Clip Card**:
   - **Grip Handle**: `⋮⋮` SVG icon with `draggable="true"` supporting native HTML5 Drag and Drop reordering.
   - **Selection Checkbox**: Independent toggle for export inclusion.
   - **Editable Clip Name**: Click/double-click to rename clip (defaults to `Clip 1`, `Clip 2`...).
   - **Timecode Badges**:
     - `Start`: Inline clickable pill displaying `HH:MM:SS.mmm`.
     - `End`: Inline clickable pill displaying `HH:MM:SS.mmm`.
     - `Duration`: Pill calculation `Δ (end - start).toFixed(1)s`.
   - **Card Action Buttons**:
     - `Seek / Preview` (Play icon): Seeks YouTube player to `start`, starts playback, and auto-pauses at `end`.
     - `Delete` (Trash icon): Removes clip from list with undo toast.
     - `Duplicate` (Clone icon): Creates an identical or offset copy of clip.
4. **Client-Side Validation Engine**:
   Before creating or exporting any clip, strict client-side validation executes:
   - `start >= 0` (non-negative start timestamp)
   - `end <= videoDuration` (cannot exceed source duration)
   - `start < end` (start must precede end)
   - `(end - start) >= 0.5` (minimum 0.5 seconds duration to prevent 0-frame FFmpeg glitches)
   - **Duplicate Detection**: A clip is flagged as duplicate if another clip has `|c.start - start| < 0.1` and `|c.end - end| < 0.1`.
   - **Error Handling**: Invalid cards display a red border with error tooltip and disable the "Bắt đầu xuất" (Export) action button until resolved.
5. **Inline Timecode Parser**:
   Accepts flexible user input formats:
   - Seconds: `85.4` -> `00:01:25.400`
   - `MM:SS`: `02:15` -> `00:02:15.000`
   - `MM:SS.mmm`: `01:30.500` -> `00:01:30.500`
   - `HH:MM:SS.mmm`: `01:05:22.100` -> `01:05:22.100`
   On blur/Enter, input is validated and reformatted. If invalid, the field shakes and reverts to previous value.
6. **Export Configuration Drawer**:
   - **Output Mode**:
     - `SEPARATE_FILES`: Export each selected clip as an individual video file (`{title}_clip_{i}_{start}-{end}.{ext}`).
     - `MERGE_ALL`: Concatenate all selected clips in list order into a single video (`{title}_selected_clips.{ext}`).
     - `IMPORT_TO_STUDIO`: Cut clips and automatically load into ToolVideo timeline for AI dubbing.
   - **Container**: `mp4` | `mkv` (default `mp4`).
   - **Quality**: `best` (default), `2160p`, `1440p`, `1080p`, `720p`.
   - **Cut Mode**:
     - `STREAM_COPY` ("Siêu nhanh – không re-encode, giữ nguyên bitrate gốc, snap keyframe gần nhất").
     - `FRAME_ACCURATE` ("Chính xác từng khung hình – tự động dùng phần cứng NVENC/QSV/AMF, fallback libx264").
   - **Output Directory Picker**: Shows current destination folder, button to choose directory.
   - **Cookie Toggle**: "Sử dụng cookie trình duyệt (cookies-from-browser)" checkbox, unchecked by default with security clarification.
7. **Realtime Export Progress Bar & Telemetry**:
   - Stage indicators: `Kiểm tra nguồn` -> `Tải video/audio` -> `Ghép nguồn` -> `Đang cắt clip K/N` -> `Đang ghép` -> `Hoàn tất`.
   - Metrics: Download speed (`MB/s`), downloaded bytes / total bytes, percentage (0-100%).
   - Action buttons during/after export:
     - `Hủy xuất` (`CLIP_EXPORT_CANCEL`): immediately terminates subprocesses and cleans temporary files.
     - `Mở thư mục` (`OPEN_OUTPUT_FOLDER`): opens Windows Explorer at output destination.
     - `Đưa vào ToolVideo` (`IMPORT_TO_STUDIO`): dispatches clip to Web UI timeline.
8. **Persistence & Session Restoration**:
   - Clips saved in `chrome.storage.local` under `clips_${videoId}`.
   - Active job state saved under `active_export_job`. If the user closes and re-opens the side panel mid-export, the UI immediately restores the live progress bar and status.

---

## 5. Realtime Protocol & Native Bridge Communication Specification (R5)

### 5.1 Transport Architecture
- **Primary Transport**: Direct WebSocket `ws://127.0.0.1:49814/ws` (handled by `bridge/nativeMessaging.js`).
- **Secondary Fallback Transport**: Stdio Native Messaging host `com.vkdub.bridge` via `chrome.runtime.connectNative`.

### 5.2 Action Constants & Payload Schemas

#### 1. `YOUTUBE_CONTEXT_SYNC` (Content Script -> Background -> Side Panel)
Sent when a YouTube watch page loads or navigates to a new video:
```json
{
  "action": "YOUTUBE_CONTEXT_SYNC",
  "payload": {
    "video_id": "dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up",
    "duration": 213.0,
    "current_time": 45.2,
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
  }
}
```

#### 2. `YOUTUBE_CLIP_ADDED` (Content Script -> Background -> Side Panel)
Sent when user presses `Enter` or clicks "Thêm đoạn" in player:
```json
{
  "action": "YOUTUBE_CLIP_ADDED",
  "payload": {
    "id": "clip_cl8491x920",
    "video_id": "dQw4w9WgXcQ",
    "name": "Clip 1",
    "start": 12.500,
    "end": 45.200,
    "duration": 32.700,
    "selected": true
  }
}
```

#### 3. `YOUTUBE_SEEK_TO` (Side Panel -> Content Script)
Seeks the active YouTube player to a specific timestamp:
```json
{
  "action": "YOUTUBE_SEEK_TO",
  "payload": {
    "time": 12.500,
    "play": true
  }
}
```

#### 4. `YOUTUBE_PREVIEW_CLIP` (Side Panel -> Content Script)
Plays the selected clip range and pauses at the end:
```json
{
  "action": "YOUTUBE_PREVIEW_CLIP",
  "payload": {
    "start": 12.500,
    "end": 45.200
  }
}
```

#### 5. `CLIP_EXPORT_REQUEST` (Side Panel -> Background -> Local Agent)
Dispatched when user clicks "Bắt đầu xuất":
```json
{
  "action": "CLIP_EXPORT_REQUEST",
  "payload": {
    "request_id": "req_84920481",
    "video_id": "dQw4w9WgXcQ",
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "video_title": "Rick Astley - Never Gonna Give You Up",
    "output_mode": "SEPARATE_FILES",
    "output_format": "mp4",
    "quality": "best",
    "cut_mode": "STREAM_COPY",
    "output_dir": "D:\\Work\\Project_AI\\ToolVideo\\output",
    "use_cookies": false,
    "clips": [
      {
        "id": "clip_cl8491x920",
        "index": 1,
        "name": "Clip 1",
        "start": 12.500,
        "end": 45.200,
        "duration": 32.700
      }
    ]
  }
}
```

#### 6. `CLIP_EXPORT_ACCEPTED` (Local Agent -> Background -> Side Panel)
Confirms job was accepted and queued:
```json
{
  "action": "CLIP_EXPORT_ACCEPTED",
  "payload": {
    "request_id": "req_84920481",
    "status": "QUEUED",
    "timestamp": 1741334510000
  }
}
```

#### 7. `CLIP_EXPORT_PROGRESS` (Local Agent -> Background -> Side Panel)
Streams realtime progress updates:
```json
{
  "action": "CLIP_EXPORT_PROGRESS",
  "payload": {
    "request_id": "req_84920481",
    "stage": "DOWNLOADING_SOURCE",
    "current_clip": 1,
    "total_clips": 1,
    "download_progress": 64.5,
    "download_speed": "12.8 MB/s",
    "downloaded_bytes": 45892014,
    "total_bytes": 71148592,
    "eta_seconds": 2,
    "overall_progress": 42.0,
    "message": "Đang tải nguồn video (64.5% - 12.8 MB/s)"
  }
}
```

#### 8. `CLIP_EXPORT_RESULT` (Local Agent -> Background -> Side Panel)
Sent when export completes successfully:
```json
{
  "action": "CLIP_EXPORT_RESULT",
  "payload": {
    "request_id": "req_84920481",
    "success": true,
    "output_files": [
      "D:\\Work\\Project_AI\\ToolVideo\\output\\Rick_Astley_clip_1_12.5-45.2.mp4"
    ],
    "merged_file": null,
    "output_directory": "D:\\Work\\Project_AI\\ToolVideo\\output"
  }
}
```

#### 9. `CLIP_EXPORT_ERROR` (Local Agent -> Background -> Side Panel)
Sent when export fails:
```json
{
  "action": "CLIP_EXPORT_ERROR",
  "payload": {
    "request_id": "req_84920481",
    "success": false,
    "error": "Lỗi FFmpeg: Codec không tương thích với container mkv."
  }
}
```

#### 10. `CLIP_EXPORT_CANCEL` (Side Panel -> Background -> Local Agent)
Cancels active export and kills subprocesses:
```json
{
  "action": "CLIP_EXPORT_CANCEL",
  "payload": {
    "request_id": "req_84920481"
  }
}
```

#### 11. `OPEN_OUTPUT_FOLDER` (Side Panel -> Background -> Local Agent)
Requests host to open output folder in Windows Explorer:
```json
{
  "action": "OPEN_OUTPUT_FOLDER",
  "payload": {
    "folder_path": "D:\\Work\\Project_AI\\ToolVideo\\output"
  }
}
```

#### 12. `IMPORT_TO_STUDIO` (Side Panel -> Background -> Local Agent)
Directly imports the exported clip into ToolVideo Web App Step 1:
```json
{
  "action": "IMPORT_TO_STUDIO",
  "payload": {
    "file_path": "D:\\Work\\Project_AI\\ToolVideo\\output\\Rick_Astley_clip_1_12.5-45.2.mp4"
  }
}
```

---

## 6. Installation, Native Messaging Registration & Extension Packaging Tooling

### 6.1 Windows Registry Keys
Chromium Native Messaging requires host registration under `HKCU`:
- **Microsoft Edge**:
  `HKEY_CURRENT_USER\Software\Microsoft\Edge\NativeMessagingHosts\com.vkdub.bridge`
- **Google Chrome**:
  `HKEY_CURRENT_USER\Software\Google\Chrome\NativeMessagingHosts\com.vkdub.bridge`

Both registry keys point to the exact manifest path generated dynamically by `src/vkdub/bridge/registry.py`:
`%LOCALAPPDATA%\VKDubStudio\native_host\com.vkdub.bridge.json`

### 6.2 Host Manifest Schema (`com.vkdub.bridge.json`)
```json
{
  "name": "com.vkdub.bridge",
  "description": "VK Dub Studio Native Messaging Bridge Host",
  "path": "D:\\Work\\Project_AI\\ToolVideo\\tools\\native_host\\vkdub_host.bat",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://bnpmffibedppchkljkcaidgijekgfmgl/"
  ]
}
```

### 6.3 Packaging & Installation Workflow
1. **Developer Mode Unpacked Installation**:
   - Google Chrome: Navigate to `chrome://extensions/` -> Enable "Developer mode" -> Click "Load unpacked" -> Select `apps/browser-extension/`.
   - Microsoft Edge: Navigate to `edge://extensions/` -> Enable "Developer mode" -> Click "Load unpacked" -> Select `apps/browser-extension/`.
2. **Registration Verification Tool**:
   `python tools/native_host/register_host.py --check`
   Outputs:
   ```
     Microsoft Edge: REGISTERED
     Google Chrome: REGISTERED
   ```
3. **Automated Live Reload**:
   When developers update extension code, triggering `Actions.RELOAD_EXTENSION` via the bridge causes `serviceWorker.js` to execute `chrome.runtime.reload()`, refreshing background worker and all adapters instantly.

---

## 7. Preservation of Existing Features (ChatGPT & Vbee)

To guarantee zero regression for existing automation:
1. **Namespace Isolation**:
   All new YouTube actions (`YOUTUBE_*`, `CLIP_EXPORT_*`) are isolated and do not collide with `CHATGPT_*` or `VBEE_*` actions in `protocol.js` and `serviceWorker.js`.
2. **Tab Query Matcher Isolation**:
   `serviceWorker.js` uses separate tab matchers:
   - `isChatGPTTab(t)` matches `chatgpt.com`, `chat.openai.com`
   - `isVbeeTab(t)` matches `vbee.vn`, `studio.vbee.vn`
   - `isYouTubeTab(t)` matches `youtube.com/watch`
   State queries and cookie queries for ChatGPT/Vbee remain completely intact and unaffected.
3. **Dual Hybrid Communication**:
   The WebSocket and Native Port connection handling in `bridge/nativeMessaging.js` is untouched, retaining full bidirectional framing, auto-reconnect, and error recovery.

---

## 8. Authoritative Feature Discovery & Edge Cases Tables

### 8.1 Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Manifest V3 | Side Panel Permission & Declaration | Enables Side Panel API in MV3 Chrome/Edge with `sidepanel/index.html` entry | `manifest.json` config | Browser Side Panel registration | Chrome throws manifest error if permissions or schema is invalid | MV3 Standard & `ORIGINAL_REQUEST.md` R2, R6 |
| 2 | Manifest V3 | YouTube Host Permissions | Enables content script injection and fetch on YouTube domains | `*://*.youtube.com/*`, `*://youtube.com/*` | Access to YouTube DOM and network requests | Content script blocked without host permissions | `manifest.json` & `ORIGINAL_REQUEST.md` R1, R6 |
| 3 | Manifest V3 | Deterministic RSA Public Key | Preserves fixed Extension ID `bnpmffibedppchkljkcaidgijekgfmgl` across Chrome and Edge | RSA public key string in `manifest.json` | Uniform extension ID across browsers | Origin mismatch in `com.vkdub.bridge.json` rejects native messaging | `apps/browser-extension/manifest.json:6` & `tools/native_host/com.vkdub.bridge.json` |
| 4 | In-Player Toolbar | Shadow DOM Isolation | Renders toolbar in Shadow Root inside `#movie_player` to prevent CSS cross-contamination | YouTube player DOM `#movie_player` | Encapsulated custom element `#vkdub-yt-clip-toolbar` | None; fallback to scoped DOM if Shadow DOM unsupported | `ORIGINAL_REQUEST.md` R1 & DOM Analysis |
| 5 | In-Player Toolbar | Pointer & Click Event Isolation | Stops click and mousedown propagation on toolbar buttons to avoid pausing YouTube video | Click / mousedown events on toolbar buttons | `e.stopPropagation()` called | If unhandled, clicking toolbar buttons toggles YouTube video playback | `ORIGINAL_REQUEST.md` R1 Acceptance Criteria |
| 6 | In-Player Toolbar | In-Player Hotkey `I` (Mark In) | Sets segment start timestamp to `video.currentTime` and updates visual badge | Keydown event `'i'` / `'I'` | `clipStart = video.currentTime`; badge updated | Intercepts `e.preventDefault()`, `e.stopImmediatePropagation()` to override YouTube Miniplayer toggle | `ORIGINAL_REQUEST.md` R1 |
| 7 | In-Player Toolbar | In-Player Hotkey `O` (Mark Out) | Sets segment end timestamp to `video.currentTime` and updates visual badge | Keydown event `'o'` / `'O'` | `clipEnd = video.currentTime`; badge updated | Intercepts `e.preventDefault()` | `ORIGINAL_REQUEST.md` R1 |
| 8 | In-Player Toolbar | In-Player Hotkey `Enter` (Add Clip) | Validates timestamps and creates new clip in storage & Side Panel | Keydown event `'Enter'` | `YOUTUBE_CLIP_ADDED` message; toast notification; resets markers | Disables action and flashes warning toast if `start >= end` or bounds invalid | `ORIGINAL_REQUEST.md` R1 |
| 9 | In-Player Toolbar | In-Player Hotkey `Escape` (Cancel) | Cancels active marker selection and clears timeline overlay | Keydown event `'Escape'` | `clipStart = null; clipEnd = null;` | Only intercepts if clip selection active; otherwise allows native YouTube fullscreen exit | `ORIGINAL_REQUEST.md` R1 |
| 10 | In-Player Toolbar | Typing Focus Guard | Bypasses all hotkeys when user is focused in an input, textarea, or contenteditable element | Keydown events on active inputs | Native typing behavior preserved | Prevents accidental clipping while user writes comments or searches | YouTube DOM Analysis & Hotkey Guard Pattern |
| 11 | In-Player Toolbar | SPA Navigation Handler | Hooks `yt-navigate-finish` to update video metadata and rebind video element without duplicate toolbars | YouTube custom SPA event `yt-navigate-finish` | Updated toolbar state & `YOUTUBE_CONTEXT_SYNC` dispatch | Re-uses existing DOM node; avoids duplicate overlays | `ORIGINAL_REQUEST.md` R1 Acceptance Criteria |
| 12 | In-Player Toolbar | 60fps Timecode Tracker | Throttles high-frequency timecode badge updates using `requestAnimationFrame` | HTMLVideoElement `timeupdate` | Formatted `HH:MM:SS.mmm` display | Fallbacks gracefully if video duration is `NaN` or unready | `ORIGINAL_REQUEST.md` R1 |
| 13 | In-Player Toolbar | Timeline Scrubber Overlay | Draws colored selection bar on YouTube's `.ytp-progress-bar` | `clipStart`, `clipEnd`, `video.duration` | Highlight element inserted into progress bar | Hidden when markers are reset | YouTube Player DOM Analysis |
| 14 | Side Panel | Video Info Header Card | Displays current YouTube video thumbnail, title, video ID, and duration | `YOUTUBE_CONTEXT_SYNC` payload | Rendered card with thumbnail and title tooltip | Displays empty state when no YouTube watch tab is open | `ORIGINAL_REQUEST.md` R2 |
| 15 | Side Panel | Draggable Clip List | Displays all marked clips with drag handle for reordering | Array of clips from storage | Draggable DOM cards with visual drop indicators | Preserves order on re-render | `ORIGINAL_REQUEST.md` R2 |
| 16 | Side Panel | Inline Timecode Editing | Allows double-clicking start or end timecode to type custom values | User text input (`MM:SS.mmm`, `HH:MM:SS.mmm`, seconds) | Parsed float seconds; formatted badge | Reverts with shake animation if `start >= end` or exceeds duration | `ORIGINAL_REQUEST.md` R2 |
| 17 | Side Panel | Inline Clip Renaming | Allows clicking clip name to give custom descriptive label | User text input | Updated `clip.name` saved to storage | Sanitizes invalid Windows filename characters | `ORIGINAL_REQUEST.md` R2 |
| 18 | Side Panel | Seek / Preview Clip | Jumps YouTube player to clip start and auto-pauses when reaching clip end | Click on Preview button | `YOUTUBE_PREVIEW_CLIP` sent to content script | Notifies user if YouTube tab was closed | `ORIGINAL_REQUEST.md` R2 |
| 19 | Side Panel | Client-Side Bounds Validation | Blocks export and highlights card if `start >= end`, `start < 0`, or `end > duration` | Clip start, end, video duration | Red validation border & tooltip error | Disables export button until errors resolved | `ORIGINAL_REQUEST.md` R2 |
| 20 | Side Panel | Duplicate Clip Prevention | Detects and prevents duplicate segments within 0.1s threshold | Clip start, end vs existing clips | Warning toast: "Đoạn cắt đã tồn tại" | Rejects duplicate addition | `ORIGINAL_REQUEST.md` R2 |
| 21 | Side Panel | Batch Selection Controls | Select all, deselect all, or toggle individual clips for export | Checkbox clicks | Updates `selected` boolean in state | Export button disabled if 0 clips selected | `ORIGINAL_REQUEST.md` R2 |
| 22 | Side Panel | Export Mode Selection | Choose between Separate Files, Merge All, or Direct Import to Studio | User radio selection | Sets `output_mode` parameter in export payload | Defaults to `SEPARATE_FILES` | `ORIGINAL_REQUEST.md` R3 |
| 23 | Side Panel | Container & Cut Mode Settings | Configure container (`mp4`/`mkv`), Quality preset, and Cut mode (`STREAM_COPY`/`FRAME_ACCURATE`) | User dropdown choices | Sets export config in payload | Explanatory note displayed for stream copy vs re-encode | `ORIGINAL_REQUEST.md` R3 |
| 24 | Side Panel | Realtime Telemetry Dashboard | Renders live progress bar, stage indicator, speed MB/s, downloaded bytes, ETA | `CLIP_EXPORT_PROGRESS` events | Animated progress bar & live metrics | Displays error message banner on `CLIP_EXPORT_ERROR` | `ORIGINAL_REQUEST.md` R5 |
| 25 | Side Panel | Job Cancellation Trigger | Sends cancel signal to Local Agent to terminate subprocesses | User clicks "Hủy xuất" | `CLIP_EXPORT_CANCEL` sent to host | Local Agent kills yt-dlp/ffmpeg and removes temp files | `ORIGINAL_REQUEST.md` R4, R5 |
| 26 | Side Panel | Session State Restoration | Persists active job ID and progress in `chrome.storage.local` | Storage read on side panel load | Resumes telemetry if side panel re-opened | Resets to idle if job is marked complete or canceled | `ORIGINAL_REQUEST.md` R5 |
| 27 | Side Panel | Open Output Folder Action | Invokes native shell to open folder containing exported files | User clicks "Mở thư mục" | `OPEN_OUTPUT_FOLDER` sent to host | Host runs `os.startfile` on output directory | `ORIGINAL_REQUEST.md` R3, R5 |
| 28 | Native Host | Dynamic Manifest Setup | Dynamically generates manifest JSON in `LOCALAPPDATA` with absolute path to `vkdub_host.bat` | `src/vkdub/bridge/registry.py` | `com.vkdub.bridge.json` created in `%LOCALAPPDATA%` | Logs warning if `vkdub_host.bat` not found | `src/vkdub/bridge/registry.py:47-80` |
| 29 | Native Host | Dual Windows Registry Setup | Registers host for both Edge and Chrome in HKCU | `register_host.py` / `ensure_host_registered()` | Keys created in Edge & Chrome registry paths | Skipped on non-Windows platforms with warning | `src/vkdub/bridge/registry.py:82-132` |
| 30 | Backend | Status Endpoint Extension | Exposes bridge and YouTube extension connection status to web frontend | GET `/api/bridge/status` | JSON `{ connected, chatgpt, vbee, youtube }` | Returns `{ connected: false }` if agent offline | `src/vkdub/web/server.py:252-260` |

---

### 8.2 Edge Cases & Observed / Specified Behaviors

| # | Feature | Input / Scenario | Observed / Specified Behavior |
|---|---------|------------------|-------------------------------|
| 1 | In-Player Hotkeys | User presses `i` while video is playing | In YouTube, `i` normally toggles the Miniplayer. `youtubeAdapter.js` intercepts `i` in the capturing phase (`useCapture: true`), calls `e.preventDefault()` and `e.stopImmediatePropagation()`, and records `clipStart = video.currentTime` without triggering the Miniplayer. |
| 2 | In-Player Hotkeys | User types in YouTube comment box or search bar | Focus element is `<textarea>` or `<input>`. Pre-flight guard checks `document.activeElement`. Hotkeys `I`, `O`, `Enter`, `Esc` are ignored; standard text input behavior is preserved. |
| 3 | In-Player Hotkeys | User presses `Ctrl+I`, `Alt+I`, `Ctrl+Enter` | Modifier keys `e.ctrlKey || e.altKey || e.metaKey` are detected. Hotkey handler immediately returns without modifying clip markers. |
| 4 | In-Player Hotkeys | User presses `Escape` with no markers active | When `clipStart === null && clipEnd === null`, `Escape` is passed through untouched, allowing native YouTube behavior (e.g. exit fullscreen mode). |
| 5 | In-Player Hotkeys | User presses `Escape` with active markers | When markers exist, `Escape` clears markers and resets toolbar display; `e.stopPropagation()` is called so YouTube does not exit fullscreen. |
| 6 | In-Player Hotkeys | User presses `Enter` with only `clipStart` set | `clipEnd` automatically defaults to `video.currentTime` (if current > start) or `video.duration`. If valid, clip is saved. |
| 7 | In-Player Hotkeys | User presses `Enter` with neither marker set | Action is rejected. In-player toast notification appears: "Vui lòng đặt điểm đầu [I] hoặc điểm cuối [O]". |
| 8 | SPA Navigation | User clicks related video (URL changes `/watch?v=A` -> `/watch?v=B`) | `yt-navigate-finish` event fires. Video ID changes. Single-instance controller detects ID change, resets active markers, rebinds video element listeners, and updates metadata without creating a second toolbar overlay. |
| 9 | SPA Navigation | User navigates from watch page to Home or Subscriptions feed | URL is no longer `/watch`. Controller detects non-watch route, hides toolbar (`display: none`), unbinds video listeners, and notifies Side Panel that no video is active. |
| 10 | Player Fullscreen | User enters fullscreen (`f` key or button) | `#movie_player` enters native fullscreen (`z-index: 2147483647`). Because `#vkdub-yt-clip-toolbar` is mounted inside `#movie_player`, it remains visible and usable in fullscreen mode. |
| 11 | Player Autohide | User mouse goes idle for 3 seconds | YouTube adds `.ytp-autohide` class to `#movie_player`. Toolbar applies smooth opacity fade-out (`opacity: 0.15` or `0`), restoring full opacity immediately upon `mousemove`. |
| 12 | Video Advertisements | Pre-roll or mid-roll ad begins playing | `#movie_player` gains `.ad-showing` class. Toolbar detects ad state, disables clipping markers, and displays "Đang phát quảng cáo...". Markers re-enable when ad completes or is skipped. |
| 13 | Live Stream Video | User opens a YouTube Live broadcast | Video duration is `Infinity` or `NaN`. Toolbar detects `!Number.isFinite(duration)` and displays `[LIVE]` badge, disabling clipping with tooltip: "Cắt video trực tiếp được hỗ trợ sau khi buổi phát kết thúc." |
| 14 | Clip Validation | User sets Start time greater than End time (`start >= end`) | Creation is blocked. Inline red highlight appears on the card with message: "Thời gian bắt đầu phải nhỏ hơn thời gian kết thúc". Export button is disabled. |
| 15 | Clip Validation | User manually edits timecode beyond video duration (`end > duration`) | Validation clamps value to `video.duration` or flags error: "Thời gian kết thúc vượt quá thời lượng video". |
| 16 | Clip Validation | Sub-second floating point rounding (`0.1 + 0.2 = 0.30000000000000004`) | All math is rounded using `Math.round(val * 1000) / 1000` to guarantee exactly 3 decimal places without IEEE 754 precision drift. |
| 17 | Clip Validation | Very short clip segment (`end - start < 0.5s`) | Enforces minimum duration threshold: `(end - start) >= 0.5s`. Rejects with error: "Thời lượng đoạn cắt tối thiểu là 0.5 giây". |
| 18 | Clip Validation | User adds an identical segment twice | Duplicate detector compares `|c.start - start| < 0.1 && |c.end - end| < 0.1`. Rejects with toast: "Đoạn cắt này đã tồn tại trong danh sách." |
| 19 | Drag and Drop | User drags Clip 3 above Clip 1 | HTML5 DnD reorders the `clips` array in memory and saves to `chrome.storage.local`. When exporting with `MERGE_ALL`, clips are concatenated in this updated sequence. |
| 20 | Timecode Parsing | User inputs raw seconds `95.5` into timecode field | Parser interprets `95.5` as 95.5 seconds, formatting it into `00:01:35.500`. |
| 21 | Timecode Parsing | User inputs invalid string `abc:xyz` | Parser rejects string, shakes input field, and restores the previous valid timecode. |
| 22 | Side Panel Close | User closes Side Panel during export | Service Worker and Local Agent continue export uninterrupted in background. Re-opening Side Panel reads `active_export_job` from `chrome.storage.local` and seamlessly restores the live progress bar. |
| 23 | Export Cancel | User clicks "Hủy xuất" mid-download | `CLIP_EXPORT_CANCEL` is sent with `request_id`. Local Agent kills active `yt-dlp` / `ffmpeg` subprocesses, deletes temporary `.part` files, cleans temp directory, and sends confirmation. |
| 24 | Desktop Disconnect | ToolVideo app or Local Agent is closed while extension is open | Side Panel displays amber badge "Mất kết nối với VK Dub Studio". Export button is disabled with prompt to launch ToolVideo. Auto-reconnect timer attempts reconnection every 2-15 seconds. |
| 25 | Dual Browser Compat | Extension loaded unpacked in Google Chrome and Microsoft Edge | Manifest V3 loaded with 0 warnings/errors in both browsers. The RSA public key ensures identical extension ID `bnpmffibedppchkljkcaidgijekgfmgl` in both, matching `allowed_origins` in native host manifest. |

---

## 9. Verification & Delivery Methods

To independently verify all specifications in this report:
1. **Manifest V3 Validation**:
   Inspect `apps/browser-extension/manifest.json`. Verify permissions include `"sidePanel"`, host permissions include `"*://*.youtube.com/*"`, and content script registers `content/youtubeAdapter.js`.
2. **Registry Keys Verification**:
   Run `python tools/native_host/register_host.py --check`. Both Edge and Chrome should report `REGISTERED`.
3. **Bridge Protocol Unit Tests**:
   Run `$env:PYTHONPATH="src"; & "D:\Work\Project_AI\ToolVideo\.venv\Scripts\python.exe" -m pytest tests/test_bridge_protocol.py tests/test_native_messaging_framing.py -v`. All tests pass 100%.
4. **Coexistence Check**:
   Inspect `apps/browser-extension/background/serviceWorker.js` to ensure `handleChatGPTTranslate` and `handleVbeeGenerate` routes remain intact.
