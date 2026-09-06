import os

import pytest

# Unit tests use Qt's offscreen backend to avoid native Windows accessibility/COM
# re-entrancy while fixtures create and destroy many windows. Smoke tests use the
# real desktop platform and verify actual media playback separately.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def isolate_vbee_credentials(monkeypatch, tmp_path):
    # Review acceptance tests must never synthesize against a developer's live account.
    from vkdub.services.credential_service import CredentialStore, VbeeAppStore, VbeeTokenStore
    from vkdub.services.recovery_service import clear_recovery_state
    from vkdub.ui.background_check import BackgroundCheck

    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path / "isolated-app"))

    class MemoryVault:
        values = {}

        def get_password(self, service, account):
            return self.values.get((service, account))

        def set_password(self, service, account, value):
            self.values[service, account] = value

        def delete_password(self, service, account):
            self.values.pop((service, account), None)

    vault = MemoryVault()
    monkeypatch.setattr(CredentialStore, "_get_backend", lambda self: self._backend or vault)
    monkeypatch.setattr("vkdub.services.health_service.fetch_update_info", lambda **kw: None)

    monkeypatch.setattr(VbeeAppStore, "get", lambda self: None)
    monkeypatch.setattr(VbeeTokenStore, "get", lambda self: None)
    clear_recovery_state()
    yield
    BackgroundCheck.shutdown()
