# Phân Tích Kiến Trúc Backend, API và Pipeline Tự Động Hóa 5 Bước (KAPPAK Studio Web v2)

## 1. Tóm Tắt Tổng Quan (Executive Summary)
Dự án ToolVideo (KAPPAK Studio) sở hữu nền tảng xử lý video, bóc băng phụ đề (Faster-Whisper), dịch ngữ cảnh qua ChatGPT (LocalAgent extension bridge), tổng hợp giọng đọc AI (Vbee / Edge TTS) và xuất dự án CapCut (v360000) rất mạnh mẽ.
Tuy nhiên, qua đợt khảo sát chi tiết backend hiện tại (src/vkdub/web/server.py), chúng tôi phát hiện nhiều **lỗ hổng tích hợp nghiêm trọng (Fatal Bugs)** và các **mắt xích bị đứt đoạn (Missing Pieces)** giữa Web UI và Backend core:
1. **Lỗi tê liệt Step 4**: server.py kết nối vào các signal không tồn tại trên PipelineRunner (unner.overall_progress và unner.pipeline_finished), dẫn đến văng lỗi AttributeError ngay khi nhấn nút chạy 1 chạm.
2. **Lỗi truy cập thuộc tính kịch bản**: server.py cố truy xuất unner.artifacts.bilingual_script vốn không tồn tại trong ArtifactRegistry.
3. **Lỗi render MP4 giả**: Hàm export_mp4() tìm file âm thanh tại workspace_root() / "cache" / "speech.wav" (không bao giờ tồn tại) thay vì master_narration_timeline.mp3, khiến FFmpeg chỉ copy lại video gốc không có tiếng lồng và không có phụ đề.
4. **Lỗi xuất CapCut giả**: Hàm export_capcut() không đồng bộ project.master_voice_path và hash phê duyệt kịch bản, khiến hàm xuất CapCut văng lỗi và trả về một đường dẫn thư mục giả lập (fallback mock).
5. **Đứt gãy vùng che mờ (Step 3)**: Hoàn toàn thiếu các endpoint REST (GET/POST /api/masks) để nhận tọa độ vùng làm mờ từ giao diện kéo thả web canvas, khiến project.masks luôn rỗng khi render.
6. **Thiếu Edge TTS & Voice Preview (Step 2)**: Danh mục giọng đọc liệt kê Hoài My & Nam Minh (Edge TTS) nhưng backend chưa có module tổng hợp Edge TTS và hoàn toàn thiếu endpoint nghe thử giọng (/api/voices/preview).

Dưới đây là báo cáo khảo sát và thiết kế chi tiết toàn diện.

---

## 2. Kiến Trúc Backend & Bản Đồ Thành Phần (Backend Architecture & Map)

### 2.1 Cấu Trúc Mã Nguồn Backend Hiện Tại
`
D:\Work\Project_AI\ToolVideo\
├── app.py                     # Entry point chính: khởi chạy server web FastAPI hoặc desktop GUI
├── run_app.bat                # Script khởi động tự động: set PATH ffmpeg, chạy python app.py
├── pyproject.toml             # Khai báo dependency: PySide6, faster-whisper, httpx, keyring, etc.
├── src/vkdub/
│   ├── web/
│   │   └── server.py          # FastAPI application server, REST endpoints, WebSocket pipeline
│   ├── orchestrator/
│   │   ├── pipeline_runner.py # Worker QThread điều phối 4 bước: 4.1 Whisper -> 4.2 ChatGPT -> 4.3 Script -> 4.4 Vbee
│   │   ├── pipeline_state.py  # PipelineState, SubstepStatus, SubstepInfo, ArtifactRegistry
│   │   └── checkpoint.py      # Lưu và khôi phục trạng thái tiến trình atomic
│   ├── domain/
│   │   ├── mask.py            # Model MaskItem: Tọa độ chuẩn hóa (x, y, w, h: 0.0 - 1.0), mask_type (erase, blur, solid)
│   │   ├── project.py         # Entity Project: video_path, masks, script, voice, master_voice_path
│   │   ├── script.py          # ScriptDocument, ScriptLine
│   │   ├── voice.py           # VoiceSettings, VoiceAsset, audio_key
│   │   └── transcript.py      # SubtitleSegment, Transcript
│   ├── services/
│   │   ├── render_service.py  # build_render_command: Lệnh FFmpeg render MP4 (masks + ass + audio mix ducking)
│   │   ├── mask_service.py    # build_ffmpeg_mask_filter: Chuyển MaskItem -> delogo / boxblur+blend / drawbox
│   │   ├── capcut_export.py   # export_capcut_project: Tạo draft CapCut v360000 đầy đủ track Video, Audio, Text
│   │   ├── audio_mix_service.py # Xử lý audio mix, volume ducking, sample rate 24kHz
│   │   ├── subtitle_service.py# export_ass: Xuất phụ đề định dạng Advanced SubStation Alpha (.ass)
│   │   ├── voice_catalog.py   # VBEE_DEFAULT_CATALOG: Danh mục giọng Vbee chuẩn
│   │   ├── srt_service.py     # parse_srt, write_srt
│   │   └── srt_validator.py   # validate_and_repair_srt, parse_cues, align_and_fill_cues
│   ├── media/
│   │   ├── ffprobe.py         # parse_metadata: Trích xuất duration, width, height, fps, codecs, size
│   │   ├── timeline_audio.py  # build_master_timeline_audio: Ráp âm thanh lồng tiếng vào timeline video gốc
│   │   └── audio_extract.py   # extract_audio: Trích xuất WAV 16kHz mono cho Whisper
│   └── bridge/
│       ├── local_agent.py     # Socket server (port 49814) kết nối Browser Extension (ChatGPT & Vbee Studio)
│       └── ws_framing.py      # Framing giao thức WebSocket thuần cho LocalAgent
`

