# Handoff Report: Video Processing Backend, yt-dlp & FFmpeg Hardware Acceleration

**Agent**: Explorer 3 (Video Engine, yt-dlp & FFmpeg Hardware Acceleration Explorer)  
**Date**: 2026-09-15  
**Working Directory**: `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_video`  
**Report Artifact**: `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_video\report.md`

---

## 1. Observation

1. **Existing Tool Assets**:
   - `tools/ffmpeg.exe` exists (size: 101,457,920 bytes). Version output: `ffmpeg version 8.1.1-essentials_build-www.gyan.dev Copyright (c) 2000-2026 the FFmpeg developers`.
   - `tools/ffprobe.exe` exists (size: 101,251,072 bytes).
   - `tools/yt-dlp.exe` does NOT exist in the repository or virtual environment.
   - FFmpeg compiled build configuration contains: `--enable-amf --enable-cuda-llvm --enable-cuvid --enable-ffnvcodec --enable-libvpl --enable-nvdec --enable-nvenc --enable-libx264 --enable-libx265`.

2. **Empirical Hardware Encoder Probe Results on Host Machine**:
   - Probe command: `.\tools\ffmpeg.exe -v error -f lavfi -i color=s=256x256:d=0.04 -c:v <encoder> -frames:v 1 -f null -`
   - `h264_nvenc`: Exit code 0 (NVIDIA NVENC is operational).
   - `hevc_nvenc`: Exit code 0 (NVIDIA HEVC NVENC is operational).
   - `h264_qsv`: Exit code 0 (Intel Quick Sync is operational).
   - `h264_amf`: Exit code 1 (`[AMF @ ...] DLL amfrt64.dll failed to open; Failed to create hardware device context (AMF)`).
   - `libx264` / `libx265`: Exit code 0 (CPU software fallback is operational).

3. **Existing Tool Discovery Architecture**:
   - `src/vkdub/media/process.py:11-97` defines `find_tool(name: str) -> str | None`. It checks `{name.upper()}_PATH`, bundled dirs (`tools/`, `tools/ffmpeg/`, `bin/`), `shutil.which(name)`, WinGet, and common Windows paths.
   - Does NOT currently search `tools/yt-dlp/yt-dlp.exe`.
   - Automatic PATH injection occurs at `src/vkdub/media/process.py:18-19`.

4. **Bridge Communication Architecture**:
   - `src/vkdub/bridge/local_agent.py:35` listens on loopback TCP/WebSocket `127.0.0.1:49814`.
   - `tools/native_host/vkdub_host.py:40` connects to `127.0.0.1:49814` and relays Chromium Native Messaging stdio frames.
   - `apps/browser-extension/bridge/nativeMessaging.js:9` connects via WebSocket `ws://127.0.0.1:49814/ws`.
   - Current actions in `src/vkdub/bridge/protocol.py:12-25` and `apps/browser-extension/bridge/protocol.js:9-29` handle ChatGPT translation and Vbee TTS.

5. **Existing Render & Export Services**:
   - `src/vkdub/services/render_service.py:32-99` builds FFmpeg argument list with `libx264` default, no hardware encoder auto-detection.
   - `src/vkdub/services/render_service.py:23-29` escapes Windows paths for filters.
   - `src/vkdub/services/render_service.py:102-111` parses progress from FFmpeg stderr using regex `r"time=(\d+):(\d+):(\d+\.\d+)"`.
   - `src/vkdub/web/server.py:448-460` provides `/api/media/select` to load media into `state.project.video_path`.

6. **Test Environment**:
   - Running `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_render.py` passed 7/7 tests.
   - Running `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_bridge_protocol.py` passed 4/4 tests.

---

## 2. Logic Chain

1. **From Observation 1 and 3**:
   `yt-dlp` is not yet bundled or integrated into `find_tool`.
   *Inference*: A dedicated discovery module (or updated `find_tool`) must be created that strictly adheres to the search order: `YTDLP_PATH` env → `tools/yt-dlp/yt-dlp.exe` → `tools/yt-dlp.exe` → system `PATH` → WinGet/Scoop. If `YTDLP_PATH` is specified but invalid, it must return `None` without falling back.

2. **From Observation 1 and 2**:
   `ffmpeg -encoders` outputs `h264_amf`, `h264_nvenc`, and `h264_qsv`. However, running `h264_amf` fails with missing DLL `amfrt64.dll`.
   *Inference*: Static string matching of encoder names is unsafe. The hardware encoder selection module MUST perform an active 1-frame probe test (`color=s=256x256:d=0.04 -frames:v 1 -f null -`) and cache the result. On this workstation, NVENC and QSV will be chosen, while systems without dedicated GPUs will fall back to `libx264`/`libx265`.

