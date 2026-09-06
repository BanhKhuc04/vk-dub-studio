# CODEX MASTER PROMPT — VK Dub Studio
## Windows Video Translation, Dubbing, Subtitle & Mask Editor
**Branding:** by vanhkhuc

You are Codex acting as a senior Windows desktop engineer, Python engineer, media-processing engineer, and product-minded UI engineer.

Your job is to build a production-oriented Windows desktop application called **VK Dub Studio**.

The app must help a Vietnamese creator:
1. Import a local video.
2. Extract/transcribe speech.
3. Translate the transcript to Vietnamese.
4. Let the user review and edit the complete script/SRT.
5. ONLY AFTER the user explicitly approves the script, generate Vietnamese voice.
6. Add/edit subtitles.
7. Add custom blur/cover masks to hide original on-screen text.
8. Preview the result.
9. Render/export the final MP4.
10. Check for new releases and update on Windows.
11. Show branding: **VK Dub Studio — by vanhkhuc**.

Do not implement a workflow that automatically renders before script approval.

---

# 1. TECHNOLOGY CHOICE

Use this stack unless an existing repository already forces a compatible alternative:

- Python 3.12
- PySide6 for desktop UI
- FFmpeg + ffprobe for media processing
- faster-whisper for LOCAL speech-to-text
- Gemini API adapter for translation
- Vbee official API adapter for TTS, with default voice label `HN - Ngọc Huyền`
- Optional local TTS adapter interface
- Optional ElevenLabs adapter for alternative voices
- SQLite for project/cache/job metadata
- pydantic/dataclasses for domain models
- keyring / Windows Credential Manager for API secrets
- requests/httpx for network calls
- pytest for tests
- PyInstaller for packaged app
- Inno Setup for Windows installer
- GitHub Releases + static `latest.json` for updater
- SHA-256 validation for downloaded installers

The architecture must use provider interfaces. Business logic must not directly depend on Gemini/Vbee.

Example interfaces:

```python
class SpeechToTextProvider(Protocol):
    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript:
        ...

class TranslationProvider(Protocol):
    def translate_segments(
        self,
        segments: list[SubtitleSegment],
        source_language: str,
        target_language: str,
    ) -> list[SubtitleSegment]:
        ...

class TextToSpeechProvider(Protocol):
    def list_voices(self) -> list[Voice]:
        ...

    def synthesize(
        self,
        text: str,
        voice_id: str,
        speed: float,
        output_path: Path,
    ) -> Path:
        ...
```

---

# 2. MOST IMPORTANT PRODUCT RULE: SCRIPT APPROVAL GATE

The app workflow is a strict state machine:

```text
IDLE
  ↓
VIDEO_IMPORTED
  ↓
TRANSCRIBING
  ↓
TRANSCRIBED
  ↓
TRANSLATING
  ↓
REVIEW_REQUIRED
  ↓
APPROVED
  ↓
GENERATING_VOICE
  ↓
VOICE_READY
  ↓
RENDERING
  ↓
DONE
```

The green button may be called:

`BẮT ĐẦU XỬ LÝ`

It may automatically run:

- prepare/extract audio
- transcribe
- translate
- prepare draft SRT

BUT IT MUST STOP AT:

`REVIEW_REQUIRED`

At that point, display a large right-side review panel.

The user must manually press:

`✓ DUYỆT KỊCH BẢN & TẠO VOICE`

Only then may TTS start.

If the user edits any subtitle/script segment after approval:
- automatically revoke approval
- state becomes `REVIEW_REQUIRED`
- disable final render until approved again

Never allow final export if:
- script is not approved
- there are invalid time ranges
- subtitle segments overlap unexpectedly
- any required translated line is empty
- voice generation is incomplete

---

# 3. MAIN UI

Build a dark Windows desktop UI inspired by the supplied reference screenshots.

Use a 3-column main layout.

## LEFT — CẤU HÌNH

Top:
- App name/logo
- `VK Dub Studio`
- `by vanhkhuc`
- current version
- Update status

Sections:

### Project
- `TẢI VIDEO`
- selected video path
- output directory
- save project
- load project

### Language
- Source language: Auto / Chinese / English / ...
- Target language: Vietnamese by default

### Speech-to-text
- Provider
- default: `Local Faster-Whisper`
- model selector: tiny / base / small / medium / large-v3
- device: Auto / CPU / CUDA
- status badge: `LOCAL • 0đ`

