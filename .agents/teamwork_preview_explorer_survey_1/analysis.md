# BÁO CÁO NGHIÊN CỨU & THIẾT KẾ KIẾN TRÚC FRONTEND UI/UX & INTERACTIVE VIDEO CANVAS
## DỰ ÁN: KAPPAK STUDIO WEB v2 (TOOLVIDEO)

- **Người thực hiện**: `teamwork_preview_explorer_survey_1` (Explorer Subagent)
- **Ngày thực hiện**: 2026-09-15
- **Thư mục làm việc**: `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_1`
- **Mã định danh dự án**: `ToolVideo - KAPPAK Studio Web v2`
- **Tệp phân tích**: `analysis.md`

---

## 1. TỔNG QUAN & MỤC TIÊU NGHIÊN CỨU (EXECUTIVE SUMMARY)

Yêu cầu cốt lõi của dự án là **tái cấu trúc toàn diện giao diện Web của ToolVideo** sang ngôn ngữ thiết kế **Apple Tối giản & Sang trọng (Apple Minimalist Aesthetic - KAPPAK Studio Web v2)**, đồng thời **loại bỏ triệt để việc người dùng phải nhập thông số tọa độ thủ công (X, Y, W, H)** bằng cách xây dựng **Interactive Video Canvas** (vẽ, kéo thả, co giãn trực tiếp trên màn hình video).

### Các mục tiêu phân tích chính:
1. **Khảo sát hiện trạng frontend**: Rà soát toàn bộ cấu trúc mã nguồn giao diện hiện có (React, Vite, CSS, các tệp mẫu HTML cũ, tài nguyên tĩnh).
2. **Khám phá chi tiết trình phát video & cơ chế làm mờ hiện tại**: Chỉ ra chính xác các dòng code đang chứa ô nhập số X, Y, Width, Height thủ công, các nút bấm dư thừa, và cách trình phát hiển thị khung video.
3. **Thiết kế chi tiết Interactive Video Canvas**:
   - Thuật toán bắt sự kiện chuột (`mousedown`, `mousemove`, `mouseup`) để vẽ vùng chữ nhật mới.
   - Cơ chế kéo di chuyển (drag/move) và 8 điểm neo co giãn (corner & edge resize handles).
   - **Mô hình toán học ánh xạ tọa độ**: Chuyển đổi chính xác giữa tọa độ hiển thị CSS (kèm hiện tượng pillarbox/letterbox do `object-fit: contain`) với hệ tọa độ chuẩn hóa (`0.0` - `1.0`) và độ phân giải gốc của video (`1920×1080`, `1080×1920`, `1280×720`).
4. **Hiện thực hóa ngôn ngữ thiết kế Apple Minimalist (KAPPAK Studio Web v2)**:
   - Hiệu ứng kính mờ frosted glass (`backdrop-blur-2xl`, độ bão hòa, viền hairline siêu mảnh, bề mặt bán trong suốt).
   - Chuyển động vật lý mượt mà bằng **Framer Motion** (spring physics: stiffness, damping).
   - Thanh thông báo trạng thái nổi phong cách **Apple Dynamic Island**.
   - Nhận diện thương hiệu chính thức với logo KAPPAK chuẩn nét từ `D:\Work\Project_AI\ToolVideo\logo\logo.png` và favicon tab trình duyệt.
   - Chế độ Dark/Light mode tối giản, chuyển đổi êm dịu.
5. **Kiến trúc mã nguồn đề xuất & Kế hoạch bàn giao**: Phân rã từ mã nguồn nguyên khối hiện tại sang cấu trúc component mô-đun hóa cao, dễ bảo trì, dễ mở rộng.

---

## 2. KHẢO SÁT HIỆN TRẠNG MÃ NGUỒN FRONTEND

