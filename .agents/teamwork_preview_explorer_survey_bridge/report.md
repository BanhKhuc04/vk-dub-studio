# Comprehensive Survey Report: Native Bridge, Local Agent, Backend & Protocol Architecture

**Author**: Explorer 1 (Native Bridge, Local Agent, Backend & Protocol Explorer)  
**Date**: 2026-09-15  
**Project**: VK Dub Studio (ToolVideo)  
**Scope**: Native Messaging / WebSocket Bridge, Local Agent, Extension Protocols, Registry Configuration, YouTube Clip Mode Integration, and R7 Preservation Guarantee  

---

## 1. Executive Summary

This survey provides a complete architectural and code-level investigation of the communication bridge between the Chromium Browser Extension (Microsoft Edge and Google Chrome) and the VK Dub Studio desktop backend.

### Key Discoveries & System Verification
1. **Dual Hybrid Transport Verified**: The extension implements a dual hybrid bridge client (`apps/browser-extension/bridge/nativeMessaging.js`) that first attempts a direct RFC 6455 WebSocket connection on `ws://127.0.0.1:49814/ws` (handled by `ws_framing.py` standard library) with a 1500ms timeout fallback to Chromium Native Messaging (`com.vkdub.bridge`).
2. **Native Host Windows Registry Registration Verified**: Both Microsoft Edge (`HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.vkdub.bridge`) and Google Chrome (`HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vkdub.bridge`) are actively registered on the local Windows system pointing to `C:\Users\khucv\AppData\Local\VKDubStudio\native_host\com.vkdub.bridge.json`.
3. **Extension Key Consistency Verified**: The extension ID computed from the RSA public key in `apps/browser-extension/manifest.json` matches `bnpmffibedppchkljkcaidgijekgfmgl`, identical to the `allowed_origins` in the native host manifest.
4. **Hardware Acceleration Confirmed**: Probe verification of `tools/ffmpeg.exe` confirmed that NVIDIA NVENC (`h264_nvenc` and `hevc_nvenc`) is fully functional on the target host hardware, providing high-speed frame-accurate re-encoding.
5. **Existing Bridge Test Suite Verified**: All 17 existing bridge unit and subprocess tests pass in 5.16s (`tests/test_bridge_protocol.py`, `tests/test_native_messaging_framing.py`, `tests/test_native_host_subprocess.py`, `tests/test_local_agent.py`, `tests/test_ws_local_agent.py`).
6. **Discovered Discrepancies**:
   - `src/vkdub/web/server.py` lines 257-259 calls `state.local_agent.is_connected()`, `state.local_agent.is_chatgpt_ready()`, `state.local_agent.is_vbee_ready()`, which are currently missing on `LocalAgent` (would raise `AttributeError`).
   - `tools/native_host/com.vkdub.bridge.json` still contains a hardcoded legacy path `d:\ToolVideo\tools\native_host\vkdub_host.bat`, though the dynamic generator in `src/vkdub/bridge/registry.py` correctly writes the active `%LOCALAPPDATA%` path.
   - `tools/native_host/vkdub_host.bat` has an old hardcoded check for `d:\ToolVideo\.venv\Scripts\python.exe` before checking relative `%~dp0..\..\.venv`.

---

## 2. Existing Native Messaging & Local Agent Bridge Architecture

### 2.1 Component Topology

```
+---------------------------------------------------------------------------------+
|                               CHROMIUM BROWSER                                  |
|                                                                                 |
|  [Content Scripts]                   [Side Panel]          [Background SW]      |
|  - chatgptAdapter.js                 (apps/browser-        (serviceWorker.js)   |
|  - vbeeAdapter.js                     extension/sidepanel)        |             |
|  - youtubeAdapter.js (NEW)                    |                   |             |
|          |                                    |                   |             |
|          +---------------- chrome.runtime.sendMessage ------------+             |
|                                                                   |             |
|                                                              [Bridge Client]    |
|                                                          (nativeMessaging.js)   |
+-------------------------------------------------------------------|-------------+
                                                                    |
                                  +---------------------------------+
                                  |
                    [Transport 1: Primary (0-dep)]    [Transport 2: Fallback]
                    WebSocket ws://127.0.0.1:49814/ws  chrome.runtime.connectNative(
                                  |                    "com.vkdub.bridge")
                                  |                                 |
                                  |                    [Stdio Process Spawn]
                                  |                    vkdub_host.bat -> vkdub_host.py
                                  |                    - Reads stdio 32-bit framed JSON
                                  |                    - Relays to TCP 127.0.0.1:49814
                                  |                                 |
                                  +----------------+----------------+
                                                   |
+--------------------------------------------------v------------------------------+
|                               VK DUB DESKTOP / LOCAL AGENT                      |
|                                                                                 |
|   LocalAgent (src/vkdub/bridge/local_agent.py)                                  |
|   - TCP Server on 127.0.0.1:49814                                               |
|   - RFC 6455 Handshake & Framing (src/vkdub/bridge/ws_framing.py)               |
|   - Protocol Action Dispatcher (_process_message)                               |
|   - Pending Request Manager (_pending_requests: dict[req_id, (Event, Container)])|
|   - BridgeStatus Model (src/vkdub/bridge/protocol.py)                           |
|   - Windows Registry Management (src/vkdub/bridge/registry.py)                  |
+---------------------------------------------------------------------------------+
```