### Translation
- Provider selector
- default cloud option: `Gemini`
- model selector
- API key status
- `Kiểm tra API`
- estimated input size
- estimated cost/free-tier note

### Voice
Default selection MUST be:

`HN - Ngọc Huyền`

Display:
- Provider
- Voice
- Speed
- Volume
- Preview voice button
- API connection state

For Vbee:
- use official API integration only
- never scrape or reverse engineer private endpoints
- if the required Vbee API key/plan is not available, show a clear message instead of silently failing

Allow other provider adapters later.

### Original audio
- Keep original audio
- Original voice/background volume
- Duck original audio while Vietnamese voice is playing
- optional `Tách nhạc nền` feature
- keep this modular because source separation may be heavy

### API & Cost Manager
Button:
`QUẢN LÝ API & CHI PHÍ`

### Activity Log
Scrollable log:
- timestamps
- current stage
- errors
- retries
- progress

Bottom buttons:
- `BẮT ĐẦU XỬ LÝ`
- stage buttons/status chips:
  - 1. Bóc băng
  - 2. Dịch
  - 3. Duyệt
  - 4. Tạo Voice
  - 5. Render
- `DỪNG`

---

# 4. CENTER — VIDEO PREVIEW + TIMELINE

The preview must support:
- play/pause
- seek
- current time / total duration
- frame preview
- overlay preview of subtitles
- overlay preview of masks
- resize with correct video aspect ratio

Below preview:

Buttons:
- Play/Pause
- `+ Thêm vùng che`
- `Xóa mask`
- `Tạo thumbnail`
- optional zoom

Timeline tracks:

```text
VIDEO      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VOICE      █████  ██████   █████████
SUBTITLE   █████  ██████   █████████
MASK             ███████
```

Clicking a script segment on the right must seek the preview to that segment.

---

# 5. CUSTOM TEXT-HIDING / MASK EDITOR

Users must be able to hide existing hardcoded text in the source video.

Workflow:
1. Press `+ Thêm vùng che`.
2. Draw a rectangle directly over the video preview.
3. The mask becomes selectable/resizable/movable.
4. User sets start/end time.
5. Preview updates immediately.
6. Final render applies the same coordinates after proper preview-to-source-video scaling.

Mask model:

```python
class MaskRegion(BaseModel):
    id: str
    start: float
    end: float
    x: float
    y: float
    width: float
    height: float
    coordinate_space: Literal["normalized"] = "normalized"
    mode: Literal["blur", "pixelate", "solid"]
    strength: float = 20
    opacity: float = 1.0
    color: str = "#000000"
```

Store coordinates normalized 0..1, not raw preview pixels.

Support:
- blur
- pixelate
- solid-color cover

Use FFmpeg for final output.

For time-bounded masks, generate valid FFmpeg filter graphs using `enable='between(t,start,end)'` or equivalent.

Masks must support multiple regions.

---

# 6. RIGHT — KỊCH BẢN / SRT REVIEW

This is a core feature, not a plain text box.

Title:
`KỊCH BẢN & PHỤ ĐỀ`

Top status:
- `CHƯA DUYỆT`
- `ĐÃ DUYỆT`

Toolbar:
- Save SRT
- Load SRT
- Undo
- Redo
- Validate
- Search/replace
- optional AI rewrite selected line

Display segments as editable rows/cards.

Each segment:
- index
- start
- end
- original/source text
- Vietnamese translation
- duration
- estimated voice duration
- warning icon
- play button
- regenerate translation button
- regenerate voice button after approval

Required operations:
- inline edit
- add segment
- delete segment
- split segment
- merge with previous/next
- adjust start/end
- drag ordering only if timestamps remain valid
- seek preview to segment

Validation rules:
- start >= 0
- end > start
- no accidental overlap
- no empty translated text
- warn if translated text is likely too long for available segment duration
- warn if TTS audio is longer than segment duration

Show summary:

```text
Kịch bản:
282 câu
0 lỗi
4 cảnh báo
Tổng thời lượng: 03:44
```

Approval area:

Checkbox:
`Tôi đã kiểm tra toàn bộ kịch bản`

Button:
`✓ DUYỆT KỊCH BẢN & TẠO VOICE`

Button remains disabled until:
- checkbox checked
- validation has zero blocking errors

After approval:
- freeze a revision hash for the approved script
- generate TTS for that revision

