---
name: kappak-ui-design
description: Use whenever building, editing, reviewing, or planning work on the KAPPAK Studio frontend (KAPPAK Home / Apple Glass Female Hero V2, or any later screen in the same product). Enforces the KAPPAK design tokens (colors, radius, shadow, blur, spacing, typography), the real product module list (Downloader, Data Studio, Auto Video, Auto Dub, Social, Today, Ask KAPPAK), the list of forbidden actions (do not touch ToolVideo, Browser Extension, SQLite/backend core, do not add microservices/auth/dark-theme-default/3D-robot-hero), and the mandatory checkpoint-and-resume workflow so work can safely continue across separate agent sessions, context resets, or different accounts/machines. Trigger this skill for keywords: KAPPAK, Apple Glass, module card, icon rail, Ask KAPPAK, hero female creator, KAPPAK Home.
---

# KAPPAK UI Design Skill

Bạn đang là agent lập trình làm việc trên frontend của **KAPPAK Studio**. Skill này là luật đứng, áp dụng cho MỌI task UI trong dự án này, không chỉ task đang được giao — vì vậy, đọc kỹ trước khi viết bất kỳ dòng code nào.

## 1. Khi nào áp dụng

Bất cứ khi nào bạn được giao việc:
- sửa/refactor `KAPPAK Home` hoặc bất kỳ trang nào dùng ngôn ngữ thiết kế "Apple Glass";
- tạo component mới cho khu vực hero, module card, icon rail, top bar, Ask KAPPAK panel;
- review code UI đã có để chấm điểm "đúng chuẩn design" hay chưa.

Nếu task không liên quan UI (backend, DB, script), skill này KHÔNG áp dụng — không tự ý mở rộng phạm vi sang backend.

## 2. Design tokens — bắt buộc dùng, không tự sáng tác màu/khoảng cách mới

```css
--app-bg: #F5F8FD;
--surface: rgba(255,255,255,.76);
--surface-strong: rgba(255,255,255,.90);
--text: #0A1738;
--text-2: #66779C;
--primary: #2777FF;
--primary-soft: #E7F1FF;
--border: rgba(76,104,153,.10);

--blue: rgba(223,238,255,.72);
--mint: rgba(219,250,240,.68);
--violet: rgba(237,225,255,.64);
--cyan: rgba(221,246,250,.66);
--pink: rgba(255,228,241,.64);
--amber: rgba(255,239,214,.66);
```

Radius: hero 30px · module-card 24px · bottom-card 22px · icon-tile 20px · search/pill 999px.

Shadow (default): `0 18px 52px rgba(52,78,130,.08), inset 0 1px 0 rgba(255,255,255,.88)`
Shadow (hover): `0 22px 56px rgba(52,78,130,.12), inset 0 1px 0 rgba(255,255,255,.92)`

Blur: top/search 18–22px · cards 14–20px · Ask panel 24–30px.
Spacing: app gap 18–24px · hero padding 42–52px · card padding 24–28px · bottom-section gap 18–20px.

Typography: Inter / hệ font kiểu SF (`-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif`). Hero headline 54–62px / weight 700–760. Card title 19–21px / weight 650–700. Body 14–16px / line-height 1.5.

Motion: hero fade-up 8–12px một lần khi load; module cards stagger 40–60ms; card hover translateY -3px; arrow hover translateX 2px; search focus glow rất nhẹ; Ask panel slide từ phải. KHÔNG bounce mạnh, KHÔNG lặp lại animation ngoài lúc load/hover/tương tác thật.

Phong cách chung: Apple-inspired, premium, sáng, glass nhẹ, editorial + technology, mềm, nữ tính vừa đủ. KHÔNG cyberpunk, KHÔNG dashboard admin, KHÔNG neon, KHÔNG blur toàn màn, KHÔNG glow mạnh, KHÔNG gradient bão hòa.

## 3. Module & nội dung sản phẩm — dùng đúng cái đang có, không suy diễn từ ảnh reference

Modules hiện tại của KAPPAK: **Downloader, Data Studio, Auto Video, Auto Dub, Social, Today**, cộng entry point **✦ Ask KAPPAK** (không phải một module card, mà là pill ở top bar / floating, mở ra panel bên phải).

Màu tint theo module: Downloader = blue · Data Studio = mint · Auto Video = violet · Auto Dub = cyan · Social = pink · Today = amber/silver. Tất cả rất nhạt, dùng tint ở trên.