### 2.2 Wire Framing Standards

1. **Chromium Native Messaging Framing**:
   - Each message is prefixed with a 32-bit unsigned integer (little-endian `<I`, 4 bytes) specifying the byte length of the following JSON string.
   - Message length limit: 1 MB per Chromium specification.
   - Stdout/stdin binary modes enforced via `msvcrt.setmode(..., os.O_BINARY)` on Windows.
2. **Local Agent WebSocket Framing (`ws_framing.py`)**:
   - Standard RFC 6455 frame format implemented with standard Python `struct`, `base64`, `hashlib`.
   - Handshake: client sends `GET /ws HTTP/1.1` with `Sec-WebSocket-Key`; server responds with `HTTP/1.1 101 Switching Protocols` and `Sec-WebSocket-Accept`.
   - Client-to-server frames are masked; server unmasks payload using the 4-byte masking key.
   - Server-to-client frames are unmasked (opcode 1 for UTF-8 text).
   - Handles opcode 9 (Ping) by replying opcode 10 (Pong); handles opcode 8 (Close).
3. **Local Agent Raw TCP Framing (when native host connects via socket)**:
   - Newline-delimited JSON (`json.dumps(msg) + "\n"`).

### 2.3 Status & Telemetry Heartbeat
- Extension service worker polls `refreshAllStatus()` and calls `sendStatusReport()` every 3,000ms.
- LocalAgent parses `STATUS_REPORT` payloads and populates `BridgeStatus`:
  - `browser_connected: bool`
  - `chatgpt_available: bool`, `chatgpt_logged_in: bool`, `chatgpt_tabs: int`
  - `vbee_available: bool`, `vbee_logged_in: bool`, `vbee_tabs: int`
  - `browser_name: str` ("Microsoft Edge" or "Google Chrome")
  - `timestamp: float`, `details: dict`

---

## 3. Preservation of Existing Workflows (Requirement R7)

To guarantee 100% preservation of ChatGPT and Vbee automation, the following message flows, data contracts, and error handling mechanisms must remain strictly untouched.

### 3.1 ChatGPT Translation Flow

#### Call Sequence
```
[PipelineRunner / User]
       |
       v
LocalAgent.translate_srt_sync(srt_content, prompt_instruction, filename, total_cues, timeout_s=600)
       |
       |-- 1. Generate UUID req_id
       |-- 2. Store (threading.Event, container) in self._pending_requests[req_id]
       |-- 3. send_command(Actions.CHATGPT_TRANSLATE, {srt_content, prompt_instruction, filename, total_cues, request_id})
       v
[Extension Background: serviceWorker.js]
       |-- 4. handleChatGPTTranslate(payload)
       |-- 5. getOrOpenTab(["*://chatgpt.com/*", ...], "https://chatgpt.com")
       |-- 6. ensureInjected(tab.id, "content/chatgptAdapter.js")
       |-- 7. chrome.tabs.sendMessage(tab.id, {action: "CHATGPT_TRANSLATE", payload}) -> ACK "STARTED"
       v
[Content Script: chatgptAdapter.js]
       |-- 8. Injects prompt and SRT into ProseMirror/Lexical/textarea input
       |-- 9. Clicks Send button
       |-- 10. Streams response; sends CHATGPT_PROGRESS updates
       |-- 11. Extracts translated SRT code block
       |-- 12. chrome.runtime.sendMessage({action: "CHATGPT_TRANSLATE_DONE", payload: {success, translated_srt, error, request_id}})
       v
[Extension Background: serviceWorker.js]
       |-- 13. Relays CHATGPT_PROGRESS -> bridge.send(CHATGPT_PROGRESS)
       |-- 14. Relays CHATGPT_TRANSLATE_DONE -> bridge.send(Actions.CHATGPT_TRANSLATE_RESULT, payload)
       v
[LocalAgent: local_agent.py]
       |-- 15. _process_message receives CHATGPT_TRANSLATE_RESULT
       |-- 16. Signals container update and sets event
       |-- 17. translate_srt_sync returns translated_srt string
```