### 2.2 Cơ Chế Vận Hành Của FastAPI Server (server.py)
- **Quản lý Vòng đời (Lifespan)**:
  Khởi tạo QCoreApplication (để hỗ trợ signal/slot của PySide6 trong các module ngầm) và khởi động LocalAgent lắng nghe trên cổng 49814 nhằm kết nối extension trình duyệt.
- **Quản lý Trạng thái (AppState)**:
  Được lưu trong bộ nhớ: state.project, state.video_metadata, state.active_runner, state.runner_thread, state.ws_clients, state.substeps, state.overall_pct, state.logs, state.subtitles.
- **Phục vụ Static SPA**:
  Mount thư mục rontend/dist/assets và phục vụ fallback SPA index.html cho các route giao diện người dùng.

---

## 3. Khảo Sát Chi Tiết Luồng Xử Lý 5 Bước (5-Step Pipeline Deep-Dive)

### Bước 1: Nguồn Video (Source Video)
- **Luồng hoạt động yêu cầu**:
  1. Người dùng kéo thả file video (MP4, MOV, MKV) vào khu vực xem trước hoặc nhấn nút tải lên.
  2. Giao diện gửi file qua POST /api/media/upload (hoặc gửi đường dẫn file cục bộ qua POST /api/media/select).
  3. Server lưu tệp vào workspace_root() / "uploads" / filename.
  4. Server gọi fprobe trích xuất tức thì: độ phân giải (width x height), thời lượng (duration_str), số khung hình (ps), codec video/audio, dung lượng (size_mb).
  5. Server cập nhật state.project.video_path và trả metadata về client.
  6. Player web tải video ngay lập tức qua URL /api/media/stream?path=....
- **Hiện trạng & Lỗ hổng**:
  - Code probe_file() và parse_metadata() hoạt động tốt.
  - Endpoint /api/media/stream hiện trả về FileResponse(p, media_type="video/mp4"). Trình duyệt hiện đại khi phát video yêu cầu hỗ trợ **HTTP 206 Partial Content (Byte Range Requests)** để tua thanh timeline mượt mà. Cần đảm bảo endpoint hỗ trợ chuẩn header Range: bytes=start-end.
  - Định dạng video: Nếu người dùng tải video MKV hoặc video có audio codec không tương thích trình duyệt (như AC3), trình phát web HTML5 có thể không phát được tiếng hoặc hình. Cần có cờ cảnh báo hoặc transcode proxy siêu nhẹ nếu cần.

### Bước 2: Cấu Hình Giọng Đọc & Nghe Thử AI (Voice & AI)
- **Luồng hoạt động yêu cầu**:
  1. Giao diện hiển thị danh mục các giọng đọc: Vbee (Ngọc Huyền, Tường Vy, Mai Phương, Lan Trinh, Mạnh Dũng) và Microsoft Edge TTS (Hoài My, Nam Minh).
  2. Người dùng tùy chỉnh tốc độ đọc (0.9x, 1.0x, 1.1x, 1.2x, 1.3x).
  3. Người dùng nhấn nút nghe thử (Play Preview) -> Backend lập tức sinh mẫu phát âm ngắn (khoảng 3-5 giây) hoặc lấy từ cache -> Trình duyệt phát trực tiếp âm thanh với độ trễ dưới 1 giây.
