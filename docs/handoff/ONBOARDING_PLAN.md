# KAPPAK Studio — Onboarding Plan

**Ngày tạo:** 19/09/2026  
**Agent:** Claude Code (lần đầu làm việc trên dự án)  
**Mục đích:** Tài liệu handoff cho các session tiếp theo

---

## 1. Tổng Quan Stack & Cách Chạy Dự Án

### 1.1 Tech Stack

| Layer | Technology |
|:---|:---|
| **Backend** | Python 3.12, FastAPI 0.141, Uvicorn 0.53, PySide6 6.10 |
| **Frontend** | React 19.3, Vite 8.3, Framer Motion 13.3 |
| **Database** | SQLite 3 (WAL mode) tại `~/.kappak/kappak.db` |
| **STT** | faster-whisper 1.2.1 (CPU/CUDA offline) |
| **TTS** | Edge TTS, Vbee, VieNeu |
| **Media** | FFmpeg, ffprobe, yt-dlp |
| **Browser Ext** | Manifest V3 (Edge/Chrome) |

### 1.2 Lệnh Chạy Thường Dùng

```powershell
# Khởi chạy Web Server (mặc định)
.\.venv\Scripts\python.exe app.py

# Chạy Desktop GUI
.\.venv\Scripts\python.exe app.py --gui

# Chạy test suite
.\.venv\Scripts\python.exe -m pytest -q

# Frontend dev server
cd frontend
npm run dev

# Build frontend
npm run build
```

### 1.3 Cấu Trúc Thư Mục Chính

```
ToolVideo/
├── src/
│   ├── vkdub/          # Auto-Dubbing Core
│   │   ├── web/server.py       # FastAPI + WebSocket endpoints
│   │   ├── orchestrator/       # PipelineRunner (4-step automation)
│   │   ├── services/          # CapCut export, render, TTS, translation
│   │   ├── providers/          # Whisper, Edge TTS, Vbee, Gemini
│   │   └── ui/                 # PySide6 desktop GUI
│   └── kappak/          # KAPPAK Personal Media Workspace
│       ├── core/db.py          # SQLite WAL engine
│       ├── modules/
│       │   ├── auto_video/     # Auto Video Generator (ƯU TIÊN 1)
│       │   ├── data_studio/    # ✅ DONE
│       │   └── downloader/     # ✅ DONE
│       └── ui/                 # Web UI components
├── frontend/            # React 19 + Vite Web UI
│   └── src/
│       ├── App.jsx             # 2400+ LOC main application
│       └── components/         # IconRail, Topbar, Views
├── tests/              # 70 test files, ~850 test cases
└── docs/               # Architecture specs, handoff logs
```

### 1.4 Environment Variables

| Variable | Mô tả |
|:---|:---|
| `FFMPEG_PATH` | Đường dẫn tới ffmpeg.exe |
| `KAPPAK_HOME` | Thư mục gốc (mặc định `~/.kappak`) |
| `VKDUB_DATA_DIR` | Thư mục dữ liệu (mặc định `%LOCALAPPDATA%\VKDubStudio`) |

**Lưu ý:** API Keys (Gemini, ChatGPT) được lưu trong Windows Credential Manager qua `keyring`, không lưu trong .env.

---

## 2. Trạng Thái Thực Tế Các Module

### ✅ Đang Hoạt Động Đầy Đủ

| Module | Trạng thái | Chi tiết |
|:---|:---:|:---|
| **Auto Dub Studio (5 bước)** | ✅ PRODUCTION | E2E verified với video thật HEHEH.mp4 (317 câu thoại tiếng Trung → tiếng Việt, Whisper STT, Edge TTS, CapCut Draft export) |
| **Universal Downloader** | ✅ PRODUCTION | yt-dlp + SHA-256 dedup, Web UI kết nối API thật |
| **Data Studio** | ✅ PRODUCTION | Quản lý tài nguyên, Smart Collections, SHA-256 duplicate detection |
| **Browser Extension v2.3.0** | ✅ PRODUCTION | YouTube/ChatGPT/Vbee adapters, Dual Bridge Native + WebSocket |

### 🟡 Có Giao Diện, Cần Logic Backend

| Module | Trạng thái | Chi tiết |
|:---|:---:|:---|
| **Ask KAPPAK AI Drawer** | 🟡 UI_ONLY | Giao diện chat có sẵn (AskKappakDrawer.jsx), cần kết nối LLM backend (Gemini/ChatGPT streaming) |

### 🔴 Placeholder / Cần Xây Dựng Từ Đầu

| Module | Trạng thái | Chi tiết |
|:---|:---:|:---|
| **Auto Video Generator** | 🔴 PARTIAL | Backend (service, renderer, templates) **đã có**, Web UI đã có, **cần E2E test và fix test fail** |
| **Social Publisher** | 🔴 STUB | Chỉ có placeholder card |
| **Today Dashboard** | 🔴 STUB | Chỉ có placeholder card |

---

## 3. Trạng Thái Test Suite

**Lệnh:** `.\.venv\Scripts\python.exe -m pytest -q`

| Chỉ số | Giá trị |
|:---|---:|
| Tổng số tests | 847 |
| Passed | 846 |
| Failed | **1** ❌ |
| Skipped | 0 |

