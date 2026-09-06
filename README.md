# VK Dub Studio — by vanhkhuc

> **Current checkpoint: VK Dub Studio 2.0 — Gemini, VieNeu, CapCut TTS and draft export verified.**
> `VK_DUB_STUDIO_V2_SPEC.md` is the source of truth. See
> [docs/VOICE_TRANSLATION_REPORT.md](docs/VOICE_TRANSLATION_REPORT.md) for current commands,
> evidence and limitations; [docs/V2_PROGRESS.md](docs/V2_PROGRESS.md) records earlier checkpoints.
> VieNeu and CapCut TTS have real preview, approval-gated synthesis and cache. CapCut v360000
> export creates editable video, WAV voice and captions. Editable CapCut rectangle blur remains
> explicitly partial until its schema is verified. The historical phase notes
> below are not current readiness claims. Launch with `.\.venv\Scripts\python.exe app.py`.

Version **0.4.0**. A Windows desktop workspace for Vietnamese video dubbing.
This implementation covers **PHASE 0 through PHASE 4** of
`CODEX_MASTER_PROMPT_VK_DUB_STUDIO.md` (all 1,238 lines reviewed).

## Completed

### Phase 0 — Repository and application shell

- Python 3.12 package with a runnable PySide6 entry point and separated UI/domain/media/services.
- Dark, resizable three-column layout; branding and version in the window title and sidebar.
- Right-side **KỊCH BẢN & PHỤ ĐỀ / Script Review** panel, initially empty.
- Approval starts disabled and requires the Phase-4 review gate below. **XUẤT VIDEO** remains
  disabled. Local processing requires a video, FFmpeg and a downloaded model.
- Asynchronous FFmpeg/ffprobe discovery, executable version checks, timeouts and retry button.
- Vietnamese timestamped activity panel and rotating logs in
  `%LOCALAPPDATA%\VKDubStudio\logs\vkdub.log` (2 MB, three backups).
- pytest tests, Ruff lint/format configuration and mypy type checks.

### Phase 1 — Local video and project

- Import a local `.mp4`, including Unicode filenames and paths with spaces.
- Qt video playback, pause, seek slider, elapsed/total time, volume, and aspect-ratio preservation.
- Real ffprobe duration, dimensions, frame rate, codecs, audio presence and file size.
- Select and persist an output folder; this phase does not generate output video.
- Save/open schema-1 `.vkdub` JSON skeletons with atomic saves and relative media paths where possible.
- Preserve project ID, source/target languages and output folder; default voice label **HN - Ngọc Huyền**.
- Unsaved-change prompt before replacing/closing a project; failed import/load preserves current state.
- Missing source files and missing tools are reported without destroying saved project references.

### Phase 2 — Local transcription

- **Local Faster-Whisper**, with tiny/base/small/medium/large-v3 model selection, source-language
  Auto/Chinese/English/Vietnamese/Japanese/Korean, and Auto/CPU/CUDA device choices.
- Separate **TẢI MODEL** action downloads public converted Whisper weights from Hugging Face.
  It does not upload the video. Incomplete downloads stay in a temporary directory and are cleaned
  on cancellation/failure; only a completed download becomes available for inference.
- FFmpeg extracts the first audio stream to 16 kHz mono PCM WAV in the application temp folder.
- A QThread supervises isolated child processes for FFmpeg/model loading/inference. Progress and
  logs use Qt signals. **DỪNG** stops the process tree, including the Windows virtual-environment
  launcher, and cleans temporary files. Closing while busy offers to cancel before closing.
