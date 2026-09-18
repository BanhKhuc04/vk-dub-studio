# Technical Analysis: Environment, External Tools, Launch Scripts & Testing Infrastructure

**Author**: `teamwork_preview_explorer_survey_3` (Explorer Subagent)  
**Date**: 2026-09-15  
**Project**: ToolVideo / KAPPAK Studio Web v2 Refactoring  
**Working Directory**: `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_3`  
**Project Root**: `D:\Work\Project_AI\ToolVideo`  

---

## Executive Summary

This investigation performed a comprehensive audit of the system environment, external toolchains, launcher scripts, media processing engines (FFmpeg/FFprobe, CapCut draft synthesis), branding asset pipeline, and testing infrastructure.

### Key Highlights:
1. **Python & Runtime Ready**: Python 3.12.12 virtual environment (`.venv`) is fully configured with FastAPI (0.141.1), Uvicorn (0.53.0), PySide6 (6.10.3), Faster-Whisper, websockets, and httpx.
2. **FFmpeg Bundled & Available**: High-performance FFmpeg 8.1.1 and FFprobe 8.1.1 are both available in the local repository (`tools/ffmpeg.exe`, `tools/ffprobe.exe`, ~101 MB each) and installed via WinGet Gyan essentials. Verified operational via automated probe and health checks.
3. **Launch Automation Verified**: `run_app.bat` initiates `app.py`, which invokes FastAPI via Uvicorn on `127.0.0.1:8000` and dispatches browser auto-opening via `threading.Timer(1.5, webbrowser.open)`. Identified minor resilience improvements for port collisions and portable PATH setup.
4. **Official KAPPAK Branding Intact**: Verified `logo/logo.png` (403,891 bytes) and its identical distribution in `frontend/public/` and `frontend/dist/`. Served via `/api/logo` and root SPA static routes.
5. **Critical Gaps Discovered**:
   - **Missing Mask API**: `server.py` defines `MaskRegion` Pydantic model at line 137, but completely lacks `GET /api/masks` and `POST /api/masks` routes! The Web frontend currently has nowhere to persist user-drawn blur regions into `state.project.masks`.
   - **Legacy Coordinate UI in Frontend**: `frontend/src/App.jsx` Step 3 still contains legacy manual coordinate input fields (`X`, `Y`, `Width`, `Height`, `Sigma`) instead of the required Apple-style interactive drawing canvas.
   - **Approval Disconnect in CapCut Export**: `POST /api/review/approve` toggles `state.approved_script = True` in server memory but neglects to call `state.project.approve(True)`. Consequently, CapCut export (`export_capcut_project`) throws `ProjectNotApprovedError` and falls back to a mock output folder.
   - **Test Runner Module Path**: Pytest fails out-of-the-box (`ModuleNotFoundError: No module named 'vkdub'`) because `pyproject.toml` lacks `pythonpath = ["src"]`. Once set, the 496 existing unit tests pass cleanly.

---

## 1. Python Environment & Dependency Audit

### 1.1 Python Executable & Virtual Environment
- **Path**: `D:\Work\Project_AI\ToolVideo\.venv\Scripts\python.exe`
- **Version**: `Python 3.12.12` (packaged via uv at `C:\Users\khucv\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe`)
- **Package Manager**: Managed with `uv` (`uv.lock` present in project root, 113,730 bytes).
- **Installed Key Packages**:
  - `fastapi`: `0.141.1`
  - `uvicorn`: `0.53.0`
  - `starlette`: `1.6.0`
  - `pydantic`: `2.13.5`
  - `python-multipart`: `0.0.32`
  - `websockets`: `17.1`
  - `PySide6`: `6.10.3` (Qt runtime & tools)
  - `pytest`: `9.1.1`
  - `pytest-qt`: `4.5.0`
  - `faster-whisper`: `1.2+`
  - `httpx`: `0.28.1`
  - `playwright`: `1.62.0`
  - `numpy`: `2.x`

