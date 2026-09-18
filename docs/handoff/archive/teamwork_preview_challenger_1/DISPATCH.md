# Adversarial Challenge: Backend Video & Export Engine (M1, M2, M3)

Read `D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md` (specifically ## 2026-09-15T04:12:10Z) and `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_2\PROJECT.md`.

## Challenge Objectives
Write and execute an adversarial stress test harness against:
1. Windows filename sanitization: attempt directory traversal (`../../etc/passwd`, `..\\..\\Windows\\System32`), reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1`, `LPT1`), control characters (`\x00-\x1f`), ultra-long titles (>300 chars), Vietnamese diacritics, and symbols (`<>:"/\\|?*`).
2. Timecode parser & validator: negative timestamps, invalid formats, non-numeric strings, start=end, start>end, end>duration, sub-millisecond precision.
3. Hardware encoder detection & fallback: test what happens when NVENC is mocked as failing (exit code 1 or crash) — verify clean fallback to QSV -> AMF -> libx264/libx265.
4. Concat manifest generation: paths containing single quotes, spaces, backslashes, Unicode characters.
5. Job cancellation & process cleanup: test cancellation during active downloading and trimming — verify child process tree is reaped via `kill_process_tree` and scratch dir is completely removed.
6. Idempotent requests: submit rapid duplicate `request_id` calls concurrently.

Write and execute your challenge harness (e.g. `tests/test_adversarial_backend_clips.py`), confirm all edge cases are handled safely.
Deliver `handoff.md` with your findings, evidence, and verdict: `APPROVE` or `DEFECT_DETECTED`.

## 2026-09-15T04:44:39Z
You are Challenger 1 (Backend Adversarial Verifier).
Working directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_challenger_1
Project root: D:\Work\Project_AI\ToolVideo
Authoritative request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md (specifically ## 2026-09-15T04:12:10Z).
Project architecture: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_2\PROJECT.md
Your dispatch assignment: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_challenger_1\DISPATCH.md

Tasks:
1. Build and execute an adversarial stress test harness (`tests/test_adversarial_backend_clips.py`) targeting:
   - Filename sanitization under malicious paths (traversal `../../`, reserved device names `CON`, `NUL`, `PRN`, `AUX`, `COM1-9`, `LPT1-9`, control characters, ultra-long titles >300 chars, Unicode).
   - Timecode parsing & validation under edge/invalid timestamps.
   - Hardware encoder detection when NVENC fails (verify clean fallback chain to QSV -> AMF -> libx264).
   - Concat manifest generation with problematic paths (quotes, spaces, backslashes).
   - Cancellation and process tree termination (`kill_process_tree`) during active downloads/trims and scratch directory cleanup.
   - Idempotency with rapid concurrent requests.
2. Run your harness:
   `cmd.exe /c "set PYTHONPATH=src&& D:\Work\Project_AI\ToolVideo\.venv\Scripts\python.exe -m pytest tests/test_adversarial_backend_clips.py -v"`
3. Deliver `handoff.md` with explicit verdict: `APPROVE` or `DEFECT_DETECTED`.
