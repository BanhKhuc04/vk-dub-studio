# Survey Task: Extension UI & YouTube In-Player Spec Mining

Read `D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md` (specifically ## 2026-09-15T04:12:10Z).

## Objective
Investigate `apps/browser-extension/` (or current extension root), its `manifest.json`, background service worker, popup/sidepanel, content scripts.
Extract precise technical requirements and specifications for:
1. YouTube In-Player Toolbar (`youtubeAdapter.js`):
   - In-player mounting without interfering with native YouTube controls (Play, Volume, Settings, Fullscreen).
   - Timecode display, hotkeys `I`, `O`, `Enter`, `Escape`.
   - Interaction with `HTMLVideoElement` (`currentTime`, `duration`), `videoId`, title, canonical URL.
   - SPA navigation handling (`yt-navigate-finish`, URL observer) preventing duplicate overlays.
2. Side Panel Clip Manager (`apps/browser-extension/sidepanel/`):
   - Clip list, thumbnail/title/duration, timecode editing, rename, delete, drag-and-drop reorder, toggle selection.
   - Client-side validation (`start < end <= duration`, duplicate prevention).
   - Communication with content script (seek/preview) and background/native host (export triggers).
3. Extension packaging and manifest updates (MV3 `sidePanel`, permissions, host permissions `*://*.youtube.com/*`).

Write your comprehensive specification report to `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_spec_miner_survey_ext\report.md` and deliver `handoff.md`.

## 2026-09-15T04:13:54Z
You are Explorer 2 (teamwork_preview_spec_miner for Extension UI & YouTube In-Player Toolbar & Side Panel).
Working directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_spec_miner_survey_ext
Project root: D:\Work\Project_AI\ToolVideo
Authoritative request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md (specifically ## 2026-09-15T04:12:10Z).
Your dispatch assignment: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_spec_miner_survey_ext\DISPATCH.md

Tasks:
1. Thoroughly investigate `apps/browser-extension/` (or current extension location), `manifest.json`, content scripts, background worker, popup/sidepanel.
2. Extract exact technical specifications for YouTube In-Player Toolbar (`youtubeAdapter.js`): mounting, hotkeys I/O/Enter/Esc, video element binding, SPA `yt-navigate-finish` handling without duplicate overlays.
3. Extract exact specifications for Side Panel Clip Manager (`apps/browser-extension/sidepanel/`): clip list, thumbnail, title, video ID, duration, timecode editing, rename, delete, drag-and-drop reorder, toggle select, validation (start < end <= duration, duplicate prevention), preview seek.
4. Extract requirements for extension installation/packaging and manifest permissions (`sidePanel`, `*://*.youtube.com/*`).
5. Write your comprehensive specification report to `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_spec_miner_survey_ext\report.md` and deliver `handoff.md`.
6. When done, send a message to parent summarizing key findings and report paths.