### 2.1 Cấu trúc thư mục frontend hiện tại
Qua kiểm tra thư mục `D:\Work\Project_AI\ToolVideo\frontend`, cấu trúc ghi nhận:
```
D:\Work\Project_AI\ToolVideo\frontend\
├── dist\                    # Thư mục build tĩnh mà FastAPI server.py đang mount
│   ├── assets\
│   ├── favicon.png
│   ├── index.html
│   └── logo.png
├── node_modules\            # Thư viện npm đã được cài đặt đầy đủ
├── parts\                   # Các đoạn mã HTML cắt nhỏ từ phiên bản tĩnh trước đó
│   ├── part1_head.html
│   ├── part2_nav.html
│   ├── part3_hero.html
│   ├── part4a_app_header_stepper.html
│   ├── part4b_app_preview.html
│   ├── part4c_app_context_steps.html
│   ├── part5_logo_audit.html
│   └── part6_workflow_footer.html
├── public\                  # Tài nguyên tĩnh công khai (logo.png, favicon.png)
├── src\                     # MÃ NGUỒN CHÍNH CỦA ỨNG DỤNG SPA HIỆN TẠI
│   ├── assets\
│   │   └── logo.png
│   ├── App.jsx              # 614 dòng - Toàn bộ logic 5 bước và Preview gom chung
│   ├── icons.jsx            # 69 dòng - Toàn bộ vector SVG icons
│   ├── main.jsx             # 5 dòng - Entry point React DOM render
│   └── styles.css           # 175 dòng - Hệ thống styling theo phong cách Neo-brutalism cũ
├── index.html               # Tệp template HTML chính của Vite
├── index.legacy.html        # Tệp HTML cũ nguyên khối dung lượng 4.9MB
├── package.json             # Cấu hình dependency (React, Vite, Framer Motion, canvas-confetti)
└── vite.config.js           # Cấu hình cổng dev 5173 và proxy tới FastAPI backend 8000
```

### 2.2 Đánh giá các thư viện & công nghệ đang có
Trong `frontend/package.json`:
- **React 18/19 & ReactDOM**: Đang hoạt động chuẩn.
- **Vite 6**: Công cụ đóng gói siêu tốc, hỗ trợ HMR (Hot Module Replacement).
- **framer-motion (`^13.3.0`)**: Thư viện hoạt ảnh mạnh mẽ nhất của hệ sinh thái React, sẵn sàng cho các hiệu ứng spring Apple.
- **canvas-confetti (`^1.9.4`)**: Đã tích hợp cho hiệu ứng chúc mừng Step 5 khi xuất video thành công.
- **Vite Proxy (`vite.config.js`)**:
  ```javascript
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true }
    }
  }
  ```
- **Máy chủ Backend FastAPI (`src/vkdub/web/server.py`)**:
  - Khi người dùng chạy ứng dụng thông thường bằng `run_app.bat`, lệnh `python app.py` kích hoạt `run_server()` tại cổng 8000.
  - `server.py` kiểm tra thư mục `frontend/dist`. Nếu có, nó tự động mount các tệp tĩnh và phục vụ SPA tại đường dẫn gốc `http://localhost:8000`.

---

## 3. KHẢO SÁT CHI TIẾT VIDEO PLAYER & CƠ CHẾ LÀM MỜ HIỆN TẠI

### 3.1 Những điểm hạn chế nghiêm trọng trong `App.jsx`
Qua phân tích sâu tệp `frontend/src/App.jsx`:

#### A. Khung phát video xem trước (`Preview` - Dòng 74 đến 138):
1. **Lớp hiển thị video tĩnh và phụ thuộc tỉ lệ 16:9 cứng**:
   - Tại `styles.css:37`, class `.screen` có thuộc tính `aspect-ratio: 16/9; overflow: hidden;`.
   - Khi người dùng chọn video dọc (9:16 - định dạng phổ biến nhất của TikTok/Shorts/Reels như `1080×1920`), thẻ `<video>` dùng `object-fit: contain` nên hình ảnh bị co lại ở giữa, xuất hiện 2 dải đen lớn (pillarbox) ở hai bên trái và phải.
2. **Xung đột sự kiện chuột Play/Pause**:
   - Thẻ `<div className="screen" onClick={togglePlay}>` gán sự kiện click chuột trực tiếp để bật/tắt video. Điều này ngăn cản việc kéo chuột vẽ vùng mờ vì bất kỳ thao tác click/drag nào cũng vô tình kích hoạt Play/Pause video.
3. **Vùng làm mờ chỉ là CSS giả lập tĩnh (Mockup Dummy)**:
   - Dòng 109: `{step===3 && <div className="blur-selection"><span>Vùng phụ đề dưới</span><i/><i/><i/><i/></div>}`
   - Class `.blur-selection` tại `styles.css:39` được cố định bằng:
     `position: absolute; left: 9%; right: 9%; bottom: 8%; height: 17%; border: 2px dashed white;`
   - Hoàn toàn không có liên kết với danh sách mask trong state, không thể click, không thể kéo, không thể co giãn, và không hề tính toán tọa độ thật.

