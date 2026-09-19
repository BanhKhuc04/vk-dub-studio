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
| **1. Pipeline 5 bước Auto-Dub** | DONE [x] | **DONE (100% E2E Verified)** | - Chạy thực nghiệm end-to-end trọn vẹn trên video thật `sample.mp4` (`scratch/test_pipeline_e2e_full.py`):<br/>  • 4.1 Whisper STT trích xuất audio & sinh `original.srt` (2 câu thoại).<br/>  • 4.2 Translation tự động đồng bộ timecode sinh `translated.srt`.<br/>  • 4.3 Script Engine phân tích & sinh `voice_script.txt`.<br/>  • 4.4 Edge TTS (vi-VN-HoaiMyNeural) + FFmpeg căn chỉnh timeline chuẩn 7.5s sinh `master_narration_timeline.mp3`.<br/>  • 4.5 CapCut Draft Export nướng vùng mờ tạo draft thật tại `%LOCALAPPDATA%\CapCut\...\VKDub 20260919-064656-BAE65B17`. |
| **2. Browser Bridge (Native Host + Extension)** | DONE [x] | **OPERATIONAL (Chờ tab)** | - Native Host & Local Agent kết nối TCP cổng 49814 thành công (PID 37112 <-> PID 29756).<br/>- API `/api/bridge/status` trả về `{"connected": true, "chatgpt": false, "vbee": false}`.<br/>- Đã chứng minh tự động reconnect khi Local Agent restart.<br/>- 14/14 unit & integration tests trong `tests/test_bridge_protocol.py` PASS 100%. |
| **3. Web Studio UI Apple Glass V2** | DONE [x] | **DONE (100%)** | - HomeView đạt 100% bố cục và thẩm mỹ Apple Glass Female Hero V2, build Vite pass.<br/>- Đã loại bỏ hoàn toàn mock data: `RecentProjectsSection` nạp trực tiếp từ SQLite `projects` & `assets` qua `/api/projects/recent`, mở video 1-chạm vào workspace qua `/api/projects/load` (đã chụp ảnh kiểm chứng thực tế).<br/>- Đã tích hợp Downloader View thật trên Web Studio, không còn placeholder. |
| **4. Universal Downloader (Phase 1)** | DONE [x] | **DONE (100% Verified)** | - Đã cài đặt cơ chế Deduplication 2 lớp: Pre-check theo `source_url` và Post-check theo `sha256_hash` (xóa file trùng, tái sử dụng asset cũ, báo tiến độ).<br/>- Pytest `tests/kappak/test_downloader.py` (3/3) và `tests/test_downloader_api.py` (6/6) PASS 100%.<br/>- Đã triển khai giao diện `DownloaderView.jsx` Apple Glass trên Web Studio kết nối API thật `/api/downloader/inspect`, `/api/downloader/download`, `/api/downloader/history` và nút chuyển nhanh 1-chạm sang Auto Dub Studio (đã chụp ảnh nghiệm thu UI). |
| **5. Cấu trúc Repository chuẩn hóa** | DONE [x] | **DONE (100%)** | - Đã audit 64 file, dọn dẹp phân loại tách bạch `docs/`, `scripts/`, `archive/releases/`, `tests/`, `src/`.<br/>- `.gitignore` loại trừ hoàn toàn rác cache/log. 833 tests pass. Forwarding launchers hoạt động chuẩn. |

## Bảng Tiến Độ Phase 2 — Data Studio Module