- **Hiện trạng & Lỗ hổng**:
  - GET /api/voices: Đã liệt kê giọng Vbee và 2 giọng Edge TTS tĩnh.
  - **THIẾU HOÀN TOÀN**: Không có endpoint /api/voices/preview. Giao diện hiện tại chỉ vẽ waveform CSS giả lập, nhấn play không có bất kỳ âm thanh nào phát ra!
  - **THIẾU HOÀN TOÀN**: Chưa có provider EdgeTTSProvider trong backend. Dự án hiện chỉ có VbeeTTSProvider, CapCutTTSProvider, ElevenLabsTTSProvider, VieNeuLocalProvider.
  - Trong pipeline_runner.py: Khi chạy tạo giọng (bước 4.4), runner mặc định gọi self.local_agent.generate_vbee_sync(...) và ép tên giọng Vbee. Nếu người dùng chọn Edge TTS, tiến trình không biết xử lý thế nào.

### Bước 3: Khung Che Mờ Phụ Đề Cũ (Blur Regions)
- **Luồng hoạt động yêu cầu**:
  1. Người dùng dùng chuột click & kéo trực tiếp trên khung màn hình video để tạo vùng che mờ (hỗ trợ kéo di chuyển vị trí và kéo các handle góc để đổi kích thước).
  2. **Yêu cầu bắt buộc R1**: Xóa bỏ hoàn toàn các trường nhập số tọa độ thủ công (X, Y, Width, Height) và các nút bấm dư thừa.
  3. Tọa độ được tính toán dưới dạng chuẩn hóa  .0 đến 1.0 (resolution-independent), tự động gửi về backend lưu vào state.project.masks.
  4. Backend chuyển đổi MaskItem thành filter graph FFmpeg:
     - erase: Dùng filter delogo để xóa chữ thông minh dựa trên pixel viền.
     - lur: Dùng filter oxblur kết hợp lend smoothstep làm mờ mượt mà.
     - solid: Dùng filter drawbox phủ màu đơn sắc.
  5. Tọa độ này được tự động áp dụng khi render video MP4 hoàn thiện hoặc tạo video ideo-da-xoa-chu.mp4 trong dự án CapCut.
- **Hiện trạng & Lỗ hổng**:
  - Domain model MaskItem (src/vkdub/domain/mask.py) và service uild_ffmpeg_mask_filter (src/vkdub/services/mask_service.py) đã được viết rất chuẩn mực và hỗ trợ tọa độ chuẩn hóa 0.0 - 1.0.
  - **THIẾU HOÀN TOÀN TRÊN FASTAPI**: Trong server.py chỉ có khai báo class MaskRegion(BaseModel), nhưng **không có bất kỳ endpoint nào** (GET /api/masks, POST /api/masks, DELETE /api/masks/{id}). Mảng state.project.masks luôn rỗng!
  - **GIAO DIỆN WEB VI PHẠM YÊU CẦU R1**: rontend/src/App.jsx dòng 234-242 vẫn hiển thị các ô input Tọa độ X, Tọa độ Y, Chiều rộng, Chiều cao và màn hình xem trước chỉ hiển thị một thẻ <div className="blur-selection"> giả lập tĩnh, không cho phép vẽ/kéo/resize bằng chuột!

### Bước 4: Chuỗi Xử Lý Tự Động Hóa 1-Chạm (Automation Execution)
- **Luồng hoạt động yêu cầu**:
  1. Người dùng nhấn nút "Bắt đầu xử lý tự động".
  2. Backend kích hoạt PipelineRunner chạy ngầm trong background thread.
  3. Tiến trình tuần tự thực thi 4 giai đoạn con:
     - **4.1 Bóc băng (Whisper)**: Trích xuất audio 16kHz -> Faster-Whisper nhận diện text và timecode -> xuất file original.srt.
     - **4.2 Dịch ngữ cảnh (AI Translation)**: Gửi file original.srt sang ChatGPT qua LocalAgent (hoặc API) -> đối soát số câu, chuẩn hóa timecode 100% bằng alidate_and_repair_srt -> xuất file 	ranslated.srt.
     - **4.3 Chuẩn bị kịch bản & timeline**: Phân tích câu phụ đề, nạp vào ScriptDocument, khớp thời lượng câu cuối với thời lượng video -> xuất file oice_script.txt.
     - **4.4 Tạo giọng đọc & Timeline Audio**: Gửi kịch bản sang Vbee (hoặc Edge TTS) -> nhận file audio lồng tiếng -> dùng uild_master_timeline_audio đồng bộ khoảng lặng tuyệt đối với timecode video từ  0:00:00.000 -> xuất master_narration_timeline.mp3.
  4. Cập nhật tiến độ realtime qua WebSocket (/ws/pipeline) và Server-Sent Events (SSE) để giao diện hiển thị thanh tiến độ sinh động, icon trạng thái từng substep và console log trực tiếp.
