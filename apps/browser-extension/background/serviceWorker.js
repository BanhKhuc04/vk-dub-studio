/**
 * VK Dub Studio — Background Service Worker (H6.1 & H6.2 Router)
 *
 * Coordinates Native Messaging with ChatGPT & Vbee content script adapters.
 * Implements self-healing script injection, dynamic tab management, and streaming logs.
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
  chatgptAdapterReady: false,
  vbeeAdapterReady: false,
};

let bridge = null;

async function checkCookiesAuth() {
  let chatgptAuthFromCookie = false;
  let vbeeAuthFromCookie = false;

  try {
    const [c1, c2, c3] = await Promise.all([
      chrome.cookies.getAll({ url: "https://chatgpt.com" }).catch(() => []),
      chrome.cookies.getAll({ url: "https://chat.openai.com" }).catch(() => []),
      chrome.cookies.getAll({ domain: "chatgpt.com" }).catch(() => []),
    ]);
    const chatgptCookies = [...c1, ...c2, ...c3];
    chatgptAuthFromCookie = chatgptCookies.some(
      (c) =>
        c.name.includes("session-token") ||
        c.name.includes("auth") ||
        c.name.includes("token") ||
        c.name.includes("user") ||
        c.name === "__Secure-next-auth.session-token"
    );
  } catch (err) {}

  try {
    const [v1, v2, v3] = await Promise.all([
      chrome.cookies.getAll({ url: "https://vbee.vn" }).catch(() => []),
      chrome.cookies.getAll({ url: "https://studio.vbee.vn" }).catch(() => []),
      chrome.cookies.getAll({ domain: "vbee.vn" }).catch(() => []),
    ]);
    const vbeeCookies = [...v1, ...v2, ...v3];
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

function isChatGPTTab(t) {
  const u = (t.url || t.pendingUrl || "").toLowerCase();
  const title = (t.title || "").toLowerCase();
  return (
    u.includes("chatgpt.com") ||
    u.includes("chat.openai.com") ||
    (u.includes("edge://sleeping-tab") && u.includes("chatgpt")) ||
    title.includes("chatgpt")
  );
}

function isVbeeTab(t) {
  const u = (t.url || t.pendingUrl || "").toLowerCase();
  const title = (t.title || "").toLowerCase();
  return (
    u.includes("vbee.vn") ||
    u.includes("studio.vbee.vn") ||
    (u.includes("edge://sleeping-tab") && u.includes("vbee")) ||
    title.includes("vbee")
  );
}

async function refreshAllStatus() {
  let allTabs = [];
  try {
    allTabs = await chrome.tabs.query({});
  } catch (e) {
    console.warn("[SW] chrome.tabs.query failed:", e);
  }

  const chatgptTabs = allTabs.filter(isChatGPTTab);
  const vbeeTabs = allTabs.filter(isVbeeTab);

  state.chatgptTabs = chatgptTabs.length;
  state.vbeeTabs = vbeeTabs.length;
  state.chatgptAvailable = chatgptTabs.length > 0;
  state.vbeeAvailable = vbeeTabs.length > 0;

  const { chatgptAuthFromCookie, vbeeAuthFromCookie } = await checkCookiesAuth();
  let chatgptLoggedIn = chatgptAuthFromCookie;
  let vbeeLoggedIn = vbeeAuthFromCookie;

  let chatgptAdapterReady = false;
  for (const t of chatgptTabs) {
    if (!t.id) continue;
    try {
      const resp = await chrome.tabs.sendMessage(t.id, {
        action: "CHECK_CHATGPT_STATUS",
      });
      if (resp && typeof resp.logged_in === "boolean") {
        chatgptLoggedIn = resp.logged_in;
        chatgptAdapterReady = true;
        break;
      }
    } catch (e) {
      if (chrome.scripting) {
        try {
          await chrome.scripting.executeScript({
            target: { tabId: t.id },
            files: ["content/chatgptAdapter.js"],
          });
          const retry = await chrome.tabs.sendMessage(t.id, {
            action: "CHECK_CHATGPT_STATUS",
          });
          if (retry && typeof retry.logged_in === "boolean") {
            chatgptLoggedIn = retry.logged_in;
            chatgptAdapterReady = true;
            break;
          }
        } catch (e2) {}
      }
    }
  }

  // Heuristic: If ChatGPT tab is open and URL is not login page, assume logged in
  if (!chatgptLoggedIn && chatgptTabs.length > 0) {
    const u = (chatgptTabs[0].url || "").toLowerCase();
    if (!u.includes("/auth/login") && !u.includes("/login")) {
      chatgptLoggedIn = true;
    }
  }

  let vbeeAdapterReady = false;
  for (const t of vbeeTabs) {
    if (!t.id) continue;
    try {
      const resp = await chrome.tabs.sendMessage(t.id, {
        action: "CHECK_VBEE_STATUS",
      });
      if (resp && typeof resp.logged_in === "boolean") {
        vbeeLoggedIn = resp.logged_in;
        vbeeAdapterReady = true;
        break;
      }
    } catch (e) {
      if (chrome.scripting) {
        try {
          await chrome.scripting.executeScript({
            target: { tabId: t.id },
            files: ["content/vbeeAdapter.js"],
          });
          const retry = await chrome.tabs.sendMessage(t.id, {
            action: "CHECK_VBEE_STATUS",
          });
          if (retry && typeof retry.logged_in === "boolean") {
            vbeeLoggedIn = retry.logged_in;
            vbeeAdapterReady = true;
            break;
          }
        } catch (e2) {}
      }
    }
  }

  // Heuristic: If studio.vbee.vn is open, assume logged in
  if (!vbeeLoggedIn && vbeeTabs.length > 0) {
    const u = (vbeeTabs[0].url || "").toLowerCase();
    if (u.includes("studio.vbee.vn") || (vbeeAuthFromCookie && !u.includes("/login"))) {
      vbeeLoggedIn = true;
    }
  }

  state.chatgptLoggedIn = chatgptLoggedIn;
  state.vbeeLoggedIn = vbeeLoggedIn;
  state.chatgptAdapterReady = chatgptAdapterReady;
  state.vbeeAdapterReady = vbeeAdapterReady;
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
    details: {
      chatgpt_adapter_ready: state.chatgptAdapterReady,
      vbee_adapter_ready: state.vbeeAdapterReady,
    },
  });

  bridge.send(report);
}

async function findMatchingTab(urlPatterns, domainKeywords = []) {
  try {
    const matched = await chrome.tabs.query({ url: urlPatterns });
    if (matched.length > 0 && matched[0].id) return matched[0];
  } catch (e) {}

  try {
    const allTabs = await chrome.tabs.query({});
    for (const t of allTabs) {
      const u = (t.url || t.pendingUrl || "").toLowerCase();
      for (const kw of domainKeywords) {
        if (u.includes(kw)) return t;
      }
    }
  } catch (e) {}

  return null;
}

async function createTabSafely(targetUrl) {
  let targetWindow = null;
  try {
    targetWindow = await chrome.windows.getLastFocused({ populate: false });
  } catch (e) {}

  if (!targetWindow || targetWindow.id === chrome.windows.WINDOW_ID_NONE) {
    try {
      const wins = await chrome.windows.getAll({ windowTypes: ["normal"] });
      if (wins.length > 0) {
        targetWindow = wins[0];
      }
    } catch (e) {}
  }

  if (targetWindow && targetWindow.id && targetWindow.id !== chrome.windows.WINDOW_ID_NONE) {
    try {
      return await chrome.tabs.create({ windowId: targetWindow.id, url: targetUrl });
    } catch (createErr) {
      console.warn("[SW] tabs.create with windowId failed, falling back to windows.create:", createErr);
    }
  }

  // Fallback: create a new browser window with targetUrl
  const win = await chrome.windows.create({ url: targetUrl, focused: true });
  if (win.tabs && win.tabs.length > 0) {
    return win.tabs[0];
  }
  const createdTabs = await chrome.tabs.query({ windowId: win.id });
  return createdTabs[0];
}

async function getOrOpenTab(urlPatterns, targetUrl, domainKeywords = []) {
  const existingTab = await findMatchingTab(urlPatterns, domainKeywords);
  if (existingTab && existingTab.id) {
    try {
      await chrome.tabs.update(existingTab.id, { active: true });
      if (existingTab.windowId && existingTab.windowId !== chrome.windows.WINDOW_ID_NONE) {
        await chrome.windows.update(existingTab.windowId, { focused: true }).catch(() => {});
      }
    } catch (e) {}
    return existingTab;
  }

  const newTab = await createTabSafely(targetUrl);
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
  await new Promise((r) => setTimeout(r, 1200));
  return newTab;
}

async function ensureInjected(tabId, scriptPath) {
  if (chrome.scripting) {
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: [scriptPath],
      });
      await new Promise((r) => setTimeout(r, 500));
      return true;
    } catch (e) {
      console.warn(`[SW] Script execution warning on tab ${tabId}:`, e);
    }
  }
  return false;
}

async function waitForVbeeDownload(jobName, startedAtMs, timeoutMs = 45000) {
  if (!chrome.downloads || !jobName) return null;
  const jobKey = String(jobName).toLowerCase().replace(/[^a-z0-9]/g, "");
  const deadline = Date.now() + timeoutMs;
  let latest = null;
  while (Date.now() < deadline) {
    const items = await chrome.downloads.search({
      startedAfter: new Date(startedAtMs - 2000).toISOString(),
    });
    const matches = items
      .filter((item) =>
        String(item.filename || "")
          .toLowerCase()
          .replace(/[^a-z0-9]/g, "")
          .includes(jobKey)
      )
      .sort((a, b) => (b.startTime || "").localeCompare(a.startTime || ""));
    if (matches.length) {
      latest = matches[0];
      if (latest.state === "complete" || latest.state === "interrupted") break;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  if (!latest) return null;
  return {
    filename: latest.filename || null,
    state: latest.state || "unknown",
    bytes_received: latest.bytesReceived || 0,
    total_bytes: latest.totalBytes || 0,
    error: latest.error || null,
  };
}

async function handleChatGPTTranslate(payload) {
  try {
    const tab = await getOrOpenTab(
      [
        "*://chatgpt.com/*",
        "*://*.chatgpt.com/*",
        "*://chat.openai.com/*",
        "*://*.openai.com/*",
      ],
      "https://chatgpt.com",
      ["chatgpt.com", "openai.com"]
    );

    // Self-healing: inject adapter directly into the tab
    await ensureInjected(tab.id, "content/chatgptAdapter.js");

    let ack;
    try {
      ack = await chrome.tabs.sendMessage(tab.id, {
        action: "CHATGPT_TRANSLATE",
        payload,
      });
    } catch (msgErr) {
      console.warn("[SW] First sendMessage failed, re-injecting chatgptAdapter.js...", msgErr);
      await ensureInjected(tab.id, "content/chatgptAdapter.js");
      ack = await chrome.tabs.sendMessage(tab.id, {
        action: "CHATGPT_TRANSLATE",
        payload,
      });
    }

    if (!ack || ack.status !== "STARTED") {
      throw new Error("ChatGPT tab không xác nhận đã bắt đầu xử lý.");
    }
    // Kết quả thật sự tới sau (có thể vài phút) qua message "CHATGPT_TRANSLATE_DONE"
    // được xử lý trong listener chrome.runtime.onMessage ở cuối file — không giữ
    // kênh sendMessage này mở, vì Chrome/Edge tự đóng kênh bất đồng bộ sau ~5 phút.
  } catch (err) {
    console.error("[SW] Error in handleChatGPTTranslate:", err);
    bridge.send({
      action: Actions.CHATGPT_TRANSLATE_RESULT,
      payload: {
        success: false,
        error: `ChatGPT: ${err.message}`,
        request_id: payload?.request_id,
      },
    });
  }
}

// request_id -> thời điểm bắt đầu, dùng để lọc đúng download khi kết quả
// VBEE_GENERATE_DONE tới muộn (không còn nằm trong closure của handleVbeeGenerate).
const vbeeStartedAt = new Map();
const vbeeWakeIntervals = new Map();

async function handleVbeeGenerate(payload) {
  try {
    const startedAtMs = Date.now();
    if (payload?.request_id) {
      vbeeStartedAt.set(payload.request_id, startedAtMs);
    }
    const tab = await getOrOpenTab(
      [
        "*://studio.vbee.vn/*dubbing*",
        "*://studio.vbee.vn/*",
        "*://vbee.vn/*",
        "*://*.vbee.vn/*",
      ],
      "https://studio.vbee.vn/studio/dubbing",
      ["studio.vbee.vn", "vbee.vn"]
    );

    if (!tab.url || !tab.url.includes("/dubbing")) {
      console.log(`[SW] Navigating tab ${tab.id} to /studio/dubbing...`);
      await chrome.tabs.update(tab.id, { url: "https://studio.vbee.vn/studio/dubbing" });
      await new Promise((resolve) => {
        const listener = (tabId, info) => {
          if (tabId === tab.id && info.status === "complete") {
            chrome.tabs.onUpdated.removeListener(listener);
            resolve();
          }
        };
        chrome.tabs.onUpdated.addListener(listener);
        setTimeout(resolve, 8000);
      });
      await new Promise((r) => setTimeout(r, 2000));
    }

    // Self-healing: inject adapter directly into the tab
    await ensureInjected(tab.id, "content/vbeeAdapter.js");

    let ack;
    try {
      ack = await chrome.tabs.sendMessage(tab.id, {
        action: "VBEE_GENERATE_VOICE",
        payload,
      });
    } catch (msgErr) {
      console.warn("[SW] First sendMessage to Vbee failed, re-injecting vbeeAdapter.js...", msgErr);
      await ensureInjected(tab.id, "content/vbeeAdapter.js");
      ack = await chrome.tabs.sendMessage(tab.id, {
        action: "VBEE_GENERATE_VOICE",
        payload,
      });
    }

    if (!ack || ack.status !== "STARTED") {
      throw new Error("Vbee adapter không xác nhận đã bắt đầu xử lý.");
    }

    // Không ép giật active tab liên tục để người dùng yên tâm làm việc khác.
    // VbeeAdapter truy vấn trực tiếp qua API nền nên không cần tab phải active.
    // Kết quả thật sự tới sau (có thể tới 10 phút) qua message "VBEE_GENERATE_DONE"
    // được xử lý trong listener chrome.runtime.onMessage ở cuối file.
  } catch (err) {
    console.error("[SW] Error in handleVbeeGenerate:", err);
    if (payload?.request_id) {
      vbeeStartedAt.delete(payload.request_id);
    }
    bridge.send({
      action: Actions.VBEE_VOICE_RESULT,
      payload: {
        success: false,
        error: `Vbee: ${err.message}`,
        request_id: payload?.request_id,
      },
    });
  }
}

async function finalizeVbeeResult(resp) {
  const requestId = resp?.request_id;
  const startedAtMs = (requestId && vbeeStartedAt.get(requestId)) || Date.now() - 5000;
  if (requestId) {
    vbeeStartedAt.delete(requestId);
    if (vbeeWakeIntervals.has(requestId)) {
      clearInterval(vbeeWakeIntervals.get(requestId));
      vbeeWakeIntervals.delete(requestId);
    }
  }

  if (resp?.download_triggered) {
    const download = await waitForVbeeDownload(resp.job_name, startedAtMs);
    resp = {
      ...resp,
      download_path: download?.filename || null,
      download_state: download?.state || "not_found",
      download_bytes: download?.bytes_received || 0,
      download_error: download?.error || null,
    };
  }

  if (resp?.success && !resp.audio_base64 && !resp.audio_url && !resp.download_triggered) {
    resp = {
      ...resp,
      success: false,
      error: "Vbee adapter báo thành công nhưng không cung cấp audio hoặc sự kiện tải file.",
    };
  }

  bridge.send({ action: Actions.VBEE_VOICE_RESULT, payload: resp });
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
        case Actions.RELOAD_EXTENSION:
          console.log("[SW] Reloading extension on request...");
          try {
            chrome.runtime.reload();
          } catch (e) {
            console.warn("[SW] Reload failed:", e);
          }
          break;
      }
    },
  });

  bridge.connect();
}

chrome.runtime.onMessage.addListener((message) => {
  if (message?.action === "CHATGPT_TRANSLATE_DONE") {
    bridge.send({ action: Actions.CHATGPT_TRANSLATE_RESULT, payload: message.payload });
    return;
  }

  if (message?.action === "VBEE_GENERATE_DONE") {
    const resp = message.payload;
    finalizeVbeeResult(resp).catch((err) => {
      console.error("[SW] Error finalizing Vbee result:", err);
      bridge.send({
        action: Actions.VBEE_VOICE_RESULT,
        payload: { success: false, error: `Vbee: ${err.message}`, request_id: resp?.request_id },
      });
    });
    return;
  }

  if (message?.action === "VBEE_PROGRESS" && bridge && bridge.isConnected) {
    bridge.send({
      action: Actions.VBEE_PROGRESS,
      payload: {
        progress: message.progress,
        message: message.message,
        request_id: message.request_id,
      },
    });
    return;
  }

  if (message?.action === "CHATGPT_PROGRESS" && bridge && bridge.isConnected) {
    bridge.send({
      action: "CHATGPT_PROGRESS",
      payload: {
        cue_count: message.cue_count,
        total_cues: message.total_cues,
        progress: message.progress,
        message: message.message,
        request_id: message.request_id,
      },
    });
    return;
  }

  if (message?.action === "WAKE_VBEE_TAB") {
    // Không ép cửa sổ nhảy lên đè màn hình người dùng
    chrome.tabs.query({}).then((allTabs) => {
      const vbeeTab = allTabs.find(isVbeeTab);
      if (vbeeTab && vbeeTab.id) {
        chrome.tabs.update(vbeeTab.id, { active: true }).catch(() => {});
      }
    }).catch(() => {});
    return;
  }

  if (message?.action === "LOG_EVENT" && bridge && bridge.isConnected) {
    bridge.send({
      action: Actions.LOG_EVENT,
      payload: { message: message.message },
    });
    return;
  }

  if (
    message?.action === "CHATGPT_TAB_READY" ||
    message?.action === "CHATGPT_STATUS_CHANGED" ||
    message?.action === "VBEE_TAB_READY" ||
    message?.action === "VBEE_STATUS_CHANGED"
  ) {
    sendStatusReport();
  }
});

chrome.tabs.onActivated.addListener(() => {
  sendStatusReport();
});

chrome.tabs.onUpdated.addListener(() => {
  sendStatusReport();
});

chrome.tabs.onRemoved.addListener(() => {
  sendStatusReport();
});

setInterval(() => {
  if (bridge && bridge.isConnected) {
    sendStatusReport();
  }
}, 3000);

initBridge();
