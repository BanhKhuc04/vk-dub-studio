import asyncio
import logging
import threading
from collections.abc import Callable, Coroutine
from typing import Any

from PySide6.QtCore import QThread, Signal

from vkdub.integrations.vbee.errors import VbeeError
from vkdub.providers.gemini_translation import ProviderError
from vkdub.services.credential_service import redact

logger = logging.getLogger("vkdub.cloud_job")


class CloudJob(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(int, str)

    def __init__(self, operation: Callable[[], Coroutine[Any, Any, Any]]) -> None:
        super().__init__()
        self.operation = operation
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def check_cancel(self) -> None:
        if self.cancel_event.is_set():
            raise asyncio.CancelledError

    async def _execute(self) -> Any:
        self.check_cancel()
        task = asyncio.create_task(self.operation())
        try:
            while not task.done():
                await asyncio.wait({task}, timeout=0.1)
                self.check_cancel()
            return await task
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    def run(self) -> None:
        try:
            result = asyncio.run(self._execute())
            self.check_cancel()
            self.succeeded.emit(result)
        except asyncio.CancelledError:
            self.cancelled.emit()
        except (ProviderError, ValueError, VbeeError) as exc:
            logger.warning("CloudJob expected error: %s", exc)
            self.failed.emit(redact(str(exc)))
        except Exception as exc:
            logger.error("CloudJob unexpected error: %s", exc, exc_info=True)
            msg = str(exc)
            if any(
                term in msg
                for term in (
                    "Target closed",
                    "Browser has been closed",
                    "Target page, context or browser has been closed",
                )
            ):
                self.failed.emit("Cửa sổ trình duyệt đã bị đóng.")
            elif "Timeout" in type(exc).__name__ or "timeout" in msg.lower():
                self.failed.emit("Tác vụ xử lý quá thời gian quy định.")
            elif isinstance(exc, (FileNotFoundError, PermissionError, OSError)):
                self.failed.emit("Lỗi truy cập tệp hoặc thư mục.")
            else:
                self.failed.emit("Không thể hoàn thành tác vụ. Vui lòng kiểm tra lại.")
        finally:
            # Release the closure containing the in-memory provider/key after completion.
            self.operation = _empty


async def _empty() -> None:
    pass
