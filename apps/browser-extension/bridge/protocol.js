/**
 * VK Dub Studio — Browser Bridge Protocol
 * Shared message actions, error codes, and protocol constants.
 */

export const ProtocolVersion = "1.0.0";
export const NativeHostName = "com.vkdub.bridge";

export const Actions = {
  // Connection & Handshake
  PING: "PING",
  PONG: "PONG",
  HELLO: "HELLO",

  // Status & Telemetry
  GET_STATUS: "GET_STATUS",
  STATUS_REPORT: "STATUS_REPORT",
  GET_AGENT_STATUS: "GET_AGENT_STATUS",
  AGENT_STATUS: "AGENT_STATUS",
  RELOAD_EXTENSION: "RELOAD_EXTENSION",

  // Logging & Events
  LOG_EVENT: "LOG_EVENT",

  // ChatGPT & Vbee
  CHATGPT_TRANSLATE: "CHATGPT_TRANSLATE",
  CHATGPT_TRANSLATE_RESULT: "CHATGPT_TRANSLATE_RESULT",
  VBEE_GENERATE_VOICE: "VBEE_GENERATE_VOICE",
  VBEE_VOICE_RESULT: "VBEE_VOICE_RESULT",
  VBEE_PROGRESS: "VBEE_PROGRESS",

  // YouTube Clip Mode
  YOUTUBE_CONTEXT_SYNC: "YOUTUBE_CONTEXT_SYNC",
  YOUTUBE_SEEK_TO: "YOUTUBE_SEEK_TO",
  YOUTUBE_PREVIEW_CLIP: "YOUTUBE_PREVIEW_CLIP",
  ENSURE_YOUTUBE_ADAPTER: "ENSURE_YOUTUBE_ADAPTER",
  CLIP_EXPORT_REQUEST: "CLIP_EXPORT_REQUEST",
  CLIP_EXPORT_ACCEPTED: "CLIP_EXPORT_ACCEPTED",
  CLIP_EXPORT_PROGRESS: "CLIP_EXPORT_PROGRESS",
  CLIP_EXPORT_RESULT: "CLIP_EXPORT_RESULT",
  CLIP_EXPORT_ERROR: "CLIP_EXPORT_ERROR",
  CLIP_EXPORT_CANCEL: "CLIP_EXPORT_CANCEL",
  OPEN_OUTPUT_FOLDER: "OPEN_OUTPUT_FOLDER",
  IMPORT_TO_STUDIO: "IMPORT_TO_STUDIO",
  IMPORT_TO_STUDIO_RESULT: "IMPORT_TO_STUDIO_RESULT",
};

export const StatusFlags = {
  BROWSER_CONNECTED: "BROWSER_CONNECTED",
  CHATGPT_AVAILABLE: "CHATGPT_AVAILABLE",
  CHATGPT_LOGGED_IN: "CHATGPT_LOGGED_IN",
  VBEE_AVAILABLE: "VBEE_AVAILABLE",
  VBEE_LOGGED_IN: "VBEE_LOGGED_IN",
};

/**
 * Creates a standardized Status Report payload.
 */
export function createStatusReport({
  browserConnected = true,
  chatgptAvailable = false,
  chatgptLoggedIn = false,
  vbeeAvailable = false,
  vbeeLoggedIn = false,
  browserName = "Microsoft Edge",
  chatgptTabs = 0,
  vbeeTabs = 0,
  details = {},
} = {}) {
  return {
    action: Actions.STATUS_REPORT,
    version: ProtocolVersion,
    timestamp: Date.now(),
    payload: {
      browser_connected: browserConnected,
      chatgpt_available: chatgptAvailable,
      chatgpt_logged_in: chatgptLoggedIn,
      vbee_available: vbeeAvailable,
      vbee_logged_in: vbeeLoggedIn,
      browser_name: browserName,
      active_tabs: {
        chatgpt: chatgptTabs,
        vbee: vbeeTabs,
      },
      details,
    },
  };
}

