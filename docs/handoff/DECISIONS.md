# Architecture & Design Decisions — KAPPAK Studio

1. **Tuân thủ bản thiết kế Apple Glass Female Hero V2:**
   - Sử dụng layout 3 tầng chính: Left Icon Rail mỏng (74px), Top Bar với thanh tìm kiếm Pill 580px, và không gian làm việc chính với Hero Card nữ creator.
   - Nền tảng màu sáng sạch `--app-bg: #F5F8FD` kết hợp thẻ kính trắng `#FFFFFF` với viền siêu mỏng `rgba(76, 104, 153, 0.12)` và bo góc lớn (22–28px).

2. **Ánh xạ 6 Module thực tế:**
   - 6 thẻ module trên trang chủ map trực tiếp tới 6 module cốt lõi của KAPPAK: Downloader (Tải nội dung), Data Studio (Thư viện & Dự án), Auto Video (Sáng tạo Video), Auto Dub (Lồng tiếng AI), Social (Mạng xã hội), Today (Tiến độ & Lịch).
   - Không có thẻ AI Agent riêng lẻ trong strip; AI Agent là trợ lý toàn cục `✦ Ask KAPPAK`.

3. **Slide-over Drawer cho Trợ lý `✦ Ask KAPPAK`:**
   - Đặt ở cạnh phải màn hình dưới dạng drawer trượt trong suốt mờ ảo, mở khi nhấn nút trên Topbar, CTA Hero banner hoặc thẻ gợi ý AI, không làm ngắt mạch trải nghiệm workspace.

4. **Vector Icon SVG động qua QSvgRenderer:**
   - Nhúng trực tiếp mã nguồn SVG và render thông qua `QSvgRenderer` để đạt độ sắc nét tuyệt đối trên mọi loại màn hình (Retina / 4K / High-DPI), hỗ trợ đổi màu linh hoạt khi active/hover.

5. **An toàn hệ thống và Cô lập tối đa:**
   - Tuyệt đối không can thiệp vào mã nguồn cũ của ToolVideo (`vkdub`) hoặc Browser Extension.
   - Giữ nguyên cấu trúc database SQLite WAL và Local Job Manager của Phase 0.