#### B. Ô nhập thông số tọa độ thủ công tại `Step3` (Dòng 218 đến 247):
Tại dòng 234 - 243 của `App.jsx`:
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
**Vấn đề UX cực đoan:**
- Người dùng không thể biết video của mình có độ phân giải bao nhiêu (1920x1080 hay 1280x720 hay 720x1280) để "đoán" con số 68 hay 1040.
- Các ô input này hoàn toàn ngắt kết nối với hình ảnh video trực quan.
- Dư thừa danh sách nút bấm cứng nhắc: "Sub dưới", "Toàn khung", "Thêm vùng" không phản ánh trạng thái thực.

#### C. Lỗ hổng kết nối Backend (`server.py`):
- Trong `src/vkdub/web/server.py:137`, schema `MaskRegion` đã được định nghĩa:
  ```python
  class MaskRegion(BaseModel):
      id: str
      x: float
      y: float
      width: float
      height: float
      label: str | None = None
  ```
- Tuy nhiên, trong toàn bộ `server.py` **chưa hề có endpoint `GET /api/masks` hoặc `POST /api/masks`**!
- Trong khi đó, hệ thống lõi backend (`src/vkdub/domain/mask.py` và `src/vkdub/services/mask_service.py`) đã có sẵn thuật toán chuyển đổi tọa độ chuẩn hóa (`0.0 - 1.0`) sang lệnh lọc FFmpeg (`delogo`, `boxblur`, `drawbox`).

---

## 4. BẢN THIẾT KẾ CHI TIẾT INTERACTIVE VIDEO CANVAS (LOẠI BỎ TOÀN BỘ Ô NHẬP LIỆU)

Để thỏa mãn hoàn toàn yêu cầu: *"Xóa bỏ hoàn toàn các trường nhập số tọa độ (X, Y, Width, Height)... Người dùng có thể dùng chuột click và kéo trực tiếp trên khung màn hình video để tạo, di chuyển hoặc thay đổi kích thước vùng che mờ"*.

### 4.1 Mô hình Toán học Ánh xạ Tọa độ (Mathematical Coordinate Mapping)

Để đảm bảo hình chữ nhật vẽ trên trình duyệt khớp chính xác từng pixel với video gốc khi FFmpeg render, ta phải giải quyết bài toán sai lệch tỉ lệ màn hình (Letterbox / Pillarbox).

#### Khái niệm các không gian tọa độ:
1. **Container CSS Space $(W_{cont}, H_{cont})$**: Kích thước vùng chứa của khung phát video trên giao diện web (tính bằng CSS px).
2. **Video Intrinsic Space $(W_{vid}, H_{vid})$**: Độ phân giải thực tế của tệp video (ví dụ: $1920 \times 1080$, $1080 \times 1920$, $1280 \times 720$).
3. **Rendered Video Box $(W_{rend}, H_{rend}, X_{off}, Y_{off})$**: Vùng hiển thị điểm ảnh thực của video bên trong Container khi áp dụng `object-fit: contain`.
4. **Normalized Space $[0.0, 1.0]$**: Không gian tọa độ độc lập độ phân giải (phù hợp tuyệt đối với cấu trúc `MaskItem` của backend).

#### Công thức tính toán Rendered Video Box:
Cho:
- Tỉ lệ khung hình video: $AR_{vid} = \frac{W_{vid}}{H_{vid}}$
- Tỉ lệ khung hình vùng chứa: $AR_{cont} = \frac{W_{cont}}{H_{cont}}$

**Trường hợp 1: $AR_{cont} \ge AR_{vid}$ (Vùng chứa rộng hơn video - xuất hiện cột đen Pillarbox 2 bên)**
Thường gặp khi phát video dọc (Shorts 9:16) trong khung ngang:
- Chiều cao hiển thị: $H_{rend} = H_{cont}$
- Chiều rộng hiển thị: $W_{rend} = H_{cont} \times AR_{vid}$
- Khoảng cách bù dải đen ngang: $X_{off} = \frac{W_{cont} - W_{rend}}{2}$
- Khoảng cách bù dọc: $Y_{off} = 0$

**Trường hợp 2: $AR_{cont} < AR_{vid}$ (Vùng chứa hẹp hơn video - xuất hiện dải đen Letterbox trên/dưới)**
Thường gặp khi phát video siêu rộng (Cinema 21:9) trong khung chuẩn:
- Chiều rộng hiển thị: $W_{rend} = W_{cont}$
- Chiều cao hiển thị: $H_{rend} = \frac{W_{cont}}{AR_{vid}}$
- Khoảng cách bù dải đen ngang: $X_{off} = 0$
- Khoảng cách bù dọc: $Y_{off} = \frac{H_{cont} - H_{rend}}{2}$

