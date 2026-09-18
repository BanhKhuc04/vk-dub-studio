# Handoff Report — Milestone M2: Video Engine (yt-dlp, HW Accel, Trimming & Concat)

## 1. Observation
- **Assigned Write Ownership**:
  - `src/vkdub/media/ytdlp.py`
  - `src/vkdub/media/hardware.py`
  - `src/vkdub/media/clip_engine.py`
  - `tests/test_clip_engine.py`
- **Initial State**:
  - `src/vkdub/media/process.py:11-96` defines `find_tool(name: str)` for ffmpeg and ffprobe. Bundled FFmpeg exists at `D:\Work\Project_AI\ToolVideo\tools\ffmpeg.exe` and FFprobe at `tools\ffprobe.exe`.
  - `yt-dlp` was absent from system PATH and bundled directory, requiring a strict 5-step search resolution order (`YTDLP_PATH` -> `tools/yt-dlp/` -> `tools/` -> system PATH -> WinGet/Scoop/Chocolatey).
  - Empirical probe test on the bundled FFmpeg binary verified:
    - `h264_nvenc`: Available (Exit code 0).
    - `h264_qsv`: Available (Exit code 0).
    - `h264_amf`: Failed (Exit code -1313558101, `DLL amfrt64.dll failed to open`, no AMD GPU/driver).
    - This confirmed that static `-encoders` querying is insufficient and active 1-frame probing is necessary.
- **Implemented Modules**:
  - `src/vkdub/media/ytdlp.py` (436 lines):
    - `find_ytdlp()`: Strict 5-step search order with authoritative override principle (if `YTDLP_PATH` is configured but nonexistent, returns `None` without falling back).
    - `YtDlpDownloader`: Single-download caching per `(video_id, quality)` in `cache/youtube/{video_id}`.
    - Strictly opt-in cookies: `--cookies-from-browser` is appended only when `use_cookies=True` and `cookie_browser` is specified; public videos never receive cookie parameters.
    - Container flag `--merge-output-format mp4` and `--ffmpeg-location` pointing to bundled ffmpeg directory.
    - Progress parsing extracting stage, percentage, download speed, ETA, and size.
  - `src/vkdub/media/hardware.py` (183 lines):
    - `HardwareEncoderDetector`: Active 1-frame probe test (`-f lavfi -i color=s=256x256:d=0.04 -c:v <encoder> -frames:v 1 -f null -`).
    - Priority order: NVENC (`h264_nvenc`/`hevc_nvenc`) -> Intel QSV (`h264_qsv`/`hevc_qsv`) -> AMD AMF (`h264_amf`/`hevc_amf`) -> CPU fallback (`libx264`/`libx265`).
    - Parameter mapping for visually lossless output (CQ 18 for NVENC, ICQ 18 for QSV, CQP 18 for AMF, CRF 18 for CPU).
    - In-memory caching with `clear_cache()` support.
  - `src/vkdub/media/clip_engine.py` (490 lines):
    - `sanitize_filename()`: Windows path sanitization stripping illegal characters `<>:"/\\|?*`, ASCII control characters `0x00-0x1F`, reserved device names `CON, PRN, AUX, NUL, COM1-9, LPT1-9`, trailing dots/spaces, and max length truncation.
    - `parse_timecode()`: Supports `HH:MM:SS.mmm`, `MM:SS.mmm`, float/int seconds, formatted string seconds, and strictly rejects negative values.
    - `build_stream_copy_trim_command()`: `-ss {start} -to {end} -i {src} -c copy -avoid_negative_ts make_zero -movflags +faststart`.
    - `build_frame_accurate_trim_command()`: `-ss {start} -to {end} -i {src} -c:v {hw_encoder} {hw_params} -c:a aac -b:a 192k -movflags +faststart`.
    - `create_concat_manifest()` & `build_concat_command()`: Cross-platform concat demuxer manifest builder using forward slashes and quote escaping, executed via `ffmpeg -f concat -safe 0 -i manifest.txt -c copy`.
    - `ClipEngine`: End-to-end trim and merge engine with subprocess error diagnostics and `kill_process_tree(pid)` process tree termination.
- **Verification Results**:
  - Command: `cmd.exe /c "set PYTHONPATH=src&& D:\Work\Project_AI\ToolVideo\.venv\Scripts\python.exe -m pytest tests/test_clip_engine.py tests/test_render.py -v"`
  - Output: `40 passed in 1.95s` (100% pass rate).
  - Linting: `ruff check src/vkdub/media/ytdlp.py src/vkdub/media/hardware.py src/vkdub/media/clip_engine.py tests/test_clip_engine.py` returned 0 errors.

## 2. Logic Chain
1. Requirement R4 mandates safe yt-dlp discovery and single-download caching per `(video_id, quality)` with opt-in cookies.
   - Observation shows `ytdlp.py` discovers yt-dlp following the 5-step search order, sets parent directory in `PATH`, verifies cache existence and ffprobe validity, and strictly omits cookie arguments for public videos.
2. Requirement R3 mandates hardware acceleration detection with graceful fallback.
   - Observation confirms `hardware.py` executes an active 1-frame probe test, selecting NVENC when present, falling back to QSV -> AMF -> libx264/libx265, caching results in memory to avoid repetitive child process launches.
3. Requirement R3 & Acceptance Criteria mandate Windows-safe path sanitization, stream-copy, frame-accurate trimming, and concat merging.
   - Observation shows `clip_engine.py` sanitizes reserved words (e.g. `CON` -> `_CON`) and illegal characters, parses multi-format timecodes, constructs exact FFmpeg stream-copy and frame-accurate commands, and performs lossless multi-clip concat demuxer merges.
4. Comprehensive test suite `tests/test_clip_engine.py` covers discovery, caching, cookie safety, hardware probing, fallback, sanitization, timecodes, command generation, error handling, process tree killing, and real FFmpeg end-to-end execution.
   - All 40 tests passed without regression to existing tests (`test_render.py`).

## 3. Caveats
- Real download from YouTube was not executed against live servers (as instructed by Acceptance Criteria §Video Processing and Test Suite to prevent external network dependencies and rate limits). Mocked subprocess runs and real synthetic FFmpeg lavfi integration tests were used instead.
- AMD AMF hardware acceleration failed on the test workstation due to lack of AMD GPU hardware; the fallback chain to NVENC/QSV/libx264 was verified and operates as designed.

## 4. Conclusion
Milestone M2 implementation is complete, genuine, and verified.
All four assigned files:
- `src/vkdub/media/ytdlp.py`
- `src/vkdub/media/hardware.py`
- `src/vkdub/media/clip_engine.py`
- `tests/test_clip_engine.py`
are implemented to specification, fully documented, pass all lint checks, and achieve a 100% pass rate on unit and integration tests.

## 5. Verification Method
To independently verify this work:
```powershell
cmd.exe /c "set PYTHONPATH=src&& D:\Work\Project_AI\ToolVideo\.venv\Scripts\python.exe -m pytest tests/test_clip_engine.py tests/test_render.py -v"
```
Lint verification:
```powershell
cmd.exe /c "D:\Work\Project_AI\ToolVideo\.venv\Scripts\python.exe -m ruff check src/vkdub/media/ytdlp.py src/vkdub/media/hardware.py src/vkdub/media/clip_engine.py tests/test_clip_engine.py"
```
Expected result: 40 passed tests, 0 lint errors.