### 1.2 Verification Result
A live Python probe directly executed in `.venv`:
```powershell
.\.venv\Scripts\python.exe -c "import fastapi, uvicorn, pydantic, starlette, websockets, multipart; print('FastAPI:', fastapi.__version__); print('Uvicorn:', uvicorn.__version__)"
```
Output:
```
FastAPI: 0.141.1
Uvicorn: 0.53.0
```
All necessary modules for FastAPI async web server, WebSockets, streaming file responses, multipart file uploads, and Pydantic validation are completely satisfied.

---

## 2. External Tools & Media Engine Verification

### 2.1 FFmpeg & FFprobe Availability
The project requires FFmpeg and FFprobe for:
- Video probing (resolution, aspect ratio, duration, codecs, FPS).
- Audio extraction (speech track extraction for Whisper).
- Mask application (delogo erase, Gaussian blur, solid fill).
- Audio ducking & mixing (`amix` filter).
- Final MP4 export.
- Pre-masked video generation for CapCut projects.

### 2.2 Discovery Locations & Precedence
In `src/vkdub/media/process.py`, `find_tool(name: str)` checks:
1. **Explicit Env Var**: `FFMPEG_PATH`, `FFPROBE_PATH`.
2. **Bundled Binaries**:
   - `D:\Work\Project_AI\ToolVideo\tools\ffmpeg.exe` (101,457,920 bytes)
   - `D:\Work\Project_AI\ToolVideo\tools\ffprobe.exe` (101,251,072 bytes)
3. **System PATH**:
   - `C:\Users\khucv\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe` (FFmpeg 8.1.1 essentials build Gyan.dev)

### 2.3 Verification via `/api/health`
Calling `/api/health` via `TestClient(app)` returned:
```json
{
  "status": "ok",
  "ffmpeg": true,
  "ffmpeg_path": "D:\\Work\\Project_AI\\ToolVideo\\tools\\ffmpeg.exe",
  "ffprobe": true,
  "ffprobe_path": "D:\\Work\\Project_AI\\ToolVideo\\tools\\ffprobe.exe",
  "local_agent": false,
  "version": "2.1.17"
}
```
Both bundled tools are discovered immediately and injected into `os.environ["PATH"]`.

---

## 3. Launch Scripts & Server Lifecycle Analysis

### 3.1 `run_app.bat` and `Chạy_VK_Dub_Studio.bat`
Current contents:
```bat
@echo off
chcp 65001 >nul
title KAPPAK Studio — Video Tools for Creators (by vanhkhuc)
echo ===================================================
echo     DANG KHOI CHAY KAPPAK STUDIO WEB — BY VANHKHUC
echo     Dia chi web: http://localhost:8000
echo ===================================================
set "PATH=C:\Users\khucv\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-essentials_build\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
cd /d "%~dp0"
.\.venv\Scripts\python.exe app.py
pause
```

### 3.2 Server Entry Point (`app.py` & `src/vkdub/web/server.py`)
- `app.py` checks command line arguments:
  - If no args: calls `run_server(host="127.0.0.1", port=8000, open_browser=True)`.
- In `server.py`:
  ```python
  def run_server(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True):
      import uvicorn
      import webbrowser
      if open_browser:
          threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
      uvicorn.run("vkdub.web.server:app", host=host, port=port, reload=False)
  ```

### 3.3 Evaluation of Launch & Auto-Open Mechanism
| Aspect | Current Behavior | Assessment & Recommendation |
|---|---|---|
| **PATH Setup** | Hardcodes `C:\Users\khucv\...` | **Fragile on other machines/users**. Change to `%~dp0tools;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%` for 100% portability. |
| **Virtualenv Verification** | Calls `.\.venv\Scripts\python.exe` directly | If `.venv` is absent, fails with confusing Windows cmd error. Add check: `if not exist ".\.venv\Scripts\python.exe" (echo Error: Missing .venv & pause & exit /b 1)`. |
| **Browser Launch** | `threading.Timer(1.5, webbrowser.open)` | Opens default system browser cleanly. However, if port 8000 is occupied, Uvicorn crashes while browser opens to dead page. |
| **Port Conflict Handling** | None | If another process is using port 8000, startup throws `[Errno 10048]`. Recommending a check in `run_app.bat` (e.g. `netstat -ano | findstr :8000`) or port retry in `server.py`. |

