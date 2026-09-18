# VK Dub Studio — Video Processing Backend, yt-dlp & FFmpeg Hardware Acceleration Survey

**Date**: 2026-09-15  
**Author**: Explorer 3 (Video Engine, yt-dlp & FFmpeg Hardware Acceleration Explorer)  
**Target Milestone**: YouTube Clip Mode & Video Processing Pipeline Architecture  
**Working Directory**: `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_video`  
**Target Project Root**: `D:\Work\Project_AI\ToolVideo`  
**Authoritative Reference**: `D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md` (## 2026-09-15T04:12:10Z)

---

## 1. Executive Summary & Codebase Context

VK Dub Studio is an AI-powered automated video dubbing pipeline for Windows. The application operates in two client surfaces:
1. **PySide6 Desktop Application** (`src/vkdub/app.py`, `src/vkdub/ui/main_window.py`).
2. **KAPPAK Studio Web v2** (`src/vkdub/web/server.py`, FastAPI on port 8000).

Both application surfaces communicate with the browser ecosystem (Chrome/Edge Extension) via:
- A local TCP/WebSocket server in `src/vkdub/bridge/local_agent.py` listening on `127.0.0.1:49814`.
- A Chromium Native Messaging Host in `tools/native_host/vkdub_host.py` (`com.vkdub.bridge`).

The milestone requirement (`ORIGINAL_REQUEST.md` ## 2026-09-15T04:12:10Z) introduces **YouTube Clip Mode**:
- Users mark clips on `https://www.youtube.com/watch*` via in-player toolbar and side panel.
- Export requests are relayed via Native Messaging / WebSocket to `LocalAgent`.
- Backend downloads source video using `yt-dlp` (cached once per `video_id`), executes trimming/merging via FFmpeg, and optionally imports exported clips directly into ToolVideo timeline/pipeline.

---

## 2. `yt-dlp` Discovery, Binary Strategy & Cookie Security

### 2.1 Current State Analysis
- `yt-dlp` does **not** currently exist in the repository or virtual environment (`pyproject.toml` contains PySide6, faster-whisper, httpx, keyring, numpy, playwright).
- `tools/` currently contains `ffmpeg.exe` (101.4 MB) and `ffprobe.exe` (101.2 MB).
- Existing tool discovery is implemented in `src/vkdub/media/process.py:11` (`find_tool(name: str)`).

### 2.2 Discovery Order & Specification Compliance
Per requirement R4, `yt-dlp` resolution must follow this exact precedence order:
1. **`YTDLP_PATH` Environment Variable**:
   - Explicit environment override takes absolute precedence.
   - If set and points to an existing file: return `str(Path(YTDLP_PATH).resolve())`.
   - If set but file does NOT exist: return `None` (authoritative override principle; prevent silent fallback to mismatched binary).
2. **Bundled Tool Subdirectory**:
   - `tools/yt-dlp/yt-dlp.exe` (and non-Windows `tools/yt-dlp/yt-dlp`).
3. **Bundled Tool Root**:
   - `tools/yt-dlp.exe` (and non-Windows `tools/yt-dlp`).
4. **System PATH**:
   - `shutil.which("yt-dlp")`.
5. **Windows Package Managers & Shims**:
   - WinGet links: `%LOCALAPPDATA%\Microsoft\WinGet\Links\yt-dlp.exe`
   - WinGet packages: `%LOCALAPPDATA%\Microsoft\WinGet\Packages\**\yt-dlp.exe`
   - Scoop shims: `%USERPROFILE%\scoop\shims\yt-dlp.exe`
   - Chocolatey: `%ALLUSERSPROFILE%\chocolatey\bin\yt-dlp.exe`

### 2.3 PATH Injection Behavior
Following the pattern established in `src/vkdub/media/process.py:12-20`, once the tool path is discovered, its parent directory must be injected into `os.environ["PATH"]` so that dependent child processes and short invocations succeed universally.

### 2.4 Cookie Opt-In Security Rules
- **Rule**: Public videos must NEVER invoke browser cookies.
- **Problem**: Passing `--cookies-from-browser` unconditionally causes yt-dlp to lock SQLite databases of running browsers (`database is locked`), triggers Windows DPAPI security elevation/delay, and risks account flagging by YouTube.
- **Enforcement**:
  - Default: `use_cookies = False`.
  - Only when `use_cookies is True` and user explicitly selects browser in the extension UI (`cookie_browser` in `["edge", "chrome", "firefox", "brave"]`), pass:
    `["--cookies-from-browser", cookie_browser]`
  - If `use_cookies` is False: Zero cookie parameters in argv.

---

## 3. Single Download & Remux Caching Engine

### 3.1 Caching Strategy
- **Principle**: A YouTube video is downloaded and remuxed **at most once** per `(video_id, quality)`. Multiple clip slices extracted from the same video MUST reuse the cached master file.
- **Cache Location**:
  `workspace_root() / "cache" / "youtube" / {video_id}`
  (Resolves via `src/vkdub/utils/paths.py:13` to `%LOCALAPPDATA%\VKDubStudio\cache\youtube\{video_id}`).
- **Cache Master Filename**:
  `source_{video_id}_{quality}.mp4` (e.g. `source_dQw4w9WgXcQ_1080p.mp4`).

### 3.2 Cache Validation & Integrity Check
Before downloading, check:
1. `cache_path.is_file() and cache_path.stat().st_size > 1024 * 1024` (at least 1 MB).
2. Validate container integrity with `ffprobe`:
   Execute fast stream check (`ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {cache_path}`).
3. If valid, skip download entirely; report 100% download progress and proceed directly to trimming.
4. If corrupt or incomplete (`.part` file remaining), remove invalid file and perform clean download.

### 3.3 yt-dlp Command Construction
```python
def build_ytdlp_download_command(
    ytdlp_exe: str,
    ffmpeg_exe: str,
    video_url: str,
    target_output: Path,
    quality: str = "1080p",
    use_cookies: bool = False,
    cookie_browser: str | None = None,
) -> list[str]:
    # Format selector matrix
    quality_map = {
        "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
        "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "best": "bestvideo+bestaudio/best",
    }
    format_spec = quality_map.get(quality.lower(), quality_map["1080p"])

    args = [
        ytdlp_exe,
        "--no-playlist",
        "--no-warnings",
        "--newline",
        "-f", format_spec,
        "--merge-output-format", "mp4",
        "--ffmpeg-location", str(Path(ffmpeg_exe).parent),
        "-o", str(target_output),
    ]

    if use_cookies and cookie_browser:
        args.extend(["--cookies-from-browser", cookie_browser])

    args.append(video_url)
    return args
```

### 3.4 Download Telemetry Parsing
yt-dlp emits progress lines to stdout:
```
[download]  45.2% of ~150.20MiB at 4.25MiB/s ETA 00:19
[download] 100% of 150.20MiB in 00:35 at 4.29MiB/s
[Merger] Merging formats into "..."
```
Regex pattern:
`r"\[download\]\s+([\d\.]+)%\s+of\s+~?([\d\.]+\s*[KkMmGg]?i?B)\s+at\s+([\d\.]+[KkMmGg]?i?B/s)\s+ETA\s+(\S+)"`
Extracts:
- `progress_pct`: `float(match.group(1))`
- `total_size`: `match.group(2)`
- `speed`: `match.group(3)`
- `eta`: `match.group(4)`
Emits `CLIP_EXPORT_PROGRESS` with phase `"downloading"` and `"remuxing"`.

---

## 4. FFmpeg Command Building: Stream Copy vs Frame-Accurate

### 4.1 Comparison Matrix

| Parameter | Stream Copy (`-c copy`) | Frame-Accurate Re-encoding |
|---|---|---|
| **Speed** | Ultra-fast (I/O bound, >500 fps, <2 sec) | Fast with GPU (80-200 fps), moderate with CPU |
| **Video Quality** | 100% original lossless (zero generational loss) | Visually lossless (CRF 17-18 or GPU CQ 18) |
| **Cut Precision** | Nearest Keyframe (GOP boundary, ~1-2s delta) | Frame-accurate (exact millisecond requested) |
| **HDR / Color Space** | 100% preserved (original BT.2020 / DCI-P3 / HLG) | Preserved or standard YUV420P Rec.709 |
| **CPU / GPU Load** | Minimal (<2% CPU, 0% GPU) | Hardware encoder (NVENC/QSV/AMF) or CPU |
| **User Notice Required** | Yes ("Nhảy theo keyframe gần nhất") | No (exact cut) |

### 4.2 Mode A: Stream Copy Command
```python
def build_stream_copy_trim_command(
    ffmpeg_exe: str,
    source_path: Path,
    output_path: Path,
    start_sec: float,
    end_sec: float,
) -> list[str]:
    duration = max(0.001, end_sec - start_sec)
    return [
        ffmpeg_exe,
        "-y",
        "-nostdin",
        "-ss", f"{start_sec:.3f}",
        "-i", str(source_path),
        "-t", f"{duration:.3f}",
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        "-movflags", "+faststart",
        str(output_path),
    ]
```

### 4.3 Mode B: Frame-Accurate Re-encoding Command
```python
def build_frame_accurate_trim_command(
    ffmpeg_exe: str,
    source_path: Path,
    output_path: Path,
    start_sec: float,
    end_sec: float,
    encoder_name: str,
    encoder_args: list[str],
    audio_codec: str = "copy",
) -> list[str]:
    duration = max(0.001, end_sec - start_sec)
    cmd = [
        ffmpeg_exe,
        "-y",
        "-nostdin",
        "-ss", f"{start_sec:.3f}",
        "-i", str(source_path),
        "-t", f"{duration:.3f}",
        "-c:v", encoder_name,
        *encoder_args,
        "-c:a", audio_codec,
    ]
    if audio_codec != "copy":
        cmd.extend(["-b:a", "192k"])
    cmd.extend(["-movflags", "+faststart", str(output_path)])
    return cmd
```

---

## 5. Hardware Encoder Detection & Quality Matrix

### 5.1 Bundled FFmpeg Capabilities
Empirically verified on bundled `tools/ffmpeg.exe`:
- **FFmpeg Version**: `8.1.1-essentials_build-www.gyan.dev`
- **Build Flags**: `--enable-amf`, `--enable-cuda-llvm`, `--enable-cuvid`, `--enable-ffnvcodec`, `--enable-libvpl`, `--enable-nvdec`, `--enable-nvenc`, `--enable-libx264`, `--enable-libx265`.
- **Supported Encoders in binary**:
  - NVIDIA: `h264_nvenc`, `hevc_nvenc`, `av1_nvenc`
  - Intel: `h264_qsv`, `hevc_qsv`, `av1_qsv`
  - AMD: `h264_amf`, `hevc_amf`, `av1_amf`
  - CPU Software: `libx264`, `libx265`

### 5.2 Empirical Hardware Probe Findings (Workstation Verification)
Running a 1-frame probe test (`color=s=256x256:d=0.04 -frames:v 1 -f null -`):
1. `h264_nvenc`: **AVAILABLE** (Exit Code 0).
2. `hevc_nvenc`: **AVAILABLE** (Exit Code 0).
3. `h264_qsv`: **AVAILABLE** (Exit Code 0).
4. `h264_amf`: **FAILED** (Exit Code 1, `DLL amfrt64.dll failed to open`, no AMD driver).
5. `libx264`: **AVAILABLE** (Exit Code 0).

**Critical Architecture Finding**:
Querying `ffmpeg -encoders` is INSUFFICIENT. FFmpeg was compiled with AMF support, but the encoder fails if the host GPU/driver is absent.
Hardware encoder selection MUST use **Active Probing** (running a 1-frame null test with 256x256 minimum dimensions) and cache the result.

### 5.3 Active Hardware Probe Implementation
```python
_DETECTED_ENCODERS: dict[str, str] = {}

def probe_encoder_operational(ffmpeg_exe: str, encoder: str) -> bool:
    import subprocess
    cmd = [
        ffmpeg_exe,
        "-v", "error",
        "-f", "lavfi",
        "-i", "color=s=256x256:d=0.04",
        "-c:v", encoder,
        "-frames:v", "1",
        "-f", "null",
        "-",
    ]
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
            timeout=3.0,
        )
        return res.returncode == 0
    except Exception:
        return False

def resolve_best_video_encoder(ffmpeg_exe: str, codec_family: str = "h264") -> tuple[str, list[str]]:
    cache_key = f"best_{codec_family}"
    if cache_key in _DETECTED_ENCODERS:
        enc = _DETECTED_ENCODERS[cache_key]
        return enc, get_encoder_params(enc)

    candidates = (
        ["h264_nvenc", "h264_qsv", "h264_amf", "libx264"]
        if codec_family == "h264"
        else ["hevc_nvenc", "hevc_qsv", "hevc_amf", "libx265"]
    )

    for cand in candidates:
        if cand.startswith("libx") or probe_encoder_operational(ffmpeg_exe, cand):
            _DETECTED_ENCODERS[cache_key] = cand
            return cand, get_encoder_params(cand)

    fallback = "libx264" if codec_family == "h264" else "libx265"
    return fallback, get_encoder_params(fallback)
```

### 5.4 Encoder Parameter Specifications (CRF 17-18 Equivalent)
1. **NVIDIA NVENC** (`h264_nvenc` / `hevc_nvenc`):
   - Parameters: `["-preset", "p5", "-rc", "vbr", "-cq", "18", "-b:v", "0", "-pix_fmt", "yuv420p"]`
   - Constant Quality mode at CQ 18 provides visually lossless output indistinguishable from x264 CRF 18.
2. **Intel QSV** (`h264_qsv` / `hevc_qsv`):
   - Parameters: `["-global_quality", "18", "-preset", "medium", "-pix_fmt", "yuv420p"]`
   - ICQ (Intelligent Constant Quality) mode at global_quality 18.
3. **AMD AMF** (`h264_amf` / `hevc_amf`):
   - Parameters: `["-rc", "cqp", "-qp_i", "18", "-qp_p", "18", "-qp_b", "18", "-quality", "quality", "-pix_fmt", "yuv420p"]`
4. **CPU Software Fallback** (`libx264` / `libx265`):
   - Parameters: `["-crf", "18", "-preset", "faster", "-pix_fmt", "yuv420p"]`

---

## 6. Container & Audio Handling

### 6.1 Container Formats: `mp4` vs `mkv`
- **MP4 (`.mp4`)**:
  - Default container for web player and desktop video player.
  - Requires `-movflags +faststart` to place the `moov` atom at the start of the file for instant HTML5 streaming without waiting for full download.
- **MKV (`.mkv`)**:
  - Matroska container; supports arbitrary audio codecs (Opus, Vorbis, FLAC) and chapter markers.
  - Does not require faststart.

### 6.2 Audio Handling Rules
- In **Stream Copy** mode:
  `-c:a copy` preserves the original audio stream without recompression.
- In **Frame-Accurate** mode:
  - If target container is MP4 and source audio is AAC: use `-c:a copy`.
  - If source audio is Opus or incompatible with MP4 container: transcode to high-quality AAC:
    `["-c:a", "aac", "-b:a", "192k"]`.

---

## 7. Multi-Clip Merging / Concatenation Engine

### 7.1 Objective
Merge all exported clip segments into a single file `{video_title}_selected_clips.{mp4|mkv}` smoothly without desync or re-encoding penalties.

### 7.2 Concat Demuxer Engine (Lossless & Fast)
Since all clips are cut from the identical source file with matching resolution, framerate, codecs, and timebases:
1. Write temporary concat manifest in scratch directory (`concat_manifest.txt`):
   ```
   ffconcat version 1.0
   file 'clip_1.mp4'
   file 'clip_2.mp4'
   file 'clip_3.mp4'
   ```
2. Command:
   ```python
   cmd = [
       ffmpeg_exe,
       "-y",
       "-nostdin",
       "-f", "concat",
       "-safe", "0",
       "-i", str(manifest_path),
       "-c", "copy",
       "-movflags", "+faststart",
       str(merged_output_path),
   ]
   ```
3. Speed: Under 1.5 seconds for multi-minute videos.

### 7.3 Filter Complex Concat Fallback
In rare edge cases where stream copy concat fails (e.g. non-zero audio pre-roll or mismatched start PTS):
```python
# Fallback filter complex:
# -filter_complex "[0:v][0:a][1:v][1:a]...concat=n=N:v=1:a=1[v][a]" -map "[v]" -map "[a]"
```
Re-encodes cleanly using the detected hardware encoder.

---

## 8. Job Execution Architecture & Security

### 8.1 Safe Subprocess Execution (Argv Array Security)
- **Zero Shell Concatenation**: Subprocess execution MUST use `list[str]`. Never pass a single concatenated command string or use `shell=True`.
- **Windows Flag**: `creationflags=0x08000000` (`CREATE_NO_WINDOW`) to prevent black console flashes.

### 8.2 Windows Path Sanitization & Traversal Prevention
Remote video titles on YouTube often contain characters illegal in Windows file systems:
- Illegal characters: `< > : " / \ | ? *` and ASCII controls `0x00 - 0x1F`.
- Reserved device names: `CON, PRN, AUX, NUL, COM1-COM9, LPT1-LPT9`.
- Path traversal vectors: `../`, `..\`, absolute paths `C:\`.
- Windows trailing space/dot restriction: Windows removes or rejects filenames ending in dot or space.

**Sanitization Algorithm**:
```python
import re

WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

def sanitize_filename(name: str, max_length: int = 100, replacement: str = "_") -> str:
    # 1. Strip path traversal and slashes
    clean = name.replace("\\", replacement).replace("/", replacement)
    # 2. Strip Windows illegal filename characters
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', replacement, clean)
    # 3. Strip trailing dots and spaces
    clean = clean.strip(" .")
    # 4. Check against Windows reserved device names
    stem = clean.split(".")[0].upper()
    if stem in WINDOWS_RESERVED:
        clean = f"_{clean}"
    # 5. Fallback for empty names
    if not clean:
        clean = "youtube_video"
    # 6. Limit max length to avoid MAX_PATH issues
    if len(clean) > max_length:
        clean = clean[:max_length].rstrip(" .")
    return clean
```

### 8.3 Safe Temp/Scratch Lifecycle
- **Scratch Directory**:
  `workspace_root() / "scratch" / "youtube_clips" / {request_id}`
- **Lifecycle Guarantees**:
  1. Created on job initiation.
  2. Intermediate files (partial downloads, individual segment clips, concat manifests) are written here.
  3. On success: Final outputs copied/moved to user-selected `output_dir`. Scratch directory recursively purged via `shutil.rmtree`.
  4. On cancellation or error: Scratch directory purged immediately, leaving zero orphaned temporary files.

### 8.4 Job Cancellation (`CLIP_EXPORT_CANCEL`) & Process Tree Killing
On Windows, when `yt-dlp` runs, it may spawn `ffmpeg` as a child process. A simple `proc.kill()` can leave `ffmpeg.exe` orphaned and continuing to write disk.
**Process Tree Termination**:
```python
def cancel_job_process(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    if sys.platform == "win32":
        # /F = force, /T = terminate entire process tree
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            creationflags=0x08000000,
        )
    else:
        proc.kill()
```

### 8.5 Idempotent `request_id` Management
- Every export request from the browser extension carries a unique `request_id` (UUIDv4).
- `JobManager` tracks active jobs in a dictionary: `_active_jobs: dict[str, ClipExportJob]`.
- If a duplicate request with the same `request_id` is received while running:
  - Respond immediately with `CLIP_EXPORT_ACCEPTED` without launching a duplicate job.
- Prevents accidental multi-click race conditions.

---

## 9. Native Bridge & Realtime Protocol Mapping

### 9.1 Protocol Actions (`protocol.py` & `protocol.js`)
The following actions extend the existing ChatGPT / Vbee bridge:

| Action | Direction | Payload Structure | Purpose |
|---|---|---|---|
| `YOUTUBE_CONTEXT_SYNC` | Ext → Agent | `{ video_id, title, url, duration }` | Extension synchronizes active video context |
| `YOUTUBE_SEEK_TO` | Agent → Ext | `{ time_seconds }` | Ask extension content script to seek player |
| `YOUTUBE_PREVIEW_CLIP` | Agent → Ext | `{ start, end }` | Playback marked clip in YouTube player |
| `CLIP_EXPORT_REQUEST` | Ext → Agent | `{ request_id, video_url, video_id, title, clips: [...], mode, merge, output_dir, container, quality, use_cookies, cookie_browser, import_to_timeline }` | Start clip export |
| `CLIP_EXPORT_ACCEPTED` | Agent → Ext | `{ request_id, status: "accepted" }` | Acknowledge start of processing |
| `CLIP_EXPORT_PROGRESS` | Agent → Ext | `{ request_id, phase, progress, clip_index, total_clips, speed, eta, message }` | Realtime progress updates |
| `CLIP_EXPORT_RESULT` | Agent → Ext | `{ request_id, success: true, files: [...], merged_file, output_dir }` | Job completion details |
| `CLIP_EXPORT_ERROR` | Agent → Ext | `{ request_id, success: false, error: str }` | Error report |
| `CLIP_EXPORT_CANCEL` | Ext → Agent | `{ request_id }` | Request cancellation |
| `OPEN_OUTPUT_FOLDER` | Ext → Agent | `{ path: str }` | Open Windows Explorer to folder |

### 9.2 Realtime Progress Phases
1. `checking`: Checking local cache for `video_id`.
2. `downloading`: `yt-dlp` downloading source video (`progress %`, `speed`, `eta`).
3. `remuxing`: yt-dlp remuxing audio/video streams.
4. `cutting`: FFmpeg trimming clips (progress `clip_index / total_clips`).
5. `merging`: FFmpeg concat demuxer assembling selected clips.
6. `completed`: Output files ready in destination directory.

---

## 10. ToolVideo Timeline / Pipeline Import Integration

When user selects "Cắt đoạn và tự động nạp vào timeline/pipeline ToolVideo để tiếp tục lồng tiếng":
1. The exported file path (either `merged_file` or selected clip) is resolved.
2. In **Desktop GUI** (`MainWindow`):
   - LocalAgent emits `video_imported = Signal(str)`.
   - `MainWindow.load_project_file` or direct video loading sets `self.project.video_path = Path(path)`, triggers `self.tools.probe(path)`, loads preview player `self.preview.load(path)`, and activates Step 1 summary.
3. In **FastAPI Server** (`server.py`):
   - LocalAgent calls internal video selection or client triggers `POST /api/media/select` with `{"path": path}`.
   - `state.project.video_path = Path(path)` and video metadata are updated.
   - WebSocket broadcast (`type: "media_selected"`) notifies the web player.
4. **"Mở thư mục" Action**:
   - Executes safe Windows Explorer invocation:
     `subprocess.run(["explorer.exe", f"/select,{str(target_file)}"])`
     This opens Windows File Explorer with the specific exported file highlighted.

---

## 11. Proposed Module Architecture & Implementation Plan

```
src/vkdub/
├── bridge/
│   ├── protocol.py        # [Update] Add YouTube Clip actions
│   └── local_agent.py     # [Update] Dispatch YouTube & Export actions
├── media/
│   ├── process.py         # [Update] Add tools/yt-dlp discovery
│   ├── ytdlp.py           # [New] yt-dlp discovery, caching, downloader
│   ├── hardware.py        # [New] Hardware encoder probe (NVENC/QSV/AMF/CPU)
│   ├── clip_engine.py     # [New] Stream copy, frame-accurate, merge concat
│   └── path_safety.py     # [New] Windows path sanitizer & traversal checks
└── services/
    └── clip_export_service.py # [New] JobManager, cancellation, progress bridge
```

### Verification & Automated Testing Plan
1. **Unit Tests**:
   - `test_ytdlp_discovery.py`: Mocks env `YTDLP_PATH`, file system candidates, verifies search order.
   - `test_path_sanitization.py`: Verifies Windows reserved names, illegal characters, traversal attempts, length truncation.
   - `test_hardware_encoder_probe.py`: Tests active probe logic and fallback matrix with mocked ffmpeg outputs.
   - `test_ffmpeg_clip_commands.py`: Verifies exact argv structures for stream copy, frame-accurate (NVENC, QSV, x264), and concat demuxer.
   - `test_clip_export_service.py`: Tests job lifecycle, idempotent request_id, cancellation (`taskkill` invocation), and progress emissions.
2. **Integration Tests**:
   - `test_bridge_clip_export.py`: Simulates extension sending `CLIP_EXPORT_REQUEST` through LocalAgent socket/WS and receiving `CLIP_EXPORT_PROGRESS` and `CLIP_EXPORT_RESULT`.
