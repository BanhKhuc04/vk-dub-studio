/**
 * VK Dub Studio — Vbee Content Script Adapter
 * Inspects Vbee DOM, reports session status, and prepares for H6.2 automation.
 */

(function () {
  const VBEE_CHECK_ACTION = "CHECK_VBEE_STATUS";

  function checkLoginState() {
    // Check for logged-in indicators
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

    // Check for login forms / buttons (indicates logged out)
    const hasLoginForm = !!(
      document.querySelector("input[type='password']") ||
      document.querySelector("form[class*='login']") ||
      document.querySelector(".login-box") ||
      document.querySelector("div[class*='login-form']")
    );

    const hasLoginButton = !!Array.from(
      document.querySelectorAll("button, a")
    ).some((el) => {
      const text = el.textContent ? el.textContent.trim() : "";
      return text === "Đăng nhập" && !text.includes("Đăng xuất");
    });

    const isStudio = window.location.hostname.includes("studio.vbee.vn");
    const isDubbingPage = window.location.pathname.includes("/dubbing");

    // Logged in if has avatar/logout and no active login form
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

  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request && request.action === VBEE_CHECK_ACTION) {
      sendResponse(checkLoginState());
      return true;
    }
  });

  try {
    chrome.runtime.sendMessage({
      action: "VBEE_TAB_READY",
      status: checkLoginState(),
    });
  } catch (err) {
    // Ignore if background not ready
  }

  let lastReportedState = null;
  const observer = new MutationObserver(() => {
    const currentState = checkLoginState().logged_in;
    if (currentState !== lastReportedState) {
      lastReportedState = currentState;
      try {
        chrome.runtime.sendMessage({
          action: "VBEE_STATUS_CHANGED",
          status: checkLoginState(),
        });
      } catch (e) {
        // ignore
      }
    }
  });

  observer.observe(document.body || document.documentElement, {
    childList: true,
    subtree: true,
  });
})();
