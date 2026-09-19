# HỆ THỐNG KAPPAK STUDIO - TÀI LIỆU KIẾN TRÚC

> **Phiên bản:** 2.1.17  
> **Ngày cập nhật:** 2026-09-19  
> **Người viết:** AI Agent (vanhkhuc.dev)

---

## 1. TỔNG QUAN KIẾN TRÚC

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         KAPPAK STUDIO                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐    ┌──────────────────────────────────────────────┐   │
│  │   WEB UI     │    │              BACKEND (FastAPI)               │   │
│  │  (React)     │◄──►│  ┌────────────────────────────────────────┐ │   │
│  │              │    │  │         Auto Dub Pipeline                │ │   │
│  │  http://     │    │  │  4.1 Whisper (STT)                     │ │   │
│  │  localhost:  │    │  │  4.2 Gemini (Translation) ◄── FIXED    │ │   │
│  │  8000        │    │  │  4.3 Script Prep                       │ │   │
│  │              │    │  │  4.4 Vbee/Edge TTS                      │ │   │
│  └──────────────┘    │  └────────────────────────────────────────┘ │   │
│                       │                                             │   │
│                       │  ┌────────────────────────────────────────┐ │   │
│                       │  │    Auto Video Generator                 │ │   │
│                       │  │    - TTS + FFmpeg 9:16                 │ │   │
│                       │  │    - Templates                          │ │   │
│                       │  └────────────────────────────────────────┘ │   │
│                       │                                             │   │
│                       │  ┌────────────────────────────────────────┐ │   │
│                       │  │    Universal Downloader                 │ │   │
│                       │  │    - yt-dlp + SHA-256                  │ │   │
│                       │  └────────────────────────────────────────┘ │   │
│                       │                                             │   │
│                       │  ┌────────────────────────────────────────┐ │   │
│                       │  │    Data Studio                         │ │   │
│                       │  │    - SQLite + 8-tier tree               │ │   │
│                       │  └────────────────────────────────────────┘ │   │
│                       └──────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    DESKTOP UI (PySide6)                           │   │
│  │              app.py --gui (Desktop GUI Mode)                      │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. BACKEND COMPONENTS (src/vkdub)

### 2.1 Providers (AI/TTS Engines)

| Provider | File | Mô tả | Trạng thái |
|:---|:---|:---|:---:|
| **EdgeTTSProvider** | `providers/edge_tts_provider.py` | Microsoft Edge TTS (miễn phí) | ✅ WORKING |
| **VbeeTTSProvider** | `providers/vbee_tts.py` | Vbee cloud TTS (Vietnamese) | ✅ WORKING |
| **VieNeuLocalProvider** | `providers/vieneu_local.py` | VieNeu local TTS | ✅ WORKING |
| **ElevenLabsTTS** | `providers/elevenlabs_tts.py` | ElevenLabs API | ✅ WORKING |
| **GeminiTranslationProvider** | `providers/gemini_translation.py` | Google Gemini dịch thuật | ✅ WORKING |
| **FasterWhisperSTT** | `providers/faster_whisper_stt.py` | Faster-Whisper STT | ✅ WORKING |
| **CapCutTTS** | `providers/capcut_tts.py` | CapCut PC TTS API | ✅ WORKING |

### 2.2 Services