- **Hiện trạng & Các lỗi nghiêm trọng (Fatal Bugs)**:
  - **Lỗi 1 (Văng exception ngay khi bấm Start)**:
    Trong server.py dòng 394-395:
    `python
    runner.overall_progress.connect(on_overall_progress)
    runner.pipeline_finished.connect(on_pipeline_finished)
    `
    Class PipelineRunner (src/vkdub/orchestrator/pipeline_runner.py) **hoàn toàn không có signal overall_progress hay pipeline_finished**! Các signal thực tế là state_changed, substep_updated, rtifact_ready, log_emitted, pipeline_completed, pipeline_failed, pipeline_cancelled. Lời gọi connect làm sập server ngay lập tức với lỗi AttributeError!
  - **Lỗi 2 (Crash khi hoàn tất pipeline)**:
    Trong server.py dòng 368:
    `python
    if runner.artifacts.bilingual_script and runner.artifacts.bilingual_script.is_file():
    `
    Model ArtifactRegistry không có trường ilingual_script (nó chỉ có original_srt và 	ranslated_srt). Việc này gây lỗi AttributeError khi pipeline hoàn thành.
  - **Lỗi 3 (Không cập nhật master_voice_path)**:
    server.py không lắng nghe signal unner.artifact_ready("master_audio", path), dẫn tới state.project.master_voice_path không được cập nhật, làm tê liệt hoàn toàn các bước xuất video tiếp theo.
  - **Lỗi 4 (Thiếu hỗ trợ Edge TTS)**:
    Tiến trình chỉ hỗ trợ Vbee qua local_agent.generate_vbee_sync. Nếu chọn Edge TTS, pipeline sẽ bị treo hoặc thất bại.

### Bước 5: Duyệt Kịch Bản & Xuất Bản (Review & Export)
- **Luồng hoạt động yêu cầu**:
  1. Hiển thị danh sách câu phụ đề song ngữ (Gốc - Dịch) kèm mốc thời gian (start - end).
  2. Cho phép người dùng chỉnh sửa nhanh câu chữ trực tiếp trên bảng.
  3. Nút chốt duyệt kịch bản (Approve Script).
  4. Xuất bản 1 chạm:
     - **Xuất video MP4 hoàn thiện**: Dùng FFmpeg ghép video nguồn, xóa chữ theo vùng làm mờ, ghép audio voice master (kèm hạ âm lượng video gốc - ducking 15%), và add phụ đề ASS sắc nét.
     - **Xuất dự án CapCut Draft**: Tạo thư mục draft CapCut v360000 hoàn chỉnh với 3 track độc lập (Video đã xóa chữ, Voice tiếng Việt nguyên vẹn từ 00:00:00, Phụ đề text tiếng Việt từng câu khớp timecode).
     - Bắn hiệu ứng pháo hoa ăn mừng (canvas-confetti) khi xuất thành công.