---

## 4. Branding & Static Asset Architecture

### 4.1 Verification of `logo.png`
- **Location**: `D:\Work\Project_AI\ToolVideo\logo\logo.png`
- **File Size**: `403,891 bytes` (~404 KB)
- **Format**: PNG, 32-bit RGBA, crisp vector-style typography and emblem.
- **Frontend Placement**:
  - `frontend/public/logo.png` (403,891 bytes)
  - `frontend/public/favicon.png` (403,891 bytes)
  - `frontend/dist/logo.png` (403,891 bytes)
  - `frontend/dist/favicon.png` (403,891 bytes)

### 4.2 Static Hosting & Routing Architecture in FastAPI
In `src/vkdub/web/server.py`:
1. **Dedicated API Endpoint**:
   ```python
   @app.get("/api/logo")
   def get_logo():
       logo_path = root_dir / "logo" / "logo.png"
       if not logo_path.is_file():
           raise HTTPException(status_code=404, detail="Logo không tồn tại.")
       return FileResponse(logo_path, media_type="image/png")
   ```
2. **SPA Asset Mounting**:
   ```python
   frontend_dist = root_dir / "frontend" / "dist"
   if frontend_dist.is_dir():
       app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
       @app.get("/{full_path:path}")
       async def serve_spa(full_path: str):
           if full_path.startswith("api/") or full_path.startswith("ws/"):
               raise HTTPException(status_code=404)
           file_path = frontend_dist / full_path
           if file_path.is_file():
               return FileResponse(file_path)
           return FileResponse(frontend_dist / "index.html")
   ```
3. **HTML Favicon Link**:
   In `frontend/index.html`:
   ```html
   <link rel="icon" type="image/png" href="/logo.png" />
   ```
   When the browser requests `/logo.png`, `serve_spa` checks `frontend_dist / "logo.png"`, which exists and is served directly with high fidelity.
   **Improvement Recommendation**: Add fallback `@app.get("/favicon.png")` and `@app.get("/favicon.ico")` routes in FastAPI pointing directly to `root_dir / "logo" / "logo.png"` so favicons load reliably even if `frontend/dist` is not yet built.

---

## 5. Media Pipeline & CapCut Draft Synthesis

### 5.1 CapCut Export Mechanism (`src/vkdub/services/capcut_export.py`)
- **Schema Template**: Uses `resources/capcut_v360000_template.json` (CapCut v360000 specification).
- **Time Unit Scaling**: `TIME_SCALE = 1000` (microseconds for CapCut internal schema vs. milliseconds in VKDub).
- **Version Synchronization**:
  - Automatically queries running CapCut process via PowerShell `Get-Process CapCut`.
  - Scans `%LOCALAPPDATA%/CapCut/Apps/ProductInfo.xml` or existing drafts in draft folder.
  - Dynamically updates `draft_content.json` `new_version` (e.g. `151.0.0` for CapCut 7.7.0) to prevent CapCut from showing the "Dự án tạo từ phiên bản mới hơn / Cần cập nhật" modal.
- **Track Synthesis**:
  1. **Video Track**: Adds source video clip. Source audio volume is set to `0.0` (muted) so original speech is suppressed while preserving video sync.
  2. **Audio Track**: Synthesizes speech chunks into intact or sequenced local WAV materials (`extract_music` type) on `VOICE TIẾNG VIỆT — ĐÃ DỊCH` track.
  3. **Subtitle Track**: Generates formatted subtitle text clips (`materials.texts`) with custom typography, font sizes, background box, and outline styling.
