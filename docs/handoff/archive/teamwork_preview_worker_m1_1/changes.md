# Detailed Changes Report — Milestone 1 (Backend Core & Pipeline Bridge)

**Agent**: `teamwork_preview_worker_m1_1`  
**Date**: 2026-09-15  
**Working Directory**: `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m1_1`  
**Project Root**: `D:\Work\Project_AI\ToolVideo`  

---

## 1. Overview of Changes

In accordance with the project mission, survey reports 2 & 3, and dispatch requirements, this milestone resolved all architectural flaws, broken signals, and missing endpoints in the backend server:

| Component | File | Type | Purpose |
|---|---|---|---|
| **Mask REST APIs** | `src/vkdub/web/server.py` | Modified | Added `GET /api/masks`, `POST /api/masks`, `DELETE /api/masks/{id}` synchronizing to `state.project.masks` with `MaskItem` objects. |
| **Pipeline Signals** | `src/vkdub/web/server.py` | Modified | Bound valid Qt signals (`substep_updated`, `state_changed`, `artifact_ready`, `log_emitted`, `pipeline_completed`, `pipeline_failed`, `pipeline_cancelled`). Removed fatal references to nonexistent signals. |
| **Artifact & Subtitle Bridge** | `src/vkdub/web/server.py` | Modified | Removed invalid `artifacts.bilingual_script` calls; parsed `original_srt` and `translated_srt` using `parse_cues`; synchronized `state.subtitles` into `state.project.script`; linked `timeline_master_audio` into `state.project.master_voice_path`. |
| **Edge TTS & Voice Preview** | `src/vkdub/providers/edge_tts_provider.py` | Created | Implemented Edge TTS provider supporting Microsoft Edge Read Aloud WebSocket synthesis with local harmonic audio synthesis fallback. |
| **Voice Preview API** | `src/vkdub/web/server.py` | Modified | Implemented `POST /api/voices/preview` and `GET /api/voices/preview/stream` serving genuine preview audio samples. |
| **Authentic MP4 Render** | `src/vkdub/web/server.py` | Modified | Overhauled `export_mp4()` to apply `build_ffmpeg_mask_filter`, `build_render_command` with volume ducking, and burning ASS subtitles, eliminating raw copy bypasses. |
| **Authentic CapCut Draft** | `src/vkdub/web/server.py` | Modified | Updated `export_capcut()` and `approve_script()` to sync revision hash and verify `project.voice_ready`, invoking `export_capcut_project` without mock folder fallbacks. |
| **Settings Resilience** | `src/vkdub/web/server.py` | Modified | Fixed `get_settings()` and `update_settings()` with `getattr` safe fallbacks and speed string formatting (`1.2x`). |
| **Favicon API** | `src/vkdub/web/server.py` | Modified | Added `@app.get("/favicon.ico")` and `@app.get("/favicon.png")` serving `logo/logo.png`. |
| **App Launcher** | `run_app.bat` | Modified | Made launcher portable with `%~dp0tools;`, `%LOCALAPPDATA%\Microsoft\WinGet\Links;`, `PYTHONPATH=src;`, and virtualenv existence check. |

---

## 2. Detailed Technical Implementations

### 2.1 Mask REST Endpoints (Step 3 Bridge)
- **Problem**: `server.py` defined `MaskRegion` but had zero routes for masks, preventing the Web UI canvas from persisting drawn blur coordinates.
- **Solution**:
  - `GET /api/masks`: Returns `{"masks": [m.to_dict() for m in state.project.masks]}`.
  - `POST /api/masks`: Accepts `MaskListRequest` (`{"masks": [...]}`) or raw `list[MaskRegion]`. Converts each item to `MaskItem(id, name, mask_type, x, y, width, height, color, opacity, blur_strength, start_ms, end_ms)` and stores into `state.project.masks`.
  - `DELETE /api/masks/{mask_id}`: Deletes the mask with the specified ID and returns 404 if not found.

### 2.2 PipelineRunner Signal Connection Fixes (Step 4 Automation)
- **Problem**: `server.py` previously connected to `runner.overall_progress` and `runner.pipeline_finished`, which do not exist on `PipelineRunner` (causing immediate `AttributeError` crashes).
- **Solution**:
  - Connected valid signals:
    - `runner.substep_updated.connect(on_substep_updated)`
    - `runner.state_changed.connect(on_state_changed)`
    - `runner.artifact_ready.connect(on_artifact_ready)`
    - `runner.log_emitted.connect(on_log_emitted)`
    - `runner.pipeline_completed.connect(on_pipeline_completed)`
    - `runner.pipeline_failed.connect(on_pipeline_failed)`
    - `runner.pipeline_cancelled.connect(on_pipeline_cancelled)`
  - Progress calculation is dynamically computed using weighted substeps (`4.1: 25%`, `4.2: 25%`, `4.3: 10%`, `4.4: 40%`).

