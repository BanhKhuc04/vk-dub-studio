import httpx

from vkdub.services.credential_service import CredentialStore
from vkdub.services.health_service import (
    check_capcut_root,
    check_gemini,
    check_tts_backend,
    check_workspace,
)
from vkdub.ui.health_banner import HealthBanner
from vkdub.ui.setup_wizard import SetupWizardDialog


def test_health_checks(tmp_path, monkeypatch):
    # Gemini missing
    monkeypatch.setattr(CredentialStore, "get", lambda self: None)
    gem_res = check_gemini()
    assert gem_res.ok is False
    assert gem_res.action_id == "open_settings_ai"

    # Gemini configured
    monkeypatch.setattr(CredentialStore, "get", lambda self: "AIzaSyTestValidKey1234567890")
    gem_ok = check_gemini(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "name": "models/" + request.url.path.rsplit("/", 1)[-1],
                    "supportedGenerationMethods": ["generateContent"],
                },
            )
        )
    )
    assert gem_ok.ok is True

    # CapCut root missing
    cc_missing = check_capcut_root(str(tmp_path / "nonexistent"))
    assert cc_missing.ok is False
    assert cc_missing.action_id == "open_settings_capcut"

    # CapCut root exists
    cc_dir = tmp_path / "capcut_drafts"
    cc_dir.mkdir()
    cc_ok = check_capcut_root(str(cc_dir))
    assert cc_ok.ok is True

    # Workspace writeable
    ws_dir = tmp_path / "workspace"
    ws_res = check_workspace(str(ws_dir))
    assert ws_res.ok is True

    # TTS backend
    assert check_tts_backend("vieneu_local").ok is False
    assert check_tts_backend("capcut_tts").ok is False


def test_health_banner_widget(qtbot):
    banner = HealthBanner()
    qtbot.addWidget(banner)

    actions = []
    banner.action_requested.connect(actions.append)

    res = check_gemini()
    banner.set_result(res)
    assert banner.isVisible()
    assert banner.title_label.text() == res.title
    assert banner.action_button.isVisible()

    banner.action_button.click()
    assert actions == ["open_settings_ai"]

    banner.close_button.click()
    assert banner.isHidden()


def test_setup_wizard_flow(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(CredentialStore, "get", lambda self: None)
    monkeypatch.setattr(CredentialStore, "save", lambda self, k: None)

    wizard = SetupWizardDialog()
    qtbot.addWidget(wizard)

    # Initial step 1: Gemini
    assert wizard.stack.currentIndex() == 0
    assert wizard.btn_prev.isEnabled() is False

    wizard.gemini_key_input.setText("AIzaSyFakeKeyForTestOnly12345")
    wizard._next_step()

    # Step 2: Voice
    assert wizard.stack.currentIndex() == 1
    assert wizard.btn_prev.isEnabled() is True
    wizard._next_step()

    # Step 3: CapCut
    assert wizard.stack.currentIndex() == 2
    wizard._next_step()

    # Step 4: Workspace
    assert wizard.stack.currentIndex() == 3
    wizard._next_step()

    # Step 5: System check
    assert wizard.stack.currentIndex() == 4
    assert wizard.btn_next.text() == "Hoàn tất ✓"

    qtbot.waitUntil(lambda: wizard.check_job is None, timeout=15000)
    wizard._next_step()  # Triggers finish
    assert wizard.settings.wizard_completed is True