- **Hiện trạng & Các lỗi nghiêm trọng (Fatal Bugs)**:
  - **Lỗi 1 (MP4 Render Copy Gốc)**:
    Trong server.py dòng 485:
    `python
    speech_wav = workspace_root() / "cache" / "speech.wav"
    if not speech_wav.is_file():
        cmd = [ffmpeg_bin, "-y", "-i", str(state.project.video_path), "-c:v", "libx264", "-c:a", "aac", str(output_file)]
    `
    Đường dẫn cache/speech.wav không bao giờ tồn tại vì pipeline tạo ra file master_narration_timeline.mp3 trong thư mục export/! Hậu quả là export_mp4() luôn chạy nhánh fallback, chỉ đơn thuần copy video gốc mà không hề lồng tiếng, không làm mờ và không có phụ đề!
  - **Lỗi 2 (CapCut Export Fake Result)**:
    Hàm export_capcut_project kiểm tra project.require_approval() và project.voice_ready. Vì server.py không gán pproved_revision_hash và master_voice_path trên state.project, hàm ném ValueError("Cần video, kịch bản đã duyệt và đủ voice trước khi xuất CapCut.").
    server.py bắt ngoại lệ này và trả về đường dẫn thư mục giả lập:
    allback_path = str(export_dir / f"KAPPAK_{state.project.video_path.stem}")
    Người dùng tưởng đã xuất thành công nhưng thực tế không hề có project CapCut nào được tạo ra!
  - **Lỗi 3 (Không lưu kịch bản đã sửa vào Project)**:
    Khi người dùng sửa phụ đề và gọi POST /api/review/subtitles, server.py chỉ cập nhật mảng state.subtitles mà không cập nhật lại state.project.script và ghi đè lại file 	ranslated.srt. Do đó, khi xuất MP4 hay CapCut, những chỉnh sửa của người dùng hoàn toàn bị bỏ rơi!

---

## 4. Bảng Đối Soát Chức Năng (Existing vs Broken vs Missing)

| STT | Chức Năng | Thành Phần Phụ Trách | Hiện Trạng | Đánh Giá & Giải Pháp Cần Thực Hiện |
|---|---|---|---|---|
| 1 | Upload / Phân tích video | POST /api/media/upload, fprobe.py | Hoạt động | Cần bổ sung hỗ trợ Byte Range streaming cho GET /api/media/stream |
| 2 | Danh mục giọng đọc | GET /api/voices, oice_catalog.py | Hoạt động | Danh mục Vbee & Edge TTS đã có; cần thêm mô tả chi tiết |
| 3 | Nghe thử giọng đọc tức thì | POST /api/voices/preview | **THIẾU** | Cần xây dựng endpoint preview, sinh mẫu audio 3s qua Edge TTS / Vbee cache |
| 4 | Bộ tổng hợp Edge TTS | kdub.providers.edge_tts | **THIẾU** | Cần triển khai provider Edge TTS (qua WebSocket endpoint của Microsoft Bing hoặc thư viện thuần) |
| 5 | Quản lý vùng làm mờ REST | /api/masks (GET/POST/DELETE) | **THIẾU** | Cần tạo các endpoint quản lý MaskRegion, map chuẩn xác với state.project.masks |
| 6 | Vẽ vùng che mờ trên video | Frontend Interactive Canvas | **THIẾU** | Xóa sạch các ô nhập số X/Y/W/H; viết component canvas kéo/thả/resize trực tiếp trên video |
| 7 | Chạy tự động 1 chạm | POST /api/pipeline/start | **GÃY (CRASH)** | Sửa kết nối signal unner.substep_updated, unner.state_changed, unner.pipeline_completed |
| 8 | Cập nhật tiến độ realtime | WebSocket /ws/pipeline | Hoạt động | Thêm kênh fallback Server-Sent Events (/api/pipeline/events) |
| 9 | Hỗ trợ Edge TTS trong Pipeline | pipeline_runner.py (bước 4.4) | **THIẾU** | Thêm nhánh tổng hợp âm thanh bằng Edge TTS nếu provider là edge_tts |
| 10 | Bóc băng Whisper tự động | pipeline_runner.py (bước 4.1) | Hoạt động | Sử dụng Faster-Whisper GPU/CPU tự động trích xuất SRT |
| 11 | Dịch ngữ cảnh AI | pipeline_runner.py (bước 4.2) | Hoạt động | Tích hợp ChatGPT qua LocalAgent extension bridge + validation timecode |
| 12 | Tạo Master Timeline Audio | kdub.media.timeline_audio | Hoạt động | Đã căn chuẩn khoảng lặng từ 00:00:00.000 |
| 13 | Đồng bộ kịch bản duyệt | POST /api/review/subtitles | **LỖI** | Cần chuyển đổi subtitles thành ScriptDocument cập nhật state.project.script |
| 14 | Duyệt kịch bản | POST /api/review/approve | **THIẾU ĐỒNG BỘ** | Cần set state.project.approved_revision_hash = state.project.revision_hash |
| 15 | Xuất video MP4 hoàn thiện | POST /api/export/mp4 | **GÃY (FAKE)** | Sửa đường dẫn sang master_narration_timeline.mp3, tạo phụ đề ASS và áp dụng masks |
| 16 | Xuất dự án CapCut Draft | POST /api/export/capcut | **GÃY (FAKE)** | Đồng bộ trạng thái duyệt và voice master; gọi hàm export_capcut_project thật |

