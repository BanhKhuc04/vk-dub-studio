"""UI unit tests for VbeeWorkflowDialog and VbeeController."""

from unittest.mock import MagicMock

from PySide6.QtCore import QObject

from vkdub.integrations.vbee.state import WorkflowState
from vkdub.ui.vbee_controller import VbeeController
from vkdub.ui.vbee_workflow_dialog import VbeeWorkflowDialog


class DummyMainWindow(QObject):
    """Dummy MainWindow mimicking the interface required by VbeeController."""

    def __init__(self) -> None:
        super().__init__()
        self.busy = False
        self.dirty = False
        self.project = MagicMock()
        self.tools = MagicMock()
        self.tools.paths = {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"}
        self.left = MagicMock()
        self.review = MagicMock()
        self.transcription = MagicMock()

    def log(self, msg: str) -> None:
        pass

    def _error(self, msg: str) -> None:
        pass

    def _refresh(self) -> None:
        pass


def test_vbee_workflow_dialog_initial_state(qtbot) -> None:
    """Verify dialog initializes with correct widgets, checklist items and disabled buttons."""
    window = DummyMainWindow()
    controller = VbeeController(window)
    dialog = VbeeWorkflowDialog(controller)
    qtbot.addWidget(dialog)

    assert dialog.isVisible() is False
    assert len(dialog.step_labels) == 6
    assert dialog.close_button.isEnabled() is False
    assert dialog.stop_button.isEnabled() is True
    assert dialog.progress_bar.value() == 0


def test_vbee_workflow_dialog_state_transitions(qtbot) -> None:
    """Verify dialog checklist icons update appropriately on state transitions."""
    window = DummyMainWindow()
    controller = VbeeController(window)
    dialog = VbeeWorkflowDialog(controller)
    qtbot.addWidget(dialog)

    # Transition to EXPORTING_SRT
    dialog.update_state(WorkflowState.EXPORTING_SRT, "Đang xuất SRT…")
    assert "●" in dialog.step_labels["export"].text()

    # Transition to OPENING_VBEE
    dialog.update_state(WorkflowState.OPENING_VBEE, "Đang mở Vbee…")
    assert "✓" in dialog.step_labels["export"].text()
    assert "●" in dialog.step_labels["open"].text()

    # Transition to LOGIN_REQUIRED
    dialog.update_state(WorkflowState.LOGIN_REQUIRED, "Vui lòng đăng nhập…")
    assert "⚠" in dialog.step_labels["open"].text()

    # Transition to READY
    dialog.update_state(WorkflowState.READY, "Hoàn tất!")
    for lbl in dialog.step_labels.values():
        assert "✓" in lbl.text()
    assert dialog.close_button.isEnabled() is True
    assert dialog.stop_button.isEnabled() is False
    assert dialog.progress_bar.value() == 100


def test_vbee_workflow_dialog_cancel_emitted(qtbot) -> None:
    """Verify clicking stop_button emits cancel_requested signal."""
    window = DummyMainWindow()
    controller = VbeeController(window)
    dialog = VbeeWorkflowDialog(controller)
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.cancel_requested, timeout=1000):
        dialog.stop_button.click()

    assert dialog.stop_button.isEnabled() is False


def test_app_settings_vbee_backend() -> None:
    """Verify AppSettings accepts 'vbee' as tts_backend without error."""
    import pytest

    from vkdub.services.app_settings import AppSettings

    settings = AppSettings(tts_backend="vbee")
    assert settings.tts_backend == "vbee"

    with pytest.raises(ValueError, match="Voice Engine không hợp lệ"):
        AppSettings(tts_backend="unsupported_engine")


def test_vbee_voice_catalog() -> None:
    """Verify voice_catalog loads default Vbee voices for 'vbee' backend."""
    from vkdub.services.voice_catalog import read_catalog

    rows = read_catalog("vbee")
    assert len(rows) >= 5
    ids = [r["id"] for r in rows]
    assert "vbee-studio-default" in ids
    assert "vbee-ngoc-huyen" in ids