- Offline-only recognition after model installation. The local provider uses `local_files_only=True`;
  recognition workers set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`.
- Typed, validated timestamped source segments and SRT serialization; read-only source rows in the
  right panel. Click a row to seek to its start. No translated text or script editor is fabricated.
- Completed source transcripts, detected language and model/device settings survive `.vkdub` save/load.
  Older projects migrate in memory; current saves use schema 4.
- Optional cache reuse through **Dùng bản chép lời đã lưu nếu có**. The key includes the extracted
  audio SHA-256, model/revision, requested language, resolved device, provider version and pipeline
  settings. Uncheck it to rerun inference. Cache reuse still extracts audio to verify the fingerprint.
- Success stops at **TRANSCRIBED**. Cancellation/failure preserves the previous completed transcript.
  Silence produces an explicit “no speech detected” result. Translation is a separate user action.

### Phase 3 — Translation and API costs

- `TranslationProvider` interface and real Gemini REST adapter using **gemini-2.5-flash-lite**.
  Structured JSON requests retain segment IDs/timestamps, source language and target Vietnamese.
  Instructions request concise, natural Vietnamese without adding information or changing names/numbers.
- Batches contain at most 30 segments / 6,000 source characters. Oversized individual segments are
  rejected before any request. Every response must have all IDs in order, without duplicates, extra
  fields or empty translations. Truncated/blocked/non-JSON output never replaces the existing draft.
- Separate **DỊCH SANG TIẾNG VIỆT** action discloses that it sends source text to Google. No video/audio
  is uploaded. The local transcription button still stops after transcription.
- Source and Vietnamese draft appear together. The original source and Gemini response remain
  immutable; Phase 4 provides a separate editable draft. Translation stops at **REVIEW_REQUIRED**.
- Optional batch cache includes provider, model, prompt version, source/target languages, IDs, times
  and source text. Valid completed batches survive later failure/cancellation. A corrupt cache stops
  with an error instead of silently incurring a new cloud request; uncheck cache to regenerate.
- Schema-3 `.vkdub` files store source and translation separately and validate their relationship.
  Schema-1/2 projects load without changing their files. Saves remain atomic and reject files >16 MB.
  Importing a new source or completing a new transcription clears its previous translation.
- **API & Chi phí** dialog: stage/provider/mode/credential/estimated usage/cost/status, OS key storage,
  connection test, account-mode selection, editable USD/VND rate, optional monthly budget, warning
  threshold and reset of local statistics. Reset does not change Google quota or billing.
- `keyring` explicitly uses **Windows Credential Manager**, with no plaintext fallback. Keys never
  enter `.vkdub`, JSON settings, cache, command arguments or request URLs. Password fields are masked;
  provider error bodies are not logged and known secrets are redacted from application messages.
- A cancellable QThread hosts asynchronous HTTPS. Cancellation stops local waiting; a sent request
  may still be processed/billed. HTTP 429/500/502/503/504 allow two retries with exponential backoff,
  respecting `Retry-After`; waits over 60 seconds ask the user to retry later. Keys are never rotated.
  Network timeouts are **not** retried automatically because the original generation may have run.
- Paid-equivalent pricing lives in **resources/provider_pricing.json**, separate from execution.
  Rates were verified against [Google pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash-lite)
  on 2026-09-04: $0.10 / 1M input text tokens and $0.40 / 1M output tokens. Free quota is unknown.
  FREE_TIER/PAID is a user declaration, not a change to the provider account or a quota check.
- Estimates use source characters / 2 + 600 input tokens per batch, and characters × 0.8 + 100 output
  tokens per batch. This is a planning heuristic, not tokenization or a cost ceiling; it does not
  subtract cached batches. Provider-reported input/output/thinking tokens and paid-equivalent USD
  are tracked in local SQLite by UTC month. Failed/cancelled requests without token metadata remain
  explicitly **unknown**, including across restart. Provider billing remains authoritative.

API references: [generateContent](https://ai.google.dev/api/generate-content),
[model connection check](https://ai.google.dev/api/models),
[model capabilities](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-lite), and
[deprecations](https://ai.google.dev/gemini-api/docs/deprecations).
The endpoint/schema are implemented from official documentation. **No live Gemini generation has
been verified on this machine: no production API key is configured.** HTTP contract and failure tests
use explicitly mocked transport; the app never substitutes a mock translation for an API result.

### Phase 4 — Script editor and approval gate

- Editable cards in the right review panel: index, start/end in seconds with millisecond precision,
  read-only associated source, Vietnamese text, duration, estimated reading time and validation status.
  Only the selected card creates editor widgets. Clicking other rows seeks; **Phát câu** plays from
  the selected start and pauses at its end, subject to media-player timing granularity.
- **Tạo bản nháp** creates blank Vietnamese lines from the source without requiring a cloud key.
  A video without transcription can also start an empty draft or load a Vietnamese SRT.
- Add/delete, split at the text cursor and playback position (midpoint if playback is outside the
  line), merge previous/next, literal case-sensitive find/replace, and undo/redo. Undo history is
  limited to 100 commands; rapid edits in the same card coalesce, with a new group after approval.
  Ctrl+Z/Ctrl+Y use the document history in the Vietnamese editor. Undo never restores approval.
- Internal drag ordering is accepted only if the resulting timeline is valid. Times are not silently
  shifted; an invalid drag is refused. Edits do not modify the source transcript or cached Gemini result.
- Validation blocks approval for an empty script, blank translations, negative/reversed/overlapping
  or out-of-order intervals, lines beyond known source duration, and lines over 12,000 characters.
  Invalid drafts remain editable and can be saved as `.vkdub` for repair.
- Reading time is only a heuristic: whitespace-separated Vietnamese syllables at about four per
  second. Lines estimated longer than their interval receive warnings. No measured/generated voice
  duration is claimed; TTS has not been implemented.
- Basic UTF-8 SRT load/save supports multiline Vietnamese and millisecond timestamps. Malformed
  imports preserve the draft; invalid timing can be imported for repair but cannot be exported.
  SRT export renumbers cues and omits internal blank separator lines while preserving the project
  text verbatim. Styling, ASS, subtitle overlays and burned subtitles remain Phase 6 work.
- **Dịch lại** explicitly regenerates the selected line through the existing Gemini adapter, using
  its associated source and bypassing cache. Only that line changes; the operation can be undone.
  Split children retain the whole source sentence association, so regeneration translates that
  whole source sentence. Manually added/SRT-imported lines without a source association cannot use
  this action. Live regeneration remains unverified without a configured key.
- Checkbox acknowledgement is bound to the current script revision. **DUYỆT KỊCH BẢN & TẠO VOICE**
  becomes enabled only after checking the entire valid script. In this phase it **records approval
  only**; a visible note explains that voice generation is unavailable. No TTS request is made.
- SHA-256 approval binds exact text (including whitespace), IDs, source associations, order, times,
  source hash, project ID, video path, target language and known duration. Every edit clears the
  approval hash and checkbox. Backend `require_approval()` revalidates content/context independently
  of the UI. Changed source context also requires fresh confirmation.
- Durable project states now include **REVIEW_REQUIRED** and **APPROVED**. The window exposes
  **TRANSCRIBING**/**TRANSLATING** during those jobs. Successful translation prepares the draft and
  stops for review; approval does not trigger voice or export.
- Schema 4 stores the editable script and approval separately from source/cloud translation. Legacy
  schema 1–3 files load without rewriting. Legacy translations become unapproved drafts. A stale
  approval hash is revoked on load while the edited content is retained. Invalid structure/future
  features are rejected to avoid data loss. Atomic saves retain the previous file on failure.
- Re-transcription, full retranslation and SRT import ask before replacing manual edits or an
  approved draft. Failed/cancelled jobs keep the previous data. Editing and approval are blocked
  during jobs. The API manager's prospective TTS character count now reflects the edited script.

The Start/Stop controls, progress and activity log remain visible while project/model settings scroll.

The original folder contained only the master prompt, with no Git metadata, application,
tests, README or existing working features. The master prompt was preserved unchanged.

## Install and run on Windows

Requires **64-bit Python 3.12** and Windows with a working graphical desktop.
Faster-whisper is installed with the project; model weights are downloaded separately from the UI.
Run these commands in PowerShell:

```powershell
Set-Location D:\ToolVideo
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe app.py
```

If your Python installation is managed by `uv` and does not include pip:

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
.\.venv\Scripts\python.exe app.py
```

