# KAPPAK Studio Web v2 — E2E Testing Infrastructure (4-Tier Suite)

**Author**: `teamwork_preview_worker_e2e_1` (E2E Test Writer)  
**Date**: 2026-09-15  
**Project**: ToolVideo / KAPPAK Studio Web v2  
**Target Files**:
- `tests/test_e2e_api.py` (Tier 1)
- `tests/test_e2e_blur_math.py` (Tier 2)
- `tests/test_e2e_kappak.py` (Tier 3 & Tier 4)

---

## 1. Executive Overview & Test Architecture

The E2E Test Suite for KAPPAK Studio Web v2 provides comprehensive, opaque-box, and progressive testability for the automated video dubbing workstation. The suite is structured into 4 distinct tiers:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       4-Tier E2E Test Architecture                      │
├─────────────────────────────────────────────────────────────────────────┤
│ Tier 1: Fast API Contracts                                              │
│ - tests/test_e2e_api.py                                                 │
│ - FastAPI REST endpoints, WebSockets, probe metadata, settings, masks   │
├─────────────────────────────────────────────────────────────────────────┤
│ Tier 2: Interactive Blur Math & Coordinate Transformations              │
│ - tests/test_e2e_blur_math.py                                           │
│ - Letterbox / pillarbox compensation, [0.0, 1.0] normalization,         │
│   8-handle resize arithmetic, delogo 1-px context boundary compliance   │
├─────────────────────────────────────────────────────────────────────────┤
│ Tier 3: 5-Step Pipeline Simulation & Signal Wiring                      │
│ - tests/test_e2e_kappak.py                                              │
│ - Full 5-step lifecycle, Signal connection contracts, approval hashes,  │
│   tamper detection, atomic checkpoint recovery                          │
├─────────────────────────────────────────────────────────────────────────┤
│ Tier 4: Output Export Integrity                                         │
│ - tests/test_e2e_kappak.py                                              │
│ - Authentic MP4 render command (audio ducking amix, mask filters, ass), │
│   authentic CapCut v360000 draft structure, unapproved rejection        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Test Execution Command & Environment

