# Dispatch: Forensic Auditor (Milestone 3: Integrity Forensics)

## Context
Project Root: D:\Work\Project_AI\ToolVideo
Original Request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md
Project Scope: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_1\PROJECT.md
Your Directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_auditor_m3_1

## Mission: Forensic Integrity Verification
You are the Forensic Auditor. You have a BINARY VETO on this milestone.
Check for ANY form of cheating, fake facades, dummy shortcuts, or circumventions:
1. Check source files (`frontend/src/App.jsx`, `frontend/src/components/InteractiveCanvas.jsx`, `frontend/src/styles.css`):
   - Confirm all manual coordinate inputs (X, Y, W, H, Sigma) are genuinely deleted, not just hidden with `display: none` or CSS tricks.
   - Confirm `InteractiveCanvas.jsx` contains genuine mouse event handlers, aspect ratio letterbox math, and resize handles.
   - Confirm Apple minimalist tokens and Framer Motion spring physics are genuinely implemented.
   - Confirm `logo/logo.png` is genuine (size 403,891 bytes).
2. Check backend files (`src/vkdub/web/server.py`, `src/vkdub/providers/edge_tts_provider.py`, `src/vkdub/services/render_service.py`, `src/vkdub/services/capcut_export.py`):
   - Confirm `export_mp4()` does NOT silently copy raw video. Verify it calls `build_render_command` with genuine audio ducking, mask filters, and subtitle burning.
   - Confirm `export_capcut()` does NOT return a fake fallback string. Verify it calls `export_capcut_project` to generate a genuine CapCut project structure.
   - Confirm Edge TTS synthesis is genuine (WebSocket connection to Microsoft Edge speech service with valid local audio fallback).
   - Confirm Mask CRUD endpoints (`GET/POST/DELETE /api/masks`) truly store and retrieve `MaskItem` objects in `state.project.masks`.
3. Check test suites:
   - Run tests: `$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_e2e_api.py tests/test_e2e_blur_math.py tests/test_e2e_kappak.py tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py -v`
   - Verify that test assertions are genuine and not trivial `assert True` mocks.
4. Record verdict (CLEAN or INTEGRITY VIOLATION) in `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_auditor_m3_1\handoff.md` and notify parent (Recipient: "b5f99409-245e-49eb-86c4-0a2263ff8cec").
