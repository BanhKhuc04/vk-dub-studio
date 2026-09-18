# Milestone M2 Implementation: Video Engine (yt-dlp, HW Accel, Trimming & Concat)

## 2026-09-15T04:19:34Z

Read `D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md` (specifically ## 2026-09-15T04:12:10Z), `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_2\PROJECT.md`, and `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_video\report.md`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Write Ownership
You exclusively own:
- `src/vkdub/media/ytdlp.py`
- `src/vkdub/media/hardware.py`
- `src/vkdub/media/clip_engine.py`
- `tests/test_clip_engine.py`

## Objective & Tasks
1. Implement `src/vkdub/media/ytdlp.py`:
   - `find_ytdlp()` strictly obeying the 5-step search order: `YTDLP_PATH` env -> `tools/yt-dlp/yt-dlp.exe` -> `tools/yt-dlp.exe` -> system PATH -> WinGet/Scoop.
   - `YtDlpDownloader` with single-download caching per `(video_id, quality)` in `cache/youtube/{video_id}`.
   - Strictly opt-in cookies (public videos NEVER pass cookie arguments).
   - Pass `--ffmpeg-location` pointing to bundled ffmpeg directory.
   - Output container `--merge-output-format mp4`.
2. Implement `src/vkdub/media/hardware.py`:
   - `HardwareEncoderDetector` with active 1-frame probe test (`-f lavfi -i color=s=256x256:d=0.04 -c:v <encoder> -frames:v 1 -f null -`).
   - Priority: NVIDIA NVENC (`h264_nvenc`/`hevc_nvenc`) -> Intel QSV (`h264_qsv`) -> AMD AMF (`h264_amf`) -> CPU `libx264`/`libx265`.
   - In-memory caching of probe results.
3. Implement `src/vkdub/media/clip_engine.py`:
   - Windows path sanitization: strip `<>:"/\\|?*`, reserved names `CON/PRN/AUX/NUL/COM1-9/LPT1-9`, control characters, trailing dots/spaces, truncate long names.
   - Stream-copy trimming: `-ss {start} -to {end} -i {src} -c copy -avoid_negative_ts make_zero`.
   - Frame-accurate trimming: `-ss {start} -to {end} -i {src} -c:v {hw_encoder_or_libx264} -crf 18 -c:a aac -b:a 192k`.
   - Multi-clip concat demuxer: build `concat_manifest.txt` and run `ffmpeg -f concat -safe 0 -i manifest.txt -c copy {merged_output}`.
   - Timecode parsing: parse `HH:MM:SS.mmm`, `MM:SS`, or float seconds to seconds float.
4. Write unit tests in `tests/test_clip_engine.py` covering all features (with subprocess mocks for yt-dlp / ffmpeg where needed).
5. Run tests:
   `cmd.exe /c "set PYTHONPATH=src&& D:\Work\Project_AI\ToolVideo\.venv\Scripts\python.exe -m pytest tests/test_clip_engine.py tests/test_render.py -v"`
6. Document results in `handoff.md` and message parent when complete.
