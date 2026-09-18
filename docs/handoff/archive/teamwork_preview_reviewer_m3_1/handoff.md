# Handoff Report — Milestone 3 (Final Verification & Hardening)

**Reviewer / Critic Subagent**: `teamwork_preview_reviewer_m3_1`  
**Date**: 2026-09-15  
**Working Directory**: `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_reviewer_m3_1`  
**Project Root**: `D:\Work\Project_AI\ToolVideo`  
**Recipient**: `parent` (`b5f99409-245e-49eb-86c4-0a2263ff8cec`)  
**Verdict**: **REQUEST_CHANGES**  

---

## 1. Observation

### Observation 1: Frontend Verification
1. **Manual Coordinate Inputs Removed**:
   - Inspected `frontend/src/App.jsx`. A case-insensitive regex search for `"Tọa độ X"`, `"Tọa độ Y"`, `"Chiều rộng"`, `"Chiều cao"`, and `"compact-grid"` yielded 0 results.
   - Lines 727-797 in `frontend/src/App.jsx` contain 1-click Quick Presets (`BLUR_PRESETS`), an Active Mask Configuration Card with percentage readouts (`Math.round(activeMask.x * 100)}%`), a blur strength slider (`4px` to `36px`), horizontal centering, and region deletion.
2. **InteractiveCanvas Implementation**:
   - `frontend/src/components/InteractiveCanvas.jsx` (448 lines) implements:
     - Letterbox/pillarbox calculation comparing container aspect ratio ($AR_{cont}$) to video aspect ratio ($AR_{vid}$) in `computeRenderBox()` (lines 43-92).
     - Mouse/pointer drawing and dragging with boundary clamping.
     - 8-handle resizing (`nw`, `n`, `ne`, `e`, `se`, `s`, `sw`, `w`) with anti-inversion and minimum size clamping (`minW = 0.02, minH = 0.02`) in lines 245-285.
     - Coordinates normalized to `[0.0, 1.0]` matching backend domain.
     - Live `backdrop-filter: blur(${blurSigma}px)` overlay and pointer capture.
3. **Apple Minimalist Aesthetic & Dynamic Island**:
   - `frontend/src/styles.css`: Frosted glass tokens (`--glass-blur: blur(24px) saturate(180%)`), hairline borders (`1px solid rgba(0,0,0,0.08)` / `rgba(255,255,255,0.12)`), SF Pro typography (`-apple-system, BlinkMacSystemFont, "SF Pro Display"`), and Dark/Light theme toggle.
   - `frontend/src/App.jsx:209-265`: Dynamic Island component with Framer Motion spring physics (`stiffness: 380, damping: 28`) reflecting idle, loading, voice preview, running progress, and success states.
   - `frontend/index.html:5-6` and `logo/logo.png`: Favicon and header brand image linked to `/logo.png`. Binary SHA256 hashes of `logo/logo.png` and `frontend/public/logo.png` are identical (`3BA7DC5E515EE51AB8F0042595E506BDD129A7E6BCB460C1730092E00A68321F`).
4. **Production Build**:
   - Executed `npm run build` in `D:\Work\Project_AI\ToolVideo\frontend`:
     ```
     > kappak-ui-v2@2.0.0 build
     > vite build
     ✓ 424 modules transformed.
     dist/index.html                   0.84 kB │ gzip:   0.48 kB
     dist/assets/index-D0WwJHBL.css   24.99 kB │ gzip:   5.27 kB
     dist/assets/index-NexhF6EW.js   406.92 kB │ gzip: 127.58 kB
     ✓ built in 200ms
     ```
     Exit code: `0`.

---

### Observation 2: Backend Core & Pipeline Bridge Verification
1. **Mask CRUD Persistence**:
   - `src/vkdub/web/server.py:363-404` exposes `GET /api/masks`, `POST /api/masks`, and `DELETE /api/masks/{mask_id}` syncing with `state.project.masks` via `MaskItem` domain objects.
2. **Edge TTS Voice Preview**:
   - `src/vkdub/web/server.py:323-360` exposes `POST /api/voices/preview` and `GET /api/voices/preview/stream`.
   - `src/vkdub/providers/edge_tts_provider.py` connects to Microsoft Edge Read Aloud WebSocket with `Sec-MS-GEC` anti-abuse token generation and falls back to local FFmpeg harmonic synthesis if offline.
