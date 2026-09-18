# Milestone M4 Implementation: YouTube In-Player Toolbar & Clip Marker

Read `D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md` (specifically ## 2026-09-15T04:12:10Z), `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_2\PROJECT.md`, and Explorer 2's report in `.agents/teamwork_preview_spec_miner_survey_ext/report.md`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Write Ownership
You exclusively own:
- `apps/browser-extension/content/youtubeAdapter.js`
You may read: all files in `apps/browser-extension/`.

## Objective & Tasks
Implement `apps/browser-extension/content/youtubeAdapter.js` as the production content script for YouTube:
1. **DOM Mounting & Shadow DOM**:
   - Mount toolbar inside `#movie_player` or beside `.ytp-chrome-bottom` without covering or breaking native YouTube player controls (Play, Volume, Progress bar, Settings, Fullscreen).
   - Use Shadow DOM encapsulation for toolbar elements to prevent CSS bleeding and conflicts.
   - Attach `e.stopPropagation()` on toolbar buttons and controls to prevent accidental video play/pause toggle.
2. **Keyboard Hotkeys**:
   - `I` (Mark Start point): Capture in capturing phase (`useCapture: true`) with `e.preventDefault()` and `e.stopImmediatePropagation()` to strictly override YouTube native Miniplayer shortcut!
   - `O` (Mark End point).
   - `Enter` (Add Clip to collection).
   - `Escape` (Cancel / Clear current selection).
   - Input protection: Do NOT trigger hotkeys when user is focused in `input`, `textarea`, or `contenteditable` elements.
3. **HTMLVideoElement & YouTube Context Binding**:
   - Query and bind to active `HTMLVideoElement`.
   - Read `currentTime`, `duration`, `videoId` (from URL `v=` or `ytd-watch-flexy`), video title (`document.title` or `h1.ytd-watch-metadata`), canonical URL.
   - Synchronize context via `chrome.runtime.sendMessage` with action `Actions.YOUTUBE_CONTEXT_SYNC` or extension storage.
4. **SPA Navigation & Singleton Protection**:
   - Singleton instance guard: `window.__vkdubYoutubeAdapter`.
   - Listen to `yt-navigate-finish` and `yt-page-data-updated` (and `MutationObserver` on URL/title) to seamlessly transition when user clicks suggested videos without F5 refresh.
   - Rebind video element and reset markers on navigation without creating duplicate toolbar overlays or multiple listeners.
5. **Seek & Preview Handlers**:
   - Listen to runtime messages from Side Panel: `Actions.YOUTUBE_SEEK_TO` (seek `video.currentTime`) and `Actions.YOUTUBE_PREVIEW_CLIP` (seek to `start`, play, and auto-pause when reaching `end`).
6. **Timecode Display & Scrubber Overlay**:
   - Format timecode as `HH:MM:SS.mmm` or `MM:SS.mmm`.
   - Visual feedback on player when In / Out points are marked.
7. Verify syntax using `node --check apps/browser-extension/content/youtubeAdapter.js`.
8. Deliver `handoff.md` and message parent when complete.

## 2026-09-15T04:33:11Z
Task dispatched:
Worker M4 (YouTube In-Player Toolbar & Clip Marker).
Owner: apps/browser-extension/content/youtubeAdapter.js
Target: Implement non-intrusive toolbar in #movie_player with Shadow DOM, capturing hotkeys (I, O, Enter, Escape) overriding miniplayer, input protection, video context binding and sync, SPA navigation handling, runtime seek & preview handlers, timecode display and scrubber overlay.
