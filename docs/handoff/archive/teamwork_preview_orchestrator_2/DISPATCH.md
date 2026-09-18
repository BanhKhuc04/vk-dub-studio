## 2026-09-15T04:13:10Z

Develop, integrate, and verify the complete "YouTube Clip Mode" and Extension Installation/Update Tooling for VK Dub Studio per requirements R1 through R7 and all Acceptance Criteria:
- R1: YouTube In-Player Toolbar & Clip Marker (Content script youtubeAdapter.js, hotkeys I/O/Enter/Esc, SPA yt-navigate-finish handling).
- R2: Chrome/Edge Side Panel Clip Manager (apps/browser-extension/sidepanel/, clip list, reordering, validation).
- R3: Export Configurations & Export Engine (Single clips, Merged clip, ToolVideo pipeline import, stream-copy vs frame-accurate HW acceleration NVENC/QSV/AMF fallback libx264/libx265).
- R4: Source Adapter & Job Execution Service (yt-dlp discovery, single download & remux cache by video_id, subprocess argv security, Windows path sanitization, cancel & retry).
- R5: Realtime Protocol & Native Bridge Communication (YOUTUBE_CONTEXT_SYNC, SEEK, PREVIEW, CLIP_EXPORT_*, OPEN_OUTPUT_FOLDER, realtime progress streaming).
- R6: Extension Installation & Update Tooling (manifest.json updates, Windows registry host registration scripts for Edge & Chrome, developer mode packaging/reloading instructions, UI integration).
- R7: Full preservation of existing ChatGPT Bridge and Vbee TTS features and uncommitted working tree changes.
- Automated test suite covering parser, validator, sanitizer, FFmpeg command builder, hardware detector, protocol mocking 100% pass.
