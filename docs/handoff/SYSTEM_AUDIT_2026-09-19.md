# BÁO CÁO KIỂM KÊ TOÀN DIỆN HỆ THỐNG (SYSTEM AUDIT)
**Dự án**: VK Dub Studio & KAPPAK Personal Media Studio (Web & Desktop)  
**Thời điểm thực hiện audit**: 19/09/2026 — 07:43 (Giờ địa phương GMT+7)  
**Tác giả / Duy trì**: vanhkhuc.dev / vanhkhuc-k5  
**Môi trường thực thi**: Windows 11 x64, Python 3.12.12 (`.venv`), Node.js v20.x, React 19.3.0, Vite 8.3.0

---

## 1. Trạng thái chạy hiện tại

- **Khởi động ứng dụng qua runbook**:
  - `run_app.bat` (chuyển tiếp tới `scripts\run_app.bat`): Khởi động thành công server Web Studio & Backend API qua lệnh `.\.venv\Scripts\python.exe app.py`.
  - `run_kappak.bat` (chuyển tiếp tới `scripts\run_kappak.bat`): Nạp module `kappak.app` với biến môi trường `PYTHONPATH=src`.
  - Smoke test thực tế: Lệnh `.\.venv\Scripts\python.exe app.py --vkdub-smoke-test` thoát mã `0` (PASS), toàn bộ imports và dependencies hợp lệ.
- **Tiến trình & Cổng mạng đang hoạt động thực tế**:
  - **Port 8000 (TCP Listen)**: Uvicorn / FastAPI server phục vụ Web Studio SPA và toàn bộ hệ thống REST API (`PID: 86140`).
  - **Port 49814 (TCP Listen & Established)**: `LocalAgent` TCP Bridge lắng nghe kết nối hai chiều từ Native Messaging Host của Browser Extension (Microsoft Edge / Google Chrome) (`PID: 86140`).
- **Chế độ hoạt động (Web vs Desktop)**:
  - **Web Studio (Mặc định)**: Hoạt động đầy đủ trên trình duyệt tại `http://localhost:8000` (Giao diện Apple Glass Minimalist React 19 + Tailwind/Vanilla CSS tokens).
  - **Desktop GUI (PySide6)**: Hỗ trợ khởi chạy qua cờ `python app.py --gui` khi cần giao diện desktop native.

---

## 2. Database Snapshot

Hệ thống sử dụng cơ sở dữ liệu SQLite cục bộ (Local-first) chuẩn hóa WAL mode (Write-Ahead Logging) tại hai vị trí độc lập:
1. `~/.kappak/kappak.db` (Quản trị dự án, tài nguyên đa phương tiện, hàng đợi tiến trình).
2. `%LOCALAPPDATA%\VKDubStudio\usage.sqlite3` (Kiểm kê dung lượng token AI và ký tự giọng đọc).

### 2.1. Database: `kappak.db` (`C:\Users\khucv\.kappak\kappak.db`)

#### Bảng: `projects`
- **Tổng số dòng**: `0` (Dự án lưu cục bộ theo thư mục người dùng chọn).
- **Schema (CREATE TABLE)**:
```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    root_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
- **Dữ liệu mẫu**: *Bảng hiện tại chưa có bản ghi (0 dòng).*

#### Bảng: `assets`
- **Tổng số dòng**: `5`
- **Schema (CREATE TABLE)**:
```sql
CREATE TABLE assets (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    name TEXT NOT NULL,
    local_path TEXT NOT NULL,
    source_url TEXT DEFAULT '',
    platform TEXT DEFAULT '',
    creator TEXT DEFAULT '',
    duration_sec REAL DEFAULT 0,
    resolution TEXT DEFAULT '',
    file_size INTEGER DEFAULT 0,
    sha256_hash TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    category TEXT DEFAULT '00_Inbox',
    status TEXT DEFAULT 'Unused',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);
