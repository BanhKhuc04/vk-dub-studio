# BRIEFING — 2026-09-15T04:20:00Z

## Mission
Implement Milestone M2: Video Engine (yt-dlp, HW Accel, Trimming & Concat) in `src/vkdub/media/` and comprehensive unit tests in `tests/test_clip_engine.py`.

## 🔒 My Identity
- Archetype: teamwork_preview_worker_m2
- Roles: implementer, qa, specialist
- Working directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m2
- Original parent: 9a210ca7-4722-402a-8ee5-2d8eb245ac13
- Milestone: M2 - Video Engine (yt-dlp, HW Accel, Trimming & Concat)

## 🔒 Key Constraints
- DO NOT CHEAT. All implementations must be genuine.
- DO NOT hardcode test results, expected outputs, or dummy/facade implementations.
- Write Ownership exclusively:
  - `src/vkdub/media/ytdlp.py`
  - `src/vkdub/media/hardware.py`
  - `src/vkdub/media/clip_engine.py`
  - `tests/test_clip_engine.py`
- Only write metadata to `.agents/teamwork_preview_worker_m2/`. Never place code/tests in `.agents/`.
- Safe subprocess execution with list argv (no shell=True).
- Strictly opt-in cookies (public videos NEVER pass cookie arguments).
- Windows path sanitization (illegal chars, reserved names CON/PRN/AUX/NUL/COM1-9/LPT1-9, trailing dots/spaces, length truncation).
- 5-step search order for yt-dlp.
- Active 1-frame probe for NVENC/QSV/AMF fallback CPU libx264/libx265 with in-memory caching.
- Multi-clip concat demuxer manifest and execution.
- Timecode parser supporting `HH:MM:SS.mmm`, `MM:SS`, or float seconds.

## Current Parent
- Conversation ID: 9a210ca7-4722-402a-8ee5-2d8eb245ac13
- Updated: not yet

## Task Summary
- **What to build**: `ytdlp.py`, `hardware.py`, `clip_engine.py`, `tests/test_clip_engine.py`
- **Success criteria**: All components implemented adhering to specs, 100% test pass on `tests/test_clip_engine.py` and `tests/test_render.py` without regressions.
- **Interface contracts**: PROJECT.md & survey report.md
- **Code layout**: `src/vkdub/media/` and `tests/`

## Key Decisions Made
- `ytdlp.py`: Strict 5-step discovery order with authoritative override semantics (returns None if YTDLP_PATH set but missing). Single-download caching keyed by (video_id, quality) in cache/youtube/{video_id}. Public videos strictly omit cookie flags.
- `hardware.py`: Active 1-frame probe test using FFmpeg lavfi 256x256 test pattern. Detection priority NVENC -> QSV -> AMF -> libx264/libx265. Visually lossless CRF 17-18 equivalent parameters mapped for each encoder. Results cached in-memory with clear_cache() support.
- `clip_engine.py`: Windows-safe sanitization stripping reserved words (CON, PRN, AUX, NUL, COM1-9, LPT1-9), illegal characters, control characters, and length limit. Robust timecode parser supporting HH:MM:SS.mmm, MM:SS.mmm, float seconds, and formatted units. Lossless stream-copy trimming and frame-accurate HW/CPU trimming. FFmpeg concat demuxer manifest builder and merge execution.

## Artifact Index
- `src/vkdub/media/ytdlp.py` — Discovery, download command, single-download caching
- `src/vkdub/media/hardware.py` — Active 1-frame probe, encoder parameter mapping, detector
- `src/vkdub/media/clip_engine.py` — Sanitization, timecode parser, stream-copy, frame-accurate, concat demuxer
- `tests/test_clip_engine.py` — 33 tests covering all Video Engine features and integration
- `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m2\DISPATCH.md` — Assignment
- `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m2\progress.md` — Heartbeat and progress
- `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m2\handoff.md` — Handoff report

## Change Tracker
- **Files modified**:
  - `src/vkdub/media/ytdlp.py` (created) — yt-dlp discovery & caching
  - `src/vkdub/media/hardware.py` (created) — active HW probe & priority
  - `src/vkdub/media/clip_engine.py` (created) — trim, merge, sanitize, parse
  - `tests/test_clip_engine.py` (created) — 33 unit & integration tests
- **Build status**: PASS (40/40 tests passing in 1.95s)
- **Pending issues**: None

## Quality Status
- **Build/test result**: 40 passed (33 in test_clip_engine.py, 7 in test_render.py)
- **Lint status**: 0 violations (ruff check passed)
- **Tests added/modified**: 33 tests in `tests/test_clip_engine.py`

## Loaded Skills
- None specified in prompt.