#### JSON Payloads
- **Request (`CHATGPT_TRANSLATE`)**:
  ```json
  {
    "action": "CHATGPT_TRANSLATE",
    "payload": {
      "srt_content": "1\n00:00:01,000 --> 00:00:03,000\nHello world\n",
      "prompt_instruction": "Dịch phụ đề sang tiếng Việt chuẩn ngữ cảnh...",
      "filename": "video.srt",
      "total_cues": 1,
      "request_id": "d1c0b396-857c-48be-8dbb-5f3333333333"
    },
    "timestamp": 1741334500.123
  }
  ```
- **Progress (`CHATGPT_PROGRESS`)**:
  ```json
  {
    "action": "CHATGPT_PROGRESS",
    "payload": {
      "cue_count": 1,
      "total_cues": 1,
      "progress": 50,
      "message": "Đang dịch đoạn 1/1...",
      "request_id": "d1c0b396-857c-48be-8dbb-5f3333333333"
    }
  }
  ```
- **Result (`CHATGPT_TRANSLATE_RESULT`)**:
  ```json
  {
    "action": "CHATGPT_TRANSLATE_RESULT",
    "payload": {
      "success": true,
      "translated_srt": "1\n00:00:01,000 --> 00:00:03,000\nXin chào thế giới\n",
      "error": null,
      "request_id": "d1c0b396-857c-48be-8dbb-5f3333333333"
    }
  }
  ```

### 3.2 Vbee Voice Synthesis Flow

#### Call Sequence
```
[PipelineRunner / User]
       |
       v
LocalAgent.generate_vbee_sync(srt_content, target_audio_path, voice_name="Ngọc Huyền", speed="1.1x", timeout_s=600)
       |
       |-- 1. Compute job_name = "vkdub_" + sha256(voice_name + speed + srt_content)[:12]
       |-- 2. Store (threading.Event, container) in self._pending_requests[req_id]
       |-- 3. send_command(Actions.VBEE_GENERATE_VOICE, {srt_content, voice_name, speed, request_id, job_name})
       v
[Extension Background: serviceWorker.js]
       |-- 4. handleVbeeGenerate(payload)
       |-- 5. getOrOpenTab(["*://studio.vbee.vn/*dubbing*", ...], "https://studio.vbee.vn/studio/dubbing")
       |-- 6. ensureInjected(tab.id, "content/vbeeAdapter.js")
       |-- 7. chrome.tabs.sendMessage(tab.id, {action: "VBEE_GENERATE_VOICE", payload}) -> ACK "STARTED"
       v
[Content Script: vbeeAdapter.js]
       |-- 8. Injects SRT file via DataTransfer File API
       |-- 9. Selects voice and speed
       |-- 10. Submits synthesis; emits VBEE_PROGRESS
       |-- 11. On complete: chrome.runtime.sendMessage({action: "VBEE_GENERATE_DONE", payload: {success, audio_base64, audio_url, download_triggered, job_name, request_id}})
       v
[Extension Background: serviceWorker.js]
       |-- 12. finalizeVbeeResult(): if download_triggered, monitors chrome.downloads
       |-- 13. bridge.send(Actions.VBEE_VOICE_RESULT, payload)
       v
[LocalAgent: local_agent.py]
       |-- 14. _process_message receives VBEE_VOICE_RESULT
       |-- 15. Strategy A: Base64 decode + _looks_like_audio validation
       |-- 16. Strategy B: Direct HTTP download from audio_url via httpx
       |-- 17. Strategy C: _wait_for_correlated_audio in Edge download directory (.crdownload stabilization)
       |-- 18. Writes verified master audio to target_audio_path
```