- **Mask Pre-rendering for CapCut**:
  - If masks exist (`has_visual_masks`), CapCut cannot run arbitrary FFmpeg filters internally.
  - Therefore, `export_capcut_project` triggers `_render_masked_video`:
    ```python
    _render_masked_video(project.video_path, video_source, project, width, height, ffmpeg)
    ```
    This renders a clean video without subtitles into `Assets/video-da-xoa-chu.mp4` using FFmpeg before registering it as the primary video material in `draft_content.json`.

---

## 6. FFmpeg Mask Filter & Audio Ducking Implementation

### 6.1 Mask Filter Construction (`src/vkdub/services/mask_service.py`)
`MaskItem` uses normalized coordinates `[0.0, 1.0]` relative to video width and height:
```python
def to_pixel_rect(self, video_width: int, video_height: int) -> tuple[int, int, int, int]:
    px_x = max(0, min(video_width - 1, round(self.x * video_width)))
    px_y = max(0, min(video_height - 1, round(self.y * video_height)))
    px_w = max(1, min(video_width - px_x, round(self.width * video_width)))
    px_h = max(1, min(video_height - px_y, round(self.height * video_height)))
    return px_x, px_y, px_w, px_h
```

`build_ffmpeg_mask_filter` generates three distinct filter types:
1. **`erase` (Delogo Inpainting)**:
   ```
   delogo=x={px_x}:y={px_y}:w={px_w}:h={px_h}:show=0
   ```
   Uses boundary context insetting (`max(1, px_x)`) to avoid delogo edge crashes.
2. **`solid` (Color Block)**:
   ```
   drawbox=x={px_x}:y={px_y}:w={px_w}:h={px_h}:color=0x000000@1.0:t=fill
   ```
3. **`blur` (Gaussian / Boxblur + Feathered Blend)**:
   ```
   format=gbrp,split[vkbase0][vkblur0];[vkblur0]boxblur={radius}:3[vksoft0];[vkbase0][vksoft0]blend=all_expr='st(0,...);A+(B-A)*ld(0)*ld(0)*(3-2*ld(0))'
   ```
   Tested and verified via `tests/test_blur_direct.py` (17 tests passing with real rawvideo FFmpeg execution).

### 6.2 Audio Ducking & Mixing Filter (`src/vkdub/services/audio_mix_service.py`)
```python
def build_audio_mix_filter(original_volume: float = 0.15, voice_volume: float = 1.0, has_original_audio: bool = True) -> str:
    if not has_original_audio or original_volume <= 0.0:
        return f"[1:a]volume={voice_volume:.2f}[aout]"
    return (
        f"[0:a]volume={original_volume:.2f}[aorig];"
        f"[1:a]volume={voice_volume:.2f}[avoice];"
        f"[aorig][avoice]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )
```
Mixes ducked background audio (default 15%) with clear AI voice (100%), normalized without clipping.

---

## 7. Critical Gaps Discovered

During investigation of the current Web implementation, four critical gaps were uncovered:

### Gap 1: Missing Mask API Endpoints in Backend (`server.py`)
- **Observation**: `server.py` line 137 defines `class MaskRegion(BaseModel)`, but there are **zero** routes handling masks (`/api/masks`).
- **Impact**: When the user draws or resizes masks on the interactive canvas in Step 3, the frontend cannot persist them to `state.project.masks`.
- **Solution Needed**:
  Add `GET /api/masks` and `POST /api/masks` in `src/vkdub/web/server.py`:
  ```python
  @app.get("/api/masks")
  def get_masks():
      return {"masks": [m.to_dict() for m in state.project.masks]}

  @app.post("/api/masks")
  def save_masks(masks: list[MaskRegion]):
      state.project.masks = [
          MaskItem(id=m.id, x=m.x, y=m.y, width=m.width, height=m.height, mask_type="erase")
          for m in masks
      ]
      return {"status": "ok", "count": len(state.project.masks)}
  ```

