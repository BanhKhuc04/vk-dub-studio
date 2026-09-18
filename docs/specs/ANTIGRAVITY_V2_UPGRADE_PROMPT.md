# ANTIGRAVITY MASTER PROMPT — VK Dub Studio 2.0

Bạn đang tiếp quản một repository ĐANG CÓ của **VK Dub Studio — by vanhkhuc**.

Không tạo project mới. Không rewrite chỉ vì muốn “sạch hơn”.

File source of truth mới:

`VK_DUB_STUDIO_V2_SPEC.md`

Đọc TOÀN BỘ file này trước khi sửa code.

## Mission
Nâng app lên **VK Dub Studio 2.0** theo hướng:
- tinh gọn;
- dễ dùng;
- setup một lần rồi nhớ;
- local-first;
- Gemini viết/dịch kịch bản;
- VieNeu Local làm TTS mặc định;
- CapCut TTS là optional/experimental;
- blur thật, không làm tối;
- multi-video/batch;
- review transcript trước TTS;
- export mỗi video thành project CapCut chỉnh tiếp được.

## Quy tắc chống báo cáo sai
Không được nói DONE chỉ vì có UI.

Status hợp lệ:
- PASS
- PARTIAL
- FAIL
- UI ONLY
- IMPLEMENTED BUT NOT VERIFIED
- BLOCKED BY UPSTREAM

PASS phải có bằng chứng code/test/run/manual verification phù hợp.

Không bịa:
- API endpoint;
- CapCut schema;
- voice ID;
- test result;
- command output;
- tính năng custom voice;
- blur editable nếu chưa mở trong CapCut thử.

## Bước 0 — Audit trước
Trước khi code:
1. đọc `VK_DUB_STUDIO_V2_SPEC.md`;
2. đọc README và docs cũ;
3. đọc entrypoint/UI/project storage/STT/Gemini/TTS/mask/exporter/updater/tests;
4. chạy test hiện tại;
5. chạy app hiện tại;
6. tạo migration map:

```text
KEEP
REFACTOR
REMOVE FROM UI
LEGACY/DISABLED
NEW FOR 2.0
```

Không xóa module cũ trước khi biết dependency.

## Remove clutter khỏi UI
2.0 không hiện:
- Vbee;
- ElevenLabs;
- HWID;
- TikTok Session ID;
- raw Gemini key list;
- model path;
- FFmpeg path;
- dev JSON controls.

Các thứ kỹ thuật cần giữ thì chuyển Settings/Nâng cao.

## User flow bắt buộc

```text
SETUP ONCE
↓
ADD VIDEO(S)
↓
SELECT CAPCUT FOLDER
↓
SELECT LANGUAGE
↓
SELECT VOICE + SPEED + PREVIEW
↓
DRAW BLUR REGION(S)
↓
START PROCESSING
↓
STT
↓
GEMINI SCRIPT
↓
REVIEW TRANSCRIPT
↓
APPROVE
↓
GENERATE VOICE + AUDIO LEVEL
↓
EXPORT PROJECT CAPCUT
```

## M1 — Audit + Migration
- xác định schema/app version hiện tại;
- migration v2;
- giữ transcript/translation/masks/project/cache nếu hợp lệ;
- Vbee/ElevenLabs thành legacy hidden;
- không làm mất project cũ.

Run tests.

## M2 — Setup + Health Check
First-run wizard:
1. Gemini;
2. Voice Engine;
3. CapCut Folder;
4. Workspace;
5. System Check.

Persist:
- wizard state;
- Gemini model;
- TTS backend;
- voice/speed;
- CapCut root;
- workspace;
- languages;
- update preference.

Gemini secret dùng keyring/Windows Credential Manager.

Voice Engine options:
- VieNeu Local (default);
- CapCut TTS (optional).

Auto-detect CapCut:
`%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft`

Lần sau mở app:
- silent health checks;
- nếu OK không mở wizard;
- nếu lỗi chỉ hiện actionable banner.

## M3 — Simplified Main UI
3 khu vực:

LEFT:
- video/project list;
- CapCut destination;
- language;
- voice;
- speed;
- preview voice;
- CTA chính.

CENTER:
- preview lớn;
- seek/play;
- `+ Làm mờ`;
- subtitle;
- preview voice;
- overflow menu.

RIGHT:
- transcript/script;
- validation;
- approval.

CTA theo state:
- `BẮT ĐẦU XỬ LÝ`;
- `DUYỆT & TẠO VOICE`;
- `XUẤT PROJECT CAPCUT`.

Stage cũ chỉ là status, không phải 5 button lớn.

## M4 — Gemini Script Workflow
Giữ STT đang chạy nếu tốt.

Gemini:
- translate;
- polish tiếng Việt;
- selected-line rewrite.

Structured JSON, preserve ID/timestamp.
Không overwrite script nếu response invalid.

Pipeline phải STOP ở review.
Không TTS trước approve.

## M5 — VieNeu + Voice Manager
Nghiên cứu repo:
`https://github.com/pnnbao97/VieNeu-TTS`