#### Audio Verification Guardrails
- `_looks_like_audio(data: bytes)`: Requires >= 1024 bytes and validates audio signatures:
  - MP3: `ID3` or sync word `0xFF 0xE0`
  - WAV: `RIFF`
  - OGG: `OggS`
  - FLAC: `fLaC`
  - MP4/M4A: `ftyp` at offset 4
- Rejects HTML error pages before creating invalid audio checkpoints.

---

## 4. YouTube Clip Mode: Protocol Action Specification

The following 10 actions expand the protocol without interfering with existing actions.

| Action Identifier | Direction | Purpose | Schema / Key Fields |
|-------------------|-----------|---------|---------------------|
| `YOUTUBE_CONTEXT_SYNC` | Content/SW -> Agent | Broadcast current YouTube video metadata, playback time, duration, SPA navigation | `video_id`, `url`, `canonical_url`, `title`, `author`, `duration`, `current_time`, `thumbnail_url`, `tab_id` |
| `YOUTUBE_SEEK_TO` | SidePanel/Agent -> SW -> Content | Seek YouTube player to specified timestamp | `time` (float seconds), `play` (bool), `tab_id` (optional) |
| `YOUTUBE_PREVIEW_CLIP` | SidePanel -> SW -> Content | Play specified clip boundary `[start, end]` in YouTube player | `start` (float), `end` (float), `loop` (bool), `tab_id` (optional) |
| `CLIP_EXPORT_REQUEST` | SidePanel -> SW -> Agent | Trigger export of marked clips (individual, merged, or pipeline dub) | `request_id`, `video_id`, `video_url`, `video_title`, `duration`, `clips` (list), `export_config` (dict) |
| `CLIP_EXPORT_ACCEPTED` | Agent -> SW -> SidePanel | Immediate ack of export request | `request_id`, `status` ("started"), `total_clips`, `message` |
| `CLIP_EXPORT_PROGRESS` | Agent -> SW -> SidePanel | Real-time multi-stage export progress telemetry | `request_id`, `stage` (enum), `clip_index`, `total_clips`, `progress` (0-100), `speed`, `downloaded_bytes`, `total_bytes`, `message` |
| `CLIP_EXPORT_RESULT` | Agent -> SW -> SidePanel | Final export results report | `request_id`, `success` (true), `output_dir`, `mode`, `generated_files` (list of paths), `merged_file` (path or null), `elapsed_seconds`, `error` (null) |
| `CLIP_EXPORT_ERROR` | Agent -> SW -> SidePanel | Export failure notification | `request_id`, `success` (false), `stage`, `error` (str), `details` (optional) |
| `CLIP_EXPORT_CANCEL` | SidePanel -> SW -> Agent | Abort running export job and kill active subprocesses | `request_id` |
| `OPEN_OUTPUT_FOLDER` | SidePanel -> SW -> Agent | Open export directory in Windows File Explorer | `folder_path` (str) |

### 4.1 Detailed Action Payloads

#### 1. `YOUTUBE_CONTEXT_SYNC`
```json
{
  "action": "YOUTUBE_CONTEXT_SYNC",
  "payload": {
    "video_id": "jNQXAC9IVRw",
    "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
    "canonical_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
    "title": "Me at the zoo",
    "author": "jawed",
    "duration": 19.08,
    "current_time": 4.12,
    "thumbnail_url": "https://i.ytimg.com/vi/jNQXAC9IVRw/hqdefault.jpg",
    "tab_id": 1024
  },
  "timestamp": 1741334520.0
}
```

#### 2. `YOUTUBE_SEEK_TO`
```json
{
  "action": "YOUTUBE_SEEK_TO",
  "payload": {
    "time": 10.5,
    "play": true,
    "tab_id": 1024
  }
}
```

#### 3. `YOUTUBE_PREVIEW_CLIP`
```json
{
  "action": "YOUTUBE_PREVIEW_CLIP",
  "payload": {
    "start": 5.0,
    "end": 12.5,
    "loop": false,
    "tab_id": 1024
  }
}
```