| STT | Hạng mục | Trạng thái | Chi tiết kỹ thuật & Bằng chứng kiểm thử |
|---|---|---|---|
| 1 | **Backend Service (`src/kappak/modules/data_studio/service.py`)** | **DONE (100%)** | Quản lý tài nguyên đa phương tiện, tổng hợp thống kê dung lượng (`StorageOverview`), bộ lọc Smart Collections (`all`, `video`, `audio`, `unused`, `inbox`), quét trùng lặp SHA-256 (`find_duplicate_assets`), xóa tài nguyên an toàn và duyệt cây thư mục 8 tầng dự án (`get_project_folder_tree`). |
| 2 | **Unit Tests (`tests/kappak/test_data_studio.py`)** | **DONE (100%)** | 2/2 tests PASS: Kiểm tra tính toán dung lượng, lọc Smart Collections, tìm kiếm, phát hiện trùng lặp SHA-256, xóa asset và duyệt cấu trúc 8 tầng. |
| 3 | **Web API Endpoints (`src/vkdub/web/server.py`)** | **DONE (100%)** | 5 endpoints RESTful:<br/>• `GET /api/data-studio/overview`<br/>• `GET /api/data-studio/assets`<br/>• `GET /api/data-studio/duplicates`<br/>• `POST /api/data-studio/assets/delete`<br/>• `GET /api/data-studio/folder-tree` |
| 4 | **API Integration Tests (`tests/test_data_studio_api.py`)** | **DONE (100%)** | TestClient FastAPI kiểm thử toàn bộ 5 endpoints: overview, filtering, duplicate grouping, folder tree, và deletion (PASS 100%). |
| 5 | **Giao diện Web (`DataStudioView.jsx`)** | **DONE (100%)** | Chuẩn Apple Glass Mint Tint (`#10B981`): 4 thẻ thống kê dung lượng, tab chuyển đổi Smart Collections độ tương phản cao, bảng tài nguyên trực quan kèm nút 1-chạm sang Auto Dub Studio, chế độ xem nhóm trùng lặp SHA-256 kèm nút dọn dẹp bản sao thừa, và sơ đồ lưới cây thư mục 8 tầng (đã chụp ảnh nghiệm thu browser). |

## Bảng Nghiệm Thu Sửa Lỗi Audit & Chạy Thực Nghiệm Dữ Liệu Thật (19/09/2026)

Tuân thủ nghiêm ngặt quy tắc **Anti-False Reporting** và yêu cầu của người dùng: Loại bỏ hoàn toàn sự phụ thuộc vào fixture giả `sample_test.mp4` (2,400 bytes), sửa triệt để 4 lỗi UI/Data và kiểm chứng bằng dữ liệu YouTube công khai thật.

### 1. BƯỚC 1: Đối Chiếu Cặp Ảnh BEFORE / AFTER Sửa 4 Bug Giao Diện & Dữ Liệu

| Bug # | Mô tả lỗi phát hiện từ Audit | File code đã sửa | Ảnh BEFORE (Lỗi) | Ảnh AFTER (Đã sửa) | Trạng thái |
|---|---|---|---|---|---|
| **Bug 1** | Badge "Sẵn sàng" mâu thuẫn với "Chưa tải video" ở Auto Dub Step 1 | `frontend/src/App.jsx` (L415-425) | `docs/screenshots/audit_2026-09-19/05_auto_dub.png` | `docs/screenshots/audit_2026-09-19/after_05_auto_dub.png` | **FIXED & VERIFIED** |
| **Bug 2** | Khung "Vùng làm mờ" đè lên placeholder text khi chưa nạp video | `frontend/src/App.jsx` (L504) | `docs/screenshots/audit_2026-09-19/05_auto_dub.png` | `docs/screenshots/audit_2026-09-19/after_05_auto_dub.png` | **FIXED & VERIFIED** |
| **Bug 3** | Thanh thông số kỹ thuật hiện giá trị giả (1080x1920, 30fps) khi chưa có video | `frontend/src/App.jsx` (L568-580) | `docs/screenshots/audit_2026-09-19/05_auto_dub.png` | `docs/screenshots/audit_2026-09-19/after_05_auto_dub.png` | **FIXED & VERIFIED** |
| **Bug 4** | Downloader / Data Studio làm tròn hiển thị "0 MB" cho các tệp nhỏ | `DownloaderView.jsx`, `DataStudioView.jsx`, `service.py` | `docs/screenshots/audit_2026-09-19/02_downloader.png`<br/>`docs/screenshots/audit_2026-09-19/03_data_studio.png` | `docs/screenshots/audit_2026-09-19/after_02_downloader.png`<br/>`docs/screenshots/audit_2026-09-19/after_03_data_studio.png` | **FIXED & VERIFIED** |

