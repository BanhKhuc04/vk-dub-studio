"""Windows Registry setup for VK Dub Studio Native Messaging Host."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("vkdub.bridge.registry")

HOST_NAME = "com.vkdub.bridge"
EXTENSION_ID = "bnpmffibedppchkljkcaidgijekgfmgl"

REGISTRY_TARGETS = [
    (r"Software\Microsoft\Edge\NativeMessagingHosts", "Microsoft Edge"),
    (r"Software\Google\Chrome\NativeMessagingHosts", "Google Chrome"),
]


def find_host_executable() -> Path | None:
    """Locate vkdub_host.bat in either installed bundle or development tree."""
    candidates = []

    # 1. If running in PyInstaller frozen environment
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).parent
        candidates.extend([
            app_dir / "_internal" / "tools" / "native_host" / "vkdub_host.bat",
            app_dir / "tools" / "native_host" / "vkdub_host.bat",
        ])

    # 2. Check source tree relative to this file
    source_root = Path(__file__).resolve().parent.parent.parent.parent
    candidates.extend([
        source_root / "tools" / "native_host" / "vkdub_host.bat",
        Path.cwd() / "tools" / "native_host" / "vkdub_host.bat",
    ])

    for cand in candidates:
        if cand.is_file():
            return cand.resolve()
    return None


def default_manifest_path() -> Path:
    """Ensure dynamic manifest file with correct host path exists in LOCALAPPDATA."""
    manifest_dir = (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        / "VKDubStudio"
        / "native_host"
    )
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = manifest_dir / f"{HOST_NAME}.json"

    host_bat = find_host_executable()
    host_path_str = str(host_bat) if host_bat else ""

    manifest_data = {
        "name": HOST_NAME,
        "description": "VK Dub Studio Native Messaging Bridge Host",
        "path": host_path_str,
        "type": "stdio",
        "allowed_origins": [
            f"chrome-extension://{EXTENSION_ID}/"
        ],
    }

    # Write or update manifest with verified path
    try:
        manifest_file.write_text(
            json.dumps(manifest_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("Could not write dynamic manifest: %s", exc)

    return manifest_file


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
                "Registered Native Messaging Host for %s at HKCU\\%s -> %s",
                browser_name,
                key_path,
                manifest_str,
            )
        except Exception as exc:
            logger.warning("Failed to register native host for %s: %s", browser_name, exc)

    return success
