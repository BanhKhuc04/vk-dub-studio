# Dispatch for Explorer 2 (Backend APIs & 5-Step Pipeline)

## Context
Project Root: D:\Work\Project_AI\ToolVideo
Original Request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md
Your Directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_2

## Mission
Investigate the backend architecture, APIs, and the 5-step automation pipeline.
1. Inspect existing backend code (FastAPI, Python scripts, existing services, pipeline modules).
2. Trace the 5-step automation workflow:
   - Step 1: Video upload/drag-and-drop, metadata extraction (resolution, duration, fps).
   - Step 2: Voice & AI voice selection (Vbee / Edge TTS), audio preview endpoints.
   - Step 3: Blur regions handling in FFmpeg/CapCut pipeline.
   - Step 4: Full automation execution (Whisper transcription, AI contextual translation, Vbee/Edge TTS synthesis, audio-video merge), realtime progress updates (SSE / WebSocket).
   - Step 5: Review & export (script editing, MP4 export, CapCut draft export).
3. Identify existing functions/classes vs what needs refactoring or building.
4. Write detailed analysis to `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_2\analysis.md` and `handoff.md`.

## 2026-09-15T03:19:58Z
Focus: Backend Architecture, APIs, and 5-Step Automation Pipeline.
1. Survey existing backend code in D:\Work\Project_AI\ToolVideo (FastAPI apps, routes, services, modules).
2. Detail the exact flow and requirements for the 5-step automation pipeline:
   - Step 1 (Source Video): Video upload/drag & drop, instant metadata extraction (resolution, duration, fps via ffprobe/backend).
   - Step 2 (Voice & AI): Voice selection options (Vbee / Edge TTS), audio preview endpoints with instant playback.
   - Step 3 (Blur Regions): Ingesting drawn blur coordinates, conversion to FFmpeg filter graphs / CapCut draft format.
   - Step 4 (Automation): 1-click execution chaining Whisper transcription, contextual AI translation, Vbee/Edge TTS audio synthesis, and audio-video merging with live progress updates (WebSocket / SSE).
   - Step 5 (Review & Export): Compact subtitle/script review, quick edit, and 1-click export of final MP4 or valid CapCut project folder.
3. Identify existing functions/endpoints vs missing or broken pieces.
4. Detail API contract requirements (endpoints, request/response models).
5. Write your comprehensive report to D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_2\analysis.md and a structured handoff to D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_2\handoff.md.
6. Send a message to parent (Recipient: "b5f99409-245e-49eb-86c4-0a2263ff8cec") notifying completion with the path to your handoff.md.
