# Changes Report: Milestone 2 — Frontend Interactive Canvas & Apple UI (KAPPAK Studio Web v2)

**Worker Subagent**: `teamwork_preview_worker_m2_1`  
**Date**: 2026-09-15  
**Directory**: `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_worker_m2_1`

---

## 1. Executive Summary

Milestone 2 has successfully modernized the frontend of ToolVideo into the **Apple Minimalist Aesthetic (KAPPAK Studio Web v2)** and implemented the **Interactive Video Canvas blur region editor**. All static, manual coordinate input boxes (`X, Y, Width, Height, Sigma`) have been eliminated from the interface and replaced with interactive mouse-driven drawing, dragging, 8-handle resizing, quick presets, and blur strength sliders.

---

## 2. File-by-File Detailed Changes

### A. `frontend/src/components/InteractiveCanvas.jsx` (NEW COMPONENT)
- **Letterbox / Pillarbox Compensation**:
  - Automatically calculates rendered video dimensions ($W_{rend}, H_{rend}$) and offsets ($X_{off}, Y_{off}$) inside the video container based on intrinsic video dimensions (`video.videoWidth`, `video.videoHeight`) and container aspect ratios.
  - Aligns the interaction canvas overlay strictly over the rendered video viewport, preventing users from drawing into black letterbox/pillarbox bars.
- **Drawing Mode**:
  - Pointer down on canvas background initiates drawing a new blur rectangle.
  - Converts client mouse coordinates into normalized `[0.0, 1.0]` coordinates.
  - Pointer capture via `setPointerCapture` guarantees smooth drawing even if the pointer moves rapidly.
  - Clamping threshold (`width >= 0.02 && height >= 0.02`) avoids creating accidental micro-rectangles.
- **Dragging / Moving Mode**:
  - Dragging the body of a mask updates normalized position with strict boundary constraints ($0 \le x \le 1 - width$, $0 \le y \le 1 - height$).
- **8-Handle Resizing with Anti-Inversion**:
  - Handles positioned at 4 corners (`nw, ne, se, sw`) and 4 edges (`n, s, e, w`).
  - Mathematical anti-inversion constraints prevent boxes from flipping inside out when dragged past their opposite edges.
  - Minimum size clamped to $0.02$ ($2\%$ of video dimension).
- **Real-Time CSS Blur Preview**:
  - Directly applies `backdrop-filter: blur(${mask.blur}px)` and `-webkit-backdrop-filter` over the video element.
  - Active box displays Apple Blue border (`#0071e3`), glowing drop shadow, and floating badge with percentage dimensions and delete button.
- **Event Collision Prevention**:
  - Stops pointer event propagation (`e.stopPropagation()`) so interacting with blur regions never inadvertently toggles video playback.

### B. `frontend/src/App.jsx` (REFACTORED)
- **Eliminated Manual Coordinate Inputs**:
  - Removed `compact-grid` and text input boxes for `Tọa độ X`, `Tọa độ Y`, `Chiều rộng`, `Chiều cao`, and `Gaussian Blur Sigma`.
  - Replaced with:
    1. **1-Click Quick Presets**:
       - *Phụ đề dưới* (`x: 0.08, y: 0.82, width: 0.84, height: 0.14`)
       - *Watermark góc phải* (`x: 0.75, y: 0.05, width: 0.20, height: 0.10`)
       - *Toàn dải đáy* (`x: 0.0, y: 0.80, width: 1.0, height: 0.20`)
    2. **Active Mask Configuration Card**:
       - Normalized percentage readouts (`X: 8%, Y: 82%`, `84% × 14%`).
       - Blur strength slider (4px - 36px, step 2).
       - Horizontal centering action ("Căn giữa ngang").
       - Direct mask deletion action ("Xóa vùng này").
    3. **Region List**:
       - Displays all configured masks with active indicators and individual delete buttons.
- **Backend Mask Synchronization**:
  - Fetches existing masks from `GET /api/masks` on mount.
  - Persists masks on any change (draw, drag, resize, preset, blur adjustment) via `POST /api/masks`.
  - Graceful fallback ensures local state stays responsive even if the backend is restarting or offline.
- **Apple Dynamic Island**:
  - Animated top-center pill powered by Framer Motion spring physics (`stiffness: 380, damping: 28`).
  - Morphing states:
    - *Idle*: Compact pill with pulsing emerald green dot ("KAPPAK v2 · Sẵn sàng").
    - *Loading / Uploading*: Animated spinner ("Đang tải và phân tích video…").
    - *Voice Preview*: Soundwave animation ("Đang nghe thử giọng đọc…").
    - *Pipeline Running*: Live step status, mini gradient progress bar, and percentage readout.
    - *Success*: Green checkmark and celebration ("Hoàn thành xuất sắc!").
    - *Error*: Red pulsing dot and error message.
- **1-Click Voice Audio Preview (Step 2)**:
  - Invokes `POST /api/voices/preview` with selected voice and sample text.
  - Plays returned audio via HTML5 `Audio` element, with fallback to Web Speech API `SpeechSynthesis`.
  - Dynamic Island reflects voice playback state with audio wave visualization.
- **Interactive Player Controls**:
  - Interactive timeline scrubber with current time / duration display.
  - Audio mute/unmute and fullscreen toggles.
- **Crisp Branding**:
  - Official logo from `/logo.png` displayed sharply in Header with Apple rounded corners and subtle hairline borders.
  - Credit badges for `vanhkhuc.dev` and `Trang Vũ <3`.

### C. `frontend/src/styles.css` (REDESIGNED)
- **Apple Minimalist Design Tokens**:
  - Backgrounds: Apple Clean (`#f5f5f7` / `#fbfbfd`) and Apple Obsidian (`#09090b` / `#0f0f13`).
  - Frosted Glass: `backdrop-filter: blur(24px) saturate(180%)`.
  - Hairline Borders: `1px solid rgba(0, 0, 0, 0.08)` (Light) / `1px solid rgba(255, 255, 255, 0.12)` (Dark).
  - Shadows: Diffused multi-layer shadows (`0 8px 30px rgba(0,0,0,0.06)`).
  - Typography: Native Apple San Francisco stack (`-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text"`).
  - Completely purged harsh 3px black neo-brutalist borders and offsets.

### D. `frontend/index.html`
- Updated title to `KAPPAK Studio Web v2 — Trạm lồng tiếng & Biên tập Video Apple Minimalist`.
- Added Apple touch icon and favicon linking to `/logo.png`.

### E. `frontend/dist/` (PRODUCTION BUILD)
- Verified with `npm run build`:
  - 424 modules transformed.
  - Zero compilation or bundling warnings.
  - Production bundle generated cleanly in `dist/`.

---

## 3. Verification Commands & Results

```powershell
cd D:\Work\Project_AI\ToolVideo\frontend
npm run build
```
Result:
- Exit Code: 0
- Output:
  - `dist/index.html` (0.84 kB)
  - `dist/assets/index-D0WwJHBL.css` (24.99 kB)
  - `dist/assets/index-NexhF6EW.js` (406.92 kB)
  - Built in 193ms.