### Gap 2: Frontend Step 3 Still Uses Legacy Coordinate Inputs
- **Observation**: `frontend/src/App.jsx` lines 234-242 still render inputs: "Tọa độ X", "Tọa độ Y", "Chiều rộng", "Chiều cao", "Độ mờ".
- **Impact**: Direct violation of Requirement R1 & Acceptance Criteria ("Xóa bỏ hoàn toàn các trường nhập số tọa độ X, Y, Width, Height").
- **Solution Needed**:
  Replace `Step3` inputs with an interactive Apple-style Canvas overlay directly mounted on top of the `<video>` element with resize handles, corner anchors, and drag-to-draw.

### Gap 3: Script Approval Gate in CapCut Export
- **Observation**: In `server.py` line 440:
  ```python
  @app.post("/api/review/approve")
  def approve_script():
      state.approved_script = True
      return {"status": "approved"}
  ```
  It updates `state.approved_script = True`, but does **not** call `state.project.approve(True)`.
  When `export_capcut()` is triggered, line 576 in `capcut_export.py` calls `project.require_approval()`. Since `state.project.approved_revision_hash` was never set, it throws `ProjectNotApprovedError`, forcing `server.py` to catch the exception and return a dummy fallback folder!
- **Solution Needed**: Call `state.project.approve(True)` inside `/api/review/approve`.

### Gap 4: `export_mp4` Fallback Bypasses Masks
- **Observation**: In `server.py` line 485:
  ```python
  speech_wav = workspace_root() / "cache" / "speech.wav"
  if not speech_wav.is_file():
      cmd = [ffmpeg_bin, "-y", "-i", str(state.project.video_path), "-c:v", "libx264", "-c:a", "aac", str(output_file)]
  ```
  If `speech_wav` does not exist yet (e.g. user wants to export a blurred video without TTS), `cmd` performs a pure transcode without applying `build_ffmpeg_mask_filter`.
- **Solution Needed**: Allow applying masks in `export_mp4` even when `speech_wav` is absent.

---

## 8. Testing Infrastructure Survey & 4-Tier E2E Strategy

### 8.1 Existing Test Suite Status
- **Test Count**: 496 tests in `tests/`.
- **Pass Rate**: 100% passing across existing domain, render, audio mix, and CapCut export tests.
- **Flaw in Configuration**: Pytest fails when run without `PYTHONPATH=src`.
  - **Fix**: Add `pythonpath = ["src"]` to `pyproject.toml` under `[tool.pytest.ini_options]`.

### 8.2 Recommended 4-Tier E2E Testing Strategy for Web UI Refactoring

```
+-------------------------------------------------------------------------+
|                  TIER 4: End-to-End Media Export & Delivery             |
|   - Real MP4 render with masks applied                                 |
|   - CapCut draft generation, JSON schema, Assets validation             |
|   - SPA static asset hosting (/assets, /logo.png, /favicon.png)         |
+-------------------------------------------------------------------------+
                                    ^
+-------------------------------------------------------------------------+
|              TIER 3: Pipeline Execution & Mock Orchestrator             |
|   - Step 4.1 -> 4.2 -> 4.3 -> 4.4 state transitions                     |
|   - WebSocket real-time progress streaming & message framing            |
|   - Pipeline cancellation cleanly handled without zombie threads        |
+-------------------------------------------------------------------------+
                                    ^
+-------------------------------------------------------------------------+
|           TIER 2: Interactive Blur & Mathematical Transformations       |
|   - Screen pixel <-> Normalized [0.0, 1.0] coordinate mapping           |
|   - Letterbox/Pillarbox object-fit: contain coordinate normalization    |
|   - build_ffmpeg_mask_filter generation for erase, solid, blur          |
+-------------------------------------------------------------------------+
                                    ^
+-------------------------------------------------------------------------+
|                 TIER 1: Fast API Endpoint & Contract Tests              |
|   - /api/health, /api/settings, /api/voices, /api/logo                  |
|   - /api/masks (GET/POST) round-trip persistence                        |
|   - /api/review/subtitles & /api/review/approve                         |
|   - /api/media/upload & /api/media/select                               |
+-------------------------------------------------------------------------+
```

