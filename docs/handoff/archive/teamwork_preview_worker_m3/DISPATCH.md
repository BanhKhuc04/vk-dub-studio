# Milestone M3 Implementation: Job Execution & Export Service

Read `D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md` (specifically ## 2026-09-15T04:12:10Z), `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_2\PROJECT.md`, and previous worker handoffs in `.agents/teamwork_preview_worker_m1/handoff.md` and `.agents/teamwork_preview_worker_m2/handoff.md`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Write Ownership
You exclusively own:
- `src/vkdub/services/clip_export_service.py`
- `tests/test_clip_export_service.py`
You may read: all files in repository.

## Objective & Tasks
1. Implement `src/vkdub/services/clip_export_service.py`:
   - `ClipExportService` managing background export jobs.
   - Integrates `YtDlpDownloader` from `src/vkdub/media/ytdlp.py` (M2).
   - Integrates `HardwareEncoderDetector` from `src/vkdub/media/hardware.py` (M2).
   - Integrates `ClipEngine`, `sanitize_filename`, `parse_timecode`, `kill_process_tree` from `src/vkdub/media/clip_engine.py` (M2).
   - Hooks into `LocalAgent` (M1) via `set_clip_export_handler` and `set_clip_cancel_handler`.
   - Sends realtime telemetry via `local_agent.send_clip_accepted`, `send_clip_progress`, `send_clip_result`, `send_clip_error`.
   - Support 3 export modes:
     * `SEPARATE`: export each clip to `{title}_clip_{i}_{start}-{end}.{container}` in output directory.
     * `MERGED`: export clips and merge into `{title}_selected_clips.{container}` using concat demuxer.
     * `IMPORT`: export clip(s) and automatically load into ToolVideo state (`state.project.video_path` in `server.py` or timeline).
   - Safe subprocess execution via argument arrays (no shell string concat).
   - Windows path sanitization & directory traversal prevention.
   - Job cancellation: terminate active process tree (`kill_process_tree`), clean temporary/scratch files, emit cancellation state.
   - Idempotent request handling via `request_id` (ignore or return existing job for duplicate requests).
2. Write unit and integration tests in `tests/test_clip_export_service.py` (using mocks for subprocesses where appropriate to ensure fast offline execution).
3. Run tests:
   `cmd.exe /c "set PYTHONPATH=src&& D:\Work\Project_AI\ToolVideo\.venv\Scripts\python.exe -m pytest tests/test_clip_export_service.py tests/test_clip_engine.py tests/test_bridge_protocol.py tests/test_youtube_clip_mode.py tests/test_e2e_clip_pipeline.py -v"`
4. Deliver `handoff.md` and message parent when complete.

## 2026-09-15T04:33:11Z
You are Worker M3 (Job Execution & Export Service).
Working directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m3
Project root: D:\Work\Project_AI\ToolVideo
Authoritative request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md (specifically ## 2026-09-15T04:12:10Z).
Project architecture: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_2\PROJECT.md
Your dispatch assignment: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m3\DISPATCH.md
Read previous worker handoffs:
- D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m1\handoff.md
- D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m2\handoff.md

Mandatory Integrity Warning:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write Ownership:
- `src/vkdub/services/clip_export_service.py`
- `tests/test_clip_export_service.py`

Tasks:
1. Implement `ClipExportService` in `src/vkdub/services/clip_export_service.py`:
   - Ties `YtDlpDownloader` (M2), `HardwareEncoderDetector` (M2), `ClipEngine` (M2), and `LocalAgent` (M1).
   - Async background job queue with thread workers.
   - Realtime progress streaming: Probing -> Downloading -> Remuxing -> Trimming K/N -> Merging -> Complete.
   - Modes: SEPARATE, MERGED, and IMPORT (load into ToolVideo `state.project.video_path`).
   - Cancellation with `kill_process_tree`, scratch directory cleanup, and idempotent `request_id`.
   - Windows path sanitization & traversal prevention.
2. Implement unit and integration tests in `tests/test_clip_export_service.py`.
3. Run tests:
   `cmd.exe /c "set PYTHONPATH=src&& D:\Work\Project_AI\ToolVideo\.venv\Scripts\python.exe -m pytest tests/test_clip_export_service.py tests/test_clip_engine.py tests/test_bridge_protocol.py tests/test_youtube_clip_mode.py tests/test_e2e_clip_pipeline.py -v"`
4. Deliver `handoff.md` and message parent when complete.