3. **Pipeline Runner Signals**:
   - `src/vkdub/web/server.py:694-700` connects genuine signals: `substep_updated`, `state_changed`, `artifact_ready`, `log_emitted`, `pipeline_completed`, `pipeline_failed`, `pipeline_cancelled`. Invalid legacy signals (`overall_progress`, `pipeline_finished`) have been removed.
4. **Authentic Export**:
   - `src/vkdub/web/server.py:845-955` (`POST /api/export/mp4`) executes `build_render_command` with audio ducking and mask filters when dubbed audio is present, and executes authentic FFmpeg `build_ffmpeg_mask_filter` + ASS subtitles when audio is absent. Raw video copy bypasses are eliminated.
   - `src/vkdub/web/server.py:781-842` (`POST /api/export/capcut`) synchronizes subtitles, approves revision hash, checks master voice readiness, and calls `export_capcut_project()`.
5. **Startup Launcher**:
   - `run_app.bat` sets UTF-8 (`chcp 65001`), prepends `%~dp0tools;` to PATH, sets `PYTHONPATH=src;`, verifies virtualenv Python at `.\.venv\Scripts\python.exe`, and runs `app.py`.
   - `app.py:29-32` invokes `run_server(host="127.0.0.1", port=8000, open_browser=True)`, automatically opening `http://localhost:8000`.

---

### Observation 3: Test Suite Execution & Crash Discovery
When executing tests in two separate batches, all 70 tests pass:
- **Batch 1** (`tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py`):
  `21 passed in 1.03s`.
- **Batch 2** (`tests/test_e2e_api.py tests/test_e2e_blur_math.py tests/test_e2e_kappak.py`):
  `49 passed in 1.50s`.

**HOWEVER**, when running the **single unified test command** mandated in the Dispatch:
```powershell
$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py tests/test_e2e_api.py tests/test_e2e_blur_math.py tests/test_e2e_kappak.py -v
```
The test run crashes at test #9 with Windows exit code `3221226505` (`0xC0000409` - `STATUS_STACK_BUFFER_OVERRUN` / `FAST_FAIL`):
```
tests/test_streamlined_5steps.py::test_export_and_import_chatgpt_srt PASSED [  1%]
tests/test_streamlined_5steps.py::test_master_voice_intact_audio_in_capcut_export PASSED [  2%]
tests/test_render.py::test_escape_ffmpeg_filter_path PASSED              [  4%]
tests/test_render.py::test_build_audio_mix_filter PASSED                 [  5%]
tests/test_render.py::test_parse_ffmpeg_progress PASSED                  [  7%]
tests/test_render.py::test_build_speech_track_wav PASSED                 [  8%]
tests/test_render.py::test_fit_voice_wav_keeps_48khz_and_fits_slot_without_pitch_resampling PASSED [ 10%]
tests/test_render.py::test_build_render_command PASSED                   [ 11%]
tests/test_render.py::test_export_dialog_checklist 
<CRASH: RETCODE 3221226505 (0xC0000409)>
```

### Forensic Root Cause Analysis:
1. In `src/vkdub/web/server.py:54`:
   ```python
   class AppState:
       def __init__(self):
           self.qt_app = QCoreApplication.instance() or QCoreApplication([])
   ```
2. During the single unified pytest run, pytest collects `tests/test_e2e_api.py`.
3. `test_e2e_api.py:23` imports `from vkdub.web.server import app, state`.
4. `server.py:76` runs `state = AppState()`, which initializes a `QCoreApplication` singleton.
5. Pytest then runs `tests/test_render.py::test_export_dialog_checklist`, which instantiates `dialog = ExportDialog()`.
6. `ExportDialog` inherits from `QDialog` (`QWidget`). In Qt, attempting to construct a `QWidget` when the global application is a `QCoreApplication` (rather than `QApplication`) triggers an immediate fatal abort: `qFatal("QWidget: Must construct a QApplication before a QWidget")` / Windows `FAST_FAIL` (`0xC0000409`).

---

## 2. Logic Chain