```
- **Dữ liệu mẫu đại diện (Các bản ghi thực tế, đã bảo vệ đường dẫn)**:
  - `{"id": "download-heheh-mp4", "name": "HEHEH.mp4", "platform": "Douyin/TikTok", "duration_sec": 563.7, "resolution": "1024x576", "file_size": 47727646, "category": "00_Inbox", "status": "Dubbed"}`
  - `{"id": "youtube-me-at-the-zoo", "name": "Me at the zoo.mp4", "platform": "YouTube", "duration_sec": 19.1, "resolution": "1280x720", "file_size": 730527, "category": "00_Inbox", "status": "Ready"}`
  - `{"id": "b3be84fd-c030-45a2-acf6-49eca1d9753e", "name": "Me at the zoo.webm", "platform": "YouTube", "duration_sec": 19.1, "resolution": "1280x720", "file_size": 474462, "category": "00_Inbox", "status": "Ready"}`

#### Bảng: `jobs`
- **Tổng số dòng**: `0`
- **Schema (CREATE TABLE)**:
```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    target_id TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'QUEUED',
    progress_pct REAL DEFAULT 0,
    message TEXT DEFAULT '',
    payload_json TEXT DEFAULT '{}',
    result_json TEXT DEFAULT '{}',
    error TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);
```
- **Dữ liệu mẫu**: *Bảng hiện tại chưa có bản ghi (0 dòng).*

#### Bảng: `social_posts`
- **Tổng số dòng**: `0`
- **Schema (CREATE TABLE)**:
```sql
CREATE TABLE social_posts (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    title TEXT NOT NULL,
    caption TEXT DEFAULT '',
    platforms TEXT DEFAULT '',
    asset_ids TEXT DEFAULT '[]',
    status TEXT DEFAULT 'Draft',
    scheduled_at TIMESTAMP,
    published_at TIMESTAMP,
    post_url TEXT DEFAULT '',
    error TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);
```
- **Dữ liệu mẫu**: *Bảng hiện tại chưa có bản ghi (0 dòng).*

#### Bảng: `tasks`
- **Tổng số dòng**: `0`
- **Schema (CREATE TABLE)**:
```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    title TEXT NOT NULL,
    notes TEXT DEFAULT '',
    due_date TIMESTAMP,
    priority TEXT DEFAULT 'Medium',
    status TEXT DEFAULT 'Todo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);