Bất kỳ ảnh/tài liệu reference nào đưa vào sau này chỉ là **tham chiếu về bố cục/cảm giác thị giác**, KHÔNG phải nội dung sản phẩm cuối. Không copy tên module, text, hoặc tính năng có trong ảnh nếu nó không khớp danh sách module thật ở trên — nếu nghi ngờ, hỏi lại người giao việc trước khi code.

## 4. Việc KHÔNG được làm (bất biến, áp dụng mọi task UI trong repo này)

- Không sửa `ToolVideo`.
- Không sửa `Browser Extension`.
- Không phá hoặc đổi schema SQLite / backend Core.
- Không thêm Redis/Celery/microservice mới.
- Không thêm hệ thống auth mới.
- Không refactor phần backend không liên quan tới UI đang làm.
- Không dùng dark theme làm mặc định.
- Không dùng robot/3D orb làm hero chính.
- Không biến Home/bất kỳ trang chính nào thành admin dashboard (nhiều panel số liệu, chart dày đặc).
- Không tự tìm/chèn ảnh người thật lấy từ web vào code production nếu chưa rõ bản quyền/model release — nếu cần ảnh người, dùng placeholder rõ ràng và báo lại cho người giao việc quyết định nguồn ảnh.

## 5. Quy trình bắt buộc: checkpoint & resume (để làm việc xuyên nhiều session/account)

Vì agent có thể bị ngắt (hết context, hết token, đổi máy, đổi account), KHÔNG được coi trí nhớ hội thoại là nguồn sự thật. Nguồn sự thật duy nhất là **file trong repo**.

**Trước khi bắt đầu bất kỳ task nào:**
1. Đọc `docs/handoff/PROGRESS.md` nếu tồn tại. Nếu không tồn tại, tạo file này.
2. Đọc `git log --oneline -20` để xác nhận trạng thái thật của code — không tin tưởng tuyệt đối vào những gì PROGRESS.md nói nếu nó có vẻ không khớp code thực tế; nếu lệch, ưu tiên code thật và ghi chú lại sự lệch đó.
3. Xác định task tiếp theo chưa "done" theo `ACCEPTANCE_CHECKLIST.md`/`AGENT_TASK.md` của gói việc đang active.

**Sau khi hoàn thành MỖI task nhỏ (không phải cuối cùng mới ghi một lần):**
1. `git add` + `git commit` với message rõ nghĩa (ví dụ: `ui: convert sidebar to icon rail per V2 spec`).
2. Cập nhật `docs/handoff/PROGRESS.md`: task nào done, task nào pending, task nào bị block và vì sao.
3. Chụp screenshot màn hình hiện tại, lưu vào `docs/handoff/screenshots/`, đối chiếu nhanh với ảnh reference.
4. Tick các dòng tương ứng trong `ACCEPTANCE_CHECKLIST.md`.
5. Tự động đọc tiếp task kế trong `AGENT_TASK.md` và làm tiếp — không cần hỏi lại người dùng nếu task đó không mơ hồ.

**Khi nào phải dừng và không tự làm tiếp:**
- Gặp yêu cầu mơ hồ hoặc mâu thuẫn với mục 3/4 ở trên → dừng, hỏi rõ, KHÔNG tự đoán.
- Ngữ cảnh/token gần hết (chủ động dừng SỚM, đừng chờ bị cắt ngang) → dừng ngay, hoàn tất bước commit + cập nhật PROGRESS.md ở trên trước khi kết thúc, rồi viết báo cáo tóm tắt.
- Đã hoàn thành toàn bộ checklist → viết báo cáo tổng kết, liệt kê rõ những gì đã làm, build/test có pass không, còn gì cần người review bằng mắt.

**Báo cáo cuối mỗi lần dừng (dù dừng vì xong việc, hết token, hay gặp vướng) luôn gồm:**
- Danh sách task đã DONE / PENDING / BLOCKED.
- Trạng thái build & test hiện tại.
- Đường dẫn screenshot mới nhất.
- Việc cụ thể agent phiên sau (có thể ở account khác) cần làm tiếp, theo đúng thứ tự.

Vì PROGRESS.md + git history nằm trong repo, một session mới — kể cả trên account/máy khác — chỉ cần đọc lại 2 nguồn đó là nối tiếp được công việc chính xác, không cần agent "nhớ" hội thoại cũ.
