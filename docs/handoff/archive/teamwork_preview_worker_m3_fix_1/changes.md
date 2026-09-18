# Changes Summary — Qt Singleton Unified Session Fix

## Overview
Resolved the PySide6 application singleton initialization conflict that previously caused a fatal abort (`0xC0000409` - FAST_FAIL) when running all 70 unified tests in a single command (`test_render.py::test_export_dialog_checklist`).

## Modified Files

### 1. `tests/conftest.py`
- **Change**: Explicitly set `os.environ["QT_QPA_PLATFORM"] = "offscreen"` and initialized a shared session-scoped `_session_qapp = QApplication.instance() or QApplication([])`.
- **Rationale**: By initializing `QApplication` as the shared singleton before any test collection or execution begins, both headless QWidget dialog tests (like `ExportDialog`) and QObject signal/pipeline runners share a fully compatible application context.

### 2. `src/vkdub/web/server.py`
- **Change**:
  - Conditionally imported `QApplication` from `PySide6.QtWidgets`.
  - In `AppState.__init__`: checked `QApplication.instance() or QCoreApplication.instance()`. Only if no instance exists, instantiated `QApplication([])` (or `QCoreApplication([])` as fallback).
- **Rationale**: Prevents `server.py` module import from unconditionally instantiating a non-GUI `QCoreApplication([])` singleton when a `QApplication` already exists or when subsequent GUI widget operations will be required.

### 3. `tests/test_ws_local_agent.py`
- **Change**: In `test_local_agent_websocket_handshake_and_flow`, changed `app = QCoreApplication.instance() or QCoreApplication([])` to also safely check `QApplication.instance() or QCoreApplication.instance() or QApplication([])`.
- **Rationale**: Prevents standalone or isolated executions of WebSocket local agent tests from locking the Qt singleton into `QCoreApplication`.

## Verification Results
1. **Unified Test Suite (70 tests)**:
   ```powershell
   $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py tests/test_e2e_api.py tests/test_e2e_blur_math.py tests/test_e2e_kappak.py -v
   ```
   **Result**: 70 passed in 2.33s (100% pass, exit code 0).

2. **Full Repository Regression Suite (564 tests)**:
   ```powershell
   $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest -v
   ```
   **Result**: 564 passed in 347.93s (100% pass, 0 failures, exit code 0).

3. **Frontend Production Build**:
   ```powershell
   cd frontend && npm run build
   ```
   **Result**: 424 modules transformed, built in 239ms, exit code 0.
