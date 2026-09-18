---
name: toolvideo-dev
description: >-
  Workflows, testing runbooks, and architectural patterns for developing VK Dub Studio and KAPPAK Studio.
  Use this skill whenever building, running, testing, or modifying video dubbing pipelines, web APIs,
  browser extensions, CapCut exports, or downloader features in this repository.
---

# ToolVideo / VK Dub Studio Development Skill

## 1. Quick Architecture Map

Component                | Path                                   | Technology / Role
:----------------------- | :------------------------------------- | :---------------------------------------------
**Desktop UI**           | `src/vkdub/ui/`                        | PySide6 6.10, dark theme, 3-column layout
**Web UI**               | `frontend/src/`                        | React 19, Vite, Framer Motion, canvas drawing
**Backend Server**       | `src/vkdub/web/server.py`              | FastAPI, WebSockets, REST endpoints
**Extension**            | `apps/browser-extension/`              | Manifest V3, Content scripts, Sidepanel
**Native Host**          | `tools/native_host/vkdub_host.py`      | 32-bit JSON Stdio IPC bridge
**Media Engines**        | `src/vkdub/media/`, `src/vkdub/services/` | FFmpeg, faster-whisper, VieNeu-TTS, Edge-TTS
**CapCut Exporter**      | `src/vkdub/services/capcut_export.py`  | Generates `draft_content.json` (v360000 / 7.7.0)
**KAPPAK Core**          | `src/kappak/`                          | SQLite WAL, Local Job Manager, yt-dlp

---

## 2. Common Development Workflows

### 2.1. Running the Application
- **Web Mode (Default)**:
  `.\.venv\Scripts\python.exe app.py` (opens `http://127.0.0.1:8000`).
- **Desktop Mode**:
  `.\.venv\Scripts\python.exe app.py --gui`.

### 2.2. Testing Runbooks
- Run core non-GUI tests:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_bridge_protocol.py tests/test_capcut_export.py tests/test_clip_engine.py tests/test_clip_export_service.py tests/test_e2e_clip_pipeline.py -q
  ```
- Run KAPPAK Core tests:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/kappak/ -q
  ```

### 2.3. Browser Extension & Native Host Setup
1. Register Native Messaging Host:
   ```powershell
   .\.venv\Scripts\python.exe tools/native_host/register_host.py
   ```
2. In Edge (`edge://extensions/`) or Chrome (`chrome://extensions/`):
   - Turn on **Developer mode**.
   - Click **Load unpacked** and select `apps/browser-extension`.
3. Quick Reload helper:
   Run `tools\reload_extension.bat`.

---

## 3. Critical Architectural Rules
1. **Never stall Qt or Web Server**: Long-running operations (audio extraction, model download, transcription, video rendering) must execute in worker threads/processes.
2. **CapCut Draft Structure**: Always preserve valid GUIDs, slot duration calculations, silence padding, and ensure audio tracks start at `00:00:00.000`.
3. **No Fake Done Claims**: Always verify changes against tests or actual runs before declaring completion.
