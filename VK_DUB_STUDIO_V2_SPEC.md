# VK DUB STUDIO 2.0 — PRODUCT & IMPLEMENTATION SPEC
## by vanhkhuc

> Source of truth cho bản nâng cấp **VK Dub Studio 2.0**. Không viết lại toàn bộ app nếu code hiện tại vẫn ổn. Ưu tiên: `audit → giữ phần tốt → bỏ rườm rà → refactor có kiểm soát → thêm tính năng → verify`.

## 1. Mục tiêu sản phẩm

VK Dub Studio 2.0 phải cho cảm giác:

```text
SETUP MỘT LẦN
    ↓
CHỌN VIDEO / NHIỀU VIDEO
    ↓
CHỌN NƠI LƯU PROJECT CAPCUT
    ↓
CHỌN NGÔN NGỮ + GIỌNG + TỐC ĐỘ
    ↓
KHOANH VÙNG CẦN LÀM MỜ
    ↓
BẮT ĐẦU XỬ LÝ
    ↓
BÓC BĂNG + GEMINI VIẾT/DỊCH KỊCH BẢN
    ↓
CHECK TRANSCRIPT/KỊCH BẢN
    ↓
DUYỆT
    ↓
TẠO VOICE + CHỈNH ÂM LƯỢNG
    ↓
XUẤT PROJECT CAPCUT
    ↓
MỞ CAPCUT VÀ CHỈNH TIẾP
```

Người dùng không cần hiểu Whisper, FFmpeg, JSON, token, model path hay provider internals.

---

## 2. Quyết định 2.0

### Bỏ khỏi UI 2.0
- ElevenLabs.
- Vbee.
- HWID.
- TikTok Session ID.
- raw API key list.
- FFmpeg/model path ở màn hình chính.
- các stage button kiểu dev panel.

Nếu module Vbee/ElevenLabs cũ đang tách tốt thì có thể giữ dưới dạng legacy/disabled, nhưng không hiển thị và không chạy mặc định.

### Gemini
Gemini là AI mặc định để:
- dịch transcript;
- làm mượt tiếng Việt;
- tạo/biên tập kịch bản theo segment/timestamp;
- tùy chọn viết lại riêng câu được chọn.

Giữ STT local hiện tại nếu đang chạy tốt; Gemini không cần thay STT.

### TTS chỉ tập trung 2 backend

#### A. VieNeu-TTS — mặc định
Repo:
`https://github.com/pnnbao97/VieNeu-TTS`

Mục tiêu:
- local/on-device;
- tiếng Việt;
- default voices;
- voice cloning/custom voice khi backend hỗ trợ;
- không cần cloud API cho local inference.

Ưu tiên open-source **VieNeu-TTS v3 Turbo** nếu tương thích máy người dùng.

#### B. CapCut TTS API — optional / experimental
Repo:
`https://github.com/K07VN/capcut-tts-api`

Mục tiêu:
- voice catalog;
- TTS;
- provider dự phòng.

Phải có health check và fail gracefully vì phụ thuộc upstream/external behavior. Không để app core phụ thuộc backend này.

---

## 3. TTS Provider Architecture

```python
class TTSProvider(Protocol):
    id: str
    display_name: str

    def health_check(self) -> HealthResult: ...
    def list_voices(self) -> list[Voice]: ...
    def preview_voice(self, text: str, voice_id: str, speed: float) -> Path: ...
    def synthesize(self, text: str, voice_id: str, speed: float, output_path: Path) -> Path: ...
```

```text
TTSProvider
├── VieNeuLocalProvider
└── CapCutTTSProvider
```

UI không gọi trực tiếp code third-party repo.

---

## 4. Setup Wizard — chỉ khi cần

Lần đầu:

```text
CHÀO MỪNG ĐẾN VK DUB STUDIO 2.0

1. Gemini
2. Voice Engine
3. CapCut
4. Workspace
5. Kiểm tra hệ thống
```

