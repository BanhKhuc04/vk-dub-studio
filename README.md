<p align="center">
  <img src="logo/kappak-logo.png" alt="KAPPAK Studio" width="120">
</p>

<h1 align="center">KAPPAK Personal Media Studio</h1>

<p align="center">
  <strong>Auto-Dubbing · Video Downloading · Media Management · Content Creation</strong>
</p>

<p align="center">
  <a href="#-cài-đặt-nhanh">Cài đặt</a> ·
  <a href="#-tính-năng-chính">Tính năng</a> ·
  <a href="#-kiến-trúc">Kiến trúc</a> ·
  <a href="#-kiểm-thử">Kiểm thử</a> ·
  <a href="#-đóng-góp">Đóng góp</a>
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-2.1.17-blue">
  <img alt="Python" src="https://img.shields.io/badge/python-3.12-green">
  <img alt="Tests" src="https://img.shields.io/badge/tests-859_passed-brightgreen">
  <img alt="License" src="https://img.shields.io/badge/license-Private-red">
</p>

---

## 📖 Giới thiệu

**KAPPAK Personal Media Studio** (trước đây là **VK Dub Studio**) là hệ sinh thái phần mềm sáng tạo nội dung và tự động hóa biên tập video dành cho Content Creator & Solo Media Producer.

### Các module chính

| Module | Mô tả | Trạng thái |
|:---|:---|:---:|
| 🎙️ **Auto Dub Studio** | Lồng tiếng tự động: STT → Dịch thuật → TTS → CapCut/MP4 | ✅ Production |
| ⬇️ **Universal Downloader** | Tải video TikTok, YouTube, Douyin, FB, IG không watermark | ✅ Production |
| 📂 **Data Studio** | Quản lý kho tư liệu, chống trùng lặp SHA-256 | ✅ Production |
| 🔌 **Browser Extension** | Tự động hóa ChatGPT & Vbee qua Edge/Chrome (Manifest V3) | ✅ Production |
| 🎬 Auto Video | Tạo video ngắn tự động từ template | 🚧 Planned |
| 📱 Social | Lên lịch đăng bài đa nền tảng | 🚧 Planned |
| 📊 Today | Dashboard thông minh hàng ngày | 🚧 Planned |

---

## 🖥️ Dual Interface

KAPPAK Studio hỗ trợ **2 giao diện** chạy song song trên cùng backend:

| | Web Studio | Desktop GUI |
|:---|:---|:---|
| **Công nghệ** | React 19 + Vite | PySide6 (Qt) |
| **Thiết kế** | Apple Glass Minimalist | Dark Theme 3-Column |
| **Cổng** | `http://localhost:8000` | Native Window |
| **Khởi chạy** | `python app.py` | `python app.py --gui` |

---

## ⚡ Cài đặt nhanh