Any script edit invalidates the hash and approval.

---

# 7. SUBTITLE SYSTEM

The app must allow fully customized subtitles.

Subtitle fields:
- text
- start/end
- font
- font size
- bold
- italic
- text color
- outline color
- outline width
- shadow
- background box
- background opacity
- alignment
- X/Y position
- bottom margin
- max width
- line spacing

Provide presets:
- Minimal
- YouTube
- TikTok
- Movie
- Bold Caption

Preview subtitle overlays in real time.

Export:
- `.srt`
- `.ass`
- hardcoded/burned subtitles into MP4

Prefer ASS for styled hardcoded subtitles.

Do not destroy the source SRT data when style changes.

---

# 8. TRANSCRIPTION

Default STT must be:

`Local Faster-Whisper`

Reason:
- works offline
- no API fee
- predictable
- no upload required

Pipeline:
1. ffmpeg extract audio to WAV/16k mono when needed
2. faster-whisper transcription
3. build timestamped segments
4. preserve source transcript

Provide model configuration.

Cache transcription using a hash of:
- video/audio fingerprint
- model name
- language settings

If already cached, offer reuse.

---

# 9. TRANSLATION

Translation target:
- natural Vietnamese
- concise enough for voice-over
- preserve meaning
- avoid adding new information
- preserve names/numbers
- keep segment boundaries unless the user intentionally merges them

Default cloud provider adapter:
`Gemini`

Translation prompt logic must request structured JSON.

Example internal request schema:

```json
{
  "segments": [
    {
      "id": 1,
      "start": 0.0,
      "end": 1.76,
      "text": "..."
    }
  ],
  "source_language": "zh",
  "target_language": "vi"
}
```

Expected response:
```json
{
  "segments": [
    {
      "id": 1,
      "translation": "..."
    }
  ]
}
```

Never trust raw model output.
Validate JSON and IDs before applying.

Batch segments to stay within provider limits.

Retry safely with exponential backoff.

Do not rotate API keys to evade provider rate limits.

---

# 10. DEFAULT VOICE: HN - NGỌC HUYỀN

The UI default voice is:

`HN - Ngọc Huyền`

Implement through a `VbeeTTSProvider` using Vbee's official API/authentication method.

Rules:
- API key stored through OS credential storage, not plaintext config files
- Test connection button
- show clear quota/API error
- split long scripts into provider-supported requests
- cache generated audio
- do not regenerate unchanged lines

Audio cache key:

```text
sha256(
  provider +
  voice_id +
  speed +
  normalized_text
)
```

If an official API plan/key is unavailable:
- keep the project editable
- do not lose translation/subtitles
- disable `Tạo Voice`
- show the exact reason
- let the user select another configured TTS provider

IMPORTANT:
Do not bundle an unofficial cloned copy of a proprietary/person-specific voice unless its license and redistribution rights have been explicitly verified.

---

# 11. API & COST MANAGER

Implement a dedicated window/dialog.

Table columns:

| Stage | Provider | Mode | Credential | Estimated usage | Estimated cost | Status |
|---|---|---|---|---:|---:|---|
| STT | Faster-Whisper | LOCAL | — | 3m44s | 0đ | Ready |
| Translate | Gemini | CLOUD | Configured | 6,250 chars | Free-tier / estimate | Ready |
| TTS | Vbee | CLOUD | Missing/Configured | 5,900 chars | estimate | ... |
| Render | FFmpeg | LOCAL | — | — | 0đ | Ready |

Modes:
- `LOCAL`
- `FREE_TIER`
- `PAID`

Implement:

```python
class ProviderPricing(BaseModel):
    provider: str
    metric: Literal[
        "characters",
        "input_tokens",
        "output_tokens",
        "audio_minutes",
        "requests"
    ]
    free_quota: float | None
    unit_size: float
    price_per_unit_usd: float
    last_verified_at: str
    source_url: str | None
```

Store pricing separately in:
`resources/provider_pricing.json`

Cost calculation must be isolated from provider execution.

IMPORTANT:
Free-tier/quota information can change.
UI must say:
`Ước tính — hạn mức thực tế do nhà cung cấp quyết định.`

The app must not claim a request is free solely from local tracking.

Also show:
- current project estimated usage
- monthly locally tracked usage
- warning threshold
- optional user budget in VND
- configurable USD/VND rate
- reset local statistics

Secrets:
- use `keyring`
- never write API keys to logs
- redact secret values from exceptions