| Service | File | Mô tả | Trạng thái |
|:---|:---|:---|:---:|
| **TranscriptionService** | `services/transcription_service.py` | Chạy Whisper transcription | ✅ WORKING |
| **TranslationService** | `services/translation_service.py` | Dịch qua Gemini/ChatGPT | ✅ WORKING |
| **TTSService** | `services/tts_service.py` | Voice generation | ✅ WORKING |
| **RenderService** | `services/render_service.py` | FFmpeg render video | ✅ WORKING |
| **CapCutExport** | `services/capcut_export.py` | Export CapCut Draft | ✅ WORKING |
| **MaskService** | `services/mask_service.py` | Blur region handling | ✅ WORKING |
| **ScriptService** | `services/script_service.py` | Script management | ✅ WORKING |
| **SubtitleService** | `services/subtitle_service.py` | SRT/ASS handling | ✅ WORKING |
| **ClipExportService** | `services/clip_export_service.py` | Clip extraction | ✅ WORKING |
| **CredentialService** | `services/credential_service.py` | Windows Credential Manager | ✅ WORKING |
| **UsageService** | `services/usage_service.py` | API usage tracking | ✅ WORKING |
| **HealthService** | `services/health_service.py` | System health check | ✅ WORKING |
| **CacheService** | `services/cache_service.py` | Translation cache | ✅ WORKING |
| **ModelService** | `services/model_service.py` | AI model management | ✅ WORKING |
| **AudioMixService** | `services/audio_mix_service.py` | Audio mixing | ✅ WORKING |
| **ProjectService** | `services/project_service.py` | Project management | ✅ WORKING |
| **UpdateService** | `services/update_service.py` | Auto-update | ✅ WORKING |
| **CostService** | `services/cost_service.py` | API cost tracking | ✅ WORKING |
| **RecoveryService** | `services/recovery_service.py` | Crash recovery | ✅ WORKING |
| **SRTVservice** | `services/srt_service.py` | SRT parsing/writing | ✅ WORKING |

### 2.3 Orchestrator

| Module | File | Mô tả | Trạng thái |
|:---|:---|:---|:---:|
| **PipelineRunner** | `orchestrator/pipeline_runner.py` | Auto Dub 4-step pipeline | ✅ WORKING (FIXED) |
| **PipelineState** | `orchestrator/pipeline_state.py` | State management | ✅ WORKING |
| **Checkpoint** | `orchestrator/checkpoint.py` | Resume support | ✅ WORKING |

### 2.4 Web Server (FastAPI)

**File:** `web/server.py`

#### API Endpoints - 39 endpoints

| Route | Method | Mô tả | Trạng thái |
|:---|:---|:---|:---:|
| `/api/health` | GET | Health check | ✅ |
| `/api/bridge/status` | GET | Browser bridge status | ✅ |
| `/api/settings` | GET/POST | Settings | ✅ |
| `/api/voices` | GET | List TTS voices | ✅ |
| `/api/voices/preview` | POST | Preview voice | ✅ |
| `/api/media/select` | POST | Select video | ✅ |
| `/api/media/sample` | POST | Load sample video | ✅ |
| `/api/media/upload` | POST | Upload video | ✅ |
| `/api/media/stream` | GET | Stream video | ✅ |
| `/api/masks` | GET/POST | Blur masks | ✅ |
| `/api/pipeline/start` | POST | **Start pipeline** | ✅ FIXED |
| `/api/pipeline/cancel` | POST | Cancel pipeline | ✅ |
| `/api/pipeline/status` | GET | Get status | ✅ |
| `/api/review/subtitles` | GET/POST | Subtitles review | ✅ |
| `/api/review/approve` | POST | Approve script | ✅ |
| `/api/export/capcut` | POST | Export CapCut | ✅ |
| `/api/export/mp4` | POST | Export MP4 | ✅ |
| `/api/downloader/inspect` | POST | Inspect URL | ✅ |
| `/api/downloader/download` | POST | Download video | ✅ |
| `/api/downloader/history` | GET | Download history | ✅ |
| `/api/data-studio/overview` | GET | Storage stats | ✅ |
| `/api/data-studio/assets` | GET | List assets | ✅ |
| `/api/data-studio/duplicates` | GET | Find duplicates | ✅ |
| `/api/data-studio/assets/delete` | POST | Delete asset | ✅ |
| `/api/data-studio/folder-tree` | GET | Folder tree | ✅ |
| `/api/auto-video/templates` | GET | Templates | ✅ |
| `/api/auto-video/assets` | GET | List assets | ✅ |
| `/api/auto-video/script/parse` | POST | Parse script | ✅ |
| `/api/auto-video/projects` | GET/POST | Projects CRUD | ✅ |
| `/api/auto-video/projects/{id}` | GET/DELETE | Project detail | ✅ |
| `/api/auto-video/projects/{id}/render` | POST | Render project | ✅ |
| `/api/auto-video/download/{id}` | GET | Download video | ✅ |
| `/api/projects/recent` | GET | Recent projects | ✅ |
| `/api/projects/load` | POST | Load project | ✅ |
| `/ws/pipeline` | WebSocket | Real-time progress | ✅ |