def test_vbee_health_check() -> None:
    """Verify check_tts_backend returns valid HealthResult for 'vbee'."""
    from vkdub.services.health_service import check_tts_backend

    res = check_tts_backend("vbee")
    assert res.title == "Vbee Dubbing Studio"
    assert res.code in ("VBEE_READY", "VBEE_BROWSER_MISSING")


def test_studio_voice_controller_vbee_delegation() -> None:
    """Verify StudioVoiceController.start delegates to vbee_controller when provider is 'vbee'."""
    from vkdub.ui.studio_voice_controller import StudioVoiceController

    window = DummyMainWindow()
    window.legacy_tts_enabled = False
    window.vbee_controller = MagicMock()
    window.vbee_controller.start_workflow.return_value = True

    # Setup project with script and approved state
    window.project.is_approved = True
    window.project.require_approval = MagicMock()
    window.project.script = MagicMock()
    window.project.script.lines = [MagicMock(id="line-1")]
    window.project.voice = MagicMock(provider="vbee", voice_id="vbee-studio-default")

    controller = StudioVoiceController(window)
    controller.configured = True
    controller.backend = "vbee"
    controller.catalog = [{"id": "vbee-studio-default", "name": "Default"}]

    started = controller.start()
    assert started is True
    window.vbee_controller.start_workflow.assert_called_once()


def test_vbee_controller_api_mode_missing_credentials(monkeypatch, tmp_path) -> None:
    """VbeeController blocks start and notifies user when Vbee API credentials are missing."""
    from vkdub.services.app_settings import AppSettings, save_app_settings

    monkeypatch.setattr("vkdub.services.app_settings.data_root", lambda: tmp_path)
    save_app_settings(AppSettings(vbee_mode="api"))

    monkeypatch.setattr("vkdub.services.credential_service.VbeeAppStore.get", lambda self: None)
    monkeypatch.setattr("vkdub.services.credential_service.VbeeTokenStore.get", lambda self: None)
    monkeypatch.setattr("vkdub.ui.vbee_controller.validate_project_for_vbee", lambda p: None)

    window = DummyMainWindow()
    window.open_settings = MagicMock()
    window._error = MagicMock()

    controller = VbeeController(window)
    started = controller.start_workflow()

    assert started is False
    window._error.assert_called_once()
    assert "Chưa cấu hình App ID hoặc Access Token" in window._error.call_args[0][0]
    window.open_settings.assert_called_once_with(2)


def test_vbee_controller_api_mode_with_credentials(monkeypatch, tmp_path) -> None:
    """VbeeController instantiates VbeeApiProvider when API mode has credentials."""
    from vkdub.integrations.vbee.provider import VbeeApiProvider
    from vkdub.services.app_settings import AppSettings, save_app_settings

    monkeypatch.setattr("vkdub.services.app_settings.data_root", lambda: tmp_path)
    save_app_settings(AppSettings(vbee_mode="api"))

    monkeypatch.setattr("vkdub.services.credential_service.VbeeAppStore.get", lambda self: "app-id-123")
    monkeypatch.setattr("vkdub.services.credential_service.VbeeTokenStore.get", lambda self: "token-456")
    monkeypatch.setattr("vkdub.ui.vbee_controller.validate_project_for_vbee", lambda p: None)

    window = DummyMainWindow()
    window.open_settings = MagicMock()
    window._error = MagicMock()
    window.left.speed_combo = MagicMock()
    window.left.speed_combo.currentData.return_value = 1.1

    controller = VbeeController(window)

    # Monkeypatch VbeeWorkflowJob.start to avoid running background thread
    monkeypatch.setattr("vkdub.ui.vbee_controller.VbeeWorkflowJob.start", lambda self: None)

    started = controller.start_workflow()
    assert started is True
    assert controller.job is not None
    assert isinstance(controller.job.provider, VbeeApiProvider)
    assert controller.job.provider.app_id == "app-id-123"
    assert controller.job.provider.token == "token-456"
    assert controller.job.speed == 1.1

