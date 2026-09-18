# KAPPAK Project Status

- **Trạng thái tổng quan:** Hoàn thành triển khai **Phương án 1 (Hero HD từ background.png)** và hoàn thành 100% **Phase 1: Downloader Module** theo đúng đặc tả kỹ thuật `KAPPAK_AGENT_CODING_BRIEF.md`.
- **Phiên bản:** KAPPAK Studio Desktop v2.1-downloader
- **Kiến trúc:** Local-first Personal Media Workspace (SQLite WAL + Persistent Local Job Manager + PySide6 Apple Glass UI + yt-dlp Core).

## Các cấu phần đã hoàn thành
1. **Core & SQLite Phase 0 (100% Nguyên vẹn):**
   - SQLite WAL Engine (`src/kappak/core/db.py`)
   - Cấu trúc thư mục dự án 8 tầng chuẩn (`src/kappak/domain/project.py`)
   - Deduplication Asset SHA-256 (`src/kappak/domain/asset.py`)
   - Persistent Local Job Manager (`src/kappak/jobs/manager.py`)
2. **Giao diện Apple Glass Female Hero V2 (Web Frontend & Desktop):**
   - **Web Frontend React 19 + Vite**: Đã triển khai hoàn chỉnh toàn bộ kiến trúc Apple Glass Female Hero V2 bám sát 100% ảnh chuẩn `reference/01_TARGET_UI_FEMALE_HERO.png`:
     - Left Icon Rail (74px) với macOS window dots, active pill rounded-square glass blue, icon primary blue.
     - Topbar 72px với Search pill lớn (580px, Ctrl + K), `• AI Sẵn sàng ˇ`, nút `✦ Ask KAPPAK`, notification bell và avatar VK.
     - Hero Banner (330px, radius 30px) với visual nữ creator tự nhiên, headline gradient blue, quote cảm hứng nổi và chữ viết tay trang trí.
     - Dải 6 module card pastel: Downloader (blue), Data Studio (mint), Auto Video (violet), Auto Dub (cyan), Social (pink), Today (amber). Tuyệt đối không có card AI Agent.
     - 3 khối đáy cân đối: Recent Projects (3 video cards thumbnail có duration), Continue Work ("+ Tạo dự án mới"), AI Suggestion ("Dùng thử ngay →").
     - Khung trợ lý Ask KAPPAK glass drawer panel (410px) trượt từ cạnh phải với quick chips và chat box.
     - Điều hướng bảo toàn chức năng sang Auto Dub Studio 5 bước mượt mà.
   - **Desktop GUI PySide6**: Đã nâng cấp HD từ `background.png`.
3. **Phase 1: Downloader Module:**
   - Engine tải `yt-dlp` và `ffmpeg` được tích hợp hoàn chỉnh.
   - Tự động phát hiện nền tảng (TikTok, YouTube, Facebook, Instagram, Douyin).
   - Trích xuất siêu dữ liệu trước khi tải (tiêu đề, tác giả, thời lượng, ảnh bìa).
   - Tải video/audio chất lượng cao, tính mã băm SHA-256 chống trùng lặp và ghi nhận vào bảng `assets`.
   - Giao diện người dùng Apple Glass đầy đủ: ô nhập link, thẻ xem trước, tùy chọn chất lượng & dự án đích, thanh tiến trình thời gian thực, bảng lịch sử và nút "Mở thư mục" nhanh.
