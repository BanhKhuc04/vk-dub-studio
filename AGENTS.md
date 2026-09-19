# AGENTS.md — Quy Chuẩn Dự Án VK Dub Studio & KAPPAK Personal Media Studio

Tài liệu này chứa các quy tắc và hướng dẫn tối cao dành cho AI Agent khi thao tác, phân tích hoặc phát triển mã nguồn trong kho lưu trữ này.

---

## 1. TỔNG QUAN DỰ ÁN
- **VK Dub Studio / KAPPAK Studio Web & Desktop**: Hệ thống phần mềm tự động hóa quy trình lồng tiếng (auto-dubbing), trích xuất và cắt clip video (YouTube, Douyin, TikTok...), dịch phụ đề giữ ngữ cảnh (Gemini / ChatGPT), tạo giọng đọc AI (VieNeu-TTS / Edge TTS / Vbee), làm mờ phụ đề cũ và xuất dự án CapCut PC Draft hoặc video MP4 hoàn chỉnh.
- **Tác giả / Duy trì**: vanhkhuc.dev
- **Môi trường**: Windows 11 x64, Python 3.12 (Virtualenv tại `.venv`), Node.js (cho `frontend/`).

---

## 2. NGUYÊN TẮC CỐT LÕI (CORE RULES)

### 2.1. Chống Báo Cáo Khống (Anti-False Reporting)
- **Tuyệt đối không tuyên bố DONE chỉ vì đã tạo xong UI hoặc giao diện mẫu**.
- Bất kỳ tính năng mới hoặc sửa lỗi nào phải được kiểm chứng bằng:
  - Unit test / Integration test tương ứng chạy PASS (`.\.venv\Scripts\python.exe -m pytest ...`).
  - Kiểm tra cú pháp và kiểu dữ liệu (`ruff check .`, `mypy`).
  - Hoặc log chạy thực tế của công cụ.
- Trạng thái chỉ được ghi là: `PASS`, `PARTIAL`, `FAIL`, `UI ONLY`, `IMPLEMENTED BUT NOT VERIFIED`, `BLOCKED`.

### 2.2. Bảo Mật Secret & API Keys
- **Tuyệt đối KHÔNG in, log hoặc lưu vết API keys, password, cookies hay private token vào console, nhật ký hệ thống (`logs/vkdub.log`), git commits hoặc file tài liệu bằng chứng**.
- Sử dụng `keyring` (Windows Credential Manager) hoặc biến môi trường `.env`.

### 2.3. Quy Chuẩn Xử Lý Tiến Trình (Subprocess & Media)
- Mọi lệnh gọi công cụ ngoại vi (`ffmpeg`, `ffprobe`, `yt-dlp`, child workers) phải dùng danh sách tham số an toàn (`subprocess.Popen(args_list)` hoặc `asyncio.create_subprocess_exec`), **tuyệt đối không nối chuỗi lệnh qua `shell=True`**.
- Không thực hiện tác vụ nặng trên UI thread của PySide6 (sử dụng `QThread` hoặc `threading.Thread` kèm cơ chế hủy an toàn process tree).
- Dọn dẹp tệp tin tạm thời trong thư mục temp/scratch khi hủy hoặc hoàn thành tác vụ.

### 2.4. Browser Extension & Bridge
- Extension chạy trên nền Microsoft Edge & Google Chrome (Manifest V3).
- Giao tiếp với Desktop qua Native Messaging Host (`tools/native_host/vkdub_host.py`) bằng khung 32-bit JSON framing trên Stdio.
- **Không truyền file binary video trực tiếp qua Native Messaging**. Chỉ truyền metadata, timecode, URL và các mã điều khiển.

---

## 3. LỆNH CHẠY THƯỜNG DÙNG (RUNBOOKS)

- **Chạy Web Server & Giao diện Web (Mặc định)**:
  ```powershell
  .\.venv\Scripts\python.exe app.py
  # Hoặc: .\run_app.bat
  ```
