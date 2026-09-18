# UI Information Architecture Cleanup Plan — VK Dub Studio

## 1. Executive Summary & Design Principles

VK Dub Studio is functionally rich but currently suffers from **information architecture overload**: controls from all 5 workflow stages, technical diagnostics, browser connection statuses, and logs are displayed concurrently in a single monolithic left panel.

### Core Architecture Rule
> **At any moment, the user must primarily see:**
> 1. **One workflow state** (Left Stepper)
> 2. **One video preview** (Center Canvas & Timeline)
> 3. **One contextual task panel** (Right Contextual Stack)

**Visual Identity Constraints:**
- Retain current dark theme (`#0d1117`, `#161b22`, `#21262d`, `#0f141e`)
- Retain typography (Consolas for timecodes, Segoe UI / system sans)
- Retain teal/green accent (`#72d7c1`, `#238636`, `#3fb950`, `#34d399`)
- Retain current video player & interactive canvas overlay
- Retain stable 3-column desktop layout

---

## 2. Inventory of Existing UI Widgets by Layout Area

### A. Current Left Sidebar (`LeftConfigPanel`)
1. **Header & Meta:**
   - App title: `label("VK Dub Studio", "heading")`
   - Version & author: `label("by vanhkhuc.dev • v2.1")`
   - Settings button: `QPushButton("⚙ Cài đặt")`
   - Credit banner: `QLabel(APP_CREDIT)`
   - Divider line: `QFrame(HLine)`
2. **Cầu Nối Trình Duyệt (`BrowserBridgeWidget`):**
   - Title: `QLabel("CẦU NỐI TRÌNH DUYỆT (H6 BRIDGE)")`
   - Refresh button: `QPushButton("🔄 Làm mới")`
   - Edge connection status: `QLabel(self.lbl_browser)`
   - ChatGPT auth status: `QLabel(self.lbl_chatgpt)`
   - Vbee auth status: `QLabel(self.lbl_vbee)`
   - Open browser button: `QPushButton("🌐 Mở Microsoft Edge")`
3. **Step 01 Source Controls:**
   - Section header: `label("01 NGUỒN VIDEO (SOURCE)", "eyebrow")`
   - Import video button: `QPushButton("📂 BƯỚC 1: CHỌN VIDEO")` (`self.import_button`)
   - Video path / info label: `QLabel(self.video_info)` (`self.video_path`)
   - Save project button: `QPushButton("💾 Lưu")` (`self.save_button`)
   - Load project button: `QPushButton("📂 Mở")` (`self.load_button`)
   - Output directory button: `QPushButton("📁")` (`self.output_button`)
   - Output directory label: `QLabel(self.output_path)`
4. **Step 02 Voice Controls:**
   - Section header: `label("02 CẤU HÌNH GIỌNG ĐỌC (VOICE)", "eyebrow")`
   - Voice dropdown: `QComboBox(self.voice_combo)`
   - Speed dropdown: `QComboBox(self.speed_combo)`
   - Test listen button: `QPushButton("▶ Nghe thử")` (`self.listen_test_button`)
5. **Step 03 Blur Mask Controls:**
   - Section header: `label("03 KHUNG CHE MỜ (BLUR REGIONS)", "eyebrow")`
   - Mask toggle button: `QPushButton("▣ Bật / Chỉnh Khung Che Mờ")` (`self.btn_toggle_mask`)
6. **Step 04 Automatic Processing Controls (`Step4PipelineWidget`):**
   - Header title: `QLabel("BƯỚC 4: XỬ LÝ TỰ ĐỘNG (END-TO-END)")`
   - Overall badge: `QLabel(self.overall_badge)`
   - Substep 4.1 row: `SubstepRowWidget` (Title, duration, status, progress, message, artifact link, retry)
   - Substep 4.2 row: `SubstepRowWidget`
   - Substep 4.3 row: `SubstepRowWidget`
   - Substep 4.4 row: `SubstepRowWidget`
   - Primary run button: `QPushButton("⚡ BƯỚC 4: BẮT ĐẦU XỬ LÝ TOÀN BỘ")` (`self.btn_primary`)
   - Cancel button: `QPushButton("⏹ Dừng")` (`self.btn_cancel`)
   - View log button: `QPushButton("📄 Xem log xử lý")` (`self.btn_view_log`)
