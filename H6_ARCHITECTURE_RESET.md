# VK Dub Studio — H6 Architecture Reset & Browser Automation Specification

**Date:** 2026-09-07  
**Branch:** `feat/h6-browser-bridge`  
**Status:** Architecture Reset Approved — Initiating H6.0 Implementation  

---

## 1. Audit of Current Repository & Root Causes of Failure

### 1.1 Root Causes of Failure in Real User Testing
Recent live testing with authentic company accounts revealed fundamental architectural flaws in the previous approach:
1. **ChatGPT Workflow Was Not Automated:**  
   `src/vkdub/services/chatgpt_bridge.py` merely exported an SRT file, placed a prompt onto the Windows clipboard using `clip`, and launched `https://chatgpt.com` via `os.startfile()`. There was no programmatic DOM automation, no automated file upload, no response waiting, and no automatic extraction of translated cues back into the studio pipeline.
2. **Vbee Opened an Isolated Browser Profile / Required Re-login:**  
   `src/vkdub/integrations/vbee/session.py` relied on Playwright's `chromium.launch_persistent_context()` pointing to `%LOCALAPPDATA%/VKDubStudio/browser_profiles/vbee`. It attempted to clone user cookies and storage files via `sync_user_browser_session()`. On modern Chromium browsers (Microsoft Edge and Google Chrome), DPAPI-encrypted SQLite cookie databases and session tokens cannot be cleanly copied between profiles without session invalidation or file lock conflicts. As a consequence, the automated browser opened with a blank or corrupted session, forcing the user to log in again on an unfamiliar browser window.
3. **Multi-Browser Profile Conflict:**  
   Launching an isolated browser while the user's everyday Microsoft Edge browser was already running created desktop clutter, process locking (`ProcessSingleton` errors), and violated corporate SSO/MFA workflows.
4. **Step 4 UI Fake Completion:**  
   The UI reported completion prematurely or generically without exposing granular sub-step states (transcription, translation, voice synthesis, download, validation), error details, retry actions, or artifact inspection.

---

## 2. Inventory of Current Playwright & Browser Code

The table below lists all current browser-related and automation code in the repository:

| File Path | Component | Current Implementation | Status / Action |
|:---|:---|:---|:---|
| `src/vkdub/integrations/vbee/session.py` | Profile & Browser Launch | Launches Playwright persistent context; copies `%LOCALAPPDATA%` Edge data. | **REPLACE / REMOVE from production path.** |
| `src/vkdub/integrations/vbee/automation.py` | Vbee DOM Automation | Playwright locators for login, SRT upload, voice selection, conversion, download. | **MIGRATE logic & selectors** to Extension adapter (`content/vbeeAdapter.js`). Playwright retained strictly for offline/mock test harnesses. |
| `src/vkdub/integrations/vbee/selectors.py` | DOM Selectors & Timeouts | Centralized dictionary of Vbee DOM selectors, classes, and URLs. | **MIGRATE** to `apps/browser-extension/content/vbeeAdapter.js`. |
| `src/vkdub/integrations/vbee/provider.py` | Vbee Provider Class | Direct Playwright runner using `async_playwright()`. | **MIGRATE** to communicate via Local Agent & Browser Extension Bridge. |
| `src/vkdub/services/chatgpt_bridge.py` | ChatGPT Integration | Clipboard copy + `os.startfile(CHATGPT_URL)`. | **REMOVE.** Replace with automated Extension adapter (`content/chatgptAdapter.js`). |
| `src/vkdub/services/health_service.py` | Environment Health Checks | Checks `import playwright` and browser binary paths. | **UPDATE** to check Local Agent IPC and Extension Bridge status. |
| `src/vkdub/ui/vbee_controller.py` | UI Vbee Controller | Executes QThread workflow with Playwright worker. | **UPDATE** to delegate to Local Agent orchestrator. |
| `packaging/vkdub.spec` | PyInstaller Specification | Bundles Playwright driver and node.exe. | **RETAIN** for test packaging; production runtime will no longer depend on bundled browser drivers. |
| `tests/test_vbee_*.py` | Playwright Unit/Mock Tests | Tests mocks for session and automation. | **RETAIN** for CI regression coverage. |

---

## 3. Component Action Matrix: Remove, Retain, or Migrate

### 3.1 What to Remove from Production Workflow
- `sync_user_browser_session()`: Raw cookie and profile directory copying.
- `create_vbee_browser_context()`: Spawning secondary browser instances via `launch_persistent_context`.
- Manual clipboard-based pseudo-automation in `chatgpt_bridge.py`.
- Fake completion signals in Step 4 that do not reflect real backend progress.