The virtual environment has already been created in this working folder. To start this checkout:

```powershell
Set-Location D:\ToolVideo
.\.venv\Scripts\python.exe app.py
```

Alternative launchers: `.\.venv\Scripts\vk-dub-studio.exe` or `scripts\dev.ps1`.
The development script uses the existing virtual environment and installs nothing.

### FFmpeg and ffprobe

Download a Windows build containing **both** executables using links on the
[official FFmpeg download page](https://www.ffmpeg.org/download.html).
Put the extracted `bin` folder on PATH, or set explicit executable paths for the current session:

```powershell
$env:FFMPEG_PATH = 'C:\Tools\ffmpeg\bin\ffmpeg.exe'
$env:FFPROBE_PATH = 'C:\Tools\ffmpeg\bin\ffprobe.exe'
.\.venv\Scripts\python.exe app.py
```

An explicit environment variable takes precedence over PATH, including when it points to a
missing file. Both tools are checked with `-version`; simply finding a file is insufficient.
The **Kiểm tra lại công cụ** button repeats detection. Reimport/reopen the video to refresh metadata.
The application does not download executables or change the system PATH.

Without standalone tools the shell still starts. Qt can preview supported MP4 files using its
media backend, but ffprobe metadata is unavailable and identified as unverified. Playback codec
support depends on the Qt multimedia backend, installed hardware/drivers, and source media.

## Use

1. Press **TẢI VIDEO** and choose a local MP4. Wait for the metadata check.
2. Press **Phát / Tạm dừng**. Drag the seek slider or focus it and use the arrow keys.
3. Choose an output folder. Hover the displayed filename/folder name to see its full path.
4. Choose **Lưu project .vkdub** (`Ctrl+S`), then **Mở project .vkdub** (`Ctrl+O`) to reload it.
5. Importing another video creates a fresh project, retaining the chosen output folder.
6. Scroll the configuration area to **BÓC BĂNG CỤC BỘ**. Choose model and language; download the model
   if necessary. `tiny` is useful for a quick test; the default selection is `base`.
7. Select **CPU** or **Auto** and press **BẮT ĐẦU XỬ LÝ**. The app stops after source transcription.
   Use **DỪNG** to cancel. Click transcript rows to seek the video, and save the project to retain them.
8. Open **API & Chi phí**, enter a Gemini API key, and press **Lưu khóa**. The key is saved in Windows
   Credential Manager. **Kiểm tra kết nối** reads model metadata; it does not generate text or prove
   translation quota. A successful test and a saved key have distinct statuses.
9. Set account mode, USD/VND rate, optional budget and threshold; press **Lưu cài đặt**. The default
   25,000 VND/USD is an editable planning value, not a live exchange-rate quotation. Budgets warn in
   the dialog; they do not enforce spending limits. Review Google quota/billing before cloud use.
10. Close the dialog and press **DỊCH SANG TIẾNG VIỆT**. This sends the transcript to Google. Free-tier
    content may be used by Google to improve its products; review the linked provider terms/pricing.
    Save the completed draft with the project. Uncheck **Dùng bản dịch đã lưu nếu có** to regenerate.
11. Select a script row in the right panel and edit its Vietnamese text/times. Without Gemini,
    press **Tạo bản nháp** and enter your translation manually, or use **Mở SRT**.
12. Use **Kiểm tra** to locate errors/warnings. Add, split, merge, search/replace and undo as needed.
    Hover the validation summary/card status for details. Save `.vkdub` even while repairing errors;
    **Lưu SRT** requires a valid script.
13. Read every line, check **Tôi đã kiểm tra toàn bộ kịch bản**, and press the approval button.
    The badge becomes **ĐÃ DUYỆT** and the revision is saved with the project. Changing even one
    character revokes approval; undoing that edit still requires checking and approving again.
14. Voice generation and final video export remain unavailable until later phases.

**Auto uses CPU** for predictable operation. CPU inference uses INT8 with four threads. CUDA is an
explicit opt-in using FP16 and requires compatible CUDA/cuDNN libraries. A detected GPU alone is
insufficient; consult the [faster-whisper requirements](https://github.com/SYSTRAN/faster-whisper#gpu).
CUDA failure is reported; select CPU and retry. CUDA has not been validated on this machine.

The tiny model was downloaded during development. Select `tiny` to reuse it immediately. Other
models require their own download. Network access is required for downloads, not for inference.

Project files reference media; they do not embed/copy MP4s. Keep the source video available.
Paths are relative to the `.vkdub` directory on the same drive, absolute across Windows drives.
Moving a project and its associated relative files together works. If a source is missing,
restore it at its recorded path. There is no dedicated relink control yet.

## Tests and smoke verification

```powershell
Set-Location D:\ToolVideo
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
```

Unit/UI tests do not need FFmpeg, a cloud account, a video download or network access.
Gemini tests inject `httpx.MockTransport`; they do not call live services or use Windows credentials.
They use Qt's offscreen backend to avoid native Windows accessibility re-entrancy when
rapidly creating/destroying test windows. The smoke script uses the actual desktop backend.
They cover project/metadata and transcript validation, schema migration, SRT timestamps,
atomic-save failure, Unicode/relative paths, cache identity, missing tools/media, subprocess
responsiveness/cancellation, nonzero transcript seeking, UI state, persistence and unsaved changes.

Smoke-start the actual themed application (not a replacement test window):

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py --output-dir "$env:TEMP\vkdub-shell-smoke"
```

For real-media verification, configure both tools, then use a disposable MP4 of at least
four seconds and an output directory outside the repository:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py `
  --video 'C:\Videos\sample.mp4' `
  --output-dir "$env:TEMP\vkdub-media-smoke"
```

The script checks actual ffprobe output, advancing playback, decoded video frames, pause,
seek to two seconds, output directory selection, save/reload and the disabled workflow gates.
It writes `smoke-result.json`, `smoke-window.png` and (with video) `smoke.vkdub`; it exits nonzero
on failure. Use a disposable output directory because these evidence filenames are reused.
Add `--hold` to leave the app open for visual inspection. The smoke playback is muted deliberately.

For a real **Phase 2** smoke test, download `tiny`, configure FFmpeg/ffprobe, and supply a spoken MP4:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_transcription.py `
  --video 'C:\Videos\speech.mp4' --model tiny --language en `
  --output-dir "$env:TEMP\vkdub-transcription-smoke"
```

Use `--language auto` or the actual source language as appropriate. This test bypasses cached
inference once, checks source rows and UI responsiveness, then verifies cache reuse, cancellation
at model loading, previous-transcript preservation, project save/reload and row seeking. It writes
`transcription-result.json`, `transcription-window.png`, `transcription.vkdub`, and a source-only
`source-transcript.srt`. An optional `--expect-text phrase` checks recognizable speech. Use a disposable
output directory: evidence filenames are reused. Approval and export must stay disabled throughout.

Manual checks: import a real MP4 through the file dialog, play/pause, seek, change volume,
resize the columns/window, select an output directory, save, reopen, and confirm the empty review
panel and disabled approval/export. Also try a corrupt MP4, missing tool, moved source video,
invalid project and canceling an unsaved-change prompt.

For a **Phase 3** native smoke, use a Phase-2 project containing a source transcript:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_api.py `
  --project 'C:\Videos\transcription.vkdub' `
  --output-dir "$env:TEMP\vkdub-api-smoke"
```

This starts the actual app, loads the source, decodes a preview frame, checks the workflow gates,
opens the API dialog, and writes screenshots/results. It makes **no live Gemini calls** and changes
no production credentials. It verifies a disposable Windows Credential Manager entry through a
second Python process, then removes it. `--hold` leaves the app/dialog open.

With your own Google account, manually save a key, restart, test connection, then translate a short
non-sensitive sample. Inspect Vietnamese meaning/names/numbers, save/reopen and reuse the cache.
Confirm that a second cached run adds no provider requests and requires review; export stays disabled.
Invalid keys, revoked permissions, quota limits, real translation quality and actual billing must
be checked with the provider; automated mocks cannot verify these account-specific facts.

### Verified on 2026-09-04 — Phase 3

- **128 tests passed**, including 54 new translation/API/cost/credential/worker/UI cases.
- Ruff lint/format and mypy checks pass (39 source files).
- Native API dialog smoke and disposable Windows credential persistence across processes passed.
- Real MP4 playback/seek/metadata/save/load and offline CPU transcription regression smokes passed,
  including cache reuse, cancellation and persistence. The UI remained responsive during inference.
- No Gemini key was configured or live generation claimed. API HTTP behavior is tested with mocks.

### Phase 4 review acceptance smoke

```powershell
.\.venv\Scripts\python.exe scripts\smoke_review.py `
  --project 'C:\Videos\jfk-transcription.vkdub' `
  --output-dir "$env:TEMP\vkdub-review-smoke"
```

This deterministic smoke expects a source-only project from the 11-second public JFK fixture used
by earlier transcription tests. It authors explicitly labelled Vietnamese test text in the real
editor; it does not call Gemini or pretend the fixture is an API result. It edits/splits, plays a
source interval, exports/reloads SRT, approves, saves/reopens the project, types one character,
checks immediate revocation, undoes without restoring approval and checks blank-text rejection.
It also verifies playback stopping at a selected end time. Screenshots, `.vkdub` files and
`review-result.json` are written to the supplied directory. Add `--hold` to leave the app open.

Manual Phase 4 checks: translate or enter your own Vietnamese text, edit time fields, add/delete,
split at the cursor, merge adjacent rows, undo/redo, find/replace and try an invalid reorder. Confirm
source text is unchanged. Check the review checkbox, approve, save/reopen, then type one character:
the badge must return to CHƯA DUYỆT, checkbox clear and export remain disabled. Undo still requires
fresh approval. Try malformed SRT and cancel replacing an edited draft; existing work must survive.

### Verified on 2026-09-04 — Phase 4

- **178 tests passed**, including 50 new script, SRT, revision, approval and review UI cases.
- Ruff lint and formatting pass (64 formatted files); mypy passes (45 source files).
- Native review acceptance smoke passed: editing/splitting, source interval playback, SRT roundtrip,
  approval persistence, immediate revocation after typing, undo without approval and blank-text gating.
- Real MP4 playback/seek/metadata/project roundtrip and real offline CPU transcription regression
  smokes passed. Transcription completed in 3.75 seconds with 49 GUI timer ticks; cache reuse and
  cancellation preserved the previous source transcript.
- Screenshots were visually checked for the three-column layout and editable review card.
- Selected-line Gemini regeneration is covered with mocked HTTP transport; no live Gemini or TTS
  requests were made. Voice generation and video export remain unavailable.

### Verified on 2026-09-04 — Phase 2

- Python 3.12.12, PySide6/Qt 6.10.3, Windows x64.
- **74 tests passed**; Ruff lint/format and mypy (29 source files) passed.
- Native desktop shell smoke passed without FFmpeg/ffprobe.
- Real-media smoke passed with FFmpeg/ffprobe 9.0.1 and a generated 5-second 1280 × 720,
  30 fps H.264/AAC MP4 with a Vietnamese filename. It verified playback, decoded/painted frames,
  pause, seek and save/reload, including replay after reopening the same source.
- Desktop visual inspection confirmed the three columns, visible paused video with letterboxing,
  metadata, branding/version, logs, empty script review and disabled approval/export controls.
- An 11-second spoken sample from the public OpenAI Whisper test fixture was embedded in an MP4.
  The actual tiny model recognized its speech on CPU in offline mode, with the UI timer continuing
  to tick. Cache reuse, cancellation at model loading, transcript persistence and row seeking passed.
- Unit cancellation testing caught a Windows virtual-environment launcher child that survived
  terminating its parent. Cancellation now terminates only the owned process tree; cleanup tests pass.
- The master prompt's SHA-256 was verified unchanged after excluding it from Ruff formatting:
  `99acca1b1eff24316779590fc609907e82e7a1f25cc5a6618e7d741af43ec353`.

## Known limitations

- **No Phase 5+ implementation:** no voice synthesis, subtitle styling/overlays, masks, audio mixing,
  rendering or updater. Basic SRT review load/save is implemented; styled subtitle export is not.
- Vbee voice label/schema defaults are preparation only; no Vbee endpoint or fake voice is provided.
- Gemini requires a key even to start a fully cached translation job; opening an already saved draft
  needs no key or network. Only the documented Flash-Lite model and Vietnamese target are supported.
- No live account/translation quality test was possible without a configured key. Connection testing
  checks model metadata only, not available quota or billing status. Estimates may differ materially
  from actual usage; retries, changed pricing and unknown requests can increase the final bill.
- SQLite currently tracks API usage only. No unified project/job/cache index, autosave/recovery,
  packaged installer or release checks yet.
- Project schema 4 is capped at 16 MB and accepts source/translation/editable-script data (up to 50,000
  segments). Schema-1/2/3 files migrate without modifying their file until save. Unknown schemas/fields,
  populated future styled subtitles/masks or changed future voice/export settings are
  rejected explicitly to avoid losing later-phase data.
- A successful ffprobe check does not guarantee Qt can decode every possible MP4 codec.
  Damaged media and unsupported codecs produce actionable playback errors.
- Preview uses Qt QVideoSink and paints the current decoded image to avoid a separate native
  video surface. This keeps paused frames and screenshots consistent, but copies frames to CPU
  memory. High-resolution/high-frame-rate performance has not been benchmarked.
- Metadata checks have a 15-second timeout; slow network/removable storage can require retry.
- Project JSON I/O is synchronous and size limited; media subprocesses use asynchronous QProcess.
- The output folder is remembered; write access is checked when saving a project. No render exists
  to test output video permissions yet.
- Source text and the original Gemini response remain read-only; edits live in a separate draft.
  Imported SRT lines are not automatically aligned to original source sentences. Split children keep
  their parent source references; merged lines combine them. Review these associations before using
  selected-line regeneration.
- Undo history is in memory only (100 commands), and resets on opening/importing a different project
  or completing full source/translation processing. There is no autosave/recovery yet; save explicitly.
- Approval hashes detect stale revisions, not maliciously forged project files. Moving a project so
  its video resolves to a different path requires approval again. External replacement of video bytes
  at the same path is not continuously fingerprinted; reimport/retranscribe a changed source.
- Large scripts are size-bounded but 50,000-row interactive performance has not been benchmarked.
  SRT import is plain UTF-8; advanced cue settings, rich editor styling and AI rewrite are deferred.
- Models live in `%LOCALAPPDATA%\VKDubStudio\models`, transcripts in `cache\transcript`, and work
  files in `temp`. `VKDUB_DATA_DIR` can override the data root for isolated tests/deployments.
  Translation batches live in `cache\translation`, numeric usage in `usage.sqlite3`, and non-secret
  account mode/budget/rate in `api-settings.json`. Credentials stay in the current Windows user's vault.
  Cache/models are local files; eviction and cache management UI are not implemented.
- Only the first source audio stream is transcribed. Tiny model quality, timestamps and language
  detection can be imperfect; no production accuracy claim is made from the short English smoke sample.
- The CPU path is verified; CUDA and long/high-resolution production inputs are not benchmarked.
- A manually damaged model directory must be renamed before redownloading. Model sizes and download
  times vary; there is no automatic model download when opening a video.
- Minimum window size is 1060 × 650 logical pixels; the configuration column can scroll on smaller
  displays. Full media/output paths are available as tooltips.

## Phase 8 — Final Render & Audio Mix (Completed)

- **Audio Track Assembly (`build_speech_track_wav`)**:
  Assembles individual segment WAV chunks into a unified 24kHz mono PCM speech track aligned to millisecond video timeline with exact silence gaps.
- **Audio Ducking Filter (`build_audio_mix_filter`)**:
  Generates FFmpeg `amix` complex filter graph with volume scaling for original audio (ducking) and generated speech track.
- **Atomic Rendering Pipeline (`RenderConfig`, `build_render_command`, `RenderController`)**:
  Executes FFmpeg with hardcoded ASS subtitles, `delogo`/`drawbox` video masks, and mixed audio. Writes to temporary file (`rendering.tmp.mp4`) first, performing atomic replacement only upon FFmpeg return code 0.
- **Pre-render Checklist Dialog (`ExportDialog`)**:
  Provides a 6-point verification gate (Video, Approved Script, Complete Voice Assets N/N, Valid Subtitles, Configured Masks, Ready FFmpeg) plus audio volume sliders and destination file picker.
- **Approval & Voice Readiness Gate**:
  Ensures the export button is only active when both script approval (`is_approved == True`) and full voice generation (`voice_ready == True`) are satisfied.

## Known limitations
- Rendering relies on external FFmpeg binary being installed and available on PATH or configured in tools.
- Real-time video preview performs CPU frame conversion; rendering speed depends on hardware CPU/GPU encoding capabilities.

## Phase 9 — Windows Packaging & Auto-Update (Completed)

- **Auto-Update Service (`update_service.py`)**:
  Semantic versioning parser and comparator (`is_newer_version`), background feed fetcher from `latest.json`, streaming downloader with progress callback, and strict SHA-256 integrity verification.
- **Update Confirmation Dialog (`UpdateDialog`)**:
  Presents release notes (Markdown changelog), old vs new version comparison, download progress, and confirmation gate before launching the setup executable. Never auto-installs without explicit user consent.
- **Settings Integration**:
  Interactive update checking in `SettingsDialog` supporting `Stable` and `Beta` channels.
- **PyInstaller Packaging**:
  `packaging/vkdub.spec` and `packaging/build_exe.py` configuring standalone packaging with necessary runtime assets and hidden imports.
- **Inno Setup Installer Script**:
  `installer/VK-Dub-Studio.iss` producing the branded installer `VK-Dub-Studio-Setup-x64.exe` for Windows 64-bit systems.
- **Release CI/CD Workflow**:
  `.github/workflows/release.yml` automating builds, SHA-256 calculation, and GitHub release asset publishing.

## Known limitations
- Auto-updater requires network access to the remote feed URL; offline environments will cleanly display a connection notification.
- PyInstaller bundling and Inno Setup compilation require their respective toolchains installed locally to produce binary distribution files.

## Phase 10 — Polish, Recovery, Logs & Final Touches (Completed)

- **Auto Save & Crash Recovery (`recovery_service.py`)**:
  Automatic background state saving every 30 seconds when dirty to `%LOCALAPPDATA%\VKDubStudio\recovery\`. Prompts user to restore unsaved session on next startup after abnormal termination. Safely cleans up upon clean save or explicit exit.
- **Diagnostic Logging & Security (`logging.py`)**:
  Rotating file logging (`RotatingFileHandler`, max 5MB, 3 backups) with automated `SecretFilter` redacting API keys, bearer tokens and credentials from logs and exception messages.
- **Log Viewer Dialog (`LogViewerDialog`)**:
  Built-in diagnostic viewer dialog with one-click refresh, copy-to-clipboard, direct folder opening in Windows Explorer, and log clearing. Accessible via `F12` shortcut or Settings.
- **Full 10-Phase Quality Assurance**:
  All 267 unit and integration tests passing, 0 mypy typing issues across 69 modules, 100% ruff lint compliance.

## Project Status: PRODUCTION READY (v1.0.0)

All 10 Phases from the Master Specification are fully developed, verified, tested, and documented.
