import json
import math
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from vkdub.domain.translation import GEMINI_MODEL
from vkdub.services.cache_service import atomic_json
from vkdub.utils.paths import data_root


def detect_default_capcut_draft_root() -> Path | None:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if not local_appdata:
        return None
    draft_dir = Path(local_appdata) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
    return draft_dir if draft_dir.is_dir() else None


def get_canonical_capcut_draft_root() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    return Path(local_appdata) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"


def detect_default_workspace_root() -> Path:
    return data_root()


@dataclass
class AppSettings:
    schema_version: int = 2
    wizard_completed: bool = False
    gemini_model: str = GEMINI_MODEL
    tts_backend: str = "vieneu_local"  # "vieneu_local" | "capcut_tts" | "vbee"
    selected_voice: str = ""
    voice_speed: float = 1.0
    capcut_draft_root: str = ""
    workspace_root: str = ""
    source_language: str = "auto"
    target_language: str = "vi"
    auto_update: bool = True
    theme: str = "dark"
    voice_volume: float = 100.0
    original_volume: float = 20.0
    vieneu_model: str = ""
    vieneu_runtime: str = ""
    default_output: str = ""
    autosave: bool = True
    vbee_mode: str = "browser"  # "browser" | "api"
    capcut_version: str = ""  # e.g. "7.7.0" or "" for auto-detect

    def __post_init__(self) -> None:
        if self.schema_version != 2:
            raise ValueError("Phiên bản cài đặt chưa được hỗ trợ.")
        for flag in (self.wizard_completed, self.auto_update, self.autosave):
            if type(flag) is not bool:
                raise ValueError("Cài đặt bật/tắt không hợp lệ.")
        if self.tts_backend not in ("vieneu_local", "capcut_tts", "vbee"):
            raise ValueError("Voice Engine không hợp lệ.")
        if self.vbee_mode not in ("browser", "api"):
            raise ValueError("Chế độ Vbee không hợp lệ.")
        if not isinstance(self.gemini_model, str) or not re.fullmatch(
            r"[A-Za-z0-9._-]{1,120}", self.gemini_model
        ):
            raise ValueError("Tên model Gemini không hợp lệ.")
        for value in (
            self.selected_voice,
            self.capcut_draft_root,
            self.workspace_root,
            self.vieneu_model,
            self.vieneu_runtime,
            self.default_output,
            self.capcut_version,
        ):
            if not isinstance(value, str) or "\0" in value:
                raise ValueError("Cài đặt đường dẫn/giọng không hợp lệ.")
        for number, low, high in (
            (self.voice_speed, 0.8, 1.3),
            (self.voice_volume, 0, 200),
            (self.original_volume, 0, 100),
        ):
            if (
                type(number) not in (int, float)
                or not math.isfinite(number)
                or not low <= number <= high
            ):
                raise ValueError("Tốc độ/âm lượng không hợp lệ.")
        if self.selected_voice and not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", self.selected_voice):
            raise ValueError("Mã giọng đã lưu không hợp lệ.")
        if self.source_language not in ("auto", "vi", "en", "zh", "ja", "ko"):
            raise ValueError("Ngôn ngữ nguồn không hợp lệ.")
        if self.target_language != "vi" or self.theme != "dark":
            raise ValueError("Ngôn ngữ đích/giao diện chưa được hỗ trợ.")
        if not self.capcut_draft_root:
            detected = detect_default_capcut_draft_root()
            if detected is not None:
                self.capcut_draft_root = str(detected)
            else:
                self.capcut_draft_root = str(get_canonical_capcut_draft_root())
        if not self.workspace_root:
            self.workspace_root = str(detect_default_workspace_root())


def load_app_settings() -> AppSettings:
    path = data_root() / "v2-settings.json"
    if not path.exists():
        return AppSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            fields = AppSettings.__dataclass_fields__
            return AppSettings(**{k: v for k, v in data.items() if k in fields})
    except Exception:
        pass
    return AppSettings()


def save_app_settings(settings: AppSettings) -> None:
    path = data_root() / "v2-settings.json"
    validated = AppSettings(**asdict(settings))
    # Keep the previous bytes, including pre-v2/invalid settings, before an explicit save.
    if path.exists():
        backup = path.with_suffix(".json.bak")
        if not backup.exists():
            backup.write_bytes(path.read_bytes())
    atomic_json(path, asdict(validated))
