# Original User Request

## 2026-09-15T03:18:26Z

Tái cấu trúc và phát triển toàn diện giao diện Web cho dự án ToolVideo tại `D:\Work\Project_AI\ToolVideo` theo phong cách Apple tối giản, sang trọng và hiện đại (KAPPAK Studio Web v2). Loại bỏ triệt để các ô nhập thông số tọa độ thủ công (X, Y, W, H), thay thế bằng thao tác kéo thả vẽ trực tiếp vùng che mờ trên màn hình video, tối ưu hóa toàn bộ quy trình lồng tiếng tự động 1-click và tích hợp logo thương hiệu chuẩn nét.

Working directory: D:\Work\Project_AI\ToolVideo
Integrity mode: development

## Requirements

### R1. Giao diện Web Apple Tối giản & Vẽ Vùng Che Mờ Trực Tiếp Trên Video (Interactive Canvas)
- Xóa bỏ hoàn toàn các trường nhập số tọa độ (X, Y, Width, Height) và các nút bấm dư thừa ở mục làm mờ.
- Người dùng có thể dùng chuột click và kéo trực tiếp trên khung màn hình video để tạo, di chuyển hoặc thay đổi kích thước vùng che mờ (hỗ trợ resize handle trực quan).
- Thiết kế chuẩn phong cách Apple: Các mảng màu tối giản, hiệu ứng kính mờ (frosted glass), viền siêu mảnh tinh tế, chuyển động spring mượt mà với Framer Motion, thông báo Dynamic Island và logo KAPPAK chính thức từ `D:\Work\Project_AI\ToolVideo\logo\logo.png`.

### R2. Tự Động Hóa Quy Trình 5 Bước "1 Chạm" Siêu Nhanh
- **Step 1 (Source Video):** Kéo thả tệp video, tự động load ngay vào player xem trước kèm thông số (độ phân giải, thời lượng, fps) mà không cần thao tác phụ.
- **Step 2 (Voice & AI):** Danh sách chọn giọng đọc AI (Vbee / Edge TTS) tinh gọn, nghe thử tức thì với 1 cú click.
- **Step 3 (Blur Regions):** Kéo vẽ trực tiếp trên video để che mờ phụ đề cũ; tự động tính toán tọa độ đưa vào pipeline FFmpeg/CapCut ngầm.
- **Step 4 (Automation):** Nút bấm 1 chạm kích hoạt toàn bộ chuỗi xử lý (Whisper bóc băng, AI dịch ngữ cảnh, tổng hợp giọng nói Vbee/Edge, ghép âm thanh) với thanh tiến độ realtime sống động.
- **Step 5 (Review & Export):** Hiển thị kịch bản tinh gọn, hỗ trợ sửa nhanh và nút xuất video MP4 hoàn thiện hoặc export CapCut project 1 chạm kèm hiệu ứng chúc mừng (confetti).

### R3. Hệ Thống Backend Tự Động & Độc Lập
- Máy chủ backend (FastAPI) phục vụ trực tiếp giao diện Web, tự động liên kết với các công cụ nền (FFmpeg, FFprobe, Local Agent bridge).
- Tệp `run_app.bat` khởi chạy tự động máy chủ và mở trình duyệt web của người dùng mà không cần cấu hình thủ công.

## Acceptance Criteria

### Giao diện & Trải nghiệm Kéo Thả (UX/UI)
- [ ] Màn hình phát video cho phép người dùng kéo thả vẽ hình chữ nhật che mờ trực tiếp lên khung hình; không còn hiển thị bất kỳ ô nhập liệu số X/Y/W/H thủ công nào.
- [ ] Vùng che mờ có thể kéo di chuyển vị trí hoặc kéo góc để đổi kích thước ngay trên video.
- [ ] Logo thương hiệu KAPPAK hiển thị sắc nét ở Header và Favicon tab trình duyệt.
- [ ] Giao diện có Dark/Light mode, hiệu ứng Apple Dynamic Island nổi và chuyển động spring mượt mà.

### Tự Động Hóa & Chức Năng (Functionality)
- [ ] Tải video lên là xem trước được ngay trên trình phát web.
- [ ] Kích hoạt tiến trình Step 4 chạy tự động từ bóc băng đến lồng tiếng, hiển thị tiến độ thời gian thực.
- [ ] Xuất thành công video MP4 hoặc xuất file dự án CapCut Draft hợp lệ.
- [ ] Chạy `run_app.bat` mở thẳng giao diện Web trên trình duyệt.

## 2026-09-15T04:12:10Z

Phát triển hoàn chỉnh tính năng “YouTube Clip Mode” và quy trình Cài đặt / Cập nhật Extension cho dự án VK Dub Studio (ToolVideo) tại `D:\Work\Project_AI\ToolVideo`.

