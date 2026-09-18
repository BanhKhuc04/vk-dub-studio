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
2. **Giao diện Apple Glass Female Hero V2 (Đã nâng cấp HD):**
   - Áp dụng hình ảnh visual nữ creator HD trích xuất trực tiếp từ `background.png` gốc, không vệt nén, siêu sắc nét.
   - Left Icon Rail (74px), Top Bar với Search Pill (580px), Dải 6 module card pastel, 3 khối nội dung đáy và Ask KAPPAK Drawer.
3. **Phase 1: Downloader Module (Mới hoàn thành):**
   - Engine tải `yt-dlp` và `ffmpeg` được tích hợp hoàn chỉnh.
   - Tự động phát hiện nền tảng (TikTok, YouTube, Facebook, Instagram, Douyin).
   - Trích xuất siêu dữ liệu trước khi tải (tiêu đề, tác giả, thời lượng, ảnh bìa).
   - Tải video/audio chất lượng cao, tính mã băm SHA-256 chống trùng lặp và ghi nhận vào bảng `assets`.
   - Giao diện người dùng Apple Glass đầy đủ: ô nhập link, thẻ xem trước, tùy chọn chất lượng & dự án đích, thanh tiến trình thời gian thực, bảng lịch sử và nút "Mở thư mục" nhanh.