#### Thiết kế Lớp Phủ (Canvas Overlay Container):
Thay vì để lớp phủ phủ kín toàn bộ $W_{cont}, H_{cont}$ dẫn đến việc người dùng vẽ vào dải đen vô nghĩa, ta đặt lớp `InteractiveCanvas` có tọa độ CSS tuyệt đối:
```css
position: absolute;
left: ${X_off}px;
top: ${Y_off}px;
width: ${W_rend}px;
height: ${H_rend}px;
pointer-events: auto;
```
Khi đó, mọi tọa độ chuột cục bộ $(x_{local}, y_{local})$ trên Canvas Overlay Container sẽ tương ứng trực tiếp với khung hình video mà không cần phải trừ lại dải đen!

#### Công thức chuyển đổi 2 chiều:
1. **Từ tọa độ chuột trên trình duyệt sang Tọa độ Chuẩn hóa (Normalized Coordinates):**
   $$x_{norm} = \text{clamp}\left(\frac{x_{local}}{W_{rend}}, 0.0, 1.0\right)$$
   $$y_{norm} = \text{clamp}\left(\frac{y_{local}}{H_{rend}}, 0.0, 1.0\right)$$
   $$w_{norm} = \text{clamp}\left(\frac{w_{local}}{W_{rend}}, 0.01, 1.0 - x_{norm}\right)$$
   $$h_{norm} = \text{clamp}\left(\frac{h_{local}}{H_{rend}}, 0.01, 1.0 - y_{norm}\right)$$

2. **Từ Tọa độ Chuẩn hóa sang Tọa độ Điểm ảnh Video Thật (Intrinsic Video Pixels cho FFmpeg/CapCut):**
   $$X_{pixel} = \text{round}(x_{norm} \times W_{vid})$$
   $$Y_{pixel} = \text{round}(y_{norm} \times H_{vid})$$
   $$Width_{pixel} = \text{round}(w_{norm} \times W_{vid})$$
   $$Height_{pixel} = \text{round}(h_{norm} \times H_{vid})$$

3. **Từ Tọa độ Chuẩn hóa sang Tọa độ Hiển thị CSS (Render Box):**
   $$Left_{css} = x_{norm} \times W_{rend}$$
   $$Top_{css} = y_{norm} \times H_{rend}$$
   $$Width_{css} = w_{norm} \times W_{rend}$$
   $$Height_{css} = h_{norm} \times H_{rend}$$

---

### 4.2 Máy trạng thái & Sự kiện tương tác chuột (Mouse Interaction State Machine)

Interactive Canvas hỗ trợ 3 chế độ tương tác mượt mà:

```
               [ Click trên vùng trống ]
       +----------------------------------------> ( DRAWING )
       |                                              |
       |                                              | mouseUp (w>2%, h>2%)
       |                                              v
    ( IDLE ) <--------------------------------- [ Tạo Mask Mới & Chọn ]
       |                                              ^
       |                                              |
       | [ Click trong thân Mask ]                    | [ Click trên 8 điểm neo ]
       +----------------------------> ( DRAGGING )    +----------------------------> ( RESIZING )
       |                                  |           |                                  |
       |                                  | mouseUp   |                                  | mouseUp
       +<---------------------------------+           +<---------------------------------+
```

#### 1. Vẽ vùng mới (Drawing Mode):
- **Bắt đầu (`onMouseDown`)**:
  - Khi click vào nền video (ngoài các mask hiện có), ghi nhận điểm bắt đầu: `startPt = { x: e.clientX, y: e.clientY }`.
  - Thiết lập trạng thái `mode = 'drawing'`. Tạo một hình chữ nhật tạm `tempRect = { x: normX, y: normY, w: 0, h: 0 }`.
- **Kéo rê (`onMouseMove`)**:
  - Tính toán tọa độ hiện tại. Hỗ trợ người dùng kéo theo **mọi hướng** (kéo sang phải/dưới, hoặc kéo ngược lên trên/trái):
    $$x = \min(startNormX, curNormX)$$
    $$y = \min(startNormY, curNormY)$$
    $$w = |curNormX - startNormX|$$
    $$h = |curNormY - startNormY|$$
