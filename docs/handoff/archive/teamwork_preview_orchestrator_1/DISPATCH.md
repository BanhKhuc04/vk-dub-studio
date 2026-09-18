## 2026-09-15T03:19:02Z

You are the Project Orchestrator for the ToolVideo Web UI refactoring project.

Working Directory: D:\Work\Project_AI\ToolVideo\.agents\teamwork_preview_orchestrator_1
Project Root: D:\Work\Project_AI\ToolVideo
Original Request: D:\Work\Project_AI\ToolVideo\.agents\ORIGINAL_REQUEST.md

Please review ORIGINAL_REQUEST.md thoroughly.
Key Objectives:
1. R1: Refactor Web UI to Apple minimalist, elegant and modern style (KAPPAK Studio Web v2).
   - Eliminate manual coordinate input boxes (X, Y, W, H).
   - Implement interactive canvas over the video player allowing users to directly draw, drag, and resize blur regions.
   - Apple aesthetics: frosted glass, ultra-thin borders, spring animations with Framer Motion, Dynamic Island notifications, and official KAPPAK logo from `D:\Work\Project_AI\ToolVideo\logo\logo.png`.
2. R2: Streamline 5-step "1-click" automation pipeline:
   - Step 1 (Source Video): Drag & drop video, instant preview with video specs (resolution, duration, fps).
   - Step 2 (Voice & AI): Compact AI voice selection (Vbee / Edge TTS), instant preview audio with 1 click.
   - Step 3 (Blur Regions): Interactive video canvas blur drawing, calculate coordinates for backend FFmpeg/CapCut pipeline.
   - Step 4 (Automation): 1-click execution of entire pipeline (Whisper transcription, AI contextual translation, Vbee/Edge TTS synthesis, audio-video merging) with live progress bar.
   - Step 5 (Review & Export): Compact script review/edit, 1-click MP4 export or valid CapCut project export with celebration confetti.
3. R3: Backend & Independent Execution:
   - FastAPI backend serving the web interface, linked with background tools (FFmpeg, FFprobe, Local Agent bridge).
   - `run_app.bat` script to start server and automatically launch browser without manual setup.
4. Acceptance criteria:
   - Interactive canvas drawing/resizing blur region without any manual X/Y/W/H numeric input.
   - KAPPAK logo crisp in Header & tab Favicon.
   - Dark/Light mode, Apple Dynamic Island, spring animations.
   - Instant video preview on drop.
   - Full automated step 4 pipeline with realtime progress.
   - Valid MP4 or CapCut Draft export.
   - `run_app.bat` working directly.

Maintain progress.md and BRIEFING.md in your working directory. Regularly update progress.md. When the project is complete, report completion back with full summary and verification.