#### 4. `CLIP_EXPORT_REQUEST`
```json
{
  "action": "CLIP_EXPORT_REQUEST",
  "payload": {
    "request_id": "clip_export_a9b1c2d3",
    "video_id": "jNQXAC9IVRw",
    "video_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
    "video_title": "Me at the zoo",
    "duration": 19.08,
    "clips": [
      {
        "id": "clip_1",
        "name": "Elephants segment",
        "start": 2.0,
        "end": 8.5,
        "selected": true
      },
      {
        "id": "clip_2",
        "name": "Conclusion",
        "start": 12.0,
        "end": 18.0,
        "selected": true
      }
    ],
    "export_config": {
      "mode": "individual",
      "output_dir": "D:\\Work\\Project_AI\\ToolVideo\\output\\clips",
      "container": "mp4",
      "quality": "best",
      "cut_mode": "stream_copy",
      "use_cookies": false
    }
  },
  "timestamp": 1741334550.0
}
```

#### 5. `CLIP_EXPORT_ACCEPTED`
```json
{
  "action": "CLIP_EXPORT_ACCEPTED",
  "payload": {
    "request_id": "clip_export_a9b1c2d3",
    "status": "started",
    "total_clips": 2,
    "message": "Đã tiếp nhận yêu cầu xuất 2 đoạn clip."
  }
}
```

#### 6. `CLIP_EXPORT_PROGRESS`
```json
{
  "action": "CLIP_EXPORT_PROGRESS",
  "payload": {
    "request_id": "clip_export_a9b1c2d3",
    "stage": "DOWNLOADING",
    "clip_index": 0,
    "total_clips": 2,
    "progress": 45,
    "speed": "8.5 MB/s",
    "downloaded_bytes": 15728640,
    "total_bytes": 34603008,
    "message": "Đang tải video nguồn chất lượng cao (45%)..."
  }
}
```
Stages:
- `CHECKING_SOURCE`: Inspect cache for pre-existing `{video_id}_{quality}.mp4`.
- `DOWNLOADING`: yt-dlp downloading bestvideo + bestaudio.
- `REMUXING`: FFmpeg muxing into single cached master source file.
- `CUTTING`: Trimming clip $K$ of $N$.
- `MERGING`: Concat demuxer merging selected clips (if mode is `merged`).
- `PIPELINE_FEED`: Loading final video into ToolVideo timeline (if mode is `pipeline_dub`).
- `COMPLETED`: All files exported successfully.
- `CANCELLED`: Process cleanly aborted by user request.

#### 7. `CLIP_EXPORT_RESULT`
```json
{
  "action": "CLIP_EXPORT_RESULT",
  "payload": {
    "request_id": "clip_export_a9b1c2d3",
    "success": true,
    "output_dir": "D:\\Work\\Project_AI\\ToolVideo\\output\\clips",
    "mode": "individual",
    "generated_files": [
      "D:\\Work\\Project_AI\\ToolVideo\\output\\clips\\Me_at_the_zoo_clip_1_00-00-02_00-00-08.mp4",
      "D:\\Work\\Project_AI\\ToolVideo\\output\\clips\\Me_at_the_zoo_clip_2_00-00-12_00-00-18.mp4"
    ],
    "merged_file": null,
    "elapsed_seconds": 6.8,
    "error": null
  }
}
```

#### 8. `CLIP_EXPORT_ERROR`
```json
{
  "action": "CLIP_EXPORT_ERROR",
  "payload": {
    "request_id": "clip_export_a9b1c2d3",
    "success": false,
    "stage": "DOWNLOADING",
    "error": "yt-dlp: Private video or age-restricted. Kích hoạt 'Dùng cookie trình duyệt' trong cài đặt xuất.",
    "details": "Sign in to confirm your age"
  }
}
```

#### 9. `CLIP_EXPORT_CANCEL`
```json
{
  "action": "CLIP_EXPORT_CANCEL",
  "payload": {
    "request_id": "clip_export_a9b1c2d3"
  }
}
```

#### 10. `OPEN_OUTPUT_FOLDER`
```json
{
  "action": "OPEN_OUTPUT_FOLDER",
  "payload": {
    "folder_path": "D:\\Work\\Project_AI\\ToolVideo\\output\\clips"
  }
}
```

---

## 5. Windows Registry Native Host Registration Inspection

### 5.1 Registry Verification

Direct query of the Windows Registry on the host machine confirmed the active registration:

```powershell
Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\com.vkdub.bridge',
                       'HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.vkdub.bridge'
```

**Results**:
- **Microsoft Edge**:
  - Key: `HKEY_CURRENT_USER\Software\Microsoft\Edge\NativeMessagingHosts\com.vkdub.bridge`
  - Value `(Default)`: `C:\Users\khucv\AppData\Local\VKDubStudio\native_host\com.vkdub.bridge.json`
  - File Exists: **True**
