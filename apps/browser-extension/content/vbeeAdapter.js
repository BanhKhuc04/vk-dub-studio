/**
 * VK Dub Studio — Vbee Content Script Adapter (H6.2 Automation)
 *
 * Implements end-to-end automated voice dubbing on Vbee Studio:
 * 1. Verifies dubbing page.
 * 2. Uploads translated.srt via DataTransfer File API.
 * 3. Selects Voice: Ngọc Huyền.
 * 4. Selects Speed: 1.1x.
 * 5. Submits conversion and handles confirmation dialogs.
 * 6. Polls for completion and extracts final master audio.
 * 7. Returns audio data/URL to background service worker.
 */

(function () {
  const VBEE_CHECK_ACTION = "CHECK_VBEE_STATUS";
  const VBEE_GENERATE_ACTION = "VBEE_GENERATE_VOICE";

  function checkLoginState() {
    const hasAvatar = !!(
      document.querySelector("div[class*='avatar']") ||
      document.querySelector("img[class*='avatar']") ||
      document.querySelector(".user-avatar") ||
      document.querySelector("div[class*='user-info']") ||
      document.querySelector("span[class*='user-name']") ||
      document.querySelector(".ant-dropdown-trigger")
    );

    const hasLogout = !!(
      document.querySelector("a[href*='logout']") ||
      Array.from(document.querySelectorAll("button, a, span")).some(
        (el) => el.textContent && el.textContent.includes("Đăng xuất")
      )
    );

    const hasLoginForm = !!(
      document.querySelector("input[type='password']") ||
      document.querySelector("form[class*='login']") ||
      document.querySelector(".login-box") ||
      document.querySelector("div[class*='login-form']")
    );

    const isStudio = window.location.hostname.includes("studio.vbee.vn");
    const isDubbingPage = window.location.pathname.includes("/dubbing");
    const isLoggedIn = (hasAvatar || hasLogout || isStudio) && !hasLoginForm;

    return {
      available: true,
      logged_in: isLoggedIn,
      is_studio: isStudio,
      is_dubbing_page: isDubbingPage,
      has_avatar: hasAvatar,
      url: window.location.href,
      title: document.title,
    };
  }

  function findElementByText(selector, textMatch, exact = false) {
    const elems = Array.from(document.querySelectorAll(selector));
    return elems.find((el) => {
      const txt = (el.innerText || el.textContent || "").trim();
      return exact ? txt === textMatch : txt.includes(textMatch);
    });
  }

  async function executeVoiceGeneration({ srt_content, voice_name = "Ngọc Huyền", speed = "1.1x", request_id }) {
    console.log("[VbeeAdapter] Starting voice generation for request:", request_id);

    // 1. Ensure on dubbing page
    if (!window.location.pathname.includes("/dubbing")) {
      console.log("[VbeeAdapter] Navigating to /studio/dubbing...");
      window.location.href = "https://studio.vbee.vn/studio/dubbing";
      return { status: "NAVIGATING", message: "Đang mở trang Chuyển phụ đề Vbee...", request_id };
    }

    // 2. Locate SRT file input
    let fileInput = null;
    for (let i = 0; i < 20; i++) {
      fileInput = document.querySelector("input[type='file'][accept*='.srt'], input[type='file']");
      if (fileInput) break;
      await new Promise((r) => setTimeout(r, 500));
    }

    if (!fileInput) {
      throw new Error("Không tìm thấy ô tải file SRT trên giao diện Vbee Dubbing.");
    }

    // 3. Upload SRT content via HTML5 File and DataTransfer
    console.log("[VbeeAdapter] Uploading translated SRT content...");
    const srtBlob = new Blob([srt_content], { type: "text/plain;charset=utf-8" });
    const srtFile = new File([srtBlob], "translated.srt", { type: "text/plain" });
    const dt = new DataTransfer();
    dt.items.add(srtFile);
    fileInput.files = dt.files;
    fileInput.dispatchEvent(new Event("change", { bubbles: true }));
    fileInput.dispatchEvent(new Event("input", { bubbles: true }));

    await new Promise((r) => setTimeout(r, 2000));

    // 4. Select Voice: Ngọc Huyền
    console.log(`[VbeeAdapter] Checking voice selection for: ${voice_name}...`);
    const pageText = document.body.innerText || "";
    if (!pageText.includes("Ngọc Huyền")) {
      const voiceTrigger =
        document.querySelector("div[class*='voice-select']") ||
        document.querySelector("div[class*='select-voice']") ||
        findElementByText("div, span, button", "Chọn giọng") ||
        findElementByText("div, span, button", "Giọng đọc");

      if (voiceTrigger) {
        voiceTrigger.click();
        await new Promise((r) => setTimeout(r, 800));
        const voiceOpt =
          findElementByText("div[role='option'], div.ant-select-item-option, span, li", voice_name) ||
          findElementByText("div, span, li", "HN - Ngọc Huyền");
        if (voiceOpt) {
          voiceOpt.click();
          console.log("[VbeeAdapter] Voice selected: Ngọc Huyền");
        }
      }
    }

    await new Promise((r) => setTimeout(r, 600));

    // 5. Select Speed: 1.1x
    console.log(`[VbeeAdapter] Configuring speed: ${speed}...`);
    const speedTrigger =
      document.querySelector(".speed [data-testid='ArrowDropDownIcon']") ||
      document.querySelector(".speed button") ||
      document.querySelector("div[class*='speed']") ||
      findElementByText("button, span, div", "1x", true) ||
      findElementByText("button, span, div", "1.0x", true);

    if (speedTrigger) {
      speedTrigger.click();
      await new Promise((r) => setTimeout(r, 800));
      const speedOpt =
        findElementByText("li.MuiMenuItem-root, div[role='option'], span", speed) ||
        findElementByText("li, div, span", "1.1x");
      if (speedOpt) {
        speedOpt.click();
        console.log("[VbeeAdapter] Speed configured to: 1.1x");
      }
    }

    await new Promise((r) => setTimeout(r, 600));

    // 6. Submit conversion
    console.log("[VbeeAdapter] Submitting dubbing conversion...");
    const submitBtn =
      findElementByText("button", "Chuyển phụ đề") ||
      findElementByText("button", "Bắt đầu chuyển") ||
      findElementByText("button", "Tạo thuyết minh") ||
      findElementByText("button", "Tạo voice") ||
      findElementByText("button", "Chuyển đổi");

    if (!submitBtn) {
      throw new Error("Không tìm thấy nút 'Chuyển phụ đề' trên Vbee.");
    }

    submitBtn.click();
    await new Promise((r) => setTimeout(r, 1200));

    // Handle confirmation modal if present
    const confirmBtn =
      findElementByText("button.ant-btn-primary, button", "Xác nhận") ||
      findElementByText("button.ant-btn-primary, button", "Đồng ý") ||
      findElementByText("button", "Tiếp tục");

    if (confirmBtn) {
      confirmBtn.click();
      console.log("[VbeeAdapter] Confirmed conversion modal.");
    }

    // 7. Poll for completion
    console.log("[VbeeAdapter] Polling for voice generation completion...");
    const startTime = Date.now();
    const maxWaitMs = 600000; // 10 minutes max for long video subtitles

    while (Date.now() - startTime < maxWaitMs) {
      // Check quota or fatal errors
      const bodyText = document.body.innerText || "";
      if (/hết ký tự/i.test(bodyText) || /không đủ điểm/i.test(bodyText) || /vượt quá số ký tự/i.test(bodyText)) {
        throw new Error("Tài khoản Vbee đã hết số dư ký tự hoặc vượt quá hạn mức.");
      }

      // Check download / completion indicators
      const downloadBtn =
        document.querySelector("button:has(svg[data-testid*='Download'])") ||
        document.querySelector("svg[data-testid*='Download']") ||
        findElementByText("button, a", "Tải xuống") ||
        findElementByText("button, a", "Tải về") ||
        findElementByText("button, a", "Tải audio") ||
        document.querySelector("a[download]");

      if (downloadBtn) {
        console.log("[VbeeAdapter] Completion detected! Fetching audio...");
        // Check if there is an explicit audio src or link
        let audioUrl = null;
        if (downloadBtn.tagName.toLowerCase() === "a" && downloadBtn.href) {
          audioUrl = downloadBtn.href;
        } else {
          const audioElem = document.querySelector("audio[src], source[src]");
          if (audioElem && audioElem.src) {
            audioUrl = audioElem.src;
          }
        }

        // If audio URL found, download blob and convert to base64
        let base64Audio = null;
        if (audioUrl && audioUrl.startsWith("http")) {
          try {
            const resp = await fetch(audioUrl);
            const blob = await resp.blob();
            base64Audio = await new Promise((resolve) => {
              const reader = new FileReader();
              reader.onloadend = () => resolve(reader.result.split(",")[1]);
              reader.readAsDataURL(blob);
            });
          } catch (e) {
            console.warn("[VbeeAdapter] Could not directly fetch audio blob:", e);
          }
        }

        // Trigger download button as well to ensure file downloads to disk if needed
        try {
          downloadBtn.click();
        } catch (e) {}

        return {
          success: true,
          audio_url: audioUrl,
          audio_base64: base64Audio,
          request_id: request_id,
        };
      }

      await new Promise((r) => setTimeout(r, 2000));
    }

    throw new Error("Quá thời gian xử lý giọng đọc trên Vbee (hơn 10 phút).");
  }

  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request && request.action === VBEE_CHECK_ACTION) {
      sendResponse(checkLoginState());
      return true;
    }

    if (request && request.action === VBEE_GENERATE_ACTION) {
      executeVoiceGeneration(request.payload || {})
        .then((res) => sendResponse(res))
        .catch((err) => sendResponse({ success: false, error: err.message, request_id: request.payload?.request_id }));
      return true;
    }
  });

  try {
    chrome.runtime.sendMessage({
      action: "VBEE_TAB_READY",
      status: checkLoginState(),
    });
  } catch (err) {}
})();