### Gemini
```text
API Key
[••••••••••••]

Model
[... ▼]

[Kiểm tra kết nối]
```

Yêu cầu:
- test bằng request nhỏ;
- timeout rõ;
- key lưu bằng Windows Credential Manager/keyring;
- không log secret;
- nếu thiếu key: có `Hướng dẫn lấy API Key`;
- nếu đã hợp lệ: lần sau không hỏi lại.

### Voice Engine
```text
(●) VieNeu Local
( ) CapCut TTS

[Kiểm tra]
```

Nếu VieNeu chưa sẵn sàng:
```text
VieNeu chưa sẵn sàng.
[Cài tự động] [Xem hướng dẫn]
```

Nếu CapCut TTS fail:
```text
CapCut TTS hiện không hoạt động.
[Thử lại] [Chuyển VieNeu Local]
```

### CapCut folder
Auto-detect Windows:

```text
%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft
```

Nếu có:
```text
✓ Đã tìm thấy CapCut
[ Dùng thư mục này ] [ Chọn thư mục khác ]
```

Nhớ lựa chọn giữa các lần mở.

### Workspace
Chọn:
- workspace/cache VKDub;
- CapCut Draft Root.

---

## 5. Startup Health Check

Mỗi lần mở app chạy nền:

```text
✓ Gemini
✓ TTS backend
✓ FFmpeg
✓ ffprobe
✓ CapCut folder
✓ Update
```

Nếu tất cả OK: **im lặng, không mở wizard**.

Nếu lỗi: banner có action.

Ví dụ:
```text
⚠ Gemini cần cấu hình lại   [Sửa]
⚠ VieNeu model chưa có      [Cài]
```

Update/network fail không được chặn app.

---

## 6. Persistence — không nhập lại mỗi lần

Nhớ:
- Gemini API key (secret store);
- Gemini model;
- TTS backend;
- VieNeu config/model;
- voice gần nhất;
- speed;
- CapCut draft root;
- workspace root;
- source language;
- target language;
- auto-update preference;
- UI preferences.

Project-specific nhớ:
- video list;
- transcript;
- translated script;
- masks;
- review state;
- TTS cache/files;
- audio gain;
- CapCut export metadata.

---

## 7. Main UI 2.0

Giữ layout 3 vùng nhưng tinh gọn:

```text
┌──────────────────────┬─────────────────────────────────┬────────────────────────┐
│ PROJECT / THIẾT LẬP  │            PREVIEW              │  TRANSCRIPT / KỊCH BẢN │
│                      │                                 │                        │
│ Video list           │                                 │  Segment editor        │
│ CapCut destination   │             VIDEO               │  Validate              │
│ Language             │                                 │  Review                │
│ Voice + speed        │                                 │                        │
│                      │                                 │                        │
│ CTA CHÍNH            │       Timeline / Blur tools     │  DUYỆT                  │
└──────────────────────┴─────────────────────────────────┴────────────────────────┘
```

UI:
- dark hiện đại;
- spacing rộng hơn;
- chữ dễ đọc;
- 1 CTA chính theo state;
- giảm số button luôn hiện.

CTA thay đổi:
```text
BẮT ĐẦU XỬ LÝ
DUYỆT & TẠO VOICE
XUẤT PROJECT CAPCUT
```

Stage cũ chuyển thành status:
```text
✓ Video
✓ Bóc băng
✓ Dịch
● Chờ duyệt
○ Voice
○ CapCut
```

---

## 8. Multi-video / Batch

Một workspace có nhiều video:

```text
[ + THÊM VIDEO ]

01 video_a.mp4    CHƯA XỬ LÝ
02 video_b.mp4    ĐÃ DUYỆT
03 video_c.mp4    ĐÃ XUẤT
```

Cho chọn nhiều:
```text
☑ video_a
☑ video_b
☐ video_c

[ XỬ LÝ ĐÃ CHỌN ]
```

Mỗi video có riêng:
- transcript;
- script;
- masks;
- voice cache;
- CapCut draft.

