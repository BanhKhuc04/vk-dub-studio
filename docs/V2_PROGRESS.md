# VK Dub Studio 2.0 progress

Updated 2026-09-05.

- M1–M4: complete and regression tested.
- M5: VieNeu 3.5 local voice and CapCut TTS are working. Native probes generated 48 kHz WAV audio;
  switching engines persists immediately. CapCut uses upstream revision
  `e06da1f4e0c0010354f4e7702f02c18cbdd419a2` and accepts the server's actual `succeed` status.
- M8: local CapCut 9.3/v360000 compatibility probe complete for video, audio, captions, timing, project
  index, and volumes. Findings are in `docs/CAPCUT_COMPATIBILITY.md`.
- M9: editable video, per-line WAV voice, and caption export works and opens in local CapCut. CapCut
  export now packages a video with every text-removal region applied and stores voice paths against the
  final draft folder. Voice clips are fitted to their available timeline slots without changing pitch,
  so adjacent sentences no longer overlap. The rectangles are baked into that source clip rather than
  editable CapCut masks.
- UI polish: the main status is a numbered six-step list, the timestamped activity log is always visible,
  and the script toolbar exposes import translated SRT plus export translated/original SRT actions. The
  preview toolbar also has a one-click `Khung Sub` toggle for the subtitle background box.

Exact-video verification used `SaveTik.io_7663461279209671999.mp4` from Downloads. The complete direct
export retained 768x576, 25 fps, and 474.88 seconds, with H.264 video and stereo AAC audio. The generated
CapCut draft contains 1 baked video, 260 non-overlapping voice clips, 260 captions, and no missing voice
files. Evidence is under `docs/evidence/downloads-real`.

Subtitle position now uses one 1920x1080 reference canvas in preview and ASS render, including non-16:9
source video. Opening `Vị trí & kiểu Sub` shows a dashed caption frame that can be dragged vertically.
CapCut captions receive the selected font size, colors, outline, background box, width, and matching
bottom position. CapCut voice materials are local imported WAV files with online-music IDs cleared; the
source-video audio opens muted and the Vietnamese voice track is explicitly named. The 260-line sample
matched all 260 voice cache keys to translated Vietnamese text and none to the Chinese source text.
