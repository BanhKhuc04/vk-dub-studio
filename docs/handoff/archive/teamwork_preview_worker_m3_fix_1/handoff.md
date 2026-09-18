# Handoff Report — Qt Singleton Unified Test Suite Fix

**Worker Subagent**: `teamwork_preview_worker_m3_fix_1`  
**Date**: 2026-09-15  
**Working Directory**: `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m3_fix_1`  
**Project Root**: `D:\Work\Project_AI\ToolVideo`  
**Recipient**: `parent` (`b5f99409-245e-49eb-86c4-0a2263ff8cec`)  
**Type**: Hard Handoff  

---

## 1. Observation

1. **Reproduction of Unified Test Failure**:
   Executed the unified single-command test suite:
   ```powershell
   $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py tests/test_e2e_api.py tests/test_e2e_blur_math.py tests/test_e2e_kappak.py -v
   ```
   Observed fatal process crash at item #9:
   ```
   tests/test_render.py::test_export_dialog_checklist 
   <Process exited with code 1 / 3221226505 (0xC0000409) FAST_FAIL>
   ```
2. **Root Cause Inspection**:
   - In `src/vkdub/web/server.py:54`:
     ```python
     self.qt_app = QCoreApplication.instance() or QCoreApplication([])
     ```
     During pytest session collection, importing `test_e2e_api.py` loaded `server.py`, which instantiated a `QCoreApplication` singleton.
   - When test execution reached `tests/test_render.py::test_export_dialog_checklist`, it created `dialog = ExportDialog()`. Because `ExportDialog` inherits from `QDialog` (`QWidget`), PySide6 triggered a fatal abort because `QWidget` requires a `QApplication` rather than a `QCoreApplication`.
   - In `tests/conftest.py:8`, `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` set the environment variable, but did not initialize a `QApplication` instance at session start.

3. **Post-Remediation Verification**:
   - Modified `src/vkdub/web/server.py` (lines 21-24, 60-65) to check `QApplication.instance() or QCoreApplication.instance()` and only instantiate `QApplication([])` if no singleton exists.
   - Modified `tests/conftest.py` (lines 8-16) to explicitly set `os.environ["QT_QPA_PLATFORM"] = "offscreen"` and instantiate `_session_qapp = QApplication.instance() or QApplication([])`.
   - Modified `tests/test_ws_local_agent.py` (lines 19-24) to also use safe `QApplication` fallback.
   - Re-executed unified test command:
     ```
     ======================= 70 passed, 2 warnings in 2.33s ========================
     ```
     Exit code: `0`.
   - Executed full repository regression test suite:
     ```powershell
     $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest -v
     ```
     ```
     ================= 564 passed, 3 warnings in 347.93s (0:05:47) =================
     ```
     Exit code: `0`.
   - Executed frontend production build:
     ```powershell
     cd frontend && npm run build
     ```
     ```
     ✓ 424 modules transformed.
     dist/index.html                   0.84 kB │ gzip:   0.48 kB
     dist/assets/index-D0WwJHBL.css   24.99 kB │ gzip:   5.27 kB
     dist/assets/index-NexhF6EW.js   406.92 kB │ gzip: 127.58 kB
     ✓ built in 239ms
     ```
     Exit code: `0`.

---

## 2. Logic Chain

1. From Observation 1, the test runner crashed whenever `tests/test_render.py` (which instantiates `QWidget`/`QDialog`) was run in the same session after `src/vkdub/web/server.py` had been imported during pytest collection.
2. From Observation 2, PySide6 does not permit creating a `QApplication` or instantiating `QWidget` instances once a `QCoreApplication` singleton has already been initialized in the process. Attempting to do so causes a fast abort (`0xC0000409`).
3. Conversely, `QApplication` inherits from `QCoreApplication`. Initializing `QApplication` satisfies both GUI widgets and non-GUI components (`QObject`, `QThread`, Qt Signals).
4. By initializing `_session_qapp = QApplication.instance() or QApplication([])` in `tests/conftest.py` under `QT_QPA_PLATFORM="offscreen"`, any test or server import in the pytest session finds an existing `QApplication` instance via `QCoreApplication.instance()` and `QApplication.instance()`.
5. By updating `src/vkdub/web/server.py` to prioritize `QApplication` when creating or querying the instance, the server never creates a conflicting `QCoreApplication` when running either in tests or in standalone mode.
6. From Observation 3, after applying these changes, all 70 unified tests pass in a single command, all 564 tests across the entire codebase pass without regressions, and the frontend production build builds cleanly.

---

## 3. Caveats

No caveats. All test requirements and build checks pass 100% with zero regressions.

---

## 4. Conclusion

The Qt singleton initialization conflict in unified test sessions is completely resolved. The full suite of 70 tests runs in a single command in 2.33 seconds with a 100% pass rate. The entire project test suite (564 tests) passes with 0 failures, and the frontend build passes with 0 errors.

---

## 5. Verification Method

1. **Unified Test Suite (70 tests in single command)**:
   ```powershell
   $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py tests/test_e2e_api.py tests/test_e2e_blur_math.py tests/test_e2e_kappak.py -v
   ```
   *Expected result*: 70 passed in ~2.3 seconds, exit code 0.

2. **Frontend Production Build**:
   ```powershell
   cd frontend
   npm run build
   ```
   *Expected result*: 424 modules transformed, exit code 0.

3. **Full Project Test Suite**:
   ```powershell
   $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest -v
   ```
   *Expected result*: 564 passed, exit code 0.

4. **Invalidation Conditions**:
   Any revert of `tests/conftest.py` or `src/vkdub/web/server.py` that causes `QCoreApplication([])` to be instantiated prior to `ExportDialog` in `test_render.py`.
