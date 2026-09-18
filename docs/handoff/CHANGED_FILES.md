# Changed Files — KAPPAK Studio V2 & Phase 1 Downloader

Danh sách các file được thêm mới hoặc chỉnh sửa:

## Thêm mới (NEW)
- `src/kappak/modules/downloader/__init__.py`: Package init cho module Downloader.
- `src/kappak/modules/downloader/service.py`: Service tải video đa nền tảng bằng `yt-dlp`, phát hiện nền tảng, trích xuất metadata, băm SHA-256 và ghi nhận Asset.
- `tests/kappak/test_downloader.py`: Bộ unit test cho Downloader service (phát hiện platform, format duration).
- `src/kappak/ui/icons.py`: Bộ sinh biểu tượng vector SVG sắc nét hỗ trợ chế độ màu động (Normal / Active).
- `src/kappak/ui/widgets/icon_rail.py`: Thanh điều hướng mỏng 74px bên trái với traffic lights macOS và các icon bo góc.
- `src/kappak/ui/widgets/top_bar.py`: Header Apple Glass với Search Pill 580px, status AI, chuông thông báo, avatar người dùng và nút `✦ Ask KAPPAK`.
- `src/kappak/ui/widgets/ask_kappak_drawer.py`: Drawer kính trượt từ cạnh phải hỗ trợ chat và gợi ý prompt nhanh.
- `src/kappak/ui/modules/home_view.py`: View Trang chủ hoàn chỉnh tích hợp Hero banner nữ creator, 6 module cards, và 3 cột dashboard đáy.
- `resources/kappak/background.png`: Bản gốc hình nền visual độ phân giải cao 1672x941 px (1.48 MB) lấy từ thư mục Downloads.
- `resources/kappak/hero_female_creator_hd.png`: Visual nữ creator độ phân giải cao trích xuất từ `background.png`.
- `resources/kappak/thumb_sample_1.png`: Thumbnail mẫu dự án Hành trình Đà Lạt.
- `resources/kappak/thumb_sample_2.png`: Thumbnail mẫu dự án Giới thiệu sản phẩm.
- `resources/kappak/thumb_sample_3.png`: Thumbnail mẫu dự án Apple Minimalist Video.

## Cập nhật (MODIFIED)
- `src/kappak/ui/modules/downloader_view.py`: Xây dựng toàn bộ giao diện Downloader Apple Glass đầy đủ tính năng: input URL, thẻ xem trước, lựa chọn chất lượng/dự án đích, thanh tiến độ và bảng lịch sử tài nguyên.
- `src/kappak/ui/modules/home_view.py`: Nâng cấp ảnh Hero Banner sang phiên bản HD từ `background.png`.
- `src/kappak/ui/theme.py`: Bổ sung toàn bộ tokens màu sắc, bo góc, gradient, và stylesheet Apple Glass V2.
- `src/kappak/ui/shell.py`: Tái cấu trúc cửa sổ chính tích hợp TopBar, IconRail, HomeView, 6 module views, AskKappakDrawer và Footer.

## Giữ nguyên (UNTOUCHED)
- Toàn bộ codebase `src/vkdub/` (ToolVideo cũ) và `apps/browser-extension/`.
- Toàn bộ Core backend Phase 0: `src/kappak/core/`, `src/kappak/domain/`, `src/kappak/jobs/`.
