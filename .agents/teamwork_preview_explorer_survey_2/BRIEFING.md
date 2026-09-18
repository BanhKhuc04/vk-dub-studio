# BRIEFING — 2026-09-15T03:20:00Z

## Mission
Investigate the backend architecture, APIs, and 5-step automation pipeline for the ToolVideo Web UI refactoring project.

## 🔒 My Identity
- Archetype: explorer
- Roles: investigation, synthesis
- Working directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_2
- Original parent: b5f99409-245e-49eb-86c4-0a2263ff8cec
- Milestone: survey_phase

## 🔒 Key Constraints
- Read-only investigation — do NOT implement code modifications to source files
- Focus exclusively on Backend Architecture, APIs, and 5-Step Automation Pipeline
- Deliver comprehensive analysis.md and handoff.md in own directory

## Current Parent
- Conversation ID: b5f99409-245e-49eb-86c4-0a2263ff8cec
- Updated: 2026-09-15T03:26:00Z

## Investigation State
- **Explored paths**:
  - `src/vkdub/web/server.py` (FastAPI app, routes, state management)
  - `src/vkdub/orchestrator/pipeline_runner.py`, `pipeline_state.py`, `checkpoint.py`
  - `src/vkdub/domain/mask.py`, `project.py`, `script.py`, `voice.py`, `subtitle.py`
  - `src/vkdub/services/render_service.py`, `mask_service.py`, `capcut_export.py`, `audio_mix_service.py`, `subtitle_service.py`, `voice_catalog.py`, `tts_service.py`
  - `src/vkdub/bridge/local_agent.py`, `protocol.py`
  - `frontend/src/App.jsx`, `styles.css`, `package.json`
- **Key findings**:
  - Fatal Bug 1: `server.py` connects to non-existent signals `overall_progress` & `pipeline_finished` on `PipelineRunner` (raises `AttributeError` on Step 4 start).
  - Fatal Bug 2: `server.py` accesses non-existent `runner.artifacts.bilingual_script`.
  - Fatal Bug 3: `export_mp4()` looks for `cache/speech.wav` (which never exists), falling back to raw video copy without voice, masks, or subtitles.
  - Fatal Bug 4: `export_capcut()` fails prerequisite checks (`voice_ready` and `approved_revision_hash`), returning a fake fallback folder.
  - Missing: REST routes for masks (`GET/POST /api/masks`, `DELETE /api/masks/{id}`).
  - Missing: REST route for voice preview (`POST /api/voices/preview`) & Edge TTS synthesis engine.
  - UI violation: `frontend/src/App.jsx` still has manual X/Y/W/H coordinate inputs for blur regions in Step 3.
- **Unexplored areas**: None within backend scope.

## Key Decisions Made
- Deliver actionable 5-component handoff report detailing exact line numbers, verified terminal outputs, API contract specifications, and implementation blueprint.

## Artifact Index
- D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_2\DISPATCH.md — Task dispatch
- D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_2\BRIEFING.md — Persistent context & memory
- D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_2\progress.md — Liveness heartbeat
- D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_2\analysis.md — Comprehensive backend & 5-step pipeline analysis
- D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_2\handoff.md — 5-component structured handoff report

