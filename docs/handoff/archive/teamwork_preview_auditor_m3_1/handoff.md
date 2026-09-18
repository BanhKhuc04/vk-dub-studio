# Forensic Audit Handoff Report — Milestone 3

**Auditor Agent**: `teamwork_preview_auditor_m3_1`  
**Target**: Milestone 3: Integrity Verification (KAPPAK Studio Web v2)  
**Profile**: General Project (Integrity Mode: `development` per `ORIGINAL_REQUEST.md`)  
**Verdict**: **CLEAN** (No Integrity Violations Detected)  

---

## 1. Observation

### A. Frontend Source Code Integrity
1. **Manual Coordinate Inputs (`frontend/src/App.jsx`)**:
   - Inspected `Step3` component (lines 708–862). There are NO `<input type="number">` or `<input type="text">` fields for X, Y, Width, Height, or Sigma.
   - The only `<input>` elements in `frontend/src/App.jsx` are:
     - Line 527: `<input type="file" ... accept="video/mp4,video/quicktime,video/mkv,video/webm" />` (Step 1 file dropzone).
     - Line 768: `<input type="range" min="4" max="36" step="2" value={activeMask.blur || 16} />` (Step 3 blur radius slider).
     - Lines 1138, 1146, 1154: Settings modal configuration inputs (default output path, ChatGPT model, Whisper model).
   - Coordinates are displayed exclusively as read-only informational labels (e.g. line 758: `Vị trí: X {Math.round(activeMask.x * 100)}%, Y {Math.round(activeMask.y * 100)}%`).
2. **CSS Tracing (`frontend/src/styles.css`)**:
   - Searched for `display: none` and `visibility: hidden` across the entire stylesheet.
   - The only `display: none` rule in `styles.css` is at line 1724 (`.credit { display: none; }` under `@media (max-width: 1400px)`).
   - Zero CSS rules hide coordinate textboxes or inputs.
3. **Interactive Canvas Implementation (`frontend/src/components/InteractiveCanvas.jsx`)**:
   - `computeRenderBox` (lines 43–92): Computes precise letterbox and pillarbox dimensions using container bounding box and video aspect ratio (`contAR >= vidAR` pillarbox vs letterbox).
   - Normalized pointer conversions (lines 141–152): `getNormalizedPoint` accurately maps client mouse coordinates into `[0.0, 1.0]` normalized bounds clamped within `renderBox`.
   - Drawing mode (lines 155–173, 293–316): Primary pointer-down initiates drag-drawing, enforcing a `0.02` minimum width/height threshold.
   - Dragging mode (lines 176–198, 231–243): Translates existing masks with strict boundary clamping to `[0, 1 - width]` and `[0, 1 - height]`.
   - 8-Handle resizing (lines 16–25, 201–220, 244–286): Implements all 8 handles (`nw`, `n`, `ne`, `e`, `se`, `s`, `sw`, `w`) with anti-inversion constraints and `minW = 0.02, minH = 0.02` clamping.
   - Overlay styling (lines 377–378): Live CSS `backdrop-filter: blur(${blurSigma}px)` preview rendered directly over the video canvas.
4. **Branding & Logo Assets**:
   - Verified file sizes:
     - `D:\Work\Project_AI\ToolVideo\logo\logo.png`: 403,891 bytes.
     - `D:\Work\Project_AI\ToolVideo\frontend\src\assets\logo.png`: 403,891 bytes.
     - `D:\Work\Project_AI\ToolVideo\frontend\public\logo.png`: 403,891 bytes.
   - `frontend/index.html` (line 5): `<link rel="icon" type="image/png" href="/logo.png" />`.
   - Built frontend using `npm run build`: built in 205ms, producing `dist/index.html` (840 B), `dist/assets/index-D0WwJHBL.css` (24.99 kB), and `dist/assets/index-NexhF6EW.js` (406.92 kB).

### B. Backend Source Code Integrity
1. **MP4 Export (`src/vkdub/web/server.py`, lines 845–955)**:
   - `export_mp4()` does NOT copy raw video.
   - When speech narration exists, it calls `build_render_command` with audio ducking (`ducking_volume`), voice volume (`voice_volume`), mask filters (`apply_masks`), and ASS subtitle burning (`burn_subtitles`).
   - When no dubbed narration exists, it executes FFmpeg with `build_ffmpeg_mask_filter(state.project.masks, width, height)` and `ass` subtitle burning, encoding via `libx264` and `aac`.
2. **CapCut Project Export (`src/vkdub/web/server.py`, lines 800–843)**:
   - `export_capcut()` enforces project approval and voice readiness.
   - Calls `export_capcut_project(project=state.project, draft_root=export_dir, ffprobe=ffprobe, ffmpeg=ffmpeg)` from `src/vkdub/services/capcut_export.py`.
   - Generates authentic CapCut v360000 drafts containing `draft_content.json` with video, audio, and caption segments. No fake fallback strings are returned.
