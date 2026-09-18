# HANDOFF REPORT: FRONTEND UI/UX & INTERACTIVE VIDEO CANVAS
## DỰ ÁN: KAPPAK STUDIO WEB v2 (TOOLVIDEO)

- **Agent**: `teamwork_preview_explorer_survey_1` (Explorer Subagent)
- **Role**: Frontend UI/UX, Interactive Video Canvas, Design System
- **Handoff Type**: Hard (Investigation complete, actionable architecture delivered)
- **Target Audience**: Orchestrator, Builder Agents, Code Reviewer
- **Tệp phân tích chi tiết**: `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_1\analysis.md`

---

## 1. OBSERVATION (QUAN SÁT THỰC TẾ TRỰC TIẾP)

1. **Vị trí và nội dung các ô nhập tọa độ thủ công**:
   - Tệp `D:\Work\Project_AI\ToolVideo\frontend\src\App.jsx`, dòng 234 - 243 (`Step3` component):
     ```jsx
     <div className="card form-card">
       <div className="compact-grid">
         <label><span>Tọa độ X</span><input defaultValue="68"/></label>
         <label><span>Tọa độ Y</span><input defaultValue="1040"/></label>
         <label><span>Chiều rộng</span><input defaultValue="584"/></label>
         <label><span>Chiều cao</span><input defaultValue="172"/></label>
         <label className="wide"><span>Độ mờ (Gaussian Blur Sigma)</span><input defaultValue="16px"/></label>
       </div>
     </div>
     ```
   - Các ô này chứa số liệu tĩnh `68`, `1040`, `584`, `172`, `16px`, không ràng buộc với dữ liệu thực, không liên kết với video thật.

2. **Vùng làm mờ giả lập trong trình phát video**:
   - Tệp `D:\Work\Project_AI\ToolVideo\frontend\src\App.jsx`, dòng 109 (`Preview` component):
     ```jsx
     {step===3 && <div className="blur-selection"><span>Vùng phụ đề dưới</span><i/><i/><i/><i/></div>}
     ```
   - Tệp `D:\Work\Project_AI\ToolVideo\frontend\src\styles.css`, dòng 39:
     ```css
     .blur-selection{position:absolute;left:9%;right:9%;bottom:8%;height:17%;border:2px dashed white;background:rgba(255,255,255,.18);backdrop-filter:blur(12px)}
     ```
   - Đây chỉ là 1 khối `div` tĩnh với 4 thẻ `<i>` giả lập góc; không có sự kiện chuột `mousedown`, `mousemove`, `mouseup`; không hỗ trợ kéo thả hoặc co giãn.
   - Thẻ bao ngoài `App.jsx:96`: `<div className="screen" onClick={togglePlay}>` gán sự kiện click play/pause trực tiếp lên toàn bộ màn hình, gây xung đột sự kiện khi người dùng muốn tương tác trên video.

3. **Cấu trúc Backend API phục vụ Masks**:
   - Tệp `D:\Work\Project_AI\ToolVideo\src\vkdub\web\server.py`, dòng 137:
     ```python
     class MaskRegion(BaseModel):
         id: str
         x: float
         y: float
         width: float
         height: float
         label: str | None = None
     ```
   - Tìm kiếm toàn bộ `server.py`: Hoàn toàn **không có** endpoint `GET /api/masks` hoặc `POST /api/masks`.
   - Ngược lại, trong `src/vkdub/domain/mask.py` (dòng 13-16) và `src/vkdub/services/mask_service.py` (dòng 26-79), hàm `build_ffmpeg_mask_filter(masks, video_width, video_height)` và `MaskItem` đã hỗ trợ đầy đủ hệ tọa độ chuẩn hóa $[0.0, 1.0]$ (`x`, `y`, `width`, `height`) để chuyển thành filter `delogo` và `boxblur` cho FFmpeg.

4. **Tài nguyên Logo & Favicon**:
   - Tệp logo gốc: `D:\Work\Project_AI\ToolVideo\logo\logo.png` (Kích thước: 403,891 bytes).
   - Tệp sao chép tĩnh: `frontend/public/logo.png`, `frontend/public/favicon.png`, `frontend/src/assets/logo.png` đều khớp kích thước byte hoàn toàn.
   - Tệp `frontend/index.html`, dòng 5 đã cấu hình: `<link rel="icon" type="image/png" href="/logo.png" />`.