### 3.2 What to Retain
- **Media & Subtitle Pipeline:**
  - Video probe and metadata extraction (`MediaTools`, `ffprobe`).
  - Audio extraction, silence padding, timeline alignment, and master narration audio generation (`capcut_export.py`, `ffmpeg`).
  - CapCut draft project generation (`capcut_export.py`).
  - Subtitle parsing, timecode conversion, SRT formatting, and validation (`srt_service.py`).
  - Local faster-whisper transcription engine.
- **Domain Models & Persistence:**
  - `Project`, `ScriptDocument`, `ScriptLine`, `VoiceSettings`, `ProjectService`.
- **UI Shell & Interactive Editors:**
  - PySide6 application frame, `VideoPreview`, `ScriptReviewPanel`, `SubtitleStyleDialog`, `MaskDialog` (blur regions).
- **Automated Mock Tests:**
  - Offline unit tests for serialization, timeline math, and updater verification.

### 3.3 What to Migrate
- **Vbee DOM Selectors & Interaction Flows:** Migrate into the extension content script `apps/browser-extension/content/vbeeAdapter.js`.
- **ChatGPT Translation Cue Handling:** Migrate prompt templates, SRT upload/injection, cue validation, and translated SRT extraction into `apps/browser-extension/content/chatgptAdapter.js`.
- **Voice Provider Interface:** Migrate `VoiceProvider` to delegate synthesis jobs through the Local Agent Native Messaging Bridge.

---

## 4. Target Architecture

```
+--------------------------------------------------------------------+
|                       VK Dub Studio Desktop                        |
|   - PySide6 GUI                                                    |
|   - Pipeline Orchestrator & Checkpoint State Machine               |
|   - Master Audio Timeline Generator (FFmpeg silence padding)       |
+---------------------------------+----------------------------------+
                                  | Local IPC (TCP 127.0.0.1:49814)
                                  v
+--------------------------------------------------------------------+
|                         VK Dub Local Agent                         |
|   - Native Host Process & Socket Server                            |
|   - Protocol Serializer / Deserializer                             |
|   - State synchronization & artifact cache                         |
+---------------------------------+----------------------------------+
                                  | Native Messaging (stdio 32-bit framed JSON)
                                  v
+--------------------------------------------------------------------+
|              VK Dub Microsoft Edge / Chrome Extension              |
|                     (apps/browser-extension/)                     |
|                                                                    |
|  +--------------------------------------------------------------+  |
|  |                 Background Service Worker                    |  |
|  |   - Native messaging port manager & reconnect logic          |  |
|  |   - Tab discovery & session detection                        |  |
|  +------------------------------+-------------------------------+  |
|                                 | Message Dispatch                 |
|            +--------------------+--------------------+             |
|            |                                         |             |
|            v                                         v             |
|  +--------------------+                    +--------------------+  |
|  |  ChatGPT Adapter   |                    |    Vbee Adapter    |  |
|  | (Content Script)   |                    |  (Content Script)  |  |
|  | - Tab management   |                    | - Dubbing tab mgmt |  |
|  | - SRT cue inject   |                    | - Voice: Ngoc Huyen|  |
|  | - Translation parse|                    | - Speed: 1.1x      |  |
|  | - Cue verification |                    | - Progress & dl    |  |
|  +--------------------+                    +--------------------+  |
+--------------------------------------------------------------------+
                                  |
              Executes inside user's existing Edge profile
          (Naturally logged in, zero re-login, zero profile cloning)
```

### Core Architecture Principles:
1. **User Profile Preservation:** The extension runs directly inside the user's primary Microsoft Edge profile. It inherits existing session cookies, authentication tokens, enterprise SSO, and local storage naturally.
2. **Zero Secondary Browser:** No new browser process with `--user-data-dir` is spawned for production tasks.
3. **Bidirectional Native Messaging:** Communication between the desktop application and Edge is governed by standard Chromium Native Messaging:
   - Manifest registered in `HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.vkdub.bridge`.
   - Host executable / script connects to Local Agent IPC socket on `127.0.0.1:49814`.
   - 32-bit little-endian length-prefixed JSON protocol on stdio.
4. **Resilient Reconnection:** If Edge is closed and reopened, or if VK Dub Studio is restarted, the bridge reconnects cleanly and reports current status immediately.

---

