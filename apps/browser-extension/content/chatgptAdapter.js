/**
 * VK Dub Studio — ChatGPT Content Script Adapter (H6.1 Automation)
 *
 * Implements end-to-end automated SRT translation:
 * 1. Verifies input field in conversation.
 * 2. Injects prompt instructions and original SRT content with modern React/Lexical support.
 * 3. Submits prompt and waits for streaming to complete.
 * 4. Extracts translated SRT code block from the response.
 * 5. Returns raw SRT text to background service worker.
 */

(function () {
  const CHATGPT_CHECK_ACTION = "CHECK_CHATGPT_STATUS";
  const CHATGPT_TRANSLATE_ACTION = "CHATGPT_TRANSLATE";

  function checkLoginState() {
    const hasPromptInput = !!findPromptInput();

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
      version: "2.2.0",
      has_input: hasPromptInput,
      has_user_menu: hasUserMenu,
      url: window.location.href,
      title: document.title,
    };
  }

  function findPromptInput() {
    return (
      document.querySelector("#prompt-textarea") ||
      document.querySelector("div[placeholder*='Ask ChatGPT'], div[placeholder*='Hỏi ChatGPT'], [data-placeholder*='Ask ChatGPT'], [data-placeholder*='Hỏi ChatGPT']") ||
      document.querySelector("div[contenteditable='true'][id*='prompt']") ||
      document.querySelector("div[contenteditable='true']") ||
      document.querySelector("textarea[placeholder*='Message']") ||
      document.querySelector("textarea")
    );
  }

  function findSendButton() {
    return (
      document.querySelector("button[data-testid='send-button']") ||
      document.querySelector("button[data-testid='fruitjuice-send-button']") ||
      document.querySelector("button[aria-label='Send prompt']") ||
      document.querySelector("button[aria-label='Gửi tin nhắn']") ||
      document.querySelector("button[aria-label*='Send']") ||
      document.querySelector("button[aria-label*='Gửi']") ||
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

  function insertPromptText(inputEl, promptText) {
    inputEl.focus();

    // Strategy 1: document.execCommand (optimal for ProseMirror/Lexical contenteditable)
    let execSuccess = false;
    try {
      if (inputEl.isContentEditable) {
        const sel = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(inputEl);
        sel.removeAllRanges();
        sel.addRange(range);
        execSuccess = document.execCommand("insertText", false, promptText);
      }
    } catch (e) {
      console.warn("[ChatGPTAdapter] execCommand error:", e);
    }

    if (!execSuccess) {
      if (inputEl.tagName && inputEl.tagName.toLowerCase() === "textarea") {
        try {
          const setter = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype,
            "value"
          )?.set;
          if (setter) {
            setter.call(inputEl, promptText);
          } else {
            inputEl.value = promptText;
          }
        } catch (e) {
          inputEl.value = promptText;
        }
        inputEl.dispatchEvent(new Event("input", { bubbles: true }));
        inputEl.dispatchEvent(new Event("change", { bubbles: true }));
      } else {
        // Fallback for contenteditable div
        inputEl.innerText = promptText;
        inputEl.dispatchEvent(
          new InputEvent("input", {
            bubbles: true,
            cancelable: true,
            inputType: "insertText",
            data: promptText,
          })
        );
      }
    }
  }

  function extractSRTFromResponses() {
    // Look at all assistant message containers
    const assistantMessages = Array.from(
      document.querySelectorAll(
        "div[data-message-author-role='assistant'], article[data-testid*='conversation-turn']"
      )
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

    // Priority 2: Full message text if code block was not formatted by AI
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

    try {
      chrome.runtime.sendMessage({
        action: "LOG_EVENT",
        message: "ChatGPT: Đang chuẩn bị gửi kịch bản vào ô nhập liệu...",
      });
    } catch (e) {}

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

    const promptText = prompt_instruction
      ? `${prompt_instruction}\n\n${srt_content}`
      : defaultInstruction;

    // Record assistant message count prior to sending new prompt
    const initialAssistantCount = document.querySelectorAll(
      "div[data-message-author-role='assistant'], article[data-testid*='conversation-turn']"
    ).length;

    // 3. Inject text into input element
    insertPromptText(inputEl, promptText);
    await new Promise((r) => setTimeout(r, 800));

    // 4. Click send button
    let sendBtn = null;
    for (let i = 0; i < 20; i++) {
      sendBtn = findSendButton();
      if (sendBtn && !sendBtn.disabled) break;
      inputEl.dispatchEvent(new Event("input", { bubbles: true }));
      await new Promise((r) => setTimeout(r, 300));
    }

    if (sendBtn && !sendBtn.disabled) {
      sendBtn.click();
    } else {
      // Fallback: trigger Enter key
      inputEl.focus();
      inputEl.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "Enter",
          code: "Enter",
          keyCode: 13,
          bubbles: true,
        })
      );
      inputEl.dispatchEvent(
        new KeyboardEvent("keyup", {
          key: "Enter",
          code: "Enter",
          keyCode: 13,
          bubbles: true,
        })
      );
      if (sendBtn) {
        try {
          sendBtn.click();
        } catch (e) {}
      }
    }

    console.log("[ChatGPTAdapter] Prompt submitted. Waiting for generation to begin...");
    try {
      chrome.runtime.sendMessage({
        action: "LOG_EVENT",
        message: "ChatGPT: Đã gửi kịch bản sang AI. Đang chờ AI bắt đầu phản hồi...",
      });
    } catch (e) {}

    // 5. Wait for streaming to begin
    let hasStarted = false;
    const waitStart = Date.now();
    while (Date.now() - waitStart < 15000) {
      const currentAssistantCount = document.querySelectorAll(
        "div[data-message-author-role='assistant'], article[data-testid*='conversation-turn']"
      ).length;
      if (isGenerating() || currentAssistantCount > initialAssistantCount) {
        hasStarted = true;
        break;
      }
      await new Promise((r) => setTimeout(r, 400));
    }

    const startTime = Date.now();
    const maxWaitMs = 360000; // 6 minutes max
    let lastLogTime = 0;

    while (Date.now() - startTime < maxWaitMs) {
      const bodyText = document.body.innerText || "";
      if (
        /reached the limit|đã đạt giới hạn|try again later|limit of messages|you've hit the message limit/i.test(
          bodyText
        )
      ) {
        throw new Error(
          "Tài khoản ChatGPT đã đạt giới hạn số tin nhắn. Vui lòng thử lại sau hoặc đổi tài khoản."
        );
      }

      const generating = isGenerating();
      const now = Date.now();

      if (now - lastLogTime > 3000) {
        lastLogTime = now;
        try {
          const srtCurrent = extractSRTFromResponses();
          const cueCount = srtCurrent ? (srtCurrent.match(/-->/g) || []).length : 0;
          if (cueCount > 0) {
            chrome.runtime.sendMessage({
              action: "LOG_EVENT",
              message: `ChatGPT: Đang sinh bản dịch (đã dịch ${cueCount} câu)...`,
            });
          } else {
            chrome.runtime.sendMessage({
              action: "LOG_EVENT",
              message: "ChatGPT: Đang xử lý nội dung dịch ngữ cảnh...",
            });
          }
        } catch (e) {}
      }

      if (!generating && (hasStarted || (Date.now() - startTime > 4000))) {
        // Wait an extra 1.5s to ensure DOM finalized
        await new Promise((r) => setTimeout(r, 1500));
        if (!isGenerating()) {
          const assistantMessages = Array.from(
            document.querySelectorAll(
              "div[data-message-author-role='assistant'], article[data-testid*='conversation-turn']"
            )
          );
          if (assistantMessages.length > initialAssistantCount || initialAssistantCount === 0) {
            const srtResult = extractSRTFromResponses();
            if (srtResult && srtResult.includes("-->")) {
              console.log("[ChatGPTAdapter] Translation extracted successfully!");
              const totalCues = (srtResult.match(/-->/g) || []).length;
              try {
                chrome.runtime.sendMessage({
                  action: "LOG_EVENT",
                  message: `ChatGPT: Đã hoàn tất tạo bản dịch (${totalCues} câu)! Đang gửi dữ liệu về VK Dub Studio...`,
                });
              } catch (e) {}
              return {
                success: true,
                translated_srt: srtResult,
                request_id: request_id,
              };
            }
          }
        }
      }
      await new Promise((r) => setTimeout(r, 1000));
    }

    throw new Error("Quá thời gian chờ phản hồi từ ChatGPT (hơn 6 phút).");
  }

  // Clear previous message listener to avoid duplicates
  if (window.__chatgptListener) {
    try {
      chrome.runtime.onMessage.removeListener(window.__chatgptListener);
    } catch (e) {}
  }

  // Handle messages from service worker
  window.__chatgptListener = (request, sender, sendResponse) => {
    if (request && request.action === CHATGPT_CHECK_ACTION) {
      sendResponse(checkLoginState());
      return true;
    }

    if (request && request.action === CHATGPT_TRANSLATE_ACTION) {
      // Trả lời NGAY để đóng kênh message trong <1s. Dịch có thể chạy tới vài
      // phút, và Chrome/Edge tự đóng kênh message bất đồng bộ sau ~5 phút —
      // nếu giữ kênh mở tới lúc dịch xong sẽ mất kết quả giữa chừng.
      sendResponse({ status: "STARTED", request_id: request.payload?.request_id });

      executeTranslation(request.payload || {})
        .then((result) => {
          chrome.runtime.sendMessage({ action: "CHATGPT_TRANSLATE_DONE", payload: result });
        })
        .catch((err) => {
          chrome.runtime.sendMessage({
            action: "CHATGPT_TRANSLATE_DONE",
            payload: {
              success: false,
              error: err.message,
              request_id: request.payload?.request_id,
            },
          });
        });
      return true;
    }
  };
  chrome.runtime.onMessage.addListener(window.__chatgptListener);

  // Notify service worker when tab loads
  try {
    chrome.runtime.sendMessage({
      action: "CHATGPT_TAB_READY",
      status: checkLoginState(),
    });
  } catch (err) {}
})();
