# Test Infrastructure — VK Dub Studio YouTube Clip Mode

## 1. Overview & Architecture

This document specifies the testing infrastructure, methodology, and execution architecture for the YouTube Clip Mode test suite in VK Dub Studio.

The test suite is structured into two complementary test files covering a 4-Tier verification hierarchy:
1. `tests/test_youtube_clip_mode.py`: Focused unit, boundary, and contract tests for individual components (Tier 1: Feature Coverage & Tier 2: Boundary & Corner Cases). Total: 124 tests.
2. `tests/test_e2e_clip_pipeline.py`: End-to-end integration workflows, cross-feature combinations, and real-world multi-step scenarios (Tier 3: Cross-Feature Combinations & Tier 4: Real-World Scenarios). Total: 40 tests.

**Total Test Count**: 164 automated tests  
**Execution Time**: ~1.45 seconds (100% offline, zero network dependencies)

---

## 2. 4-Tier Testing Methodology

```
+-----------------------------------------------------------------------------------+
| TIER 4: Real-World Scenarios (20 tests)                                           |
| - Podcast highlight extraction (3 segments, separate / merged reel)               |
| - Long gaming stream trimming (5 segments, non-sequential, >3 hours)              |
| - Rapid YouTube Short extraction (<15s, subsecond)                                |
| - Network error recovery, telemetry streaming & idempotency                       |
+-----------------------------------------------------------------------------------+
                                          ▲
+-----------------------------------------|-----------------------------------------+
| TIER 3: Cross-Feature Combinations (20 tests)                                     |
| - Stream-copy + Merged export                                                     |
| - Frame-Accurate + NVENC hardware acceleration + Single clip export               |
| - Stream-copy + Import to ToolVideo Studio timeline / Project state               |
| - Opt-in cookies vs public video zero-cookie enforcement                          |
| - Frame-Accurate + CPU fallback + MKV container without faststart                 |
+-----------------------------------------------------------------------------------+
                                          ▲
+-----------------------------------------|-----------------------------------------+
| TIER 2: Boundary & Corner Cases (56 tests)                                        |
| - Empty/whitespace titles, special characters, and Unicode/Vietnamese diacritics  |
| - Windows reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)              |
| - Timestamp boundaries: start=0, start=end (zero length), end>duration, negative  |
| - Missing tool resilience: missing yt-dlp, missing ffmpeg, AMF missing DLL        |
| - Cancellation handling: process tree killing (taskkill /F /T /PID) & cleanup     |
+-----------------------------------------------------------------------------------+
                                          ▲
+-----------------------------------------|-----------------------------------------+
| TIER 1: Feature Coverage (68 tests)                                               |
| - URL parsing (standard watch, youtu.be, embed, shorts, mobile, query params)     |
| - ClipItem validation & fractional precision                                      |
| - Timecode parsing & formatting (HH:MM:SS.mmm, MM:SS, numeric, filename-safe)     |
| - Windows filename sanitization & path safety                                     |
| - Hardware encoder probing & priority matrix (NVENC -> QSV -> AMF -> libx264)     |
| - FFmpeg stream-copy command generation (-c copy, -avoid_negative_ts make_zero)   |
| - FFmpeg frame-accurate command generation (CQ/CRF 18, high-quality audio)        |
| - Concat demuxer manifest generation (ffconcat version 1.0, quoting safety)       |
| - yt-dlp 5-step discovery precedence order                                        |
| - Protocol message serialization & bidirectional schema conversion                |
+-----------------------------------------------------------------------------------+
```

---

## 3. Mocking Strategy & Determinism

### 3.1 Subprocess & Network Decoupling
To achieve deterministic execution in <2 seconds:
- **yt-dlp Downloads**: `subprocess.Popen` is mocked when exercising network failure, progress telemetry, or cancellations. Cache hits bypass execution completely.
- **FFmpeg Trimming & Concat**: Command generation functions (`build_stream_copy_trim_command`, `build_frame_accurate_trim_command`, `build_concat_command`) produce inspectable `list[str]` argv arrays verified directly. File operations touch synthetic zero-byte or small mock files in isolated temporary directories (`tmp_path`).
- **Hardware Probes**: `subprocess.run` exit codes are intercepted to simulate available or missing GPU drivers (`h264_nvenc`, `h264_qsv`, `h264_amf`, `libx264`). In-memory cache clearing (`clear_hw_cache`) is executed before each hardware test to avoid cross-test contamination.

### 3.2 Process Tree Killing on Windows
On Windows, child processes spawned by yt-dlp or ffmpeg must be terminated cleanly. `kill_process_tree(pid)` invokes:
`taskkill /F /T /PID {pid}`
The test suite verifies that `kill_process_tree` is triggered whenever a job is cancelled mid-download or mid-trimming.

---

## 4. Authoritative Verification Sources

All expected outputs, parameter thresholds, and error modes are derived from:
1. `ORIGINAL_REQUEST.md` (## 2026-09-15T04:12:10Z):
   - R1: In-player toolbar hotkeys (`I`, `O`, `Enter`, `Escape`), timecode extraction.
   - R2: Clip validation (`start < end`, `end <= duration`, `duration >= 0.5s`).
   - R3: Stream-copy (`-c copy`), Frame-accurate (NVENC/QSV/AMF/x264, CRF 17-18).
   - R4: yt-dlp discovery order (5 steps), opt-in cookies (public videos NEVER use cookies), single download caching, path sanitization.
   - R5: 10 Protocol Actions (`YOUTUBE_CONTEXT_SYNC`, `CLIP_EXPORT_REQUEST`, etc.).
2. `PROJECT.md` § Architecture, Interface Contracts, and Milestones.
3. Windows Filesystem Specification:
   - Reserved filenames (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`).
   - Prohibited characters (`< > : " / \ | ? *`).

---

## 5. How to Run the Tests

### Primary Command
```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_youtube_clip_mode.py tests/test_e2e_clip_pipeline.py -v
```

### Run with Short Summary
```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_youtube_clip_mode.py tests/test_e2e_clip_pipeline.py -q
```

### Run Regression Verification (All Bridge & Media Suites)
```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_youtube_clip_mode.py tests/test_e2e_clip_pipeline.py tests/test_bridge_protocol.py tests/test_clip_engine.py tests/test_render.py -v
```
