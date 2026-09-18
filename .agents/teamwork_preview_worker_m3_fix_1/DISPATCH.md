## 2026-09-15T03:48:06Z
# Dispatch: Worker M3 Fix (Unified Test Session Qt Conflict Fix)

## Context
Project Root: D:\Work\Project_AI\ToolVideo
Original Request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md
Gate Status: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_1\GATE_STATUS.md
Reviewer M3 Handoff: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_reviewer_m3_1\handoff.md
Your Directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m3_fix_1

## Mandatory Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Write Ownership
You exclusively own:
- `src/vkdub/web/server.py`
- `tests/conftest.py`
- Any related test configuration file

## Problem to Solve
When running the full unified test suite in a single pytest command:
`$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py tests/test_e2e_api.py tests/test_e2e_blur_math.py tests/test_e2e_kappak.py -v`
The test runner crashes at `tests/test_render.py::test_export_dialog_checklist` with exit code `3221226505` (`0xC0000409` - `FAST_FAIL`).

**Root Cause**:
In `src/vkdub/web/server.py:54`:
`self.qt_app = QCoreApplication.instance() or QCoreApplication([])`
When `server.py` is imported (e.g. during `test_e2e_api.py`), it creates a `QCoreApplication` singleton (which is a non-GUI application).
Later, when `tests/test_render.py` runs and instantiates `ExportDialog(QDialog)`, PySide6 immediately fast-fails because GUI widgets cannot run on a non-GUI `QCoreApplication`.

**Solution**:
1. In `src/vkdub/web/server.py`, initialize `self.qt_app` cleanly:
   Try to check for `QApplication.instance()` or `QCoreApplication.instance()`. If no application instance exists, prefer creating a `QApplication([])` (or `QGuiApplication([])`) if `QtWidgets` is importable, or lazily initialize `self.qt_app` only when `PipelineRunner` requires it.
2. In `tests/conftest.py`:
   Add a session-scoped fixture or initialization at the top:
   ```python
   import os
   os.environ["QT_QPA_PLATFORM"] = "offscreen"
   from PySide6.QtWidgets import QApplication
   app = QApplication.instance() or QApplication([])
   ```
   This ensures that throughout the entire pytest session, the Qt singleton is a headless `QApplication`, allowing both headless API tests AND QWidget dialog tests to run in the same process without conflicts.
3. Verify by running the full unified command:
   `$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py tests/test_e2e_api.py tests/test_e2e_blur_math.py tests/test_e2e_kappak.py -v`
   All 70 tests must pass with exit code 0.
4. Deliver report to `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m3_fix_1\changes.md` and `handoff.md`.
