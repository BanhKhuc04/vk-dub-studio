# Voice and translation — 2026-09-05

Scope: the user explicitly requested continuing voice implementation and diagnosing
translation failure. Existing video, blur, STT, project, script and cache code was
retained. The work was split into diagnosis, Gemini repair, local engine setup,
adapter/controller, voice management, and verification.

## Translation: verified repair

The saved Gemini key was present. With the previously saved `gemini-2.5-flash-lite`,
`models.get` succeeded but an actual small `generateContent` translation returned
HTTP 404. This reproduced why the old connection test looked valid while translation
failed. No secret or private transcript was printed or placed in evidence.

`gemini-3.5-flash` completed real structured translation with the existing key, and
the saved model was updated to that verified model. New settings use the same default.
No other key was created or substituted. The explicit settings button now says
**Kiểm tra dịch thử** and translates a short fixed sentence; it validates the result's
segment ID. Startup retains its inexpensive model-access check and does not silently
generate billable text on each launch.

Gemini 3 requests now use `thinkingLevel: minimal`; Gemini 2.5 retains its compatible
configuration. A 404 points to model selection and an actual generation test. Translation
failures stay visible in an actionable banner. Invalid, missing, reordered or duplicate
segments still cannot overwrite the existing script. Translation stops at review.

The old pricing file incorrectly applied Flash-Lite prices to 3.5 Flash. The verified
3.5 Flash standard estimate is now $1.50 input / $9 output per million tokens, with
model-specific accounting; unknown model prices remain unknown rather than borrowing
another model's rate. These are paid-equivalent estimates, not a claim about the user's
free-tier entitlement. Sources: [Gemini configuration](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5),
[official pricing](https://ai.google.dev/gemini-api/docs/pricing).

## VieNeu Local: implemented and exercised

- Installed the official `vieneu==3.5.0` package in `D:\ToolVideo\.runtime\vieneu`,
  separate from the app/STT virtual environment. Selected CPU ONNX, v3 Turbo, fp32.
  Runtime/model locations persist in app settings; new installations have a managed
  default directory. Installation is available from Settings → Voice.
- Catalog contains 20 real SDK presets, with stable app IDs mapped to the exact
  upstream IDs. No invented voices or bundled third-party reference recordings.
- Setup downloads the official model assets and synthesizes a real probe before
  writing readiness. Health validates the installed version and 16 model artifacts.
- `VieNeuLocalProvider` communicates with an isolated worker process. Qt does not
  import or run the SDK. Normal synthesis uses the downloaded models offline.
- **Nghe thử** creates real WAV audio before script approval. **Duyệt & tạo voice**
  synthesizes only after explicit review. Failed/missing lines can be retried.
- Reuses the existing content-validated segment/chunk cache. VieNeu retains 48 kHz PCM
  through assembly. Speed uses FFmpeg `atempo`, and voice playback volume is applied.
- Cancelling stops the owned Windows process tree, including its venv launcher child.
  Completed cache remains; partial preview/audio is not published.
- Settings → Voice supports adding an authorized reference, registering with the SDK,
  saving the resulting speaker profile, previewing, renaming, deleting and restart
  persistence. The source recording is not modified or uploaded. v3 Turbo does not
  require reference text. Deleted catalog entries retain internal reference files so
  old saved projects are not destructively altered.
- Voice controls now scroll instead of being compressed; main preview and voice
  management fit beside one another. Missing engines and generation failures remain
  actionable rather than reporting success.

Upstream research: [VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS),
[the installed release](https://pypi.org/project/vieneu/3.5.0/).
Exact installed dependencies: `evidence/voice-v2/runtime-packages.txt`.

## Evidence

Commands use `.venv\Scripts\python.exe` in `D:\ToolVideo`.

| Verification | Result | Evidence |
|---|---|---|
| `-m pytest -q` | 346 tests passed, no skipped tests | `evidence/voice-v2/all-tests.txt` |
| `-m mypy` | No issues in 83 source files | `evidence/voice-v2/mypy.txt` |
| `-m ruff check .` / `-m ruff format --check .` | Passed; 128 Python files formatted | `evidence/voice-v2/ruff-*.txt` |
| `scripts/smoke_voice_v2.py --video docs/evidence/media/sample.mp4 --output-dir docs/evidence/voice-v2/final` | Native Windows app, real Gemini and VieNeu, all assertions passed | `evidence/voice-v2/final/result.json` |
| Native restart and saved project/audio | 20 voices restored; installed health and saved audio ready; voice controls readable | `evidence/voice-v2/final/restart-result.json` |
| Real custom voice enrollment + synthesis | Registered from a locally generated synthetic QA sample, renamed, generated 2.469 s WAV | `evidence/voice-v2/custom/result.json` |
| Separate process custom voice reload | Saved profile/name restored, generated at 1.2x, then removed QA catalog entry | `evidence/voice-v2/custom/restart-result.json` |
| Real worker cancellation | 0.33 s; process exited; no partial output audio | `evidence/voice-v2/custom/cancel-result.json` |

The final native pipeline translated two labelled fixture segments using live Gemini:
“Chào mọi người.” and “Cảm ơn các bạn đã xem video này.” It retained the original
0–3 s / 3–7.5 s times and stopped before approval. Approving generated two real voice
files. A second generation made zero synthesis calls. Editing the first line revoked
approval; reapproving regenerated exactly one line and preserved the second asset.
One additional call generated the preview: four synthesis calls in total, 70.27 s
elapsed and 1,099 Qt timer ticks. This demonstrates responsiveness, not a throughput
guarantee for long videos or other hardware.

The small test transcript is explicitly a fixture, not new STT output from the user's
video. No claim is made that the user's entire seven-minute video has been translated,
reviewed or dubbed. The existing STT regression tests remain passing.

Native screenshots inspected: `final/voice-ready.png`, `final/voice-settings.png`,
`final/restart-voice-settings.png`, `final/restart-volume-settings.png` under
`evidence/voice-v2`. Earlier QA found compressed settings controls; those were corrected
and the final restart check passed. Final preview: `evidence/voice-v2/preview.wav`,
48 kHz, 5.754 s, non-silent, zero clipped samples (`audio-quality.json`).

## Boundaries and next approval

Verified here: Gemini translation repair and the VieNeu Local voice workflow. Custom
voice enrollment was exercised with a synthetic QA recording, not a claim about the
similarity of any user's voice. Listen to the attached sample to judge voice quality.

Superseded 2026-09-05: CapCut TTS is now integrated from the reviewed upstream revision and verified
with real audio. The v360000 compatibility probe and single-project export are also implemented;
see `CAPCUT_COMPATIBILITY.md`. Batch export and editable rectangle blur remain incomplete.

The user should save any open project and reopen the app to load these code changes.
Stop after this report for user review.