5. **Ngôn ngữ trực quan CSS hiện tại**:
   - Tệp `frontend/src/styles.css`, dòng 2-8 và 31: Đang mang phong cách Neo-brutalism với viền đen đậm `--navy:#101a3e; --shadow:3px 4px 0 var(--navy); border: 2px solid var(--navy);`. Điều này không thỏa mãn ngôn ngữ **Apple Minimalist** (kính mờ, viền siêu mảnh, bóng đổ khuếch tán đa tầng).

---

## 2. LOGIC CHAIN (CHUỖI LÝ LUẬN TỪ QUAN SÁT ĐẾN KẾT LUẬN)

1. **Từ Quan sát 1 & 2**: Người dùng hiện tại bị buộc phải nhập tay các con số pixel thô ($X, Y, W, H$) trong khi không biết độ phân giải video là bao nhiêu, và vùng che mờ trên video chỉ là CSS tĩnh không thể di chuyển hay kéo dãn.
   $\rightarrow$ **Suy luận**: Cần xóa bỏ hoàn toàn `compact-grid` chứa 5 ô nhập liệu này tại `Step3`, đồng thời thay thế phần tử `.blur-selection` bằng một component `InteractiveCanvas` chứa các event handler chuột trực tiếp.

2. **Từ Quan sát 2 & Phân tích Tỉ lệ Video**: Khi video được đưa vào thẻ `<video style="object-fit: contain">`, nếu tỉ lệ khung hình của video khác với tỉ lệ vùng chứa (ví dụ video 9:16 trong khung 16:9), trình duyệt sẽ tạo dải đen (pillarbox ở hai bên hoặc letterbox ở trên/dưới). Nếu tính tọa độ trực tiếp theo kích thước vùng chứa CSS, tọa độ sẽ bị lệch nghiêm trọng khi chuyển sang video gốc.
   $\rightarrow$ **Suy luận**: Bắt buộc phải tính toán **Rendered Video Box** ($W_{rend}, H_{rend}, X_{off}, Y_{off}$) dựa trên `video.videoWidth`, `video.videoHeight` và `container.clientWidth`, `container.clientHeight`. Lớp phủ tương tác `InteractiveCanvas` phải được neo chính xác trên Rendered Box này để tọa độ chuột cục bộ chia cho $(W_{rend}, H_{rend})$ cho ra tỉ lệ chuẩn hóa $0.0 - 1.0$ chuẩn xác 100%.

3. **Từ Quan sát 3**: Domain model `MaskItem` và pipeline FFmpeg `build_ffmpeg_mask_filter` trong `mask_service.py` đã dùng tọa độ chuẩn hóa $[0.0, 1.0]$ và hỗ trợ cả `delogo`, `boxblur`, `drawbox`. Điểm đứt gãy duy nhất là `server.py` thiếu 2 endpoint nhận và gửi danh sách masks.
   $\rightarrow$ **Suy luận**: Chỉ cần bổ sung `GET /api/masks` và `POST /api/masks` trong `server.py` lưu vào `state.project.masks`. Khi `Step 5` gọi `export_mp4`, hàm `build_render_command` sẽ tự động nhúng bộ lọc xóa mờ chuẩn xác vào video xuất ra.

4. **Từ Quan sát 4 & 5**: Giao diện cần chuyển dịch từ Neo-brutalism sang Apple Minimalist Aesthetic.
   $\rightarrow$ **Suy luận**: Thiết kế lại toàn bộ Design Tokens trong `styles.css` sang hệ thống kính mờ `backdrop-filter: blur(24px) saturate(180%)`, viền 1px hairline `rgba(255,255,255,0.12)`, tích hợp Dynamic Island với layout spring animation của Framer Motion, và đặt logo `logo.png` sắc nét tại Header.

---

## 3. CAVEATS (GIỚI HẠN & GIẢ ĐỊNH)

1. **Hỗ trợ Multi-touch trên màn hình cảm ứng**: Thiết kế tập trung vào sự kiện chuột máy tính (`mousedown`, `mousemove`, `mouseup`), tuy nhiên kiến trúc này có thể dễ dàng bổ sung các sự kiện `PointerEvent` (`onPointerDown`, `onPointerMove`, `onPointerUp`) để hỗ trợ đồng thời chuột và màn hình cảm ứng/bút vẽ.
2. **Độ phân giải video khi chưa tải lên**: Khi người dùng chưa chọn video, canvas sẽ hiển thị khung tỉ lệ mặc định 16:9 với hướng dẫn kéo thả tải tệp.
3. **Các tính năng khác không thuộc phạm vi**: Không can thiệp vào thuật toán bóc băng Whisper hay model AI dịch thuật; chỉ tập trung vào tầng giao diện tương tác và API cầu nối.