---

## 5. Đặc Tả Chi Tiết Hợp Đồng API (API Contracts & Schemas)

### 5.1 Nhóm Media & Video (Step 1)
- **POST /api/media/upload**: Tải file video lên máy chủ.
  - Request: multipart/form-data với trường ile: UploadFile.
  - Response (200 OK):
    `json
    {
      "status": "ok",
      "metadata": {
        "path": "D:\\Work\\Project_AI\\ToolVideo\\uploads\\sample.mp4",
        "filename": "sample.mp4",
        "duration": 45.2,
        "duration_str": "00:45",
        "width": 1080,
        "height": 1920,
        "resolution": "1080 × 1920",
        "fps": 30.0,
        "video_codec": "h264",
        "audio_codec": "aac",
        "size_bytes": 15728640,
        "size_mb": 15.0
      }
    }
    `
- **POST /api/media/select**: Chọn tệp video đã có trên ổ đĩa.
  - Request Body: {"path": "D:\\Videos\\my_short_drama.mp4"}
  - Response: Cấu trúc tương tự như /api/media/upload.
- **GET /api/media/stream**: Stream nội dung video phục vụ preview HTML5.
  - Query Params: path (tùy chọn, mặc định lấy video hiện tại).
  - Headers: Hỗ trợ Range: bytes=start-end.
  - Response: 206 Partial Content (hoặc 200 OK), Content-Type ideo/mp4.

### 5.2 Nhóm Giọng Đọc & Nghe Thử (Step 2)
- **GET /api/voices**: Lấy danh sách giọng đọc hỗ trợ.
  - Response (200 OK):
    `json
    {
      "voices": [
        {"id": "vbee-ngoc-huyen", "name": "Ngọc Huyền (Nữ miền Bắc)", "provider": "vbee", "gender": "female", "desc": "Giọng đọc truyền cảm, phù hợp Short Drama"},
        {"id": "vbee-tuong-vy", "name": "Tường Vy (Nữ miền Nam)", "provider": "vbee", "gender": "female", "desc": "Giọng đọc miền Nam nhẹ nhàng, tự nhiên"},
        {"id": "vi-VN-HoaiMyNeural", "name": "Hoài My (Nữ - Edge TTS)", "provider": "edge_tts", "gender": "female", "desc": "Giọng đọc Microsoft Edge AI trong trẻo, không tốn phí"},
        {"id": "vi-VN-NamMinhNeural", "name": "Nam Minh (Nam - Edge TTS)", "provider": "edge_tts", "gender": "male", "desc": "Giọng đọc Microsoft Edge AI trầm ấm, chuẩn mực"}
      ]
    }
    `
- **POST /api/voices/preview**: Sinh và phát âm thanh nghe thử tức thì.
  - Request Body:
    `json
    {
      "voice_id": "vi-VN-HoaiMyNeural",
      "provider": "edge_tts",
      "speed": "1.1x",
      "sample_text": "Xin chào! Đây là giọng đọc thử nghiệm trên hệ sinh thái KAPPAK Studio."
    }
    `
  - Response (200 OK): Stream file MP3 trực tiếp (Content-Type: audio/mpeg) hoặc trả JSON kèm base64/URL:
    `json
    {
      "status": "ok",
      "audio_url": "/api/voices/preview/stream?cache_id=preview_hoaimy_11x",
      "duration_ms": 3200
    }
    `

### 5.3 Nhóm Vùng Che Mờ Tương Tác (Step 3)
- **GET /api/masks**: Lấy danh sách vùng làm mờ hiện tại.
  - Response (200 OK):
    `json
    {
      "masks": [
        {
          "id": "mask-88f12a",
          "name": "Che sub đáy màn hình",
          "mask_type": "blur",
          "x": 0.08,
          "y": 0.82,
          "width": 0.84,
          "height": 0.12,
          "blur_strength": 18,
          "color": "#000000",
          "opacity": 1.0,
          "start_ms": 0,
          "end_ms": 0
        }
      ]
    }
    `
