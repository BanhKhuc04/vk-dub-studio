"""Unit tests for production packaging paths, resource resolution, and update system."""

import os
import sys
from pathlib import Path

import pytest

from vkdub.media.process import find_tool
from vkdub.services.update_service import UpdateInfo, is_newer_version
from vkdub.utils.paths import data_root, resource_path
from vkdub.version import __version__


def test_version_is_semantic():
    parts = __version__.split(".")
    assert len(parts) >= 3
    assert all(p.isdigit() for p in parts[:3])
    assert __version__ == "2.1.3"


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
        version="2.1.4",
        published_at="2026-09-07T00:00:00Z",
        installer_url="https://github.com/vanhkhuc/vk-dub-studio/releases/download/v2.1.4/VKDubStudio-Setup-2.1.4.exe",
        sha256="a" * 64,
        changelog=("Sửa lỗi cập nhật",),
        file_size_bytes=100000000,
    )
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


def test_bundled_model_detected_by_model_service():
    from vkdub.services.model_service import model_directory, model_ready

    assert model_ready("base") is True
    path = model_directory("base")
    assert path.is_dir()
    assert (path / "model.bin").is_file()

