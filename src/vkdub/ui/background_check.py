"""Background setup checks independent of processing jobs."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal


class BackgroundCheck(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    active: set["BackgroundCheck"] = set()

    def __init__(self, operation: Callable[[], Any]) -> None:
        super().__init__()
        self.operation = operation
        self.active.add(self)
        self.finished.connect(self._release)

    def run(self) -> None:
        try:
            self.succeeded.emit(self.operation())
        except Exception:
            self.failed.emit("Không kiểm tra được cấu hình. Hãy thử lại.")
        finally:
            self.operation = lambda: None

    def _release(self) -> None:
        self.active.discard(self)
        self.deleteLater()

    @classmethod
    def shutdown(cls) -> None:
        # Only process teardown waits for bounded network/subprocess checks.
        for job in list(cls.active):
            job.wait()
        cls.active.clear()
