# Dispatch: Reviewer for Milestone 1 (Backend Core & Pipeline Bridge)

## Context
Project Root: D:\Work\Project_AI\ToolVideo
Original Request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md
Project Scope: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_1\PROJECT.md
Worker M1 Handoff: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m1_1\handoff.md
Worker M1 Changes: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m1_1\changes.md
Your Directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_reviewer_m1_1

## Mission
Independently review the backend changes implemented by `teamwork_preview_worker_m1_1`:
1. Verify `src/vkdub/web/server.py`:
   - Mask REST endpoints (`GET/POST/DELETE /api/masks`).
   - Signal wiring on `PipelineRunner` (`substep_updated`, `state_changed`, `artifact_ready`, `pipeline_completed`, `pipeline_failed`).
   - Subtitle extraction from `original_srt`/`translated_srt` and assignment to `state.subtitles` without referencing `bilingual_script`.
   - Voice preview endpoint `POST /api/voices/preview` and `EdgeTTSProvider`.
   - Authentic MP4 export using `master_narration_timeline.mp3` and `build_ffmpeg_mask_filter`.
   - Authentic CapCut export synchronizing approval hash and voice status.
2. Run test verification:
   - `$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py -v`
   - `$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_e2e_api.py tests/test_e2e_blur_math.py tests/test_e2e_kappak.py -v`
3. Check for any regression, security risks, or unhandled exceptions.
4. Record your verdict (APPROVE or REQUEST_CHANGES) in `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_reviewer_m1_1\handoff.md` and notify parent (Recipient: "b5f99409-245e-49eb-86c4-0a2263ff8cec").

## 2026-09-15T03:35:41Z
You are teamwork_preview_reviewer_m1_1, a Reviewer subagent for Milestone 1 (Backend Core & Pipeline Bridge).
Your working directory is: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_reviewer_m1_1
Project Root: D:\Work\Project_AI\ToolVideo
Original Request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md
Your Dispatch file: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_reviewer_m1_1\DISPATCH.md
Project Scope: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_1\PROJECT.md
Worker M1 Handoff: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m1_1\handoff.md
Worker M1 Changes: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m1_1\changes.md

You MUST read D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md and your DISPATCH.md before starting work.

Review Tasks:
1. Examine code changes in src/vkdub/web/server.py and src/vkdub/providers/edge_tts_provider.py.
2. Verify all requirements: Mask REST APIs (GET/POST/DELETE), PipelineRunner signal wiring, ArtifactRegistry/subtitles handling, Edge TTS voice preview, authentic MP4 render command, authentic CapCut export, AppSettings resilience, and run_app.bat.
3. Run test commands:
   $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py -v
   $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_e2e_api.py tests/test_e2e_blur_math.py tests/test_e2e_kappak.py -v
4. Provide structured verdict (APPROVE or REQUEST_CHANGES) in handoff.md.
5. Notify parent (Recipient: "b5f99409-245e-49eb-86c4-0a2263ff8cec").
