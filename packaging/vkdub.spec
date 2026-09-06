# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

ROOT_DIR = Path(SPECPATH).resolve().parent

datas = [
    (str(ROOT_DIR / 'resources'), 'resources'),
]

# Collect Playwright driver (node.exe, cli.js, package)
try:
    import playwright
    pw_dir = Path(playwright.__file__).parent
    driver_dir = pw_dir / 'driver'
    if driver_dir.is_dir():
        datas.append((str(driver_dir), 'playwright/driver'))
except Exception as exc:
    print(f"Warning: Could not locate playwright driver: {exc}")

# Bundle standalone tools (ffmpeg, ffprobe) if present
if (ROOT_DIR / 'tools').is_dir():
    datas.append((str(ROOT_DIR / 'tools'), 'tools'))

# Bundle offline models (faster-whisper base) if present
if (ROOT_DIR / 'models').is_dir():
    datas.append((str(ROOT_DIR / 'models'), 'models'))

datas += collect_data_files('faster_whisper')
datas += collect_data_files('ctranslate2')
datas += collect_data_files('playwright')

hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'httpx',
    'sounddevice',
    'numpy',
    'ctranslate2',
    'faster_whisper',
    'keyring',
    'keyring.backends',
    'keyring.backends.Windows',
    'playwright',
    'playwright.async_api',
    'playwright._impl._driver',
    'vkdub',
    'vkdub.app',
    'vkdub.version',
    'vkdub.utils.paths',
    'vkdub.utils.logging',
    'vkdub.integrations.vbee.provider',
    'vkdub.integrations.vbee.automation',
    'vkdub.integrations.vbee.session',
    'vkdub.integrations.vbee.workflow',
    'vkdub.providers.vbee_tts',
    'vkdub.providers.vieneu_tts',
    'vkdub.services.update_service',
]
hiddenimports += collect_submodules('vkdub')

icon_path = str(ROOT_DIR / 'resources' / 'icon.ico') if (ROOT_DIR / 'resources' / 'icon.ico').is_file() else None

a = Analysis(
    [str(ROOT_DIR / 'app.py')],
    pathex=[str(ROOT_DIR / 'src'), str(ROOT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'IPython', 'notebook', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VK Dub Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='VK Dub Studio',
)