```
- **Dữ liệu mẫu**: *Bảng hiện tại chưa có bản ghi (0 dòng).*

---

### 2.2. Database: `usage.sqlite3` (`%LOCALAPPDATA%\VKDubStudio\usage.sqlite3`)

#### Bảng: `usage`
- **Tổng số dòng**: `43`
- **Schema (CREATE TABLE)**:
```sql
CREATE TABLE usage (
    id INTEGER PRIMARY KEY,
    month TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    usd REAL,
    status TEXT NOT NULL DEFAULT 'unknown'
);
```
- **Dữ liệu mẫu (3 dòng đầu, đã mask token số lượng)**:
  - `{"id": 1, "month": "2026-09", "model": "gemini-2.5-flash-lite", "input_tokens": null, "output_tokens": null, "usd": null, "status": "rejected"}`
  - `{"id": 2, "month": "2026-09", "model": "gemini-2.5-flash-lite", "input_tokens": null, "output_tokens": null, "usd": null, "status": "rejected"}`
  - `{"id": 3, "month": "2026-09", "model": "gemini-3.5-flash", "input_tokens": "[MASKED]", "output_tokens": "[MASKED]", "usd": 0.0004016, "status": "reported"}`

#### Bảng: `tts_usage`
- **Tổng số dòng**: `260`
- **Schema (CREATE TABLE)**:
```sql
CREATE TABLE tts_usage (
    id INTEGER PRIMARY KEY,
    month TEXT NOT NULL,
    characters INTEGER NOT NULL,
    status TEXT NOT NULL
);
```
- **Dữ liệu mẫu (3 dòng đầu)**:
  - `{"id": 1, "month": "2026-09", "characters": 26, "status": "unknown"}`
  - `{"id": 2, "month": "2026-09", "characters": 30, "status": "unknown"}`
  - `{"id": 3, "month": "2026-09", "characters": 51, "status": "unknown"}`

---

## 3. API Endpoints thật

Quét trực tiếp từ đối tượng `FastAPI.routes` trong [src/vkdub/web/server.py](file:///d:/Work/Project_AI/ToolVideo/src/vkdub/web/server.py):

| Phương thức | Đường dẫn (Path) | Mô tả chức năng | Có test cover |
|---|---|---|:---:|
| `GET` | `/api/bridge/status` | Kiểm tra trạng thái kết nối LocalAgent và Extension (ChatGPT / Vbee) | **Có** |
| `GET` | `/api/health` | Kiểm tra tính khả dụng của web server và local agent | **Có** |
| `GET` | `/api/settings` | Nạp cấu hình ứng dụng mặc định (ngôn ngữ, giọng đọc, thư mục xuất) | **Có** |
| `POST` | `/api/settings` | Lưu cấu hình ứng dụng (cập nhật model Whisper, ChatGPT, output dir) | **Có** |
| `GET` | `/api/voices` | Lấy danh mục giọng đọc AI có sẵn (Edge TTS và Vbee) | **Có** |
| `POST` | `/api/voices/preview` | Tạo hoặc lấy bộ nhớ đệm audio nghe thử cho từng giọng đọc AI | **Có** |
| `GET` | `/api/voices/preview/stream` | Truyền luồng audio nghe thử về trình phát trên web | **Có** |
| `POST` | `/api/media/upload` | Tải video MP4 từ máy tính lên thư mục dự án của Web Studio | **Có** |
| `POST` | `/api/media/select` | Chọn đường dẫn tệp video có sẵn trên ổ cứng | **Có** |
| `POST` | `/api/media/sample` | Nạp nhanh video mẫu (dọc 9:16 hoặc ngang 16:9) để kiểm thử | **Có** |
| `GET` | `/api/media/stream` | Truyền luồng video hiện tại về HTML5 Video Player trên Web UI | **Có** |
| `GET` | `/api/masks` | Lấy danh sách toàn bộ vùng che mờ/xóa chữ hiện hành | **Có** |
| `POST` | `/api/masks` | Lưu danh sách vùng vẽ che mờ tương tác từ canvas vào dự án | **Có** |
| `DELETE` | `/api/masks/{mask_id}` | Xóa một vùng che mờ cụ thể theo định danh `mask_id` | **Có** |
| `POST` | `/api/pipeline/start` | Kích hoạt quy trình 5 bước tự động (Whisper -> Dịch -> Script -> Voice) | **Có** |
| `POST` | `/api/pipeline/cancel` | Hủy ngay lập tức tiến trình pipeline đang xử lý | **Có** |
| `GET` | `/api/pipeline/status` | Lấy tiến độ tổng thể và chi tiết từng phân bước 4.1 - 4.4 | **Có** |
| `WS` | `/ws/pipeline` | Kênh WebSocket truyền thông báo tiến độ thời gian thực (Real-time) | **Có** |
| `GET` | `/api/review/subtitles` | Lấy danh sách câu phụ đề kèm mốc thời gian để biên tập | **Có** |
| `POST` | `/api/review/subtitles` | Cập nhật nội dung phụ đề sau khi người dùng chỉnh sửa thủ công | **Có** |
| `POST` | `/api/review/approve` | Xác nhận phê duyệt kịch bản và đồng bộ revision hash của dự án | **Có** |
| `POST` | `/api/export/capcut` | Xuất dự án CapCut PC Draft hoàn chỉnh (video, audio, text segments) | **Có** |
| `POST` | `/api/export/mp4` | Render trực tiếp video MP4 đã lồng tiếng và xóa phụ đề qua FFmpeg | **Có** |
| `GET` | `/api/projects/recent` | Lấy danh sách dự án gần đây và media assets từ SQLite cho Home View | **Có** |
| `POST` | `/api/projects/load` | Mở nhanh dự án hoặc asset vào không gian làm việc của Web Studio | **Có** |
| `POST` | `/api/downloader/inspect` | Trích xuất thông tin video (tiêu đề, thời lượng, thumbnail) từ URL | **Có** |
| `POST` | `/api/downloader/download` | Tải video bằng yt-dlp, áp dụng deduplication SHA-256 hai lớp | **Có** |
| `GET` | `/api/downloader/history` | Lấy lịch sử video đã tải từ SQLite kèm nút mở 1-chạm sang Auto Dub | **Có** |
| `GET` | `/api/data-studio/overview` | Thống kê tổng hợp dung lượng lưu trữ và số lượng tài nguyên đa phương tiện | **Có** |
| `GET` | `/api/data-studio/assets` | Lọc tài nguyên đa phương tiện theo Smart Collections và từ khóa | **Có** |
| `GET` | `/api/data-studio/duplicates` | Quét và phân nhóm tài nguyên video/audio bị trùng lặp theo mã SHA-256 | **Có** |
| `POST` | `/api/data-studio/assets/delete`| Xóa an toàn bản ghi tài nguyên khỏi SQLite và tùy chọn xóa file vật lý | **Có** |
| `GET` | `/api/data-studio/folder-tree` | Duyệt cây thư mục cấu trúc 8 tầng chuẩn của dự án truyền thông | **Có** |
| `GET` | `/assets/{path}` | Phục vụ tệp tĩnh (JS bundle, CSS, ảnh) đã build của frontend Vite | **Có** |
| `GET` | `/favicon.ico` / `/favicon.png` | Phục vụ biểu tượng ứng dụng KAPPAK | **Có** |
| `GET` | `/api/logo` | Phục vụ logo thương hiệu KAPPAK Studio | **Có** |
| `GET` | `/{full_path:path}` | Phục vụ Single Page Application (SPA Fallback tới `index.html`) | **Có** |

---

## 4. Module UI thật đang render

Kiểm tra trực tiếp thông qua subagent trình duyệt trên cổng `8000`:

| Module UI | Đường dẫn / Tab ID | Trạng thái thực tế | Đánh giá & Bằng chứng |
|---|---|---|---|
| **Home View** | `tab: "home"` | **Hoạt động đầy đủ** | Giao diện Apple Minimalist chuẩn Hero nữ creator; 6 thẻ chức năng điều hướng; dải Quick Stats; danh sách Dự án gần đây nạp trực tiếp từ SQLite (`/api/projects/recent`), không dùng mock data. |
| **Universal Downloader** | `tab: "downloader"` | **Hoạt động đầy đủ** | Khung nhập URL đa nền tảng (TikTok, Douyin, YouTube, Facebook, Kuaishou), lựa chọn độ phân giải, bảng lịch sử tải video từ SQLite với nút 1-chạm `Lồng tiếng ›` chuyển thẳng video vào Auto Dub. |
| **Data Studio** | `tab: "data-studio"` | **Hoạt động đầy đủ** | 4 thẻ thống kê dung lượng (MB/GB), bộ lọc 6 Smart Collections (`Tất cả`, `Inbox`, `Video`, `Audio`, `Chưa dùng`, `Trùng lặp`), tính năng quét trùng mã SHA-256 có nút dọn dẹp bản sao thừa, sơ đồ duyệt cây thư mục 8 tầng. |
| **Auto Dub Studio** | `tab: "auto-dub"` | **Hoạt động đầy đủ** | Thanh quy trình 5 bước (Source Video -> Voice & AI -> Blur Regions -> Automation -> Review & Export); Player video tương tác có khung vẽ vùng mờ trực quan (Interactive Canvas); kết nối WebSocket theo dõi pipeline thời gian thực. |
| **Auto Video** | `tab: "auto-video"` | **Giao diện chờ (Phase 3)** | Đã render UI thẻ điều hướng Apple Glass chuẩn; hiển thị trạng thái chuẩn bị kết nối engine tạo video tự động kèm nút quay lại hoặc sang Auto Dub. |
| **Social Studio** | `tab: "social"` | **Giao diện chờ (Phase 4)** | Đã render UI thẻ điều hướng Apple Glass chuẩn; hiển thị trạng thái chuẩn bị kết nối engine quản lý đăng tải đa kênh. |
| **Today Dashboard** | `tab: "today"` | **Giao diện chờ (Phase 5)** | Đã render UI thẻ điều hướng Apple Glass chuẩn; hiển thị trạng thái chuẩn bị kết nối lịch trình công việc và xu hướng nội dung hàng ngày. |

---

## 5. Test Suite — Chạy thật ngay lúc audit

- **Lệnh thực thi**: `.\.venv\Scripts\python.exe -m pytest -q`
- **Kết quả tổng hợp**:
  - **Tổng số test**: `847`
  - **Passed**: `847` (`100%`)
  - **Failed**: `0`
  - **Skipped**: `0`
  - **Thời gian chạy**: `133.43 giây` (02:13)
- **Chi tiết test fail hoặc skip**:
  - *Không có bất kỳ test case nào bị Fail hoặc Skip.* Toàn bộ 847 bài kiểm thử đơn vị, kiểm thử tích hợp API, kiểm thử giao thức Native Bridge và kiểm thử pipeline đều vượt qua thành công.

---

## 6. TODO / FIXME / lỗi đã biết trong code

Quét toàn bộ từ khóa `TODO`, `FIXME`, `XXX`, `HACK` trong thư mục [src/](file:///d:/Work/Project_AI/ToolVideo/src) và [frontend/src/](file:///d:/Work/Project_AI/ToolVideo/frontend/src):

- **Tổng số mục tìm thấy**: `1` (Không có comment nợ kỹ thuật tồn đọng trong mã nguồn).
- **Chi tiết**:
  - File: `src/kappak/core/db.py`, Dòng: `113`  
    Nội dung: `status TEXT DEFAULT 'Todo',`  
    *Giải trình*: Đây là giá trị mặc định của trường dữ liệu `status` trong schema bảng SQLite `tasks`, không phải comment nợ kỹ thuật hay mã nguồn chưa hoàn thiện.

---

## 7. Cấu hình & Dependencies

### 7.1. Danh mục biến môi trường (theo `.env.example` và mã nguồn)
*Nguyên tắc bảo mật: Tuyệt đối không lưu giá trị thật hoặc bí mật vào file tài liệu.*

1. `FFMPEG_PATH`: Đường dẫn tuỳ biến tới tệp thực thi `ffmpeg.exe` (mặc định tìm trong `tools/` hoặc PATH hệ thống).
2. `FFPROBE_PATH`: Đường dẫn tuỳ biến tới tệp thực thi `ffprobe.exe`.
3. `VKDUB_DATA_DIR`: Thư mục dữ liệu tuỳ biến của ứng dụng (mặc định lưu tại `%LOCALAPPDATA%\VKDubStudio`).
4. `KAPPAK_HOME`: Thư mục gốc lưu trữ cơ sở dữ liệu SQLite và thư mục dự án của KAPPAK Studio (mặc định tại `~/.kappak`).
5. `DISCORD_WEBHOOK_URL`: Đường dẫn Webhook gửi báo cáo tiến độ tới kênh Discord nội bộ.
6. `YTDLP_PATH`: Đường dẫn tuỳ chọn tới công cụ `yt-dlp.exe` (tự động phát hiện trong `tools/yt-dlp/`).

*(Lưu ý: Khóa API Gemini, ChatGPT Token và mật khẩu Vbee được quản lý thông qua Windows Credential Manager `keyring`, tuyệt đối không lưu trong file văn bản `.env`)*.

### 7.2. Dependencies chính và phiên bản đang khóa

#### Backend Python (`pyproject.toml` / `.venv`):
- `python`: `3.12.12`
- `PySide6`: `6.10.3` (Giao diện Desktop native & Qt Event Loop)
- `fastapi`: `0.141.1` (REST API & WebSocket Framework)
- `uvicorn`: `0.53.0` (ASGI Web Server)
- `faster-whisper`: `1.2.1` (Mô hình nhận diện giọng nói STT offline)
- `httpx`: `0.28.1` (HTTP client bất đồng bộ)
- `keyring`: `25.7.0` (Quản lý khóa bảo mật trên Windows Credential Manager)
- `numpy`: `2.5.3` (Xử lý mảng số học và tín hiệu âm thanh)
- `playwright`: `1.62.0` (Tự động hóa trình duyệt headless)

#### Frontend Web (`frontend/package.json` / `package-lock.json`):
- `react`: `19.3.0`
- `react-dom`: `19.3.0`
- `vite`: `8.3.0`
- `@vitejs/plugin-react`: `6.1.1`
- `framer-motion`: `13.3.0` (Hiệu ứng chuyển động Apple Spring Physics)
- `canvas-confetti`: `1.9.4` (Hiệu ứng ăn mừng khi hoàn thành export video)

---

## 8. Lịch sử gần đây (30 commits gần nhất)

```text
51582fb fix(pipeline): support mocked LocalAgent and pre-cancel check in PipelineRunner
f639a94 feat(data_studio): complete Phase 2 Media Asset Management, SHA-256 duplicate detection, 8-tier tree, and Apple Glass UI
b9812c7 docs(audit): complete 100% gap audit verification across all 5 modules with real data
bf14b9e feat(downloader): complete SHA-256 deduplication, real recent projects SQLite integration, and Web Downloader View
d53d102 fix(downloader): enforce URL pre-check and SHA-256 post-check deduplication in service
10deb63 docs(audit): complete rigorous gap audit on section 7.1 per anti-false reporting rules
27ec3c6 docs(handoff): record repo cleanup milestone and test results in PROGRESS.md
53615c2 fix(refs): update paths for moved scripts and test runners
7648d0c chore(archive): move zip packages to archive/releases and updater metadata to packaging/
d1ab671 chore(scripts): relocate batch runners to scripts/ with root forwarding launchers
8f2c74f docs(handoff): archive legacy multi-agent teamwork logs to docs/handoff/archive/
87d17b9 docs(screenshots): consolidate all UI screenshots into docs/screenshots/
ea7488d docs(specs): move architecture and prompt specs to docs/specs/
8f3288a chore(config): update .gitignore and add CLEANUP_PLAN.md
6e45409 chore(skills): track .agent/skills fallback path
c11131e feat(ui): implement KAPPAK Home V2 Apple Glass Female Hero layout per spec
d9ffe92 feat(web): subtitle search-replace, timecode seek, cue voice preview and Discord export alerts
91f2c43 feat(web-studio): complete KAPPAK Web v2 Apple Minimalist, sequential automation pipeline, aspect ratio engine & Discord notifications
cf143a3 fix: Tu dong quay lai Buoc 04 tao lai Vbee khi sua hoac nap lai kich ban (v2.1.17)
d8ee5f0 fix: Tu dong chuyen xuat CapCut/MP4 va sua loi nap/tai SRT khi da duyet kich ban (v2.1.16)
f94b3d6 fix: Tu dong chuyen xuat CapCut, nut Project moi, dong ho dem gio va tinh gian kich ban (v2.1.15)
5dd3523 fix: Khac phuc 6 van de chatgpt, huy tien trinh, giao dien step 3 va chan tieng trung (v2.1.14)
f1bef92 feat(chatgpt): Gui 1 lan duy nhat bang file .srt va tu dong tiep tuc tao (v2.1.13)
98e9db1 feat: separate sub regions with red border & resolve Vbee progress and background tab freezing (v2.1.12)
c79ed38 feat(capcut): fix CapCut version mismatch popup, auto-match installed CapCut (7.7.0), and retroactively patch existing drafts (v2.1.11)
cfee127 release: v2.1.10 fix CapCut version compatibility and retro-patch existing drafts
87f6a1b release: v2.1.9 fix Vbee WinError 2 ffmpeg discovery and robust fallback
ea345c3 feat(pipeline): fix Step 4 UI layout, auto-chunk long ChatGPT translations and add manual SRT import (v2.1.8)
d87609b fix(extension): resilient allTabs scanning, host-only cookies support and 3s status sync
3d97973 release: v2.1.7 dual-channel websocket extension bridge and dynamic manifest
```

---

## 9. Rác / Dư thừa còn sót

Qua rà soát cây thư mục kho lưu trữ:
- **Tệp nén (.zip)**: Toàn bộ các bản đóng gói phát hành cũ đã được di chuyển tập trung vào `archive/releases/` (ví dụ: `VK_Dub_Studio_Ban_Day_Du_Nhe.zip`, `KAPPAK_Extension_v2.3.0_Cai_Dat.zip`). Các tệp build zip trong `dist/` và `build/` đã được loại trừ an toàn bởi `.gitignore`.
- **Tệp tin bất thường lớn / trùng lặp**: Không có tệp tin rác lớn nào bị theo dõi bởi Git. Thư mục `docs/evidence/` chứa video/audio kiểm chứng thực nghiệm đã được đưa vào quy tắc ignore.
- **Trạng thái Git Working Tree**: Sạch 100% (`git status -s` không có thay đổi chưa commit, không có tệp untracked).

---

## 10. Ảnh chụp trạng thái hiện tại (Audit 19/09/2026)

Toàn bộ ảnh chụp màn hình được chụp tự động bằng browser subagent trên hệ thống đang chạy thật và lưu tại thư mục [docs/screenshots/audit_2026-09-19/](file:///d:/Work/Project_AI/ToolVideo/docs/screenshots/audit_2026-09-19):

1. **Home Module**: `docs/screenshots/audit_2026-09-19/01_home.png` (597.7 KB)
2. **Downloader Module**: `docs/screenshots/audit_2026-09-19/02_downloader.png` (109.1 KB)
3. **Data Studio Module**: `docs/screenshots/audit_2026-09-19/03_data_studio.png` (121.0 KB)
4. **Auto Video Module**: `docs/screenshots/audit_2026-09-19/04_auto_video.png` (74.3 KB)
5. **Auto Dub Studio Module**: `docs/screenshots/audit_2026-09-19/05_auto_dub.png` (230.9 KB)
6. **Social Module**: `docs/screenshots/audit_2026-09-19/06_social.png` (75.3 KB)
7. **Today Module**: `docs/screenshots/audit_2026-09-19/07_today.png` (75.1 KB)
8. **Auto Dub Studio — Pipeline thực tế với video `HEHEH.mp4` (Whisper bóc 317 câu thoại gốc, Dịch tiếng Việt tự động, Xuất CapCut Draft & MP4)**: `docs/screenshots/audit_2026-09-19/08_heheh_verified_pipeline.png` (185.4 KB)

---

## 11. Known Issues tổng hợp

Bảng phân loại mức độ nghiêm trọng của các tồn tại, cảnh báo hoặc tính năng đang trong lộ trình phát triển:

| STT | Vấn đề / Tồn tại kỹ thuật | Mức độ nghiêm trọng | Chi tiết & Hướng xử lý đề xuất |
|:---:|---|:---:|---|
| 1 | **Các Module Phase 3, 4, 5 đang ở dạng Placeholder UI** | **Vừa** | Các tab `Auto Video`, `Social`, `Today` đã có UI Apple Glass hoàn chỉnh nhưng chưa gắn kết nối worker AI chuyên sâu. Hiện tại đang ưu tiên dồn lực hoàn thiện Phase 1 (Downloader) và Phase 2 (Data Studio). |
| 2 | **Thời gian render nướng vùng mờ (Blur Mask) với video dài >9 phút** | **Vừa** | Khi video nguồn dài (>9 phút) và có vùng che chữ, FFmpeg mất 40-60 giây để xử lý video trước khi đưa vào CapCut Draft. Đề xuất: Chuyển tác vụ xuất MP4/CapCut thành Job bất đồng bộ qua `LocalJobManager` kèm thông báo tiến độ thanh phần trăm. |
| 3 | **Cảnh báo Deprecation `sqlite3.PARSE_DECLTYPES` trên Python 3.12** | **Thấp** | Python 3.12 thông báo mặc định converter của `sqlite3` bị lỗi thời. Không ảnh hưởng đến dữ liệu hay hoạt động hiện tại (test vẫn pass 100%), nhưng cần viết hàm `sqlite3.register_converter` riêng khi nâng cấp phiên bản Python tiếp theo. |
| 4 | **Cảnh báo Starlette `httpx` TestClient trong môi trường kiểm thử** | **Thấp** | FastAPI test client phát cảnh báo khuyên dùng `httpx2`. Chỉ xuất hiện trong output của Pytest runner, hoàn toàn không ảnh hưởng tới môi trường runtime của người dùng cuối. |
| 5 | **AsyncMock coroutine warning trong test Vbee Automation** | **Thấp** | `test_vbee_automation_mock.py` cảnh báo coroutine mock file chooser chưa được await trong mock assertion. Hoàn toàn là kiểm thử giả lập, không ảnh hưởng runtime thực tế. |

---
*Báo cáo được khởi tạo tự động, kiểm chứng thực nghiệm 100% không suy đoán.*