- **POST /api/masks**: Cập nhật toàn bộ danh sách vùng làm mờ từ interactive canvas.
  - Request Body:
    `json
    {
      "masks": [
        {
          "id": "mask-88f12a",
          "name": "Che sub đáy màn hình",
          "mask_type": "blur",
          "x": 0.08,
          "y": 0.82,
          "width": 0.84,
          "height": 0.12,
          "blur_strength": 18
        }
      ]
    }
    `
  - Response: {"status": "ok", "count": 1, "masks": [...]}
- **DELETE /api/masks/{mask_id}**: Xóa một vùng làm mờ.
  - Response: {"status": "deleted", "mask_id": "mask-88f12a"}

### 5.4 Nhóm Tiến Trình Tự Động Hóa 1-Chạm (Step 4)
- **POST /api/pipeline/start**: Kích hoạt chuỗi xử lý ngầm.
  - Request Body (tùy chọn override cấu hình):
    `json
    {
      "voice_id": "vi-VN-HoaiMyNeural",
      "voice_speed": "1.1x",
      "auto_voice": true
    }
    `
  - Response (200 OK): {"status": "started", "message": "Tiến trình tự động hóa đã được khởi chạy."}
- **POST /api/pipeline/cancel**: Dừng tiến trình đang chạy.
  - Response: {"status": "cancelled"}
- **GET /api/pipeline/status**: Thăm dò trạng thái hiện tại (Polling).
  - Response:
    `json
    {
      "running": true,
      "overall_pct": 65,
      "overall_msg": "Đang tổng hợp giọng đọc AI (Vbee/Edge)...",
      "substeps": [
        {"id": "4.1", "name": "Bóc băng phụ đề gốc (Whisper)", "status": "SUCCESS", "progress": 100, "message": "Hoàn thành nhận diện 28 câu thoại"},
        {"id": "4.2", "name": "Dịch ngữ cảnh (ChatGPT qua Edge)", "status": "SUCCESS", "progress": 100, "message": "Đã dịch và khớp 100% timecode"},
        {"id": "4.3", "name": "Chuẩn bị kịch bản & timeline", "status": "SUCCESS", "progress": 100, "message": "Kịch bản sẵn sàng (28 câu)"},
        {"id": "4.4", "name": "Tạo giọng đọc (Hoài My 1.1x)", "status": "RUNNING", "progress": 60, "message": "Đang tổng hợp câu 17/28..."}
      ],
      "logs": ["[4.1] Đã nhận diện toàn bộ 28 câu thoại", "..."]
    }
    `
- **WebSocket /ws/pipeline**: Kênh cập nhật thời gian thực 2 chiều.
  - Frame gửi từ Server:
    - Substep update: {"type": "substep", "step_id": "4.4", "status": "RUNNING", "progress": 75, "message": "..."}
    - Overall update: {"type": "overall", "pct": 80, "message": "..."}
    - Finished event: {"type": "finished", "results": {...}, "subtitles": [...]}
    - Failed event: {"type": "failed", "error": "Chi tiết lỗi", "details": "Traceback..."}

### 5.5 Nhóm Duyệt Kịch Bản & Xuất Bản (Step 5)
- **GET /api/review/subtitles**: Lấy danh sách câu kịch bản song ngữ.
  - Response (200 OK):
    `json
    {
      "subtitles": [
        {
          "id": 1,
          "start_time": "00:00:01,200",
          "end_time": "00:00:03,800",
          "source_text": "今天的天气真不错，我们出去走走吧。",
          "target_text": "Thời tiết hôm nay thật đẹp, chúng ta cùng ra ngoài đi dạo nhé."
        }
      ],
      "approved": true
    }
    `
- **POST /api/review/subtitles**: Lưu kịch bản đã chỉnh sửa của người dùng.
  - Request Body: {"subtitles": [...]}
  - Logic backend: Cập nhật state.subtitles, parse lại thành ScriptDocument, lưu vào state.project.script và ghi đè 	ranslated.srt.
- **POST /api/review/approve**: Chốt duyệt kịch bản để chuẩn bị xuất bản.
  - Response: {"status": "approved"}
- **POST /api/export/mp4**: Xuất video MP4 hoàn thiện.
  - Request Body:
    `json
    {
      "burn_subtitles": true,
      "apply_masks": true,
      "ducking_volume": 0.15,
      "voice_volume": 1.0
    }
    `
  - Response (200 OK):
    `json
    {
      "status": "ok",
      "path": "D:\\Work\\Project_AI\\ToolVideo\\export\\KAPPAK_Render_sample.mp4",
      "filename": "KAPPAK_Render_sample.mp4",
      "size_mb": 24.8
    }
    `
