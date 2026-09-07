import hashlib
from unittest.mock import MagicMock, patch

import pytest

from vkdub.services.update_service import (
    UpdateInfo,
    apply_patch_and_restart,
    apply_update_and_restart,
    download_installer,
    fetch_update_info,
    is_newer_version,
    parse_version,
    verify_sha256,
)
from vkdub.ui.update_dialog import UpdateDialog


def test_parse_version():
    assert parse_version("1.0.0") == (1, 0, 0)
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("V2.10.5") == (2, 10, 5)
    assert parse_version("v1.0-beta.1") == (1, 0, 0)
    assert parse_version("0.5") == (0, 5, 0)


def test_is_newer_version():
    assert is_newer_version("1.1.0", "1.0.0") is True
    assert is_newer_version("1.0.1", "1.0.0") is True
    assert is_newer_version("2.0.0", "1.99.99") is True
    assert is_newer_version("1.0.0", "1.0.0") is False
    assert is_newer_version("0.9.0", "1.0.0") is False
    assert is_newer_version("v1.2.0", "1.1.9") is True


def test_update_info_model():
    valid_hash = "a" * 64
    info = UpdateInfo.from_dict(
        {
            "version": "1.1.0",
            "published_at": "2026-09-04T00:00:00Z",
            "installer_url": "https://example.com/setup.exe",
            "sha256": valid_hash,
            "changelog": ["Thêm tính năng mới", "Sửa lỗi"],
            "file_size_bytes": 1024000,
        }
    )
    assert info.version == "1.1.0"
    assert info.sha256 == valid_hash
    assert len(info.changelog) == 2

    # Invalid hash raises ValueError
    with pytest.raises(ValueError):
        UpdateInfo.from_dict(
            {
                "version": "1.1.0",
                "published_at": "",
                "installer_url": "https://example.com/setup.exe",
                "sha256": "invalid_short_hash",
                "changelog": [],
            }
        )

    with pytest.raises(ValueError, match="Phiên bản"):
        UpdateInfo.from_dict(
            {
                "version": "../../payload",
                "installer_url": "https://example.com/setup.exe",
                "sha256": valid_hash,
                "changelog": [],
            }
        )

    with pytest.raises(ValueError, match="Đường dẫn"):
        UpdateInfo.from_dict(
            {
                "version": "1.1.0",
                "installer_url": "http://example.com/setup.exe",
                "sha256": valid_hash,
                "changelog": [],
            }
        )


def test_verify_sha256(tmp_path):
    sample = tmp_path / "sample.exe"
    data = b"Hello VK Dub Studio installer content"
    sample.write_bytes(data)
    correct_hash = hashlib.sha256(data).hexdigest()

    assert verify_sha256(sample, correct_hash) is True
    assert verify_sha256(sample, correct_hash.upper()) is True
    assert verify_sha256(sample, "0" * 64) is False
    assert verify_sha256(tmp_path / "non_existent.exe", correct_hash) is False


def test_fetch_update_info_mock():
    valid_hash = "b" * 64
    mock_payload = {
        "version": "1.2.0",
        "published_at": "2026-09-04T00:00:00Z",
        "installer_url": "https://example.com/setup.exe",
        "sha256": valid_hash,
        "changelog": ["Cải tiến lớn"],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = "https://example.com/latest.json"
    mock_resp.json.return_value = mock_payload

    with patch("httpx.Client.get", return_value=mock_resp):
        info = fetch_update_info("https://example.com/latest.json")
        assert info is not None
        assert info.version == "1.2.0"

    # Test failure
    mock_resp.status_code = 404
    with patch("httpx.Client.get", return_value=mock_resp):
        assert fetch_update_info("https://example.com/latest.json") is None

    assert fetch_update_info("http://example.com/latest.json") is None


def test_download_installer_checksum_mismatch(tmp_path):
    target = tmp_path / "installer.exe"
    fake_data = b"MZFake installer bytes"

    class FakeResponse:
        status_code = 200
        headers = {"content-length": str(len(fake_data))}
        url = "https://cdn.example.com/test.exe"

        def iter_bytes(self, chunk_size=32768):
            yield fake_data

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def stream(self, method, url):
            class StreamContext:
                def __enter__(self):
                    return FakeResponse()

                def __exit__(self, *args):
                    pass

            return StreamContext()

    with patch("httpx.Client", return_value=FakeClient()):
        # Download with mismatched hash fails
        success = download_installer(
            url="https://example.com/test.exe",
            target_path=target,
            expected_sha256="c" * 64,
        )
        assert success is False
        assert not target.exists()

        # Download with matching hash succeeds
        correct_hash = hashlib.sha256(fake_data).hexdigest()
        success = download_installer(
            url="https://example.com/test.exe",
            target_path=target,
            expected_sha256=correct_hash,
        )
        assert success is True
        assert target.is_file()
        assert target.read_bytes() == fake_data
        assert not target.with_suffix(".exe.part").exists()


def test_download_installer_rejects_insecure_redirect_and_non_executable(tmp_path):
    target = tmp_path / "installer.exe"

    class FakeResponse:
        status_code = 200
        headers = {"content-length": "4"}
        url = "http://cdn.example.com/test.exe"

        def iter_bytes(self, chunk_size=32768):
            yield b"nope"

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def stream(self, method, url):
            class StreamContext:
                def __enter__(self):
                    return FakeResponse()

                def __exit__(self, *args):
                    pass

            return StreamContext()

    with patch("httpx.Client", return_value=FakeClient()):
        assert (
            download_installer(
                "https://example.com/test.exe", target, hashlib.sha256(b"nope").hexdigest()
            )
            is False
        )
    assert not target.exists()


def test_apply_update_reverifies_before_launch(tmp_path):
    installer = tmp_path / "setup.exe"
    payload = b"MZverified installer"
    installer.write_bytes(payload)
    expected_hash = hashlib.sha256(payload).hexdigest()

    with patch("subprocess.Popen") as popen:
        apply_update_and_restart(installer, expected_hash, silent=True)
        args = popen.call_args.args[0]
        assert args[0] == str(installer.resolve())
        assert "/CLOSEAPPLICATIONS" in args
        assert "/SILENT" in args

    installer.write_bytes(b"MZtampered")
    with patch("subprocess.Popen") as popen, pytest.raises(ValueError, match="đã thay đổi"):
        apply_update_and_restart(installer, expected_hash)
    popen.assert_not_called()


def test_legacy_patch_application_is_disabled(tmp_path):
    with pytest.raises(RuntimeError, match="vô hiệu hóa"):
        apply_patch_and_restart(tmp_path / "legacy.zip")


def test_update_dialog_ui(qtbot):
    info = UpdateInfo(
        version="2.0.0",
        published_at="2026-09-04T00:00:00Z",
        installer_url="https://example.com/installer.exe",
        sha256="d" * 64,
        changelog=("Cải thiện hiệu năng", "Giao diện mới"),
    )

    dlg = UpdateDialog(info)
    qtbot.addWidget(dlg)

    assert "2.0.0" in dlg.windowTitle() or "VK Dub Studio" in dlg.windowTitle()
    assert dlg.btn_update.isEnabled() is True
    assert dlg.btn_later.isEnabled() is True
    assert "Cải thiện hiệu năng" in dlg.txt_changelog.toPlainText()
