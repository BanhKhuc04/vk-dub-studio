# Dispatch: Worker for Milestone 2 (Frontend Interactive Canvas & Apple UI - KAPPAK Studio Web v2)

## Context
Project Root: D:\Work\Project_AI\ToolVideo
Original Request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md
Project Scope: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_1\PROJECT.md
Explorer Survey 1 Report: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_1\analysis.md
Your Directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m2_1

## Mandatory Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Write Ownership
You exclusively own:
- `frontend/src/App.jsx`
- `frontend/src/components/InteractiveCanvas.jsx`
- `frontend/src/styles.css`
- `frontend/src/assets/`
- `frontend/public/`
- `frontend/index.html`
You must NOT modify backend Python files or tests in `tests/`.

## Mission
Refactor and modernize the frontend to Apple Minimalist Aesthetic (KAPPAK Studio Web v2) and implement the Interactive Canvas blur region editor:

1. **Eliminate Manual Coordinate Inputs**:
   - In `frontend/src/App.jsx` Step 3, completely remove the manual coordinate text boxes (X, Y, W, H, Sigma at lines ~234-243).
   - In their place, provide:
     - Clear visual status: active blur mask label, normalized boundaries, blur strength slider (0 - 32px), delete mask button.
     - 1-click Quick Presets: "Phụ đề dưới" (Bottom subtitle: y=0.82, h=0.14, w=0.84, x=0.08), "Watermark góc phải" (Top-right: x=0.75, y=0.05, w=0.2, h=0.1), "Toàn dải đáy" (Full bottom strip: x=0.0, y=0.8, w=1.0, h=0.2).
     - Sync masks with backend: fetch `GET /api/masks` and persist on change via `POST /api/masks`.

2. **Interactive Video Canvas (`InteractiveCanvas.jsx`)**:
   - Create `frontend/src/components/InteractiveCanvas.jsx` and render it inside the video player container in `Preview` component (`App.jsx`).
   - Must handle Letterbox / Pillarbox compensation:
     Calculate rendered video dimensions ($W_{rend}, H_{rend}$) and offsets ($X_{off}, Y_{off}$) inside the container based on `video.videoWidth` and `video.videoHeight`.
     The canvas and interaction area must align strictly to the rendered video box.
   - Support:
     - Click and drag to draw a new rectangle anywhere on the video.
     - Click and drag inside an existing rectangle to move it.
     - 8 resize handles (`nw`, `ne`, `se`, `sw`, `n`, `s`, `e`, `w`) to resize the box smoothly with min-size clamping and anti-inversion.
     - Real-time visual CSS blur preview: `backdrop-filter: blur(16px)` directly over the video frame.
     - Seamlessly update normalized `[0.0, 1.0]` coordinates.
     - Ensure video player play/pause clicks do not conflict with canvas drawing (stop propagation when interacting with masks).

3. **Apple Minimalist Design System (KAPPAK Studio Web v2)**:
   - Modernize `frontend/src/styles.css`:
     - Frosted glass effect (`backdrop-filter: blur(24px) saturate(180%)`).
     - Ultra-thin hairline borders (`1px solid rgba(255, 255, 255, 0.12)` in dark mode, `1px solid rgba(0, 0, 0, 0.08)` in light mode).
     - Diffused multi-layer drop shadows.
     - Dark / Light mode toggle with smooth theme transition.
     - System typography: `-apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif`.
     - Framer Motion spring animations (`type: "spring", stiffness: 350, damping: 25`) on cards, tabs, and step transitions.

4. **Dynamic Island Notification Bar**:
   - Implement Apple-style Dynamic Island pill at top center with Framer Motion spring physics layout animations.
   - Shows live system states:
     - "Sẵn sàng" (Idle pill)
     - "Đang tải video..." (Loading video)
     - "Đang nghe thử giọng đọc..." (Playing TTS preview)
     - "Đang xử lý pipeline..." (Realtime step badge & progress)
     - "Hoàn thành xuất sắc!" (Celebration)

5. **Crisp KAPPAK Logo & Favicon**:
   - Verify official logo from `logo/logo.png` is displayed sharply in Header with proper retina display sizing.
   - Ensure `frontend/public/logo.png` and `favicon` are linked in `frontend/index.html`.

6. **Streamline 5-Step Pipeline Experience**:
   - Step 1: Drag & drop video file with immediate preview in player and video metadata badges (Resolution, Duration, FPS).
   - Step 2: Voice selection cards (Vbee / Edge TTS) with 1-click "Nghe thử" button invoking `POST /api/voices/preview` with instant audio playback.
   - Step 3: Interactive blur canvas drawing (NO X/Y/W/H boxes).
   - Step 4: 1-click "Bắt đầu tự động" running the full pipeline with live WebSocket progress bar.
   - Step 5: Subtitle review/edit, 1-click MP4 export or CapCut export with confetti celebration (`canvas-confetti`).

7. **Build & Verify**:
   - Run `npm run build` in `frontend/` to produce the production build.
   - Deliver full report to `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m2_1\changes.md` and `handoff.md`.

## 2026-09-15T03:35:41Z
Received dispatch invocation from parent (b5f99409-245e-49eb-86c4-0a2263ff8cec):
- Milestone: M2 (Frontend Interactive Canvas & Apple UI - KAPPAK Studio Web v2)
- Focus: Eliminate manual inputs, InteractiveCanvas.jsx, Apple UI, Dynamic Island, 5-step flow, Crisp KAPPAK Branding, build verification.
