"""Browser discovery, persistent profile, and session management for Vbee automation."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vkdub.utils.paths import data_root

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Playwright

logger = logging.getLogger("vkdub.vbee")

# Common executable paths on Windows for discovery verification
EDGE_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)

CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
)


def get_vbee_profile_dir() -> Path:
    """Return persistent user profile directory for Vbee browser sessions.

    Located under %LOCALAPPDATA%/VKDubStudio/browser_profiles/vbee to ensure
    it stays outside the git repository and workspace.
    """
    profile_dir = data_root() / "browser_profiles" / "vbee"
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir


def detect_browser_channel() -> str | None:
    """Detect available browser channel on the current system.

    Prefers 'msedge' on Windows (universal), then 'chrome', or None (bundled chromium).
    """
    for edge_path in EDGE_CANDIDATES:
        if Path(edge_path).is_file():
            return "msedge"

    for chrome_path in CHROME_CANDIDATES:
        if Path(chrome_path).is_file():
            return "chrome"

    # Fallback: check PATH
    if shutil.which("msedge"):
        return "msedge"
    if shutil.which("chrome"):
        return "chrome"

    return None


async def create_vbee_browser_context(
    playwright: Playwright,
    profile_dir: Path | None = None,
    downloads_path: Path | None = None,
    headless: bool = False,
    channel: str | None = None,
) -> BrowserContext:
    """Launch persistent browser context with stored cookies/session."""
    user_data_dir = profile_dir or get_vbee_profile_dir()
    chosen_channel = channel or detect_browser_channel()

    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--start-maximized",
    ]

    context_kwargs: dict[str, Any] = {
        "user_data_dir": str(user_data_dir),
        "headless": headless,
        "args": launch_args,
        "viewport": {"width": 1280, "height": 800},
        "locale": "vi-VN",
        "accept_downloads": True,
        "ignore_default_args": ["--enable-automation"],
    }

    if downloads_path:
        downloads_path.mkdir(parents=True, exist_ok=True)
        context_kwargs["downloads_path"] = str(downloads_path)

    if chosen_channel:
        context_kwargs["channel"] = chosen_channel

    logger.info(
        "Khởi tạo trình duyệt Vbee: channel=%s, profile=%s, headless=%s",
        chosen_channel or "default",
        user_data_dir,
        headless,
    )

    try:
        return await playwright.chromium.launch_persistent_context(**context_kwargs)
    except Exception as exc:
        # If launched with a channel and it fails, retry without channel (bundled chromium)
        if chosen_channel:
            logger.warning(
                "Lỗi khởi chạy với channel=%s (%s). Thử lại với Chromium mặc định.",
                chosen_channel,
                exc,
            )
            context_kwargs.pop("channel", None)
            return await playwright.chromium.launch_persistent_context(**context_kwargs)
        raise
