"""Unit tests for Vbee automation layer and workflow orchestrator using mocked browser."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.integrations.vbee.automation import VbeeBrowserAutomation
from vkdub.integrations.vbee.errors import (
    VbeeDownloadError,
    VbeeQuotaExceededError,
)
from vkdub.integrations.vbee.state import WorkflowState
from vkdub.integrations.vbee.workflow import VbeeVoiceWorkflow


def _make_mock_page(url: str = "https://studio.vbee.vn/studio/dubbing") -> AsyncMock:
    page = AsyncMock()
    page.url = url
    page.set_default_timeout = MagicMock()
    page.set_default_navigation_timeout = MagicMock()
    page.query_selector = AsyncMock(return_value=None)
    page.is_closed = MagicMock(return_value=False)
    mock_loc = MagicMock()
    mock_loc.first = mock_loc
    mock_loc.is_visible = AsyncMock(return_value=False)
    mock_loc.count = AsyncMock(return_value=0)
    mock_loc.input_value = AsyncMock(return_value="")
    mock_loc.click = AsyncMock()
    mock_loc.filter = MagicMock(return_value=mock_loc)
    page.locator = MagicMock(return_value=mock_loc)
    return page


@pytest.mark.anyio
async def test_automation_is_logged_in_detection() -> None:
    """Verify login status detection based on URL and element visibility."""
    mock_context = MagicMock()
    mock_page = _make_mock_page("https://vbee.vn/login")
    mock_context.pages = [mock_page]

    automation = VbeeBrowserAutomation(mock_context)

    # 1. On login URL -> False
    assert await automation.is_logged_in() is False

    # 2. Login password input visible -> False
    mock_page.url = "https://studio.vbee.vn/studio/dubbing"
    mock_elem = AsyncMock()
    mock_elem.is_visible.return_value = True

    async def query_selector(selector: str) -> AsyncMock | None:
        if "password" in selector:
            return mock_elem
        return None

    mock_page.query_selector.side_effect = query_selector
    assert await automation.is_logged_in() is False

    # 3. Avatar visible -> True
    async def query_selector_logged_in(selector: str) -> AsyncMock | None:
        if "avatar" in selector:
            return mock_elem
        return None

    mock_page.query_selector.side_effect = query_selector_logged_in
    assert await automation.is_logged_in() is True


@pytest.mark.anyio
async def test_automation_upload_srt(tmp_path: Path) -> None:
    """Verify upload_srt calls set_input_files on found file input."""
    mock_context = MagicMock()
    mock_page = _make_mock_page()
    mock_context.pages = [mock_page]

    mock_input = AsyncMock()
    mock_page.query_selector.return_value = mock_input

    automation = VbeeBrowserAutomation(mock_context)

    srt_file = tmp_path / "test.srt"
    srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nXin chào\n", encoding="utf-8")

    await automation.upload_srt(srt_file)
    mock_input.set_input_files.assert_called_once_with(str(srt_file.resolve()))


@pytest.mark.anyio
async def test_automation_wait_for_completion_success() -> None:
    """Verify wait_for_completion finishes when download button or completed indicator appears."""
    mock_context = MagicMock()
    mock_page = _make_mock_page()
    mock_context.pages = [mock_page]

    mock_download_btn = AsyncMock()
    mock_download_btn.is_visible.return_value = True
    mock_download_btn.is_enabled.return_value = True

    async def query_selector(selector: str) -> AsyncMock | None:
        if "Tải xuống" in selector:
            return mock_download_btn
        return None

    mock_page.query_selector.side_effect = query_selector

    automation = VbeeBrowserAutomation(mock_context)
    # Should complete immediately
    await automation.wait_for_completion(timeout_s=5.0, poll_interval_s=0.1)


@pytest.mark.anyio
async def test_automation_wait_for_completion_quota_error() -> None:
    """Verify wait_for_completion raises VbeeQuotaExceededError when quota alert is present."""
    mock_context = MagicMock()
    mock_page = _make_mock_page()
    mock_context.pages = [mock_page]

    mock_error = AsyncMock()
    mock_error.is_visible.return_value = True
    mock_error.text_content.return_value = "Tài khoản của bạn đã hết ký tự để chuyển đổi."

    async def query_selector(selector: str) -> AsyncMock | None:
        if "hết ký tự" in selector:
            return mock_error
        return None

    mock_page.query_selector.side_effect = query_selector

    automation = VbeeBrowserAutomation(mock_context)
    with pytest.raises(VbeeQuotaExceededError, match="hết ký tự"):
        await automation.wait_for_completion(timeout_s=2.0, poll_interval_s=0.1)


@pytest.mark.anyio
async def test_automation_download_file_failure(tmp_path: Path) -> None:
    """Verify download_output_audio raises VbeeDownloadError if no download button exists."""
    mock_context = MagicMock()
    mock_page = _make_mock_page()
    mock_context.pages = [mock_page]
    mock_page.query_selector.return_value = None

    automation = VbeeBrowserAutomation(mock_context)
    with pytest.raises(VbeeDownloadError, match="Không tìm thấy nút"):
        await automation.download_output_audio(tmp_path)


@pytest.mark.anyio
async def test_download_is_atomic_and_sanitizes_provider_filename(tmp_path: Path) -> None:
    mock_context = MagicMock()
    automation = VbeeBrowserAutomation(mock_context)
    download = MagicMock()
    download.suggested_filename = "../../unsafe.exe"
    download.url = ""

    async def save_as(target: str) -> None:
        Path(target).write_bytes(b"valid audio")

    download.save_as = AsyncMock(side_effect=save_as)
    result = await automation._save_download(download, tmp_path)

    assert result.parent == tmp_path
    assert result.suffix == ".mp3"
    assert result.read_bytes() == b"valid audio"
    assert not tuple(tmp_path.glob("*.part"))


@pytest.mark.anyio
async def test_download_rejects_insecure_fallback_and_cleans_partial(tmp_path: Path) -> None:
    automation = VbeeBrowserAutomation(MagicMock())
    download = MagicMock()
    download.suggested_filename = "voice.mp3"
    download.url = "http://example.com/voice.mp3"
    download.save_as = AsyncMock(side_effect=OSError("disk interrupted"))

    with pytest.raises(VbeeDownloadError, match="không an toàn"):
        await automation._save_download(download, tmp_path)
    assert not tuple(tmp_path.glob("*.part"))


def test_partial_download_cleanup_is_scoped(tmp_path: Path) -> None:
    (tmp_path / "old.crdownload").write_bytes(b"partial")
    (tmp_path / "old.part").write_bytes(b"partial")
    completed = tmp_path / "voice.mp3"
    completed.write_bytes(b"complete")

    VbeeBrowserAutomation.cleanup_partial_downloads(tmp_path)

    assert completed.read_bytes() == b"complete"
    assert not tuple(tmp_path.glob("*.crdownload"))
    assert not tuple(tmp_path.glob("*.part"))


@pytest.mark.anyio
async def test_workflow_orchestrator_mocked_provider(tmp_path: Path) -> None:
    """Verify VbeeVoiceWorkflow transitions through states cleanly with a mocked provider."""
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\x00" * 1024)

    # Create dummy audio file for provider to return
    dummy_audio = tmp_path / "vbee_result.wav"
    dummy_audio.write_bytes(b"\x00" * 4096)

    project = Project(
        video_path=video,
        target_language="vi",
        script=ScriptDocument((ScriptLine.new(0, 1000, "Xin chào"),)),
    )
    project.approve(True)

    mock_provider = AsyncMock()
    mock_provider.execute_dubbing.return_value = dummy_audio

    observed_states: list[WorkflowState] = []

    def state_tracker(st: WorkflowState, msg: str) -> None:
        observed_states.append(st)

    workflow = VbeeVoiceWorkflow(
        project=project,
        provider=mock_provider,
        ffmpeg="ffmpeg",
        ffprobe="ffprobe",
        state_callback=state_tracker,
        working_dir=tmp_path / "staging",
    )

    # Mock importer's slice_and_import_vbee_audio so this unit test doesn't require real ffmpeg
    from unittest.mock import patch

    with patch("vkdub.integrations.vbee.workflow.slice_and_import_vbee_audio") as mock_slice:
        mock_slice.return_value = {
            "lines_count": 1,
            "master_wav": str(dummy_audio),
            "target_dir": str(tmp_path),
            "total_duration_ms": 1000,
        }

        res = await workflow.run()

        assert res["status"] == "success"
        assert res["lines_count"] == 1
        assert WorkflowState.EXPORTING_SRT in observed_states
        assert WorkflowState.OPENING_VBEE in observed_states
        assert WorkflowState.READY in observed_states
        assert workflow.current_state == WorkflowState.READY


@pytest.mark.anyio
async def test_automation_ensure_voice_ngoc_huyen() -> None:
    """Verify ensure_voice_ngoc_huyen succeeds when trigger or option matches."""
    mock_context = MagicMock()
    mock_page = _make_mock_page()
    mock_context.pages = [mock_page]

    # Voice selector already has Ngọc Huyền
    mock_trigger = AsyncMock()
    mock_trigger.is_visible.return_value = True
    mock_trigger.text_content.return_value = "HN - Ngọc Huyền"
    mock_page.query_selector.return_value = mock_trigger

    automation = VbeeBrowserAutomation(mock_context)
    await automation.ensure_voice_ngoc_huyen()


@pytest.mark.anyio
async def test_automation_ensure_speed_and_format() -> None:
    """Verify ensure_speed_1x and ensure_format_mp3 interact correctly with selectors."""
    mock_context = MagicMock()
    mock_page = _make_mock_page()
    mock_context.pages = [mock_page]

    mock_elem = AsyncMock()
    mock_elem.is_visible.return_value = True
    mock_elem.text_content.return_value = "1.0x"
    mock_elem.get_attribute.return_value = "ant-radio-button-wrapper-checked"
    mock_page.query_selector.return_value = mock_elem

    automation = VbeeBrowserAutomation(mock_context)
    await automation.ensure_speed_1x()
    await automation.ensure_format_mp3()


@pytest.mark.anyio
async def test_automation_ensure_speed_1_1() -> None:
    """Verify ensure_speed(1.1) interacts with dropdown and selects 1.1x."""
    mock_context = MagicMock()
    mock_page = _make_mock_page()
    mock_context.pages = [mock_page]

    # Setup locator behavior for speed input and dropdown items
    mock_input = MagicMock()
    mock_input.is_visible = AsyncMock(return_value=True)
    mock_input.input_value = AsyncMock(return_value="1x")  # Initially 1x

    mock_trigger = MagicMock()
    mock_trigger.is_visible = AsyncMock(return_value=True)
    mock_trigger.click = AsyncMock()

    mock_opt_1_1 = MagicMock()
    mock_opt_1_1.text_content = AsyncMock(return_value="1.1x\nNhanh")
    mock_opt_1_1.click = AsyncMock()

    mock_options = MagicMock()
    mock_options.count = AsyncMock(return_value=1)
    mock_options.nth = MagicMock(return_value=mock_opt_1_1)

    def locator_side_effect(selector: str):
        if "input" in selector:
            loc = MagicMock()
            loc.first = mock_input
            return loc
        if "ArrowDropDownIcon" in selector or "popupIndicator" in selector:
            loc = MagicMock()
            loc.first = mock_trigger
            return loc
        if "MuiMenuItem" in selector or "listbox" in selector:
            return mock_options
        loc = MagicMock()
        loc.first = MagicMock(is_visible=AsyncMock(return_value=False))
        return loc

    mock_page.locator = MagicMock(side_effect=locator_side_effect)

    automation = VbeeBrowserAutomation(mock_context)
    await automation.ensure_speed(1.1)

    # Verify that trigger was clicked to open dropdown and 1.1x option was clicked
    mock_trigger.click.assert_awaited_once()
    mock_opt_1_1.click.assert_awaited_once()


@pytest.mark.anyio
async def test_automation_find_job_row_and_completion() -> None:
    """Verify find_job_row locates row and wait_job_completion detects download button."""
    mock_context = MagicMock()
    mock_page = _make_mock_page()
    mock_context.pages = [mock_page]

    unique_name = "vkdub_test_20260906_120000.srt"

    mock_row = AsyncMock()
    mock_row.inner_text.return_value = f"{unique_name} Hoàn thành"

    # Mock locator query (synchronous in Playwright)
    mock_candidates = MagicMock()
    mock_candidates.count = AsyncMock(return_value=1)
    mock_candidates.nth = MagicMock(return_value=mock_row)

    mock_page.locator = MagicMock(return_value=mock_candidates)

    # Mock download button inside row
    mock_download_btn = AsyncMock()
    mock_download_btn.is_visible.return_value = True
    mock_download_btn.is_enabled.return_value = True
    mock_row.locator = MagicMock(return_value=MagicMock(first=mock_download_btn))

    automation = VbeeBrowserAutomation(mock_context)
    row = await automation.find_job_row(unique_name, timeout_s=2.0)
    assert row is mock_row

    await automation.wait_job_completion(
        job_row=row,
        unique_name=unique_name,
        timeout_s=2.0,
        poll_interval_s=0.05,
    )