7. **Step 05 Review & Export Controls:**
   - Section header: `label("05 DUYỆT & XUẤT (REVIEW & EXPORT)", "eyebrow")`
   - Review status label: `QLabel(self.lbl_review_status)`
   - Approve button: `QPushButton("✔ BƯỚC 5: CHỐT KỊCH BẢN (DUYỆT)")` (`self.btn_approve_script`)
   - CapCut draft root label: `QLabel(self.capcut_dest_lbl)`
   - Change CapCut folder button: `QPushButton("Đổi…")` (`self.btn_capcut_folder`)
8. **Primary CTA & Pipeline Status Section:**
   - Eyebrow: `label("QUY TRÌNH & HÀNH ĐỘNG", "eyebrow")`
   - Process CTA button: `QPushButton("🚀 BẮT ĐẦU XỬ LÝ")` (`self.process_button`)
   - Stop button: `QPushButton("⏹ DỪNG")` (`self.stop_button`)
   - Job progress: `QProgressBar(self.job_progress)`
   - 6-Stage status box: `self.status_box` (`status_video`, `status_stt`, `status_trans`, `status_review`, `status_voice`, `status_export`)
9. **Export Result Actions:**
   - Export video button: `QPushButton("🎞 XUẤT VIDEO")` (`self.export_video_button`)
   - Export CapCut button: `QPushButton("🎬 XUẤT CAPCUT")` (`self.export_capcut_button`)
   - Open CapCut app: `QPushButton("MỞ CAPCUT")` (`self.open_capcut_button`)
   - Open CapCut project folder: `QPushButton("MỞ PROJECT")` (`self.open_capcut_folder_button`)
10. **Activity Log:**
    - Log header: `QLabel("● NHẬT KÝ ĐANG CHẠY")` (`self.activity_header`)
    - Log text edit: `QPlainTextEdit(self.logs)`
11. **Legacy / Hidden Tech Widgets (for backward compatibility):**
    - `ffmpeg_status`, `ffprobe_status`, `detect_button`, `language_voice`, `model_selector`, `device_selector`, `model_status`, `download_button`, `reuse_cache`, `translation_cache`, `api_button`, `translate_button`.

### B. Current Center Panel (`VideoPreview`)
1. **Header:** `label("Xem trước video", "heading")`
2. **Video Canvas:** `VideoCanvas(self.video)` (with subtitle rendering & interactive mask drag/resize)
3. **Empty hint:** `QLabel("Tải video MP4 để bắt đầu...")`
4. **Timeline & Seek Bar:** `QSlider(self.seek)`
5. **Primary Controls Row:**
   - Play/pause: `QPushButton("▶ Phát")` (`self.play_button`)
   - Time label: `QLabel("00:00 / 00:00")` (`self.time_label`)
   - Volume icon: `QLabel("🔊")`
   - Volume slider: `QSlider(self.volume)`
6. **Secondary Actions Row:**
   - Mask button: `QPushButton("▣ Khung dịch / Xóa chữ")` (`self.btn_mask`)
   - Blur button: `QPushButton("🌫 Làm mờ chữ")` (`self.btn_blur`)
   - Subtitle button: `QPushButton("✥ Vị trí & kiểu Sub")` (`self.btn_subtitle`)
   - Subtitle box toggle: `QPushButton("▣ Khung Sub")` (`self.btn_sub_box`)
   - Preview voice button: `QPushButton("Preview Voice")` (`self.btn_preview_voice`)
   - More menu: `QToolButton("⋯")` (`self.btn_more`) with Video Info and Capture Frame actions.
7. **Metadata label:** `QLabel(self.metadata_label)`

### C. Current Right Panel (`ScriptReviewPanel`)
1. **Header:**
   - Title: `label("KỊCH BẢN", "heading")`
   - Summary: `QLabel("0 câu • 0 lỗi • 0 cảnh báo")` (`self.summary`)
   - Review Badge: `QLabel("CHƯA DUYỆT")` (`self.badge`)
   - Stage info: `QLabel(self.stage)`