- **Kết thúc (`onMouseUp`)**:
  - Nếu $w > 0.02$ và $h > 0.02$ (tránh việc click vô tình tạo chấm nhỏ li ti), tạo một `MaskItem` mới với `id = uuidv4()`, thêm vào danh sách và đặt làm vùng đang chọn (`activeMaskId`).

#### 2. Kéo di chuyển vị trí (Dragging / Moving Mode):
- **Bắt đầu (`onMouseDown` trên thân hộp mask)**:
  - Ngăn chặn sự kiện nổi bọt (`e.stopPropagation()`).
  - Ghi nhận `dragOrigin = { clientX, clientY }` và tọa độ ban đầu của mask `initialMask = { x, y }`.
  - Thiết lập con trỏ chuột `cursor: move`.
- **Kéo rê (`onMouseMove`)**:
  - Độ dịch chuyển: $\Delta x = \frac{e.clientX - dragOrigin.clientX}{W_{rend}}$, $\Delta y = \frac{e.clientY - dragOrigin.clientY}{H_{rend}}$.
  - Cập nhật tọa độ mới được giới hạn an toàn trong khung hình:
    $$x_{new} = \max(0.0, \min(1.0 - width, initialX + \Delta x))$$
    $$y_{new} = \max(0.0, \min(1.0 - height, initialY + \Delta y))$$
- **Kết thúc (`onMouseUp`)**: Lưu trạng thái vào danh sách và đồng bộ API.

#### 3. Co giãn 8 hướng bằng điểm neo (8-Handle Resizing Mode):
Trên hình chữ nhật đang chọn, bố trí 8 điểm neo tương tác:
- **4 góc**:
  - `nw` (Tây Bắc): Thay đổi đồng thời $x, y, width, height$. Con trỏ: `nwse-resize`.
  - `ne` (Đông Bắc): Thay đổi đồng thời $y, width, height$. Con trỏ: `nesw-resize`.
  - `se` (Đông Nam): Thay đổi $width, height$. Con trỏ: `nwse-resize`.
  - `sw` (Tây Nam): Thay đổi đồng thời $x, width, height$. Con trỏ: `nesw-resize`.
- **4 cạnh**:
  - `n` (Bắc - cạnh trên): Thay đổi $y$ và $height$. Con trỏ: `ns-resize`.
  - `s` (Nam - cạnh dưới): Thay đổi $height$. Con trỏ: `ns-resize`.
  - `w` (Tây - cạnh trái): Thay đổi $x$ và $width$. Con trỏ: `ew-resize`.
  - `e` (Đông - cạnh phải): Thay đổi $width$. Con trỏ: `ew-resize`.
- **Ràng buộc an toàn**: Đặt kích thước tối thiểu $w_{min} = 0.02$ và $h_{min} = 0.02$ để tránh việc hộp bị lộn ngược khi kéo quá đà.

---

### 4.3 Hiệu ứng Xem Trước Trực Quan Trên Video (Visual Blur Preview)

Một cải tiến UX vượt trội so với các phần mềm truyền thống:
Khi người dùng vẽ hình chữ nhật che mờ trên video, chính phần tử overlay trên web sẽ áp dụng hiệu ứng CSS:
```css
backdrop-filter: blur(16px);
-webkit-backdrop-filter: blur(16px);
background: rgba(255, 255, 255, 0.12);
border: 1.5px solid rgba(0, 113, 227, 0.8);
box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.3), inset 0 0 12px rgba(0,0,0,0.1);
border-radius: 6px;
```
Người dùng ngay lập tức nhìn thấy phụ đề cũ hoặc logo trên video đang phát bị mờ đi chân thực giống hệt như kết quả xuất video cuối cùng!

---

### 4.4 Tái Cấu Trúc Bảng Điều Khiển Bước 3 (Step 3 Control Panel)
Xóa bỏ vĩnh viễn các ô nhập $X, Y, W, H$. Thay thế bằng giao diện điều khiển chuẩn Apple:

1. **Bộ Preset 1-Chạm Nhanh (Smart Presets)**:
   - **Phụ đề dưới (Bottom Sub)**: Tạo tự động vùng `x: 0.05, y: 0.82, w: 0.90, h: 0.14`.
   - **Watermark góc trên phải (Top-Right Logo)**: Tạo tự động vùng `x: 0.74, y: 0.04, w: 0.22, h: 0.08`.
   - **Toàn dải đáy (Full Bottom Strip)**: Tạo tự động vùng `x: 0.0, y: 0.80, w: 1.0, h: 0.18`.