### Yêu cầu hệ thống
- **Windows 10/11** x64
- **Python 3.12+** (khuyên dùng cài qua [uv](https://docs.astral.sh/uv/))
- **Node.js 20+** (cho frontend development)
- **FFmpeg** (tự động dò tìm trong `tools/` hoặc PATH)

### 1. Clone & Thiết lập môi trường

```powershell
git clone https://github.com/vanhkhuc-k5/vk-dub-studio.git
cd vk-dub-studio

# Tạo virtualenv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Cài đặt dependencies
pip install -e ".[dev]"
```

### 2. Cấu hình API Keys (bảo mật)

```powershell
# Lưu Gemini API Key vào Windows Credential Manager
.\.venv\Scripts\python.exe -c "import keyring; keyring.set_password('vkdub', 'gemini_api_key', 'YOUR_KEY')"
```

> [!NOTE]
> API keys được lưu an toàn trong Windows Credential Manager, không bao giờ xuất hiện trong code, log hay git history.

### 3. Khởi chạy

```powershell
# Web Studio (khuyên dùng)
.\.venv\Scripts\python.exe app.py
# → Truy cập http://localhost:8000

# Desktop GUI
.\.venv\Scripts\python.exe app.py --gui
```

---

## 🎙️ Tính năng chính

### Auto Dub Studio — Pipeline lồng tiếng 5 bước

| Bước | Tên | Công nghệ |
|:---:|:---|:---|
| 1️⃣ | **Nguồn Video** | Upload/drag-drop MP4, MKV, MOV. FFprobe metadata. |
| 2️⃣ | **Giọng & AI** | Chọn giọng Edge TTS / Vbee, tốc độ 0.9x–1.3x |
| 3️⃣ | **Vùng Che Mờ** | Canvas tương tác vẽ vùng blur (delogo, drawbox, boxblur) |
| 4️⃣ | **Tự Động Hóa** | Whisper STT → Gemini/ChatGPT dịch → TTS sinh giọng |
| 5️⃣ | **Duyệt & Xuất** | Review kịch bản → Xuất CapCut Draft v360000 hoặc MP4 |

### Universal Downloader
- Tải video từ **YouTube, TikTok, Douyin, Facebook, Instagram** chất lượng gốc
- Trích xuất metadata trước khi tải (tiêu đề, thumbnail, tác giả, thời lượng)
- Chống trùng lặp 2 lớp: Pre-check URL + Post-check SHA-256
- Chuyển 1-chạm sang Auto Dub Studio

### Browser Extension (KAPPAK Extension v2.3.0)
- **YouTube Adapter**: In-player toolbar, phím tắt I/O/Enter cắt clip, highlight scrubber
- **ChatGPT Adapter**: Tự động điền prompt & paste SRT, trích xuất kết quả dịch
- **Vbee Adapter**: Upload SRT, chọn giọng, sinh audio tự động
- **Side Panel**: Quản lý danh sách clips, kéo thả sắp xếp, xuất batch

---

## 🏗️ Kiến trúc

```
vk-dub-studio/
├── app.py                          # Entry point (FastAPI / PySide6 / Workers)
├── src/
│   ├── vkdub/                      # Auto-Dubbing Core
│   │   ├── web/server.py           # FastAPI + WebSocket server
│   │   ├── orchestrator/           # PipelineRunner (4-step automation)
│   │   ├── services/               # CapCut export, render, blur, SRT, TTS, translation
│   │   ├── media/                  # FFmpeg, clip engine, hardware probe, yt-dlp
│   │   ├── providers/              # Whisper, Edge TTS, Vbee, VieNeu, Gemini
│   │   ├── bridge/                 # LocalAgent TCP:49814, registry
│   │   └── ui/                     # PySide6 desktop GUI
│   └── kappak/                     # Personal Media Workspace
│       ├── core/db.py              # SQLite WAL engine
│       ├── jobs/manager.py         # ThreadPoolExecutor job queue
│       └── modules/                # downloader, data_studio
├── frontend/                       # React 19 + Vite Web UI
│   ├── src/App.jsx                 # 2400+ LOC main application
│   └── src/components/             # IconRail, Topbar, Canvas, Views
├── apps/browser-extension/         # Manifest V3 (Edge/Chrome)
│   ├── adapters/                   # YouTube, ChatGPT, Vbee content scripts
│   ├── bridge/                     # Native Messaging + WebSocket dual transport
│   └── sidepanel/                  # Clip management UI
├── tools/native_host/              # 32-bit JSON IPC bridge
├── tests/                          # 70 files, 859 test cases
├── packaging/                      # PyInstaller + Inno Setup build
└── docs/                           # Architecture specs, handoff logs, screenshots
```

### Tech Stack

| Layer | Technology |
|:---|:---|
| **Backend** | Python 3.12, FastAPI, Uvicorn, WebSockets |
| **Desktop GUI** | PySide6 (Qt 6.10) |
| **Web Frontend** | React 19, Vite, Framer Motion, Vanilla CSS |
| **Database** | SQLite 3 (WAL mode, Foreign Keys) |
| **STT** | faster-whisper (CTranslate2, CPU/CUDA) |
| **Translation** | Google Gemini 2.5 Flash / ChatGPT Web |
| **TTS** | Edge TTS, Vbee Studio, VieNeu-TTS |
| **Media** | FFmpeg, ffprobe, yt-dlp |
| **Extension** | Manifest V3 (Chrome/Edge) |
| **Security** | Windows Credential Manager (keyring) |
| **CI/CD** | GitHub Actions (Ruff, Mypy, Pytest, PyInstaller, Inno Setup) |

---

## 🧪 Kiểm thử

```powershell
# Chạy toàn bộ test suite (859 test cases)
.\.venv\Scripts\python.exe -m pytest -q

# Chạy nhóm test cốt lõi
.\.venv\Scripts\python.exe -m pytest tests/test_bridge_protocol.py tests/test_capcut_export.py tests/test_clip_engine.py -q

# Chạy KAPPAK module tests
.\.venv\Scripts\python.exe -m pytest tests/kappak/ -q

# Lint & Type check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
```

### Test Coverage Summary

| Component | Test Files | Test Cases | Quality |
|:---|:---:|:---:|:---:|
| YouTube Clip & Engine | 5 | 203 | Comprehensive |
| Voice, TTS & Translation | 12 | 155 | Real Tests |
| Browser Bridge & IPC | 5 | 30 | Comprehensive |
| Pipeline & Recovery | 8 | 84 | Comprehensive |
| Desktop UI (PySide6) | 8 | 73 | Comprehensive |
| Packaging & Updater | 8 | 84 | Real Tests |
| E2E Integration | 4 | 88 | Comprehensive |
| Blur & Computer Vision | 3 | 50 | Comprehensive |
| CapCut Export | 2 | 11 | Comprehensive |
| KAPPAK Core | 4 | 10 | Real Tests |

---

## 🔌 Browser Extension Setup

1. Đăng ký Native Messaging Host:
   ```powershell
   .\.venv\Scripts\python.exe tools/native_host/register_host.py
   ```

2. Mở `edge://extensions/` hoặc `chrome://extensions/`
3. Bật **Developer Mode**
4. Click **Load Unpacked** → Chọn `apps/browser-extension/`

---

## 🤝 Đóng góp

### Quy trình làm việc

1. Tạo **GitHub Issue** (Bug Report hoặc Feature Request)
2. Tạo branch: `feat/issue-N-description` hoặc `fix/issue-N-description`
3. Code + Test (tuân thủ [AGENTS.md](AGENTS.md))
4. Tạo **Pull Request** link Issue
5. CI tự động kiểm tra (Ruff + Mypy + Pytest)
6. Review & Merge vào `develop`

### Commit Convention

```
feat(module): mô tả tính năng mới
fix(module): mô tả lỗi đã sửa
docs: cập nhật tài liệu
chore: dọn dẹp, cấu hình
test: thêm/sửa test
refactor: tái cấu trúc
```

### Anti-False Reporting Rules

> [!WARNING]
> Tuyệt đối không tuyên bố DONE chỉ vì đã tạo UI. Mọi tính năng phải kèm:
> - Test pass (`pytest`)
> - Lint clean (`ruff check .`)
> - Type check clean (`mypy`)
> - Trạng thái: `PASS` | `PARTIAL` | `FAIL` | `UI ONLY` | `IMPLEMENTED BUT NOT VERIFIED`

---

## 📄 Tài liệu bổ sung

- [📋 Project Overview](docs/PROJECT_OVERVIEW.md) — Kiến trúc chi tiết
- [📐 AGENTS.md](AGENTS.md) — Quy chuẩn cho AI Agent
- [📊 Progress Tracking](docs/handoff/PROGRESS.md) — Tiến độ milestone
- [🎯 Status Board](docs/handoff/STATUS.md) — Trạng thái module

---

<p align="center">
  <strong>KAPPAK Studio v2.1.17</strong><br>
  Sản phẩm tạo bởi <a href="https://github.com/vanhkhuc-k5">vanhkhuc.dev</a><br>
  <em>Dành tặng em bé Trang Vũ ❤️</em>
</p>