- **Chạy Desktop GUI (PySide6)**:
  ```powershell
  .\.venv\Scripts\python.exe app.py --gui
  ```
- **Chạy Bộ Kiểm Thử (Pytest)**:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_bridge_protocol.py tests/test_capcut_export.py -q
  ```
- **Đăng Ký Native Messaging Host (Edge & Chrome)**:
  ```powershell
  .\.venv\Scripts\python.exe tools/native_host/register_host.py
  ```
- **Khởi Chạy Frontend Vite Dev Server**:
  ```powershell
  cd frontend
  npm run dev
  ```

---

## 4. ROADMAP PHÁT TRIỂN (DEVELOPMENT ROADMAP)

Bất kỳ AI Agent nào đọc tài liệu này phải hiểu trạng thái và hướng phát triển:

### 4.1. Trạng Thái Hiện Tại (v2.1.17 — 19/09/2026)

| Module | Trạng thái | Ghi chú |
|:---|:---:|:---|
| Auto Dub Studio (5 bước) | ✅ PRODUCTION | Pipeline hoàn chỉnh: Whisper STT → Dịch → TTS → CapCut/MP4 |
| Universal Downloader | ✅ PRODUCTION | yt-dlp + SHA-256 dedup, Web + Desktop |
| Data Studio | ✅ PRODUCTION | Quản lý kho tư liệu, 8-tier tree, smart collections |
| Browser Extension v2.3.0 | ✅ PRODUCTION | YouTube/ChatGPT/Vbee adapters, Dual Bridge |
| Ask KAPPAK AI Drawer | 🟡 UI_ONLY | Giao diện chat có sẵn, cần kết nối LLM backend |
| Auto Video Generator | 🔴 STUB | Placeholder card, chưa có logic |
| Social Publisher | 🔴 STUB | Placeholder card, chưa có logic |
| Today Dashboard | 🔴 STUB | Placeholder card, chưa có logic |

### 4.2. Pha Phát Triển Tiếp Theo

1. **Pha 1 (Test Coverage)**: Bổ sung unit test cho Edge-TTS, VieNeu-TTS, CapCut TTS API, KAPPAK UI, Frontend React.
2. **Pha 2 (Ask KAPPAK AI)**: Kết nối `AskKappakDrawer` với Gemini/ChatGPT API thực, streaming response, lịch sử chat SQLite.
3. **Pha 3 (New Modules)**: Hoàn thiện 3 module STUB: Auto Video, Social, Today.
4. **Pha 4 (Production Scale)**: Auto-update, i18n, batch processing, plugin system.

---

## 5. QUY CHUẨN GIT WORKFLOW

### 5.1. Issue-First Development
- Mọi thay đổi code phải tạo **GitHub Issue** trước khi bắt đầu.
- Branch đặt tên: `feat/issue-N-mô-tả` hoặc `fix/issue-N-mô-tả`.

### 5.2. Conventional Commits
- `feat(module):` — Tính năng mới
- `fix(module):` — Sửa lỗi
- `docs:` — Cập nhật tài liệu
- `chore:` — Dọn dẹp, cấu hình
- `test:` — Thêm/sửa test
- `refactor:` — Tái cấu trúc không đổi hành vi

### 5.3. Pull Request Checklist
Mọi PR phải kèm:
- [ ] Tests pass: `.\.venv\Scripts\python.exe -m pytest -q`
- [ ] Linter clean: `ruff check .`
- [ ] Type check: `mypy`
- [ ] Không có secrets trong code/log
- [ ] Subprocess dùng args_list (không shell=True)
- [ ] Trạng thái: PASS / PARTIAL / FAIL / UI_ONLY

### 5.4. Branching Strategy
- `main` ← Production releases (tag `v*`)
- `develop` ← Integration branch
- `feat/*`, `fix/*` ← Feature/fix branches từ `develop`

### 5.5. Discord Notifications
- Mọi CI pass/fail, release, issue → tự động gửi Discord webhook.