2. **Thẻ Vùng Đang Chọn (Active Region Card)**:
   - Thay vì hiện con số thô, hiển thị dạng huy hiệu thông minh:
     *Ví dụ: "Vùng 01 · Đáy màn hình (1728 × 151 px) · Tỷ lệ 90% × 14%"*
   - Thanh trượt độ mờ trực quan (**Blur Strength Slider**): Điều chỉnh từ `5px` đến `40px` kèm con số hiển thị động.
   - Lựa chọn kiểu che mờ:
     - **Xóa mờ thông minh (Delogo)**: Tự tái tạo điểm ảnh xung quanh (khuyên dùng).
     - **Mờ mịn (Gaussian Blur)**: Làm nhòe phụ đề gốc.
     - **Dải đơn sắc (Solid Color)**: Hộp màu đen/tối che kín hoàn toàn.
3. **Thao tác nhanh**:
   - Nút "Thêm vùng che mới" (chuyển sang chế độ vẽ).
   - Nút "Căn giữa ngang" (Center Horizontally).
   - Nút "Xóa vùng này" (Kèm phím tắt `Delete`/`Backspace`).

---

## 5. THIẾT KẾ PHONG CÁCH APPLE TỐI GIẢN (KAPPAK STUDIO WEB v2)

### 5.1 Bảng màu & Design Tokens (Apple Minimalist System)

Thay thế phong cách Neo-brutalism (viền đen 3px dày cộp, bóng đổ gắt `3px 4px 0`) bằng hệ thống visual tinh tế, mượt mà chuẩn Apple:

| Token | Light Mode (Apple Clean) | Dark Mode (Apple Obsidian) | Ghi chú thiết kế |
|---|---|---|---|
| `--bg-base` | `#fbfbfd` | `#000000` / `#0a0a0c` | Nền trung tính cao cấp chuẩn macOS / iOS |
| `--surface-glass` | `rgba(255, 255, 255, 0.75)` | `rgba(26, 26, 30, 0.75)` | Kính mờ `backdrop-filter: blur(24px) saturate(180%)` |
| `--surface-subtle` | `rgba(0, 0, 0, 0.03)` | `rgba(255, 255, 255, 0.05)` | Bề mặt phụ mờ nhạt |
| `--border-hairline`| `rgba(0, 0, 0, 0.08)` | `rgba(255, 255, 255, 0.12)` | Viền siêu mảnh 1px thanh thoát |
| `--border-focus`   | `rgba(0, 113, 227, 0.4)` | `rgba(41, 151, 255, 0.5)` | Viền sáng khi active |
| `--text-primary`   | `#1d1d1f` | `#f5f5f7` | San Francisco deep ink |
| `--text-secondary` | `#86868b` | `#a1a1a6` | Xám mờ phụ |
| `--accent-blue`    | `#0071e3` (Apple Blue) | `#2997ff` | Màu thương hiệu chủ đạo |
| `--accent-green`   | `#34c759` (Apple Emerald) | `#30d158` | Trạng thái sẵn sàng / hoàn thành |
| `--shadow-diffuse` | `0 8px 32px rgba(0,0,0,0.06)` | `0 12px 40px rgba(0,0,0,0.5)` | Đổ bóng đa tầng khuếch tán mềm |

---

### 5.2 Thanh Thông Báo Apple Dynamic Island

Dynamic Island là điểm nhấn công nghệ cao của KAPPAK Studio Web v2:
- **Vị trí**: Nằm cố định ở chính giữa mép trên màn hình (`position: fixed; top: 16px; left: 50%; transform: translateX(-50%)`).
- **Chất liệu**: Kính đen sâu obsidian `rgba(15, 15, 18, 0.92)`, bo tròn hoàn hảo `border-radius: 9999px`, viền ánh sáng `1px solid rgba(255, 255, 255, 0.18)`, đổ bóng nổi `0 12px 36px -4px rgba(0, 0, 0, 0.5)`.
- **Hình thái động (Layout Morphing với Framer Motion)**:
  1. **Trạng thái Chờ / Sẵn sàng (Idle)**:
     - Kích thước gọn nhẹ: $190 \times 36 \text{ px}$.
     - Chấm xanh ngọc neon phát sáng nhẹ (`box-shadow: 0 0 10px #34d399`) kèm nhãn `KAPPAK v2 · Sẵn sàng`.
  2. **Trạng thái Tiến trình đang chạy (Processing - Step 4 / Render)**:
     - Tự động co giãn mượt mà sang kích thước rộng: $380 \times 44 \text{ px}$ bằng vật lý spring (`stiffness: 420, damping: 28`).
     - Hiển thị spinner xoay siêu nhỏ, tên bước đang chạy (ví dụ: *"Bóc băng Whisper (42%)"*), và thanh tiến độ mỏng $3\text{px}$ phát sáng gradient.
  3. **Trạng thái Thành công (Success)**:
     - Biểu tượng checkmark xanh bật nảy nhẹ, kèm thông báo thành công và kích hoạt hiệu ứng pháo giấy Confetti rơi rực rỡ.
  4. **Trạng thái Cảnh báo / Lỗi (Alert)**:
     - Chấm đỏ cảnh báo pulse nhịp điệu, thông điệp lỗi ngắn gọn, dễ hiểu.