1. From Observation 1, the frontend fulfills all functional and aesthetic criteria: manual coordinate textboxes are completely eradicated, `InteractiveCanvas.jsx` contains mathematically sound letterbox/pillarbox compensation and 8-handle resizing, the Apple Minimalist design tokens and Dynamic Island are cleanly implemented, and the Vite production build succeeds with 0 errors in 200ms.
2. From Observation 2, backend endpoints in `server.py` implement Mask CRUD, Edge TTS preview with offline fallback, correct Signal wiring to `PipelineRunner`, authentic MP4 rendering with FFmpeg mask filters, and authentic CapCut project exports.
3. From Observation 3, while individual test suites pass when run separately (21/21 in Batch 1, 49/49 in Batch 2 = 70/70 total), executing the required single unified command causes a fatal process crash (`0xC0000409`) at `test_export_dialog_checklist`.
4. Because `server.py` unconditionally initializes `QCoreApplication([])` at module import time, any test session collecting both `server.py` and Qt GUI widgets will crash.
5. In accordance with the Reviewer Protocol, the reviewer must NOT modify implementation code directly, but must report failures and issue a `REQUEST_CHANGES` verdict with actionable remediation steps.

---

## 3. Caveats

- **Integrity Violation Assessment**: Rigorous adversarial review was conducted across all files. No hardcoded test results, facade logic, or verification bypasses were detected. The implementations in `InteractiveCanvas.jsx`, `server.py`, and `edge_tts_provider.py` are authentic and substantive.
- **Isolated Execution**: When tests are run in isolated batches, all 70 unit and integration tests pass 100%. The defect is solely an application-level Qt singleton collision when running both GUI and web server test modules in a single Python process.

---

## 4. Conclusion

**Verdict**: **REQUEST_CHANGES**

### Critical Finding 1: Qt QCoreApplication Singleton Collision in Unified Test Run
- **Where**: `src/vkdub/web/server.py:54` (and/or `tests/conftest.py:8`)
- **What**: In `src/vkdub/web/server.py:54`, `AppState.__init__` creates a `QCoreApplication` instance:
  ```python
  self.qt_app = QCoreApplication.instance() or QCoreApplication([])
  ```
  When `tests/test_e2e_api.py` is collected in a unified pytest run, this creates a `QCoreApplication` singleton. When `tests/test_render.py::test_export_dialog_checklist` subsequently attempts to create `dialog = ExportDialog()` (`QDialog`/`QWidget`), Qt aborts with `0xC0000409` (`STATUS_STACK_BUFFER_OVERRUN`).
- **Why**: `QWidget` requires `QApplication` (or `QGuiApplication`), not `QCoreApplication`. Since `QApplication` is a subclass of `QCoreApplication`, initializing `QApplication` satisfies both GUI widgets and background `QThread`/`Signal` processing, whereas initializing `QCoreApplication` breaks all subsequent GUI widget instantiation.
- **Suggested Fix**:
  In `src/vkdub/web/server.py:52-56`, lazily initialize or prefer `QApplication`:
  ```python
  class AppState:
      def __init__(self):
          try:
              from PySide6.QtWidgets import QApplication
              self.qt_app = QApplication.instance() or QApplication([])
          except Exception:
              from PySide6.QtCore import QCoreApplication
              self.qt_app = QCoreApplication.instance() or QCoreApplication([])
  ```
  AND/OR in `tests/conftest.py`:
  ```python
  from PySide6.QtWidgets import QApplication
  _qapp = QApplication.instance() or QApplication([])
  ```
  This ensures that when the test suite runs in a single process, the global application instance is a `QApplication`, allowing all 70 tests to pass in a single unified command.

---

## 5. Verification Method

To reproduce and verify:

1. **Reproduce Failure (Current State)**:
   ```powershell
   $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py tests/test_e2e_api.py tests/test_e2e_blur_math.py tests/test_e2e_kappak.py -v
   ```
   *Observed*: Process crashes at `tests/test_render.py::test_export_dialog_checklist` with exit code `3221226505`.

2. **Verify Batch Success**:
   ```powershell
   $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py -v
   $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_e2e_api.py tests/test_e2e_blur_math.py tests/test_e2e_kappak.py -v
   ```
   *Observed*: 21 passed in batch 1, 49 passed in batch 2 (all 70 passing).

3. **Verify Frontend Build**:
   ```powershell
   cd frontend
   npm run build
   ```
   *Observed*: Exit code 0, 424 modules built.
