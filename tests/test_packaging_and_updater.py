"""Unit tests for production packaging paths, resource resolution, and update system."""

import sys
import tomllib
from pathlib import Path

from vkdub.media.process import find_tool
from vkdub.services.update_service import UpdateInfo, is_newer_version
from vkdub.utils.paths import data_root, resource_path
from vkdub.version import __version__


def test_version_is_semantic():
    parts = __version__.split(".")
    assert len(parts) >= 3
    assert all(p.isdigit() for p in parts[:3])
    assert __version__ == "2.1.7"


def test_resource_path_resolution(tmp_path):
    # Test resolving known resources
    icon = resource_path("icon.ico")
    assert icon.is_file()
    assert icon.name == "icon.ico"

    pricing = resource_path("provider_pricing.json")
    assert pricing.is_file()
    assert pricing.name == "provider_pricing.json"

    presets = resource_path("subtitle_presets.json")
    assert presets.is_file()


def test_resource_path_supports_standard_wheel_installation(tmp_path, monkeypatch):
    installed = tmp_path / "share" / "vk-dub-studio" / "wheel-only.txt"
    installed.parent.mkdir(parents=True)
    installed.write_text("installed", encoding="utf-8")
    monkeypatch.setattr(sys, "prefix", str(tmp_path))

    assert resource_path("wheel-only.txt") == installed


def test_find_tool_with_bundled_tools(tmp_path, monkeypatch):
    # Ensure explicit env override takes precedence
    fake_exe = tmp_path / "custom_tool.exe"
    fake_exe.write_bytes(b"MZ")
    monkeypatch.setenv("TESTTOOL_PATH", str(fake_exe))
    assert find_tool("testtool") == str(fake_exe)

    # When env override points to missing file, returns None
    monkeypatch.setenv("TESTTOOL_PATH", str(tmp_path / "missing.exe"))
    assert find_tool("testtool") is None


def test_update_manifest_structure():
    info = UpdateInfo(
        version="2.2.0",
        published_at="2026-09-08T00:00:00Z",
        installer_url="https://github.com/vanhkhuc/vk-dub-studio/releases/download/v2.2.0/VKDubStudio-Setup-2.2.0.exe",
        sha256="a" * 64,
        changelog=("Sửa lỗi cập nhật",),
        file_size_bytes=100000000,
        patch_url="https://github.com/vanhkhuc/vk-dub-studio/releases/download/v2.1.7/VKDubStudio-Patch-2.1.7.zip",
        patch_sha256="b" * 64,
        patch_size_bytes=3000000,
    )
    assert info.has_patch is False
    assert is_newer_version(info.version, __version__) is True
    assert is_newer_version("2.1.1", info.version) is False
    assert is_newer_version(__version__, __version__) is False


def test_user_data_directory_is_in_localappdata(monkeypatch):
    monkeypatch.delenv("VKDUB_DATA_DIR", raising=False)
    path = data_root()
    assert "VKDubStudio" in str(path)
    assert not str(path).startswith("C:\\Program Files")


def test_cli_dispatcher_detects_subprocesses(monkeypatch):
    from vkdub.app import run_cli_or_worker

    # No arguments returns None (standard GUI flow)
    monkeypatch.setattr(sys, "argv", ["app.py"])
    assert run_cli_or_worker() is None

    monkeypatch.setattr(sys, "argv", ["app.py", "--vkdub-smoke-test"])
    assert run_cli_or_worker() == 0


def test_cli_dispatcher_runs_explicit_transcription_worker(monkeypatch):
    from vkdub.app import run_cli_or_worker

    monkeypatch.setattr(
        "vkdub.services.transcription_runner.main",
        lambda: 23,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["VK Dub Studio.exe", "--vkdub-transcription-worker", "request.json", "result.json"],
    )
    assert run_cli_or_worker() == 23
    assert sys.argv == ["vkdub.services.transcription_runner", "request.json", "result.json"]


def test_minimal_entrypoint_smoke_dispatch(monkeypatch):
    import app

    monkeypatch.setattr(sys, "argv", ["VK Dub Studio.exe", "--vkdub-smoke-test"])
    assert app._run() == 0


def test_release_versions_are_synchronized():
    package_data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert package_data["project"]["version"] == __version__
    installer_text = Path("installer/VK-Dub-Studio.iss").read_text(encoding="utf-8")
    assert f'#define MyAppVersion "{__version__}"' in installer_text


def test_downloaded_model_detected_by_model_service(tmp_path, monkeypatch):
    from vkdub.services.model_service import model_directory, model_ready

    data_directory = tmp_path / "app-data"
    model = data_directory / "models" / "base"
    model.mkdir(parents=True)
    for filename in ("model.bin", "config.json", "tokenizer.json"):
        (model / filename).write_bytes(b"test")
    monkeypatch.setenv("VKDUB_DATA_DIR", str(data_directory))

    assert model_ready("base") is True
    path = model_directory("base")
    assert path == model
