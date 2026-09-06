"""Playwright browser automation layer for Vbee Dubbing Studio."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from vkdub.integrations.vbee.errors import (
    VbeeAutomationError,
    VbeeConversionFailedError,
    VbeeDownloadError,
    VbeeQuotaExceededError,
    VbeeTimeoutError,
)
from vkdub.integrations.vbee.selectors import (
    COMPLETION_INDICATORS,
    CONFIRM_MODAL_BUTTONS,
    DEFAULT_NAVIGATION_TIMEOUT_MS,
    DEFAULT_PAGE_TIMEOUT_MS,
    DEFAULT_POLL_INTERVAL_S,
    DEFAULT_PROCESSING_TIMEOUT_S,
    DOWNLOAD_BUTTON_SELECTORS,
    DOWNLOAD_FORMAT_MP3,
    DOWNLOAD_FORMAT_WAV,
    DUBBING_TAB_SELECTORS,
    FILE_INPUT_SELECTORS,
    GENERAL_ERROR_SELECTORS,
    LOGGED_IN_INDICATORS,
    LOGIN_CHECK_INTERVAL_S,
    LOGIN_REQUIRED_INDICATORS,
    LOGIN_WAIT_TIMEOUT_S,
    PROCESSING_INDICATORS,
    QUOTA_ERROR_SELECTORS,
    SUBMIT_CONVERT_BUTTONS,
    UPLOAD_BUTTON_SELECTORS,
    VBEE_DUBBING_URL,
)

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Download, Page

logger = logging.getLogger("vkdub.vbee")


class VbeeBrowserAutomation:
    """Manages browser automation interactions with Vbee Dubbing Studio."""

    def __init__(
        self,
        context: BrowserContext,
        downloads_dir: Path | None = None,
    ) -> None:
        self.context = context
        self.downloads_dir = downloads_dir or Path.cwd()
        self.page: Page | None = None

    async def get_or_create_page(self) -> Page:
        """Get an existing open page or open a new one."""
        pages = self.context.pages
        if pages:
            self.page = pages[0]
        else:
            self.page = await self.context.new_page()
        self.page.set_default_timeout(DEFAULT_PAGE_TIMEOUT_MS)
        self.page.set_default_navigation_timeout(DEFAULT_NAVIGATION_TIMEOUT_MS)
        return self.page

    async def open_dubbing_studio(self) -> None:
        """Navigate to Vbee Dubbing Studio URL."""
        page = await self.get_or_create_page()
        logger.info("Đang điều hướng đến %s", VBEE_DUBBING_URL)
        try:
            await page.goto(VBEE_DUBBING_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)
        except Exception as exc:
            raise VbeeAutomationError(
                f"Không thể kết nối tới Vbee Dubbing Studio: {exc}. Kiểm tra kết nối Internet."
            ) from exc

    async def is_logged_in(self) -> bool:
        """Check whether the user is currently authenticated on Vbee."""
        page = await self.get_or_create_page()
        current_url = page.url.lower()

        # If redirected to login page or auth flow
        if "/login" in current_url or "/auth" in current_url:
            return False

        # Check for explicit login input forms
        for selector in LOGIN_REQUIRED_INDICATORS:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    return False
            except Exception:
                continue

        # Check for logged-in UI elements
        for selector in LOGGED_IN_INDICATORS:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    return True
            except Exception:
                continue

        # If on studio page and no login forms visible, assume logged in
        if "studio.vbee.vn" in current_url:
            return True

        return False

    async def wait_for_user_login(
        self,
        timeout_s: float = LOGIN_WAIT_TIMEOUT_S,
        check_cancel: Callable[[], None] | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> bool:
        """Wait interactively for user to complete manual login on the open browser."""
        page = await self.get_or_create_page()
        start_time = asyncio.get_event_loop().time()

        if progress_callback:
            progress_callback("Vui lòng đăng nhập tài khoản Vbee trên trình duyệt vừa mở…")

        while (asyncio.get_event_loop().time() - start_time) < timeout_s:
            if check_cancel:
                check_cancel()

            logged_in = await self.is_logged_in()
            if logged_in:
                logger.info("Phát hiện phiên đăng nhập Vbee thành công.")
                if progress_callback:
                    progress_callback("Đã đăng nhập thành công. Tiếp tục quy trình…")
                # Navigate back to dubbing page if needed
                if "dubbing" not in page.url.lower():
                    await page.goto(VBEE_DUBBING_URL, wait_until="domcontentloaded")
                    await page.wait_for_timeout(2000)
                return True

            await asyncio.sleep(LOGIN_CHECK_INTERVAL_S)

        raise VbeeTimeoutError(
            f"Hết thời gian chờ đăng nhập ({int(timeout_s)}s). Vui lòng thử lại khi đã sẵn sàng."
        )

    async def ensure_on_dubbing_tab(self) -> None:
        """Ensure the browser is on the Subtitle/Dubbing section of Vbee Studio."""
        page = await self.get_or_create_page()
        current_url = str(page.url).lower() if hasattr(page, "url") else ""
        if "dubbing" not in current_url:
            await page.goto(VBEE_DUBBING_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

        for selector in DUBBING_TAB_SELECTORS:
            try:
                tab = await page.query_selector(selector)
                if tab and await tab.is_visible():
                    await tab.click()
                    await page.wait_for_timeout(1000)
                    break
            except Exception:
                continue

    async def upload_srt(self, srt_path: Path) -> None:
        """Upload the generated SRT subtitle file to Vbee Dubbing Studio."""
        if not srt_path.is_file():
            raise VbeeAutomationError(f"Không tìm thấy file SRT cần upload: {srt_path}")

        page = await self.get_or_create_page()
        await self.ensure_on_dubbing_tab()

        logger.info(
            "Bắt đầu upload file SRT: %s (%d bytes)", srt_path.name, srt_path.stat().st_size
        )

        # 1. Try finding direct file input
        for selector in FILE_INPUT_SELECTORS:
            try:
                input_elem = await page.query_selector(selector)
                if input_elem:
                    await input_elem.set_input_files(str(srt_path.resolve()))
                    logger.info("Đã upload file SRT qua file input: %s", selector)
                    await page.wait_for_timeout(2500)
                    return
            except Exception:
                continue

        # 2. Try clicking upload trigger button with file chooser
        for btn_selector in UPLOAD_BUTTON_SELECTORS:
            try:
                btn = await page.query_selector(btn_selector)
                if btn and await btn.is_visible():
                    async with page.expect_file_chooser(timeout=5000) as fc_info:
                        await btn.click()
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(str(srt_path.resolve()))
                    logger.info("Đã upload file SRT qua file chooser từ nút: %s", btn_selector)
                    await page.wait_for_timeout(2500)
                    return
            except Exception:
                continue

        raise VbeeAutomationError(
            "Không tìm thấy vị trí tải file SRT trên giao diện Vbee. "
            "Có thể giao diện Vbee đã thay đổi cấu trúc selectors."
        )

    async def submit_conversion(self) -> None:
        """Click the Convert / Generate voice button to start synthesis."""
        page = await self.get_or_create_page()

        # Check for immediate quota error before submitting
        await self._check_errors_on_page()

        # Locate convert button
        button_found = False
        for selector in SUBMIT_CONVERT_BUTTONS:
            try:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible() and await btn.is_enabled():
                    await btn.click()
                    button_found = True
                    logger.info("Đã bấm nút chuyển phụ đề: %s", selector)
                    await page.wait_for_timeout(2000)
                    break
            except Exception:
                continue

        if not button_found:
            raise VbeeAutomationError(
                "Không tìm thấy nút 'Chuyển phụ đề' khả dụng trên giao diện Vbee."
            )

        # Check for any confirmation modal (e.g. "Xác nhận trừ credit")
        for modal_btn_sel in CONFIRM_MODAL_BUTTONS:
            try:
                modal_btn = await page.query_selector(modal_btn_sel)
                if modal_btn and await modal_btn.is_visible():
                    await modal_btn.click()
                    logger.info("Đã xác nhận modal: %s", modal_btn_sel)
                    await page.wait_for_timeout(1500)
                    break
            except Exception:
                continue

        # Verify no immediate rejection
        await self._check_errors_on_page()

    async def _check_errors_on_page(self) -> None:
        """Scan DOM for quota warnings or failure alerts."""
        page = await self.get_or_create_page()

        for selector in QUOTA_ERROR_SELECTORS:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    text = (await elem.text_content() or "").strip()
                    raise VbeeQuotaExceededError(
                        f"Vbee thông báo vượt hạn mức/thiếu số dư: {text or 'Hết credit'}"
                    )
            except VbeeQuotaExceededError:
                raise
            except Exception:
                continue

        for selector in GENERAL_ERROR_SELECTORS:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    text = (await elem.text_content() or "").strip()
                    if text and ("lỗi" in text.lower() or "thất bại" in text.lower()):
                        raise VbeeConversionFailedError(f"Vbee báo lỗi: {text}")
            except (VbeeQuotaExceededError, VbeeConversionFailedError):
                raise
            except Exception:
                continue

    async def wait_for_completion(
        self,
        timeout_s: float = DEFAULT_PROCESSING_TIMEOUT_S,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        check_cancel: Callable[[], None] | None = None,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> None:
        """Monitor Vbee processing dynamically until completion without arbitrary sleeps."""
        page = await self.get_or_create_page()
        start_time = asyncio.get_event_loop().time()
        poll_count = 0

        logger.info("Bắt đầu giám sát tiến trình xử lý Vbee (timeout=%.0fs)…", timeout_s)

        while (asyncio.get_event_loop().time() - start_time) < timeout_s:
            if check_cancel:
                check_cancel()

            poll_count += 1
            elapsed = int(asyncio.get_event_loop().time() - start_time)

            # 1. Check for error alerts
            await self._check_errors_on_page()

            # 2. Check if a download button or completion indicator is visible
            for selector in DOWNLOAD_BUTTON_SELECTORS + COMPLETION_INDICATORS:
                try:
                    elem = await page.query_selector(selector)
                    if elem and await elem.is_visible() and await elem.is_enabled():
                        logger.info(
                            "Phát hiện trạng thái hoàn thành trên Vbee sau %ds (selector=%s)",
                            elapsed,
                            selector,
                        )
                        if progress_callback:
                            progress_callback(100, "Vbee đã xử lý xong phụ đề thành công!")
                        return
                except Exception:
                    continue

            # 3. Check for progress status text or progress bar
            progress_msg = f"Vbee đang xử lý phụ đề thành voice… ({elapsed}s)"
            for selector in PROCESSING_INDICATORS:
                try:
                    elem = await page.query_selector(selector)
                    if elem and await elem.is_visible():
                        txt = (await elem.text_content() or "").strip()
                        if txt:
                            progress_msg = f"Vbee: {txt} ({elapsed}s)"
                        break
                except Exception:
                    continue

            # Estimate progress percentage smoothly up to 95% while waiting
            estimated_pct = min(95, max(10, int(elapsed / max(1, timeout_s * 0.4) * 100)))
            if progress_callback:
                progress_callback(estimated_pct, progress_msg)

            await asyncio.sleep(poll_interval_s)

        raise VbeeTimeoutError(
            f"Vbee xử lý quá thời gian quy định ({int(timeout_s)}s). "
            "Có thể job đang ở hàng đợi quá dài hoặc gặp sự cố trên cloud."
        )

    async def download_output_audio(self, target_dir: Path) -> Path:
        """Trigger the download of the completed audio file and save to target_dir."""
        page = await self.get_or_create_page()
        target_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Đang kích hoạt tải file âm thanh từ Vbee…")

        # Find the download button
        download_btn = None
        for selector in DOWNLOAD_BUTTON_SELECTORS:
            try:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible() and await btn.is_enabled():
                    download_btn = btn
                    break
            except Exception:
                continue

        if not download_btn:
            raise VbeeDownloadError(
                "Không tìm thấy nút 'Tải xuống' âm thanh kết quả trên trang Vbee."
            )

        # Listen for the download event and click the button
        try:
            async with page.expect_download(timeout=45000) as download_info:
                await download_btn.click()

                # Handle format sub-options if a dropdown appears (e.g. MP3 / WAV menu)
                for fmt_sel in DOWNLOAD_FORMAT_MP3 + DOWNLOAD_FORMAT_WAV:
                    try:
                        menu_item = await page.query_selector(fmt_sel)
                        if menu_item and await menu_item.is_visible():
                            await menu_item.click()
                            break
                    except Exception:
                        pass

            download: Download = await download_info.value
            suggested_name = download.suggested_filename or "vbee_dubbed_audio.mp3"
            destination = target_dir / suggested_name

            await download.save_as(str(destination))

            if not destination.is_file() or destination.stat().st_size == 0:
                raise VbeeDownloadError(f"Tải file thất bại hoặc file rỗng: {destination}")

            logger.info(
                "Tải thành công file audio từ Vbee: %s (%d bytes)",
                destination.name,
                destination.stat().st_size,
            )
            return destination

        except Exception as exc:
            if isinstance(exc, VbeeDownloadError):
                raise
            raise VbeeDownloadError(f"Lỗi trong quá trình tải file âm thanh: {exc}") from exc

    async def close(self) -> None:
        """Safely close context and associated pages."""
        try:
            if self.context:
                await self.context.close()
        except Exception as exc:
            logger.debug("Lỗi đóng browser context: %s", exc)
