/**
 * VK Dub Studio — Background Service Worker (H6.1 & H6.2 Router)
 *
 * Coordinates Native Messaging with ChatGPT & Vbee content script adapters.
 */

import { NativeMessagingBridge } from "../bridge/nativeMessaging.js";
import { Actions, createStatusReport } from "../bridge/protocol.js";

const isEdge = navigator.userAgent.includes("Edg/");
const browserName = isEdge ? "Microsoft Edge" : "Google Chrome";

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
  } catch (err) {}

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
  } catch (err) {}

  return { chatgptAuthFromCookie, vbeeAuthFromCookie };
}

async function refreshAllStatus() {
  let chatgptTabs = [];
  try {
    chatgptTabs = await chrome.tabs.query({
      url: ["*://chatgpt.com/*", "*://*.chatgpt.com/*"],
    });
  } catch (e) {}

  let vbeeTabs = [];
  try {
    vbeeTabs = await chrome.tabs.query({
      url: ["*://vbee.vn/*", "*://*.vbee.vn/*"],
    });
  } catch (e) {}

  state.chatgptTabs = chatgptTabs.length;
  state.vbeeTabs = vbeeTabs.length;
  state.chatgptAvailable = chatgptTabs.length > 0;
  state.vbeeAvailable = vbeeTabs.length > 0;

  const { chatgptAuthFromCookie, vbeeAuthFromCookie } = await checkCookiesAuth();
  let chatgptLoggedIn = chatgptAuthFromCookie;
  let vbeeLoggedIn = vbeeAuthFromCookie;

  if (chatgptTabs.length > 0 && chatgptTabs[0].id) {
    try {
      const resp = await chrome.tabs.sendMessage(chatgptTabs[0].id, {
        action: "CHECK_CHATGPT_STATUS",
      });
      if (resp && typeof resp.logged_in === "boolean") {
        chatgptLoggedIn = resp.logged_in;
      }
    } catch (e) {}
  }

  if (vbeeTabs.length > 0 && vbeeTabs[0].id) {
    try {
      const resp = await chrome.tabs.sendMessage(vbeeTabs[0].id, {
        action: "CHECK_VBEE_STATUS",
      });
      if (resp && typeof resp.logged_in === "boolean") {
        vbeeLoggedIn = resp.logged_in;
      }
    } catch (e) {}
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

async function getOrOpenTab(urlPatterns, targetUrl) {
  const tabs = await chrome.tabs.query({ url: urlPatterns });
  if (tabs.length > 0 && tabs[0].id) {
    await chrome.tabs.update(tabs[0].id, { active: true });
    return tabs[0];
  }
  const newTab = await chrome.tabs.create({ url: targetUrl });
  // Wait for tab to load
  await new Promise((resolve) => {
    const listener = (tabId, info) => {
      if (tabId === newTab.id && info.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    };
    chrome.tabs.onUpdated.addListener(listener);
    setTimeout(resolve, 8000); // 8s safety timeout
  });
  // Extra wait for content script injection
  await new Promise((r) => setTimeout(r, 1500));
  return newTab;
}

async function handleChatGPTTranslate(payload) {
  try {
    const tab = await getOrOpenTab(
      ["*://chatgpt.com/*", "*://*.chatgpt.com/*"],
      "https://chatgpt.com"
    );
    const resp = await chrome.tabs.sendMessage(tab.id, {
      action: "CHATGPT_TRANSLATE",
      payload,
    });
    bridge.send({
      action: Actions.CHATGPT_TRANSLATE_RESULT,
      payload: resp,
    });
  } catch (err) {
    bridge.send({
      action: Actions.CHATGPT_TRANSLATE_RESULT,
      payload: {
        success: false,
        error: err.message,
        request_id: payload?.request_id,
      },
    });
  }
}

async function handleVbeeGenerate(payload) {
  try {
    const tab = await getOrOpenTab(
      ["*://studio.vbee.vn/*", "*://vbee.vn/*"],
      "https://studio.vbee.vn/studio/dubbing"
    );
    const resp = await chrome.tabs.sendMessage(tab.id, {
      action: "VBEE_GENERATE_VOICE",
      payload,
    });
    bridge.send({
      action: Actions.VBEE_VOICE_RESULT,
      payload: resp,
    });
  } catch (err) {
    bridge.send({
      action: Actions.VBEE_VOICE_RESULT,
      payload: {
        success: false,
        error: err.message,
        request_id: payload?.request_id,
      },
    });
  }
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
      console.log("[SW] Received action from Native Host:", msg?.action);
      if (!msg || !msg.action) return;

      switch (msg.action) {
        case Actions.GET_STATUS:
          await sendStatusReport();
          break;
        case Actions.CHATGPT_TRANSLATE:
          await handleChatGPTTranslate(msg.payload || {});
          break;
        case Actions.VBEE_GENERATE_VOICE:
          await handleVbeeGenerate(msg.payload || {});
          break;
        case Actions.PING:
          bridge.send({ action: Actions.PONG, timestamp: Date.now() });
          break;
      }
    },
  });

  bridge.connect();
}

chrome.runtime.onMessage.addListener((message) => {
  if (
    message?.action === "CHATGPT_TAB_READY" ||
    message?.action === "CHATGPT_STATUS_CHANGED" ||
    message?.action === "VBEE_TAB_READY" ||
    message?.action === "VBEE_STATUS_CHANGED"
  ) {
    sendStatusReport();
  }
});

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

setInterval(() => {
  if (bridge && bridge.isConnected) {
    sendStatusReport();
  }
}, 10000);

initBridge();
