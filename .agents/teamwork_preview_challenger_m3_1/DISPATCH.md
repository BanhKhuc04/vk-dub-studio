# Dispatch: Challenger (Milestone 3: Adversarial Verification)

## Context
Project Root: D:\Work\Project_AI\ToolVideo
Original Request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md
Project Scope: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_1\PROJECT.md
Test Ready Report: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_e2e_1\TEST_READY.md
Your Directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_challenger_m3_1

## Mission
Stress-test and adversarially probe the integrated application:
1. Challenge coordinate math:
   - Extreme aspect ratios (e.g. 9:16 vertical TikTok/Shorts, 21:9 ultrawide, 1:1 square).
   - Verify boundary clamping, anti-inversion (dragging handle past opposite handle), sub-pixel rounding.
   - Verify FFmpeg `delogo` requires at least 1px border around the logo/mask area to avoid crash.
2. Challenge API edge cases:
   - Malformed mask JSON payloads, negative coordinates, NaN, out-of-range floats.
   - Pipeline cancel when already idle or when busy.
   - Export calls before approval or without audio tracks.
   - Voice preview with invalid voice IDs or empty text.
3. Challenge `run_app.bat` and production assets:
   - Verify `dist/index.html` exists and is served by `server.py` at `/` or `/index.html`.
   - Verify `/logo.png` and `/api/logo` return valid PNG image bytes matching `logo/logo.png`.
4. Run full test suite and any adversarial probes:
   `$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_e2e_api.py tests/test_e2e_blur_math.py tests/test_e2e_kappak.py -v`
5. Record your verdict (APPROVE or CHALLENGE_FAILED) in `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_challenger_m3_1\handoff.md` and notify parent (Recipient: "b5f99409-245e-49eb-86c4-0a2263ff8cec").

## 2026-09-15T03:40:44Z
You are teamwork_preview_challenger_m3_1, a Challenger subagent for Milestone 3 (Adversarial Verification).
Your working directory is: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_challenger_m3_1
Project Root: D:\Work\Project_AI\ToolVideo
Original Request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md
Your Dispatch file: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_challenger_m3_1\DISPATCH.md
Project Scope: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_1\PROJECT.md

Challenger Tasks:
1. Stress-test coordinate math for letterbox/pillarbox across 9:16 vertical (Shorts/TikTok), 21:9 ultrawide, and 1:1 square.
2. Probe API contracts with edge cases (boundary clamping, invalid voice preview IDs, malformed mask coordinates, pipeline cancel while idle).
3. Verify production bundle and static assets (dist/index.html, /logo.png).
4. Run full test suite:
   $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_e2e_api.py tests/test_e2e_blur_math.py tests/test_e2e_kappak.py -v
5. Deliver handoff with verdict (APPROVE or CHALLENGE_FAILED) to handoff.md and notify parent (Recipient: "b5f99409-245e-49eb-86c4-0a2263ff8cec").

