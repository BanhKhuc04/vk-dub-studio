/**
 * VK Dub Studio — YouTube In-Player Toolbar & Clip Marker Content Script
 *
 * Implements non-intrusive YouTube in-player clip marking, hotkey capture,
 * timeline range highlight, and bidirectional synchronization with Side Panel.
 *
 * Architecture & Features:
 * 1. Mounts non-intrusive toolbar inside #movie_player using Shadow DOM encapsulation.
 * 2. Intercepts hotkeys in capturing phase (I, O, Enter, Escape) overriding YouTube Miniplayer on 'I'.
 * 3. Focus & typing protection for inputs, textareas, contenteditables, and search/comment boxes.
 * 4. Video context binding, 60fps rAF timecode tracking (HH:MM:SS.mmm), and duration calculations.
 * 5. Scrubber range overlay injected into YouTube's .ytp-progress-bar.
 * 6. SPA navigation resilience via yt-navigate-finish & yt-page-data-updated (singleton controller).
 * 7. Runtime message handlers for YOUTUBE_SEEK_TO, YOUTUBE_PREVIEW_CLIP, and YOUTUBE_CONTEXT_SYNC.
 * 8. Apple Frosted Glass HUD design with Dynamic Island toast feedback.
 */

(function () {
  "use strict";

  // Shared Action Constants matching apps/browser-extension/bridge/protocol.js
  const Actions = {
    YOUTUBE_CONTEXT_SYNC: "YOUTUBE_CONTEXT_SYNC",
    YOUTUBE_SEEK_TO: "YOUTUBE_SEEK_TO",
    YOUTUBE_PREVIEW_CLIP: "YOUTUBE_PREVIEW_CLIP",
    YOUTUBE_CLIP_ADDED: "YOUTUBE_CLIP_ADDED",
    OPEN_SIDE_PANEL: "OPEN_SIDE_PANEL",
    GET_YOUTUBE_STATUS: "GET_YOUTUBE_STATUS",
  };

  const TOOLBAR_HOST_ID = "vkdub-yt-clip-toolbar";
  const TOOLBAR_HOST_MARKER = "data-vkdub-youtube-toolbar";

  /**
   * Rounds a timestamp in seconds to exactly 3 decimal places (milliseconds).
   * Prevents IEEE 754 floating point drift (e.g. 0.1 + 0.2 = 0.30000000000000004).
   * @param {number|string} val
   * @returns {number}
   */
  function roundMs(val) {
    const num = Number(val);
    if (!Number.isFinite(num)) return 0;
    return Math.round(num * 1000) / 1000;
  }

  /**
   * Formats seconds into standardized timecode: HH:MM:SS.mmm or MM:SS.mmm.
   * @param {number|null} seconds
   * @param {boolean} forceHours
   * @returns {string}
   */
  function formatTimecode(seconds, forceHours = false) {
    if (seconds === null || seconds === undefined || !Number.isFinite(Number(seconds)) || Number(seconds) < 0) {
      return forceHours ? "--:--:--.---" : "--:--.---";
    }
    const totalMs = Math.round(Number(seconds) * 1000);
    const ms = totalMs % 1000;
    const totalSecs = Math.floor(totalMs / 1000);
    const s = totalSecs % 60;
    const totalMins = Math.floor(totalSecs / 60);
    const m = totalMins % 60;
    const h = Math.floor(totalMins / 60);

    const pad2 = (n) => String(n).padStart(2, "0");
    const pad3 = (n) => String(n).padStart(3, "0");

    if (h > 0 || forceHours) {
      return `${pad2(h)}:${pad2(m)}:${pad2(s)}.${pad3(ms)}`;
    }
    return `${pad2(m)}:${pad2(s)}.${pad3(ms)}`;
  }

  /**
   * Parses flexible user timecode strings into seconds (number).
   * Supports: "85.4", "01:25", "01:25.400", "01:05:22.100".
   * @param {string|number} input
   * @returns {number|null}
   */
  function parseTimecode(input) {
    if (typeof input === "number") {
      return Number.isFinite(input) && input >= 0 ? roundMs(input) : null;
    }
    if (typeof input !== "string") return null;
    const str = input.trim();
    if (!str) return null;

    // Direct numeric seconds
    if (/^\d+(\.\d+)?$/.test(str)) {
      const val = parseFloat(str);
      return Number.isFinite(val) && val >= 0 ? roundMs(val) : null;
    }

    const parts = str.split(":");
    if (parts.length === 2) {
      // MM:SS or MM:SS.mmm
      const mins = parseInt(parts[0], 10);
      const secs = parseFloat(parts[1]);
      if (Number.isFinite(mins) && Number.isFinite(secs) && mins >= 0 && secs >= 0 && secs < 60) {
        return roundMs(mins * 60 + secs);
      }
    } else if (parts.length === 3) {
      // HH:MM:SS or HH:MM:SS.mmm
      const hrs = parseInt(parts[0], 10);
      const mins = parseInt(parts[1], 10);
      const secs = parseFloat(parts[2]);
      if (Number.isFinite(hrs) && Number.isFinite(mins) && Number.isFinite(secs) && hrs >= 0 && mins >= 0 && mins < 60 && secs >= 0 && secs < 60) {
        return roundMs(hrs * 3600 + mins * 60 + secs);
      }
    }
    return null;
  }

  /**
   * Validates clip boundary constraints.
   * @param {number} start
   * @param {number} end
   * @param {number} duration
   * @returns {{ valid: boolean, error?: string }}
   */
  function validateClipBounds(start, end, duration = 0) {
    if (start === null || start === undefined || !Number.isFinite(Number(start))) {
      return { valid: false, error: "Chưa đặt thời gian bắt đầu." };
    }
    if (end === null || end === undefined || !Number.isFinite(Number(end))) {
      return { valid: false, error: "Chưa đặt thời gian kết thúc." };
    }
    const s = roundMs(start);
    const e = roundMs(end);
    if (s < 0) {
      return { valid: false, error: "Thời gian bắt đầu không thể âm." };
    }
    if (s >= e) {
      return { valid: false, error: "Thời gian bắt đầu phải nhỏ hơn thời gian kết thúc." };
    }
    if (e - s < 0.5) {
      return { valid: false, error: "Thời lượng đoạn cắt tối thiểu là 0.5 giây." };
    }
    if (duration > 0 && e > duration + 0.5) {
      return { valid: false, error: "Thời gian kết thúc vượt quá thời lượng video." };
    }
    return { valid: true };
  }

  /**
   * Checks whether two clips represent duplicate segments within 0.1s threshold.
   * @param {{ start: number, end: number }} clipA
   * @param {{ start: number, end: number }} clipB
   * @returns {boolean}
   */
  function isDuplicateClip(clipA, clipB) {
    if (!clipA || !clipB) return false;
    return Math.abs(clipA.start - clipB.start) < 0.1 && Math.abs(clipA.end - clipB.end) < 0.1;
  }

  /**
   * Guard to detect whether keyboard event originated inside user editable inputs.
   * Protects comments, search bar, descriptions, and custom Polymer textboxes.
   * @param {KeyboardEvent} e
   * @returns {boolean}
   */
  function isUserTyping(e) {
    const path = typeof e.composedPath === "function" ? e.composedPath() : [e.target];
    for (const el of path) {
      if (!el || el.nodeType !== Node.ELEMENT_NODE) continue;
      const tag = (el.tagName || "").toUpperCase();
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
      if (el.isContentEditable) return true;
      const role = el.getAttribute ? el.getAttribute("role") : null;
      if (role === "textbox" || role === "searchbox" || role === "combobox") return true;
      if (el.id === "contenteditable-root") return true;
    }

    const active = document.activeElement;
    if (active && active.nodeType === Node.ELEMENT_NODE) {
      const activeTag = (active.tagName || "").toUpperCase();
      if (activeTag === "INPUT" || activeTag === "TEXTAREA" || activeTag === "SELECT") return true;
      if (active.isContentEditable) return true;
      const activeRole = active.getAttribute ? active.getAttribute("role") : null;
      if (activeRole === "textbox" || activeRole === "searchbox" || activeRole === "combobox") return true;
    }
    return false;
  }

  /**
   * CSS styles injected exclusively into the Toolbar Shadow Root.
   */
  const TOOLBAR_SHADOW_CSS = `
    :host {
      all: initial;
      position: absolute;
      top: 14px;
      left: 16px;
      z-index: 60;
      pointer-events: none;
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Segoe UI", Roboto, sans-serif;
      -webkit-font-smoothing: antialiased;
      user-select: none;
      transition: opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1), transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }

    :host(.vkdub-hidden) {
      display: none !important;
    }

    :host(.vkdub-faded) {
      opacity: 0.7 !important;
      pointer-events: auto !important;
    }

    :host(:hover),
    :host(.vkdub-active) {
      opacity: 1 !important;
      pointer-events: auto !important;
    }

    .vkdub-hud-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 8px;
      background: rgba(22, 22, 26, 0.88);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 12px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.15);
      pointer-events: auto;
      transition: all 0.2s ease;
    }

    .vkdub-brand {
      display: flex;
      align-items: center;
      gap: 5px;
      padding: 2px 4px;
      cursor: pointer;
    }

    .vkdub-logo-icon {
      color: #0A84FF;
      flex-shrink: 0;
    }

    .vkdub-brand-title {
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.5px;
      color: #0A84FF;
      text-transform: uppercase;
    }

    .vkdub-detected-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #30D158;
      box-shadow: 0 0 7px rgba(48, 209, 88, 0.9);
      flex-shrink: 0;
    }

    .vkdub-divider {
      width: 1px;
      height: 14px;
      background: rgba(255, 255, 255, 0.14);
      margin: 0 2px;
      flex-shrink: 0;
    }

    .vkdub-timecode-box {
      display: flex;
      align-items: center;
      padding: 2px 6px;
      background: rgba(0, 0, 0, 0.4);
      border-radius: 6px;
      border: 1px solid rgba(255, 255, 255, 0.08);
    }

    .vkdub-timecode-val {
      font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
      font-size: 11.5px;
      font-weight: 600;
      color: #FFFFFF;
      font-variant-numeric: tabular-nums;
      letter-spacing: 0.2px;
    }

    .vkdub-btn {
      appearance: none;
      -webkit-appearance: none;
      border: none;
      background: rgba(255, 255, 255, 0.08);
      color: rgba(255, 255, 255, 0.92);
      padding: 4px 7px;
      border-radius: 7px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      font-size: 11px;
      font-weight: 500;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      cursor: pointer;
      outline: none;
      transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1);
      white-space: nowrap;
    }

    .vkdub-btn:hover {
      background: rgba(255, 255, 255, 0.15);
      border-color: rgba(255, 255, 255, 0.25);
      color: #FFFFFF;
    }

    .vkdub-btn:active {
      transform: scale(0.96);
    }

    .vkdub-btn:disabled {
      opacity: 0.4;
      cursor: not-allowed;
      transform: none !important;
    }

    .vkdub-btn-marker-in.active {
      background: rgba(48, 209, 88, 0.18);
      border-color: rgba(48, 209, 88, 0.5);
      color: #30D158;
    }

    .vkdub-btn-marker-out.active {
      background: rgba(10, 132, 255, 0.18);
      border-color: rgba(10, 132, 255, 0.5);
      color: #0A84FF;
    }

    .vkdub-btn-primary {
      background: #0A84FF;
      border-color: #0A84FF;
      color: #FFFFFF;
      font-weight: 600;
    }

    .vkdub-btn-primary:hover:not(:disabled) {
      background: #0071E3;
      border-color: #0071E3;
    }

    .vkdub-btn-ghost {
      background: transparent;
      border-color: transparent;
      color: rgba(255, 255, 255, 0.7);
    }

    .vkdub-btn-ghost:hover {
      background: rgba(255, 255, 255, 0.08);
      color: #FFFFFF;
    }

    .vkdub-keycap {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0 4px;
      height: 14px;
      font-size: 9px;
      font-weight: 700;
      border-radius: 3px;
      background: rgba(0, 0, 0, 0.45);
      border: 1px solid rgba(255, 255, 255, 0.2);
      color: rgba(255, 255, 255, 0.85);
      text-transform: uppercase;
      line-height: 1;
    }

    .vkdub-keycap-subtle {
      background: rgba(255, 255, 255, 0.15);
      border-color: rgba(255, 255, 255, 0.25);
    }

    .vkdub-duration-badge {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      padding: 2px 5px;
      background: rgba(255, 214, 10, 0.15);
      border: 1px solid rgba(255, 214, 10, 0.4);
      border-radius: 5px;
      color: #FFD60A;
      font-size: 10.5px;
      font-weight: 600;
      font-family: ui-monospace, "SF Mono", monospace;
    }

    .vkdub-clear-marker {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 13px;
      height: 13px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.2);
      font-size: 10px;
      line-height: 1;
      margin-left: 2px;
      cursor: pointer;
      color: inherit;
    }

    .vkdub-clear-marker:hover {
      background: rgba(255, 69, 58, 0.7);
      color: #FFFFFF;
    }

    /* Collapsed mode */
    .vkdub-hud-pill.collapsed .vkdub-collapsible {
      display: none !important;
    }

    /* Toast Notification inside player */
    .vkdub-toast-container {
      position: absolute;
      top: 48px;
      left: 0;
      right: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      pointer-events: none;
      z-index: 100;
    }

    .vkdub-toast {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      background: rgba(18, 18, 20, 0.94);
      backdrop-filter: blur(25px);
      -webkit-backdrop-filter: blur(25px);
      border: 1px solid rgba(255, 255, 255, 0.16);
      border-radius: 20px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
      color: #FFFFFF;
      font-size: 11px;
      font-weight: 500;
      pointer-events: auto;
      animation: vkdubToastIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards;
      transition: opacity 0.2s ease, transform 0.2s ease;
    }

    .vkdub-toast-icon {
      font-weight: 700;
    }

    .vkdub-toast.success .vkdub-toast-icon { color: #30D158; }
    .vkdub-toast.warning .vkdub-toast-icon { color: #FFD60A; }
    .vkdub-toast.error .vkdub-toast-icon { color: #FF453A; }
    .vkdub-toast.info .vkdub-toast-icon { color: #0A84FF; }

    @keyframes vkdubToastIn {
      from { opacity: 0; transform: translateY(-8px) scale(0.95); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
  `;

  /**
   * CSS styles injected into document.head for the Scrubber Progress Overlay.
   */
  const SCRUBBER_PAGE_CSS = `
    .vkdub-progress-range-overlay {
      position: absolute !important;
      top: 0 !important;
      bottom: 0 !important;
      height: 100% !important;
      background: linear-gradient(90deg, rgba(10, 132, 255, 0.75), rgba(48, 209, 88, 0.85)) !important;
      border-left: 2px solid #30D158 !important;
      border-right: 2px solid #0A84FF !important;
      box-shadow: 0 0 8px rgba(10, 132, 255, 0.6) !important;
      pointer-events: none !important;
      z-index: 34 !important;
      border-radius: 2px !important;
      transition: opacity 0.15s ease !important;
    }

    .vkdub-progress-marker-in {
      position: absolute !important;
      top: -3px !important;
      width: 2px !important;
      height: calc(100% + 6px) !important;
      background: #30D158 !important;
      box-shadow: 0 0 6px #30D158 !important;
      z-index: 36 !important;
      pointer-events: none !important;
      border-radius: 1px !important;
    }

    .vkdub-progress-marker-out {
      position: absolute !important;
      top: -3px !important;
      width: 2px !important;
      height: calc(100% + 6px) !important;
      background: #0A84FF !important;
      box-shadow: 0 0 6px #0A84FF !important;
      z-index: 36 !important;
      pointer-events: none !important;
      border-radius: 1px !important;
    }
  `;

  /**
   * Controller managing YouTube In-Player Toolbar and Clip Marker state.
   */
  class YouTubeAdapter {
    constructor() {
      this.version = "2.3.0";
      this.initialized = false;
      this.hostElement = null;
      this.shadowRoot = null;
      this.videoElement = null;

      // Active state
      this.currentVideoId = null;
      this.currentVideoTitle = "";
      this.duration = 0;
      this.currentTime = 0;
      this.clipStart = null;
      this.clipEnd = null;
      this.clipCounter = 1;
      this.isCollapsed = false;

      // Animation & Throttling
      this.rafId = null;
      this.lastSyncTime = 0;
      this.previewActive = false;
      this.previewCheckTimer = null;

      // Bound event listeners
      this._onKeydown = this.handleKeydown.bind(this);
      this._onTimeUpdate = this.handleTimeUpdate.bind(this);
      this._onVideoLoaded = this.handleVideoLoaded.bind(this);
      this._onNavigate = this.handleNavigation.bind(this);
      this._onMouseMove = this.handleMouseMove.bind(this);

      // DOM Observers
      this.navObserver = null;
      this.playerClassObserver = null;
    }

    /**
     * Initializes the adapter singleton and binds events.
     */
    init() {
      if (this.initialized) {
        this.handleNavigation();
        return;
      }

      this.injectProgressStyles();
      this.setupDOMMount();
      this.bindGlobalEvents();
      this.initialized = true;

      // Initial navigation probe
      this.handleNavigation();
    }

    /**
     * Injects scrubber overlay styles into page head.
     */
    injectProgressStyles() {
      const STYLE_ID = "vkdub-yt-progress-style";
      if (!document.getElementById(STYLE_ID)) {
        const style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = SCRUBBER_PAGE_CSS;
        (document.head || document.documentElement).appendChild(style);
      }
    }

    /**
     * Creates and mounts the Toolbar container into #movie_player with Shadow DOM.
     */
    setupDOMMount() {
      const player = document.querySelector("#movie_player");
      const candidates = Array.from(
        document.querySelectorAll(`#${TOOLBAR_HOST_ID}, [${TOOLBAR_HOST_MARKER}]`)
      );
      let existingHost = null;

      if (this.hostElement && candidates.includes(this.hostElement)) {
        existingHost = this.hostElement;
      } else {
        existingHost = candidates.find((node) => node.shadowRoot) || candidates[0] || null;
      }

      // Reloading an unpacked extension or replacing YouTube's SPA player can leave
      // more than one old toolbar node behind. Keep one canonical host only.
      candidates.forEach((node) => {
        if (node !== existingHost) node.remove();
      });

      const isAdoptingExistingHost = !!existingHost && this.hostElement !== existingHost;
      const host = existingHost || document.createElement("div");
      host.id = TOOLBAR_HOST_ID;
      host.setAttribute(TOOLBAR_HOST_MARKER, this.version);
      this.hostElement = host;

      if (!host.shadowRoot) {
        this.shadowRoot = host.attachShadow({ mode: "open" });
        this.buildToolbarShadowDOM();
      } else {
        this.shadowRoot = host.shadowRoot;

        // A toolbar adopted from a previous extension context may still look alive
        // while all of its click handlers are dead. Rebuild it once for this adapter.
        if (isAdoptingExistingHost || !this.shadowRoot.querySelector(".vkdub-toolbar-root")) {
          this.shadowRoot.replaceChildren();
          this.buildToolbarShadowDOM();
        }
      }

      if (player && this.hostElement.parentElement !== player) {
        player.appendChild(this.hostElement);
      }

      this.observePlayerAutohide();
    }

    /**
     * Constructs HTML and binds isolated click handlers in the Shadow Root.
     */
    buildToolbarShadowDOM() {
      const styleEl = document.createElement("style");
      styleEl.textContent = TOOLBAR_SHADOW_CSS;
      this.shadowRoot.appendChild(styleEl);

      const rootWrapper = document.createElement("div");
      rootWrapper.className = "vkdub-toolbar-root";
      rootWrapper.innerHTML = `
        <div class="vkdub-hud-pill" id="hud-pill">
          <!-- Brand Badge -->
          <div class="vkdub-brand" id="btn-brand" title="Đã nhận diện video YouTube — VK Dub Studio Clip Mode">
            <svg class="vkdub-logo-icon" viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
              <path d="M19 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm-7 13.5l-5-3.5V8l5 3.5v5.5zm6-3.5l-5 3.5V11.5l5-3.5v6z"/>
            </svg>
            <span class="vkdub-brand-title">VK Clip</span>
            <span class="vkdub-detected-dot" title="Đã nhận diện video"></span>
          </div>

          <div class="vkdub-divider"></div>

          <!-- Playhead Timecode -->
          <div class="vkdub-timecode-box" title="Thời gian hiện tại">
            <span class="vkdub-timecode-val" id="timecode-display">00:00.000</span>
          </div>

          <!-- In-Point Marker [I] -->
          <button class="vkdub-btn vkdub-collapsible vkdub-btn-marker-in" id="btn-mark-in" title="Đặt điểm đầu [Phím I]">
            <span class="vkdub-keycap">I</span>
            <span class="vkdub-btn-label" id="lbl-mark-in">Đầu: --:--.---</span>
            <span class="vkdub-clear-marker" id="clear-in" title="Xóa điểm đầu" style="display:none;">&times;</span>
          </button>

          <!-- Out-Point Marker [O] -->
          <button class="vkdub-btn vkdub-collapsible vkdub-btn-marker-out" id="btn-mark-out" title="Đặt điểm cuối [Phím O]">
            <span class="vkdub-keycap">O</span>
            <span class="vkdub-btn-label" id="lbl-mark-out">Cuối: --:--.---</span>
            <span class="vkdub-clear-marker" id="clear-out" title="Xóa điểm cuối" style="display:none;">&times;</span>
          </button>

          <!-- Duration Badge -->
          <div class="vkdub-duration-badge vkdub-collapsible" id="duration-badge" style="display:none;">
            <span>Δ</span>
            <span id="lbl-duration">0.0s</span>
          </div>

          <!-- Add Clip [Enter] -->
          <button class="vkdub-btn vkdub-btn-primary vkdub-collapsible" id="btn-add-clip" title="Thêm đoạn cắt vào danh sách [Phím Enter]" disabled>
            <svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor">
              <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
            </svg>
            <span>Thêm</span>
            <span class="vkdub-keycap vkdub-keycap-subtle">↵</span>
          </button>

          <!-- Cancel Marker Selection [Esc] -->
          <button class="vkdub-btn vkdub-btn-ghost vkdub-collapsible" id="btn-cancel" title="Hủy chọn đoạn [Phím Esc]" style="display:none;">
            <span>Hủy</span>
            <span class="vkdub-keycap vkdub-keycap-subtle">Esc</span>
          </button>

          <!-- Side Panel Trigger -->
          <button class="vkdub-btn vkdub-btn-ghost vkdub-collapsible" id="btn-sidepanel" title="Mở Trình Quản Lý Clip (Side Panel)">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor">
              <path d="M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zm12 2v12h4V6h-4zM4 6v12h10V6H4z"/>
            </svg>
          </button>

          <!-- Collapse Toggle -->
          <button class="vkdub-btn vkdub-btn-ghost" id="btn-collapse" title="Thu gọn / Mở rộng Toolbar">
            <span id="collapse-icon">◀</span>
          </button>
        </div>

        <div class="vkdub-toast-container" id="toast-container"></div>
      `;

      this.shadowRoot.appendChild(rootWrapper);
      this.bindToolbarElementEvents();
    }

    /**
     * Attaches isolated events inside Shadow Root, stopping propagation to native player.
     */
    bindToolbarElementEvents() {
      const root = this.shadowRoot;
      if (!root) return;

      // Universal click/mousedown protection inside shadow root
      const stopBubbling = (e) => {
        e.stopPropagation();
      };
      root.addEventListener("click", stopBubbling);
      root.addEventListener("mousedown", stopBubbling);
      root.addEventListener("mouseup", stopBubbling);
      root.addEventListener("dblclick", stopBubbling);

      // Buttons
      const btnIn = root.getElementById("btn-mark-in");
      const btnOut = root.getElementById("btn-mark-out");
      const clearIn = root.getElementById("clear-in");
      const clearOut = root.getElementById("clear-out");
      const btnAdd = root.getElementById("btn-add-clip");
      const btnCancel = root.getElementById("btn-cancel");
      const btnCollapse = root.getElementById("btn-collapse");
      const btnSidepanel = root.getElementById("btn-sidepanel");

      if (btnIn) {
        btnIn.addEventListener("click", (e) => {
          e.stopPropagation();
          this.setInPoint();
        });
      }

      if (btnOut) {
        btnOut.addEventListener("click", (e) => {
          e.stopPropagation();
          this.setOutPoint();
        });
      }

      if (clearIn) {
        clearIn.addEventListener("click", (e) => {
          e.stopPropagation();
          this.clipStart = null;
          this.updateMarkersUI();
          this.updateProgressBarOverlay();
          this.showToast("Đã xóa điểm đầu", "info");
        });
      }

      if (clearOut) {
        clearOut.addEventListener("click", (e) => {
          e.stopPropagation();
          this.clipEnd = null;
          this.updateMarkersUI();
          this.updateProgressBarOverlay();
          this.showToast("Đã xóa điểm cuối", "info");
        });
      }

      if (btnAdd) {
        btnAdd.addEventListener("click", (e) => {
          e.stopPropagation();
          this.addClip();
        });
      }

      if (btnCancel) {
        btnCancel.addEventListener("click", (e) => {
          e.stopPropagation();
          this.clearSelection();
        });
      }

      if (btnCollapse) {
        btnCollapse.addEventListener("click", (e) => {
          e.stopPropagation();
          this.toggleCollapse();
        });
      }

      if (btnSidepanel) {
        btnSidepanel.addEventListener("click", (e) => {
          e.stopPropagation();
          this.requestOpenSidePanel();
        });
      }
    }

    /**
     * Binds window keyboard interceptor in CAPTURING phase to override YouTube Miniplayer.
     */
    bindGlobalEvents() {
      // Capturing phase listener
      window.addEventListener("keydown", this._onKeydown, true);

      // SPA Navigation Events
      window.addEventListener("yt-navigate-finish", this._onNavigate);
      window.addEventListener("yt-page-data-updated", this._onNavigate);
      window.addEventListener("popstate", this._onNavigate);

      // Backup observer for document title / URL mutation
      if (typeof MutationObserver !== "undefined") {
        this.navObserver = new MutationObserver(() => {
          const id = this.extractVideoId();
          if (id && id !== this.currentVideoId) {
            this.handleNavigation();
          }
        });
        this.navObserver.observe(document, { subtree: true, childList: true });
      }

      // Host hover tracking for autohide
      window.addEventListener("mousemove", this._onMouseMove, { passive: true });
    }

    /**
     * Observes YouTube player autohide class toggles (.ytp-autohide).
     */
    observePlayerAutohide() {
      const player = document.querySelector("#movie_player");
      if (!player) return;

      if (this.playerClassObserver) {
        this.playerClassObserver.disconnect();
      }

      if (typeof MutationObserver !== "undefined") {
        this.playerClassObserver = new MutationObserver(() => {
          const isAutohide = player.classList.contains("ytp-autohide");
          if (this.hostElement) {
            if (isAutohide && !this.previewActive) {
              this.hostElement.classList.add("vkdub-faded");
            } else {
              this.hostElement.classList.remove("vkdub-faded");
            }
          }
        });

        this.playerClassObserver.observe(player, { attributes: true, attributeFilter: ["class"] });
      }
    }

    /**
     * Mouse move handler restores toolbar visibility when player is active.
     */
    handleMouseMove() {
      if (this.hostElement && this.hostElement.classList.contains("vkdub-faded")) {
        this.hostElement.classList.remove("vkdub-faded");
      }
    }

    /**
     * Handles Capturing Phase Hotkeys.
     * Overrides 'I' for YouTube Miniplayer.
     * @param {KeyboardEvent} e
     */
    handleKeydown(e) {
      // 1. Guard: Check if focused on typing input
      if (isUserTyping(e)) return;

      // 2. Guard: Check modifiers (Ctrl, Alt, Meta)
      if (e.ctrlKey || e.altKey || e.metaKey) return;

      // 3. Guard: Check if watch page and player active
      if (!this.isWatchPage()) return;

      const key = e.key;

      if (key === "i" || key === "I") {
        // OVERRIDE YOUTUBE NATIVE MINIPLAYER SHORTCUT
        e.preventDefault();
        e.stopImmediatePropagation();
        this.setInPoint();
        return;
      }

      if (key === "o" || key === "O") {
        e.preventDefault();
        e.stopImmediatePropagation();
        this.setOutPoint();
        return;
      }

      if (key === "Enter") {
        if (this.hasActiveSelection()) {
          e.preventDefault();
          e.stopImmediatePropagation();
          this.addClip();
        } else {
          this.showToast("Vui lòng đặt điểm đầu [I] hoặc điểm cuối [O]", "warning");
        }
        return;
      }

      if (key === "Escape") {
        if (this.hasActiveSelection()) {
          e.preventDefault();
          e.stopImmediatePropagation();
          this.clearSelection();
        }
        // If no markers active, let Escape pass through for native fullscreen exit!
      }
    }

    /**
     * Returns true if user has marked at least one boundary point.
     * @returns {boolean}
     */
    hasActiveSelection() {
      return this.clipStart !== null || this.clipEnd !== null;
    }

    /**
     * Checks if current URL is a valid YouTube watch page.
     * @returns {boolean}
     */
    isWatchPage() {
      return window.location.pathname === "/watch" && !!this.extractVideoId();
    }

    /**
     * Extracts YouTube Video ID from URL, Polymer component, or player data.
     * @returns {string}
     */
    extractVideoId() {
      try {
        const params = new URLSearchParams(window.location.search);
        const v = params.get("v");
        if (v) return v;

        const player = document.querySelector("#movie_player");
        if (player && typeof player.getVideoData === "function") {
          const data = player.getVideoData();
          if (data && data.video_id) return data.video_id;
        }

        const flexy = document.querySelector("ytd-watch-flexy");
        if (flexy && flexy.getAttribute("video-id")) {
          return flexy.getAttribute("video-id");
        }
      } catch (e) {}
      return "";
    }

    /**
     * Extracts current YouTube video title.
     * @returns {string}
     */
    extractVideoTitle() {
      try {
        const titleEl = document.querySelector("h1.ytd-watch-metadata yt-formatted-string") ||
                        document.querySelector("h1.ytd-watch-metadata") ||
                        document.querySelector("#title h1") ||
                        document.querySelector("meta[name='title']");
        if (titleEl) {
          const t = titleEl.textContent || titleEl.getAttribute("content");
          if (t && t.trim()) return t.trim();
        }
      } catch (e) {}
      const raw = document.title || "";
      return raw.replace(/\s*-\s*YouTube\s*$/i, "").trim();
    }

    /**
     * Detects if video is an advertisement.
     * @returns {boolean}
     */
    isAdShowing() {
      const player = document.querySelector("#movie_player");
      if (player && (player.classList.contains("ad-showing") || player.classList.contains("ad-interrupting"))) {
        return true;
      }
      return !!document.querySelector(".ytp-ad-player-overlay, .ytp-ad-text");
    }

    /**
     * Detects if video is a live stream.
     * @returns {boolean}
     */
    isLiveStream() {
      const player = document.querySelector("#movie_player");

      // YouTube exposes a reliable current-live flag through its player API.
      // `isLiveContent` is intentionally ignored because it remains true for
      // archived livestreams, which are normal seekable videos and can be cut.
      try {
        const videoData = player && typeof player.getVideoData === "function"
          ? player.getVideoData()
          : null;
        if (videoData && videoData.isLive === true) return true;
      } catch (e) {}

      // A finite positive duration is definitive VOD/replay evidence. This
      // check must happen before inspecting YouTube's persistent live badge:
      // the badge can exist in the DOM while hidden on ordinary videos.
      if (this.videoElement) {
        const duration = this.videoElement.duration;
        if (Number.isFinite(duration) && duration > 0) return false;
        if (duration === Infinity) return true;
      }

      if (player && player.classList.contains("ytp-live")) return true;

      // Metadata may not be ready yet. Only accept a live badge that is
      // actually visible inside the active player, never mere DOM presence.
      const liveBadge = player && player.querySelector(".ytp-live-badge");
      if (!liveBadge || liveBadge.hasAttribute("disabled")) return false;
      const style = window.getComputedStyle(liveBadge);
      return liveBadge.getClientRects().length > 0 &&
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        style.opacity !== "0";
    }

    /**
     * SPA Navigation handler. Seamlessly transitions across video switches without duplicate nodes.
     */
    handleNavigation() {
      const videoId = this.extractVideoId();

      if (!this.isWatchPage()) {
        if (this.hostElement) {
          this.hostElement.classList.add("vkdub-hidden");
        }
        this.clearScrubberOverlay();
        return;
      }

      // Ensure toolbar node exists in #movie_player
      this.setupDOMMount();
      if (this.hostElement) {
        this.hostElement.classList.remove("vkdub-hidden");
      }

      // If video changed or first load
      if (videoId && videoId !== this.currentVideoId) {
        this.currentVideoId = videoId;
        this.currentVideoTitle = this.extractVideoTitle();
        this.clipStart = null;
        this.clipEnd = null;

        this.bindVideoElement();
        this.updateMarkersUI();
        this.clearScrubberOverlay();

        // Delay context sync slightly for metadata to settle
        setTimeout(() => {
          this.syncContext();
          this.showToast("Đã nhận diện video YouTube", "success");
        }, 500);
      } else {
        this.bindVideoElement();
      }
    }

    /**
     * Finds and binds the active HTMLVideoElement.
     */
    bindVideoElement() {
      const player = document.querySelector("#movie_player");
      let video = null;

      if (player) {
        video = player.querySelector("video.html5-main-video") || player.querySelector("video");
      }
      if (!video) {
        video = document.querySelector("video");
      }

      if (video && video !== this.videoElement) {
        if (this.videoElement) {
          this.videoElement.removeEventListener("timeupdate", this._onTimeUpdate);
          this.videoElement.removeEventListener("loadedmetadata", this._onVideoLoaded);
          this.videoElement.removeEventListener("durationchange", this._onVideoLoaded);
        }

        this.videoElement = video;
        this.duration = Number.isFinite(video.duration) ? roundMs(video.duration) : 0;
        this.currentTime = roundMs(video.currentTime);

        video.addEventListener("timeupdate", this._onTimeUpdate);
        video.addEventListener("loadedmetadata", this._onVideoLoaded);
        video.addEventListener("durationchange", this._onVideoLoaded);

        this.updateTimecodeDisplays(this.currentTime);
      }
    }

    /**
     * Video metadata/duration change handler.
     */
    handleVideoLoaded() {
      if (!this.videoElement) return;
      this.duration = Number.isFinite(this.videoElement.duration) ? roundMs(this.videoElement.duration) : 0;
      this.syncContext();
    }

    /**
     * 60fps rAF-throttled timeupdate handler.
     */
    handleTimeUpdate() {
      if (!this.videoElement) return;
      this.currentTime = roundMs(this.videoElement.currentTime);

      if (this.rafId) return;
      this.rafId = requestAnimationFrame(() => {
        this.updateTimecodeDisplays(this.currentTime);
        this.updateProgressBarOverlay();
        this.rafId = null;
      });
    }

    /**
     * Updates timecode text in the toolbar HUD.
     * @param {number} time
     */
    updateTimecodeDisplays(time) {
      if (!this.shadowRoot) return;
      const displayEl = this.shadowRoot.getElementById("timecode-display");
      if (!displayEl) return;

      if (this.isAdShowing()) {
        displayEl.textContent = "[Ad]";
        return;
      }
      if (this.isLiveStream()) {
        displayEl.textContent = "[LIVE]";
        return;
      }

      const forceHours = this.duration >= 3600;
      displayEl.textContent = formatTimecode(time, forceHours);
    }

    /**
     * Sets In-Point (Điểm đầu) at current playhead timestamp.
     * @param {number|null} time
     */
    setInPoint(time = null) {
      if (this.isAdShowing()) {
        this.showToast("Đang phát quảng cáo, không thể đánh dấu", "warning");
        return;
      }
      if (this.isLiveStream()) {
        this.showToast("Video trực tiếp: Cắt clip được hỗ trợ sau khi kết thúc phát", "warning");
        return;
      }

      const now = time !== null ? roundMs(time) : (this.videoElement ? roundMs(this.videoElement.currentTime) : 0);
      this.clipStart = now;

      // If existing Out-point precedes new In-point, reset Out-point
      if (this.clipEnd !== null && this.clipStart >= this.clipEnd) {
        this.clipEnd = null;
      }

      this.updateMarkersUI();
      this.updateProgressBarOverlay();

      const forceHours = this.duration >= 3600;
      this.showToast(`[I] Đặt điểm đầu: ${formatTimecode(this.clipStart, forceHours)}`, "info");
    }

    /**
     * Sets Out-Point (Điểm cuối) at current playhead timestamp.
     * @param {number|null} time
     */
    setOutPoint(time = null) {
      if (this.isAdShowing()) {
        this.showToast("Đang phát quảng cáo, không thể đánh dấu", "warning");
        return;
      }
      if (this.isLiveStream()) {
        this.showToast("Video trực tiếp: Cắt clip được hỗ trợ sau khi kết thúc phát", "warning");
        return;
      }

      const now = time !== null ? roundMs(time) : (this.videoElement ? roundMs(this.videoElement.currentTime) : 0);

      // Warning if Out-point precedes In-point
      if (this.clipStart !== null && now <= this.clipStart) {
        this.showToast("Điểm cuối [O] phải lớn hơn điểm đầu [I]", "warning");
        return;
      }

      this.clipEnd = now;
      this.updateMarkersUI();
      this.updateProgressBarOverlay();

      const forceHours = this.duration >= 3600;
      this.showToast(`[O] Đặt điểm cuối: ${formatTimecode(this.clipEnd, forceHours)}`, "info");
    }

    /**
     * Updates toolbar button labels, badges, and colors according to marker state.
     */
    updateMarkersUI() {
      if (!this.shadowRoot) return;
      const root = this.shadowRoot;

      const btnIn = root.getElementById("btn-mark-in");
      const btnOut = root.getElementById("btn-mark-out");
      const lblIn = root.getElementById("lbl-mark-in");
      const lblOut = root.getElementById("lbl-mark-out");
      const clearIn = root.getElementById("clear-in");
      const clearOut = root.getElementById("clear-out");
      const durationBadge = root.getElementById("duration-badge");
      const lblDuration = root.getElementById("lbl-duration");
      const btnAdd = root.getElementById("btn-add-clip");
      const btnCancel = root.getElementById("btn-cancel");

      const forceHours = this.duration >= 3600;

      // In Point
      if (this.clipStart !== null) {
        if (btnIn && btnIn.classList) btnIn.classList.add("active");
        if (lblIn) lblIn.textContent = `Đầu: ${formatTimecode(this.clipStart, forceHours)}`;
        if (clearIn && clearIn.style) clearIn.style.display = "inline-flex";
      } else {
        if (btnIn && btnIn.classList) btnIn.classList.remove("active");
        if (lblIn) lblIn.textContent = "Đầu: --:--.---";
        if (clearIn && clearIn.style) clearIn.style.display = "none";
      }

      // Out Point
      if (this.clipEnd !== null) {
        if (btnOut && btnOut.classList) btnOut.classList.add("active");
        if (lblOut) lblOut.textContent = `Cuối: ${formatTimecode(this.clipEnd, forceHours)}`;
        if (clearOut && clearOut.style) clearOut.style.display = "inline-flex";
      } else {
        if (btnOut && btnOut.classList) btnOut.classList.remove("active");
        if (lblOut) lblOut.textContent = "Cuối: --:--.---";
        if (clearOut && clearOut.style) clearOut.style.display = "none";
      }

      // Duration & Add Button
      const hasSelection = this.hasActiveSelection();
      if (btnCancel && btnCancel.style) {
        btnCancel.style.display = hasSelection ? "inline-flex" : "none";
      }

      if (this.clipStart !== null && this.clipEnd !== null) {
        const delta = roundMs(this.clipEnd - this.clipStart);
        if (durationBadge && durationBadge.style) durationBadge.style.display = "inline-flex";
        if (lblDuration) lblDuration.textContent = `${delta.toFixed(1)}s`;
        if (btnAdd) btnAdd.disabled = delta < 0.5;
      } else if (this.clipStart !== null) {
        if (durationBadge && durationBadge.style) durationBadge.style.display = "none";
        if (btnAdd) btnAdd.disabled = false;
      } else {
        if (durationBadge && durationBadge.style) durationBadge.style.display = "none";
        if (btnAdd) btnAdd.disabled = true;
      }
    }

    /**
     * Updates or draws the visual scrubber range overlay inside YouTube's .ytp-progress-bar.
     */
    updateProgressBarOverlay() {
      const progressBar = document.querySelector(".ytp-progress-bar");
      if (!progressBar) return;

      let rangeEl = progressBar.querySelector(".vkdub-progress-range-overlay");
      let markerInEl = progressBar.querySelector(".vkdub-progress-marker-in");
      let markerOutEl = progressBar.querySelector(".vkdub-progress-marker-out");

      if (!rangeEl) {
        rangeEl = document.createElement("div");
        rangeEl.className = "vkdub-progress-range-overlay";
        progressBar.appendChild(rangeEl);
      }
      if (!markerInEl) {
        markerInEl = document.createElement("div");
        markerInEl.className = "vkdub-progress-marker-in";
        progressBar.appendChild(markerInEl);
      }
      if (!markerOutEl) {
        markerOutEl = document.createElement("div");
        markerOutEl.className = "vkdub-progress-marker-out";
        progressBar.appendChild(markerOutEl);
      }

      const dur = this.duration || (this.videoElement ? this.videoElement.duration : 0);
      if (!dur || dur <= 0) {
        this.clearScrubberOverlay();
        return;
      }

      if (this.clipStart === null && this.clipEnd === null) {
        this.clearScrubberOverlay();
        return;
      }

      const inPct = this.clipStart !== null ? (this.clipStart / dur) * 100 : 0;
      let outPct = this.clipEnd !== null ? (this.clipEnd / dur) * 100 : null;

      if (this.clipStart !== null) {
        markerInEl.style.left = `${Math.min(100, Math.max(0, inPct))}%`;
        markerInEl.style.display = "block";
      } else {
        markerInEl.style.display = "none";
      }

      if (this.clipEnd !== null) {
        markerOutEl.style.left = `${Math.min(100, Math.max(0, outPct))}%`;
        markerOutEl.style.display = "block";
      } else {
        markerOutEl.style.display = "none";
      }

      if (this.clipStart !== null && this.clipEnd !== null) {
        const left = Math.min(inPct, outPct);
        const width = Math.abs(outPct - inPct);
        rangeEl.style.left = `${Math.min(100, Math.max(0, left))}%`;
        rangeEl.style.width = `${Math.min(100 - left, Math.max(0, width))}%`;
        rangeEl.style.display = "block";
      } else if (this.clipStart !== null) {
        // Dynamic live scrubber extension while playing
        const currPct = (this.currentTime / dur) * 100;
        if (currPct > inPct) {
          rangeEl.style.left = `${inPct}%`;
          rangeEl.style.width = `${currPct - inPct}%`;
          rangeEl.style.display = "block";
        } else {
          rangeEl.style.display = "none";
        }
      } else {
        rangeEl.style.display = "none";
      }
    }

    /**
     * Clears scrubber overlay from page DOM.
     */
    clearScrubberOverlay() {
      const progressBar = document.querySelector(".ytp-progress-bar");
      if (!progressBar) return;
      const elements = progressBar.querySelectorAll(".vkdub-progress-range-overlay, .vkdub-progress-marker-in, .vkdub-progress-marker-out");
      elements.forEach((el) => {
        el.style.display = "none";
      });
    }

    /**
     * Cancels active selection and resets marker state.
     */
    clearSelection() {
      this.clipStart = null;
      this.clipEnd = null;
      this.updateMarkersUI();
      this.clearScrubberOverlay();
      this.showToast("Đã hủy chọn đoạn", "info");
    }

    /**
     * Commits the current marker selection as a new clip.
     * Validates bounds and dispatches YOUTUBE_CLIP_ADDED.
     */
    addClip() {
      let start = this.clipStart;
      let end = this.clipEnd;
      const dur = this.duration || (this.videoElement ? this.videoElement.duration : 0);

      // Boundary inferencing
      if (start === null && end === null) {
        this.showToast("Vui lòng đặt điểm đầu [I] hoặc điểm cuối [O]", "warning");
        return;
      }

      if (start === null && end !== null) {
        start = 0;
      } else if (start !== null && end === null) {
        const curr = this.videoElement ? roundMs(this.videoElement.currentTime) : start;
        if (curr > start && curr - start >= 0.5) {
          end = curr;
        } else if (dur > start && dur - start >= 0.5) {
          end = dur;
        } else {
          this.showToast("Điểm cuối phải lớn hơn điểm đầu tối thiểu 0.5s", "warning");
          return;
        }
      }

      start = roundMs(start);
      end = roundMs(end);

      // Validation
      const val = validateClipBounds(start, end, dur);
      if (!val.valid) {
        this.showToast(val.error, "warning");
        return;
      }

      const clipId = `clip_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
      const clipPayload = {
        id: clipId,
        videoId: this.currentVideoId,
        video_id: this.currentVideoId,
        name: `Clip ${this.clipCounter++}`,
        start,
        end,
        duration: roundMs(end - start),
        selected: true,
        createdAt: Date.now(),
      };

      // Dispatches runtime message
      try {
        if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
          chrome.runtime.sendMessage({
            action: Actions.YOUTUBE_CLIP_ADDED,
            payload: clipPayload,
          }).catch(() => {});
        }
      } catch (e) {}

      // Persists into chrome.storage.local
      try {
        if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
          const key = `clips_${this.currentVideoId}`;
          chrome.storage.local.get([key], (res) => {
            const list = Array.isArray(res[key]) ? res[key] : [];
            const isDup = list.some((c) => isDuplicateClip(c, clipPayload));
            if (!isDup) {
              list.push(clipPayload);
              chrome.storage.local.set({ [key]: list }).catch(() => {});
            }
          });
        }
      } catch (e) {}

      const forceHours = this.duration >= 3600;
      this.showToast(
        `Đã lưu ${clipPayload.name} (${formatTimecode(start, forceHours)} ➔ ${formatTimecode(end, forceHours)})`,
        "success"
      );

      // Reset markers for next clip
      this.clipStart = null;
      this.clipEnd = null;
      this.updateMarkersUI();
      this.clearScrubberOverlay();
    }

    /**
     * Seeks native HTMLVideoElement to target timestamp.
     * @param {number} time
     * @param {boolean} play
     * @returns {number}
     */
    seekTo(time, play = true) {
      if (!this.videoElement) {
        this.bindVideoElement();
      }
      if (!this.videoElement) return 0;

      const target = Math.max(0, roundMs(time));
      this.videoElement.currentTime = target;
      if (play && this.videoElement.paused) {
        this.videoElement.play().catch(() => {});
      }
      return this.videoElement.currentTime;
    }

    /**
     * Previews a clip segment: seeks to start, plays, and auto-pauses at end.
     * @param {number} start
     * @param {number} end
     * @param {boolean} loop
     */
    previewClip(start, end, loop = false) {
      this.stopPreview();

      if (!this.videoElement) {
        this.bindVideoElement();
      }
      if (!this.videoElement) return;

      const s = Math.max(0, roundMs(start));
      const e = Math.min(this.duration || Infinity, roundMs(end));

      if (s >= e) return;

      this.previewActive = true;
      this.videoElement.currentTime = s;
      this.videoElement.play().catch(() => {});

      const forceHours = this.duration >= 3600;
      this.showToast(`Xem thử: ${formatTimecode(s, forceHours)} ➔ ${formatTimecode(e, forceHours)}`, "info");

      const checkPreviewEnd = () => {
        if (!this.previewActive || !this.videoElement) return;

        if (this.videoElement.currentTime >= e) {
          if (loop) {
            this.videoElement.currentTime = s;
            this.videoElement.play().catch(() => {});
          } else {
            this.videoElement.pause();
            this.previewActive = false;
            this.showToast("Đã xem xong đoạn xem thử", "info");
            return;
          }
        }
        this.previewCheckTimer = requestAnimationFrame(checkPreviewEnd);
      };

      this.previewCheckTimer = requestAnimationFrame(checkPreviewEnd);
    }

    /**
     * Cancels active preview monitor.
     */
    stopPreview() {
      this.previewActive = false;
      if (this.previewCheckTimer) {
        cancelAnimationFrame(this.previewCheckTimer);
        this.previewCheckTimer = null;
      }
    }

    /**
     * Dispatches YOUTUBE_CONTEXT_SYNC message to background service worker and storage.
     */
    syncContext() {
      if (!this.isWatchPage()) return null;

      const videoId = this.currentVideoId || this.extractVideoId();
      const title = this.extractVideoTitle();
      const author = this.extractAuthor();
      const dur = this.duration || (this.videoElement ? roundMs(this.videoElement.duration) : 0);
      const curr = this.videoElement ? roundMs(this.videoElement.currentTime) : 0;
      const url = window.location.href;
      const canonicalUrl = videoId ? `https://www.youtube.com/watch?v=${videoId}` : url;
      const thumbnailUrl = videoId ? `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg` : "";

      const payload = {
        videoId,
        video_id: videoId,
        title,
        duration: dur,
        currentTime: curr,
        current_time: curr,
        url,
        canonicalUrl,
        canonical_url: canonicalUrl,
        author,
        thumbnailUrl,
        thumbnail_url: thumbnailUrl,
        timestamp: Date.now(),
      };

      try {
        if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
          chrome.runtime.sendMessage({
            action: Actions.YOUTUBE_CONTEXT_SYNC,
            payload,
          }).catch(() => {});
        }
      } catch (e) {}

      try {
        if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
          chrome.storage.local.set({ current_youtube_context: payload }).catch(() => {});
        }
      } catch (e) {}

      return payload;
    }

    /**
     * Extracts YouTube channel name / author.
     * @returns {string}
     */
    extractAuthor() {
      try {
        const el = document.querySelector("ytd-channel-name a") ||
                   document.querySelector("#channel-name a") ||
                   document.querySelector("#owner-name a");
        return el ? (el.textContent || "").trim() : "";
      } catch (e) {
        return "";
      }
    }

    /**
     * Toggles collapsed pill mode.
     */
    toggleCollapse() {
      this.isCollapsed = !this.isCollapsed;
      if (!this.shadowRoot) return;
      const pill = this.shadowRoot.getElementById("hud-pill");
      const icon = this.shadowRoot.getElementById("collapse-icon");
      if (pill) {
        pill.classList.toggle("collapsed", this.isCollapsed);
      }
      if (icon) {
        icon.textContent = this.isCollapsed ? "▶" : "◀";
      }
    }

    /**
     * Sends request to background worker to open or focus Side Panel.
     */
    requestOpenSidePanel() {
      try {
        if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
          chrome.runtime.sendMessage({
            action: Actions.OPEN_SIDE_PANEL,
            payload: { tabId: null },
          }).catch(() => {});
        }
      } catch (e) {}
    }

    /**
     * Renders Apple Dynamic Island style animated toast inside shadow DOM.
     * @param {string} message
     * @param {"info"|"success"|"warning"|"error"} type
     * @param {number} durationMs
     */
    showToast(message, type = "info", durationMs = 2200) {
      if (!this.shadowRoot) return;
      const container = this.shadowRoot.getElementById("toast-container");
      if (!container) return;

      const toast = document.createElement("div");
      toast.className = `vkdub-toast ${type}`;

      const iconSymbol = {
        success: "✓",
        warning: "⚠",
        error: "✕",
        info: "✦",
      }[type] || "✦";

      toast.innerHTML = `
        <span class="vkdub-toast-icon">${iconSymbol}</span>
        <span class="vkdub-toast-msg">${message}</span>
      `;

      container.appendChild(toast);

      setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(-6px) scale(0.95)";
        setTimeout(() => {
          if (toast.parentElement) toast.parentElement.removeChild(toast);
        }, 200);
      }, durationMs);
    }

    /**
     * Returns current state object for debugging and side panel status queries.
     */
    getState() {
      return {
        version: this.version,
        initialized: this.initialized,
        videoId: this.currentVideoId,
        videoTitle: this.currentVideoTitle,
        duration: this.duration,
        currentTime: this.currentTime,
        clipStart: this.clipStart,
        clipEnd: this.clipEnd,
        isCollapsed: this.isCollapsed,
        isAd: this.isAdShowing(),
        isLive: this.isLiveStream(),
        isWatchPage: this.isWatchPage(),
      };
    }

    /**
     * Cleans up all DOM nodes, observers, and listeners.
     */
    destroy() {
      window.removeEventListener("keydown", this._onKeydown, true);
      window.removeEventListener("yt-navigate-finish", this._onNavigate);
      window.removeEventListener("yt-page-data-updated", this._onNavigate);
      window.removeEventListener("popstate", this._onNavigate);
      window.removeEventListener("mousemove", this._onMouseMove);

      if (this.videoElement) {
        this.videoElement.removeEventListener("timeupdate", this._onTimeUpdate);
        this.videoElement.removeEventListener("loadedmetadata", this._onVideoLoaded);
        this.videoElement.removeEventListener("durationchange", this._onVideoLoaded);
      }

      if (this.navObserver) {
        this.navObserver.disconnect();
      }
      if (this.playerClassObserver) {
        this.playerClassObserver.disconnect();
      }

      this.stopPreview();
      this.clearScrubberOverlay();

      if (this.hostElement && this.hostElement.parentElement) {
        this.hostElement.parentElement.removeChild(this.hostElement);
      }

      this.initialized = false;
    }
  }

  // Singleton Instance Guard
  let adapterInstance = window.__vkdubYoutubeAdapter;
  if (!adapterInstance) {
    adapterInstance = new YouTubeAdapter();
    window.__vkdubYoutubeAdapter = adapterInstance;
  }

  // Runtime Message Dispatcher
  if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      if (!message || !message.action) return false;

      switch (message.action) {
        case Actions.YOUTUBE_SEEK_TO: {
          const rawTime = message.payload?.seconds !== undefined ? message.payload.seconds : message.payload?.time;
          const play = message.payload?.play !== false;
          const newTime = adapterInstance.seekTo(rawTime, play);
          sendResponse({ success: true, currentTime: newTime });
          return true;
        }

        case Actions.YOUTUBE_PREVIEW_CLIP: {
          const start = message.payload?.start;
          const end = message.payload?.end;
          const loop = !!message.payload?.loop;
          adapterInstance.previewClip(start, end, loop);
          sendResponse({ success: true });
          return true;
        }

        case Actions.GET_YOUTUBE_STATUS:
        case "YOUTUBE_GET_STATUS": {
          sendResponse({ success: true, state: adapterInstance.getState() });
          return true;
        }

        default:
          return false;
      }
    });
  }

  // Initialize on document readiness
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      adapterInstance.init();
      notifyAdapterReady();
    });
  } else {
    adapterInstance.init();
    notifyAdapterReady();
  }

  /**
   * Proactively notifies the service worker & side panel that this adapter is
   * alive and has a valid video context.  Side panel listens for this event to
   * update its YouTube status badge without polling.
   */
  function notifyAdapterReady() {
    // Small delay to let extractVideoId / bindVideoElement settle
    setTimeout(() => {
      try {
        if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
          const state = adapterInstance.getState();
          chrome.runtime.sendMessage({
            action: "YOUTUBE_ADAPTER_READY",
            payload: {
              videoId: state.videoId,
              videoTitle: state.videoTitle,
              duration: state.duration,
              currentTime: state.currentTime,
              isWatchPage: state.isWatchPage,
              url: window.location.href,
            },
          }).catch(() => {});
        }
      } catch (_e) {}
    }, 300);
  }

  // Node.js CommonJS exports for unit testing
  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      YouTubeAdapter,
      Actions,
      roundMs,
      formatTimecode,
      parseTimecode,
      validateClipBounds,
      isDuplicateClip,
      isUserTyping,
    };
  }
})();
