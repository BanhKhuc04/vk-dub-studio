# BRIEFING — 2026-09-15T10:34:00Z

## Mission
Implement backend core improvements & pipeline bridge for ToolVideo Web UI (Milestone 1).

## 🔒 My Identity
- Archetype: worker
- Roles: implementer, qa, specialist
- Working directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m1_1
- Original parent: b5f99409-245e-49eb-86c4-0a2263ff8cec
- Milestone: Milestone 1 - Backend Core & Pipeline Bridge

## 🔒 Key Constraints
- Write ownership: src/vkdub/web/server.py, any new backend helper in src/vkdub/ (e.g. src/vkdub/providers/edge_tts_provider.py), run_app.bat
- Must NOT touch frontend/ or tests/
- Genuine implementation only, no mock/fake shortcuts, no hardcoded results
- Must pass tests: tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py

## Current Parent
- Conversation ID: b5f99409-245e-49eb-86c4-0a2263ff8cec
- Updated: 2026-09-15T10:34:00Z

## Task Summary
- **What to build**: 
  1. Mask REST APIs: GET /api/masks, POST /api/masks, DELETE /api/masks/{id} syncing to state.project.masks
  2. Fix PipelineRunner signal connections in server.py (substep_updated, state_changed, artifact_ready, log_emitted, pipeline_completed, pipeline_failed, pipeline_cancelled)
  3. Fix ArtifactRegistry references (remove non-existent bilingual_script; parse original_srt / translated_srt for state.subtitles; link timeline_master_audio into state.project.master_voice_path)
  4. Implement POST /api/voices/preview and GET /api/voices/preview/stream with Edge TTS provider (support offline fallback audio if external network unavailable)
  5. Fix export_mp4() to authentically render dubbed audio + mask filter using build_render_command and bundled ffmpeg
  6. Fix export_capcut() to synchronize approved_revision_hash and voice status so genuine CapCut draft is generated
  7. Verify and fix run_app.bat with portable toolpaths and PYTHONPATH
  8. Fix get_settings() to safely handle optional attributes with safe defaults
- **Success criteria**: 100% test pass on existing suites (21/21) and E2E suites (49/49), genuine CapCut draft & MP4 export
- **Interface contracts**: Survey reports 2 & 3, DISPATCH.md

## Key Decisions Made
- Implemented `EdgeTTSProvider` supporting Microsoft Edge Read Aloud WebSocket synthesis with automatic local FFmpeg harmonic synthesizer fallback when network/auth is unavailable.
- Synchronized `state.subtitles` to `state.project.script` automatically on subtitle save and approval, computing SHA256 revision hash and marking `state.project.approved_revision_hash`.
- Integrated `build_ffmpeg_mask_filter` in both dubbed and non-dubbed export branches, completely eliminating raw copy shortcuts.
- Bound all valid Qt signals (`substep_updated`, `state_changed`, `artifact_ready`, `log_emitted`, `pipeline_completed`, `pipeline_failed`, `pipeline_cancelled`) and calculated weighted progress (25%, 25%, 10%, 40%).

## Change Tracker
- **Files modified**:
  - `src/vkdub/web/server.py`: Complete backend core overhaul (masks, runner signals, audio/subtitle sync, authentic export, voice preview, favicon)
  - `src/vkdub/providers/edge_tts_provider.py`: New Edge TTS provider with WebSocket and offline fallback synthesis
  - `run_app.bat`: Portable startup script with tools directory PATH, PYTHONPATH, and virtualenv verification
- **Build status**: All tests pass (21/21 required tests, 49/49 E2E tests)
- **Pending issues**: None

## Quality Status
- **Build/test result**: PASS (70+ tests passing)
- **Lint status**: Clean (py_compile validated)
- **Tests added/modified**: 0 in tests/ (per write ownership constraint); verified against all existing and newly authored E2E suites

## Loaded Skills
- None