## 5. H6.0 — Browser Bridge Foundation Specification

### 5.1 Extension Structure (`apps/browser-extension/`)
```
apps/browser-extension/
├── manifest.json              # Manifest V3 with deterministic key
├── background/
│   └── serviceWorker.js       # Native messaging connector, lifecycle & status monitor
├── content/
│   ├── chatgptAdapter.js      # ChatGPT DOM & session detection
│   └── vbeeAdapter.js         # Vbee DOM & session detection
├── bridge/
│   ├── nativeMessaging.js     # Native host port communication & framing
│   └── protocol.js            # Standardized message definitions & types
└── icons/
    └── icon48.png             # Extension icon
```

### 5.2 Deterministic Extension Identity
To ensure that `allowed_origins` in the Native Messaging Host manifest is permanent across any installation or clone without manual editing, `manifest.json` includes a fixed RSA public `"key"`. This gives the extension a deterministic 32-character extension ID.

### 5.3 Reported State Attributes
The extension must actively inspect the browser state and report:
- `BROWSER_CONNECTED`: Native messaging bridge active between Edge and Local Agent.
- `CHATGPT_AVAILABLE`: `https://chatgpt.com` is accessible / tab exists.
- `CHATGPT_LOGGED_IN`: ChatGPT has an active authenticated session (no login gate, prompt input available).
- `VBEE_AVAILABLE`: `https://studio.vbee.vn` is accessible / tab exists.
- `VBEE_LOGGED_IN`: Vbee has an active authenticated session (avatar/user-info present, not login page).

### 5.4 Native Messaging Host Configuration
- **Host Name:** `com.vkdub.bridge`
- **Registry Location:**
  - Edge: `HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.vkdub.bridge`
  - Chrome: `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vkdub.bridge`
- **Host Script:** `tools/native_host/vkdub_host.bat` calling `tools/native_host/vkdub_host.py`
- **Socket Forwarding:** `127.0.0.1:49814`

### 5.5 Desktop Status Display
The Desktop UI (via `HealthBanner` and Left Panel / Status Bar) displays real-time status:
- `[Edge Connected]` (Green) or `[Waiting for Edge...]` (Amber)
- `[ChatGPT: Logged In]` (Green) or `[ChatGPT: Not Logged In]` (Red)
- `[Vbee: Logged In]` (Green) or `[Vbee: Not Logged In]` (Red)
- "Mở Microsoft Edge" action button to open Edge if disconnected.

---

## 6. Implementation Stages (H6.0 through H6.4)

| Milestone | Scope | Deliverables |
|:---|:---|:---|
| **H6.0 (Current)** | **Browser Bridge Foundation** | `apps/browser-extension/`, Native Host, Registry setup, Local Agent IPC, real-time Desktop status display. Acceptance verification with live Edge profile. |
| **H6.1** | **ChatGPT Adapter** | Automated new chat, SRT cue upload/injection, translation waiting, cue count & timecode validator, auto-repair/retry. |
| **H6.2** | **Vbee Adapter** | Automated dubbing tab navigation, SRT upload, voice selection (Ngọc Huyền), speed selection (1.1x), progress tracking, master audio download. |
| **H6.3** | **Orchestrator & Checkpoints** | Persistent state machine (`PROJECT_CREATED` -> `EXPORTED`), atomic checkpoint saves, resume-on-restart, artifact registry. |
| **H6.4** | **UI Reset (5 Steps)** | 01 Source, 02 Voice, 03 Blur, 04 Automatic Processing (with 4.1-4.4 real states, retry, view artifact, logs), 05 Review & Export. Master audio timeline with silence padding. |

---

## 7. Acceptance Criteria for H6.0

1. **User opens their normal Microsoft Edge profile:**
   - Normal Edge profile is used; no second browser window or profile is created.
2. **Existing Login Reuse:**
   - User is already logged into ChatGPT and Vbee in normal Edge.
   - Zero login prompts or credential requests appear.
3. **Real Status Reporting:**
   - Extension reports `BROWSER_CONNECTED: true`.
   - Extension accurately reports `CHATGPT_AVAILABLE`, `CHATGPT_LOGGED_IN`, `VBEE_AVAILABLE`, `VBEE_LOGGED_IN`.
   - Desktop UI reflects these real statuses immediately.
4. **Reconnection Resilience:**
   - Restarting VK Dub Studio while Edge is open reconnects automatically.
   - Closing Edge marks browser as disconnected; reopening Edge restores connection.