### 3.1 Test Fail Details

| File | Test | Lỗi |
|:---|:---|:---|
| `tests/kappak/test_core.py` | `test_local_job_manager_cancellation` | Cần điều tra chi tiết |

**Khuyến nghị:** Đây là ưu tiên sửa lỗi đầu tiên trước khi thêm tính năng mới.

### 3.2 Deprecation Warnings

- `sqlite3.PARSE_DECLTYPES` → cần viết custom converter khi nâng Python
- `httpx` TestClient → nên đổi sang `httpx2`
- AsyncMock coroutine trong test Vbee

---

## 4. Rủi Ro & Vùng Nhạy Cảm

### 🔴 Cần Cẩn Thận Khi Sửa

1. **Test fail `test_local_job_manager_cancellation`**
   - File: `tests/kappak/test_core.py`
   - Có thể ảnh hưởng đến Job Manager trong production

2. **Auto Video Generator — Module Ưu Tiên 1**
   - Backend đã có nhưng **chưa test E2E thực tế**
   - Cần chạy thử với video thật để xác nhận render pipeline hoạt động

3. **Database migrations**
   - SQLite schema thay đổi có thể break existing data
   - Backup trước khi sửa schema

4. **Subprocess calls với FFmpeg/yt-dlp**
   - Cần kiểm tra `creationflags=0x08000000` trên Windows
   - Không dùng `shell=True`

### 🟡 Có Thể Sửa An Toàn

1. **Frontend React components** — có test coverage tốt
2. **API endpoints** — có integration tests
3. **Auto Video UI** — component độc lập

---

## 5. Danh Sách Việc Đề Xuất (Theo Thứ Tự Ưu Tiên)

### Ưu Tiên 1: Sửa Test Fail
- **Hành động:** Điều tra và sửa `test_local_job_manager_cancellation` trong `tests/kappak/test_core.py`
- **Lý do:** Tuân thủ Anti-False Reporting — tất cả tests phải pass trước khi thêm tính năng

### Ưu Tiên 2: E2E Test Auto Video Generator
- **Hành động:**
  1. Chạy thử backend Auto Video service với script thật
  2. Test render pipeline (scene segmentation → TTS → FFmpeg concat → output MP4)
  3. Kết nối Web UI với backend và test end-to-end
- **Lý do:** Module này là ưu tiên phát triển tiếp theo theo AGENTS.md

### Ưu Tiên 3: Hoàn Thiện Ask KAPPAK AI
- **Hành động:** Kết nối AskKappakDrawer với Gemini/ChatGPT API
- **Lý do:** UI đã có sẵn, cần backend streaming response

### Ưu Tiên 4: Xây Dựng Social Publisher
- **Hành động:** Tạo backend service + UI cho đăng bài đa nền tảng
- **Lý do:** Theo roadmap trong AGENTS.md

### Ưu Tiên 5: Xây Dựng Today Dashboard
- **Hành động:** Tạo dashboard với analytics và trending content
- **Lý do:** Theo roadmap trong AGENTS.md

---

## 6. Câu Hỏi Cần Người Dùng Trả Lời

### Q1: Thứ tự ưu tiên chính xác?
Trong AGENTS.md ghi **Auto Video Generator** là ưu tiên 1, nhưng có 1 test fail. Có nên:
- (A) Sửa test fail trước rồi mới phát triển Auto Video
- (B) Phát triển Auto Video trước, test fail sửa sau

### Q2: Scope của Auto Video Generator?
Module này bao gồm:
- ✅ Backend: service, renderer, templates (đã có)
- ✅ UI: AutoVideoView.jsx với 3 steps (đã có)
- ❓ Cần thêm tính năng gì ngoài script-to-video pipeline?

### Q3: API cho Ask KAPPAK AI?
- Gemini API đã được cấu hình trong hệ thống?
- Cần streaming response hay single response?

---

## 7. Nguồn Tài Liệu Tham Khảo

| File | Mô tả |
|:---|:---|
| `AGENTS.md` | Quy tắc và roadmap dự án |
| `README.md` | Tổng quan và hướng dẫn cài đặt |
| `docs/handoff/SYSTEM_AUDIT_2026-09-19.md` | Audit toàn diện ngày 19/09 |
| `docs/handoff/PROGRESS.md` | Tiến độ các phase phát triển |
| `docs/handoff/STATUS.md` | Trạng thái các module |
| `src/vkdub/web/server.py` | Tất cả API endpoints |
| `src/kappak/modules/auto_video/service.py` | Auto Video backend service |

---

## 8. Quick Start Checklist Cho Session Tiếp Theo

```powershell
# 1. Verify environment
.\.venv\Scripts\python.exe -m pytest tests/kappak/test_core.py -q

# 2. Check Auto Video backend
.\.venv\Scripts\python.exe -c "from kappak.modules.auto_video import AutoVideoService; print('OK')"

# 3. Start dev server
.\.venv\Scripts\python.exe app.py

# 4. Frontend dev (separate terminal)
cd frontend
npm run dev
```

---

*Document được tạo tự động bởi Claude Code onboarding agent*
*Chờ user duyệt trước khi bắt đầu bất kỳ thay đổi code nào*