---

### 5.3 Hoạt Ảnh Vật Lý Spring (Framer Motion Transitions)

Thay vì chuyển cảnh giật cục, mọi thành phần trong KAPPAK Studio Web v2 đều được cấu hình tham số vật lý Apple:
```javascript
export const appleSpring = {
  type: "spring",
  stiffness: 380,
  damping: 30,
  mass: 0.8
};
```
- **Chuyển đổi giữa 5 Bước**: Khung bên phải sử dụng `<AnimatePresence mode="wait">` với hiệu ứng:
  `initial={{ opacity: 0, y: 12, scale: 0.98 }}`
  `animate={{ opacity: 1, y: 0, scale: 1 }}`
  `exit={{ opacity: 0, y: -8, scale: 0.98 }}`
- **Nút bấm & Card**: Phản hồi xúc giác trực quan:
  `whileHover={{ scale: 1.015, y: -1 }}`
  `whileTap={{ scale: 0.985 }}`

---

### 5.4 Tích Hợp Logo Thương Hiệu KAPPAK Chính Thức

1. **Nguồn tệp gốc**:
   - `D:\Work\Project_AI\ToolVideo\logo\logo.png` (Kích thước 403.891 bytes).
   - Tệp đã có sẵn trong `frontend/public/logo.png`, `frontend/public/favicon.png` và `frontend/src/assets/logo.png`.
2. **Hiển thị tại Header**:
   - Hiển thị hình ảnh logo với kích thước $40 \times 40 \text{ px}$, bo tròn góc mềm mại $10\text{px}$, đổ bóng nhẹ $0\ 2\text{px}\ 8\text{px}\ \text{rgba}(0,0,0,0.12)$.
   - Text thương hiệu: Chữ `KAPPAK` đậm nét, kèm sub-label `STUDIO WEB v2` viết hoa với tracking dãn cách chữ sang trọng (`letter-spacing: 0.2em`).
3. **Favicon Tab Trình Duyệt**:
   - Đã cấu hình thẻ `<link rel="icon" type="image/png" href="/logo.png" />` trong `index.html`. Đảm bảo logo KAPPAK hiển thị sắc nét trên tab Google Chrome / Microsoft Edge.

---

## 6. THIẾT KẾ ĐỒNG BỘ BACKEND & PIPELINE

### 6.1 Bổ sung Endpoints Quản lý Mask trong `src/vkdub/web/server.py`
Để Canvas trên Frontend lưu trữ và kích hoạt đúng vùng che trong FFmpeg, máy chủ FastAPI cần bổ sung 2 endpoints:

1. **`GET /api/masks`**:
   - Trả về danh sách vùng che hiện có trong `state.project.masks`.
   - Cấu trúc phản hồi:
     ```json
     {
       "status": "ok",
       "masks": [
         {
           "id": "mask-1",
           "name": "Vùng phụ đề dưới",
           "mask_type": "erase",
           "x": 0.05,
           "y": 0.82,
           "width": 0.90,
           "height": 0.14,
           "blur_strength": 16
         }
       ]
     }
     ```
2. **`POST /api/masks`**:
   - Nhận danh sách mask từ người dùng sau khi vẽ hoặc chỉnh sửa trên Canvas.
   - Chuyển đổi thành các đối tượng `MaskItem` và lưu vào `state.project.masks`.
   - Tự động kiểm tra tính hợp lệ qua hàm `validate_mask(m)` trong `mask_service.py`.

