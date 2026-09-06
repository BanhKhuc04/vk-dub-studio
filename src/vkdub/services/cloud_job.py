import asyncio
import threading
from collections.abc import Callable, Coroutine
from typing import Any

from PySide6.QtCore import QThread, Signal

from vkdub.providers.gemini_translation import ProviderError
from vkdub.services.credential_service import redact


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
        except (ProviderError, ValueError) as exc:
            self.failed.emit(redact(str(exc)))
        except Exception:
            self.failed.emit(
                "Không hoàn thành công việc API. Kiểm tra kết nối và quyền ghi dữ liệu cục bộ."
            )
        finally:
            # Release the closure containing the in-memory provider/key after completion.
            self.operation = _empty


async def _empty() -> None:
    pass
