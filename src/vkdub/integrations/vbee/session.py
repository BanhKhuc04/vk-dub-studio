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


def find_edge_executable() -> str | None:
    for candidate in EDGE_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


def cleanup_stale_profile_processes(profile_dir: Path) -> None:
    """Terminate any lingering browser processes using this dedicated automation profile."""
    if os.name != "nt":
        return
    import subprocess

    profile_str = str(profile_dir).replace("/", "\\")
    cmd = (
        f'Get-CimInstance Win32_Process -Filter "Name = \'msedge.exe\' or Name = \'chrome.exe\'" | '
        f'Where-Object {{ $_.CommandLine -like "*{profile_str}*" }} | '
        f'ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}'
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, timeout=5)
    except Exception as exc:
        logger.debug("cleanup_stale_profile_processes: %s", exc)


async def create_vbee_browser_context(
    playwright: Playwright,
    profile_dir: Path | None = None,
    downloads_path: Path | None = None,
    headless: bool = False,
    channel: str | None = None,
) -> BrowserContext:
    """Launch persistent browser context with stored cookies/session."""
    user_data_dir = profile_dir or get_vbee_profile_dir()
    cleanup_stale_profile_processes(user_data_dir)
    edge_exe = find_edge_executable()

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
    }

    if edge_exe:
        context_kwargs["executable_path"] = edge_exe
    elif channel:
        context_kwargs["channel"] = channel
    else:
        detected = detect_browser_channel()
        if detected:
            context_kwargs["channel"] = detected
        else:
            raise RuntimeError(
                "Không tìm thấy Microsoft Edge hoặc Google Chrome trên máy tính.\n"
                "Vui lòng cài đặt Microsoft Edge hoặc Google Chrome để sử dụng tính năng tự động hóa Vbee."
            )

    logger.info(
        "Khởi tạo trình duyệt Vbee: exe=%s, profile=%s, headless=%s",
        edge_exe or context_kwargs.get("channel", "bundled"),
        user_data_dir,
        headless,
    )

    try:
        return await playwright.chromium.launch_persistent_context(**context_kwargs)
    except Exception as exc:
        err_msg = str(exc)
        if "existing browser session" in err_msg or "ProcessSingleton" in err_msg:
            logger.warning("Phát hiện tiến trình cũ đang giữ profile. Đang dọn dẹp và thử lại…")
            cleanup_stale_profile_processes(user_data_dir)
            import asyncio

            await asyncio.sleep(1.0)
            return await playwright.chromium.launch_persistent_context(**context_kwargs)

        if "Executable doesn't exist" in err_msg or "channel" in err_msg:
            raise RuntimeError(
                "Không thể mở trình duyệt điều khiển Vbee. "
                "Hãy đảm bảo Microsoft Edge hoặc Google Chrome đã được cài đặt trên máy tính của bạn."
            ) from exc
        raise