2. **Toolbar:**
   - 14 Action buttons: `add`, `delete`, `split`, `merge_previous`, `merge_next`, `undo`, `redo`, `search`, `load`, `save`, `import_vbee`, `save_source`, `validate`, `prepare`
   - Overflow menu: `QToolButton("Thêm ⋯")` (`self.more_button`)
3. **Search / Replace Bar:**
   - `find_text`, `replace_text`, `find_next`, `replace_all`
4. **Placeholder:** `QLabel(self.placeholder)`
5. **Script List:** `ScriptList(self.rows)` with row cards
6. **Bottom Approval Box:**
   - Checkbox: `QCheckBox("Tôi đã kiểm tra toàn bộ kịch bản")` (`self.review_checkbox`)
   - Approve CTA: `QPushButton("✓ DUYỆT KỊCH BẢN & TẠO VOICE")` (`self.approve_button`)
   - Voice note: `QLabel(self.voice_note)`
   - Export button: `QPushButton("XUẤT VIDEO")` (`self.export_button`)

---

## 3. Target Restructured Architecture

### 3.1 Global Top Bar (`TopBarWidget`)
- **Branding:** `VK Dub Studio` · `by vanhkhuc.dev`
- **Project filename badge:** `📄 {project_name}` with dirty asterisk `*`
- **Browser Connection Pills:**
  - `● Edge` (Green = Connected, Yellow = Waiting)
  - `● ChatGPT` (Green = Logged in, Red/Yellow = Not logged in)
  - `● Vbee` (Green = Logged in, Red/Yellow = Not logged in)
- **Project Actions:** `💾 Lưu`, `📂 Mở`
- **Settings:** `⚙ Cài đặt`

### 3.2 Left Sidebar (`WorkflowStepperWidget`) — Stepper ONLY
Contains **ONLY** the 5 stages with active indicators and real-time short summaries:
1. `01 Source` (e.g., `✓ 0906(1).mp4` or `○ Chưa chọn video`)
2. `02 Voice` (e.g., `✓ Ngọc Huyền · 1.1x`)
3. `03 Blur Regions` (e.g., `✓ 1 vùng che mờ` or `○ Chưa tạo`)
4. `04 Automatic Processing` (e.g., `● Đang chạy` or `✓ Hoàn tất (4/4)`)
5. `05 Review & Export` (e.g., `○ Chờ duyệt` or `✓ Đã duyệt`)

*No logs, no voice sliders, no automation substeps, and no export buttons in the sidebar.*
Clicking any step item immediately switches the Right Contextual Panel.

### 3.3 Center Area (`VideoPreview`) — Clean Video & Timeline
- Dominant video canvas (`VideoCanvas`)
- Timeline seek bar (`QSlider`)
- Under-video minimal controls:
  - Play/Pause (`▶ Phát` / `⏸ Tạm dừng`)
  - Time code (`00:00 / 00:00`)
  - Volume slider
- Secondary tools row:
  - `✥ Phụ đề` (Opens Subtitle Style Dialog)
  - `🌫 Làm mờ` (Switches or adds blur region in Step 3)
  - `🎵 Nghe Voice` (Quick test audio)
  - `⋯` More menu (Khung nền Sub, Thông tin video, Chụp ảnh khung hình)

### 3.4 Right Panel (`QStackedWidget`) — Current Step Context ONLY
Contains 5 dedicated contextual pages:

#### Page 0: Step 01 — Source Panel (`Step1SourcePanel`)
- Douyin / Video URL input field + `[ 📥 Tải video ]`
- Divider `— HOẶC —`
- `[ 📂 CHỌN VIDEO TỪ MÁY (MP4) ]`
- Selected Video Metadata Card:
  - Filename, path, file size
  - Resolution, Framerate, Duration
  - Audio status
- Navigation CTA: `[ Tiếp tục: Chọn giọng đọc → ]`

#### Page 1: Step 02 — Voice Panel (`Step2VoicePanel`)
- Voice selector: Default `Ngọc Huyền (HN - Nữ)`
- Speed selector: Default `1.1x` (options: 0.8x, 0.9x, 1.0x, 1.1x, 1.2x, 1.3x)
- Action: `[ ▶ Nghe thử giọng đọc ]`
- Settings link: `Cài đặt giọng đọc khác trong ⚙ Cài đặt`
- Navigation: `[ ← Quay lại ]` and `[ Tiếp tục: Khung che mờ → ]`

