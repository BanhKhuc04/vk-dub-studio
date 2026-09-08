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
  RELOAD_EXTENSION: "RELOAD_EXTENSION",

  // Logging & Events
  LOG_EVENT: "LOG_EVENT",

  // Future H6.1 / H6.2 Placeholders
  CHATGPT_TRANSLATE: "CHATGPT_TRANSLATE",
  CHATGPT_TRANSLATE_RESULT: "CHATGPT_TRANSLATE_RESULT",
  VBEE_GENERATE_VOICE: "VBEE_GENERATE_VOICE",
  VBEE_VOICE_RESULT: "VBEE_VOICE_RESULT",
  VBEE_PROGRESS: "VBEE_PROGRESS",
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