---

# 12. PROVIDER STRATEGY

Default low-cost setup:

### STT
`faster-whisper`
- local
- cost = 0
- default

### Translation
`Gemini`
- support free-tier accounts
- API key required
- app must track only estimated usage
- provider quota remains authoritative

Optional:
`Google Cloud Translation`

### TTS
Default UI voice:
`HN - Ngọc Huyền`

Primary exact-voice provider:
`Vbee official API`

Optional alternative providers:
- ElevenLabs
- another licensed provider
- local TTS model installed by user

Do not hard-code the app to one provider.

---

# 13. VOICE TIMING / DUBBING

For each subtitle segment:
1. Generate/reuse TTS audio.
2. Read actual generated duration with ffprobe.
3. Compare against target segment duration.
4. If within tolerance, place audio normally.
5. If slightly longer, allow limited tempo adjustment.
6. If too long, show warning to user rather than silently mangling audio.

Suggested limits:
- natural TTS speed UI: 0.8x–1.3x
- FFmpeg `atempo` for small fit corrections only

Do not exceed extreme speed changes automatically.

Store per-segment TTS metadata:
- text revision hash
- provider
- voice
- requested speed
- actual duration
- output path
- generation timestamp

Allow `Nghe thử`.

---

# 14. AUDIO MIX

Final mix should support:
- Vietnamese TTS
- original audio
- original audio ducking
- optional isolated background music track

V1 can use volume ducking.

Optional later module:
- Demucs source separation

Do not block the whole MVP on Demucs.

---

# 15. FINAL RENDER

The final render must combine:
- source video
- masks
- subtitles
- Vietnamese voice
- chosen original/background audio mix

Default output:
- MP4
- H.264 video
- AAC audio
- preserve source resolution and fps when practical
- sane CRF/preset defaults

Before render show:

```text
KIỂM TRA TRƯỚC KHI XUẤT

✓ Video
✓ Kịch bản đã duyệt
✓ 282/282 voice đã tạo
✓ Subtitle hợp lệ
✓ 2 vùng che
✓ FFmpeg sẵn sàng

[ XUẤT VIDEO ]
```

If script is not approved:
`XUẤT VIDEO` must be disabled.

Render to a temporary output first.
Only rename/move to final destination after successful completion.

Do not overwrite an existing final file without confirmation.

---

# 16. PROJECT FILE

Use a project format:

`.vkdub`

Example:

```json
{
  "schema_version": 1,
  "app_version": "0.1.0",
  "project_id": "...",
  "video_path": "...",
  "source_language": "auto",
  "target_language": "vi",
  "transcript": [],
  "subtitles": [],
  "masks": [],
  "voice": {
    "provider": "vbee",
    "voice_id": "hn-ngoc-huyen",
    "display_name": "HN - Ngọc Huyền",
    "speed": 1.0
  },
  "script_review": {
    "approved": false,
    "approved_revision_hash": null
  },
  "export": {
    "container": "mp4",
    "video_codec": "h264",
    "audio_codec": "aac"
  }
}
```

Implement migrations for future schema versions.

Never store API keys in the project file.

---

# 17. AUTO SAVE / RECOVERY

Autosave project state:
- after script edits
- mask edits
- voice settings changes
- every 30 seconds while dirty

On crash/restart:
- detect recovery state
- offer `Khôi phục project`

Long jobs must support cancellation.

Do not leave orphan temp files after normal completion.

---

# 18. WINDOWS AUTO UPDATE

App version:
Semantic Versioning, e.g. `1.0.0`.

On startup:
1. asynchronously fetch `latest.json`
2. compare versions
3. if newer, show:
   - new version
   - changelog
   - size
   - Update now / Later
4. download installer to temp
5. verify SHA-256
6. launch installer
7. exit app

Example `latest.json`:

```json
{
  "version": "1.1.0",
  "published_at": "2026-09-04T00:00:00Z",
  "installer_url": "https://github.com/<owner>/<repo>/releases/download/v1.1.0/VK-Dub-Studio-Setup.exe",
  "sha256": "...",
  "changelog": [
    "Cải thiện dịch",
    "Sửa lỗi render",
    "Thêm preset subtitle"
  ]
}
```

Add:
- `Kiểm tra cập nhật` button in Settings
- update channel field prepared for `stable` / `beta`
- app must not auto-install without user confirmation in V1