---

## 3. WEB UI (frontend/src)

### 3.1 Routes/Pages

| Route | Component | Mô tả | Trạng thái |
|:---|:---|:---|:---:|
| `/` (home) | `HomeView.jsx` | Dashboard | ✅ WORKING |
| `/auto-dub` | `App.jsx` (inline) | Auto Dub Studio | ✅ WORKING |
| `/downloader` | `DownloaderView.jsx` | Universal Downloader | ✅ WORKING |
| `/data-studio` | `DataStudioView.jsx` | Data Studio | ✅ WORKING |
| `/auto-video` | `AutoVideoView.jsx` | Auto Video Generator | ⚠️ UI_ONLY |
| `/social` | Inline placeholder | Social Publisher | 🔴 STUB |
| `/today` | Inline placeholder | Today Dashboard | 🔴 STUB |

### 3.2 Auto Dub Steps

| Step | File | API | Trạng thái |
|:---|:---|:---|:---:|
| 1. Source Video | `Step1.jsx` (inline) | `/api/media/upload` | ✅ WORKING |
| 2. Voice Selection | `Step2.jsx` (inline) | `/api/voices/preview` | ✅ WORKING |
| 3. Blur Regions | `Step3.jsx` (inline) | `/api/masks` | ✅ WORKING |
| 4. Pipeline | `Step4.jsx` (inline) | `/api/pipeline/start` | ✅ WORKING |
| 5. Review/Export | `Step5.jsx` (inline) | `/api/export/*` | ✅ WORKING |

### 3.3 Global Components

| Component | File | Mô tả |
|:---|:---|:---|
| `IconRail` | `IconRail.jsx` | Left sidebar navigation |
| `Topbar` | `Topbar.jsx` | Header with status badges |
| `InteractiveCanvas` | `InteractiveCanvas.jsx` | Draggable blur masks |
| `AskKappakDrawer` | `AskKappakDrawer.jsx` | AI Chat (STUB) |
| `DynamicIsland` | Inline | Status pill |

---

## 4. AUTO DUB PIPELINE (Chi Tiết)

### 4.1 Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AUTO DUB 4-STEP PIPELINE                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │   4.1    │───►│   4.2    │───►│   4.3    │───►│   4.4    │     │
│  │ Whisper  │    │ Gemini/  │    │  Script  │    │   TTS    │     │
│  │   STT    │    │ ChatGPT  │    │  Prep    │    │  Voice   │     │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘     │
│       │                │                │                │              │
│       ▼                ▼                ▼                ▼          │
│  original.srt    translated.srt    voice_script.txt   *.mp3         │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │              Translation Fallback Order                          │ │
│  │  1. ChatGPT (via Edge Extension LocalAgent)                     │ │
│  │  2. Gemini API ◄── FIXED (was copy original)                    │ │
│  │  3. Copy original (only if no API key)                         │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Output Files

| File | Mô tả | Ví dụ |
|:---|:---|:---|
| `original.srt` | Phụ đề gốc (Whisper) | 317 câu tiếng Trung |
| `translated.srt` | Phụ đề dịch (Gemini) | 317 câu tiếng Việt |
| `voice_script.txt` | Script voice (clean) | 317 dòng text |
| `vbee_master_raw.mp3` | Voice AI raw | ~9MB audio |
| `master_narration_timeline.mp3` | Timeline sync | ~1.7MB |
| `.pipeline_checkpoint.json` | Resume checkpoint | State save |

