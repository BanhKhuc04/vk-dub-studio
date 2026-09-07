"""Playwright browser automation layer for Vbee Dubbing Studio."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit
from uuid import uuid4

from vkdub.integrations.vbee.errors import (
    VbeeAutomationError,
    VbeeConversionFailedError,
    VbeeDownloadError,
    VbeeJobNotFoundError,
    VbeeProcessingFailedError,
    VbeeQuotaExceededError,
    VbeeSubmitError,
    VbeeTimeoutError,
    VbeeUploadError,
    VbeeVoiceNotFoundError,
)
from vkdub.integrations.vbee.selectors import (
    COMPLETION_INDICATORS,
    CONFIRM_MODAL_BUTTONS,
    DEFAULT_NAVIGATION_TIMEOUT_MS,
    DEFAULT_PAGE_TIMEOUT_MS,
    DEFAULT_POLL_INTERVAL_S,
    DEFAULT_PROCESSING_TIMEOUT_S,
    DOWNLOAD_BUTTON_SELECTORS,
    DUBBING_TAB_SELECTORS,
    FILE_INPUT_SELECTORS,
    FORMAT_OPTIONS_MP3,
    GENERAL_ERROR_SELECTORS,
    LOGGED_IN_INDICATORS,
    LOGIN_CHECK_INTERVAL_S,
    LOGIN_REQUIRED_INDICATORS,
    LOGIN_WAIT_TIMEOUT_S,
    PROCESSING_INDICATORS,
    QUOTA_ERROR_SELECTORS,
    SPEED_OPTIONS_1X,
    SPEED_TRIGGER,
    SUBMIT_CONVERT_BUTTONS,
    UPLOAD_BUTTON_SELECTORS,
    VBEE_DUBBING_URL,
    VOICE_NGOC_HUYEN_OPTIONS,
    VOICE_SELECT_TRIGGER,
)
from vkdub.utils.paths import data_root

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Download, Locator, Page

logger = logging.getLogger("vkdub.vbee")

JOB_ROW_SELECTORS = (
    "tr",
    ".MuiTableRow-root",
    ".ant-table-row",
    "div.ant-list-item",
    "div[class*='history-item']",
)


def format_speed_label(speed: float | str) -> str:
    """Format speed value into Vbee display label format (e.g. 1.1 -> '1.1x', 1.0 -> '1x')."""
    if isinstance(speed, str):
        cleaned = speed.strip().rstrip("x").strip()
        try:
            val = float(cleaned)
        except ValueError:
            val = 1.1
    else:
        try:
            val = float(speed)
        except (ValueError, TypeError):
            val = 1.1
    s = f"{val:.2f}".rstrip("0").rstrip(".")
    return f"{s}x"


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
        self._submitted: bool = False

    async def get_or_create_page(self) -> Page:
        """Get an existing open page or open a new one."""
        if self.page and not self.page.is_closed():
            return self.page
        pages = self.context.pages
        if pages:
            self.page = pages[0]
        else:
            self.page = await self.context.new_page()
        self.page.set_default_timeout(DEFAULT_PAGE_TIMEOUT_MS)
        self.page.set_default_navigation_timeout(DEFAULT_NAVIGATION_TIMEOUT_MS)
        return self.page

    @staticmethod
    def _download_destination(target_dir: Path, suggested_name: str) -> Path:
        """Return a traversal-safe, non-overwriting destination for Vbee audio."""
        raw_name = Path(suggested_name.replace("\\", "/")).name
        suffix = Path(raw_name).suffix.lower()
        if suffix not in {".mp3", ".wav", ".m4a", ".aac", ".ogg"}:
            suffix = ".mp3"
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(raw_name).stem).strip("._")
        stem = stem[:100] or "vbee_dubbed_audio"
        destination = target_dir / f"{stem}{suffix}"
        if destination.exists():
            destination = target_dir / f"{stem}_{uuid4().hex[:8]}{suffix}"
        return destination

    @staticmethod
    def cleanup_partial_downloads(target_dir: Path) -> None:
        """Remove only Vbee staging partials; never touch completed user audio."""
        for pattern in ("*.part", "*.crdownload"):
            for partial in target_dir.glob(pattern):
                try:
                    partial.unlink(missing_ok=True)
                except OSError:
                    logger.debug("Không thể dọn file tải dở: %s", partial)

    async def _save_download(self, download: Download, target_dir: Path) -> Path:
        """Persist a Playwright download atomically with a bounded HTTPS fallback."""
        import httpx

        destination = self._download_destination(
            target_dir, download.suggested_filename or "vbee_dubbed_audio.mp3"
        )
        temporary = target_dir / f".{destination.name}.{uuid4().hex}.part"
        max_bytes = 256 * 1024 * 1024
        try:
            try:
                await download.save_as(str(temporary))
            except Exception as save_error:
                logger.debug(
                    "download.save_as failed (%s); attempting bounded direct fetch",
                    save_error,
                )

            if not temporary.is_file() or temporary.stat().st_size == 0:
                url = str(download.url or "")
                parsed = urlsplit(url)
                if (
                    parsed.scheme != "https"
                    or not parsed.hostname
                    or parsed.username is not None
                    or parsed.password is not None
                ):
                    raise VbeeDownloadError("Vbee trả đường dẫn tải audio không an toàn.")
                downloaded = 0
                try:
                    async with httpx.AsyncClient(
                        timeout=httpx.Timeout(60, connect=15), follow_redirects=False
                    ) as client:
                        async with client.stream("GET", url) as response:
                            response.raise_for_status()
                            with temporary.open("wb") as output:
                                async for chunk in response.aiter_bytes():
                                    downloaded += len(chunk)
                                    if downloaded > max_bytes:
                                        raise VbeeDownloadError(
                                            "File audio Vbee vượt giới hạn an toàn 256 MB."
                                        )
                                    output.write(chunk)
                except httpx.HTTPError:
                    raise VbeeDownloadError(
                        "Không thể tải file audio Vbee qua kết nối HTTPS."
                    ) from None

            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise VbeeDownloadError("Vbee trả file audio rỗng.")
            os.replace(temporary, destination)
            return destination
        finally:
            temporary.unlink(missing_ok=True)

    async def dismiss_popups(self) -> None:
        """Dismiss common onboarding modals, policy consent dialogs, and announcement banners."""
        try:
            page = await self.get_or_create_page()
            # 1. Policy consent modal
            cb = page.locator(
                "input[type='checkbox'], .ant-checkbox-input, span.ant-checkbox"
            ).first
            if await cb.is_visible():
                await cb.click()
                await page.wait_for_timeout(300)
                agree_btn = page.locator(
                    "button:has-text('Đồng ý & Tiếp tục'), button:has-text('Tiếp tục')"
                ).first
                if await agree_btn.is_visible():
                    await agree_btn.click()
                    await page.wait_for_timeout(1000)

            # 2. Onboarding survey modal ("Để sau")
            skip_btn = page.get_by_text("Để sau", exact=True).first
            if await skip_btn.is_visible():
                await skip_btn.click()
                await page.wait_for_timeout(1000)

            # 3. Generic close button
            close_btn = page.locator(
                "button.ant-modal-close, .ant-notification-notice-close, button.close-button"
            ).first
            if await close_btn.is_visible():
                await close_btn.click()
        except Exception as exc:
            logger.debug("Dismiss popups check ignored: %s", exc)

    async def open_dubbing_studio(self) -> None:
        """Navigate to Vbee Dubbing Studio URL."""
        page = await self.get_or_create_page()
        logger.info("[VBEE][BROWSER] Đang điều hướng đến %s", VBEE_DUBBING_URL)
        try:
            await page.goto(VBEE_DUBBING_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)
            await self.dismiss_popups()
        except Exception as exc:
            raise VbeeAutomationError(
                f"Không thể kết nối tới Vbee Dubbing Studio: {exc}. Kiểm tra kết nối Internet."
            ) from exc

    async def is_logged_in(self) -> bool:
        """Check whether the user is currently authenticated on Vbee using robust DOM evidence."""
        page = await self.get_or_create_page()
        current_url = page.url.lower()

        # 1. Negative evidence: redirected to login URL
        if "/login" in current_url or "/auth" in current_url:
            return False

        # 2. Negative evidence: visible login forms or password inputs
        for selector in LOGIN_REQUIRED_INDICATORS:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    return False
            except Exception:
                continue

        # 3. Positive evidence: user profile, avatar, or account elements
        for selector in LOGGED_IN_INDICATORS:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    return True
            except Exception:
                continue

        # 4. Positive evidence: authenticated studio workspace elements (upload zone / dubbing tabs)
        if "studio.vbee.vn" in current_url:
            for selector in DUBBING_TAB_SELECTORS + FILE_INPUT_SELECTORS + UPLOAD_BUTTON_SELECTORS:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        return True
                except Exception:
                    continue

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
            raise VbeeUploadError(f"Không tìm thấy file SRT cần upload: {srt_path}")

        page = await self.get_or_create_page()
        await self.ensure_on_dubbing_tab()

        logger.info(
            "Bắt đầu upload file SRT: %s (%d bytes)", srt_path.name, srt_path.stat().st_size
        )

        uploaded = False
        # 1. Try finding direct file input
        for selector in FILE_INPUT_SELECTORS:
            try:
                input_elem = await page.query_selector(selector)
                if input_elem:
                    try:
                        async with page.expect_file_chooser(timeout=5000) as chooser_info:
                            await input_elem.evaluate("input => input.click()")
                        chooser = await chooser_info.value
                        await chooser.set_files(str(srt_path.resolve()))
                    except Exception:
                        # Fallback for pages and test doubles that expose the input
                        # directly without dispatching a native chooser event.
                        await input_elem.set_input_files(str(srt_path.resolve()))
                    selected_files = await input_elem.evaluate(
                        "input => input.files ? input.files.length : 0"
                    )
                    if selected_files != 1:
                        continue
                    logger.info("Đã upload file SRT qua file input: %s", selector)
                    uploaded = True
                    break
            except Exception:
                continue

        # 2. Try clicking upload trigger button with file chooser
        if not uploaded:
            for btn_selector in UPLOAD_BUTTON_SELECTORS:
                try:
                    btn = await page.query_selector(btn_selector)
                    if btn and await btn.is_visible():
                        async with page.expect_file_chooser(timeout=5000) as fc_info:
                            await btn.click()
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(str(srt_path.resolve()))
                        logger.info("Đã upload file SRT qua file chooser từ nút: %s", btn_selector)
                        uploaded = True
                        break
                except Exception:
                    continue

        if not uploaded:
            raise VbeeUploadError(
                "Không tìm thấy vị trí tải file SRT trên giao diện Vbee. "
                "Có thể giao diện Vbee đã thay đổi cấu trúc selectors."
            )

        try:
            await page.wait_for_timeout(2000)
        except Exception:
            pass

    async def ensure_voice_ngoc_huyen(self) -> None:
        """Ensure the dubbing voice is strictly set to HN - Ngọc Huyền."""
        page = await self.get_or_create_page()
        logger.info("Kiểm tra và thiết lập giọng đọc 'HN - Ngọc Huyền'…")

        # 1. Check if Ngọc Huyền is already selected/active
        for selector in VOICE_SELECT_TRIGGER:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    txt = (await elem.text_content() or "").strip()
                    if "ngọc huyền" in txt.lower():
                        logger.info("Giọng đọc hiện tại đã là 'HN - Ngọc Huyền': %s", txt)
                        return
            except Exception:
                continue

        # 2. Click voice selector trigger to open voice dropdown / modal
        opened = False
        for selector in VOICE_SELECT_TRIGGER:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    await elem.click()
                    opened = True
                    try:
                        await page.wait_for_timeout(800)
                    except Exception:
                        pass
                    break
            except Exception:
                continue

        # 3. Check for search input in voice selector modal
        try:
            search_input = await page.query_selector(
                "input[placeholder*='Tìm'], input[placeholder*='giọng'], input[class*='search']"
            )
            if search_input and await search_input.is_visible():
                await search_input.fill("Ngọc Huyền")
                try:
                    await page.wait_for_timeout(500)
                except Exception:
                    pass
        except Exception:
            pass

        # 4. Select Ngọc Huyền from dropdown / list
        selected = False
        for selector in VOICE_NGOC_HUYEN_OPTIONS:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    await elem.click()
                    selected = True
                    logger.info("Đã chọn giọng 'HN - Ngọc Huyền' qua selector: %s", selector)
                    try:
                        await page.wait_for_timeout(1000)
                    except Exception:
                        pass
                    break
            except Exception:
                continue

        if not selected:
            # Fallback text search
            try:
                loc = page.locator("div, span, li, p").filter(has_text="Ngọc Huyền").first
                if await loc.is_visible():
                    await loc.click()
                    selected = True
                    logger.info("Đã chọn giọng 'HN - Ngọc Huyền' qua text filter")
                    try:
                        await page.wait_for_timeout(1000)
                    except Exception:
                        pass
            except Exception:
                pass

        if not selected and not opened:
            logger.info("Không phát hiện bộ chọn giọng đọc hoặc giọng mặc định đã áp dụng.")
            return

        if not selected:
            raise VbeeVoiceNotFoundError(
                "Không tìm thấy giọng 'HN - Ngọc Huyền' trong danh mục giọng đọc Vbee."
            )

    async def ensure_speed(self, speed: float = 1.1) -> None:
        """Verify and set playback / dubbing speed on Vbee (default 1.1x)."""
        target_str = format_speed_label(speed)
        page = await self.get_or_create_page()
        logger.info("Kiểm tra và thiết lập tốc độ đọc %s…", target_str)

        # 1. Check if the current speed input already matches target_str
        try:
            speed_input = page.locator(".speed input, input[placeholder*='Tốc độ']").first
            if await speed_input.is_visible():
                current_val = (await speed_input.input_value() or "").strip()
                if current_val.lower() == target_str.lower():
                    logger.info("Tốc độ đọc hiện tại đã là %s.", target_str)
                    return
        except Exception:
            pass

        # Also check existing text triggers (for legacy/mock pages)
        for selector in SPEED_TRIGGER:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    txt = (await elem.text_content() or "").strip()
                    if txt in (target_str, f"{target_str} (Chuẩn)"):
                        logger.info("Tốc độ đọc hiện tại đã là %s.", target_str)
                        return
                    if target_str == "1x" and txt in ("1.0x", "1.0"):
                        logger.info("Tốc độ đọc hiện tại đã là 1x.")
                        return
            except Exception:
                continue

        # 2. Open speed dropdown
        for selector in (
            ".speed [data-testid='ArrowDropDownIcon']",
            ".speed .MuiAutocomplete-popupIndicator",
            ".speed button",
            *SPEED_TRIGGER,
        ):
            try:
                trigger_locator = page.locator(selector).first
                if await trigger_locator.is_visible():
                    await trigger_locator.click()
                    try:
                        await page.wait_for_timeout(500)
                    except Exception:
                        pass
                    break
            except Exception:
                continue

        # 3. Locate and select target speed option
        selected = False
        target_pattern = re.compile(rf"^\s*{re.escape(target_str)}(\s|$)", re.IGNORECASE)

        try:
            options = page.locator(
                "li.MuiMenuItem-root, .MuiAutocomplete-listbox li, ul[role='listbox'] li"
            )
            count = await options.count()
            for i in range(count):
                opt = options.nth(i)
                txt = (await opt.text_content() or "").strip()
                if target_pattern.match(txt) or txt.lower().startswith(target_str.lower()):
                    await opt.click()
                    selected = True
                    logger.info(
                        "Đã chọn tốc độ %s từ dropdown: %s", target_str, txt.replace("\n", " ")
                    )
                    try:
                        await page.wait_for_timeout(500)
                    except Exception:
                        pass
                    break
        except Exception as exc:
            logger.debug("Lỗi khi quét options tốc độ: %s", exc)

        # Fallback selectors
        if not selected:
            for selector in (
                f"li.MuiMenuItem-root:has-text('{target_str}')",
                f"li:has-text('{target_str}')",
                f"div[role='option']:has-text('{target_str}')",
                f"span:has-text('{target_str}')",
                *(SPEED_OPTIONS_1X if target_str == "1x" else ()),
            ):
                try:
                    option_locator = page.locator(selector).first
                    if await option_locator.is_visible():
                        await option_locator.click()
                        selected = True
                        logger.info("Đã chọn tốc độ %s qua selector: %s", target_str, selector)
                        try:
                            await page.wait_for_timeout(500)
                        except Exception:
                            pass
                        break
                except Exception:
                    continue

        # 4. Verify result
        try:
            speed_input = page.locator(".speed input, input[placeholder*='Tốc độ']").first
            if await speed_input.is_visible():
                current_val = (await speed_input.input_value() or "").strip()
                logger.info("Tốc độ đọc sau thiết lập: %s (kỳ vọng: %s)", current_val, target_str)
        except Exception:
            pass

    async def ensure_speed_1x(self) -> None:
        """Verify and set playback / dubbing speed to 1x (backward compatibility wrapper)."""
        await self.ensure_speed(1.0)

    async def ensure_format_mp3(self) -> None:
        """Verify and select MP3 audio format."""
        page = await self.get_or_create_page()
        logger.info("Kiểm tra và thiết lập định dạng âm thanh MP3…")

        for selector in FORMAT_OPTIONS_MP3:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    cls = await elem.get_attribute("class") or ""
                    checked = await elem.get_attribute("checked") or await elem.get_attribute(
                        "aria-checked"
                    )
                    if "checked" in cls or "active" in cls or checked == "true":
                        logger.info("Định dạng MP3 đã được chọn sẵn.")
                        return
                    await elem.click()
                    logger.info("Đã chọn định dạng MP3: %s", selector)
                    try:
                        await page.wait_for_timeout(500)
                    except Exception:
                        pass
                    return
            except Exception:
                continue

    async def submit_conversion(self) -> None:
        """Click the Convert / Generate voice button to start synthesis exactly once."""
        if self._submitted:
            logger.info("[VBEE][SUBMIT] Bỏ qua vì đã gửi yêu cầu chuyển đổi trước đó.")
            return

        page = await self.get_or_create_page()

        # Locate convert button
        button_found = False
        for selector in SUBMIT_CONVERT_BUTTONS:
            try:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible() and await btn.is_enabled():
                    await btn.click()
                    button_found = True
                    self._submitted = True
                    logger.info("[VBEE][SUBMIT] Đã bấm nút chuyển phụ đề: %s", selector)
                    try:
                        await page.wait_for_timeout(2000)
                    except Exception:
                        pass
                    break
            except Exception:
                continue

        if not button_found:
            raise VbeeSubmitError(
                "Không tìm thấy nút 'Chuyển phụ đề' khả dụng trên giao diện Vbee."
            )

        upload_rejection = await page.query_selector("text=/Phải upload file phụ đề/i")
        if upload_rejection and await upload_rejection.is_visible():
            raise VbeeUploadError(
                "Vbee không nhận tệp SRT vừa chọn. Hãy xuất lại SRT rồi thử lại hoặc "
                "dùng nút 'Tải SRT Vbee' để tải lên thủ công."
            )

        # Check for any confirmation modal (e.g. "Xác nhận trừ credit")
        for modal_btn_sel in CONFIRM_MODAL_BUTTONS:
            try:
                modal_btn = await page.query_selector(modal_btn_sel)
                if modal_btn and await modal_btn.is_visible():
                    await modal_btn.click()
                    logger.info("[VBEE][SUBMIT] Đã xác nhận modal: %s", modal_btn_sel)
                    try:
                        await page.wait_for_timeout(1500)
                    except Exception:
                        pass
                    break
            except Exception:
                continue

        # Verify no immediate rejection
        await self._check_errors_on_page()

    async def _check_errors_on_page(self) -> None:
        """Scan DOM for actionable failures while ignoring low-balance banners."""
        page = await self.get_or_create_page()

        for selector in QUOTA_ERROR_SELECTORS:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    text = self._safe_error_text(await elem.text_content())
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
                    text = self._safe_error_text(await elem.text_content())
                    if text and ("lỗi" in text.lower() or "thất bại" in text.lower()):
                        raise VbeeConversionFailedError(f"Vbee báo lỗi: {text}")
            except (VbeeQuotaExceededError, VbeeConversionFailedError):
                raise
            except Exception:
                continue

    @staticmethod
    def _safe_error_text(raw_text: str | None) -> str:
        """Return a short provider diagnostic without account identifiers."""
        text = re.sub(r"\s+", " ", raw_text or "").strip()
        text = re.sub(
            r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            "[email đã ẩn]",
            text,
            flags=re.IGNORECASE,
        )
        return text[:240]

    async def snapshot_job_rows(self) -> frozenset[str]:
        """Capture normalized job rows so a provider-renamed new job can be identified."""
        page = await self.get_or_create_page()
        rows: set[str] = set()
        for row_selector in JOB_ROW_SELECTORS:
            try:
                candidates = page.locator(row_selector)
                for index in range(await candidates.count()):
                    text = self._normalized_row_text(await candidates.nth(index).inner_text())
                    if text:
                        rows.add(text)
            except Exception:
                continue
        return frozenset(rows)

    @staticmethod
    def _normalized_row_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    async def find_job_row(
        self,
        unique_name: str,
        timeout_s: float = 30.0,
        previous_rows: frozenset[str] | None = None,
    ) -> Locator:
        """Find the submitted job by filename or as a newly inserted provider-renamed row."""
        page = await self.get_or_create_page()
        stem = Path(unique_name).stem
        logger.info("Tìm dòng công việc trên Vbee khớp với tên: %s (hoặc %s)", unique_name, stem)

        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout_s:
            new_row = None
            for row_selector in JOB_ROW_SELECTORS:
                try:
                    candidates = page.locator(row_selector)
                    count = await candidates.count()
                    for i in range(count):
                        row = candidates.nth(i)
                        txt = await row.inner_text()
                        if unique_name in txt or stem in txt:
                            logger.info(
                                "Đã tìm thấy dòng công việc khớp với '%s' (hàng số %d)",
                                stem,
                                i,
                            )
                            return row
                        normalized = self._normalized_row_text(txt)
                        if (
                            previous_rows is not None
                            and normalized
                            and normalized not in previous_rows
                        ):
                            new_row = row
                except Exception:
                    continue

            if new_row is not None:
                logger.info(
                    "Vbee đã đổi tên job; dùng dòng mới xuất hiện sau khi gửi '%s'.",
                    stem,
                )
                return new_row

            try:
                row_selector = (
                    f"tr:has-text('{stem}'), "
                    f".MuiTableRow-root:has-text('{stem}'), "
                    f".ant-table-row:has-text('{stem}')"
                )
                row = page.locator(row_selector).first
                if await row.is_visible():
                    logger.info("Đã tìm thấy dòng công việc qua direct row locator: %s", stem)
                    return row
            except Exception:
                pass

            await asyncio.sleep(1.0)

        raise VbeeJobNotFoundError(
            f"Không tìm thấy dòng công việc cho file '{unique_name}' "
            f"trên bảng danh sách Vbee sau {int(timeout_s)}s."
        )

    async def wait_job_completion(
        self,
        job_row: Locator,
        unique_name: str,
        timeout_s: float = DEFAULT_PROCESSING_TIMEOUT_S,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        check_cancel: Callable[[], None] | None = None,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> None:
        """Monitor the specific job row until processing completes or fails."""
        start_time = asyncio.get_event_loop().time()
        stem = Path(unique_name).stem
        logger.info(
            "Bắt đầu theo dõi tiến trình xử lý cho job '%s' (timeout=%.0fs)…", stem, timeout_s
        )

        while (asyncio.get_event_loop().time() - start_time) < timeout_s:
            if check_cancel:
                check_cancel()

            elapsed = int(asyncio.get_event_loop().time() - start_time)

            await self._check_errors_on_page()

            try:
                row_text = await job_row.inner_text()
                if "thất bại" in row_text.lower() or "lỗi" in row_text.lower():
                    raise VbeeProcessingFailedError(
                        f"Job '{stem}' bị báo lỗi trên Vbee: {row_text.strip()}"
                    )
            except VbeeProcessingFailedError:
                raise
            except Exception:
                pass

            try:
                for sel in DOWNLOAD_BUTTON_SELECTORS + COMPLETION_INDICATORS:
                    btn = job_row.locator(sel).first
                    if await btn.is_visible():
                        logger.info("Job '%s' đã hoàn thành sau %ds!", stem, elapsed)
                        if progress_callback:
                            progress_callback(100, f"Vbee đã xử lý xong file '{stem}'!")
                        return
            except Exception:
                pass

            status_text = f"Vbee đang xử lý '{stem}'… ({elapsed}s)"
            try:
                for p_sel in PROCESSING_INDICATORS:
                    p_elem = job_row.locator(p_sel).first
                    if await p_elem.is_visible():
                        txt = (await p_elem.text_content() or "").strip()
                        if txt:
                            status_text = f"Vbee: {txt} ({elapsed}s)"
                        break
            except Exception:
                pass

            pct = min(95, max(15, int(elapsed / max(1, timeout_s * 0.3) * 100)))
            if progress_callback:
                progress_callback(pct, status_text)

            await asyncio.sleep(poll_interval_s)

        raise VbeeTimeoutError(
            f"Job '{unique_name}' xử lý quá thời gian quy định ({int(timeout_s)}s). "
            "Vui lòng kiểm tra trên giao diện Vbee."
        )

    async def download_from_job_row(
        self,
        job_row: Locator,
        target_dir: Path,
        timeout_ms: int = 45000,
    ) -> Path:
        """Trigger and verify audio download exclusively from the specified job row."""
        page = await self.get_or_create_page()
        target_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup_partial_downloads(target_dir)
        logger.info("Kích hoạt tải file âm thanh từ dòng công việc…")

        download_btn = None
        for selector in DOWNLOAD_BUTTON_SELECTORS:
            try:
                btn = job_row.locator(selector).first
                if await btn.is_visible():
                    download_btn = btn
                    break
            except Exception:
                continue

        if not download_btn:
            try:
                svg = job_row.locator("svg[data-testid*='Download']").first
                if await svg.is_visible():
                    download_btn = svg
            except Exception:
                pass

        if not download_btn:
            raise VbeeDownloadError("Không tìm thấy nút tải xuống trên dòng công việc tương ứng.")

        try:
            async with page.expect_download(timeout=timeout_ms) as download_info:
                await download_btn.click()

            download: Download = await download_info.value
            destination = await self._save_download(download, target_dir)

            logger.info(
                "Tải file audio thành công: %s (%d bytes)",
                destination.name,
                destination.stat().st_size,
            )
            return destination

        except Exception as exc:
            if isinstance(exc, VbeeDownloadError):
                raise
            raise VbeeDownloadError(f"Lỗi khi tải file âm thanh từ Vbee: {exc}") from exc

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

        logger.info("Bắt đầu giám sát tiến trình xử lý Vbee (timeout=%.0fs)…", timeout_s)

        while (asyncio.get_event_loop().time() - start_time) < timeout_s:
            if check_cancel:
                check_cancel()

            elapsed = int(asyncio.get_event_loop().time() - start_time)

            await self._check_errors_on_page()

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
        self.cleanup_partial_downloads(target_dir)

        logger.info("Đang kích hoạt tải file âm thanh từ Vbee…")

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

        try:
            async with page.expect_download(timeout=45000) as download_info:
                await download_btn.click()

            download: Download = await download_info.value
            destination = await self._save_download(download, target_dir)

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

    async def capture_debug_screenshot(self, prefix: str = "vbee_error") -> Path | None:
        """Capture full-page screenshot into logs directory for troubleshooting."""
        try:
            page = await self.get_or_create_page()
            logs_dir = data_root() / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = logs_dir / f"{prefix}_{timestamp}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info("Đã lưu ảnh chụp màn hình debug: %s", screenshot_path)
            return screenshot_path
        except Exception as exc:
            logger.warning("Không thể chụp ảnh màn hình debug: %s", exc)
            return None

    async def close(self) -> None:
        """Safely close context and associated pages."""
        try:
            if self.context:
                await self.context.close()
        except Exception as exc:
            logger.debug("Lỗi đóng browser context: %s", exc)