export const ExportStage = {
  PROBING: "PROBING",
  CHECKING_SOURCE: "CHECKING_SOURCE",
  DOWNLOADING: "DOWNLOADING",
  REMUXING: "REMUXING",
  TRIMMING: "TRIMMING",
  MERGING: "MERGING",
  PIPELINE_FEED: "PIPELINE_FEED",
  COMPLETE: "COMPLETE",
  CANCELLED: "CANCELLED",
  ERROR: "ERROR",
};

export const ExportMode = {
  SEPARATE: "SEPARATE",
  MERGED: "MERGED",
  IMPORT: "IMPORT",
};

export const CutMode = {
  STREAM_COPY: "STREAM_COPY",
  FRAME_ACCURATE: "FRAME_ACCURATE",
};

/**
 * Creates a standardized YouTube Context Sync payload.
 */
export function createYouTubeContextSync({
  videoId = "",
  title = "",
  duration = 0,
  url = "",
  canonicalUrl = "",
  author = "",
  currentTime = 0,
  thumbnailUrl = "",
  tabId = null,
} = {}) {
  return {
    action: Actions.YOUTUBE_CONTEXT_SYNC,
    version: ProtocolVersion,
    timestamp: Date.now(),
    payload: {
      videoId,
      video_id: videoId,
      title,
      duration,
      url,
      canonicalUrl: canonicalUrl || url,
      canonical_url: canonicalUrl || url,
      author,
      currentTime,
      current_time: currentTime,
      thumbnailUrl,
      thumbnail_url: thumbnailUrl,
      tabId,
      tab_id: tabId,
      timestamp: Date.now(),
    },
  };
}

/**
 * Creates a YouTube Seek To action payload.
 */
export function createYouTubeSeekTo(seconds, play = true, tabId = null) {
  return {
    action: Actions.YOUTUBE_SEEK_TO,
    version: ProtocolVersion,
    timestamp: Date.now(),
    payload: {
      seconds,
      time: seconds,
      play,
      tabId,
      tab_id: tabId,
    },
  };
}

/**
 * Creates a YouTube Preview Clip action payload.
 */
export function createYouTubePreviewClip(start, end, loop = false, tabId = null) {
  return {
    action: Actions.YOUTUBE_PREVIEW_CLIP,
    version: ProtocolVersion,
    timestamp: Date.now(),
    payload: {
      start,
      end,
      loop,
      tabId,
      tab_id: tabId,
    },
  };
}

/**
 * Creates a Clip Export Request action payload.
 */
export function createClipExportRequest({
  requestId = "",
  jobId = "",
  videoId = "",
  videoUrl = "",
  videoTitle = "",
  duration = 0,
  clips = [],
  exportMode = ExportMode.SEPARATE,
  outputDir = "",
  container = "mp4",
  quality = "best",
  cutMode = CutMode.STREAM_COPY,
  useCookies = false,
  browser = "edge",
} = {}) {
  const reqId = requestId || `clip_export_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  return {
    action: Actions.CLIP_EXPORT_REQUEST,
    version: ProtocolVersion,
    timestamp: Date.now(),
    payload: {
      requestId: reqId,
      request_id: reqId,
      jobId: jobId || reqId,
      job_id: jobId || reqId,
      videoId,
      video_id: videoId,
      videoUrl,
      video_url: videoUrl,
      videoTitle,
      video_title: videoTitle,
      duration,
      clips,
      exportMode,
      export_mode: exportMode,
      outputDir,
      output_dir: outputDir,
      container,
      quality,
      cutMode,
      cut_mode: cutMode,
      useCookies,
      use_cookies: useCookies,
      browser,
      timestamp: Date.now(),
    },
  };
}

/**
 * Creates a Clip Export Cancel action payload.
 */
export function createClipExportCancel(requestId, jobId = "") {
  return {
    action: Actions.CLIP_EXPORT_CANCEL,
    version: ProtocolVersion,
    timestamp: Date.now(),
    payload: {
      requestId,
      request_id: requestId,
      jobId: jobId || requestId,
      job_id: jobId || requestId,
    },
  };
}

/**
 * Creates an Open Output Folder action payload.
 */
export function createOpenOutputFolder(folderPath) {
  return {
    action: Actions.OPEN_OUTPUT_FOLDER,
    version: ProtocolVersion,
    timestamp: Date.now(),
    payload: {
      path: folderPath,
      folder_path: folderPath,
    },
  };
}