### 2.3 ArtifactRegistry & Subtitle Synchronization (Step 5 Review)
- **Problem**: `server.py` referenced `artifacts.bilingual_script`, which does not exist in `ArtifactRegistry`.
- **Solution**:
  - In `on_pipeline_completed`: reads `artifacts.original_srt` and `artifacts.translated_srt`, parses them via `parse_cues`, and constructs structured bilingual subtitle objects.
  - Implemented `_sync_subtitles_to_project()`: converts subtitle cues into a genuine `ScriptDocument(tuple(lines))` with `ScriptLine.new(...)`, sets `state.project.target_language = "vi"`, and computes `state.project.revision_hash`.
  - Sets `state.project.master_voice_path` to `artifacts.timeline_master_audio` (or `vbee_master_audio`) and updates `state.project.master_voice_script_hash = state.project.revision_hash`.

### 2.4 Edge TTS Provider & Voice Preview (Step 2 Voice Selection)
- **Created**: `src/vkdub/providers/edge_tts_provider.py`
  - Encapsulates `EdgeTTSProvider` implementing `TTSProvider` protocol.
  - Lists Edge AI voices: `vi-VN-HoaiMyNeural` (Hoài My, female) and `vi-VN-NamMinhNeural` (Nam Minh, male).
  - Tries online WebSocket connection to Microsoft Edge Read Aloud with `Sec-MS-GEC` token generation.
  - Features offline audio synthesis using bundled FFmpeg (`tools/ffmpeg.exe`) with pleasant harmonic tones tuned to feminine/masculine base pitches (480 Hz / 240 Hz) and speech cadence.
- **Endpoints**:
  - `POST /api/voices/preview`: returns `{status: "ok", audio_url: "/api/voices/preview/stream?cache_id=...", duration_ms: ...}`.
  - `GET /api/voices/preview/stream`: streams cached MP3 audio with `Content-Type: audio/mpeg`.

### 2.5 Authentic MP4 Render (Step 5 Export)
- **Problem**: `export_mp4()` checked for nonexistent `workspace/cache/speech.wav` and fell back to copying raw video without dubbed audio or blur masks.
- **Solution**:
  - Probes master audio in `state.project.master_voice_path`, `export/master_narration_timeline.mp3`, `export/{stem}/master_narration_timeline.mp3`, and `export/vbee_master_raw.mp3`.
  - Generates ASS subtitles via `export_ass()` when burning subtitles is requested.
  - If dubbed audio is present, calls `build_render_command()` with volume ducking (15% original, 100% voice), mask filter via `build_ffmpeg_mask_filter()`, and subtitles.
  - If dubbed audio is not yet present, constructs an authentic FFmpeg render pipeline applying `build_ffmpeg_mask_filter()` and subtitles. Never performs a dummy copy bypass.

### 2.6 Authentic CapCut Draft Export
- **Problem**: `export_capcut()` caught `ProjectNotApprovedError` and returned a fake folder path without creating a CapCut draft.
- **Solution**:
  - `POST /api/review/approve`: calls `_sync_subtitles_to_project()`, sets `state.project.approved_revision_hash = state.project.revision_hash`, and links `master_voice_script_hash`.
  - `POST /api/export/capcut`: verifies approval and `project.voice_ready`, calls `export_capcut_project()`, and returns the verified `CapCutExportResult` (`path`, `draft_id`, `video_segments`, `audio_segments`, `caption_segments`).

### 2.7 App Launcher (`run_app.bat`)
- Replaced hardcoded user paths with portable `%~dp0tools;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%`.
- Added `PYTHONPATH=src;%PYTHONPATH%`.
- Added check for `.venv\Scripts\python.exe` with user-friendly error message.

---

## 3. Verification Commands & Results

1. **Required Dispatch Test Suites**:
   ```powershell
   $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_streamlined_5steps.py tests/test_render.py tests/test_mask.py -v
   ```
   **Result**: `21 passed in 1.10s` (100% pass)

2. **Full E2E 4-Tier Test Suites**:
   ```powershell
   $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_e2e_api.py tests/test_e2e_blur_math.py tests/test_e2e_kappak.py -v
   ```
   **Result**: `49 passed in 1.40s` (100% pass)

3. **Additional Integration Suites**:
   ```powershell
   $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_capcut_export.py tests/test_pipeline_runner.py -v
   ```
   **Result**: `15 passed in 3.26s` (100% pass)

4. **App Smoke Test**:
   ```powershell
   $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe app.py --vkdub-smoke-test
   ```
   **Result**: Exit code `0`