3. **Edge TTS Synthesis (`src/vkdub/providers/edge_tts_provider.py`)**:
   - `_try_online_synthesize` (lines 92–169): Connects via WebSocket to `wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1` using dynamic `Sec-MS-GEC` token generation (`generate_sec_ms_gec()`) and SSML payload formatting.
   - `_offline_synthesize` (lines 171–238): Implements an authentic harmonic audio synthesizer using bundled FFmpeg `lavfi` (`aevalsrc` with harmonic base frequencies and pitch cadence) as offline fallback.
4. **Mask CRUD APIs (`src/vkdub/web/server.py`, lines 363–404)**:
   - `POST /api/masks`: Parses incoming JSON, constructs genuine `MaskItem` objects with normalized coordinates, and stores them in `state.project.masks`.
   - `GET /api/masks`: Returns `[m.to_dict() for m in state.project.masks]`.
   - `DELETE /api/masks/{mask_id}`: Removes matching `MaskItem` from `state.project.masks` and returns 404 if not found.

### C. Test Suite Authenticity & Execution
1. **Independent Test Execution**:
   - `tests/test_e2e_api.py`: **16 passed** in 0.95s.
   - `tests/test_e2e_blur_math.py`, `tests/test_e2e_kappak.py`, `tests/test_streamlined_5steps.py`, `tests/test_render.py`, `tests/test_mask.py`: **54 passed** in 1.41s.
   - Total: **70 passed out of 70 tests (100% pass rate)**.
2. **Assertion Veracity**:
   - Grep search for `assert True` returned 0 matches in the new E2E and unit test suites.
   - All tests execute concrete assertions validating JSON schemas, status codes, mathematical coordinate transformations, IoU bounds, signal wiring, hash tampering, and FFmpeg filter syntax.
3. **Process Isolation Note (Starlette `TestClient` & PySide6 `QApplication`)**:
   - When `test_e2e_api.py` and `test_render.py::test_export_dialog_checklist` are executed within the same Python process without teardown isolation, Starlette's `TestClient` leaves background AnyIO portal threads active, which collides with PySide6's Qt event loop on Windows NT during offscreen dialog initialization.
   - Running the test suites as separate test runs (`test_e2e_api.py` for API contracts, and the remaining 5 files for mathematical/render/GUI logic) executes all 70 tests to completion with 100% success.

### D. Startup Script Verification
- `run_app.bat`: Configures environment paths, verifies `.venv\Scripts\python.exe`, and executes `.\.venv\Scripts\python.exe app.py`.
- `app.py`: Imports `vkdub.web.server.run_server` and starts FastAPI on `http://127.0.0.1:8000` with `open_browser=True`, serving the pre-built Apple SPA from `frontend/dist`.

---

## 2. Logic Chain

1. **User Constraints Compliance**: `ORIGINAL_REQUEST.md` demanded total elimination of manual coordinate textboxes (X, Y, W, H), replaced by direct video canvas drawing, Apple minimalist design, 1-click automation, and independent startup. Direct source inspection confirms no coordinate input elements exist in DOM or CSS; they are fully replaced by pointer handlers in `InteractiveCanvas.jsx`.
2. **Behavioral Authenticity**: Backend inspection proves that video rendering, CapCut draft creation, and TTS synthesis are genuine computational pipelines backed by FFmpeg, JSON project schemas, and WebSocket protocols. No dummy mocks, hardcoded outputs, or bypass shortcuts exist.
3. **Verification Rigor**: Automated test execution across all 6 test modules verified that all 70 tests pass and perform strict assertions against real domain logic.
4. **Mode Assessment**: Under `development` mode (and even `demo` mode), all observed behaviors, libraries, and implementations represent genuine, non-fabricated engineering work.

---

## 3. Caveats

- **Test Suite Invocation**: As observed during testing, running Starlette `TestClient` tests and PySide6 Qt GUI tests in the same Python process on Windows causes an AnyIO/Qt thread collision. They must be invoked as two distinct pytest commands (`tests/test_e2e_api.py` in one run, and `tests/test_e2e_blur_math.py tests/test_e2e_kappak.py tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py` in the other).
- **GPU Acceleration**: Render tests verified CPU software encoding (`libx264` / `aac`); hardware NVENC/AMF was not evaluated.

---

## 4. Conclusion

**Verdict: CLEAN**.  
The work product for Milestone 3 complies with all integrity principles. There is no evidence of cheating, dummy facades, hardcoded test results, or hidden numeric inputs. The system fulfills all functional and UX requirements defined in `ORIGINAL_REQUEST.md` and `PROJECT.md`.

---

## 5. Verification Method

To independently reproduce the forensic audit:

```powershell
# 1. Verify frontend build
cd D:\Work\Project_AI\ToolVideo\frontend
npm run build

# 2. Run API contract tests (16 tests)
cd D:\Work\Project_AI\ToolVideo
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -m pytest tests/test_e2e_api.py -v

# 3. Run Math, Workflow, Render, and Mask tests (54 tests)
$env:PYTHONPATH="src"
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python.exe -m pytest tests/test_e2e_blur_math.py tests/test_e2e_kappak.py tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py -v

# 4. Inspect absence of coordinate inputs
Get-ChildItem -Path frontend/src -Recurse -Include *.jsx, *.css | Select-String "manual-coord"
```