Tests are executed with the bundled Python 3.12.12 virtual environment and `pytest 9.1.1`:

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -m pytest tests/test_e2e_kappak.py tests/test_e2e_blur_math.py tests/test_e2e_api.py -v
```

### Key Runtime Dependencies:
- `fastapi` & `starlette.testclient.TestClient`: High-speed in-memory HTTP and WebSocket client.
- `PySide6.QtCore`: Signal / Slot execution runtime for pipeline runner.
- `pytest` & `pytest-qt`: Parallelizable test runner and assertion framework.
- Bundled `tools/ffmpeg.exe` & `tools/ffprobe.exe` (v8.1.1 essentials).

---

## 3. Tier-by-Tier Specifications

### Tier 1: Fast API Contracts (`tests/test_e2e_api.py`)
1. **Health & Tool Probing**:
   - `GET /api/health` validates presence of FFmpeg and FFprobe binaries and app version (`2.x`).
   - `GET /api/bridge/status` returns connection status to LocalAgent extension bridge.
2. **Branding Assets**:
   - `GET /api/logo` streams official `logo/logo.png`, validating PNG binary magic bytes (`\x89PNG\r\n\x1a\n`).
3. **Media Ingestion & Streaming**:
   - `POST /api/media/select` probes video resolution, duration, FPS, codecs, and size.
   - `POST /api/media/upload` handles multipart video uploads and triggers instant metadata probing.
   - `GET /api/media/stream` tests byte-range streaming (`Accept-Ranges: bytes`).
4. **Voice Catalog & Preview**:
   - `GET /api/voices` returns unified catalog of Vbee voices and Microsoft Edge TTS voices (`vi-VN-HoaiMyNeural`, `vi-VN-NamMinhNeural`).
   - `POST /api/voices/preview` tests voice synthesis audio generation.
5. **Interactive Mask Persistence**:
   - Full CRUD lifecycle: `GET /api/masks`, `POST /api/masks` (stores `MaskItem` in `state.project.masks`), `DELETE /api/masks/{mask_id}`.
6. **Review Subtitles & Approval**:
   - `GET /api/review/subtitles` & `POST /api/review/subtitles`.
   - `POST /api/review/approve` sets `state.approved_script = True`.
7. **Real-time Pipeline & WebSocket**:
   - `GET /api/pipeline/status` and `POST /api/pipeline/cancel`.
   - `/ws/pipeline` WebSocket connection receives initial state broadcast.

### Tier 2: Interactive Blur Math & Coordinate Transformations (`tests/test_e2e_blur_math.py`)
1. **Viewport & Container Geometry**:
   - Implements `calculate_video_viewport` for CSS `object-fit: contain`.
   - Tests Letterbox (black bars top/bottom when $AR_v > AR_c$), Pillarbox (black bars left/right when $AR_v < AR_c$), and exact fit.
   - Covers 16:9 landscape, 9:16 portrait (TikTok/Reels), 1:1 square, and 21:9 ultrawide media.
2. **Coordinate Normalization & Clamping**:
   - `screen_to_normalized`: maps container mouse clicks $(x_s, y_s)$ to normalized $[0.0, 1.0]$.
   - Detects clicks in margins outside the video frame and clamps boundary values.
   - `normalized_roundtrip_quantization_invariance`: verifies norm -> screen -> norm is bijective within float epsilon.
3. **8-Handle Resizing Arithmetic**:
   - Independent transformation algorithms for all 8 handles (`nw`, `n`, `ne`, `e`, `se`, `s`, `sw`, `w`).
   - Anti-inversion logic prevents bounding box collapse or negative dimensions by clamping to `min_size`.
4. **Translation & Clamping**:
   - Dragging masks clamps strictly within $[0.0, 1.0 - w]$ and $[0.0, 1.0 - h]$.
5. **FFmpeg Filter Graph Generation**:
   - `delogo` 1-pixel context boundary compliance: tests that when $x=0$ or $x+w=1.0$, `delogo` insets by 1 pixel ($x \ge 1, w \le W_v - 2$) so FFmpeg's delogo filter does not fail.
   - `boxblur` + `blend` smoothstep filter chain for blur masks.
   - `drawbox` fill for solid masks.
   - Exclusion of `sub_region` masks from FFmpeg render filter chains.
   - Timing filter expressions (`between(t, ...)` and `gte(t, ...)`).

### Tier 3: 5-Step Pipeline Simulation & Signal Wiring (`tests/test_e2e_kappak.py`)
1. **Full 5-Step Lifecycle Simulation**:
   - Video selection -> Voice configuration -> Blur mask creation -> Pipeline execution -> Script approval.
2. **Signal Verification & Regression Prevention**:
   - Asserts all required signals on `PipelineRunner`: `substep_updated`, `state_changed`, `artifact_ready`, `log_emitted`, `pipeline_completed`, `pipeline_failed`, `pipeline_cancelled`.
   - Verifies removal of deprecated signals (`overall_progress` and `pipeline_finished`) that caused fatal crashes in Survey 2.
3. **Approval Revision Hashing**:
   - `project.revision_hash` binds script lines, video path, target language, and duration.
   - `project.approve(True)` assigns `approved_revision_hash`.
   - Modifying script text or timing changes `revision_hash` and immediately invalidates approval (`is_approved == False`, `voice_ready == False`).
4. **Atomic Checkpointing**:
   - Tests `save_checkpoint` and `load_checkpoint` to ensure resumption without duplicate execution.

### Tier 4: Output Export Integrity (`tests/test_e2e_kappak.py`)
1. **Authentic MP4 Render Command**:
   - `build_render_command` with video, master voice audio, masks, and ASS subtitles.
   - Verifies `-vf` contains `delogo`, `drawbox`, and `ass`.
   - Verifies `-filter_complex` contains `amix=inputs=2` with audio ducking (`volume=0.15` and `volume=1.00`).
   - Verifies raw copy fallback (`copy`) is NOT triggered when audio is present.
2. **Authentic CapCut Draft Structure**:
   - `export_capcut_project` produces genuine CapCut draft folder `VKDub YYYYMMDD-HHMMSS-<id>`.
   - Validates `draft_content.json` structure:
     - Track `"VOICE TIẾNG VIỆT — ĐÃ DỊCH"` containing 1 intact audio segment.
     - Track `"PHỤ ĐỀ TIẾNG VIỆT"` containing subtitle text segments.
     - Text materials with Vietnamese font, color, border, and content.
3. **Strict Validation & Rejection**:
   - Rejects unapproved projects (`is_approved == False`) with `ValueError`.
   - Rejects projects with missing voice assets.
4. **Path & Encoding Escaping**:
   - Verifies `escape_ffmpeg_filter_path` handles Windows drive colons (`C\:/`), single quotes (`\'`), and Vietnamese diacritics (`Tiếng Việt`).

---

## 4. Progressive Testability & Graceful Failure

Per dispatch instructions, endpoints that are actively being built by Milestone 1 (`teamwork_preview_worker_m1_1`) are tested with graceful failure semantics (`pytest.xfail`):
- `POST /api/settings`: Handled `AttributeError: 'AppSettings' object has no attribute 'chatgpt_model'` in `server.py` as an escalated defect.
- `POST /api/voices/preview`: Graceful `pytest.xfail` when status is 404 or 405 pending M1 implementation.
- `GET/POST/DELETE /api/masks`: Graceful `pytest.xfail` when status is 404 pending M1 implementation.

Once Milestone 1 deploys the backend endpoints in `server.py`, these tests will transition automatically to `PASS` without modifying test assertions.
