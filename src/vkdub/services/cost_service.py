import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vkdub.domain.translation import GEMINI_MODEL

DISCLAIMER = "Ước tính — hạn mức thực tế do nhà cung cấp quyết định."


@dataclass(frozen=True)
class ProviderPricing:
    provider: str
    metric: Literal["characters", "input_tokens", "output_tokens", "audio_minutes", "requests"]
    free_quota: float | None
    unit_size: float
    price_per_unit_usd: float
    last_verified_at: str
    source_url: str | None

    def __post_init__(self) -> None:
        if self.metric not in (
            "characters",
            "input_tokens",
            "output_tokens",
            "audio_minutes",
            "requests",
        ):
            raise ValueError("Đơn vị giá không hợp lệ.")
        if not math.isfinite(self.unit_size) or self.unit_size <= 0:
            raise ValueError("Đơn vị giá phải dương.")
        if not math.isfinite(self.price_per_unit_usd) or self.price_per_unit_usd < 0:
            raise ValueError("Giá không hợp lệ.")


def load_pricing(model: str = GEMINI_MODEL) -> list[ProviderPricing]:
    from vkdub.utils.paths import resource_path

    path = resource_path("provider_pricing.json")
    if not path.is_file():
        path = Path(sys.prefix) / "share" / "vk-dub-studio" / "provider_pricing.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get(model)
    if not entries:
        raise ValueError("Chưa có giá đã xác minh cho model này.")
    return [ProviderPricing(**row) for row in entries]


def estimate_usd(input_tokens: int, output_tokens: int, prices: list[ProviderPricing]) -> float:
    if min(input_tokens, output_tokens) < 0:
        raise ValueError("Số token phải không âm.")
    usage = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    # Paid-equivalent estimate. Local counters never prove free-tier entitlement.
    return sum(usage.get(p.metric, 0) / p.unit_size * p.price_per_unit_usd for p in prices)


def estimate_tokens(characters: int, batches: int) -> tuple[int, int]:
    """Planning heuristic, NOT a provider tokenizer or a guaranteed upper bound."""
    return math.ceil(characters / 2) + batches * 600, math.ceil(characters * 0.8) + batches * 100