Có global defaults + per-video override.

---

## 9. Voice UX

Màn chính chỉ cần:

```text
GIỌNG ĐỌC
[ Tên giọng ▼ ]

Tốc độ
[ 1.0x ▼ ]

[ ▶ Nghe thử ]
[ ⚙ Quản lý giọng ]
```

Provider details nằm trong Settings.

---

## 10. Quản lý / tự tạo voice

Settings → Voice:

```text
VOICE ENGINE
VieNeu Local ▼

GIỌNG ĐÃ LƯU
- Voice A
- Voice B

[ + THÊM GIỌNG ]
```

Với VieNeu:
```text
Tên giọng
[ Giọng của tôi ]

Reference Audio
[ Chọn WAV/MP3 ]

Reference text (nếu backend cần)
[ ... ]

[ Tạo / Đăng ký giọng ]
```

Sau đó:
- voice xuất hiện ở dropdown;
- preview;
- persist sau restart;
- rename/delete.

Chỉ dùng reference audio mà user có quyền sử dụng. Không bundle reference giọng của bên thứ ba nếu chưa xác minh quyền.

Với CapCut TTS:
- refresh/search voice catalog;
- favorite;
- không giả định custom voice nếu repo không hỗ trợ.

---

## 11. Ngôn ngữ

```text
Ngôn ngữ gốc
[ Auto / Trung / Anh / Nhật / Hàn / ... ]

Dịch sang
[ Tiếng Việt ]
```

Default target: Vietnamese.

---

## 12. Gemini Script Pipeline

```text
VIDEO
 ↓
STT hiện tại
 ↓
SOURCE TRANSCRIPT
 ↓
GEMINI TRANSLATE + POLISH
 ↓
DRAFT SCRIPT
 ↓
USER REVIEW
```

Gemini phải:
- giữ segment ID;
- giữ timestamp;
- dịch tự nhiên, nói được;
- không tự thêm thông tin;
- giữ tên riêng/số liệu;
- trả structured JSON.

Không áp dụng output nếu JSON lỗi, mất ID, duplicate ID hoặc thiếu segment.

---

## 13. Blur Editor — blur thật, KHÔNG làm tối

Nút:
```text
[ + LÀM MỜ ]
```

Bấm xong rectangle xuất hiện ngay trên video.

Có thể:
- drag;
- resize;
- move;
- delete;
- duplicate;
- set start/end.

**BẮT BUỘC:**
- không black overlay;
- không semi-transparent dark rectangle;
- không giảm brightness để giả blur.

Phải blur pixel thật (Gaussian/box blur) và giữ độ sáng tổng thể gần nguồn.

Data lưu normalized coordinate:

```json
{
  "x": 0.12,
  "y": 0.76,
  "width": 0.70,
  "height": 0.12,
  "start": 2.4,
  "end": 17.8,
  "blur_strength": 18
}
```

Không lưu preview pixel tuyệt đối.

---

## 14. Luồng xử lý

Sau khi user đã:
- add video;
- chọn CapCut folder;
- chọn ngôn ngữ;
- chọn voice/speed;
- khoanh blur;

bấm:

```text
BẮT ĐẦU XỬ LÝ
```

Chạy:
```text
1. Prepare media
2. STT
3. Gemini translate/script
4. Validate
5. STOP ở REVIEW_REQUIRED
```

Không tạo toàn bộ voice trước review.

---

## 15. Review transcript/kịch bản

Right panel:

```text
KỊCH BẢN
126 câu · 0 lỗi · 2 cảnh báo

#001 00:00.00 → 00:02.30
Gốc: ...
Tiếng Việt: ...
[▶]
```

Cho:
- sửa text/timestamp;
- add/delete;
- split/merge;
- search/replace;
- undo/redo;
- click segment → seek preview.

Validation:
- text rỗng;
- timestamp invalid;
- overlap;
- ordering;
- text quá dài so với duration.

---

## 16. Review Gate

