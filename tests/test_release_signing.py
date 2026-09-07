from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def load_build_module():
    build_file = Path(__file__).resolve().parents[1] / "packaging" / "build_all.py"
    spec = importlib.util.spec_from_file_location("vkdub_build_all", build_file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_signing_is_optional_for_local_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_build_module()
    monkeypatch.delenv("VANHKHUC_CODESIGN_PFX", raising=False)
    monkeypatch.delenv("VANHKHUC_CODESIGN_PASSWORD", raising=False)
    monkeypatch.delenv("VANHKHUC_REQUIRE_SIGNING", raising=False)

    assert module.signing_configuration() is None


def test_release_signing_fails_closed_when_required(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_build_module()
    monkeypatch.delenv("VANHKHUC_CODESIGN_PFX", raising=False)
    monkeypatch.delenv("VANHKHUC_CODESIGN_PASSWORD", raising=False)
    monkeypatch.setenv("VANHKHUC_REQUIRE_SIGNING", "1")

    with pytest.raises(RuntimeError, match="required"):
        module.signing_configuration()


def test_release_signing_rejects_partial_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_build_module()
    monkeypatch.setenv("VANHKHUC_CODESIGN_PFX", "certificate.pfx")
    monkeypatch.delenv("VANHKHUC_CODESIGN_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="Both"):
        module.signing_configuration()


def test_sign_binary_signs_and_verifies_without_logging_password(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_build_module()
    signtool = tmp_path / "signtool.exe"
    certificate = tmp_path / "certificate.pfx"
    binary = tmp_path / "application.exe"
    for path in (signtool, certificate, binary):
        path.write_bytes(b"test")
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    config = module.SigningConfiguration(signtool, certificate, "top-secret-password")

    module.sign_binary(binary, config)

    assert [call[1] for call in calls] == ["sign", "verify"]
    assert "/tr" in calls[0]
    assert "https://timestamp.digicert.com" in calls[0]
    assert "top-secret-password" not in capsys.readouterr().out