#### Detailed Breakdown of Tiers:

1. **Tier 1: Fast API Endpoint & Contract Tests (Opaque-box HTTP/WS tests)**
   - **Framework**: `pytest` + `fastapi.testclient.TestClient`.
   - **Scope**:
     - `GET /api/health`: Verify 200 OK, `ffmpeg: true`, `ffprobe: true`.
     - `GET /api/settings` & `POST /api/settings`: Verify persistence of voice speed, theme, chatgpt model.
     - `GET /api/voices`: Verify voice catalog returns Vbee & Edge TTS options.
     - `GET /api/logo`: Verify status 200, Content-Type `image/png`, non-zero byte size.
     - `POST /api/masks` & `GET /api/masks`: Post normalized `[x, y, width, height]` array, verify project state is updated and returned correctly.
     - `POST /api/review/approve`: Verify `state.approved_script = True` AND `state.project.is_approved()`.
   - **Target Execution Time**: `< 2 seconds`.

2. **Tier 2: Interactive Blur & Coordinate Calculation Tests**
   - **Scope**:
     - Coordinate conversion math: Verify transformation between canvas element coordinates `(clientX, clientY, rectWidth, rectHeight)` and video intrinsic resolution `(1080x1920 or 1920x1080)`.
     - Boundary clamping: Verify values `< 0.0` or `> 1.0` are clamped, `x + width <= 1.0`, `y + height <= 1.0`.
     - FFmpeg filter output: Verify `build_ffmpeg_mask_filter` outputs valid `delogo`, `drawbox`, and `boxblur` filters.
   - **Target Execution Time**: `< 1 second`.

3. **Tier 3: Pipeline Execution & Mock Orchestrator Integration Tests**
   - **Scope**:
     - Mount a test WebSocket client to `/ws/pipeline`.
     - Trigger `/api/pipeline/start` with a mocked runner.
     - Verify received JSON messages match the expected event schemas: `{"type": "substep", ...}`, `{"type": "overall", ...}`, `{"type": "finished", ...}`.
     - Verify `/api/pipeline/cancel` cleanly stops execution.
   - **Target Execution Time**: `< 3 seconds`.

4. **Tier 4: End-to-End Media Export & Asset Delivery Tests**
   - **Scope**:
     - Generate a synthetic 2-second test MP4 via FFmpeg `lavfi color=size=320x180:duration=2`.
     - Upload or select synthetic video via `/api/media/select`.
     - Save a test mask via `/api/masks`.
     - Call `/api/export/mp4`: Inspect resulting MP4 with ffprobe, verify resolution, duration, and that delogo/blur filter executed without error.
     - Call `/api/export/capcut`: Inspect resulting folder, verify `draft_content.json` exists, version matches local schema, tracks contain video, audio, and subtitle segments, and `Assets/video-da-xoa-chu.mp4` is generated.
     - Static file test: Request `/`, `/assets/*`, `/logo.png`, `/favicon.png`, verify HTTP 200 and correct MIME types.
   - **Target Execution Time**: `< 8 seconds`.

---

## 9. Actionable Recommendations for Implementation Phase

1. **Fix Backend Mask Endpoints**:
   Implement `GET /api/masks` and `POST /api/masks` in `src/vkdub/web/server.py`.
2. **Fix Approval Gate in `server.py`**:
   Update `approve_script()` to invoke `state.project.approve(True)`.
3. **Fix Export MP4 Mask Fallback**:
   In `export_mp4()`, apply masks even if `speech_wav` is not yet generated.
4. **Update `pyproject.toml` for Test Automation**:
   Add `pythonpath = ["src"]` to `[tool.pytest.ini_options]`.
5. **Enhance `run_app.bat`**:
   Replace hardcoded user path with portable `%~dp0tools;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%`.
6. **Frontend Interactive Canvas**:
   In `frontend/src/App.jsx`, eliminate the manual coordinate input cards and implement the interactive drag/resize canvas overlay on the video player in Step 3.
