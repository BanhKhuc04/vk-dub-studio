# Dispatch: E2E Testing Worker

## 2026-09-15T03:27:29Z

## Context
Project Root: D:\Work\Project_AI\ToolVideo
Original Request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md
Project Scope: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_1\PROJECT.md
Your Directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_e2e_1

## Mandatory Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Write Ownership
You exclusively own:
- `tests/test_e2e_kappak.py`
- `tests/test_e2e_blur_math.py`
- `tests/test_e2e_api.py`
- `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_e2e_1\TEST_INFRA.md`
- `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_e2e_1\TEST_READY.md`
You must NOT touch frontend files or `src/vkdub/web/server.py`.

## Mission
Design and implement the comprehensive 4-Tier E2E test suite based on requirements in `ORIGINAL_REQUEST.md`:
- Tier 1: Fast API contracts (Status, logo endpoint, video info probe, voices catalog, mask CRUD endpoints `GET/POST/DELETE /api/masks`, voice preview `POST /api/voices/preview`).
- Tier 2: Interactive blur coordinate transformations (letterbox/pillarbox normalization, CSS px <-> normalized `[0.0, 1.0]` <-> intrinsic video pixel mapping, FFmpeg `delogo`/`boxblur` filter syntax verification).
- Tier 3: 5-Step pipeline execution simulation (verifying `PipelineRunner` signal handling, progress broadcasting, subtitle synchronization, approved revision hash computation).
- Tier 4: Output export integrity (verifying authentic MP4 render command structure with audio muxing + blur filter, and authentic CapCut draft folder structure with draft_content.json).

Run tests using:
`$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_e2e_kappak.py tests/test_e2e_blur_math.py tests/test_e2e_api.py -v` (or existing tests).
Ensure the tests fail gracefully if backend endpoints are not yet fully implemented, but pass once M1 is completed.
Publish `TEST_READY.md` in your directory and report handoff.
