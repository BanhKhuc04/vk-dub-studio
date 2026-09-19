# Next Steps — KAPPAK Studio Development

Kế hoạch phát triển các phase chức năng nghiệp vụ tiếp theo dựa trên nền tảng UI Apple Glass V2 đã hoàn thiện:

1. **Phase 1: Downloader Module (`src/kappak/modules/downloader/`)** — ✅ HOÀN THÀNH 100%
   - Đã tích hợp `yt-dlp` local core, chống trùng SHA-256 hai lớp.
   - Hỗ trợ tải chất lượng cao đa nền tảng, Web UI và Desktop UI đều hoạt động thực tế.

2. **Phase 2: Data Studio Module (`src/kappak/modules/data_studio/`)** — ✅ HOÀN THÀNH 100%
   - Trình quản lý bộ sưu tập thông minh (Smart Collections), phát hiện trùng lặp SHA-256.
   - Thống kê dung lượng lưu trữ, duyệt cây thư mục 8 tầng trực quan.

3. **Phase 3: Auto Video Module (`src/kappak/modules/auto_video/`)** — 🚀 **ĐANG TRIỂN KHAI (ƯU TIÊN SỐ 1 THEO CHỈ ĐẠO)**
   - Trình cắt ghép tự động dựa trên kịch bản & tư liệu (Script-to-Video).
   - Ghép cảnh thông minh, thêm hook/CTA, hiệu ứng chuyển cảnh.
   - Tự động căn chỉnh khung hình dọc 9:16 cho TikTok / Reels / Shorts.
   - Tự động sinh phụ đề động & lồng giọng đọc AI.

4. **Phase 4: Auto Dub Module (`src/kappak/modules/auto_dub/`)**
   - Tích hợp pipeline nhận dạng giọng nói (faster-whisper local).
   - Tích hợp VieNeu-TTS tạo giọng đọc tự nhiên.
   - Trộn âm thanh và đồng bộ phụ đề thông minh qua FFmpeg.

5. **Phase 5: Social & Phase 6: Today**
   - Quản lý kênh và lên lịch đăng bài tự động.
   - Theo dõi tiến độ công việc và nhiệm vụ ưu tiên.

6. **Phase 7: Chat Agent hoàn chỉnh (`✦ Ask KAPPAK`)**
   - Kết nối LLM local/API để cho phép người dùng ra lệnh điều khiển toàn bộ 6 module bằng ngôn ngữ tự nhiên ngay trong AskKappakDrawer.