Ưu tiên open-source local v3 Turbo khi tương thích.

Tạo adapter `VieNeuLocalProvider`, không gọi repo trực tiếp từ UI.

Phải có:
- health check;
- default/saved voices;
- preview;
- synthesize;
- cache;
- worker/cancel;
- friendly setup.

Voice Settings:
`+ THÊM GIỌNG`

Cho:
- name;
- reference audio user có quyền sử dụng;
- ref text nếu backend cần;
- register/save;
- preview;
- persist;
- rename/delete.

Không bundle reference voice bên thứ ba nếu chưa verify permission.

## Optional — CapCut TTS
Nghiên cứu:
`https://github.com/K07VN/capcut-tts-api`

Tạo `CapCutTTSProvider`.

Xem như experimental/external:
- health check runtime;
- fail isolated;
- fallback VieNeu;
- voice catalog;
- không giả định custom voice nếu repo không có.

## M6 — TRUE BLUR EDITOR
Requirement cứng:

Bấm `+ LÀM MỜ` → rectangle xuất hiện ngay.

User có thể drag/resize/move/delete/duplicate/set start-end.

Phải BLUR PIXEL THẬT.

KHÔNG:
- black box;
- dark overlay;
- semi-transparent rectangle;
- giảm brightness giả blur.

Store normalized 0..1 coordinates.
Preview resize không lệch.

## M7 — Multi-video / Batch
Một workspace chứa nhiều video.

Mỗi video riêng:
- transcript;
- masks;
- review;
- voice cache;
- CapCut state.

Global defaults + per-video override.

Batch process/export.
Một video fail không làm mất video đã thành công.

## M8 — CAPCUT COMPATIBILITY PROBE
KHÔNG nhảy thẳng sang generate draft JSON đoán mò.

Windows draft root thường:
`%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft`

Làm probe:
1. detect local CapCut;
2. chỉ đọc draft user làm reference, không sửa;
3. xác định filename/version/schema/timing;
4. tạo hoặc yêu cầu user tạo draft test thủ công có:
   - video;
   - audio;
   - caption;
   - rectangle blur/mask;
5. diff/inspect;
6. document `docs/CAPCUT_COMPATIBILITY.md`;
7. mọi field/ID exporter dùng phải có nguồn từ local verified sample hoặc tested library.

Không tuyên bố M9 PASS nếu M8 chưa verify.

## M9 — Editable CapCut Export
Mục tiêu:
1 VKDub video → 1 NEW CapCut draft.

Không chỉ render MP4.

Project hướng tới editable:
- source video;
- TTS audio;
- original audio level;
- captions;
- timing;
- blur/mask nếu schema đã verify.

Unique draft ID.
Không overwrite project khác.

Sau export:
- `MỞ CAPCUT`;
- `MỞ THƯ MỤC PROJECT`.

Blur editable phải được mở thử trong CapCut trước khi PASS.
Nếu chưa được → PARTIAL, giải thích fallback.
Tuyệt đối không thay blur bằng black box.

## M10 — Polish + Update
- silent update check;
- prompt khi có bản mới;
- network fail không block app;
- autosave;
- recovery;
- progress/cancel/retry;
- friendly empty states;
- installer giữ settings.

## Persistence
User không nhập lại mỗi launch.
Nhớ:
- Gemini key secure;
- model;
- TTS backend;
- voices;
- speed;
- CapCut root;
- workspace;
- languages;
- UI/update preferences.

## Review Gate bắt buộc
Sau STT + Gemini:
`REVIEW_REQUIRED`.

User sửa/check rồi bấm:
`DUYỆT & TẠO VOICE`.

Lưu revision hash.
Nếu script thay đổi sau approval:
- revoke approval;
- export disabled;
- regenerate chỉ segment thay đổi sau re-approve.

## Audio UI
Chỉ cần:
- Voice volume;
- Original audio volume;
- speed;
- preview.

Không show FFmpeg internals.

## Working style
Không làm mega-edit tất cả một lần.

Mỗi milestone:
1. inspect;
2. change;
3. test;
4. run;
5. manual verify;
6. update `docs/V2_PROGRESS.md`.

## TASK NGAY BÂY GIỜ
Làm CHỈ:
- M1 Audit + Migration;
- M2 Setup + Health Check;
- M3 Simplified Main UI.

Chưa làm CapCut exporter trong lượt đầu.

Checklist:
1. đọc V2 spec;
2. audit repo;
3. run current tests;
4. run app;
5. migration v2;
6. hide Vbee/ElevenLabs UI;
7. persistent settings;
8. setup wizard;
9. silent startup health check;
10. simplified main UI shell;
11. preserve video/STT/script functionality;
12. run tests again;
13. smoke test.

Báo cuối:

```text
VK DUB STUDIO 2.0 — CHECKPOINT

Status:
PASS / PARTIAL / FAIL

Milestones:
M1:
M2:
M3:

Changed:
- ...

Verified:
- commands
- tests
- manual checks

Still incomplete:
- ...

Regression check:
- ...

Next:
M4
```

STOP sau báo cáo và chờ user duyệt.