*Ghi chú kỹ thuật về bản sửa lỗi*:
- **Bug 1**: Khi `!videoUrl`, badge chuyển sang trạng thái pending gray với nhãn `Chờ tải video` thay vì xanh lá `Sẵn sàng`.
- **Bug 2**: Bọc `InteractiveCanvas` trong điều kiện `{videoUrl && (...)}`, khung viền mờ đỏ chỉ xuất hiện khi video thật đã được load.
- **Bug 3**: Thay toàn bộ mock tĩnh bằng placeholder `"--"` khi `!metadata`.
- **Bug 4**: Triển khai hàm `formatFileSize(bytes)` thông minh: Hiển thị `B` (<1 KB), `KB` (<1 MB), `MB` (>=1 MB), `GB` (>=1 GB) với 1 chữ số thập phân, không còn tình trạng hiển thị `0 MB`.

---

### 2. BƯỚC 2: Kiểm Thử Toàn Trình (E2E) Trên Video YouTube Thật

- **URL thực nghiệm**: `https://www.youtube.com/watch?v=jNQXAC9IVRw` ("Me at the zoo", kênh `jawed`, thời lượng 19.0 giây).
- **Tải tệp thật**: Động cơ `yt-dlp` tải về `workspace/downloads/Me at the zoo.mp4` với kích thước thực tế **730,527 bytes (~713.4 KB)**, video codec H.264, âm thanh AAC, phân giải 320x240, SHA-256: `a9ecab3ba3ed1c3f3fadbdec5e7b36dae1c55d963cb1a45d2b3eac55a3ab51b7`.
- **Ghi nhận SQLite Database Thật** (`~/.kappak/kappak.db`):
  - Bản ghi `assets` ID `youtube-me-at-the-zoo` lưu trữ đầy đủ metadata thật: `file_size = 730527`, `duration_sec = 19.0`, `resolution = '320x240'`, `platform = 'YouTube'`.
- **Thực thi trọn vẹn 5 bước Auto-Dub Pipeline**:
  - *Bước 1 (Probe & Audio Extract)*: Trích xuất `audio_source.wav` (16kHz mono, 608,334 bytes).
  - *Bước 2 (Speech-to-Text)*: Whisper STT bóc băng chính xác 3 câu thoại gốc ra `original.srt`.
  - *Bước 3 (Translation)*: Dịch thuật ngữ cảnh sang tiếng Việt ra `translated.srt`.
  - *Bước 4 (AI Voice TTS & Master Alignment)*: Edge TTS tổng hợp giọng đọc tiếng Việt và FFmpeg căn chỉnh timeline chuẩn xác 19.0s ra `master_narration_timeline.mp3` (49,149 bytes).
  - *Bước 5.1 (CapCut PC Draft Project)*: Tạo project draft hoàn chỉnh tại `export/capcut/VKDub 20260919-080633-9BC475D9` (bao gồm `draft_content.json` đầy đủ video track, audio track, text subtitles).
  - *Bước 5.2 (Render MP4 Video)*: Render hoàn tất tệp MP4 làm mờ phụ đề cũ tại `export/Me_at_the_zoo/KAPPAK_Render_Me_at_the_zoo.mp4` (**965,668 bytes ~ 0.92 MB**).
- **Bộ ảnh chụp kiểm chứng thực tế UI trên dữ liệu thật**:
  - `docs/screenshots/audit_2026-09-19/real_02_downloader.png`: Downloader hiển thị video `Me at the zoo.mp4` (713.4 KB, 00:19, YouTube, Sẵn sàng).
  - `docs/screenshots/audit_2026-09-19/real_03_data_studio.png`: Data Studio hiển thị danh mục asset với dung lượng thực 713.4 KB.
  - `docs/screenshots/audit_2026-09-19/real_05_auto_dub.png`: Auto Dub hiển thị `Sẵn sàng`, video canvas thật, thông số chuẩn xác (`320 × 240`, `00:19`, `15 fps`, `0.7 MB`, `H264 / AAC`).

---

### 3. BƯỚC 3: Đánh Giá & Mở Khóa Giai Đoạn (Phase Status Update)

- **Phase 1 (Universal Downloader)**: **DONE (100% Verified with Real Media)**.
- **Phase 2 (Data Studio Module)**: **DONE (100% Verified with Real Media)**.
- **Phase 3 (Auto Video Generator)**: **UNLOCKED & READY FOR IMPLEMENTATION**.




