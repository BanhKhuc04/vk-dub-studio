/**
 * VK Dub Studio — Side Panel Clip Manager Controller
 *
 * Implements Apple-inspired UI logic, clip list management, HTML5 Drag-and-Drop,
 * inline timecode editing, client-side validation, seek/preview routing, and
 * realtime export progress telemetry via the Native Messaging Bridge.
 */

import {
  Actions,
  ExportStage,
  ExportMode,
  CutMode,
  createClipExportRequest,
  createClipExportCancel,
  createOpenOutputFolder,
  createYouTubeSeekTo,
  createYouTubePreviewClip,
} from "../bridge/protocol.js";

// ==========================================================================
// Timecode & Math Utilities
// ==========================================================================

export function roundMs(val) {
  const num = Number(val);
  if (!Number.isFinite(num)) return 0;
  return Math.round(num * 1000) / 1000;
}

export function formatTimecode(seconds, forceHours = false) {
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

export function parseTimecode(input) {
  if (typeof input === "number") {
    return Number.isFinite(input) && input >= 0 ? roundMs(input) : null;
  }
  if (typeof input !== "string") return null;
  const str = input.trim();
  if (!str) return null;

  // Direct seconds (e.g. "85.4")
  if (/^\d+(\.\d+)?$/.test(str)) {
    const val = parseFloat(str);
    return Number.isFinite(val) && val >= 0 ? roundMs(val) : null;
  }

  const parts = str.split(":");
  if (parts.length === 2) {
    const mins = parseInt(parts[0], 10);
    const secs = parseFloat(parts[1]);
    if (Number.isFinite(mins) && Number.isFinite(secs) && mins >= 0 && secs >= 0 && secs < 60) {
      return roundMs(mins * 60 + secs);
    }
  } else if (parts.length === 3) {
    const hrs = parseInt(parts[0], 10);
    const mins = parseInt(parts[1], 10);
    const secs = parseFloat(parts[2]);
    if (
      Number.isFinite(hrs) &&
      Number.isFinite(mins) &&
      Number.isFinite(secs) &&
      hrs >= 0 &&
      mins >= 0 &&
      mins < 60 &&
      secs >= 0 &&
      secs < 60
    ) {
      return roundMs(hrs * 3600 + mins * 60 + secs);
    }
  }
  return null;
}

export function formatDurationPill(seconds) {
  const s = Math.max(0, Number(seconds) || 0);
  if (s < 60) {
    return `${s.toFixed(1)}s`;
  }
  const mins = Math.floor(s / 60);
  const rem = (s % 60).toFixed(1);
  return `${mins}m ${rem}s`;
}

export function validateClip(clip, videoDuration = 0, allClips = []) {
  if (!clip) return { valid: false, error: "Đoạn cắt không hợp lệ." };

  const start = roundMs(clip.start);
  const end = roundMs(clip.end);

  if (!Number.isFinite(start) || start < 0) {
    return { valid: false, error: "Thời gian bắt đầu không thể âm." };
  }
  if (!Number.isFinite(end)) {
    return { valid: false, error: "Thời gian kết thúc không hợp lệ." };
  }
  if (start >= end) {
    return { valid: false, error: "Thời gian bắt đầu phải nhỏ hơn thời gian kết thúc." };
  }
  if (end - start < 0.5) {
    return { valid: false, error: "Thời lượng đoạn cắt tối thiểu là 0.5 giây." };
  }
  if (videoDuration > 0 && end > videoDuration + 0.5) {
    return { valid: false, error: "Thời gian kết thúc vượt quá thời lượng video." };
  }

  // Duplicate detection
  if (Array.isArray(allClips)) {
    const isDup = allClips.some((c) => {
      if (c.id === clip.id) return false;
      return Math.abs(c.start - start) < 0.1 && Math.abs(c.end - end) < 0.1;
    });
    if (isDup) {
      return { valid: false, error: "Đoạn cắt bị trùng lặp với một đoạn khác." };
    }
  }

  return { valid: true };
}

// ==========================================================================
// Clip Manager Application State
// ==========================================================================

class SidePanelApp {
  constructor() {
    this.video = {
      videoId: "",
      title: "",
      duration: 0,
      currentTime: 0,
      url: "",
      author: "",
      thumbnailUrl: "",
      tabId: null,
    };

    this.clips = [];
    this.draggedIndex = null;
    this.isConnected = false;
    this.connectionStatusTimer = null;
    this.connectionStatusFailures = 0;
    this.youtubeDetected = false;
    this.youtubeDetectionTimer = null;

    this.activeJob = {
      requestId: null,
      jobId: null,
      stage: null,
      percent: 0,
      speed: "-- MB/s",
      downloadedBytes: 0,
      totalBytes: 0,
      message: "",
      currentClip: 0,
      totalClips: 0,
      isRunning: false,
      files: [],
      mergedFile: null,
      outputDir: "",
    };

    this.settings = {
      exportMode: ExportMode.SEPARATE,
      outputDir: "",
      container: "mp4",
      quality: "best",
      cutMode: CutMode.STREAM_COPY,
      useCookies: false,
    };

    this.elements = {};
  }

  init() {
    this.cacheDomElements();
    this.bindEvents();
    this.setupDnD();
    this.initChromeListeners();
    this.loadSavedState();
  }

  cacheDomElements() {
    this.elements = {
      statusBadge: document.getElementById("connection-status-badge"),
      statusLabel: document.getElementById("connection-status-text"),
      youtubeStatusBadge: document.getElementById("youtube-status-badge"),
      youtubeStatusLabel: document.getElementById("youtube-status-text"),
      toastContainer: document.getElementById("toast-container"),

      // Video Card
      videoCard: document.getElementById("video-card"),
      videoThumb: document.getElementById("video-thumbnail"),
      videoDuration: document.getElementById("video-duration-badge"),
      videoTitle: document.getElementById("video-title"),
      videoIdBadge: document.getElementById("video-id-badge"),
      videoAuthorBadge: document.getElementById("video-author-badge"),
      youtubeRecovery: document.getElementById("youtube-recovery"),
      youtubeErrorDetail: document.getElementById("youtube-error-detail"),
      btnRetryYouTube: document.getElementById("btn-retry-youtube"),

      // Clips & Empty State
      emptyState: document.getElementById("empty-state"),
      clipsSection: document.getElementById("clips-section"),
      clipsList: document.getElementById("clips-list"),
      btnAddFirstManual: document.getElementById("btn-add-first-manual"),
      selectAllCheckbox: document.getElementById("select-all-checkbox"),
      selectedSummary: document.getElementById("selected-summary"),
      btnAddManual: document.getElementById("btn-add-clip-manual"),
      btnClearClips: document.getElementById("btn-clear-clips"),

      // Validation
      validationBanner: document.getElementById("validation-banner"),
      validationBannerText: document.getElementById("validation-banner-text"),

      // Export settings
      exportCard: document.getElementById("export-card"),
      outputDirInput: document.getElementById("output-dir-input"),
      btnOpenFolder: document.getElementById("btn-open-folder"),
      containerSelect: document.getElementById("container-select"),
      qualitySelect: document.getElementById("quality-select"),
      useCookiesCheckbox: document.getElementById("use-cookies-checkbox"),
      btnExportStart: document.getElementById("btn-export-start"),
      exportButtonText: document.getElementById("export-button-text"),

      // Progress
      progressCard: document.getElementById("progress-card"),
      progressStageBadge: document.getElementById("progress-stage-badge"),
      progressPercentLabel: document.getElementById("progress-percent-label"),
      progressBarFill: document.getElementById("progress-bar-fill"),
      progressMessage: document.getElementById("progress-message"),
      progressSpeed: document.getElementById("progress-speed"),
      progressBytes: document.getElementById("progress-bytes"),
      progressClipsCounter: document.getElementById("progress-clips-counter"),
      btnCancelExport: document.getElementById("btn-cancel-export"),

      // Result
      resultCard: document.getElementById("result-card"),
      resultSummary: document.getElementById("result-summary"),
      resultFilesUl: document.getElementById("result-files-ul"),
      btnResultOpenFolder: document.getElementById("btn-result-open-folder"),
      btnResultImportStudio: document.getElementById("btn-result-import-studio"),
      btnResultDone: document.getElementById("btn-result-done"),
    };
  }

  bindEvents() {
    this.elements.btnAddFirstManual.addEventListener("click", () => {
      this.addManualClip();
    });

    this.elements.btnRetryYouTube.addEventListener("click", async () => {
      this.hideYouTubeError();
      this.elements.btnRetryYouTube.disabled = true;
      this.updateYouTubeStatus("pending", "YouTube: đang kích hoạt lại...");
      try {
        await this.detectActiveTab();
      } catch (error) {
        const detail = error?.message || String(error || "Không kích hoạt được YouTube");
        this.updateYouTubeStatus("disconnected", "YouTube: kích hoạt thất bại");
        this.showYouTubeError(detail);
      } finally {
        this.elements.btnRetryYouTube.disabled = false;
      }
    });

    // Select All Checkbox
    this.elements.selectAllCheckbox.addEventListener("change", (e) => {
      const checked = e.target.checked;
      this.clips.forEach((c) => (c.selected = checked));
      this.saveClips();
      this.renderClipsList();
    });

    // Add Clip Manually
    this.elements.btnAddManual.addEventListener("click", () => {
      this.addManualClip();
    });

    // Clear All Clips
    this.elements.btnClearClips.addEventListener("click", () => {
      if (!this.clips.length) return;
      if (confirm("Bạn có chắc chắn muốn xóa toàn bộ danh sách đoạn cắt không?")) {
        this.clips = [];
        this.saveClips();
        this.renderClipsList();
        this.showToast("Đã xóa toàn bộ đoạn cắt", "info");
      }
    });

    // Export Mode Segmented Control
    const modeRadios = document.querySelectorAll('input[name="export-mode"]');
    modeRadios.forEach((r) => {
      r.addEventListener("change", (e) => {
        this.settings.exportMode = e.target.value;
        this.saveSettings();
        this.updateExportButtonState();
      });
    });

    // Cut Mode Radios
    const cutRadios = document.querySelectorAll('input[name="cut-mode"]');
    cutRadios.forEach((r) => {
      r.addEventListener("change", (e) => {
        this.settings.cutMode = e.target.value;
        this.saveSettings();
      });
    });

    // Output Directory
    this.elements.outputDirInput.addEventListener("input", (e) => {
      this.settings.outputDir = e.target.value.trim();
      this.saveSettings();
    });

    // Open Output Folder
    this.elements.btnOpenFolder.addEventListener("click", () => {
      this.openOutputFolder(this.settings.outputDir);
    });

    // Container Select
    this.elements.containerSelect.addEventListener("change", (e) => {
      this.settings.container = e.target.value;
      this.saveSettings();
    });

    // Quality Select
    this.elements.qualitySelect.addEventListener("change", (e) => {
      this.settings.quality = e.target.value;
      this.saveSettings();
    });

    // Cookies Checkbox
    this.elements.useCookiesCheckbox.addEventListener("change", (e) => {
      this.settings.useCookies = e.target.checked;
      this.saveSettings();
    });

    // Start Export
    this.elements.btnExportStart.addEventListener("click", () => {
      this.startExport();
    });

    // Cancel Export
    this.elements.btnCancelExport.addEventListener("click", () => {
      this.cancelExport();
    });

    // Result Actions
    this.elements.btnResultOpenFolder.addEventListener("click", () => {
      this.openOutputFolder(this.activeJob.outputDir || this.settings.outputDir);
    });

    this.elements.btnResultImportStudio.addEventListener("click", () => {
      this.importResultToStudio();
    });

    this.elements.btnResultDone.addEventListener("click", () => {
      this.elements.resultCard.classList.add("hidden");
      this.elements.exportCard.classList.remove("hidden");
    });
  }

  setupDnD() {
    const list = this.elements.clipsList;

    list.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      const targetCard = e.target.closest(".clip-card");
      if (!targetCard) return;

      const cards = [...list.querySelectorAll(".clip-card")];
      cards.forEach((c) => c.classList.remove("drag-over"));
      targetCard.classList.add("drag-over");
    });

    list.addEventListener("drop", (e) => {
      e.preventDefault();
      const targetCard = e.target.closest(".clip-card");
      if (!targetCard || this.draggedIndex === null) return;

      const targetIndex = parseInt(targetCard.dataset.index, 10);
      if (Number.isFinite(targetIndex) && targetIndex !== this.draggedIndex) {
        const moved = this.clips.splice(this.draggedIndex, 1)[0];
        this.clips.splice(targetIndex, 0, moved);
        this.saveClips();
        this.renderClipsList();
      }
    });

    list.addEventListener("dragend", () => {
      this.draggedIndex = null;
      const cards = list.querySelectorAll(".clip-card");
      cards.forEach((c) => {
        c.classList.remove("dragging", "drag-over");
      });
    });
  }

  // ==========================================================================
  // Storage & Persistence
  // ==========================================================================

  loadSavedState() {
    if (typeof chrome === "undefined" || !chrome.storage || !chrome.storage.local) {
      this.detectActiveTab();
      return;
    }

    chrome.storage.local.get(
      ["last_export_settings", "current_youtube_context", "active_export_job"],
      (res) => {
        if (res.last_export_settings) {
          this.settings = { ...this.settings, ...res.last_export_settings };
          this.applySettingsToUi();
        }

        if (res.current_youtube_context) {
          this.updateVideoContext(res.current_youtube_context, false);
        }

        if (res.active_export_job && res.active_export_job.isRunning) {
          this.activeJob = { ...this.activeJob, ...res.active_export_job };
          this.restoreActiveJobUi();
        }

        // The active tab is authoritative. Stored context is only a fast visual
        // restore and must not make an old YouTube video look currently detected.
        this.detectActiveTab();
      }
    );
  }

  applySettingsToUi() {
    this.elements.outputDirInput.value = this.settings.outputDir || "";
    this.elements.containerSelect.value = this.settings.container || "mp4";
    this.elements.qualitySelect.value = this.settings.quality || "best";
    this.elements.useCookiesCheckbox.checked = !!this.settings.useCookies;

    const modeRadio = document.querySelector(`input[name="export-mode"][value="${this.settings.exportMode}"]`);
    if (modeRadio) modeRadio.checked = true;

    const cutRadio = document.querySelector(`input[name="cut-mode"][value="${this.settings.cutMode}"]`);
    if (cutRadio) cutRadio.checked = true;
  }

  saveSettings() {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      chrome.storage.local.set({ last_export_settings: this.settings }).catch(() => {});
    }
  }

  loadClipsForVideo(videoId) {
    if (!videoId) {
      this.clips = [];
      this.renderClipsList();
      return;
    }

    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      const key = `clips_${videoId}`;
      chrome.storage.local.get([key], (res) => {
        this.clips = Array.isArray(res[key]) ? res[key] : [];
        this.renderClipsList();
      });
    }
  }

  saveClips() {
    if (!this.video.videoId) return;
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      const key = `clips_${this.video.videoId}`;
      chrome.storage.local.set({ [key]: this.clips }).catch(() => {});
    }
  }

  saveActiveJobState() {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      chrome.storage.local.set({ active_export_job: this.activeJob }).catch(() => {});
    }
  }

  // ==========================================================================
  // Active Tab Detection & Context Sync
  // ==========================================================================

  detectActiveTab() {
    if (typeof chrome === "undefined" || !chrome.tabs || !chrome.tabs.query) {
      this.updateYouTubeStatus("disconnected", "YouTube: không kiểm tra được");
      return;
    }

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs || !tabs.length) {
        this.clearDetectedVideo("YouTube: chưa mở video");
        return;
      }
      const tab = tabs[0];
      const url = tab.url || tab.pendingUrl || "";

      if (url.includes("youtube.com/watch")) {
        let urlVideoId = "";
        try {
          urlVideoId = new URL(url).searchParams.get("v") || "";
        } catch (_urlError) {}

        // URL and tab title require no page-script injection. Record them first
        // so download/manual clipping remains available under strict Edge site access.
        if (urlVideoId) {
          this.updateVideoContext({
            videoId: urlVideoId,
            title: (tab.title || "Video YouTube").replace(/\s*-\s*YouTube\s*$/i, "").trim(),
            duration: 0,
            currentTime: 0,
            url,
            tabId: tab.id,
          });
        }
        this.updateYouTubeStatus("pending", "YouTube: đã nhận URL, đang bật toolbar...");
        this.video.tabId = tab.id;
        this.requestYouTubeStatus(tab)
          .then((resp) => {
            if (!resp || !resp.state || !resp.state.videoId) {
              throw new Error("Content script chưa trả về thông tin video");
            }

            if (resp.state.isWatchPage) {
              this.updateVideoContext({
                videoId: resp.state.videoId,
                title: resp.state.videoTitle,
                duration: resp.state.duration,
                currentTime: resp.state.currentTime,
                url: tab.url,
                tabId: tab.id,
              });
              if (resp.adapterReady === false) {
                this.updateYouTubeStatus("pending", "YouTube: nhận cơ bản, toolbar lỗi");
                this.showToast(
                  `Không khởi động được toolbar: ${resp.error || "lỗi chưa xác định"}`,
                  "error",
                  6500
                );
              }
            }
          })
          .catch((error) => {
            const rawDetail = error?.message || String(error || "Lỗi không xác định");
            const detail = /\bBlocked\b/i.test(rawDetail)
              ? "Edge chưa nạp quyền chèn script của extension. Hãy Reload VK Dub Studio Bridge tại edge://extensions (không chỉ Ctrl+Shift+R trang YouTube), rồi tải lại YouTube."
              : rawDetail;
            this.youtubeDetected = !!this.video.videoId;
            this.elements.videoCard.classList.toggle("detected", this.youtubeDetected);
            this.updateYouTubeStatus("disconnected", "YouTube: đã nhận video, toolbar bị chặn");
            this.elements.videoTitle.title = detail;
            this.showYouTubeError(detail);
            this.updateExportButtonState();
          });
      } else {
        this.clearDetectedVideo("YouTube: chưa mở video");
      }
    });
  }

  async requestYouTubeStatus(tab) {
    const message = { action: "GET_YOUTUBE_STATUS" };

    // Content script may have been auto-injected by manifest but not yet fully
    // initialised. Retry with progressive delays before falling back.
    const retryDelays = [0, 300, 600, 1000];
    for (const delay of retryDelays) {
      if (delay > 0) {
        await new Promise((r) => setTimeout(r, delay));
      }
      try {
        const resp = await chrome.tabs.sendMessage(tab.id, message);
        if (resp?.state?.videoId) return resp;
      } catch (_err) {
        // Listener not registered yet — keep trying
      }
    }

    // Ask the service worker to inject and verify the adapter. Keeping this in
    // the background is more reliable in Edge Side Panel contexts.
    this.updateYouTubeStatus("pending", "YouTube: đang kích hoạt...");
    const result = await chrome.runtime.sendMessage({
      action: Actions.ENSURE_YOUTUBE_ADAPTER,
      payload: { tabId: tab.id },
    });
    if (!result?.success || !result?.state?.videoId) {
      throw new Error(result?.error || "Không kích hoạt được adapter");
    }
    return result;
  }

  scheduleActiveTabDetection(delayMs = 180) {
    if (this.youtubeDetectionTimer) clearTimeout(this.youtubeDetectionTimer);
    this.youtubeDetectionTimer = setTimeout(() => {
      this.youtubeDetectionTimer = null;
      this.detectActiveTab();
    }, delayMs);
  }

  clearDetectedVideo(statusText) {
    this.youtubeDetected = false;
    this.video = {
      videoId: "",
      title: "",
      duration: 0,
      currentTime: 0,
      url: "",
      author: "",
      thumbnailUrl: "",
      tabId: null,
    };
    this.clips = [];
    this.elements.videoCard.classList.remove("detected");
    this.elements.videoTitle.textContent = "Hãy mở một video YouTube";
    this.elements.videoTitle.title = "Mở trang youtube.com/watch để bắt đầu";
    this.elements.videoIdBadge.textContent = "v=--------";
    this.elements.videoAuthorBadge.textContent = "YouTube";
    this.elements.videoDuration.textContent = "00:00:00";
    this.hideYouTubeError();
    this.updateYouTubeStatus("disconnected", statusText);
    this.renderClipsList();
  }

  showYouTubeError(message) {
    if (!this.elements.youtubeRecovery || !this.elements.youtubeErrorDetail) return;
    this.elements.youtubeErrorDetail.textContent = message;
    this.elements.youtubeRecovery.classList.remove("hidden");
  }

  hideYouTubeError() {
    if (!this.elements.youtubeRecovery || !this.elements.youtubeErrorDetail) return;
    this.elements.youtubeRecovery.classList.add("hidden");
    this.elements.youtubeErrorDetail.textContent = "";
  }

  updateYouTubeStatus(status, message) {
    if (!this.elements.youtubeStatusBadge || !this.elements.youtubeStatusLabel) return;
    this.elements.youtubeStatusBadge.className = `status-badge ${status}`;
    this.elements.youtubeStatusLabel.textContent = message;
    this.elements.youtubeStatusBadge.title =
      status === "connected"
        ? "Extension đã nhận diện đúng video YouTube đang mở"
        : status === "pending"
          ? "Đang hỏi content script trên tab YouTube"
          : "Mở một video YouTube; nếu đã mở, nhấn F5 sau khi Reload extension";
  }

  updateVideoContext(payload, switchClips = true) {
    if (!payload || !payload.videoId) return;

    const changedVideo = this.video.videoId !== payload.videoId;
    this.video.videoId = payload.videoId;
    this.video.title = payload.title || this.video.title || "Video YouTube";
    this.video.duration = payload.duration || this.video.duration || 0;
    this.video.currentTime = payload.currentTime || 0;
    this.video.url = payload.url || `https://www.youtube.com/watch?v=${payload.videoId}`;
    this.video.author = payload.author || this.video.author || "YouTube";
    this.video.thumbnailUrl =
      payload.thumbnailUrl || `https://i.ytimg.com/vi/${payload.videoId}/mqdefault.jpg`;
    if (payload.tabId) this.video.tabId = payload.tabId;

    // UI Updates
    this.elements.videoTitle.textContent = this.video.title;
    this.elements.videoTitle.title = this.video.title;
    this.elements.videoIdBadge.textContent = `v=${this.video.videoId}`;
    this.elements.videoAuthorBadge.textContent = this.video.author;
    this.elements.videoThumb.src = this.video.thumbnailUrl;
    this.elements.videoDuration.textContent = formatTimecode(this.video.duration, true);
    this.hideYouTubeError();
    this.youtubeDetected = true;
    this.elements.videoCard.classList.add("detected");
    this.updateYouTubeStatus("connected", "YouTube: đã nhận video");

    if (changedVideo && switchClips) {
      this.loadClipsForVideo(this.video.videoId);
    }
  }

  // ==========================================================================
  // Clip Management Logic
  // ==========================================================================

  addClipFromEvent(clipData) {
    if (!clipData) return;

    // Duplicate check
    const isDup = this.clips.some((c) => {
      return (
        Math.abs(c.start - clipData.start) < 0.1 &&
        Math.abs(c.end - clipData.end) < 0.1
      );
    });

    if (isDup) {
      this.showToast("Đoạn cắt đã tồn tại trong danh sách", "warning");
      return;
    }

    const newClip = {
      id: clipData.id || `clip_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      name: clipData.name || `Clip ${this.clips.length + 1}`,
      start: roundMs(clipData.start),
      end: roundMs(clipData.end),
      duration: roundMs(clipData.duration || clipData.end - clipData.start),
      selected: true,
      createdAt: Date.now(),
    };

    this.clips.push(newClip);
    this.saveClips();
    this.renderClipsList();
    this.showToast(`Đã thêm ${newClip.name}`, "success");
  }

  addManualClip() {
    const curTime = this.video.currentTime || 0;
    const end = Math.min(this.video.duration || Infinity, curTime + 10);

    const newClip = {
      id: `clip_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      name: `Clip ${this.clips.length + 1}`,
      start: roundMs(curTime),
      end: roundMs(end),
      duration: roundMs(end - curTime),
      selected: true,
      createdAt: Date.now(),
    };

    this.clips.push(newClip);
    this.saveClips();
    this.renderClipsList();
    this.showToast(`Đã tạo ${newClip.name}`, "info");
  }

  renderClipsList() {
    const hasClips = this.clips.length > 0;
    this.elements.emptyState.classList.toggle("hidden", hasClips);
    this.elements.clipsSection.classList.toggle("hidden", !hasClips);

    if (!hasClips) {
      this.updateExportButtonState();
      return;
    }

    const list = this.elements.clipsList;
    list.innerHTML = "";

    let totalDuration = 0;
    let selectedCount = 0;
    const forceHours = this.video.duration >= 3600;

    this.clips.forEach((clip, index) => {
      const validation = validateClip(clip, this.video.duration, this.clips);
      if (clip.selected) {
        selectedCount++;
        totalDuration += clip.duration;
      }

      const card = document.createElement("div");
      card.className = `clip-card ${validation.valid ? "" : "has-error"}`;
      card.dataset.id = clip.id;
      card.dataset.index = index;
      card.draggable = true;

      // Card Header / Row 1
      const topRow = document.createElement("div");
      topRow.className = "clip-top-row";

      // Drag Grip
      const grip = document.createElement("span");
      grip.className = "drag-grip";
      grip.title = "Kéo thả để sắp xếp lại thứ tự";
      grip.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <circle cx="9" cy="6" r="2"/><circle cx="15" cy="6" r="2"/>
          <circle cx="9" cy="12" r="2"/><circle cx="15" cy="12" r="2"/>
          <circle cx="9" cy="18" r="2"/><circle cx="15" cy="18" r="2"/>
        </svg>
      `;

      // Checkbox
      const chk = document.createElement("input");
      chk.type = "checkbox";
      chk.className = "apple-checkbox";
      chk.checked = !!clip.selected;
      chk.addEventListener("change", (e) => {
        clip.selected = e.target.checked;
        this.saveClips();
        this.updateSummaryText();
        this.updateExportButtonState();
      });

      // Name Input
      const nameInput = document.createElement("input");
      nameInput.type = "text";
      nameInput.className = "clip-name-input";
      nameInput.value = clip.name;
      nameInput.placeholder = "Tên đoạn...";
      nameInput.addEventListener("change", (e) => {
        clip.name = e.target.value.trim() || `Clip ${index + 1}`;
        this.saveClips();
      });

      // Mini Actions (Preview Seek, Delete)
      const actionsMini = document.createElement("div");
      actionsMini.className = "clip-actions-mini";

      // Preview Button
      const btnPreview = document.createElement("button");
      btnPreview.className = "btn-icon";
      btnPreview.title = "Xem thử đoạn này trên YouTube";
      btnPreview.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>
      `;
      btnPreview.addEventListener("click", () => {
        this.previewClip(clip);
      });

      // Delete Button
      const btnDel = document.createElement("button");
      btnDel.className = "btn-icon danger";
      btnDel.title = "Xóa đoạn này";
      btnDel.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      `;
      btnDel.addEventListener("click", () => {
        this.deleteClip(clip.id);
      });

      actionsMini.appendChild(btnPreview);
      actionsMini.appendChild(btnDel);

      topRow.appendChild(grip);
      topRow.appendChild(chk);
      topRow.appendChild(nameInput);
      topRow.appendChild(actionsMini);

      // Card Body / Row 2 (Timecodes and Duration)
      const bodyRow = document.createElement("div");
      bodyRow.className = "clip-body-row";

      const tcGroup = document.createElement("div");
      tcGroup.className = "timecode-pill-group";

      const lblIn = document.createElement("span");
      lblIn.className = "timecode-label";
      lblIn.textContent = "IN";

      const inInput = document.createElement("input");
      inInput.type = "text";
      inInput.className = "timecode-edit-input";
      inInput.value = formatTimecode(clip.start, forceHours);
      inInput.title = "Nhấp để sửa thời gian bắt đầu (Enter để lưu)";
      inInput.addEventListener("change", (e) => {
        const parsed = parseTimecode(e.target.value);
        if (parsed !== null) {
          clip.start = parsed;
          clip.duration = roundMs(clip.end - clip.start);
          this.saveClips();
          this.renderClipsList();
        } else {
          e.target.value = formatTimecode(clip.start, forceHours);
          this.showToast("Định dạng timecode không hợp lệ", "warning");
        }
      });
      inInput.addEventListener("click", (e) => {
        // Seek player to clip start
        this.seekPlayerTo(clip.start);
      });

      const arrow = document.createElement("span");
      arrow.className = "timecode-arrow";
      arrow.textContent = "➔";

      const lblOut = document.createElement("span");
      lblOut.className = "timecode-label";
      lblOut.textContent = "OUT";

      const outInput = document.createElement("input");
      outInput.type = "text";
      outInput.className = "timecode-edit-input";
      outInput.value = formatTimecode(clip.end, forceHours);
      outInput.title = "Nhấp để sửa thời gian kết thúc (Enter để lưu)";
      outInput.addEventListener("change", (e) => {
        const parsed = parseTimecode(e.target.value);
        if (parsed !== null) {
          clip.end = parsed;
          clip.duration = roundMs(clip.end - clip.start);
          this.saveClips();
          this.renderClipsList();
        } else {
          e.target.value = formatTimecode(clip.end, forceHours);
          this.showToast("Định dạng timecode không hợp lệ", "warning");
        }
      });
      outInput.addEventListener("click", (e) => {
        this.seekPlayerTo(clip.end);
      });

      tcGroup.appendChild(lblIn);
      tcGroup.appendChild(inInput);
      tcGroup.appendChild(arrow);
      tcGroup.appendChild(lblOut);
      tcGroup.appendChild(outInput);

      const durPill = document.createElement("span");
      durPill.className = "clip-duration-pill";
      durPill.textContent = formatDurationPill(clip.duration);

      bodyRow.appendChild(tcGroup);
      bodyRow.appendChild(durPill);

      card.appendChild(topRow);
      card.appendChild(bodyRow);

      // Validation error message row
      if (!validation.valid) {
        const errRow = document.createElement("div");
        errRow.className = "clip-error-msg";
        errRow.innerHTML = `
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          <span>${validation.error}</span>
        `;
        card.appendChild(errRow);
      }

      // DnD Event Handlers on Card
      card.addEventListener("dragstart", (e) => {
        this.draggedIndex = index;
        card.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
      });

      list.appendChild(card);
    });

    this.updateSummaryText();
    this.updateExportButtonState();
  }

  deleteClip(clipId) {
    const idx = this.clips.findIndex((c) => c.id === clipId);
    if (idx !== -1) {
      const removed = this.clips.splice(idx, 1)[0];
      this.saveClips();
      this.renderClipsList();
      this.showToast(`Đã xóa ${removed.name}`, "info");
    }
  }

  updateSummaryText() {
    const selected = this.clips.filter((c) => c.selected);
    const totalDuration = selected.reduce((acc, c) => acc + (c.duration || 0), 0);
    this.elements.selectedSummary.textContent = `${selected.length} đoạn đã chọn (${formatTimecode(
      totalDuration
    )})`;

    this.elements.selectAllCheckbox.checked =
      this.clips.length > 0 && selected.length === this.clips.length;
  }

  updateExportButtonState() {
    const selected = this.clips.filter((c) => c.selected);
    const hasInvalid = selected.some((c) => !validateClip(c, this.video.duration, this.clips).valid);

    const btn = this.elements.btnExportStart;
    const btnText = this.elements.exportButtonText;

    if (!this.youtubeDetected || !this.video.videoId) {
      btn.disabled = true;
      btnText.textContent = "Hãy mở video YouTube";
      this.elements.validationBanner.classList.add("hidden");
      return;
    }

    if (!selected.length) {
      btn.disabled = true;
      btnText.textContent = "Chưa chọn đoạn nào";
      this.elements.validationBanner.classList.add("hidden");
      return;
    }

    if (hasInvalid) {
      btn.disabled = true;
      btnText.textContent = "Cần sửa đoạn bị lỗi";
      this.elements.validationBanner.classList.remove("hidden");
      this.elements.validationBannerText.textContent =
        "Có đoạn cắt chưa hợp lệ (start >= end hoặc vượt thời lượng). Vui lòng điều chỉnh.";
      return;
    }

    this.elements.validationBanner.classList.add("hidden");
    btn.disabled = this.activeJob.isRunning;

    const modeLabels = {
      SEPARATE: `Xuất ${selected.length} tệp riêng`,
      MERGED: `Ghép ${selected.length} đoạn thành 1`,
      IMPORT: `Cắt & đưa vào ToolVideo`,
    };

    btnText.textContent = modeLabels[this.settings.exportMode] || `Bắt đầu xuất (${selected.length} đoạn)`;
  }

  // ==========================================================================
  // In-Player YouTube Control Relaying
  // ==========================================================================

  seekPlayerTo(seconds) {
    const payload = { seconds: roundMs(seconds), play: true, tabId: this.video.tabId };
    this.dispatchToContentScript(Actions.YOUTUBE_SEEK_TO, payload);
  }

  previewClip(clip) {
    const payload = {
      start: roundMs(clip.start),
      end: roundMs(clip.end),
      loop: false,
      tabId: this.video.tabId,
    };
    this.dispatchToContentScript(Actions.YOUTUBE_PREVIEW_CLIP, payload);
    this.showToast(`Đang xem thử: ${clip.name}`, "info");
  }

  dispatchToContentScript(action, payload) {
    // 1. Direct tab sendMessage if tabId known
    if (this.video.tabId && typeof chrome !== "undefined" && chrome.tabs) {
      chrome.tabs.sendMessage(this.video.tabId, { action, payload }).catch(() => {
        // Fallback: send via background
        this.dispatchViaBackground(action, payload);
      });
      return;
    }

    // 2. Fallback via background router
    this.dispatchViaBackground(action, payload);
  }

  dispatchViaBackground(action, payload) {
    if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
      chrome.runtime.sendMessage({ action, payload }).catch(() => {});
    }
  }

  // ==========================================================================
  // Export Job Lifecycle & Telemetry
  // ==========================================================================

  startExport() {
    const selected = this.clips.filter((c) => c.selected);
    if (!selected.length) return;

    // Final integrity check
    for (const c of selected) {
      const v = validateClip(c, this.video.duration, this.clips);
      if (!v.valid) {
        this.showToast(`Lỗi: ${v.error}`, "error");
        return;
      }
    }

    const requestId = `req_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    // An empty destination deliberately delegates to the Local Agent's configured
    // ToolVideo workspace instead of baking a developer-specific drive path into
    // the extension.
    const outputDir = this.settings.outputDir || "";

    const exportClipsPayload = selected.map((c, i) => ({
      id: c.id,
      index: i + 1,
      name: c.name,
      start: roundMs(c.start),
      end: roundMs(c.end),
      duration: roundMs(c.duration),
    }));

    const req = createClipExportRequest({
      requestId,
      jobId: requestId,
      videoId: this.video.videoId,
      videoUrl: this.video.url,
      videoTitle: this.video.title,
      duration: this.video.duration,
      clips: exportClipsPayload,
      exportMode: this.settings.exportMode,
      outputDir,
      container: this.settings.container,
      quality: this.settings.quality,
      cutMode: this.settings.cutMode,
      useCookies: this.settings.useCookies,
      browser: navigator.userAgent.includes("Edg/") ? "edge" : "chrome",
    });

    // Initialize UI active job state
    this.activeJob = {
      requestId,
      jobId: requestId,
      stage: ExportStage.PROBING,
      percent: 0,
      speed: "-- MB/s",
      downloadedBytes: 0,
      totalBytes: 0,
      message: "Đang kiểm tra nguồn và kết nối...",
      currentClip: 0,
      totalClips: selected.length,
      isRunning: true,
      files: [],
      mergedFile: null,
      outputDir,
    };

    this.saveActiveJobState();
    this.restoreActiveJobUi();

    // Send to background service worker for bridge forwarding
    this.dispatchViaBackground(Actions.CLIP_EXPORT_REQUEST, req.payload);
    this.showToast("Đã gửi yêu cầu xuất video", "info");
  }

  cancelExport() {
    if (!this.activeJob.requestId) return;

    const cancelMsg = createClipExportCancel(this.activeJob.requestId, this.activeJob.jobId);
    this.dispatchViaBackground(Actions.CLIP_EXPORT_CANCEL, cancelMsg.payload);

    this.activeJob.isRunning = false;
    this.activeJob.stage = ExportStage.CANCELLED;
    this.activeJob.message = "Đã hủy tác vụ xuất video.";
    this.saveActiveJobState();

    this.showToast("Đã hủy tác vụ xuất video", "warning");
    setTimeout(() => {
      this.elements.progressCard.classList.add("hidden");
      this.elements.exportCard.classList.remove("hidden");
      this.updateExportButtonState();
    }, 1200);
  }

  handleExportAccepted(payload) {
    const requestId = payload?.requestId || payload?.request_id;
    if (requestId && requestId !== this.activeJob.requestId) return;
    this.activeJob.stage = ExportStage.CHECKING_SOURCE;
    this.activeJob.message = "Đã nhận tác vụ, đang kiểm tra cache nguồn...";
    this.updateProgressUi();
  }

  handleExportProgress(payload) {
    if (!payload) return;
    const requestId = payload.requestId || payload.request_id;
    if (this.activeJob.requestId && requestId && requestId !== this.activeJob.requestId) {
      return;
    }

    this.activeJob.stage = payload.stage || this.activeJob.stage;
    this.activeJob.percent = Number.isFinite(payload.percent)
      ? Math.round(payload.percent)
      : Number.isFinite(payload.overall_progress)
      ? Math.round(payload.overall_progress)
      : this.activeJob.percent;

    this.activeJob.speed = payload.speed || payload.download_speed || this.activeJob.speed;
    this.activeJob.downloadedBytes = payload.downloadedBytes || payload.downloaded_bytes || this.activeJob.downloadedBytes;
    this.activeJob.totalBytes = payload.totalBytes || payload.total_bytes || this.activeJob.totalBytes;
    this.activeJob.currentClip = payload.currentClip || payload.current_clip || this.activeJob.currentClip;
    this.activeJob.totalClips = payload.totalClips || payload.total_clips || this.activeJob.totalClips;
    this.activeJob.message = payload.message || this.formatStageMessage(this.activeJob.stage);

    this.updateProgressUi();
    this.saveActiveJobState();
  }

  handleExportResult(payload) {
    const requestId = payload?.requestId || payload?.request_id;
    if (this.activeJob.requestId && requestId && requestId !== this.activeJob.requestId) {
      return;
    }
    this.activeJob.isRunning = false;
    this.activeJob.stage = ExportStage.COMPLETE;
    this.activeJob.percent = 100;
    this.activeJob.files = payload?.files || payload?.output_files || [];
    this.activeJob.mergedFile = payload?.mergedFile || payload?.merged_file || null;
    this.activeJob.outputDir =
      payload?.outputDir || payload?.output_dir || payload?.output_directory || this.settings.outputDir;

    this.saveActiveJobState();

    // Show result UI
    this.elements.progressCard.classList.add("hidden");
    this.elements.resultCard.classList.remove("hidden");

    const totalFiles = this.activeJob.files.length;
    this.elements.resultSummary.textContent = this.activeJob.mergedFile
      ? `Đã ghép thành công video: ${this.getBasename(this.activeJob.mergedFile)}`
      : `Đã hoàn tất xuất ${totalFiles} tệp video riêng lẻ.`;

    const ul = this.elements.resultFilesUl;
    ul.innerHTML = "";

    const displayList = this.activeJob.mergedFile
      ? [this.activeJob.mergedFile]
      : this.activeJob.files;

    displayList.forEach((path) => {
      const li = document.createElement("li");
      li.textContent = path;
      ul.appendChild(li);
    });

    this.showToast("Xuất video thành công!", "success");
    this.updateExportButtonState();
  }

  handleExportError(payload) {
    const requestId = payload?.requestId || payload?.request_id;
    if (this.activeJob.requestId && requestId && requestId !== this.activeJob.requestId) {
      return;
    }
    this.activeJob.isRunning = false;
    this.activeJob.stage = ExportStage.ERROR;
    const errMsg = payload?.error || "Đã xảy ra lỗi trong quá trình xuất video.";

    this.saveActiveJobState();
    this.showToast(`Lỗi xuất: ${errMsg}`, "error");

    this.elements.progressCard.classList.add("hidden");
    this.elements.exportCard.classList.remove("hidden");
    this.updateExportButtonState();
  }

  formatStageMessage(stage) {
    switch (stage) {
      case ExportStage.PROBING:
        return "Đang kiểm tra phần cứng và encoder...";
      case ExportStage.CHECKING_SOURCE:
        return "Đang kiểm tra tệp nguồn...";
      case ExportStage.DOWNLOADING:
        return "Đang tải luồng video/audio từ YouTube...";
      case ExportStage.REMUXING:
        return "Đang ghép video và audio nguồn...";
      case ExportStage.TRIMMING:
        return `Đang cắt đoạn ${this.activeJob.currentClip}/${this.activeJob.totalClips}...`;
      case ExportStage.MERGING:
        return "Đang ghép tất cả các đoạn...";
      case ExportStage.PIPELINE_FEED:
        return "Đang nạp vào timeline ToolVideo...";
      case ExportStage.COMPLETE:
        return "Hoàn tất xuất video!";
      default:
        return "Đang xử lý...";
    }
  }

  restoreActiveJobUi() {
    this.elements.exportCard.classList.add("hidden");
    this.elements.progressCard.classList.remove("hidden");
    this.updateProgressUi();
  }

  updateProgressUi() {
    const job = this.activeJob;
    this.elements.progressStageBadge.textContent = job.stage || "Đang xử lý";
    this.elements.progressPercentLabel.textContent = `${job.percent}%`;
    this.elements.progressBarFill.style.width = `${job.percent}%`;
    this.elements.progressMessage.textContent = job.message || "";
    this.elements.progressSpeed.textContent = job.speed || "-- MB/s";

    if (job.totalBytes > 0) {
      const mbDl = (job.downloadedBytes / (1024 * 1024)).toFixed(1);
      const mbTot = (job.totalBytes / (1024 * 1024)).toFixed(1);
      this.elements.progressBytes.textContent = `${mbDl} / ${mbTot} MB`;
    } else {
      this.elements.progressBytes.textContent = "-- / --";
    }

    this.elements.progressClipsCounter.textContent = `${job.currentClip || 0} / ${job.totalClips || 0}`;
  }

  openOutputFolder(path) {
    const p = path || this.settings.outputDir;
    const msg = createOpenOutputFolder(p);
    this.dispatchViaBackground(Actions.OPEN_OUTPUT_FOLDER, msg.payload);
    this.showToast("Đang mở thư mục trong Windows Explorer...", "info");
  }

  importResultToStudio() {
    const targetFile = this.activeJob.mergedFile || (this.activeJob.files && this.activeJob.files[0]);
    if (!targetFile) {
      this.showToast("Không tìm thấy tệp kết quả để đưa vào ToolVideo", "warning");
      return;
    }

    this.dispatchViaBackground(Actions.IMPORT_TO_STUDIO, {
      file_path: targetFile,
      video_id: this.video.videoId,
      request_id: this.activeJob.requestId,
      job_id: this.activeJob.jobId,
    });
    this.showToast("Đang đưa tệp vào ToolVideo...", "info");
  }

  getBasename(filePath) {
    if (!filePath) return "";
    const parts = filePath.split(/[\\/]/);
    return parts[parts.length - 1] || filePath;
  }

  // ==========================================================================
  // Native Bridge & Background Communication
  // ==========================================================================

  initChromeListeners() {
    if (typeof chrome === "undefined" || !chrome.runtime || !chrome.runtime.onMessage) {
      return;
    }

    chrome.runtime.onMessage.addListener((message) => {
      if (!message || !message.action) return;

      switch (message.action) {
        case Actions.STATUS_REPORT: {
          const connected = !!(message.payload && message.payload.browser_connected);
          this.updateConnectionStatus(connected);
          break;
        }

        case Actions.YOUTUBE_CONTEXT_SYNC: {
          if (
            !this.video.tabId ||
            !message.payload?.tabId ||
            message.payload.tabId === this.video.tabId
          ) {
            this.updateVideoContext(message.payload);
          }
          break;
        }

        case "YOUTUBE_ADAPTER_READY": {
          // Content script just finished init — update context and re-probe
          if (message.payload?.videoId) {
            this.updateVideoContext(message.payload);
            this.updateYouTubeStatus("connected", "YouTube: đã nhận video");
            this.hideYouTubeError();
          } else {
            this.scheduleActiveTabDetection(200);
          }
          break;
        }

        case "YOUTUBE_CLIP_ADDED": {
          this.addClipFromEvent(message.payload);
          break;
        }

        case Actions.CLIP_EXPORT_ACCEPTED: {
          this.handleExportAccepted(message.payload);
          break;
        }

        case Actions.CLIP_EXPORT_PROGRESS: {
          this.handleExportProgress(message.payload);
          break;
        }

        case Actions.CLIP_EXPORT_RESULT: {
          this.handleExportResult(message.payload);
          break;
        }

        case Actions.CLIP_EXPORT_ERROR: {
          this.handleExportError(message.payload);
          break;
        }

        case Actions.AGENT_STATUS: {
          this.connectionStatusFailures = 0;
          this.updateConnectionStatus(
            message.payload?.connected === true,
            message.payload?.transport || null
          );
          break;
        }

        case Actions.IMPORT_TO_STUDIO_RESULT: {
          if (message.payload?.success) {
            this.showToast("Đã đưa tệp vào ToolVideo!", "success");
          } else {
            this.showToast(
              message.payload?.error || "Không thể đưa tệp vào ToolVideo.",
              "error"
            );
          }
          break;
        }

        default:
          break;
      }
    });

    if (chrome.tabs) {
      chrome.tabs.onActivated.addListener(() => this.scheduleActiveTabDetection());
      chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
        if (
          tabId === this.video.tabId ||
          changeInfo.status === "complete" ||
          typeof changeInfo.url === "string"
        ) {
          this.scheduleActiveTabDetection();
        }
      });
    }

    // Query the worker directly instead of relying only on broadcast messages.
    // The direct response prevents a newly opened Side Panel from displaying a
    // stale disconnected state while the WebSocket is already established.
    this.refreshConnectionStatus();
    this.connectionStatusTimer = setInterval(() => this.refreshConnectionStatus(), 2000);
    window.addEventListener("unload", () => {
      if (this.connectionStatusTimer) clearInterval(this.connectionStatusTimer);
    }, { once: true });
  }

  async refreshConnectionStatus() {
    try {
      const response = await chrome.runtime.sendMessage({
        action: Actions.GET_STATUS,
        payload: { lightweight: true },
      });
      if (!response || typeof response.connected !== "boolean") {
        throw new Error("Service worker không trả trạng thái kết nối");
      }
      this.connectionStatusFailures = 0;
      this.updateConnectionStatus(response.connected, response.transport);
    } catch (_error) {
      this.connectionStatusFailures += 1;
      // Ignore one transient worker wake-up failure to avoid a flashing badge.
      if (this.connectionStatusFailures >= 2) {
        this.updateConnectionStatus(false);
      }
    }
  }

  updateConnectionStatus(connected, transport = null) {
    this.isConnected = connected;
    this.elements.statusBadge.className = `status-badge ${connected ? "connected" : "disconnected"}`;
    this.elements.statusLabel.textContent = connected
      ? "ToolVideo: đã kết nối"
      : "ToolVideo: chưa kết nối";
    this.elements.statusBadge.title = connected
      ? `Local Agent VK Dub Studio đang hoạt động${transport ? ` qua ${transport}` : ""}`
      : "Chưa kết nối với Local Agent VK Dub Studio";
  }

  // ==========================================================================
  // Dynamic Island Animated Toast
  // ==========================================================================

  showToast(message, type = "info", durationMs = 2400) {
    const container = this.elements.toastContainer;
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `apple-toast ${type}`;

    const iconSymbol = {
      success: "✓",
      warning: "⚠",
      error: "✕",
      info: "✦",
    }[type] || "✦";

    toast.innerHTML = `
      <span class="toast-icon">${iconSymbol}</span>
      <span class="toast-msg">${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(-6px) scale(0.95)";
      setTimeout(() => {
        if (toast.parentElement) toast.parentElement.removeChild(toast);
      }, 250);
    }, durationMs);
  }
}

// Instantiate and initialize on DOM readiness if running in browser
if (typeof document !== "undefined") {
  const bootSidePanel = () => {
    const app = new SidePanelApp();
    app.init();
    if (typeof window !== "undefined") {
      window.__vkdubSidePanelApp = app;
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootSidePanel);
  } else {
    bootSidePanel();
  }
}