```text
☐ Tôi đã kiểm tra transcript/kịch bản

[ DUYỆT & TẠO VOICE ]
```

Khi duyệt:
- lưu revision hash;
- mới được TTS.

Nếu sửa sau approval:
- revoke approval;
- export disabled;
- chỉ invalidate TTS segment thay đổi;
- cần duyệt lại.

---

## 17. TTS + Audio

Sau approval:

```text
Tạo voice 1/126...
...
126/126
```

Cache từng segment.

Nếu sửa 1 câu thì chỉ tạo lại câu đó.

Simple controls:
```text
Voice volume      100%
Original audio     20%
Speed              1.0x

[ Preview Voice ]
```

Không show FFmpeg internals.

---

## 18. CapCut Export — mục tiêu cốt lõi

Không chỉ xuất MP4. Có:

```text
[ XUẤT PROJECT CAPCUT ]
```

Mỗi video → 1 CapCut draft riêng.

Mục tiêu project mở trong CapCut và còn chỉnh được:
- source video;
- generated TTS audio;
- subtitle/caption track;
- timing;
- original/voice volume;
- blur/mask nếu schema đã verify.

### Windows draft root
Thường:
```text
%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft
```

Windows draft thường có:
```text
<draft-id>/
├── draft_content.json
├── draft_meta_info.json
└── ...
```

### BẮT BUỘC: Compatibility Probe
Không hard-code schema mù.

Trước exporter hoàn chỉnh:
1. detect CapCut draft root;
2. chỉ đọc draft user làm schema reference, không sửa;
3. xác định filename/version/schema/timing units;
4. tạo/nhờ user tạo 1 draft test thủ công gồm:
   - 1 video;
   - 1 audio;
   - 1 caption;
   - 1 rectangle blur/mask;
5. so sánh JSON;
6. ghi findings vào `docs/CAPCUT_COMPATIBILITY.md`;
7. chỉ dùng field/ID đã verify hoặc từ library đã test.

Không được tuyên bố blur editable nếu chưa mở thử trong CapCut.

### Safety
Exporter chỉ tạo draft mới với unique ID.
Không sửa/overwrite project CapCut khác.

Sau export:
```text
✓ Đã tạo project CapCut
[ MỞ CAPCUT ] [ MỞ THƯ MỤC PROJECT ]
```

---

## 19. Blur trong CapCut

Mục tiêu: blur rectangle theo timeline và chỉnh tiếp được trong CapCut.

Ưu tiên dùng effect + mask/overlay track tương thích schema local.

Nếu schema blur chưa verify:
- status `PARTIAL`;
- không nói DONE;
- fallback phải ghi rõ.

Tuyệt đối không thay blur bằng black box.

---

## 20. Batch CapCut Export

```text
3 video sẵn sàng
☑ video_a
☑ video_b
☑ video_c

[ XUẤT 3 PROJECT CAPCUT ]
```

Mỗi video:
- unique draft;
- assets riêng;
- progress riêng;
- lỗi một video không phá hai video kia.

---

## 21. Settings 2.0

Tabs:
```text
Chung
AI
Voice
CapCut
Cập nhật
Nâng cao
```

### Chung
- workspace;
- language defaults;
- theme.

### AI
- Gemini key;
- model;
- test connection.

### Voice
- backend;
- model status;
- voices;
- add voice;
- preview/test.

### CapCut
- draft root;
- auto detect;
- compatibility test;
- open folder.

### Cập nhật
- version;
- auto-check;
- check now.

### Nâng cao
- FFmpeg;
- logs;
- cache;
- diagnostics.

---

## 22. Health Model

```python
class HealthResult:
    ok: bool
    code: str
    title: str
    message: str
    action_label: str | None
```

Checks:
- Gemini;
- TTS provider;
- FFmpeg;
- ffprobe;
- CapCut root;
- write permission;
- update.

Nếu OK: silent.
Nếu fail: actionable banner.

---

## 23. Background Tasks

