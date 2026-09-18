# Next Steps — KAPPAK Studio Development

Kế hoạch phát triển các phase chức năng nghiệp vụ tiếp theo dựa trên nền tảng UI Apple Glass V2 đã hoàn thiện:

1. **Phase 1: Downloader Module (`src/kappak/modules/downloader/`)**
   - Tích hợp `yt-dlp` local core.
   - Hỗ trợ tải video chất lượng cao từ TikTok, YouTube, Douyin, Facebook, Instagram.
   - Tự động lưu vào folder `00_Inbox` của dự án và tạo bản ghi Asset (hash SHA-256 chống trùng).

2. **Phase 2: Data Studio Module (`src/kappak/modules/data_studio/`)**
   - Trình quản lý bộ sưu tập thông minh (Smart Collections).
   - Quét và phát hiện trùng lặp tài nguyên đa phương tiện bằng SHA-256.
   - Trình duyệt cây thư mục dự án 8 tầng trực quan.

3. **Phase 3: Auto Video Module (`src/kappak/modules/auto_video/`)**
   - Trình cắt ghép tự động dựa trên kịch bản (Script-to-Video).
   - Thuật toán lọc bỏ khoảng lặng (Silence detection / removal).
   - Tự động căn chỉnh khung hình dọc 9:16 cho TikTok / Reels / Shorts.

4. **Phase 4: Auto Dub Module (`src/kappak/modules/auto_dub/`)**
   - Tích hợp pipeline nhận dạng giọng nói (faster-whisper local).
   - Tích hợp VieNeu-TTS tạo giọng đọc tự nhiên.
   - Trộn âm thanh và đồng bộ phụ đề thông minh qua FFmpeg.

5. **Phase 5: Social & Phase 6: Today**
   - Quản lý kênh và lên lịch đăng bài tự động.
   - Theo dõi tiến độ công việc và nhiệm vụ ưu tiên.

6. **Phase 7: Chat Agent hoàn chỉnh (`✦ Ask KAPPAK`)**
   - Kết nối LLM local/API để cho phép người dùng ra lệnh điều khiển toàn bộ 6 module bằng ngôn ngữ tự nhiên ngay trong AskKappakDrawer.
