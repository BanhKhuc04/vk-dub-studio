# CapCut compatibility probe

Probe date: 2026-09-05. Host: Windows. CapCut: 9.3.0.3970.

The probe only read existing drafts under `%LOCALAPPDATA%/CapCut/User Data/Projects/com.lveditor.draft`.
It did not modify those drafts. Ten drafts were inspected structurally; user text and media were not
copied into the application template.

Verified local findings:

- canonical files are `draft_content.json` and `draft_meta_info.json`;
- the local content schema reports version `360000`;
- timeline values are microseconds (`1 ms = 1000` timeline units);
- local examples contain editable video, audio, and text tracks with material IDs referenced by segments;
- `root_meta_info.json` is the project-list index. VKDub creates one backup named
  `root_meta_info.vkdub-backup.json` before its first index update;
- exported projects use a unique draft ID and a new directory. No existing draft directory is changed.

The generated test `VKDub QA - Video Voice Caption` was registered in the local index and opened in
CapCut 9.3. Its timeline visibly showed one editable caption, one source-video clip, and one WAV voice
clip. The preview loaded the expected 7.9-second source video.

VKDub text-removal and legacy blur rectangles are baked into a new H.264 source clip under the draft's
`Assets` folder. This ensures the removal is visible in CapCut without inventing an unverified editable
effect schema. The rectangles cannot yet be adjusted again inside CapCut. Per-line WAV paths point to
their final locations under that same `Assets` folder, so moving the staging directory into place does
not leave broken voice references. Each WAV is pitch-preservingly fitted to its sentence slot before it
is registered, preventing adjacent voice segments from overlapping on the CapCut timeline. M9 is
verified for applied masks, video, voice audio, captions, timing, and volumes; only editable CapCut mask
construction remains partial.

The full Downloads sample `SaveTik.io_7663461279209671999.mp4` produced 260 voice segments and 260 text
segments with zero missing voice files and zero audio timeline overlaps. Its baked source remained
768x576 at 25 fps for 474.88 seconds. A frame comparison measured a mean change of 48.02 inside the text
removal rectangle and 0.95 outside it, confirming that the mask was baked into the CapCut media rather
than silently omitted.

Imported voice materials use CapCut's locally observed `extract_music` shape (`category_name=local`) and
clear the template's remote `music_id`, `resource_id`, and `request_id`. The video clip retains its source
audio but opens at volume zero, while `VOICE TIẾNG VIỆT — ĐÃ DỊCH` is the audible track. Subtitle materials
copy the VKDub style and map the 1080p-relative bottom margin to CapCut's normalized Y transform. On the
260-line sample, all assets matched translated-text cache keys, zero matched source-text keys, and a
Whisper audit of the first eight exported assets detected Vietnamese with probability 0.9838.

Implementation fields come from the sanitized local v360000 template at
`resources/capcut_v360000_template.json`. The exporter refuses another template schema.