---

## 5. CÁC MODULE ĐÃ LIÊN KẾT VỚI WEB UI

### ✅ ĐÃ HOẠT ĐỘNG (Connected)

| Module | Backend | Web UI | API |
|:---|:---|:---|:---|
| Auto Dub Pipeline | ✅ | ✅ | `/api/pipeline/*` |
| Universal Downloader | ✅ | ✅ | `/api/downloader/*` |
| Data Studio | ✅ | ✅ | `/api/data-studio/*` |
| Media Upload | ✅ | ✅ | `/api/media/*` |
| Voice Preview | ✅ | ✅ | `/api/voices/preview` |
| Mask/Blur | ✅ | ✅ | `/api/masks` |
| Export MP4 | ✅ | ✅ | `/api/export/mp4` |
| Export CapCut | ✅ | ✅ | `/api/export/capcut` |

---

## 6. CÁC MODULE CHƯA HOẶC ÍT LIÊN KẾT

### ⚠️ UI_ONLY (Có UI, thiếu logic)

| Module | Backend | Web UI | Vấn đề |
|:---|:---|:---|:---|
| **Auto Video Generator** | ✅ | ✅ | UI đầy đủ nhưng chỉ mock |
| **Ask KAPPAK AI** | ❌ | ✅ | Không có LLM backend |

### 🔴 STUB (Chỉ có UI placeholder)

| Module | Backend | Web UI | Vấn đề |
|:---|:---|:---|:---|
| **Social Publisher** | ❌ | ✅ | Không có logic |
| **Today Dashboard** | ❌ | ✅ | Không có logic |

---

## 7. CÁC BACKEND COMPONENTS CHƯA KẾT NỐI WEB UI

### 7.1 Providers (Đã hoạt động nhưng UI chưa dùng hết)

| Provider | Web UI Status | Ghi chú |
|:---|:---|:---|
| **ElevenLabsTTS** | ⚠️ UI có dropdown | Chưa chọn được trong UI |
| **VieNeuLocal** | ⚠️ UI có dropdown | Chưa chọn được trong UI |
| **CapCutTTS** | ⚠️ UI có dropdown | Chưa chọn được trong UI |

### 7.2 Services (Backend-only)

| Service | Web UI | Ghi chú |
|:---|:---|:---|
| **TranscriptionRunner** | ✅ Qua PipelineRunner | Chạy tự động |
| **TranslationService** | ✅ Qua PipelineRunner | Chạy tự động |
| **CredentialService** | ✅ Settings dialog | Desktop only |
| **UsageService** | ✅ API Cost dialog | Desktop only |
| **CacheService** | ✅ Tự động | Translation cache |
| **UpdateService** | ✅ Desktop check | Desktop only |
| **RecoveryService** | ✅ Tự động | Crash recovery |
| **CostService** | ✅ Desktop | Desktop only |

---

## 8. FIXES ĐÃ THỰC HIỆN (2026-09-19)

### 8.1 Pipeline Translation Fallback (FIXED)

**Vấn đề:** Khi không có ChatGPT (Edge Extension), hệ thống copy nguyên script gốc thay vì dịch.

**Fix:** Thêm Gemini API làm fallback.

**Files changed:**
- `src/vkdub/orchestrator/pipeline_runner.py`
- `src/vkdub/domain/transcript.py`

**Code changes:**

```python
# Before (BUG)
if not is_chatgpt_ready:
    raw_translated_srt = raw_original_srt  # ← Copy nguyên!

# After (FIXED)
if is_chatgpt_ready:
    raw_translated_srt = self.local_agent.translate_srt_sync(...)
elif is_gemini_ready:
    raw_translated_srt = self._translate_with_gemini(...)
else:
    raw_translated_srt = raw_original_srt  # Only as last resort
```

---

## 9. DESKTOP UI (PySide6)

### 9.1 Entry Points

