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
      version: "2.1.8",
      is_studio: isStudio,
      is_dubbing_page: isDubbingPage,
      has_avatar: hasAvatar,
      url: window.location.href,
      title: document.title,
    };
  }

  function safeClick(elem) {
    if (!elem) return false;
    try {
      if (typeof elem.click === "function") {
        elem.click();
        return true;
      }
      if (elem.parentElement && typeof elem.parentElement.click === "function") {
        elem.parentElement.click();
        return true;
      }
      const evt = new MouseEvent("click", {
        bubbles: true,
        cancelable: true,
        view: window,
      });
      elem.dispatchEvent(evt);
      return true;
    } catch (err) {
      console.warn("[VbeeAdapter] safeClick error:", err);
      return false;
    }
  }

  function findElementByText(selector, textMatch, exact = false) {
    const elems = Array.from(document.querySelectorAll(selector));
    return elems.find((el) => {
      const txt = (el.innerText || el.textContent || "").trim();
      return exact ? txt === textMatch : txt.includes(textMatch);
    });
  }

  async function waitForElement(finder, timeoutMs = 1500, stepMs = 100) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const el = finder();
      if (el) return el;
      await new Promise((r) => setTimeout(r, stepMs));
    }
    return null;
  }

  function normalizedJobKey(value) {
    // Vbee removes separators such as '_' from uploaded SRT names. Match the
    // stable alphanumeric identity so retry still finds exactly the same job.
    return String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  async function queryVbeeRequest(jobName, requireJobMatch = false) {
    const endpoints = [
      "https://vbee.vn/api/v2/requests?type=dubbing&limit=5&sort=-createdAt&fields=id,title,characters,credits,seconds,createdAt,progress,status,voice,audioType,audioLink",
      `${window.location.origin}/api/v2/requests?type=dubbing&limit=5&sort=-createdAt&fields=id,title,characters,credits,seconds,createdAt,progress,status,voice,audioType,audioLink`,
    ];
    for (const apiUrl of endpoints) {
      try {
        const res = await fetch(apiUrl, { credentials: "include" });
        if (res.ok) {
          const json = await res.json();
          const reqs = json?.result?.requests || json?.data?.requests || json?.data || [];
          for (const req of reqs) {
            const title = String(req.title || req.name || "");
            const matchesJob =
              !jobName || normalizedJobKey(title).includes(normalizedJobKey(jobName));
            if (matchesJob) {
              const rawProg = req.progress;
              const isSuccess = req.status === 1 || req.status === "SUCCESS";
              const progNum = typeof rawProg === "number" ? rawProg : (isSuccess ? 100 : 0);
              return {
                id: req.id,
                title: req.title,
                progress: Math.max(0, Math.min(100, Math.round(progNum))),
                status: req.status,
                audioUrl: req.audioLink || null,
                createdAt: req.createdAt,
              };
            }
          }
          if (!requireJobMatch && reqs.length > 0) {
            const newest = reqs[0];
            const createdTime = new Date(newest.createdAt || Date.now()).getTime();
            if (Date.now() - createdTime < 900000) {
              const rawProg = newest.progress;
              const isSuccess = newest.status === 1 || newest.status === "SUCCESS";
              const progNum = typeof rawProg === "number" ? rawProg : (isSuccess ? 100 : 0);
              return {
                id: newest.id,
                title: newest.title,
                progress: Math.max(0, Math.min(100, Math.round(progNum))),
                status: newest.status,
                audioUrl: newest.audioLink || null,
                createdAt: newest.createdAt,
              };
            }
          }
        }
      } catch (err) {
        console.warn("[VbeeAdapter] Error querying requests API:", apiUrl, err);
      }
    }
    return null;
  }

  async function getCompletedAudioFromApi(jobName) {
    const req = await queryVbeeRequest(jobName, true);
    if (req && (req.status === 1 || req.status === "SUCCESS" || req.progress === 100) && req.audioUrl) {
      return req;
    }
    return null;
  }

  function findJobRow(jobName) {
    return Array.from(document.querySelectorAll("tr, .ant-table-row, div[class*='row']")).find(
      (row) => normalizedJobKey(row.innerText).includes(normalizedJobKey(jobName))
    );
  }

  function findDownloadButton(row) {
    return row?.querySelector(
      "button:has(svg[data-testid*='Download']), svg[data-testid*='Download'], " +
      "svg[data-testid='DownloadRoundedIcon'], button[title*='Tải'], a[download]"
    );
  }

  async function completedResult(job, requestId, jobName) {
    // Không tự tải + encode base64 trong tab (chậm, tốn RAM, có thể vượt giới
    // hạn kích thước Native Messaging). Phía Python (local_agent.py) đã tự
    // tải trực tiếp từ audio_url bằng httpx khi audio_base64 vắng mặt.
    return {
      success: true,
      audio_url: job.audioUrl,
      request_id: requestId,
      job_name: jobName,
    };
  }

  async function executeVoiceGeneration({ srt_content, voice_name = "Ngọc Huyền", speed = "1.1x", request_id, job_name }) {
    console.log("[VbeeAdapter] Starting voice generation for request:", request_id);
    if (!request_id || !job_name || !srt_content) {
      throw new Error("Yêu cầu Vbee thiếu request_id, job_name hoặc nội dung SRT.");
    }

    // Retry safety: reuse only a completed job with the same deterministic script identity.
    const existingJob = await getCompletedAudioFromApi(job_name);
    if (existingJob && existingJob.audioUrl) {
      console.log("[VbeeAdapter] Found already completed audio on Vbee:", existingJob.audioUrl);
      return await completedResult(existingJob, request_id, job_name);
    }

    const existingRow = findJobRow(job_name);
    const existingDownload = findDownloadButton(existingRow);
    if (existingDownload) {
      safeClick(existingDownload);
      return { success: true, download_triggered: true, request_id, job_name };
    }

    // 2. Ensure on dubbing page
    if (!window.location.pathname.includes("/dubbing")) {
      console.log("[VbeeAdapter] Navigating to /studio/dubbing...");
      window.location.href = "https://studio.vbee.vn/studio/dubbing";
      return { status: "NAVIGATING", message: "Đang mở trang Chuyển phụ đề Vbee...", request_id };
    }

    // 3. Handle initial policy / terms agreement modal if present
    const termsCheckbox = document.querySelector("input[type='checkbox'], .ant-checkbox-input, span.ant-checkbox");
    if (termsCheckbox) {
      if (!termsCheckbox.checked && !termsCheckbox.classList.contains("ant-checkbox-checked")) {
        safeClick(termsCheckbox);
        await new Promise((r) => setTimeout(r, 400));
      }
      const agreeBtn =
        findElementByText("button", "Đồng ý & Tiếp tục") ||
        findElementByText("button", "Đồng ý") ||
        findElementByText("button", "Tiếp tục");
      if (agreeBtn) {
        safeClick(agreeBtn);
        await new Promise((r) => setTimeout(r, 1000));
      }
    }

    // 4. Check if subtitles are already loaded in the editor table
    const pageText = document.body.innerText || "";
    const isSubLoaded = pageText.includes(`${job_name}.srt`);

    if (!isSubLoaded && srt_content) {
      console.log("[VbeeAdapter] Uploading SRT subtitle file...");
      let fileInput = null;
      for (let i = 0; i < 20; i++) {
        fileInput = document.querySelector("input[type='file'][accept*='.srt'], input[type='file']");
        if (fileInput) break;
        await new Promise((r) => setTimeout(r, 400));
      }

      if (!fileInput) {
        throw new Error("Không tìm thấy ô tải file SRT trên giao diện Vbee Dubbing.");
      }

      const srtBlob = new Blob([srt_content], { type: "text/plain;charset=utf-8" });
      const srtFile = new File([srtBlob], `${job_name}.srt`, { type: "text/plain" });
      const dt = new DataTransfer();
      dt.items.add(srtFile);
      fileInput.files = dt.files;
      fileInput.dispatchEvent(new Event("change", { bubbles: true }));
      fileInput.dispatchEvent(new Event("input", { bubbles: true }));
      await new Promise((r) => setTimeout(r, 2000));
    }

    // 5. Select Voice: Ngọc Huyền (if not already selected)
    try {
      const curText = document.body.innerText || "";
      if (!curText.includes(voice_name) && !curText.includes("Ngọc Huyền")) {
        const voiceTrigger =
          document.querySelector("div[class*='voice-select']") ||
          document.querySelector("div[class*='select-voice']") ||
          findElementByText("div, span, button", "Chọn giọng") ||
          findElementByText("div, span, button", "Giọng đọc");

        if (voiceTrigger) {
          safeClick(voiceTrigger);
          const voiceOpt = await waitForElement(
            () =>
              findElementByText("div[role='option'], div.ant-select-item-option, span, li", voice_name) ||
              findElementByText("div, span, li", "HN - Ngọc Huyền")
          );
          if (voiceOpt) {
            safeClick(voiceOpt);
            console.log("[VbeeAdapter] Voice selected:", voice_name);
          }
        }
      }
    } catch (voiceErr) {
      console.warn("[VbeeAdapter] Voice configuration notice:", voiceErr);
    }

    await new Promise((r) => setTimeout(r, 600));

    // 6. Select Speed: 1.1x (if not already 1.1x)
    try {
      const curText = document.body.innerText || "";
      if (!curText.includes("1.1x")) {
        const speedTrigger =
          document.querySelector(".speed button") ||
          document.querySelector("button:has([data-testid*='ArrowDrop'])") ||
          document.querySelector(".speed") ||
          document.querySelector("div[class*='speed']") ||
          findElementByText("button, span, div", "1x", true) ||
          document.querySelector("[data-testid='ArrowDropDownIcon']");

        if (speedTrigger) {
          safeClick(speedTrigger);
          const speedOpt = await waitForElement(
            () =>
              findElementByText("li.MuiMenuItem-root, div[role='option'], span, li", speed) ||
              findElementByText("li, div, span", "1.1x")
          );
          if (speedOpt) {
            safeClick(speedOpt);
            console.log("[VbeeAdapter] Speed configured to: 1.1x");
          }
        }
      }
    } catch (speedErr) {
      console.warn("[VbeeAdapter] Speed configuration notice:", speedErr);
    }

    await new Promise((r) => setTimeout(r, 600));

    // 7. Submit conversion
    console.log("[VbeeAdapter] Submitting dubbing conversion...");
    try {
      chrome.runtime.sendMessage({
        action: "LOG_EVENT",
        message: `Vbee: Đang chọn giọng '${voice_name}' (${speed}) và nạp kịch bản vào studio...`,
      });
    } catch (e) {}

    const submitBtn =
      findElementByText("button", "Chuyển phụ đề") ||
      findElementByText("button", "Bắt đầu chuyển") ||
      findElementByText("button", "Tạo thuyết minh") ||
      findElementByText("button", "Tạo voice") ||
      findElementByText("button", "Chuyển đổi") ||
      document.querySelector("button.ant-btn-primary");

    if (!submitBtn) {
      throw new Error("Không tìm thấy nút 'Chuyển phụ đề' trên Vbee.");
    }

    safeClick(submitBtn);
    await new Promise((r) => setTimeout(r, 1200));

    // Handle confirmation modal if present
    for (let attempt = 0; attempt < 6; attempt++) {
      const confirmBtn =
        findElementByText("button.ant-btn-primary, button", "Xác nhận") ||
        findElementByText("button.ant-btn-primary, button", "Đồng ý") ||
        findElementByText("button", "Tiếp tục");
      if (confirmBtn) {
        safeClick(confirmBtn);
        console.log("[VbeeAdapter] Confirmed conversion modal.");
        break;
      }
      await new Promise((r) => setTimeout(r, 400));
    }

    // 8. Poll for completion (API + DOM)
    console.log("[VbeeAdapter] Polling for completion...");
    try {
      chrome.runtime.sendMessage({
        action: "LOG_EVENT",
        message: "Vbee: Đã gửi yêu cầu tạo voice, đang chờ máy chủ xử lý...",
      });
    } catch (e) {}

    const startTime = Date.now();
    const maxWaitMs = 600000; // 10 minutes max
    let lastLogTime = 0;

    while (Date.now() - startTime < maxWaitMs) {
      // Check quota or fatal errors
      const bodyText = document.body.innerText || "";
      if (/hết ký tự/i.test(bodyText) || /không đủ điểm/i.test(bodyText) || /vượt quá số ký tự/i.test(bodyText)) {
        throw new Error("Tài khoản Vbee đã hết số dư ký tự hoặc vượt quá hạn mức.");
      }

      // Query real server status via Vbee API
      const apiReq = await queryVbeeRequest(job_name, false);
      if (apiReq) {
        const pct = Math.max(0, Math.min(100, Math.round(apiReq.progress || 0)));
        try {
          chrome.runtime.sendMessage({
            action: "VBEE_PROGRESS",
            progress: pct,
            message: `Vbee: Đang tổng hợp giọng nói (${pct}%)...`,
            request_id: request_id,
          });
        } catch (e) {}

        const now = Date.now();
        if (now - lastLogTime > 2500) {
          lastLogTime = now;
          try {
            chrome.runtime.sendMessage({
              action: "LOG_EVENT",
              message: `Vbee: Đang tổng hợp giọng nói (${pct}%)...`,
            });
          } catch (e) {}
        }

        // If completed and audioLink is ready, return directly without needing DOM click
        if ((apiReq.status === 1 || apiReq.status === "SUCCESS" || pct === 100) && apiReq.audioUrl) {
          console.log("[VbeeAdapter] Completion detected via API with direct audioUrl:", apiReq.audioUrl);
          try {
            chrome.runtime.sendMessage({
              action: "VBEE_PROGRESS",
              progress: 100,
              message: "Vbee: Đã hoàn tất tạo giọng đọc 100%!",
              request_id: request_id,
            });
            chrome.runtime.sendMessage({
              action: "LOG_EVENT",
              message: "Vbee: Đã hoàn tất tạo giọng đọc 100%! Đang chuyển file âm thanh về máy...",
            });
          } catch (e) {}
          return await completedResult(apiReq, request_id, job_name);
        }

        // If 100% or done in API but audioUrl not in API, wake tab so DOM unfreezes
        if (apiReq.status === 1 || apiReq.status === "SUCCESS" || pct === 100) {
          try {
            chrome.runtime.sendMessage({ action: "WAKE_VBEE_TAB" });
          } catch (e) {}
        }
      }

      // Check DOM row fallback
      const firstRow = findJobRow(job_name);
      if (firstRow) {
        const rowText = firstRow.innerText || "";
        const isProcessing = /\b\d{1,2}%\b/.test(rowText) || /đang xử lý/i.test(rowText) || !!firstRow.querySelector("[role='progressbar'], .ant-spin");

        if (!isProcessing) {
          const rowDlBtn = findDownloadButton(firstRow);
          if (rowDlBtn) {
            console.log("[VbeeAdapter] Completion detected in DOM row! Clicking download...");
            try {
              chrome.runtime.sendMessage({
                action: "VBEE_PROGRESS",
                progress: 100,
                message: "Vbee: Đã hoàn tất tạo giọng đọc 100%!",
                request_id: request_id,
              });
              chrome.runtime.sendMessage({
                action: "LOG_EVENT",
                message: "Vbee: Đã hoàn tất tạo giọng đọc! Đang bấm tải xuống...",
              });
            } catch (e) {}
            safeClick(rowDlBtn);
            return {
              success: true,
              download_triggered: true,
              request_id,
              job_name,
            };
          }
        }
      }

      // Periodically wake tab every 5s so Edge does not freeze background timers
      if (Math.floor((Date.now() - startTime) / 1000) % 5 === 0) {
        try {
          chrome.runtime.sendMessage({ action: "WAKE_VBEE_TAB" });
        } catch (e) {}
      }

      await new Promise((r) => setTimeout(r, 1200));
    }

    throw new Error("Quá thời gian xử lý giọng đọc trên Vbee (hơn 10 phút).");
  }

  if (window.__vbeeListener) {
    try {
      chrome.runtime.onMessage.removeListener(window.__vbeeListener);
    } catch (e) {}
  }

  window.__vbeeListener = (request, sender, sendResponse) => {
    if (request && request.action === VBEE_CHECK_ACTION) {
      sendResponse(checkLoginState());
      return true;
    }

    if (request && request.action === VBEE_GENERATE_ACTION) {
      // Trả lời NGAY để đóng kênh message trong <1s. Tạo voice có thể chạy
      // tới 10 phút, vượt xa giới hạn ~5 phút mà Chrome/Edge giữ một kênh
      // message bất đồng bộ mở — nếu giữ kênh mở sẽ mất kết quả giữa chừng.
      sendResponse({ status: "STARTED", request_id: request.payload?.request_id });

      executeVoiceGeneration(request.payload || {})
        .then((res) => {
          chrome.runtime.sendMessage({ action: "VBEE_GENERATE_DONE", payload: res });
        })
        .catch((err) => {
          chrome.runtime.sendMessage({
            action: "VBEE_GENERATE_DONE",
            payload: { success: false, error: err.message, request_id: request.payload?.request_id },
          });
        });
      return true;
    }
  };
  chrome.runtime.onMessage.addListener(window.__vbeeListener);

  try {
    chrome.runtime.sendMessage({
      action: "VBEE_TAB_READY",
      status: checkLoginState(),
    });
  } catch (err) {}
})();
