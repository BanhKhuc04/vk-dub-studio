"""App-owned voice IDs and durable reference files; upstream IDs stay in the adapter."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from vkdub.services.app_settings import load_app_settings
from vkdub.services.cache_service import atomic_json
from vkdub.utils.paths import data_root

VIENEU_VERSION = "3.5.0"


def engine_root() -> Path:
    configured = load_app_settings().vieneu_runtime
    return Path(configured).resolve() if configured else data_root() / "engines" / "vieneu"


def engine_python(root: Path | None = None) -> Path:
    import os

    root = root or engine_root()
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def find_system_python() -> Path | None:
    """Locate a valid Python 3 interpreter on Windows that can create venvs."""
    import glob
    import os
    import shutil
    import subprocess
    import sys

    candidates: list[Path] = []

    # 1. If running under normal Python runtime (not frozen)
    if not getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable))

    # 2. Check PATH
    for cmd in ("python", "python3"):
        if found := shutil.which(cmd):
            candidates.append(Path(found))

    # 3. Check Windows py launcher
    if py_cmd := shutil.which("py"):
        try:
            res = subprocess.run(
                [py_cmd, "-3", "-c", "import sys; print(sys.executable)"],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=0x08000000 if os.name == "nt" else 0,
            )
            if res.returncode == 0 and res.stdout.strip():
                candidates.append(Path(res.stdout.strip()))
        except Exception:
            pass

    # 4. Check common installation directories on Windows
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if local_appdata:
        py_dir = Path(local_appdata) / "Programs" / "Python"
        if py_dir.is_dir():
            for sub in sorted(py_dir.glob("Python3*"), reverse=True):
                exe = sub / "python.exe"
                if exe.is_file():
                    candidates.append(exe)

    for pattern in ("C:\\Program Files\\Python3*", "C:\\Program Files (x86)\\Python3*", "C:\\Python3*"):
        for matched in glob.glob(pattern):
            exe = Path(matched) / "python.exe"
            if exe.is_file():
                candidates.append(exe)

    # Validate candidates
    seen = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            if resolved in seen or not resolved.is_file():
                continue
            seen.add(resolved)
            # Verify candidate can import venv
            test = subprocess.run(
                [str(resolved), "-c", "import venv; print(1)"],
                capture_output=True,
                timeout=4,
                creationflags=0x08000000 if os.name == "nt" else 0,
            )
            if test.returncode == 0:
                return resolved
        except Exception:
            continue

    return None



VBEE_DEFAULT_CATALOG: list[dict[str, Any]] = [
    {"id": "vbee-studio-default", "name": "Vbee Studio — Tự động / Mặc định", "custom": False},
    {"id": "vbee-ngoc-huyen", "name": "Ngọc Huyền (Nữ miền Bắc)", "custom": False},
    {"id": "vbee-tuong-vy", "name": "Tường Vy (Nữ miền Nam)", "custom": False},
    {"id": "vbee-mai-phuong", "name": "Mai Phương (Nữ miền Bắc)", "custom": False},
    {"id": "vbee-lan-trinh", "name": "Lan Trinh (Nữ miền Nam)", "custom": False},
    {"id": "vbee-manh-dung", "name": "Mạnh Dũng (Nam miền Bắc)", "custom": False},
    {"id": "vbee-minh-hoang", "name": "Minh Hoàng (Nam miền Nam)", "custom": False},
]


def catalog_path(backend: str = "vieneu_local") -> Path:
    if backend == "capcut_tts":
        return data_root() / "voices" / "capcut.json"
    if backend == "vbee":
        return data_root() / "voices" / "vbee.json"
    return data_root() / "voices" / "catalog.json"


def read_catalog(backend: str = "vieneu_local") -> list[dict[str, Any]]:
    path = catalog_path(backend)
    if not path.is_file():
        if backend == "vbee":
            save_catalog(VBEE_DEFAULT_CATALOG, "vbee")
            return [dict(r) for r in VBEE_DEFAULT_CATALOG]
        return []
    try:
        if path.stat().st_size > 2_000_000:
            raise ValueError
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError
        seen = set()
        for row in rows:
            if (
                not isinstance(row, dict)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", row["id"])
                or row["id"] in seen
                or not isinstance(row["name"], str)
                or not row["name"].strip()
                or type(row["custom"]) is not bool
            ):
                raise ValueError
            seen.add(row["id"])
        return rows
    except (ValueError, KeyError, TypeError, OSError):
        # Keep the corrupt file so it can be recovered; never replace it with defaults.
        raise ValueError("Danh sách giọng bị lỗi. Kiểm tra thư mục giọng trong Cài đặt.") from None


def save_catalog(rows: list[dict[str, Any]], backend: str = "vieneu_local") -> None:
    atomic_json(catalog_path(backend), rows)


def install_presets(presets: list[list[str]]) -> list[dict[str, Any]]:
    rows = [r for r in read_catalog() if r["custom"]]
    for label, upstream_id in presets:
        key = hashlib.sha256((VIENEU_VERSION + ":" + upstream_id).encode()).hexdigest()[:24]
        rows.append(
            {"id": f"vieneu-{key}", "name": label, "upstream_id": upstream_id, "custom": False}
        )
    if not presets:
        raise ValueError("VieNeu chưa trả về giọng mặc định. Chưa xác nhận cài đặt thành công.")
    save_catalog(rows)
    return rows


def find_voice(identifier: str, backend: str = "vieneu_local") -> dict[str, Any]:
    voice = next((r for r in read_catalog(backend) if r["id"] == identifier), None)
    if voice is None:
        raise ValueError("Giọng đã bị xóa hoặc chưa cài. Hãy chọn lại giọng đọc.")
    return voice


def rename_voice(identifier: str, name: str) -> None:
    name = name.strip()
    if not name or len(name) > 100:
        raise ValueError("Tên giọng phải có từ 1 đến 100 ký tự.")
    rows = read_catalog()
    voice = next((r for r in rows if r["id"] == identifier), None)
    if voice is None or not voice["custom"]:
        raise ValueError("Chỉ đổi tên giọng tự thêm.")
    voice["name"] = name
    save_catalog(rows)


def delete_voice(identifier: str) -> None:
    rows = read_catalog()
    voice = next((r for r in rows if r["id"] == identifier), None)
    if voice is None or not voice["custom"]:
        raise ValueError("Chỉ xóa giọng tự thêm.")
    # Retain reference files for old projects/cache; never touch the user's source audio.
    save_catalog([r for r in rows if r["id"] != identifier])
