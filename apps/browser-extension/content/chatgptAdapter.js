/**
 * VK Dub Studio — ChatGPT Content Script Adapter
 * Inspects ChatGPT DOM, reports session status, and prepares for H6.1 automation.
 */

(function () {
  const CHATGPT_CHECK_ACTION = "CHECK_CHATGPT_STATUS";

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

    // Explicit login buttons indicate logged out state
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

  // Handle queries from Background Service Worker
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request && request.action === CHATGPT_CHECK_ACTION) {
      sendResponse(checkLoginState());
      return true;
    }
  });

  // Notify service worker when tab loads or navigation occurs
  try {
    chrome.runtime.sendMessage({
      action: "CHATGPT_TAB_READY",
      status: checkLoginState(),
    });
  } catch (err) {
    // Ignore if background not yet ready
  }

  // Observe DOM changes (e.g. login completes without full page reload)
  let lastReportedState = null;
  const observer = new MutationObserver(() => {
    const currentState = checkLoginState().logged_in;
    if (currentState !== lastReportedState) {
      lastReportedState = currentState;
      try {
        chrome.runtime.sendMessage({
          action: "CHATGPT_STATUS_CHANGED",
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
