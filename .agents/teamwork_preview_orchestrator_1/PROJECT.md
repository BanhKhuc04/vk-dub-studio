# Project: ToolVideo Web UI Refactoring (KAPPAK Studio Web v2)

## Architecture
KAPPAK Studio Web v2 is an automated video localization and dubbing workstation featuring an Apple-minimalist Web UI connected to a high-performance Python FastAPI backend.
- **Frontend Layer (`frontend/`)**: React + Vite SPA using Apple Design Language (frosted glass, hairline borders, Framer Motion spring physics, Dynamic Island notifications, and crisp KAPPAK branding). Features an `InteractiveCanvas` overlay on the video player with letterbox/pillarbox compensation, enabling mouse-drawn blur masks with 8-handle resizing and eliminating manual X/Y/W/H numeric inputs.
- **Backend API Layer (`src/vkdub/web/server.py`)**: FastAPI application providing REST and WebSocket endpoints for video upload & metadata probing, voice catalog & preview, mask coordinate persistence, 5-step pipeline execution, script review, and MP4 / CapCut project exports.
- **Media & Processing Pipeline (`src/vkdub/`)**:
  - Mask Service (`mask_service.py`): Converts normalized `[0.0, 1.0]` coordinates into FFmpeg `delogo`/`boxblur` filter graphs and CapCut draft tracks.
  - Pipeline Runner (`pipeline_runner.py`): Manages multi-threaded pipeline execution (Whisper transcription, contextual translation, TTS voice synthesis, audio timeline alignment).
  - CapCut Export (`capcut_export.py`): Generates valid CapCut drafts with aligned video, dubbed audio, and subtitle tracks.
  - Render Service (`render_service.py`): Executes bundled FFmpeg commands to render final dubbed and masked MP4 videos.
- **External Tools & Environment**: Bundled FFmpeg & FFprobe 8.1.1 in `tools/`, Python 3.12 in `.venv`, automated one-click startup via `run_app.bat`.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Eliminate Manual Coordinate Inputs | Remove static numeric text inputs (X, Y, W, H, Sigma) from Step 3 | M2 | ORIGINAL_REQUEST R1 |
| 2 | Interactive Video Canvas Blur | Mouse-driven drawing, dragging, and 8-handle resizing directly over video with letterbox/pillarbox compensation | M2 | ORIGINAL_REQUEST R1 |
| 3 | Apple Minimalist Design System | Frosted glass (backdrop-blur 24px), hairline borders, diffused shadows, Dark/Light mode toggle | M2 | ORIGINAL_REQUEST R1 |
| 4 | Framer Motion & Dynamic Island | Spring animation transitions and Apple-style Dynamic Island notification banner | M2 | ORIGINAL_REQUEST R1 |
| 5 | Crisp KAPPAK Branding & Favicon | Official logo from `logo/logo.png` rendered sharply in Header and browser tab Favicon | M2 | ORIGINAL_REQUEST R1 |
| 6 | Step 1 Video Drag & Drop Preview | Instant video load on drop with resolution, duration, and FPS metadata | M2 | ORIGINAL_REQUEST R2 |
| 7 | Step 2 AI Voice Selection & Preview | Compact voice selector (Vbee / Edge TTS) with 1-click audio preview endpoint | M1, M2 | ORIGINAL_REQUEST R2 |
| 8 | Step 3 Blur Mask Synchronization | Backend REST APIs (`GET/POST/DELETE /api/masks`) syncing normalized coordinates to project state | M1, M2 | ORIGINAL_REQUEST R2 |
| 9 | Step 4 1-Click Pipeline Automation | Automated execution of Whisper, AI translation, TTS, audio merge with live WebSocket progress | M1, M2 | ORIGINAL_REQUEST R2 |
| 10 | Step 5 Script Review & Confetti Export | Compact script editor, 1-click authentic MP4 export or CapCut draft export with confetti celebration | M1, M2 | ORIGINAL_REQUEST R2 |
| 11 | Backend Signal Wiring & Stability | Fix runner signals (`substep_updated`, `state_changed`, etc.) and `ArtifactRegistry` access in `server.py` | M1 | Survey Report 2 |
| 12 | Authentic MP4 Render & Subtitles | Render MP4 using master narration audio, mask filters, and subtitles without fallback raw copy | M1 | Survey Report 2 |
| 13 | Authentic CapCut Draft Export | Sync project approval hash and voice status so genuine CapCut draft project is created | M1 | Survey Report 2 |
| 14 | Independent Startup Script | `run_app.bat` starts FastAPI and opens browser cleanly | M1 | ORIGINAL_REQUEST R3 |
| 15 | 4-Tier Opaque-box Test Suite | Comprehensive automated tests for API contracts, blur math, pipeline execution, and exports | E2E | ORIGINAL_REQUEST & Strategy |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Suite | 4-Tier test suite (API contracts, blur math, pipeline simulation, export integrity) | None | DONE |
| M1 | Backend Core & Pipeline Bridge | Mask APIs, signal wiring, Edge TTS preview, authentic MP4/CapCut export, run_app.bat | None | DONE |
| M2 | Frontend Interactive Canvas & Apple UI | Remove manual inputs, InteractiveCanvas, Apple styling, Dynamic Island, branding, 5-step UI | M1 (contracts) | DONE |
| M3 | Final Verification & Hardening | Pass 100% E2E tests, adversarial stress tests, forensic audit, verify run_app.bat | M1, M2, E2E | DONE |