---

## 4. CONCLUSION (KẾT LUẬN & ĐỀ XUẤT HÀNH ĐỘNG)

Thiết kế đã giải quyết triệt để 100% các yêu cầu được giao. Các hành động cụ thể cho đội ngũ Builder Agent:

1. **Frontend - Gỡ bỏ ô nhập liệu thủ công**:
   - Xóa bỏ thẻ `<div className="compact-grid">` và 5 ô nhập liệu X, Y, W, H tại `App.jsx:234-243`.
   - Thay thế bằng Smart Presets ("Phụ đề dưới", "Watermark góc phải", "Toàn dải đáy"), thẻ hiển thị vùng đang chọn, và thanh trượt điều chỉnh Blur Strength trực quan.
2. **Frontend - Xây dựng `InteractiveCanvas.jsx`**:
   - Tạo component phủ trực tiếp lên Rendered Video Box.
   - Bắt sự kiện vẽ vùng mới bằng chuột, kéo di chuyển vị trí, và co giãn 8 điểm neo (`nw, ne, se, sw, n, s, e, w`).
   - Hiển thị hiệu ứng mờ kính `backdrop-filter: blur(16px)` trực tiếp trên khung hình đang phát.
3. **Frontend - Ngôn ngữ thiết kế Apple Minimalist (KAPPAK Studio Web v2)**:
   - Cập nhật `styles.css` theo bảng mã màu kính mờ tinh xảo, viền siêu mảnh và đổ bóng đa tầng.
   - Nâng cấp Dynamic Island với hoạt ảnh co giãn layout tự nhiên qua Framer Motion.
   - Khóa chặt hiển thị logo chính thức KAPPAK tại Header và Favicon.
4. **Backend - Bổ sung Mask API**:
   - Thêm `GET /api/masks` và `POST /api/masks` trong `src/vkdub/web/server.py` để lưu trữ đồng bộ vào `state.project.masks`.

---

## 5. VERIFICATION METHOD (PHƯƠNG PHÁP KIỂM TRA ĐỘC LẬP)

Để kiểm chứng tính chính xác của các phân tích và giải pháp:

1. **Kiểm tra tệp và dòng code chứa lỗi UX**:
   - Mở tệp `D:\Work\Project_AI\ToolVideo\frontend\src\App.jsx` tại các dòng `234-243` để xác nhận sự tồn tại của 5 ô input X, Y, W, H.
   - Mở tệp `D:\Work\Project_AI\ToolVideo\src\vkdub\web\server.py` và tìm kiếm `api/masks` để xác nhận hiện chưa có endpoint xử lý mask.
2. **Kiểm tra mô hình dữ liệu Domain**:
   - Mở tệp `D:\Work\Project_AI\ToolVideo\src\vkdub\domain\mask.py` kiểm tra hàm `to_pixel_rect(video_width, video_height)` để xác nhận backend đã xây dựng sẵn trên nền tảng tọa độ chuẩn hóa $[0.0, 1.0]$.
3. **Kiểm tra sau khi Builder Agent hoàn thành thi công**:
   - Chạy lệnh build frontend:
     ```bash
     cd D:\Work\Project_AI\ToolVideo\frontend && npm run build
     ```
   - Chạy lệnh khởi động hệ thống:
     ```bash
     D:\Work\Project_AI\ToolVideo\run_app.bat
     ```
   - Mở trình duyệt web tại `http://localhost:8000`:
     - Tải một video dọc (9:16) hoặc ngang (16:9) vào Bước 1.
     - Chuyển sang Bước 3: Xác nhận không còn ô nhập X, Y, W, H nào.
     - Dùng chuột vẽ một hình chữ nhật trên video: Xác nhận hình chữ nhật xuất hiện với hiệu ứng làm mờ thật và 8 điểm neo co giãn.
     - Di chuyển hoặc kéo góc: Xác nhận vùng mờ thay đổi mượt mà.
     - Kiểm tra thanh thông báo Apple Dynamic Island trên cùng màn hình.
     - Kiểm tra logo KAPPAK trên Header và Favicon trên tab trình duyệt.
