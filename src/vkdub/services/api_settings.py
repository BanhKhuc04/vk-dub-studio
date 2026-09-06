import json
import math
from dataclasses import asdict, dataclass

from vkdub.services.cache_service import atomic_json
from vkdub.utils.paths import data_root


@dataclass(frozen=True)
class ApiSettings:
    mode: str = "FREE_TIER"
    usd_vnd: float = 25000
    budget_vnd: float = 0
    warning_percent: float = 80

    def __post_init__(self) -> None:
        if self.mode not in ("FREE_TIER", "PAID"):
            raise ValueError("Chế độ tài khoản không hợp lệ.")
        for value in (self.usd_vnd, self.budget_vnd, self.warning_percent):
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Cài đặt chi phí không hợp lệ.")
        if not 1 <= self.usd_vnd <= 1_000_000 or not 0 <= self.budget_vnd <= 1_000_000_000:
            raise ValueError("Tỷ giá hoặc ngân sách ngoài phạm vi.")
        if not 1 <= self.warning_percent <= 100:
            raise ValueError("Ngưỡng cảnh báo phải từ 1 đến 100%.")


def load_settings() -> ApiSettings:
    path = data_root() / "api-settings.json"
    if not path.exists():
        return ApiSettings()
    try:
        if path.stat().st_size > 4096:
            raise ValueError
        return ApiSettings(**json.loads(path.read_text(encoding="utf-8")))
    except (TypeError, ValueError):
        raise ValueError("Cài đặt API bị hỏng; mở API & Chi phí để lưu lại.") from None


def save_settings(settings: ApiSettings) -> None:
    atomic_json(data_root() / "api-settings.json", asdict(settings))
