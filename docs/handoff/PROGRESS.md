# KAPPAK UI — Apple Glass Female Hero V2 Progress

Trạng thái thực hiện các nhiệm vụ theo `AGENT_TASK.md` và `ACCEPTANCE_CHECKLIST.md`.

## Bảng Tiến Độ Checkpoint

| # | Nhiệm vụ | Trạng thái | Ghi chú / Bằng chứng |
|---|---|---|---|
| 1 | Audit frontend hiện tại | **DONE** | Stack: React 19 + Vite 8.3, Vanilla CSS, không Tailwind/CSS Modules. Báo cáo chi tiết đã duyệt. |
| 2 | Thu sidebar thành icon rail | **DONE** | Component `IconRail.jsx` 74px Apple Glass, window dots, 7 icon chức năng, Help/Theme/Settings/Logo. |
| 3 | Làm topbar giống tỷ lệ target | **DONE** | Component `Topbar.jsx` 72px, Search Pill lớn (Ctrl + K), `• AI Sẵn sàng ˇ`, `✦ Ask KAPPAK`, Bell, Avatar VK. |
| 4 | Tạo hero với female creator visual | **DONE** | Component `HeroSection.jsx`, visual nữ creator tự nhiên ngồi laptop, headline gradient blue, quote nổi, handwritten script. |
| 5 | Tạo module strip 6 card | **DONE** | Component `ModuleStrip.jsx`: Downloader (blue), Data Studio (mint), Auto Video (violet), Auto Dub (cyan), Social (pink), Today (amber). Không có AI Agent card. |
| 6 | Tạo Recent Projects section | **DONE** | Component `RecentProjectsSection.jsx` (~52% width), 3 video card thumbnail có duration, metadata và menu. |
| 7 | Tạo Continue Work section | **DONE** | Component `ContinueWorkSection.jsx` (~24% width), empty state chuẩn + nút pill `+ Tạo dự án mới`. |
| 8 | Tạo AI Suggestion section | **DONE** | Component `AISuggestionSection.jsx` (~24% width), thẻ pastel gradient, nút `Dùng thử ngay →` mở Ask KAPPAK. |
| 9 | Tạo Ask KAPPAK panel shell | **DONE** | Component `AskKappakDrawer.jsx` (410px), slide-over từ phải, backdrop blur 26px, quick chips và chat box. |
| 10 | Giữ backend/Core Phase 0 nguyên vẹn | **DONE** | Không sửa ToolVideo, Browser Extension, SQLite hay backend Python. Điều hướng sang Auto Dub Studio trơn tru. |
| 11 | Chạy build/test | **DONE** | `npm run build` PASS (284ms); `pytest` 20/20 test cases PASS (100%). |
## Bảng Tiến Độ Repo Cleanup (Branch: chore/repo-cleanup)

| Bước | Nhiệm vụ | Trạng thái | Commit / Ghi chú chi tiết |
|---|---|---|---|
| **BƯỚC 0** | An toàn trước: Tạo branch `chore/repo-cleanup` và kiểm tra working tree | **DONE** | Đã tạo branch riêng `chore/repo-cleanup`, working tree sạch sẽ trước khi thao tác. |
| **BƯỚC 1** | Audit 64 file/folder & Lập `CLEANUP_PLAN.md` | **DONE** | Báo cáo chi tiết 6 nhóm phân loại, bảng map cũ -> mới; User đã duyệt plan. |
| **BƯỚC 2** | Cập nhật `.gitignore` và dọn cache/log | **DONE** | Commit `8f3288a`: Thêm quy tắc loại trừ `__pycache__/`, `*.pyc`, `workspace/cache/`, `.venv/`, `*.log`. |
| **BƯỚC 3.1** | Di chuyển Specs sang `docs/specs/` | **DONE** | Commit `ea7488d`: Chuyển 7 file spec, reset, master prompt vào `docs/specs/`. Hợp nhất `background.png` vào `docs/design_specs/`. |
| **BƯỚC 3.2** | Di chuyển Screenshots sang `docs/screenshots/` | **DONE** | Commit `87d17b9`: Gom 12 file png ở root + toàn bộ thư mục `ui_screenshots/` (`before/`, `dark/`, `wide_1920x1080/`) vào `docs/screenshots/`. |
| **BƯỚC 3.3** | Gom log Multi-Agent cũ sang `docs/handoff/archive/` | **DONE** | Commit `8f2c74f`: Chuyển `sentinel/`, `teamwork_preview_*/`, `ORIGINAL_REQUEST.md` sang `docs/handoff/archive/`. Giữ nguyên `.agent/skills/` và `.agents/skills/`. |
| **BƯỚC 3.4** | Di chuyển Batch scripts sang `scripts/` | **DONE** | Commit `d1ab671`: Chuyển `run_app.bat`, `run_kappak.bat`, `Chạy_VK_Dub_Studio.bat`, `reload_extension.bat` sang `scripts/`. Tạo thin forwarding wrappers tại root để tương thích ngược. |
| **BƯỚC 3.5** | Di chuyển Releases zip sang `archive/releases/` | **DONE** | Commit `7648d0c`: Chuyển 4 file zip vào `archive/releases/`, loại duplicate `latest.json` ở root và chuyển `test_icon.ico` vào `resources/`. |
| **BƯỚC 4** | Sửa references bị vỡ & kiểm thử tích hợp | **DONE** | Commit `53615c2`: Cập nhật `tests/test_manifest_and_packaging.py`, `tests/test_adversarial_challenger.py`, `scripts/export_all_ui_screenshots.py`, `frontend/`, `README.md`. |
| **BƯỚC 5** | Kiểm tra hồi quy, build frontend & nghiệm thu | **DONE** | `npm run build` PASS (449ms); `pytest` 833 passed; `reload_extension.bat` chạy thành công đăng ký Native Host. |

