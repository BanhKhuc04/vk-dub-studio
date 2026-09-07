/**
 * VK Dub Studio — Background Service Worker
 * Manages Native Messaging bridge, monitors ChatGPT & Vbee tabs and cookies.
 */

import { NativeMessagingBridge } from "../bridge/nativeMessaging.js";
import { Actions, createStatusReport } from "../bridge/protocol.js";

const isEdge = navigator.userAgent.includes("Edg/");
const browserName = isEdge ? "Microsoft Edge" : "Google Chrome";

// State cache
const state = {
  chatgptAvailable: false,
  chatgptLoggedIn: false,
  vbeeAvailable: false,
  vbeeLoggedIn: false,
  chatgptTabs: 0,
  vbeeTabs: 0,
};

let bridge = null;

async function checkCookiesAuth() {
  let chatgptAuthFromCookie = false;
  let vbeeAuthFromCookie = false;

  try {
    const chatgptCookies = await chrome.cookies.getAll({ domain: "chatgpt.com" });
    chatgptAuthFromCookie = chatgptCookies.some(
      (c) =>
        c.name.includes("session-token") ||
        c.name.includes("auth") ||
        c.name === "__Secure-next-auth.session-token"
    );
  } catch (err) {
    console.debug("[SW] Error checking ChatGPT cookies:", err);
  }

  try {
    const vbeeCookies = await chrome.cookies.getAll({ domain: "vbee.vn" });
    vbeeAuthFromCookie = vbeeCookies.some(
      (c) =>
        c.name.toLowerCase().includes("token") ||
        c.name.toLowerCase().includes("session") ||
        c.name.toLowerCase().includes("auth") ||
        c.name === "accessToken" ||
        c.name === "jwt"
    );
  } catch (err) {
    console.debug("[SW] Error checking Vbee cookies:", err);
  }

  return { chatgptAuthFromCookie, vbeeAuthFromCookie };
}

async function refreshAllStatus() {
  // 1. Query ChatGPT tabs
  let chatgptTabs = [];
  try {
    chatgptTabs = await chrome.tabs.query({
      url: ["*://chatgpt.com/*", "*://*.chatgpt.com/*"],
    });
  } catch (e) {
    // ignore
  }

  // 2. Query Vbee tabs
  let vbeeTabs = [];
  try {
    vbeeTabs = await chrome.tabs.query({
      url: ["*://vbee.vn/*", "*://*.vbee.vn/*"],
    });
  } catch (e) {
    // ignore
  }

  state.chatgptTabs = chatgptTabs.length;
  state.vbeeTabs = vbeeTabs.length;
  state.chatgptAvailable = chatgptTabs.length > 0;
  state.vbeeAvailable = vbeeTabs.length > 0;

  // 3. Check Cookie authentication
  const { chatgptAuthFromCookie, vbeeAuthFromCookie } = await checkCookiesAuth();
  let chatgptLoggedIn = chatgptAuthFromCookie;
  let vbeeLoggedIn = vbeeAuthFromCookie;

  // 4. Query active content script if tabs are open for deeper DOM confirmation
  if (chatgptTabs.length > 0 && chatgptTabs[0].id) {
    try {
      const resp = await chrome.tabs.sendMessage(chatgptTabs[0].id, {
        action: "CHECK_CHATGPT_STATUS",
      });
      if (resp && typeof resp.logged_in === "boolean") {
        chatgptLoggedIn = resp.logged_in;
      }
    } catch (e) {
      // Content script may not be loaded yet or tab loading
    }
  }

  if (vbeeTabs.length > 0 && vbeeTabs[0].id) {
    try {
      const resp = await chrome.tabs.sendMessage(vbeeTabs[0].id, {
        action: "CHECK_VBEE_STATUS",
      });
      if (resp && typeof resp.logged_in === "boolean") {
        vbeeLoggedIn = resp.logged_in;
      }
    } catch (e) {
      // Content script may not be loaded yet
    }
  }

  state.chatgptLoggedIn = chatgptLoggedIn;
  state.vbeeLoggedIn = vbeeLoggedIn;

  return state;
}

async function sendStatusReport() {
  await refreshAllStatus();
  if (!bridge || !bridge.isConnected) return;

  const report = createStatusReport({
    browserConnected: true,
    chatgptAvailable: state.chatgptAvailable,
    chatgptLoggedIn: state.chatgptLoggedIn,
    vbeeAvailable: state.vbeeAvailable,
    vbeeLoggedIn: state.vbeeLoggedIn,
    browserName: browserName,
    chatgptTabs: state.chatgptTabs,
    vbeeTabs: state.vbeeTabs,
  });

  bridge.send(report);
}

function initBridge() {
  bridge = new NativeMessagingBridge({
    onConnect: () => {
      console.log("[SW] Native bridge connected! Sending initial status...");
      sendStatusReport();
    },
    onDisconnect: (err) => {
      console.warn("[SW] Native bridge disconnected:", err);
    },
    onMessage: async (msg) => {
      console.log("[SW] Received from Native Host:", msg);
      if (!msg || !msg.action) return;

      switch (msg.action) {
        case Actions.GET_STATUS:
          await sendStatusReport();
          break;
        case Actions.PING:
          bridge.send({ action: Actions.PONG, timestamp: Date.now() });
          break;
        default:
          console.warn("[SW] Unhandled action:", msg.action);
          break;
      }
    },
  });

  bridge.connect();
}

// Listen to content script notifications
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || !message.action) return;

  if (
    message.action === "CHATGPT_TAB_READY" ||
    message.action === "CHATGPT_STATUS_CHANGED" ||
    message.action === "VBEE_TAB_READY" ||
    message.action === "VBEE_STATUS_CHANGED"
  ) {
    sendStatusReport();
  }
});

// Listen to tab events to update availability
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.url) {
    if (tab.url.includes("chatgpt.com") || tab.url.includes("vbee.vn")) {
      sendStatusReport();
    }
  }
});

chrome.tabs.onRemoved.addListener(() => {
  sendStatusReport();
});

// Periodic status refresh (every 10 seconds)
setInterval(() => {
  if (bridge && bridge.isConnected) {
    sendStatusReport();
  }
}, 10000);

// Start bridge connection
initBridge();