3. **From Requirement R4 and Observation 1**:
   `yt-dlp` needs FFmpeg to merge `bestvideo + bestaudio` into an MP4 container.
   *Inference*: `yt-dlp` invocations must pass `--ffmpeg-location str(Path(ffmpeg_exe).parent)` and `--merge-output-format mp4`.

4. **From Requirement R4 and Cookie Security**:
   Running `--cookies-from-browser` locks Chromium SQLite databases, causes delays, and risks account flags.
   *Inference*: Public videos must never receive cookie parameters. The command builder must only pass `--cookies-from-browser <browser>` when `use_cookies` is explicitly `True`.

5. **From Requirement R3 and Observation 5**:
   Two cutting modes are required:
   - "Siêu nhanh": Stream copy (`-c copy`) with `-avoid_negative_ts make_zero` (snaps to keyframe).
   - "Chính xác từng khung hình": Re-encodes using detected hardware encoder (NVENC/QSV/AMF at CQ/CRF 18) or CPU `libx264`/`libx265`.
   *Inference*: Separate command builders for stream copy and frame-accurate re-encoding are required, along with a concat demuxer (`-f concat -safe 0`) for merging selected clips.

6. **From Requirement R4 & R5 and Observation 4**:
   `LocalAgent` receives export requests asynchronously from the browser extension.
   *Inference*: A `ClipExportService` / `JobManager` must run downloads and trims in worker threads, manage process trees (using Windows `taskkill /F /T /PID` on cancellation), track idempotent `request_id`, sanitize Windows file names, clean scratch directories, and stream progress events (`CLIP_EXPORT_PROGRESS`).

---

## 3. Caveats

1. **yt-dlp Executable Distribution**:
   While discovery and execution architecture is fully designed, `yt-dlp.exe` is not currently checked into Git (binary size ~15-30MB). An installer or automated setup script may need to place it in `tools/yt-dlp/yt-dlp.exe`.
2. **Direct YouTube Network Downloads in Tests**:
   Automated unit and integration test suites should mock subprocess execution of `yt-dlp` and `ffmpeg` to prevent tests from failing due to external network rate limits or bot blocking.
3. **No Caveats Regarding Local Capabilities**:
   Local FFmpeg hardware acceleration via NVENC and QSV was tested and confirmed functional on this host.

---

## 4. Conclusion

1. **yt-dlp Integration**: Ready to implement in `src/vkdub/media/ytdlp.py` with the 5-step search precedence order, single-download caching per `video_id`, `--merge-output-format mp4`, and strict opt-in cookie isolation.
2. **FFmpeg Trimming & Concat**: Ready to implement in `src/vkdub/media/clip_engine.py` with dual-mode stream-copy vs frame-accurate trimming, plus lossless concat demuxer merging.
3. **Hardware Encoder Detection**: Ready to implement in `src/vkdub/media/hardware.py` using active 1-frame probes with memory caching, prioritizing NVENC → QSV → AMF → `libx264`/`libx265` (CRF 17-18).
4. **Job Execution & Security**: Ready to implement in `src/vkdub/services/clip_export_service.py` with Windows path sanitization, traversal prevention, `CREATE_NO_WINDOW`, `taskkill` process-tree cancellation, idempotent `request_id`, and timeline import to `server.py` and `MainWindow`.

---

## 5. Verification Method

1. **Verify Report and Documentation**:
   Inspect `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_video\report.md`.
2. **Verify Host Hardware Encoders**:
   ```powershell
   .\tools\ffmpeg.exe -v error -f lavfi -i color=s=256x256:d=0.04 -c:v h264_nvenc -frames:v 1 -f null -
   echo "NVENC exit code: $LASTEXITCODE"
   .\tools\ffmpeg.exe -v error -f lavfi -i color=s=256x256:d=0.04 -c:v h264_qsv -frames:v 1 -f null -
   echo "QSV exit code: $LASTEXITCODE"
   ```
3. **Verify Existing Tests**:
   ```powershell
   $env:PYTHONPATH='src'
   .\.venv\Scripts\python.exe -m pytest tests/test_render.py tests/test_bridge_protocol.py
   ```
4. **Invalidation Conditions**:
   - If FFmpeg binaries in `tools/` are updated or replaced with builds lacking hardware codecs.
   - If Windows OS environment alters GPU driver access for NVENC/QSV.