## Bảng Kết Quả Gap Audit Mục 7.1 (Chống Báo Cáo Khống - Ngày 19/09/2026)

| Mục theo PROJECT_OVERVIEW.md | Trạng thái cũ | Trạng thái sau Audit | Lý do hạ / Bằng chứng kiểm tra thực tế |
|---|---|---|---|
| **1. Pipeline 5 bước Auto-Dub** | DONE [x] | **PARTIAL** | - Whisper STT & Edge TTS chạy thực tế 100% trên `sample.mp4`.<br/>- CapCut Export chạy thật 100%, xuất draft hợp lệ tại `%LOCALAPPDATA%\CapCut\...\VKDub 20260919-064656-BAE65B17` (có video xóa chữ, master-voice.mp3, draft_content.json).<br/>- **GAP:** Bước Dịch thuật (ChatGPT/Gemini) & Vbee TTS chưa tự động end-to-end độc lập do chưa có Gemini API Key và tab ChatGPT/Vbee chưa đăng nhập (pipeline tự động fallback sang kịch bản gốc để sửa tay). |
| **2. Browser Bridge (Native Host + Extension)** | DONE [x] | **OPERATIONAL (Chờ tab)** | - Native Host & Local Agent kết nối TCP cổng 49814 thành công (PID 37112 <-> PID 29756).<br/>- API `/api/bridge/status` trả về `{"connected": true, "chatgpt": false, "vbee": false}`.<br/>- Đã chứng minh tự động reconnect khi Local Agent restart.<br/>- **GAP:** Trạng thái tab ChatGPT và Vbee đang là `false` do người dùng chưa mở/đăng nhập tab trong trình duyệt. |
| **3. Web Studio UI Apple Glass V2** | DONE [x] | **PENDING (UI Shell Only)** | - HomeView đạt 100% bố cục và thẩm mỹ Apple Glass Female Hero V2, build Vite pass.<br/>- **GAP 1:** `RecentProjectsSection` đang dùng danh sách **mock hardcode** (`SAMPLE_PROJECTS`), chưa nối API thật từ database.<br/>- **GAP 2:** 5/6 module cards khi click (Downloader, Data Studio, Auto Video, Social, Today) chỉ hiển thị **màn hình placeholder** ("Tính năng đang được kích hoạt..."), chưa có view chức năng thật trên Web. |
| **4. Universal Downloader (Phase 1)** | DONE [x] | **PENDING (Thiếu Dedup & Web UI)** | - `yt-dlp` tải video và lưu SQLite hoạt động trên desktop core.<br/>- **GAP 1 (Trọng yếu):** Chưa có logic kiểm tra `SELECT * FROM assets WHERE sha256_hash = ?` để phát hiện và chặn tải trùng (mới chỉ tính SHA-256 rồi lưu record mới với UUID mới).<br/>- **GAP 2:** Chưa có UI Downloader trên Web Studio (mới chỉ có placeholder). |
| **5. Cấu trúc Repository chuẩn hóa** | DONE [x] | **DONE (100%)** | - Đã audit 64 file, dọn dẹp phân loại tách bạch `docs/`, `scripts/`, `archive/releases/`, `tests/`, `src/`.<br/>- `.gitignore` loại trừ hoàn toàn rác cache/log. 833 tests pass. Forwarding launchers hoạt động chuẩn. |