### 6.2 Chuỗi kết nối FFmpeg khi Xuất MP4 (`Step 5`):
Khi người dùng bấm **"Xuất video MP4 hoàn thiện"**:
- `export_mp4()` trong `server.py` gọi `build_render_command(project=state.project, config=cfg, ...)`.
- Trong `render_service.py:59`, nếu `config.apply_masks and project.masks`:
  Hàm `build_ffmpeg_mask_filter(project.masks, video_width, video_height)` sẽ đọc trực tiếp tọa độ chuẩn hóa mà người dùng đã vẽ trên Canvas, nhân với độ phân giải video thực, và áp dụng filter `delogo` hoặc `boxblur` hoàn hảo!

---

## 7. KIẾN TRÚC MÃ NGUỒN ĐỀ XUẤT & BỐ CỤC TỆP TIN (FILE LAYOUT)

Hiện tại toàn bộ logic frontend bị nhồi nhét trong một tệp duy nhất `App.jsx` (614 dòng), gây khó khăn cho việc mở rộng, bảo trì và kiểm thử.
Kiến trúc mô-đun hóa tối ưu được đề xuất:

```
frontend/src/
├── components/
│   ├── Topbar.jsx                 # Header: Logo KAPPAK chuẩn nét, Dark/Light switch, Badge AI
│   ├── Sidebar.jsx                # Menu 5 bước xử lý với trạng thái hoàn thành & icon
│   ├── DynamicIsland.jsx          # Thanh thông báo Apple Dynamic Island nổi linh hoạt
│   ├── VideoPlayer/
│   │   ├── VideoPlayer.jsx        # Thẻ HTML5 <video>, thanh timeline scrubber, nút Play/Pause
│   │   ├── InteractiveCanvas.jsx  # [TRỌNG TÂM] Lớp phủ vẽ chuột, kéo thả, 8 handle co giãn
│   │   ├── MaskRect.jsx           # Hộp hiển thị mờ, hiệu ứng backdrop-blur, viền xanh neon
│   │   └── useVideoCoordinates.js # Hook tính toán rendered box, letterbox/pillarbox, normalized mapping
│   ├── SettingsModal.jsx          # Cửa sổ cài đặt hệ thống kính mờ
│   └── steps/
│       ├── Step1Source.jsx        # Bước 1: Kéo thả tải video, metadata card
│       ├── Step2Voice.jsx         # Bước 2: Danh sách giọng Vbee/Edge TTS, nghe thử tức thì
│       ├── Step3Blur.jsx          # Bước 3: Quản lý vùng che mờ (Smart Presets, KHÔNG X/Y/W/H)
│       ├── Step4Automation.jsx    # Bước 4: Nút 1 chạm kích hoạt Whisper + Dịch + Lồng tiếng
│       └── Step5Export.jsx        # Bước 5: Kịch bản tinh gọn, xuất MP4 / CapCut 1 chạm & Confetti
├── hooks/
│   ├── usePipelineWs.js           # Kết nối WebSocket cập nhật tiến độ thời gian thực
│   └── useTheme.js                # Quản lý Dark/Light mode và lưu localStorage
├── icons.jsx                      # Hệ thống vector icons SVG
├── styles.css                     # Design tokens Apple Minimalist (CSS Variables, Glassmorphism)
├── App.jsx                        # Component gốc điều phối State và chuyển Step
└── main.jsx                       # Entry point
```

---

## 8. KẾT LUẬN & ĐỀ XUẤT HÀNH ĐỘNG CHO AGENT THI CÔNG (ACTIONABLE NEXT STEPS)

1. **Loại bỏ hoàn toàn các ô nhập liệu số**: Xóa sạch `compact-grid` chứa X, Y, Width, Height trong Step 3. Thay bằng các preset thông minh và thanh trượt Blur.
2. **Hiện thực hóa `InteractiveCanvas`**: Triển khai trực tiếp lớp phủ SVG hoặc DOM trên thẻ video, áp dụng chuẩn xác bộ công thức chuyển đổi tọa độ đã nêu ở Mục 4.1.
3. **Cập nhật giao diện theo phong cách Apple**: Thay thế các viền dày 3px đen và bóng đổ thô bằng kính mờ `backdrop-filter: blur(24px)`, viền hairline mảnh mai và đổ bóng khuếch tán.
4. **Bổ sung API `/api/masks`** trên backend `src/vkdub/web/server.py` để khép kín vòng lặp dữ liệu từ lúc người dùng vẽ trên màn hình đến khi FFmpeg xuất video thành phẩm.