Packaging:
- PyInstaller
- Inno Setup

Output name:
`VK-Dub-Studio-Setup-x64.exe`

Brand installer:
`VK Dub Studio`
`by vanhkhuc`

Optional future:
Windows code signing.

---

# 19. FOLDER STRUCTURE

Create approximately:

```text
vk-dub-studio/
├─ app.py
├─ pyproject.toml
├─ README.md
├─ .env.example
├─ src/
│  └─ vkdub/
│     ├─ __init__.py
│     ├─ version.py
│     ├─ ui/
│     │  ├─ main_window.py
│     │  ├─ left_config_panel.py
│     │  ├─ video_preview.py
│     │  ├─ timeline_widget.py
│     │  ├─ script_review_panel.py
│     │  ├─ subtitle_style_dialog.py
│     │  ├─ api_manager_dialog.py
│     │  ├─ export_dialog.py
│     │  └─ settings_dialog.py
│     ├─ domain/
│     │  ├─ models.py
│     │  ├─ project.py
│     │  ├─ state_machine.py
│     │  └─ validation.py
│     ├─ services/
│     │  ├─ pipeline_service.py
│     │  ├─ transcription_service.py
│     │  ├─ translation_service.py
│     │  ├─ tts_service.py
│     │  ├─ subtitle_service.py
│     │  ├─ mask_service.py
│     │  ├─ audio_mix_service.py
│     │  ├─ render_service.py
│     │  ├─ project_service.py
│     │  ├─ cache_service.py
│     │  ├─ pricing_service.py
│     │  └─ update_service.py
│     ├─ providers/
│     │  ├─ base.py
│     │  ├─ faster_whisper_stt.py
│     │  ├─ gemini_translate.py
│     │  ├─ vbee_tts.py
│     │  └─ elevenlabs_tts.py
│     ├─ media/
│     │  ├─ ffmpeg.py
│     │  ├─ ffprobe.py
│     │  ├─ filters.py
│     │  └─ audio.py
│     ├─ storage/
│     │  ├─ database.py
│     │  ├─ secrets.py
│     │  └─ migrations.py
│     └─ utils/
│        ├─ logging.py
│        ├─ hashing.py
│        └─ paths.py
├─ resources/
│  ├─ provider_pricing.json
│  ├─ subtitle_presets.json
│  └─ icons/
├─ tests/
│  ├─ test_state_machine.py
│  ├─ test_srt.py
│  ├─ test_validation.py
│  ├─ test_pricing.py
│  ├─ test_mask_coordinates.py
│  ├─ test_revision_approval.py
│  └─ test_ffmpeg_filters.py
├─ scripts/
│  ├─ dev.ps1
│  ├─ build.ps1
│  └─ release.ps1
└─ installer/
   └─ vkdub.iss
```

---

# 20. THREADING / RESPONSIVENESS

NEVER run:
- FFmpeg
- transcription
- translation HTTP requests
- TTS
- render
on the Qt main UI thread.

Use:
- QThread / worker abstractions
- signals for progress/log/status
- cancellation tokens/events

UI must remain responsive during all long operations.

---

# 21. LOGGING