Working directory: D:\Work\Project_AI\ToolVideo
Integrity mode: development

## Requirements

### R1. YouTube In-Player Toolbar & Clip Marker (Extension Content Script)
- Tích hợp `youtubeAdapter.js` trực tiếp trên trang `https://www.youtube.com/watch*` mà không mở trang trung gian hay thay thế controls gốc của YouTube.
- Toolbar nhỏ gọn hiển thị timecode hiện tại, nút "Đặt điểm đầu" (phím `I`), "Đặt điểm cuối" (phím `O`), "Thêm đoạn" (phím `Enter`), "Hủy chọn" (phím `Escape`).
- Đọc trực tiếp từ `HTMLVideoElement` (`currentTime`, `duration`), `videoId`, title và canonical URL.
- Xử lý YouTube SPA navigation (`yt-navigate-finish` / URL change observer) để chuyển video mượt mà không duplicate toolbar / overlay.

### R2. Chrome/Edge Side Panel Clip Manager
- Cung cấp Side Panel chuyên biệt (`apps/browser-extension/sidepanel/`) quản lý danh sách các đoạn đã chọn cho video hiện tại.
- Hiển thị thumbnail, title, video ID, tổng thời lượng.
- Quản lý danh sách clips: hiển thị Start/End/Duration, nút xem thử (seek player YouTube tới đoạn đó), sửa timecode trực tiếp, đổi tên clip, xóa đoạn, kéo thả sắp xếp lại thứ tự, toggle chọn từng đoạn hoặc tất cả.
- Client-side validation: chặn tạo clip trùng lặp hoặc có `start >= end` hoặc vượt quá `duration`.

### R3. Export Configurations & Export Engine
- Lựa chọn xuất:
  1. Xuất từng đoạn thành file riêng lẻ.
  2. Ghép tất cả các đoạn được chọn thành một video duy nhất.
  3. Cắt đoạn và tự động nạp vào timeline/pipeline ToolVideo để tiếp tục lồng tiếng.
- Thiết lập xuất:
  - Chọn thư mục lưu kết quả (hỗ trợ nút "Mở thư mục" sau khi xong).
  - Định dạng container: `mp4` hoặc `mkv`.
  - Chất lượng nguồn: Best, 2160p, 1440p, 1080p, 720p.
  - Chế độ cắt:
    + "Siêu nhanh – giữ nguyên chất lượng": Sử dụng FFmpeg stream-copy (`-c copy`), không re-encode, giữ nguyên FPS/HDR/bitrate gốc (chấp nhận snap keyframe gần nhất, có chú thích rõ cho người dùng).
    + "Chính xác từng khung hình": Cắt chuẩn xác từng frame. Tự động phát hiện và ưu tiên hardware encoder (NVIDIA NVENC `h264_nvenc`/`hevc_nvenc`, Intel QSV `h264_qsv`, AMD AMF `h264_amf`), fallback sang `libx264`/`libx265` chất lượng cao (CRF 17-18). Giữ nguyên FPS và resolution, audio copy hoặc AAC chất lượng cao.

### R4. Source Adapter & Job Execution Service (yt-dlp & FFmpeg)
- Tải nguồn an toàn bằng `yt-dlp`:
  - Tìm kiếm `yt-dlp` theo thứ tự: `YTDLP_PATH` env, `tools/yt-dlp/yt-dlp.exe`, `tools/yt-dlp.exe`, và PATH hệ thống.
  - Tải `bestvideo + bestaudio` rồi remux 1 lần duy nhất cho mỗi video (cache theo `video_id`, `format_id`, `quality`). Tái sử dụng file nguồn đã tải cho mọi clip cắt của cùng video đó.
  - Chỉ dùng `cookies-from-browser` khi người dùng kích hoạt rõ ràng trong UI (video công khai tuyệt đối không gọi cookie).
  - FFmpeg và yt-dlp chạy qua subprocess argv an toàn (không dùng shell command concat).
  - Chuẩn hóa tên file Windows, chống path traversal, dọn file tạm an toàn trong thư mục cache/scratch của ToolVideo.
  - Hỗ trợ hủy job (`CLIP_EXPORT_CANCEL`), retry, và quản lý theo `request_id` (idempotent, chống bấm duplicate).

