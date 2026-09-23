# Wrapper package to expose src/vkdub as top-level package
import os
import sys
from pathlib import Path

# When running in a PyInstaller frozen bundle, look for bundled modules in _internal/src/vkdub or _internal/vkdub
if getattr(sys, "frozen", False):
    _base = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parent.parent
    for _candidate in (_base / "src" / "vkdub", _base / "vkdub"):
        if _candidate.is_dir() and str(_candidate) not in __path__:
            __path__.append(str(_candidate))
else:
    _src_path = Path(__file__).resolve().parent.parent / "src" / "vkdub"
    if not _src_path.is_dir():
        _src_path = Path(__file__).resolve().parent / "src" / "vkdub"
    if _src_path.is_dir() and str(_src_path) not in __path__:
        __path__.append(str(_src_path))
