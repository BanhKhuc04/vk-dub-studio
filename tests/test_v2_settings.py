from vkdub.services.app_settings import (
    AppSettings,
    detect_default_capcut_draft_root,
    load_app_settings,
    save_app_settings,
)


def test_app_settings_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path / "data"))
    settings = AppSettings()
    assert settings.wizard_completed is False
    assert settings.gemini_model == "gemini-3.5-flash"
    assert settings.tts_backend == "vieneu_local"
    assert settings.source_language == "auto"
    assert settings.target_language == "vi"
    assert settings.voice_speed == 1.0
    assert settings.voice_volume == 100.0
    assert settings.original_volume == 20.0
    assert settings.capcut_draft_root != ""
    assert settings.workspace_root != ""


def test_app_settings_roundtrip_persistence(tmp_path, monkeypatch):
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path / "data"))
    settings = AppSettings(
        wizard_completed=True,
        gemini_model="gemini-2.5-flash",
        tts_backend="capcut_tts",
        selected_voice="my-custom-voice",
        voice_speed=1.2,
        capcut_draft_root=str(tmp_path / "CapCutDrafts"),
        workspace_root=str(tmp_path / "MyWorkspace"),
        source_language="zh",
        voice_volume=90.0,
        original_volume=15.0,
    )
    save_app_settings(settings)

    loaded = load_app_settings()
    assert loaded.wizard_completed is True
    assert loaded.gemini_model == "gemini-2.5-flash"
    assert loaded.tts_backend == "capcut_tts"
    assert loaded.selected_voice == "my-custom-voice"
    assert loaded.voice_speed == 1.2
    assert loaded.capcut_draft_root == str(tmp_path / "CapCutDrafts")
    assert loaded.workspace_root == str(tmp_path / "MyWorkspace")
    assert loaded.source_language == "zh"
    assert loaded.voice_volume == 90.0
    assert loaded.original_volume == 15.0


def test_capcut_draft_root_detection(tmp_path, monkeypatch):
    mock_localappdata = tmp_path / "AppData" / "Local"
    monkeypatch.setenv("LOCALAPPDATA", str(mock_localappdata))

    # Before dir exists
    assert detect_default_capcut_draft_root() is None

    # After dir created
    draft_dir = mock_localappdata / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
    draft_dir.mkdir(parents=True, exist_ok=True)
    detected = detect_default_capcut_draft_root()
    assert detected == draft_dir