Log to:
`%LOCALAPPDATA%\VKDubStudio\logs\`

Use rotating logs.

Never log:
- raw API keys
- Authorization headers

User-visible activity log should contain friendly Vietnamese messages.

Developer log may contain stack traces.

---

# 22. DATA PATHS

Use:

```text
%LOCALAPPDATA%\VKDubStudio\
├─ projects\
├─ cache\
│  ├─ transcript\
│  ├─ translation\
│  └─ tts\
├─ temp\
├─ logs\
└─ app.db
```

Do not put large generated files inside the source repository.

---

# 23. ERROR HANDLING

Every pipeline stage must fail independently.

Examples:
- translation fails → keep transcript
- one TTS segment fails → mark only that segment failed and allow retry
- render fails → preserve project and voice cache
- update download fails → app still runs normally

Display actionable error messages.

Implement:
`Retry failed items`

---

# 24. ACCEPTANCE TESTS

The MVP is accepted only if all of these work:

## Test A — Basic workflow
1. Import MP4.
2. Preview plays.
3. Transcribe locally.
4. Translate to Vietnamese.
5. Right panel shows editable translated segments.
6. Processing STOPS.
7. Render button disabled.
8. User edits one line.
9. User validates.
10. User approves script.
11. Voice generation starts.
12. Voice uses selected default label `HN - Ngọc Huyền` when Vbee is configured.
13. User exports.
14. Output MP4 plays.

## Test B — Approval invalidation
1. Approve script.
2. Edit one character.
3. Approval is automatically revoked.
4. Final render becomes disabled.
5. User must approve again.

## Test C — Mask
1. Add a rectangular mask.
2. Move/resize it.
3. Set start 5s/end 10s.
4. Preview shows it only in that range.
5. Render shows it in the correct source-video position.

## Test D — Subtitle
1. Edit subtitle.
2. Change font/size/position.
3. Preview updates.
4. SRT/ASS export works.
5. Burned subtitle output matches preview reasonably.

## Test E — API secrets
1. Save API key.
2. Restart app.
3. Credential remains available.
4. Key is not present in project JSON or log file.

## Test F — Offline STT
1. Disconnect network.
2. Local faster-whisper still works if model is installed.

## Test G — Updater
1. Current version 1.0.0.
2. latest.json reports 1.0.1.
3. Update dialog appears.
4. Download checksum is validated.
5. Bad checksum refuses install.

---

# 25. DEVELOPMENT PLAN

Implement in phases.

## PHASE 0 — Repository & smoke test
- project structure
- PySide6 app opens
- dark theme
- version + branding
- FFmpeg detection
- tests run

## PHASE 1 — Video + project
- import MP4
- video preview
- ffprobe metadata
- save/load `.vkdub`
- output folder

## PHASE 2 — Local transcription
- faster-whisper
- worker thread
- SRT model
- right script panel

## PHASE 3 — Translation
- provider abstraction
- Gemini adapter
- API manager
- translation cache
- cost estimator

## PHASE 4 — Script review gate
- editor
- validation
- revision hash
- approval invalidation
- stop pipeline at REVIEW_REQUIRED

DO NOT start Phase 5 until Phase 4 acceptance tests pass.

## PHASE 5 — TTS
- Vbee provider
- default HN - Ngọc Huyền UI selection
- audio cache
- per-segment regenerate
- duration validation

## PHASE 6 — Subtitle editor
- style presets
- SRT
- ASS
- preview overlay

## PHASE 7 — Masks
- interactive rectangles
- normalized coordinates
- time range
- FFmpeg render filters

## PHASE 8 — Audio mix + render
- combine voice/source audio
- subtitles
- masks
- progress
- safe final output

## PHASE 9 — Windows packaging/update
- PyInstaller
- Inno Setup
- latest.json
- GitHub release workflow support
- updater UI

## PHASE 10 — polish
- recovery
- logs
- UX
- performance
- tests
- README

---

# 26. CODEX WORKING RULES

When implementing:

1. Inspect the repository before modifying it.
2. Do not delete working features without a reason.
3. Keep modules small and focused.
4. Prefer typed domain models.
5. Avoid giant UI files.
6. Keep provider code behind interfaces.
7. Add tests whenever logic changes.
8. Run tests after each meaningful milestone.
9. Run a smoke start of the app after UI changes.
10. Do not silently swallow exceptions.
11. Never commit real API keys.
12. Keep `.env.example`, never `.env`.
13. Add useful comments for non-obvious FFmpeg logic.
14. Document manual installation requirements.
15. If a provider API is uncertain, implement its adapter boundary and clearly mark the exact missing verified endpoint/schema rather than inventing it.
16. Do not scrape providers or bypass their quotas.
17. Do not implement automatic export before script approval.
18. After every phase, update `README.md` with:
    - completed
    - how to run
    - known limitations
    - next step

---

# 27. FIRST CODEX TASK

Start now with PHASE 0 and PHASE 1.

Before coding:
- inspect existing files
- report current repository state in 5–10 lines
- state what files you will add/change

Then implement:
- runnable PySide6 shell
- dark 3-column UI
- branding `VK Dub Studio — by vanhkhuc`
- import local video
- video playback/seek
- ffmpeg/ffprobe detection
- output directory
- project save/load skeleton
- right-side empty Script Review panel
- disabled `DUYỆT KỊCH BẢN & TẠO VOICE`
- disabled `XUẤT VIDEO`
- version display
- logs panel
- basic tests

Then run:
- tests
- lint/type checks if configured
- app smoke test

Finally report:
- files changed
- commands run
- test results
- screenshot/manual verification steps
- next phase

Do not jump ahead and fake unfinished API integrations.
