"""VoiceProvider abstraction and extensible provider implementations for Vbee."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from vkdub.domain.project import Project


class VoiceProvider(Protocol):
    """General protocol for voice synthesis providers (Browser automation, API, etc.)."""

    name: str

    async def execute_dubbing(
        self,
        project: Project,
        srt_path: Path,
        progress_callback: Callable[[int, str], None],
        check_cancel: Callable[[], None],
    ) -> Path:
        """Execute the dubbing workflow and return the path to the downloaded audio."""
        ...

    async def close(self) -> None:
        """Release any held network or browser resources."""
        ...


class VbeeBrowserProvider:
    """Vbee Voice Provider implementation backed by Playwright browser automation."""

    name = "vbee_browser"

    def __init__(
        self,
        downloads_dir: Path | None = None,
        headless: bool = False,
    ) -> None:
        self.downloads_dir = downloads_dir
        self.headless = headless
        self._automation: Any = None

    async def execute_dubbing(
        self,
        project: Project,
        srt_path: Path,
        progress_callback: Callable[[int, str], None],
        check_cancel: Callable[[], None],
    ) -> Path:
        """Coordinate browser automation steps from upload to download."""
        from playwright.async_api import async_playwright

        from vkdub.integrations.vbee.automation import VbeeBrowserAutomation
        from vkdub.integrations.vbee.session import create_vbee_browser_context

        progress_callback(15, "Đang khởi chạy trình duyệt…")
        check_cancel()

        async with async_playwright() as playwright:
            context = await create_vbee_browser_context(
                playwright=playwright,
                downloads_path=self.downloads_dir,
                headless=self.headless,
            )
            automation = VbeeBrowserAutomation(context, self.downloads_dir)
            self._automation = automation

            try:
                progress_callback(25, "Đang mở Vbee Dubbing Studio…")
                await automation.open_dubbing_studio()
                check_cancel()

                # Verify authentication
                logged_in = await automation.is_logged_in()
                if not logged_in:
                    progress_callback(30, "Chờ đăng nhập Vbee trên trình duyệt…")
                    # Wait for user to log in interactively
                    await automation.wait_for_user_login(
                        check_cancel=check_cancel,
                        progress_callback=lambda msg: progress_callback(35, msg),
                    )

                progress_callback(45, "Đang tải file SRT lên hệ thống Vbee…")
                check_cancel()
                await automation.upload_srt(srt_path)

                progress_callback(55, "Đang bắt đầu chuyển phụ đề…")
                check_cancel()
                await automation.submit_conversion()

                progress_callback(60, "Vbee đang chuyển đổi phụ đề thành voice…")
                await automation.wait_for_completion(
                    check_cancel=check_cancel,
                    progress_callback=progress_callback,
                )

                progress_callback(90, "Đang tải file âm thanh kết quả…")
                check_cancel()
                target_dir = self.downloads_dir or Path(srt_path.parent)
                audio_path = await automation.download_output_audio(target_dir)

                progress_callback(95, "Tải file hoàn tất!")
                return audio_path

            finally:
                await automation.close()
                self._automation = None

    async def close(self) -> None:
        if self._automation:
            await self._automation.close()
            self._automation = None
