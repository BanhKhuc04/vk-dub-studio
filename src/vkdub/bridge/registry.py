"""Windows Registry setup for VK Dub Studio Native Messaging Host."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger("vkdub.bridge.registry")

HOST_NAME = "com.vkdub.bridge"

REGISTRY_TARGETS = [
    (r"Software\Microsoft\Edge\NativeMessagingHosts", "Microsoft Edge"),
    (r"Software\Google\Chrome\NativeMessagingHosts", "Google Chrome"),
]


def default_manifest_path() -> Path:
    """Locate the native messaging host manifest in the project or application install tree."""
    # Check project tools dir
    cand = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "tools"
        / "native_host"
        / f"{HOST_NAME}.json"
    )
    if cand.is_file():
        return cand
    # Fallback to current working directory tools
    cand2 = Path.cwd() / "tools" / "native_host" / f"{HOST_NAME}.json"
    if cand2.is_file():
        return cand2
    return cand


def ensure_host_registered(manifest_path: Path | None = None) -> bool:
    """Ensure that the Native Messaging Host is registered for Edge and Chrome.

    Returns True if at least one browser is successfully registered.
    """
    if sys.platform != "win32":
        return False

    import winreg

    target_manifest = (manifest_path or default_manifest_path()).resolve()
    if not target_manifest.is_file():
        logger.warning("Cannot register native host, manifest not found at %s", target_manifest)
        return False

    success = False
    manifest_str = str(target_manifest)

    for subkey_base, browser_name in REGISTRY_TARGETS:
        key_path = f"{subkey_base}\\{HOST_NAME}"
        try:
            # Check existing value
            already_correct = False
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                    val, _ = winreg.QueryValueEx(key, "")
                    if val == manifest_str:
                        already_correct = True
            except Exception:
                pass

            if already_correct:
                success = True
                continue

            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, manifest_str)
            success = True
            logger.info(
                "Registered Native Messaging Host for %s at HKCU\\%s", browser_name, key_path
            )
        except Exception as exc:
            logger.warning("Failed to register native host for %s: %s", browser_name, exc)

    return success
