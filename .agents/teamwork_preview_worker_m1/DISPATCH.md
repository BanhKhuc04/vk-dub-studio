# Milestone M1 Implementation: Bridge Protocol & Compatibility Layer

Read `D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md` (specifically ## 2026-09-15T04:12:10Z), `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_2\PROJECT.md`, and `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_bridge\report.md`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Write Ownership
You exclusively own:
- `src/vkdub/bridge/protocol.py`
- `apps/browser-extension/bridge/protocol.js`
- `src/vkdub/bridge/local_agent.py`
- `src/vkdub/web/server.py` (only the missing `is_connected()`, `is_chatgpt_ready()`, `is_vbee_ready()` delegation/property fix)
- `tests/test_bridge_protocol.py`

## Objective & Tasks
1. Update `src/vkdub/bridge/protocol.py` and `apps/browser-extension/bridge/protocol.js` with the 10 new protocol actions:
   - `YOUTUBE_CONTEXT_SYNC`
   - `YOUTUBE_SEEK_TO`
   - `YOUTUBE_PREVIEW_CLIP`
   - `CLIP_EXPORT_REQUEST`
   - `CLIP_EXPORT_ACCEPTED`
   - `CLIP_EXPORT_PROGRESS`
   - `CLIP_EXPORT_RESULT`
   - `CLIP_EXPORT_ERROR`
   - `CLIP_EXPORT_CANCEL`
   - `OPEN_OUTPUT_FOLDER`
2. Add typed dataclasses/schemas in `protocol.py` for clip payloads (`ClipItem`, `ClipExportRequest`, `ClipExportProgress`, `ClipExportResult`, etc.).
3. Update `src/vkdub/bridge/local_agent.py`:
   - Route `CLIP_EXPORT_REQUEST`, `CLIP_EXPORT_CANCEL`, `OPEN_OUTPUT_FOLDER` safely.
   - Implement `is_connected()`, `is_chatgpt_ready()`, `is_vbee_ready()` on `LocalAgent` so `server.py:257` does not raise `AttributeError`.
   - Ensure 100% preservation of ChatGPT and Vbee TTS workflows (R7).
4. Expand `tests/test_bridge_protocol.py` to cover new actions and validation.
5. Run the existing and new tests:
   `cmd.exe /c "set PYTHONPATH=src&& D:\Work\Project_AI\ToolVideo\.venv\Scripts\python.exe -m pytest tests/test_bridge_protocol.py tests/test_native_messaging_framing.py tests/test_local_agent.py tests/test_ws_local_agent.py -v"`
6. Document results in `handoff.md` and message parent when complete.

## 2026-09-15T04:19:34Z
You are Worker M1 (Bridge Protocol & Compatibility Layer).
Working directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m1
Project root: D:\Work\Project_AI\ToolVideo
Authoritative request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md (specifically ## 2026-09-15T04:12:10Z).
Project architecture: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_2\PROJECT.md
Survey findings: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_bridge\report.md
Your dispatch assignment: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m1\DISPATCH.md

Mandatory Integrity Warning:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write Ownership:
- `src/vkdub/bridge/protocol.py`
- `apps/browser-extension/bridge/protocol.js`
- `src/vkdub/bridge/local_agent.py`
- `src/vkdub/web/server.py` (only the missing `is_connected()`, `is_chatgpt_ready()`, `is_vbee_ready()` delegation/property fix)
- `tests/test_bridge_protocol.py`

Tasks:
1. Implement the 10 new protocol actions and payload schemas in `protocol.py` and `protocol.js`.
2. Implement routing in `local_agent.py` for clip actions (`CLIP_EXPORT_REQUEST`, `CLIP_EXPORT_CANCEL`, `OPEN_OUTPUT_FOLDER`), preserving 100% of ChatGPT and Vbee TTS logic (R7).
3. Fix the missing status helper methods in `local_agent.py` so `server.py:257` does not throw `AttributeError`.
4. Update/expand `tests/test_bridge_protocol.py`.
5. Run the test suite:
   `cmd.exe /c "set PYTHONPATH=src&& D:\Work\Project_AI\ToolVideo\.venv\Scripts\python.exe -m pytest tests/test_bridge_protocol.py tests/test_native_messaging_framing.py tests/test_local_agent.py tests/test_ws_local_agent.py -v"`
6. Deliver `handoff.md` and message parent when complete.