- **Google Chrome**:
  - Key: `HKEY_CURRENT_USER\Software\Google\Chrome\NativeMessagingHosts\com.vkdub.bridge`
  - Value `(Default)`: `C:\Users\khucv\AppData\Local\VKDubStudio\native_host\com.vkdub.bridge.json`
  - File Exists: **True**

### 5.2 Host Manifest File Content
Location: `C:\Users\khucv\AppData\Local\VKDubStudio\native_host\com.vkdub.bridge.json`
```json
{
  "name": "com.vkdub.bridge",
  "description": "VK Dub Studio Native Messaging Bridge Host",
  "path": "D:\\Work\\Project_AI\\ToolVideo\\tools\\native_host\\vkdub_host.bat",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://bnpmffibedppchkljkcaidgijekgfmgl/"
  ]
}
```

### 5.3 Extension Key Cryptographic Validation
- Public Key from `apps/browser-extension/manifest.json`:
  `MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0rUwetRNAsoPBo0o0hVtgMJJL0bQfOUs5LiCdDlMg242irjOt4L75Qr3+322+SHDUEA/lYcQglaEHKD3tSlE/pwUIhekHHadAAZnYladqLEApp9Lk1587C82LnfK9K+qmI1PM7jviNJxFdFHtHttF3O00eFYrPWw0P9ygtL92mEFFxcV1qh3lG8zWiJtRe1Ph2oOw5YjWuDFm+5WrtgfFA0xJgn9hK76Y8aCtTK+oQXGhBnzrb5p9wSDC7s6NRHUjBytONPXD1o1OonDmnfLi7ZnUjJjzHx8GX54tBcZ/7F/tBWqvUoZEwN/xIiERxxjvh4WFhnRcAu1r6yo5i5QjQIDAQAB`
- SHA256 derivation executed via Python:
  First 32 hex nibbles mapped to `[a-p]` yields:
  `bnpmffibedppchkljkcaidgijekgfmgl`
- **Result**: Perfect cryptographic match with `allowed_origins`.

---

## 6. Execution Engine & Hardware Acceleration Findings

### 6.1 yt-dlp Source Adapter
- **Path Resolution Order** (Requirement R4):
  1. `os.environ.get("YTDLP_PATH")`
  2. `tools/yt-dlp/yt-dlp.exe`
  3. `tools/yt-dlp.exe`
  4. System `PATH` via `shutil.which("yt-dlp")`
- **Single-Pass Caching**:
  - Video cache directory: `Path(os.environ.get("LOCALAPPDATA", ...)) / "VKDubStudio" / "cache" / "youtube"`
  - Cache key: `{video_id}_{quality}.mp4`
  - Download options:
    `yt-dlp --no-playlist -f "bestvideo[height<={max_h}]+bestaudio/best" --merge-output-format mp4 -o {cache_template}`
  - Subprocess execution: `subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)`
  - Regex progress parsing:
    `r"\[download\]\s+(\d+\.?\d*)%\s+of\s+~?(\S+)\s+at\s+(\S+)\s+ETA\s+(\S+)"`

### 6.2 FFmpeg Cutting & Re-encoding Engine

#### 1. Fast Stream Copy (`-c copy`)
- Target: Cut clips without re-encoding, preserving exact original HDR, bitrate, FPS, and color profile.
- Command:
  `tools/ffmpeg.exe -ss {start_s} -to {end_s} -i {cached_source} -c copy -avoid_negative_ts make_zero -y {output_clip}`
- Keyframe behavior: Snaps to nearest I-frame. UI must include user note: "Cắt siêu nhanh theo keyframe gần nhất".

#### 2. Frame-Accurate Cut (Hardware Accelerated)
- Host Hardware Test Results:
  - FFmpeg version: 8.1.1 essentials (gyan.dev)
  - `h264_nvenc`: **AVAILABLE & TESTED WORKING** (Exit code 0 on synthetic frame test)
  - `hevc_nvenc`: **AVAILABLE**
  - `h264_qsv` / `hevc_qsv`: Built-in (Intel)
  - `h264_amf` / `hevc_amf`: Built-in (AMD)
  - CPU Fallback: `libx264` (CRF 17-18, preset medium)
- Command:
  `tools/ffmpeg.exe -ss {start_s} -to {end_s} -i {cached_source} -c:v h264_nvenc -preset p5 -cq 19 -c:a aac -b:a 192k -y {output_clip}`

