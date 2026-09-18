# UI TARGET SPEC — KAPPAK HOME V2

## 1. Mục tiêu thị giác

Bám sát ảnh `reference/01_TARGET_UI_FEMALE_HERO.png`.

Phong cách:
- Apple-inspired;
- premium;
- sáng;
- glassmorphism nhẹ;
- editorial + technology;
- clean;
- mềm;
- nữ tính vừa đủ;
- không cyberpunk;
- không dashboard admin;
- không neon;
- không quá nhiều panel kỹ thuật.

---

# 2. Tổng thể layout

Desktop wide:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Icon rail │ Top Bar                                                        │
│           ├─────────────────────────────────────────────────────────────────┤
│           │ HERO: text trái + female creator phải                          │
│           ├─────────────────────────────────────────────────────────────────┤
│           │ Module card strip                                              │
│           ├───────────────────────────────┬──────────────┬──────────────────┤
│           │ Recent Projects               │ Continue Work│ AI Suggestion    │
│           └───────────────────────────────┴──────────────┴──────────────────┘
```

Giữ bố cục gần ảnh reference hơn bản V1 trước.

---

# 3. Left Icon Rail

Width khoảng 72–80px.

Chỉ icon.

Các icon:
- Home
- Projects/Data
- Downloader
- Auto Video
- Auto Dub
- Social
- Today
- Help
- Settings

Active item:
- rounded square;
- glass blue;
- icon primary blue.

Không hiển thị text cạnh icon.

---

# 4. Top Bar

Height khoảng 72px.

## Trái
Logo KAPPAK nhỏ gọn.

## Giữa
Search bar dài:

```text
Tìm kiếm công cụ, dự án, mẫu... (Ctrl + K)
```

Style:
- pill;
- white glass;
- border rất nhẹ;
- shadow thấp;
- rộng 520–650px.

## Phải
- `AI Sẵn sàng`
- notification
- avatar
- dropdown

Có thể thêm `✦ Ask KAPPAK` dạng pill nhẹ gần khu vực phải.

---

# 5. Hero chính

Đây là điểm nhấn số 1.

## Chiều cao
Khoảng 310–350px.

## Bố cục
- Text block bên trái ~48–52%.
- Người mẫu nữ bên phải ~48–52%.

## Text

Eyebrow:
```text
KAPPAK STUDIO
```

Headline đề xuất:
```text
Biến ý tưởng thành
nội dung tuyệt vời
```

hoặc:
```text
Làm truyền thông
nhẹ nhàng hơn
```

Dùng 1 đoạn gradient nhẹ ở 1–2 từ cuối.

Subheading:
```text
Tải, sắp xếp, xử lý và xuất bản nội dung.
Nhanh hơn. Gọn hơn. Tập trung hơn.
```

CTA/pill:
```text
✦ Bắt đầu với KAPPAK
```

Có thể giữ handwritten accent nhỏ:
```text
Good Ideas
Better Stories
```

## Người mẫu nữ

Cảm giác:
- Asian young female creator;
- natural;
- premium lifestyle;
- ánh sáng sáng, dịu;
- áo pastel/xanh nhạt/trắng;
- ngồi với laptop;
- biểu cảm tự nhiên;
- không giống ảnh stock doanh nghiệp;
- không glamour quá mức;
- không fashion editorial đậm;
- phù hợp creator/media workspace.

Background:
- white + icy blue;
- blur office/studio rất nhẹ;
- vài glass objects ở xa;
- viết tay trang trí nhẹ kiểu `Create Faster Together`.

Ảnh người mẫu là hero visual chính, không dùng robot/3D sphere làm focal chính trong version này.

---

# 6. Module Cards

Bám theo card strip trong ảnh target.

## Desktop >= 1600px
Cho 6 card trên một hàng nếu đủ chỗ.

```text
Downloader | Data Studio | Auto Video | Auto Dub | Social | Today
```

Nếu viewport hẹp hơn:
- 3x2;
- hoặc horizontal scroll nhẹ nếu framework phù hợp.

## Card style
- height 190–225px;
- glass white;
- border 1px rất nhẹ;
- radius 22–26px;
- icon tile pastel;
- title đậm;
- description 2 dòng;
- arrow button tròn phía dưới.

Không nhét chart/số liệu vào card.

## Tông màu
Downloader: blue  
Data Studio: mint  
Auto Video: violet  
Auto Dub: cyan  
Social: pink  
Today: amber/silver

Màu rất nhạt.

---

# 7. Bottom Content

Giữ đúng tinh thần ảnh target.

## A. Recent Projects
Chiếm khoảng 50–55% chiều ngang.

Hiện 3 project card thumbnail.

Ví dụ:
- Alpha Books Campaign
- Product Review
- TikTok Batch

Mỗi card:
- thumbnail;
- duration nếu là video;
- project name;
- last updated;
- overflow menu.

## B. Continue Work
Khoảng 22–25%.

Nếu chưa có:
```text
Chưa có phiên làm việc gần đây
```

CTA:
```text
+ Tạo dự án mới
```

Nếu có:
- show project gần nhất;
- progress nhỏ;
- `Tiếp tục`.

## C. AI Suggestion / Ask KAPPAK
Khoảng 23–27%.

Không biến thành full AI dashboard.

Có thể hiển thị:
```text
Gợi ý bởi KAPPAK
```

Ví dụ:
```text
Bạn có 8 video mới tải nhưng chưa đưa vào project.
```

CTA:
```text
Xem ngay
```

Card này click có thể mở Ask KAPPAK.

---

# 8. Ask KAPPAK

Không tạo AI Agent card trong module strip.

Dùng:
```text
✦ Ask KAPPAK
```

ở topbar hoặc floating pill.

Click → right-side glass panel:

```text
┌──────────────────────────────┐
│ ✦ KAPPAK                    │
│ Bạn muốn làm gì?             │
│                              │
│ conversation                 │
│                              │
│ [ Nhập yêu cầu...        ↑ ] │
└──────────────────────────────┘
```

Width 390–430px.

---

# 9. Typography

Ưu tiên:
- Inter;
- SF-like system font;
- Segoe UI fallback.

Hero headline:
- 54–62px;
- weight 700–760;
- letter spacing âm nhẹ.

Card title:
- 19–21px;
- weight 650–700.

Body:
- 14–16px;
- line-height 1.5.

---

# 10. Glass language

Glass phải tinh tế.

Dùng:
- rgba white surfaces;
- background blur nhẹ;
- hairline border;
- shadow mềm;
- pastel tint rất nhạt.

Không dùng:
- blur toàn màn;
- glow mạnh;
- viền neon;
- gradient quá bão hòa.

---

# 11. Motion

- Hero fade-up 8–12px.
- Module cards stagger 40–60ms.
- Card hover translateY -3px.
- Arrow hover translateX 2px.
- Search focus glow rất nhẹ.
- Ask panel slide từ phải.

Không bounce mạnh.

---

# 12. Điều phải sửa so với Phase 0 hiện tại

1. Bỏ sidebar text rộng.
2. Thêm hero có người mẫu nữ.
3. Đưa modules thành visual cards.
4. Thêm recent projects.
5. Thêm continue work.
6. Thêm AI suggestion.
7. Giảm vùng trắng chết.
8. Tăng visual hierarchy.
9. Apple Glass rõ hơn.
10. Ask KAPPAK trở thành assistant entry point xuyên suốt.
