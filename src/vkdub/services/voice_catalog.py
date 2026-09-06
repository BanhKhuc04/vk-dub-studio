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


def catalog_path(backend: str = "vieneu_local") -> Path:
    return data_root() / "voices" / ("capcut.json" if backend == "capcut_tts" else "catalog.json")


def read_catalog(backend: str = "vieneu_local") -> list[dict[str, Any]]:
    path = catalog_path(backend)
    if not path.is_file():
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
