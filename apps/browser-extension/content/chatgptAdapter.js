/**
 * VK Dub Studio — ChatGPT Content Script Adapter (H6.1 Automation)
 *
 * Implements end-to-end automated SRT translation:
 * 1. Opens or focuses conversation.
 * 2. Injects prompt instructions and original SRT content.
 * 3. Submits prompt and waits for generation to complete.
 * 4. Extracts translated SRT code block from the response.
 * 5. Returns raw SRT text to background service worker.
 */

(function () {
  const CHATGPT_CHECK_ACTION = "CHECK_CHATGPT_STATUS";
  const CHATGPT_TRANSLATE_ACTION = "CHATGPT_TRANSLATE";

  function checkLoginState() {
    const hasPromptInput = !!(
      document.querySelector("#prompt-textarea") ||
      document.querySelector("textarea[placeholder*='Message']") ||
      document.querySelector("div[contenteditable='true'][id*='prompt']")
    );

    const hasUserMenu = !!(
      document.querySelector("[data-testid='user-menu-button']") ||
      document.querySelector("[data-testid*='profile']") ||
      document.querySelector("button[aria-label*='User']") ||
      document.querySelector("nav div[class*='avatar']")
    );

    const hasLoginButton = !!(
      document.querySelector("a[href*='/auth/login']") ||
      document.querySelector("button[data-testid='login-button']") ||
      Array.from(document.querySelectorAll("button, a")).some(
        (el) => el.textContent && el.textContent.trim() === "Log in"
      )
    );

    const isLoggedIn = (hasPromptInput || hasUserMenu) && !hasLoginButton;

    return {
      available: true,
      logged_in: isLoggedIn,
      has_input: hasPromptInput,
      has_user_menu: hasUserMenu,
      url: window.location.href,
      title: document.title,
    };
  }

  function findPromptInput() {
    return (
      document.querySelector("#prompt-textarea") ||
      document.querySelector("div[contenteditable='true'][id*='prompt']") ||
      document.querySelector("textarea[placeholder*='Message']") ||
      document.querySelector("div[contenteditable='true']")
    );
  }

  function findSendButton() {
    return (
      document.querySelector("button[data-testid='send-button']") ||
      document.querySelector("button[data-testid='fruitjuice-send-button']") ||
      document.querySelector("button[aria-label='Send prompt']") ||
      document.querySelector("button[aria-label='Gửi tin nhắn']") ||
      document.querySelector("form button:has(svg)")
    );
  }

  function isGenerating() {
    return !!(
      document.querySelector("button[data-testid='stop-button']") ||
      document.querySelector("button[aria-label='Stop streaming']") ||
      document.querySelector("button[aria-label='Dừng tạo']") ||
      document.querySelector(".result-streaming")
    );
  }

  function extractSRTFromResponses() {
    // Look at all assistant message containers
    const assistantMessages = Array.from(
      document.querySelectorAll("div[data-message-author-role='assistant'], article[data-testid*='conversation-turn']")
    );

    if (!assistantMessages.length) return null;
    const lastMessage = assistantMessages[assistantMessages.length - 1];

    // Priority 1: Check code blocks (pre code)
    const codeBlocks = Array.from(lastMessage.querySelectorAll("pre code, pre"));
    for (let i = codeBlocks.length - 1; i >= 0; i--) {
      const codeText = codeBlocks[i].innerText || codeBlocks[i].textContent || "";
      if (codeText.includes("-->") && /\d{1,2}:\d{2}:\d{2}/.test(codeText)) {
        return cleanSRTText(codeText);
      }
    }

    // Priority 2: Full message text if code block not used
    const fullText = lastMessage.innerText || lastMessage.textContent || "";
    if (fullText.includes("-->") && /\d{1,2}:\d{2}:\d{2}/.test(fullText)) {
      return cleanSRTText(fullText);
    }

    return null;
  }

  function cleanSRTText(text) {
    let cleaned = text.trim();
    // Remove markdown code fences if wrapped
    cleaned = cleaned.replace(/^```[a-zA-Z]*\n?/, "");
    cleaned = cleaned.replace(/\n?```$/, "");

    // Find the first cue index line (e.g. "1" followed by timecode)
    const firstCueMatch = cleaned.search(/(?:^|\n)\s*1\s*\n\s*\d{1,2}:\d{2}:\d{2}/);
    if (firstCueMatch !== -1) {
      cleaned = cleaned.substring(firstCueMatch).trim();
    }
    return cleaned;
  }

  async function executeTranslation({ srt_content, prompt_instruction, request_id }) {
    console.log("[ChatGPTAdapter] Executing translation for request:", request_id);

    // 1. Wait for input to be ready
    let inputEl = null;
    for (let i = 0; i < 30; i++) {
      inputEl = findPromptInput();
      if (inputEl) break;
      await new Promise((r) => setTimeout(r, 500));
    }

    if (!inputEl) {
      throw new Error("Không tìm thấy ô nhập tin nhắn trên giao diện ChatGPT.");
    }

    // 2. Build full prompt
    const defaultInstruction =
      "Dịch lại toàn bộ file phụ đề SRT này sang tiếng Việt:\n" +
      "- Sát nghĩa, đúng bối cảnh và cảm xúc nhân vật, văn phong tự nhiên.\n" +
      "- Giữ nguyên 100% định dạng SRT, số thứ tự từng câu và mốc thời gian (timecode).\n" +
      "- Không gộp câu, không tách câu, không bỏ sót bất kỳ dòng nào.\n" +
      "- Tuyệt đối không thay đổi hay làm lệch bất kỳ mốc thời gian nào.\n" +
      "- Xuất toàn bộ phụ đề SRT đã dịch đầy đủ trong một khối mã (code block ```srt).\n\n" +
      "--- NỘI DUNG PHỤ ĐỀ SRT GỐC ---\n" +
      srt_content +
      "\n--- HẾT ---";

    const promptText = prompt_instruction ? `${prompt_instruction}\n\n${srt_content}` : defaultInstruction;

    // 3. Inject text into input element
    inputEl.focus();
    if (inputEl.tagName.toLowerCase() === "textarea") {
      inputEl.value = promptText;
      inputEl.dispatchEvent(new Event("input", { bubbles: true }));
      inputEl.dispatchEvent(new Event("change", { bubbles: true }));
    } else {
      // Contenteditable div
      inputEl.innerText = promptText;
      inputEl.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText" }));
    }

    await new Promise((r) => setTimeout(r, 600));

    // 4. Click send button
    let sendBtn = null;
    for (let i = 0; i < 15; i++) {
      sendBtn = findSendButton();
      if (sendBtn && !sendBtn.disabled) break;
      await new Promise((r) => setTimeout(r, 400));
    }

    if (!sendBtn) {
      // Fallback: trigger Enter key
      inputEl.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", keyCode: 13, bubbles: true }));
    } else {
      sendBtn.click();
    }

    console.log("[ChatGPTAdapter] Prompt submitted. Waiting for generation to complete...");

    // 5. Wait for streaming to start then complete
    await new Promise((r) => setTimeout(r, 2500));

    const startTime = Date.now();
    const maxWaitMs = 360000; // 6 minutes max

    while (Date.now() - startTime < maxWaitMs) {
      const generating = isGenerating();
      if (!generating) {
        // Wait an extra 1.5s to ensure DOM finalized
        await new Promise((r) => setTimeout(r, 1500));
        if (!isGenerating()) {
          const srtResult = extractSRTFromResponses();
          if (srtResult && srtResult.includes("-->")) {
            console.log("[ChatGPTAdapter] Translation extracted successfully!");
            return {
              success: true,
              translated_srt: srtResult,
              request_id: request_id,
            };
          }
        }
      }
      await new Promise((r) => setTimeout(r, 1000));
    }

    throw new Error("Quá thời gian chờ phản hồi từ ChatGPT (hơn 6 phút).");
  }

  // Handle messages from service worker
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request && request.action === CHATGPT_CHECK_ACTION) {
      sendResponse(checkLoginState());
      return true;
    }

    if (request && request.action === CHATGPT_TRANSLATE_ACTION) {
      executeTranslation(request.payload || {})
        .then((result) => sendResponse(result))
        .catch((err) => sendResponse({ success: false, error: err.message, request_id: request.payload?.request_id }));
      return true; // Keep message channel open for async response
    }
  });

  // Notify service worker when tab loads
  try {
    chrome.runtime.sendMessage({
      action: "CHATGPT_TAB_READY",
      status: checkLoginState(),
    });
  } catch (err) {}
})();