#### 3. Merge Mode
- Concat list generator writes temporary `concat_list.txt`:
  ```
  file 'D:\path\to\clip_1.mp4'
  file 'D:\path\to\clip_2.mp4'
  ```
- Command:
  `tools/ffmpeg.exe -f concat -safe 0 -i concat_list.txt -c copy -y {merged_output}`

#### 4. Filename Sanitization & Windows Path Traversal Protection
- Windows prohibited characters: `< > : " / \ | ? *`
- Reserved names: `CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`
- Truncate base title to 60 characters to avoid exceeding Windows `MAX_PATH` (260 chars).
- Output filename format: `{sanitized_title}_clip_{i}_{start_hh-mm-ss}_{end_hh-mm-ss}.{container}`

---

## 7. Extension Installation & Update Tooling Architecture (R6)

### 7.1 Manifest V3 Updates Needed
In `apps/browser-extension/manifest.json`:
1. Add `"sidePanel"` to `permissions`:
   `"permissions": ["nativeMessaging", "tabs", "storage", "cookies", "downloads", "scripting", "webNavigation", "sidePanel"]`
2. Add YouTube to `host_permissions`:
   `"*://*.youtube.com/*"`, `"*://youtube.com/*"`
3. Add `side_panel` declaration:
   ```json
   "side_panel": {
     "default_path": "sidepanel/sidepanel.html"
   }
   ```
4. Add content script match for YouTube:
   ```json
   {
     "matches": [
       "*://*.youtube.com/watch*",
       "*://youtube.com/watch*"
     ],
     "js": ["content/youtubeAdapter.js"],
     "run_at": "document_idle"
   }
   ```

### 7.2 Host Registration Helper & Settings Integration
1. Extend `src/vkdub/bridge/registry.py`:
   - Add `check_host_registration() -> dict[str, bool]`
   - Add `register_host() -> dict[str, bool]`
   - Add `unregister_host() -> dict[str, bool]`
2. Expose in `src/vkdub/web/server.py`:
   - `GET /api/bridge/host-status`: Returns registration status for Edge and Chrome.
   - `POST /api/bridge/register-host`: Registers native host in HKCU registry.
   - Fix `GET /api/bridge/status`: Implement `is_connected()`, `is_chatgpt_ready()`, `is_vbee_ready()` on `LocalAgent`.
3. Provide standalone script:
   - `scripts/register_extension.bat`: 1-click script to verify virtualenv, generate dynamic native host manifest, and set HKCU registry keys.

---

## 8. Summary of Integration Blueprint

```
+---------------------------------------------------------------------------------------+
| NEW / MODIFIED FILES TO IMPLEMENT (BLUEPRINT)                                         |
+---------------------------------------------------------------------------------------+
| 1. Extension Side:                                                                    |
|    - apps/browser-extension/manifest.json (sidePanel permission, youtube hosts)       |
|    - apps/browser-extension/bridge/protocol.js (10 new Action constants)              |
|    - apps/browser-extension/content/youtubeAdapter.js (In-player toolbar, hotkeys)    |
|    - apps/browser-extension/sidepanel/sidepanel.html (Side panel UI layout)           |
|    - apps/browser-extension/sidepanel/sidepanel.js (Clip manager & export controls)   |
|    - apps/browser-extension/sidepanel/sidepanel.css (Apple-style sleek glass styling) |
|    - apps/browser-extension/background/serviceWorker.js (Route new actions & storage)|
|                                                                                       |
| 2. Backend & Local Agent:                                                             |
|    - src/vkdub/bridge/protocol.py (10 new Action constants in Python)                 |
|    - src/vkdub/bridge/local_agent.py (Add YouTube context, clip export signals,     |
|      is_connected / is_chatgpt_ready / is_vbee_ready methods)                         |
|    - src/vkdub/services/youtube_downloader.py (yt-dlp adapter, caching, progress)    |
|    - src/vkdub/services/clip_export_service.py (FFmpeg stream-copy, NVENC, cancel)    |
|    - src/vkdub/bridge/registry.py (check_host_registration, register_host)           |
|                                                                                       |
| 3. Unit & Integration Test Suite:                                                     |
|    - tests/test_youtube_clip_mode.py (URL parser, clip validator, sanitizer,        |
|      FFmpeg command builder, hardware encoder detector, protocol actions)             |
+---------------------------------------------------------------------------------------+
```