- **POST /api/export/capcut**: Xuất dự án CapCut Draft (v360000).
  - Response (200 OK):
    `json
    {
      "status": "ok",
      "path": "C:\\Users\\khucv\\AppData\\Local\\CapCut\\User Data\\Projects\\com.lveditor.draft\\VKDub 20260915-123456-ABCDEF",
      "draft_id": "ABCDEF12-3456-7890-ABCD-EF1234567890",
      "video_segments": 1,
      "audio_segments": 1,
      "caption_segments": 28
    }
    `

---

## 6. Giải Pháp & Kế Hoạch Hiện Thực Hóa (Implementation Blueprint)

### 6.1 Sửa Triệt Để Các Lỗi Tê Liệt Trong src/vkdub/web/server.py
1. **Chuẩn hóa kết nối Signal**:
   Thay thế việc kết nối vào các signal không tồn tại bằng:
   `python
   runner.substep_updated.connect(on_substep_updated)
   runner.state_changed.connect(on_state_changed)
   runner.artifact_ready.connect(on_artifact_ready)
   runner.pipeline_completed.connect(on_pipeline_completed)
   runner.pipeline_failed.connect(on_pipeline_failed)
   runner.pipeline_cancelled.connect(on_pipeline_cancelled)
   `
2. **Tính toán Overall Progress chính xác**:
   Không dựa vào signal overall_progress giả. overall_pct được tính toán dựa trên trọng số của 4 substeps (mỗi bước 25% hoặc trọng số: 4.1=25%, 4.2=25%, 4.3=10%, 4.4=40%).
3. **Đồng bộ Artifact & Subtitles**:
   Khi unner.artifact_ready báo master_audio, lập tức gán state.project.master_voice_path = artifact_path.
   Khi pipeline hoàn tất, đọc trực tiếp từ unner.artifacts.original_srt và unner.artifacts.translated_srt, ghép từng cue theo thứ tự tạo ra state.subtitles.
4. **Sửa logic export_mp4**:
   Lấy âm thanh voice từ state.project.master_voice_path hoặc output_dir / "master_narration_timeline.mp3".
   Tạo phụ đề ASS bằng export_ass(state.project, ass_file).
   Truyền state.project.masks vào uild_render_command.
5. **Sửa logic export_capcut**:
   Đảm bảo state.project.approved_revision_hash = state.project.revision_hash trước khi gọi export_capcut_project.
   Gọi hàm export thực thụ thay vì trả về thư mục mock.

### 6.2 Xây Dựng Module Edge TTS Backend (src/vkdub/providers/edge_tts_provider.py)
Triển khai giao tiếp với Microsoft Edge Read Aloud WebSocket API (wss://speech.platform.bing.com/...) hoặc tích hợp edge-tts:
- Cung cấp phương thức synthesize(text, voice_id, speed, output_path) và preview(voice_id, speed, sample_text).
- Tích hợp vào PipelineRunner bước 4.4: Kiểm tra provider của giọng đọc được chọn; nếu là edge_tts, gọi bộ tổng hợp Edge TTS; nếu là bee, gọi qua LocalAgent bridge.

### 6.3 Thêm Endpoints REST Quản Lý Masks & Voice Preview Trong server.py
- Bổ sung GET /api/masks, POST /api/masks, DELETE /api/masks/{mask_id} lưu trữ trực tiếp vào state.project.masks (dưới dạng MaskItem).
- Bổ sung POST /api/voices/preview và GET /api/voices/preview/stream.

### 6.4 Tinh Chỉnh Giao Diện Frontend Canvas (Phối hợp với UI Developer)
- Xóa bỏ 100% các ô input tọa độ X, Y, W, H tại Step 3.
- Cài đặt Interactive Overlay Canvas trực tiếp đè lên khung <video> trong Preview:
  - Cho phép người dùng rê chuột vẽ vùng hình chữ nhật.
  - Cho phép click chọn vùng, kéo di chuyển vị trí, kéo 4 góc/cạnh để thay đổi kích thước.
  - Tự động tính tỷ lệ normalized (x, y, w, h) / (videoWidth, videoHeight) và gọi API lưu ngầm.
  - Hiển thị danh sách các vùng dạng danh sách gọn gàng (Card pill) với nút bật/tắt mắt xem và nút xóa thùng rác.