## Interface Contracts

### 1. Mask REST APIs (`/api/masks`)
- `GET /api/masks` -> `list[MaskRegion]`
  ```json
  [
    {
      "id": "mask_1",
      "x": 0.08,
      "y": 0.82,
      "width": 0.84,
      "height": 0.14,
      "label": "Phụ đề dưới"
    }
  ]
  ```
- `POST /api/masks` -> `{"status": "ok", "count": int}`
  Payload: `{"masks": [MaskRegion, ...]}`
- `DELETE /api/masks/{mask_id}` -> `{"status": "ok"}`

### 2. Voice Preview API (`/api/voices/preview`)
- `POST /api/voices/preview` -> `{"status": "ok", "audio_url": "/api/voices/preview_audio?id=..."}`
  Payload: `{"voice_id": "vi-VN-HoaiMyNeural", "text": "Xin chào, đây là giọng đọc thử nghiệm."}`

### 3. Pipeline Execution Signals (`PipelineRunner` -> `server.py`)
- `runner.substep_updated`: `(substep_id: str, status: object, pct: int, message: str)` -> updates `state.progress` & emits to WebSocket `/ws/progress`
- `runner.state_changed`: `(new_state: object, label: str)` -> updates `state.status`
- `runner.artifact_ready`: `(artifact_type: str, path: Path)` -> stores artifact in `state.project` and `state.artifacts`
- `runner.pipeline_completed`: `(project: object)` -> synchronizes `state.subtitles`, sets `state.project.master_voice_path`, and marks pipeline done
- `runner.pipeline_failed`: `(error_type: str, message: str)` -> reports error to WebSocket

### 4. Review & Export
- `POST /api/review/approve` -> `state.project.approve(True)`, computes `state.project.approved_revision_hash`
- `POST /api/export/mp4` -> calls `build_render_command` with master audio, `state.project.masks`, generates output MP4
- `POST /api/export/capcut` -> calls `export_capcut_project` with approved project and master voice, creates valid draft folder

## Code Layout
- Frontend Source: `D:\Work\Project_AI\ToolVideo\frontend\`
  - `src/App.jsx` — 5-step UI container, state, Dynamic Island
  - `src/components/InteractiveCanvas.jsx` — Canvas blur drawing and resize overlay
  - `src/styles.css` — Apple Minimalist design tokens, frosted glass, typography
  - `src/assets/logo.png` & `public/logo.png` — Official KAPPAK branding
- Backend Source: `D:\Work\Project_AI\ToolVideo\src\vkdub\`
  - `web/server.py` — FastAPI REST endpoints, WebSocket handler, static asset mounting
  - `domain/mask.py` — MaskItem domain model and normalization logic
  - `services/mask_service.py` — FFmpeg filter builder and CapCut mask track builder
  - `services/capcut_export.py` — CapCut project draft generator
  - `services/render_service.py` — FFmpeg render command generator
  - `orchestrator/pipeline_runner.py` — Workflow orchestrator
- Startup Script: `D:\Work\Project_AI\ToolVideo\run_app.bat`
- Tests: `D:\Work\Project_AI\ToolVideo\tests\`