| Entry | Command | Mô tả |
|:---|:---|:---|
| Web Mode | `python app.py` | FastAPI + React |
| Desktop Mode | `python app.py --gui` | PySide6 GUI |

### 9.2 Desktop Controllers

| Controller | File | Mô tả |
|:---|:---|:---|
| `TranslationController` | `ui/translation_controller.py` | Translation with Gemini |
| `TTSController` | `ui/tts_controller.py` | TTS management |
| `StudioVoiceController` | `ui/studio_voice_controller.py` | Voice settings |
| `ReviewController` | `ui/review_controller.py` | Subtitle review |

---

## 10. DATABASE

### 10.1 SQLite Schema

**File:** `src/kappak/core/db.py`

| Table | Mô tả |
|:---|:---|
| `assets` | Downloaded videos/audio |
| `projects` | Auto Dub projects |
| `auto_video_projects` | Auto Video projects |
| `usage_log` | API usage tracking |

---

## 11. BROWSER EXTENSION

### 11.1 Native Messaging Host

**File:** `tools/native_host/vkdub_host.py`

Kết nối Edge/Chrome extension với desktop app qua Native Messaging (32-bit JSON framing).

---

## 12. CÁC BƯỚC PHÁT TRIỂN TIẾP THEO

### Ưu tiên cao:
1. **Auto Video Generator** - Kết nối backend với UI
2. **Ask KAPPAK AI** - Kết nối với Gemini/ChatGPT API

### Ưu tiên trung bình:
3. **Social Publisher** - Xây dựng từ đầu
4. **Today Dashboard** - Xây dựng từ đầu

### Ưu tiên thấp:
5. **Test Coverage** - Bổ sung unit tests
6. **Production Scale** - Auto-update, i18n, batch processing

---

## 13. CÁCH CHẠY TEST

### 13.1 Web Server
```bash
python app.py
# Mở: http://localhost:8000
```

### 13.2 Desktop GUI
```bash
python app.py --gui
```

### 13.3 Backend API Test
```bash
# Health check
curl http://localhost:8000/api/health

# Start pipeline
curl -X POST http://localhost:8000/api/pipeline/start \
  -H "Content-Type: application/json" \
  -d '{"video_path": "docs/evidence/media/sample.mp4"}'

# Check status
curl http://localhost:8000/api/pipeline/status
```

### 13.4 Python Test Script
```bash
python test_auto_dub_pipeline.py
```

---

## 14. ENVIRONMENT & DEPENDENCIES

### 14.1 Python Version
- Python 3.12

### 14.2 Key Dependencies
| Package | Version | Purpose |
|:---|:---|:---|
| FastAPI | 0.104+ | Web server |
| PySide6 | 6.6+ | Desktop GUI |
| faster-whisper | 0.9+ | STT |
| edge-tts | 6.1+ | TTS |
| httpx | 0.25+ | HTTP client |
| yt-dlp | 2024+ | Downloader |
| ffmpeg | latest | Media processing |

### 14.3 External Tools
| Tool | Path | Purpose |
|:---|:---|:---|
| ffmpeg | `tools/ffmpeg.exe` | Video/audio processing |
| ffprobe | `tools/ffprobe.exe` | Media metadata |

---

## 15. SECURITY

### 15.1 API Keys
- Lưu trong Windows Credential Manager
- Không hardcode trong code
- Sử dụng `CredentialStore` class

### 15.2 Log Security
- `SecretFilter` tự động redact API keys
- Không log secrets ra console

### 15.3 Subprocess Safety
- Dùng `args_list` thay vì `shell=True`
- Kill process tree khi hủy

---

## 16. LOGGING

- **File:** `logs/vkdub.log`
- **Format:** Structured logging với `SecretFilter`
- **Levels:** DEBUG, INFO, WARNING, ERROR

---

## 17. CONTACT & SUPPORT

- **Tác giả:** vanhkhuc.dev
- **GitHub:** VK Dub Studio repository
- **Discord:** Notification via webhook