Không block Qt UI thread.

Background:
- STT;
- Gemini;
- TTS;
- CapCut export;
- update check;
- model setup/download.

Có progress, cancel, retry và friendly errors.

---

## 24. Error UX

Không show raw traceback cho user.

Ví dụ:
```text
Không thể dùng Gemini
API key chưa hợp lệ.
[ Mở Cài đặt AI ]
```

```text
VieNeu chưa sẵn sàng
Model chưa được cài.
[ Cài ngay ]
```

```text
Không thể xuất CapCut
Thư mục draft không còn tồn tại.
[ Chọn lại thư mục ]
```

Traceback chỉ ghi log.

---

## 25. Migration từ app hiện tại

Không mất dữ liệu cũ.

Migration v2 giữ:
- transcript;
- translation;
- masks;
- selected video;
- project/cache dùng được.

Vbee/ElevenLabs:
- hide UI;
- config cũ đánh dấu legacy;
- không chạy mặc định.

---

## 26. Research notes đã xác minh (2026-09-04)

### VieNeu-TTS
`https://github.com/pnnbao97/VieNeu-TTS`

Repo hiện mô tả:
- v3 Turbo open-source;
- local CPU ONNX path;
- default voices;
- instant voice cloning từ reference audio;
- Python SDK;
- Apache 2.0 cho repo hiện tại.

Không giả định v4 open-source; maintainer mô tả v4 là proprietary/API-only.

### capcut-tts-api
`https://github.com/K07VN/capcut-tts-api`

Repo hiện có:
- Python SDK;
- TTS;
- STT;
- voice catalog;
- DeviceConfig;
- async/polling task flow.

Cần audit upstream behavior trước khi ship production.

### CapCut draft
Các open-source tooling hiện tại ghi nhận Windows draft root thường là:
`%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft`

Canonical Windows file thường là `draft_content.json`, nhưng schema có thể thay đổi theo version → exporter phải probe/test local draft.

---

## 27. Acceptance Tests 2.0

### First run
- wizard xuất hiện;
- Gemini check;
- TTS check;
- CapCut folder detect/chọn;
- restart;
- không hỏi lại nếu vẫn OK.

### Broken config
- invalid Gemini → banner + fix action.

### Multi-video
- add 3 videos;
- state riêng;
- không lẫn transcript.

### Blur
- + Làm mờ;
- rectangle hiện;
- drag/resize;
- preview blur thật;
- không darken;
- timing đúng.

### Script
- STT + Gemini;
- stop review;
- edit;
- validate;
- approve.

### Voice
- VieNeu health;
- preview;
- synthesize;
- cache;
- đổi 1 segment → regenerate 1 segment.

### Custom Voice
- add authorized reference;
- saved voice xuất hiện;
- restart vẫn còn.

### CapCut Export
- export 1 draft;
- CapCut nhìn thấy/open được;
- video/audio/caption timing đúng;
- blur editable nếu đã verify; nếu chưa → status PARTIAL rõ ràng.

### Batch CapCut
- 3 video → 3 unique drafts;
- 1 fail không phá 2 cái còn lại.

### Update
- newer version → prompt;
- latest → silent;
- fail → app vẫn dùng được.

---

## 28. Milestones 2.0

```text
M1 Audit + Migration
M2 Setup & Health Check
M3 Simplified Main UI
M4 Gemini Script Workflow
M5 VieNeu + Voice Manager
M6 True Blur Editor
M7 Multi-video / Batch
M8 CapCut Compatibility Probe
M9 Editable CapCut Export
M10 Polish + Installer + Update
```

M8 phải verify trước khi M9 được PASS.

---

## 29. Definition of Done

Status chuẩn:
```text
PASS
PARTIAL
FAIL
UI ONLY
IMPLEMENTED BUT NOT VERIFIED
BLOCKED BY UPSTREAM
```

Feature chỉ PASS khi có code + test hợp lý + app run + manual verify cho media/visual behavior.
