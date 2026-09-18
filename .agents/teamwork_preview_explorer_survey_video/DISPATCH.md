# Survey Task: Video Processing Backend & yt-dlp / FFmpeg Architecture

Read `D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md` (specifically ## 2026-09-15T04:12:10Z).

## Objective
Investigate the backend video processing pipeline, services, and FFmpeg/yt-dlp utilities in VK Dub Studio (`backend/`, `tools/`, etc.).
Extract technical details for:
1. `yt-dlp` discovery and execution:
   - Search order: `YTDLP_PATH` env, `tools/yt-dlp/yt-dlp.exe`, `tools/yt-dlp.exe`, system PATH.
   - Download strategy: single download & remux per video_id/format/quality, caching structure.
   - Cookies opt-in rules (public video must not call cookies).
2. FFmpeg command building & hardware acceleration:
   - Stream copy (`-c copy`) vs frame-accurate re-encoding.
   - Hardware encoder detection (NVIDIA NVENC, Intel QSV, AMD AMF) with fallback to CPU `libx264`/`libx265` (CRF 17-18).
   - Audio handling (copy or AAC high quality), container support (`mp4`, `mkv`).
   - Merging/concatenation of multiple clips into one file.
3. Job Execution Service & Security:
   - Safe subprocess execution via argument arrays (no shell string concat).
   - Windows path sanitization & directory traversal prevention.
   - Safe temp/scratch file lifecycle and cleanup.
   - Job control: cancellation (`CLIP_EXPORT_CANCEL`), retry, idempotent `request_id`.
   - ToolVideo timeline/pipeline import mechanism.

Write your comprehensive findings to `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_video\report.md` and deliver `handoff.md`.

## 2026-09-15T04:13:54Z
You are Explorer 3 (Video Engine, yt-dlp & FFmpeg Hardware Acceleration Explorer).
Working directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_video
Project root: D:\Work\Project_AI\ToolVideo
Authoritative request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md (specifically ## 2026-09-15T04:12:10Z).
Your dispatch assignment: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_video\DISPATCH.md

Tasks:
1. Thoroughly investigate the backend video processing pipeline, services, and FFmpeg/yt-dlp utilities in VK Dub Studio (`backend/`, `tools/`, etc.).
2. Map `yt-dlp` discovery (YTDLP_PATH env, tools/yt-dlp/yt-dlp.exe, tools/yt-dlp.exe, PATH), single download & remux caching per video_id/format/quality, cookies opt-in rules.
3. Map FFmpeg command building: stream copy (`-c copy`) vs frame-accurate re-encoding; hardware encoder detection (NVENC, QSV, AMF) fallback libx264/libx265 (CRF 17-18); container formats mp4/mkv; clip concat/merge engine.
4. Map job execution architecture: safe subprocess argv execution (no shell string concat), Windows path sanitization & traversal prevention, temp/scratch cleanup, job cancellation (`CLIP_EXPORT_CANCEL`), retry, idempotent `request_id`, and ToolVideo pipeline import.
5. Write your comprehensive findings to `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_video\report.md` and deliver `handoff.md`.
6. When done, send a message to parent summarizing key findings and report paths.
