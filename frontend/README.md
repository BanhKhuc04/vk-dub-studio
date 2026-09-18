# KAPPAK UI v2

Bản UI mới tối giản hơn, không dùng emoji/icon chữ.
Toàn bộ icon quan trọng được dựng bằng inline SVG trong `src/icons.jsx`.

## Điểm đã sửa
- Icon SVG đồng bộ, nét mảnh, tối giản.
- Bỏ poster/doodle gây rối ở sidebar.
- Badge `vanhkhuc.dev / Trang Vũ <3` là code HTML + SVG, không phải ảnh.
- Step 5 có khu vực **Xuất bản** rõ ràng:
  - Xuất video MP4 với SVG video-export riêng.
  - Xuất dự án CapCut với SVG CapCut riêng.
- Light/Dark mode.
- Settings tối giản.

## Chạy
```bash
npm install
npm run dev
```

Đây là UI frontend. Hãy nối handler của 2 nút export vào logic FFmpeg/CapCut hiện tại trong ToolVideo.
