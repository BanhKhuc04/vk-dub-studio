"""Register VK Dub Studio Native Messaging Host in Windows Registry for Edge and Chrome."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("vkdub.register_host")

HOST_NAME = "com.vkdub.bridge"

REGISTRY_TARGETS = [
    (r"Software\Microsoft\Edge\NativeMessagingHosts", "Microsoft Edge"),
    (r"Software\Google\Chrome\NativeMessagingHosts", "Google Chrome"),
]


def get_manifest_path() -> Path:
    """Return absolute path to Native Messaging Host manifest file."""
    return Path(__file__).resolve().parent / f"{HOST_NAME}.json"


def register_host(manifest_path: Path | None = None) -> list[str]:
    """Register the manifest path under HKCU for Edge and Chrome.

    Returns:
        List of registered browser names.
    """
    if sys.platform != "win32":
        logger.warning("Native messaging registry registration is only supported on Windows.")
        return []

    import winreg

    manifest = (manifest_path or get_manifest_path()).resolve()
    if not manifest.is_file():
        raise FileNotFoundError(f"Manifest file not found: {manifest}")

    manifest_str = str(manifest)
    registered = []

    for subkey_base, browser_name in REGISTRY_TARGETS:
        key_path = f"{subkey_base}\\{HOST_NAME}"
        try:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, manifest_str)
            registered.append(browser_name)
            logger.info("Successfully registered native host for %s at HKCU\\%s", browser_name, key_path)
        except Exception as exc:
            logger.error("Failed to register native host for %s: %s", browser_name, exc)

    return registered


def unregister_host() -> list[str]:
    """Remove Native Messaging Host registry keys from HKCU for Edge and Chrome."""
    if sys.platform != "win32":
        return []

    import winreg

    unregistered = []
    for subkey_base, browser_name in REGISTRY_TARGETS:
        key_path = f"{subkey_base}\\{HOST_NAME}"
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
            unregistered.append(browser_name)
            logger.info("Unregistered %s at HKCU\\%s", browser_name, key_path)
        except FileNotFoundError:
            pass
        except Exception as exc:
            logger.error("Failed to unregister %s: %s", browser_name, exc)

    return unregistered


def is_host_registered() -> dict[str, bool]:
    """Check if native host is currently registered in Edge and Chrome."""
    if sys.platform != "win32":
        return {"Microsoft Edge": False, "Google Chrome": False}

    import winreg

    results = {}
    for subkey_base, browser_name in REGISTRY_TARGETS:
        key_path = f"{subkey_base}\\{HOST_NAME}"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, "")
                results[browser_name] = bool(val and Path(val).is_file())
        except Exception:
            results[browser_name] = False

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Register VK Dub Native Messaging Host")
    parser.add_argument("--uninstall", action="store_true", help="Remove registration")
    parser.add_argument("--check", action="store_true", help="Check registration status")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.check:
        status = is_host_registered()
        for browser, ok in status.items():
            print(f"  {browser}: {'REGISTERED' if ok else 'NOT REGISTERED'}")
        return

    if args.uninstall:
        done = unregister_host()
        print(f"Unregistered for: {', '.join(done) or 'None'}")
    else:
        done = register_host()
        print(f"Registered for: {', '.join(done) or 'None'}")
        print(f"Manifest path: {get_manifest_path()}")


if __name__ == "__main__":
    main()