#### Page 2: Step 03 — Blur Inspector (`Step3BlurPanel`)
- Region list: List of configured blur regions
- Actions: `[ ➕ Thêm vùng làm mờ ]`
- Selected Region Inspector:
  - Coordinates: X, Y, Width, Height (live sync with canvas rectangle drag/resize)
  - Blur strength slider (5px – 50px)
  - Action: `[ 🗑 Xóa vùng này ]`
- Live video interaction: User can drag and resize directly on canvas
- Navigation: `[ ← Quay lại ]` and `[ Tiếp tục: Xử lý tự động → ]`

#### Page 3: Step 04 — Automation Console (`Step4AutomationPanel`)
- Overall progress bar & status badge
- 4 Substeps:
  - `4.1 Transcription` (Whisper: segment count, duration, status)
  - `4.2 ChatGPT Translation` (contextual translation, SRT, duration, status)
  - `4.3 Script / Timeline Validation` (timeline sync check, status)
  - `4.4 Vbee Voice Generation` (Vbee master audio generation, status)
- State per step: PENDING, RUNNING, SUCCESS, FAILED
- Actions:
  - `[ ⚡ BẮT ĐẦU XỬ LÝ TOÀN BỘ ]`
  - `[ ⏹ Dừng ]`
- Error handling:
  - On failure, show: `FAILED`, human-readable explanation, and `[ 🔄 Thử lại ]`
  - Raw exception / traceback tucked inside expandable `▶ Chi tiết kỹ thuật (Technical details)`
- Navigation: `[ Tiếp tục: Duyệt kịch bản & Xuất → ]` (enabled when pipeline completes)

#### Page 4: Step 05 — Review & Export (`Step5ReviewExportPanel`)
- Streamlined Script Editor:
  - Header: `KỊCH BẢN` · `{N} câu`
  - Header tools: `🔍 Tìm kiếm`, `➕ Thêm câu`, `⋯ Thao tác khác` (Import SRT, Export SRT, Validate SRT, Regenerate Voice)
  - Search / Replace bar
  - Script cards list (reduced borders, clear timecode, original, translation, warning badge, play button)
- Approval Gate:
  - `☑ Tôi đã kiểm tra toàn bộ kịch bản`
  - `[ ✔ CHỐT KỊCH BẢN (DUYỆT) ]`
- Primary Export Section (at the end of Step 05):
  - `[ 🎞 XUẤT VIDEO MP4 ]`
  - `[ 🎬 XUẤT DỰ ÁN CAPCUT ]`
  - CapCut draft root status + `Đổi...` button

### 3.5 Bottom Drawer (`DiagnosticsDrawer`)
- Collapsed by default at bottom of window
- Toggle button: `[ 📋 Logs & Diagnostics ▸ ]`
- When expanded (e.g. 130px height):
  - Log console (`QPlainTextEdit`) with auto-scroll
  - Quick buttons: `Xóa log`, `Sao chép`, `Mở log chi tiết (F12)`

---

## 4. Signal & Controller Compatibility Strategy
To ensure 100% compatibility with `tests/test_ui.py` and existing controllers without changing backend logic:
- `MainWindow.left` will be maintained as an access facade / delegate object exposing:
  - `import_button`, `output_button`, `save_button`, `load_button`, `detect_button`
  - `voice_combo`, `speed_combo`, `listen_test_button`
  - `btn_toggle_mask`
  - `step4_pipeline` (delegating to the Automation Console)
  - `lbl_review_status`, `btn_approve_script`
  - `process_button`, `stop_button`, `job_progress`, `status_box`
  - `export_video_button`, `export_capcut_button`, `open_capcut_button`, `open_capcut_folder_button`
  - `logs`, `credit_label`, `ffprobe_status`, `ffmpeg_status`
  - All signals: `settings_requested`, `vbee_voice_requested`, `pipeline_start_requested`, etc.
- This guarantees all existing tests (`pytest tests/test_ui.py`) and pipeline bindings remain fully functional.
