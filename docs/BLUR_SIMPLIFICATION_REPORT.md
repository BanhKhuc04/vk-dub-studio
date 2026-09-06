# Direct blur editing — user-requested follow-up

This change follows the user's explicit request to simplify blur editing after the
M1–M3 checkpoint. It extends the existing project incrementally; it does not mark
the entire M6 milestone or CapCut export as complete.

## Behavior

- **+ Làm mờ** immediately adds and selects a region on the video. No settings dialog.
- Drag the region to move it; drag any corner to resize within the video bounds.
- The **×** above the top-right corner deletes the selected region. Delete/Backspace
  also delete it; Escape or clicking empty space hides the selection controls.
- Coordinates remain normalized when resizing the window and saving/reopening projects.
- Preview uses three box-blur passes and a smooth feather into the original image.
  No black tint or dark fallback rectangle is used for blur. Flat colors and brightness
  are preserved. Overlapping regions are composited in order without restoring detail.
- Existing render filters now use true box blur and the same feather profile, retaining
  saved timing and solid-mask compatibility. New regions are always blur, full duration.
- The former advanced dialog remains a compatibility module; the main blur action no
  longer opens it. No new voice, batch, or CapCut functionality is enabled.

## Verification on the final application code

All commands use `.venv\Scripts\python.exe` from `D:\ToolVideo`.

| Check | Actual result | Evidence |
|---|---|---|
| `-m pytest -q` | **337 passed in 34.90 s**, no skips | `evidence/blur/all-tests.txt` |
| `-m mypy` | 77 source files, no issues | `evidence/blur/mypy.txt` |
| `-m ruff check .` | All checks passed | `evidence/blur/ruff-check.txt` |
| `-m ruff format --check .` | 120 files formatted | `evidence/blur/ruff-format.txt` |
| `scripts/smoke_blur.py --video docs/evidence/media/sample.mp4 --output-dir docs/evidence/blur/verified` | Native **Windows** app, 39 decoded frames, 25 during blur playback, 46 timer ticks; add/drag/resize/save/reopen/delete passed | `evidence/blur/verified/native-result.json` |
| Actual FFmpeg encode via existing `build_render_command` | Two regions, timed corner region, ASS subtitles and mixed audio; H264/AAC, 960×540, 7.88 s output | `evidence/blur/render-result.json`, `render-log.txt`, `blur-render.mp4` |

Image tests measure unchanged flat RGB colors, detail reduction, mean brightness,
exact source pixels at feather boundaries, smooth near-edge transition, and exact
pixel restoration after deletion. Interaction tests cover all four resize corners,
letterboxed dragging, inactive regions, overlap, and project persistence. A real
FFmpeg raw-frame test verifies timing, full-frame edges, and multiple regions.

Native screenshots inspected: `evidence/blur/verified/blur-selected.png`,
`evidence/blur/verified/after-delete.png`. The actual encoded frame is
`evidence/blur/render-frame.png`. The clip is a locally generated test pattern with
speech, not the user's original video.

Earlier native attempts are retained rather than presented as successful evidence:
one run's source changed during testing and failed its saved-mask assertion; another
timed out waiting for a decoded frame after reopening. The smoke now explicitly
starts playback when the native decoder needs it to deliver that first frame. The
final run completed every assertion. No application assertions were removed.

Limits: preview/render are verified here; editable blur in CapCut is unverified.
The legacy FFmpeg render took 46.66 s for this short clip with two regions, so this
is correctness evidence, not a realtime export performance claim. This scoped fix
does not add the remaining advanced M6 controls such as timing/duplicate UI.

Stop here for user approval.
