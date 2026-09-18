# E2E Test Suite Creation Task

Read `D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md` (specifically ## 2026-09-15T04:12:10Z) and `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_2\PROJECT.md`.

## Mandatory Rules & Integrity Warning
DO NOT CHEAT. All tests must be genuine verification tests. DO NOT hardcode trivial passes. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Write Ownership
You exclusively own:
- `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_test_writer_e2e\TEST_INFRA.md`
- `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_test_writer_e2e\TEST_READY.md`
- `tests/test_youtube_clip_mode.py`
- `tests/test_e2e_clip_pipeline.py`

## Objective & Scope
Construct the comprehensive automated E2E test suite using the 4-tier methodology:
- Tier 1: Feature Coverage (>=5 tests per feature: URL parsing, clip validation, timecode formatting, sanitize filename, hardware probing, stream copy cmd, frame accurate cmd, concat manifest, yt-dlp discovery, protocol serialization).
- Tier 2: Boundary & Corner Cases (>=5 tests per feature: empty title, non-ASCII/Vietnamese chars, Windows reserved names CON/NUL/PRN, start=0, start=end, end>duration, negative timestamps, missing yt-dlp, missing ffmpeg, AMF missing dll fallback, cancel mid-execution).
- Tier 3: Cross-Feature Combinations (Stream copy + Merged export; Frame-Accurate + NVENC + Single export; Stream copy + Import to Studio; Opt-in cookies vs no cookies).
- Tier 4: Real-World Application Scenarios (Realistic multi-clip podcast trimming, long gaming stream clipping with 5 segments, fast short video extraction).

All tests must mock external network/YouTube downloads and FFmpeg subprocess runs where appropriate so tests run 100% offline, reliably and fast (<10 seconds).
Run pytest to verify all created tests pass:
`$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_youtube_clip_mode.py tests/test_e2e_clip_pipeline.py`

When complete:
- Write `TEST_INFRA.md` and `TEST_READY.md` in your working directory.
- Deliver `handoff.md` and message parent.

## 2026-09-15T04:19:34Z
You are E2E Test Writer for VK Dub Studio YouTube Clip Mode.
Working directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_test_writer_e2e
Project root: D:\Work\Project_AI\ToolVideo
Authoritative request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md (specifically ## 2026-09-15T04:12:10Z).
Project architecture: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_2\PROJECT.md
Your dispatch assignment: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_test_writer_e2e\DISPATCH.md

Tasks:
1. Design and write the comprehensive automated E2E test suite in `tests/test_youtube_clip_mode.py` and `tests/test_e2e_clip_pipeline.py`.
2. Cover all 4 tiers:
   - Tier 1: Feature coverage (>=5 tests per feature: URL parsing, clip validation, timecode formatting, filename sanitization, hardware probing, stream copy command, frame-accurate command, concat manifest, yt-dlp discovery, protocol serialization).
   - Tier 2: Boundary & Corner cases (>=5 tests per feature: empty title, Vietnamese/Unicode characters, Windows reserved names CON/NUL/PRN, start=0, start=end, end>duration, negative timestamps, missing yt-dlp, missing ffmpeg, AMF missing DLL fallback, cancellation mid-execution).
   - Tier 3: Cross-feature combinations (Stream-copy + Merged export; Frame-Accurate + NVENC + Single export; Stream-copy + Import to Studio; Opt-in cookies vs no cookies).
   - Tier 4: Real-world application scenarios (Multi-clip podcast trimming, long stream clipping, fast short extraction).
3. Ensure all tests run fast and offline using mocks for network downloads and subprocess calls where appropriate.
4. Run the test suite:
   `cmd.exe /c "set PYTHONPATH=src&& D:\Work\Project_AI\ToolVideo\.venv\Scripts\python.exe -m pytest tests/test_youtube_clip_mode.py tests/test_e2e_clip_pipeline.py -v"`
5. Write `TEST_INFRA.md` and `TEST_READY.md` in your working directory.
6. Deliver `handoff.md` and message parent with summary and test results.

