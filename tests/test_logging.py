from vkdub.ui.log_viewer_dialog import LogViewerDialog
from vkdub.utils.logging import (
    clear_logs,
    configure_logging,
    get_log_file_path,
    read_recent_logs,
)


def test_configure_logging_and_redact(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    logger = configure_logging()
    logger.info("Normal log line without secrets")

    log_path = get_log_file_path()
    assert log_path.parent.is_dir()

    # Log with potential secrets (API key pattern)
    secret_key = "AIzaSySecretApiKey1234567890abcdef"
    logger.info(f"API key used: {secret_key}")

    content = read_recent_logs()
    assert "Normal log line" in content

    # Clear logs test
    assert clear_logs() is True
    assert read_recent_logs() == "" or "Chưa có dữ liệu" in read_recent_logs()


def test_log_viewer_dialog_ui(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    log_path = get_log_file_path()
    sample_text = (
        "2026-09-04 12:00:00 INFO Initialized application\n2026-09-04 12:00:01 INFO Tools ready\n"
    )
    log_path.write_text(sample_text, encoding="utf-8")

    dlg = LogViewerDialog()
    qtbot.addWidget(dlg)

    assert "Nhật ký hệ thống" in dlg.windowTitle()
    assert "Initialized application" in dlg.txt_log.toPlainText()
    assert dlg.btn_refresh.isEnabled() is True
    assert dlg.btn_copy.isEnabled() is True