### R5. Realtime Protocol & Native Bridge Communication
- Mở rộng giao thức Native Messaging / WebSocket hiện có giữa Browser Extension và Local Agent (`local_agent.py`, `protocol.js`, `manifest.json`):
  - Action mới: `YOUTUBE_CONTEXT_SYNC`, `YOUTUBE_SEEK_TO`, `YOUTUBE_PREVIEW_CLIP`, `CLIP_EXPORT_REQUEST`, `CLIP_EXPORT_ACCEPTED`, `CLIP_EXPORT_PROGRESS`, `CLIP_EXPORT_RESULT`, `CLIP_EXPORT_ERROR`, `CLIP_EXPORT_CANCEL`, `OPEN_OUTPUT_FOLDER`.
  - Extension chỉ gửi URL, timecode, metadata và lệnh điều khiển; không chuyển video binary qua Native Messaging.
  - Báo cáo tiến độ realtime: Kiểm tra nguồn → Tải video/audio → Ghép nguồn → Đang cắt clip K/N → Đang ghép → Hoàn tất (kèm % tiến độ, tốc độ download, dung lượng tải, đường dẫn file).
  - Khi reload extension/side panel, khôi phục trạng thái job đang chạy.

### R6. Quy trình Cài đặt & Cập nhật Extension (Installation & Update Tooling)
- Cập nhật manifest (`manifest.json`) hỗ trợ host permission `*://*.youtube.com/*`, `sidePanel`, permissions cần thiết.
- Bổ sung cơ chế / script hoặc giao diện hỗ trợ người dùng cài đặt & cập nhật extension dễ dàng:
  - Tự động đăng ký hoặc kiểm tra Native Messaging Host vào Windows Registry (`Software\Microsoft\Edge\NativeMessagingHosts` và `Software\Google\Chrome\NativeMessagingHosts`).
  - Cung cấp script / hướng dẫn tự động reload hoặc package extension cho Chrome / Edge (developer mode unpacked).
  - Tích hợp trạng thái hoặc nút quản lý Extension / Host vào VK Dub Studio Settings hoặc Browser Bridge Widget.

### R7. Bảo toàn chức năng hiện tại (ChatGPT & Vbee Workflow)
- Giữ nguyên vẹn 100% các tính năng đang chạy: ChatGPT translation bridge, Vbee TTS automation, Native host communication.
- Không ghi đè hay hoàn tác bất kỳ thay đổi chưa commit nào khác trong working tree.

## Acceptance Criteria

### YouTube UI & Navigation
- [ ] Mở bất kỳ video nào trên `https://www.youtube.com/watch?v=...`, toolbar xuất hiện phía dưới/trên player mà không làm đè hay hỏng controls gốc (Play, Volume, Settings, Fullscreen).
- [ ] Phím tắt `I`, `O`, `Enter`, `Escape` hoạt động chính xác theo video playback hiện tại.
- [ ] Chuyển sang video khác qua SPA (bấm gợi ý video YouTube không F5), context video (id, title, duration) và toolbar được cập nhật chính xác, không sinh overlay trùng lặp.
- [ ] Side Panel hiển thị đúng video info, danh sách các đoạn, hỗ trợ kéo thả sắp xếp, xóa, đổi tên, preview nhảy đúng currentTime trên player.
- [ ] Chặn thêm đoạn nếu `start >= end` hoặc vượt quá `duration`.

### Video Processing & Backend
- [ ] Nguồn video tải 1 lần qua `yt-dlp`, cache theo `video_id` và tái sử dụng cho tất cả các đoạn cắt.
- [ ] Chế độ Stream Copy cắt không re-encode video (sử dụng `-c copy`), giữ nguyên HDR/FPS/bitrate.
- [ ] Chế độ Frame-Accurate cắt đúng chính xác timestamp, tự động nhận diện và sử dụng phần cứng khả dụng (NVENC/QSV/AMF), fallback libx264/libx265.
- [ ] Xuất từng đoạn sinh ra các file định dạng `{video_title}_clip_{i}_{start}-{end}.{mp4|mkv}` hợp lệ, tên file được sanitize an toàn cho Windows.
- [ ] Chế độ Merge nối các clip thành 1 file `{video_title}_selected_clips.{mp4|mkv}` mượt mà.
- [ ] Nút "Mở thư mục" và "Đưa vào ToolVideo" hoạt động đúng sau khi xuất xong.
- [ ] Có thể hủy job (`CLIP_EXPORT_CANCEL`) an toàn giữa chừng, tiến trình phụ được kill và file tạm dọn dẹp.

### Extension Installation & Compatibility
- [ ] Có script / lệnh / widget hỗ trợ kiểm tra và đăng ký Native Host cho Chrome & Edge.
- [ ] Extension Manifest V3 load thành công trên Microsoft Edge & Google Chrome mà không có cảnh báo/lỗi manifest.
- [ ] Test suite tự động cho URL parser, validator clip, filename sanitizer, FFmpeg command builder, hardware encoder detector, và Native Protocol vượt qua 100% tests (sử dụng mocks, không phụ thuộc download YouTube thật).
- [ ] Luồng ChatGPT Bridge và Vbee TTS hiện tại hoàn toàn không bị ảnh hưởng.
