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

    // Priority 1: Check code blocks (pre code, pre)
    const codeBlocks = Array.from(lastMessage.querySelectorAll("pre code, pre"));
    const validSrtParts = [];
    for (const block of codeBlocks) {
      const codeText = block.innerText || block.textContent || "";
      if (codeText.includes("-->") && /\d{1,2}:\d{2}:\d{2}/.test(codeText)) {
        const cleaned = cleanSRTText(codeText);
        if (cleaned) {
          validSrtParts.push(cleaned);
        }
      }
    }

    if (validSrtParts.length > 0) {
      // If AI continued generation across multiple code blocks, join them
      return validSrtParts.join("\n\n");
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

  async function findChatGPTFileInput() {
    // Check if input[type='file'] already exists in DOM
    let fileInput = document.querySelector("input[type='file']");
    if (fileInput) return fileInput;

    // Try finding the attach button (plus / paperclip / upload)
    const attachBtn = (
      document.querySelector("button[data-testid='attach-button']") ||
      document.querySelector("button[aria-label*='Attach']") ||
      document.querySelector("button[aria-label*='Đính kèm']") ||
      document.querySelector("button[aria-label*='Tệp đính kèm']") ||
      document.querySelector("button[aria-label*='Upload']") ||
      document.querySelector("form button:has(svg path[d*='M16.5'])") ||
      document.querySelector("form button:has(svg path[d*='M12'])") ||
      document.querySelector("form button[aria-haspopup]")
    );

    if (attachBtn) {
      try {
        attachBtn.click();
        await new Promise((r) => setTimeout(r, 400));
        fileInput = document.querySelector("input[type='file']");
        if (fileInput) return fileInput;

        // Check for menu item 'Upload from computer' / 'Tải lên từ máy tính'
        const menuItems = Array.from(
          document.querySelectorAll("[role='menuitem'], button, div[role='button']")
        );
        const uploadItem = menuItems.find((el) =>
          /upload from computer|tải lên từ máy tính|upload|tải lên|tệp/i.test(
            el.textContent || ""
          )
        );
        if (uploadItem) {
          uploadItem.click();
          await new Promise((r) => setTimeout(r, 400));
          fileInput = document.querySelector("input[type='file']");
        }
      } catch (e) {
        console.warn("[ChatGPTAdapter] Error clicking attach button:", e);
      }
    }

    return fileInput || document.querySelector("input[type='file']");
  }

  function findContinueButton() {
    return (
      document.querySelector("button[data-testid='continue-button']") ||
      document.querySelector("button[data-testid='continue-generating-button']") ||
      Array.from(document.querySelectorAll("button")).find((b) =>
        /continue generating|tiếp tục tạo|tiếp tục sinh|continue/i.test(
          (b.innerText || b.textContent || "").trim()
        )
      )
    );
  }

  async function executeTranslation({ srt_content, prompt_instruction, filename, request_id }) {
    console.log("[ChatGPTAdapter] Executing translation for request:", request_id);
    const targetFilename = filename || "original.srt";

    try {
      chrome.runtime.sendMessage({
        action: "LOG_EVENT",
        message: `ChatGPT: Đang chuẩn bị tải file ${targetFilename} lên...`,
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

    // 2. Attempt to attach .srt as file
    let fileAttached = false;
    try {
      const fileInput = await findChatGPTFileInput();
      if (fileInput) {
        const file = new File([srt_content], targetFilename, {
          type: "text/plain",
          lastModified: Date.now(),
        });
        const dt = new DataTransfer();
        dt.items.add(file);
        fileInput.files = dt.files;
        fileInput.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
        fileInput.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
        fileAttached = true;
        console.log("[ChatGPTAdapter] File attached successfully:", targetFilename);
        try {
          chrome.runtime.sendMessage({
            action: "LOG_EVENT",
            message: `ChatGPT: Đã đính kèm file ${targetFilename} thành công. Đang tải lên...`,
          });
        } catch (e) {}
        // Give ChatGPT time to mount attachment pill
        await new Promise((r) => setTimeout(r, 2000));
      }
    } catch (attachErr) {
      console.warn("[ChatGPTAdapter] File attachment failed, falling back to text prompt:", attachErr);
      fileAttached = false;
    }

    // 3. Build appropriate prompt
    let promptText = "";
    if (fileAttached) {
      const defaultFileInstruction =
        `Dịch toàn bộ nội dung file phụ đề ${targetFilename} đính kèm sang tiếng Việt:\n` +
        "- Sát nghĩa, tự nhiên, đúng bối cảnh và cảm xúc câu chuyện.\n" +
        "- Giữ nguyên 100% định dạng SRT, số thứ tự từng câu và mốc thời gian (timecode).\n" +
        "- Không gộp câu, không tách câu, không bỏ sót bất kỳ câu nào.\n" +
        "- Xuất toàn bộ nội dung file phụ đề SRT tiếng Việt hoàn chỉnh trong khối mã ```srt.";

      promptText = prompt_instruction || defaultFileInstruction;
    } else {
      try {
        chrome.runtime.sendMessage({
          action: "LOG_EVENT",
          message: "ChatGPT: Không tìm thấy ô tải file, đang dùng phương thức dự phòng (dán toàn bộ phụ đề vào ô chat)...",
        });
      } catch (e) {}
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

      promptText = prompt_instruction
        ? `${prompt_instruction}\n\n${srt_content}`
        : defaultInstruction;
    }

    // Record assistant message count prior to sending new prompt
    const initialAssistantCount = document.querySelectorAll(
      "div[data-message-author-role='assistant'], article[data-testid*='conversation-turn']"
    ).length;

    // 4. Inject prompt text
    insertPromptText(inputEl, promptText);
    await new Promise((r) => setTimeout(r, 800));

    // 5. Click send button (wait up to 12s if file is still uploading)
    let sendBtn = null;
    for (let i = 0; i < 40; i++) {
      sendBtn = findSendButton();
      if (sendBtn && !sendBtn.disabled) break;
      inputEl.dispatchEvent(new Event("input", { bubbles: true }));
      await new Promise((r) => setTimeout(r, 300));
    }

    if (sendBtn && !sendBtn.disabled) {
      sendBtn.click();
    } else {
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
        message: "ChatGPT: Đã gửi yêu cầu sang AI. Đang chờ AI bắt đầu phản hồi...",
      });
    } catch (e) {}

    // 6. Wait for streaming to begin
    let hasStarted = false;
    const waitStart = Date.now();
    while (Date.now() - waitStart < 20000) {
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
    const maxWaitMs = 600000; // 10 minutes max for full file translation
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

      // Auto-click Continue Generating if response paused
      if (!generating) {
        const continueBtn = findContinueButton();
        if (continueBtn && !continueBtn.disabled) {
          console.log("[ChatGPTAdapter] Detected Continue Generating button. Clicking...");
          try {
            chrome.runtime.sendMessage({
              action: "LOG_EVENT",
              message: "ChatGPT: Phát hiện nội dung dài, đang tự động bấm 'Tiếp tục tạo'...",
            });
          } catch (e) {}
          continueBtn.click();
          await new Promise((r) => setTimeout(r, 2000));
          continue;
        }
      }

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

      if (!generating && (hasStarted || Date.now() - startTime > 4000)) {
        await new Promise((r) => setTimeout(r, 1500));
        if (!isGenerating()) {
          // Double check continue button again before completing
          const continueBtn = findContinueButton();
          if (continueBtn && !continueBtn.disabled) {
            continueBtn.click();
            await new Promise((r) => setTimeout(r, 2000));
            continue;
          }

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

    throw new Error("Quá thời gian chờ phản hồi từ ChatGPT (hơn 10 phút).");
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
