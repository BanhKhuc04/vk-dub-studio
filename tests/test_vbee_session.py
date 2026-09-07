"""Regression coverage for the single persistent Vbee browser profile."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from vkdub.integrations.vbee.session import (
    create_vbee_browser_context,
    is_vbee_profile_initialized,
    saved_browser_executable,
)


def test_saved_browser_and_initialized_profile_are_reused(tmp_path: Path) -> None:
    profile = tmp_path / "vbee"
    (profile / "Default").mkdir(parents=True)
    (profile / "Local State").write_text("{}", encoding="utf-8")
    browser = tmp_path / "msedge.exe"
    browser.write_bytes(b"browser")
    (profile / "Last Browser").write_text(str(browser), encoding="utf-16")

    assert is_vbee_profile_initialized(profile)
    assert saved_browser_executable(profile) == str(browser)


@pytest.mark.anyio
async def test_context_uses_exact_existing_profile_and_download_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = tmp_path / "canonical-vbee-profile"
    (profile / "Default").mkdir(parents=True)
    (profile / "Local State").write_text("{}", encoding="utf-8")
    browser = tmp_path / "msedge.exe"
    browser.write_bytes(b"browser")
    (profile / "Last Browser").write_text(str(browser), encoding="utf-16")
    downloads = tmp_path / "downloads"

    monkeypatch.setattr(
        "vkdub.integrations.vbee.session.cleanup_stale_profile_processes", lambda _: None
    )
    context = MagicMock()
    playwright = MagicMock()
    playwright.chromium.launch_persistent_context = AsyncMock(return_value=context)

    result = await create_vbee_browser_context(
        playwright,
        profile_dir=profile,
        downloads_path=downloads,
    )

    assert result is context
    kwargs = playwright.chromium.launch_persistent_context.await_args.kwargs
    assert kwargs["user_data_dir"] == str(profile.resolve())
    assert kwargs["executable_path"] == str(browser)
    assert kwargs["downloads_path"] == str(downloads.resolve())
    assert not (tmp_path / "canonical-vbee-profile-2").exists()


def test_untrusted_last_browser_marker_is_ignored(tmp_path: Path) -> None:
    profile = tmp_path / "vbee"
    profile.mkdir()
    executable = tmp_path / "anything.exe"
    executable.write_bytes(b"not a browser")
    (profile / "Last Browser").write_text(str(executable), encoding="utf-16")

    assert saved_browser_executable(profile) is None
