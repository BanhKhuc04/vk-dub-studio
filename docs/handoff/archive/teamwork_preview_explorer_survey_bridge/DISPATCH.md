# Survey Task: Native Bridge & Local Agent Architecture

Read `D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md` (specifically ## 2026-09-15T04:12:10Z).

## Objective
Map the existing Native Messaging / WebSocket bridge between Browser Extension and Local Agent (`local_agent.py`, `protocol.js`, `manifest.json`, backend services).
Document how ChatGPT Bridge and Vbee TTS currently function so R7 (100% preservation) is strictly guaranteed.
Map where and how new actions (`YOUTUBE_CONTEXT_SYNC`, `YOUTUBE_SEEK_TO`, `YOUTUBE_PREVIEW_CLIP`, `CLIP_EXPORT_REQUEST`, `CLIP_EXPORT_ACCEPTED`, `CLIP_EXPORT_PROGRESS`, `CLIP_EXPORT_RESULT`, `CLIP_EXPORT_ERROR`, `CLIP_EXPORT_CANCEL`, `OPEN_OUTPUT_FOLDER`) should be integrated.
Examine Windows Registry registration for Native Messaging Hosts (Chrome and Edge).

Write your comprehensive findings to `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_bridge\report.md` and deliver `handoff.md`.

## 2026-09-15T04:13:54Z
You are Explorer 1 (Native Bridge, Local Agent, Backend & Protocol Explorer).
Working directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_bridge
Project root: D:\Work\Project_AI\ToolVideo
Authoritative request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md (specifically ## 2026-09-15T04:12:10Z).
Your dispatch assignment: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_bridge\DISPATCH.md

Tasks:
1. Thoroughly investigate the existing Native Messaging / WebSocket bridge between Browser Extension and Local Agent (`local_agent.py`, `protocol.js`, `manifest.json`, backend services, etc.).
2. Map existing message flow and structures for ChatGPT Bridge and Vbee TTS to guarantee 100% preservation (R7).
3. Map the protocol actions needed: YOUTUBE_CONTEXT_SYNC, YOUTUBE_SEEK_TO, YOUTUBE_PREVIEW_CLIP, CLIP_EXPORT_REQUEST, CLIP_EXPORT_ACCEPTED, CLIP_EXPORT_PROGRESS, CLIP_EXPORT_RESULT, CLIP_EXPORT_ERROR, CLIP_EXPORT_CANCEL, OPEN_OUTPUT_FOLDER.
4. Check Windows Registry native host registration for Chrome and Edge (`Software\Microsoft\Edge\NativeMessagingHosts` and `Software\Google\Chrome\NativeMessagingHosts`).
5. Write your comprehensive report to `D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_explorer_survey_bridge\report.md` and deliver `handoff.md`.
6. When done, send a message to parent summarizing key findings and report paths.
