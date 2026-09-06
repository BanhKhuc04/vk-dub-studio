import logging
from dataclasses import replace

import pytest

from vkdub.services.api_settings import ApiSettings, load_settings, save_settings
from vkdub.services.cost_service import DISCLAIMER, estimate_tokens, estimate_usd, load_pricing
from vkdub.services.credential_service import CredentialStore, SecretFilter, redact
from vkdub.services.usage_service import UsageLedger, UsageRecorder


def test_paid_equivalent_formula_never_subtracts_free_quota():
    prices = load_pricing()
    assert estimate_usd(1_000_000, 1_000_000, prices) == pytest.approx(10.5)
    assert estimate_usd(100, 200, prices) == pytest.approx(0.00195)
    assert estimate_usd(
        100, 200, [replace(p, free_quota=1_000_000) for p in prices]
    ) == pytest.approx(0.00195)
    assert estimate_tokens(1000, 2) == (1700, 1000)
    assert estimate_tokens(0, 0) == (0, 0)
    assert "Ước tính" in DISCLAIMER


def test_settings_survive_restart_and_exclude_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
    settings = ApiSettings("PAID", 26000, 50000, 70)
    save_settings(settings)
    assert load_settings() == settings
    path = tmp_path / "api-settings.json"
    assert "key" not in path.read_text()
    path.write_text('{"api_key":"must-not-store"}')
    with pytest.raises(ValueError):
        load_settings()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"usd_vnd": float("nan")},
        {"usd_vnd": 0},
        {"budget_vnd": -1},
        {"warning_percent": 101},
        {"mode": "FREE"},
    ],
)
def test_invalid_cost_settings(kwargs):
    with pytest.raises(ValueError):
        ApiSettings(**kwargs)


def test_monthly_usage_unknown_and_reset(tmp_path):
    ledger = UsageLedger(tmp_path / "usage.db")
    recorder = UsageRecorder(ledger)
    one = recorder.begin("gemini-2.5-flash-lite")
    recorder.response(
        one, {"usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 30}}, 200
    )
    recorder.begin("gemini-2.5-flash-lite")
    rejected = recorder.begin("gemini-2.5-flash-lite")
    recorder.response(rejected, {}, 429)
    assert ledger.monthly()["requests"] == 3
    assert ledger.monthly()["unknown"] == 1
    assert ledger.monthly()["output_tokens"] == 30
    assert ledger.monthly("2000-01")["requests"] == 0
    assert UsageLedger(ledger.path).monthly() == ledger.monthly()
    ledger.reset()
    assert ledger.monthly()["requests"] == 0


class MemoryVault:
    def __init__(self):
        self.values = {}

    def get_password(self, service, account):
        return self.values.get((service, account))

    def set_password(self, service, account, value):
        self.values[service, account] = value

    def delete_password(self, service, account):
        del self.values[service, account]


def test_credential_storage_redaction_and_delete():
    vault = MemoryVault()
    store = CredentialStore(vault)
    secret = "test-sensitive-key-12345"
    store.save(secret)
    assert CredentialStore(vault).get() == secret
    assert secret not in redact(f"provider error contains {secret}")
    record = logging.LogRecord("vkdub", logging.ERROR, "", 0, "%s", (secret,), None)
    SecretFilter().filter(record)
    assert secret not in record.getMessage()
    store.delete()
    assert store.get() is None


def test_credential_backend_error_is_sanitized():
    class BrokenVault:
        def set_password(self, *args):
            raise RuntimeError("secret-backend-value")

    with pytest.raises(RuntimeError) as exc:
        CredentialStore(BrokenVault()).save("secret-backend-value")
    assert "secret-backend-value" not in str(exc.value)
