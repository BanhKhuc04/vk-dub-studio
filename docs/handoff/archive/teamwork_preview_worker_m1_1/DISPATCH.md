# Dispatch: Milestone 1 Worker (Backend Core & Pipeline Bridge)

## Context
Project Root: D:\Work\Project_AI\ToolVideo
Original Request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md
Project Scope: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_1\PROJECT.md
Explorer Survey 2 Report: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_2\analysis.md
Explorer Survey 3 Report: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_3\analysis.md
Your Directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m1_1

## Mandatory Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Write Ownership
You exclusively own:
- `src/vkdub/web/server.py`
- Any new backend helper module in `src/vkdub/` (e.g. `src/vkdub/providers/edge_tts_provider.py`)
- `run_app.bat`
You must NOT touch files in `frontend/` or `tests/`.

## Mission
Fix the critical backend gaps identified in Survey Reports 2 and 3:
1. **Mask REST Endpoints**:
   - Implement `GET /api/masks`: returns `list[MaskRegion]` from `state.project.masks`.
   - Implement `POST /api/masks`: accepts `{"masks": [MaskRegion, ...]}` and updates `state.project.masks` with `MaskItem` objects.
   - Implement `DELETE /api/masks/{mask_id}`: deletes specific mask from `state.project.masks`.
2. **Fix Fatal Signal Crash in PipelineRunner**:
   - In `server.py`, replace invalid `runner.overall_progress` and `runner.pipeline_finished` with valid signals:
     - `runner.substep_updated.connect(on_substep_updated)`
     - `runner.state_changed.connect(on_state_changed)`
     - `runner.artifact_ready.connect(on_artifact_ready)`
     - `runner.pipeline_completed.connect(on_pipeline_completed)`
     - `runner.pipeline_failed.connect(on_pipeline_failed)`
3. **Fix ArtifactRegistry & Subtitle Extraction**:
   - Do NOT access `runner.artifacts.bilingual_script`.
   - When subtitles or `original_srt` / `translated_srt` are ready, parse them and populate `state.subtitles`.
   - Capture `runner.artifacts.timeline_master_audio` or `vbee_master_audio` into `state.project.master_voice_path`.
4. **Voice Preview Endpoint**:
   - Implement `POST /api/voices/preview`: returns preview audio url or generates Edge TTS sample audio (with fallback if offline).
5. **Authentic MP4 Export**:
   - In `export_mp4()`, do NOT copy raw video. Use `state.project.master_voice_path` (or master narration from export artifacts), apply `build_ffmpeg_mask_filter` with `state.project.masks`, and render genuine dubbed/masked MP4.
6. **Authentic CapCut Export**:
   - In `export_capcut()`, ensure `state.project.approved_revision_hash` and `state.project.master_voice_path` are set properly (via `/api/review/approve`), and call `export_capcut_project` to produce a valid CapCut project folder.
7. **Ensure `run_app.bat`**:
   - Works cleanly and launches browser without errors.

Test your changes:
Run: `$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py -v`
Write a detailed report to `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m1_1\changes.md` and `handoff.md`.

## 2026-09-15T03:33:13Z
**Sender**: b5f99409-245e-49eb-86c4-0a2263ff8cec
**Context**: Milestone 1 Backend Implementation & E2E Testing Synchronization
**Content**: The E2E Test Writer has completed the 4-Tier test suite. In addition to the planned tasks, please ensure you fix `server.py:194-195` where `get_settings()` attempts to access `s.chatgpt_model` and `s.whisper_model` which causes an AttributeError on `AppSettings`. Use `getattr(s, "chatgpt_model", "gpt-4o")` and `getattr(s, "whisper_model", "base")` or set safe defaults. Also verify all 49 E2E tests in `tests/test_e2e_api.py`, `tests/test_e2e_blur_math.py`, and `tests/test_e2e_kappak.py` pass.
**Action**: Incorporate this fix and complete your implementation and test verification.
