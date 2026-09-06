import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from vkdub.services.credential_service import SecretFilter


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("vkdub")
    logger.setLevel(logging.INFO)
    logger.addFilter(SecretFilter())
    if logger.handlers:
        return logger
    root = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share")))
    folder = root / "VKDubStudio" / "logs"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = RotatingFileHandler(
            folder / "vkdub.log",
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
    except OSError:
        handler = logging.StreamHandler()
        logger.addHandler(handler)
        logger.exception("Không thể tạo tệp log; dùng stderr.")
        return logger
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    handler.addFilter(SecretFilter())
    logger.addHandler(handler)
    return logger


def get_log_file_path() -> Path:
    """Return the absolute path of the primary log file."""
    root = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share")))
    folder = root / "VKDubStudio" / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "vkdub.log"


def read_recent_logs(max_lines: int = 500) -> str:
    """Read the most recent lines from the log file."""
    log_path = get_log_file_path()
    if not log_path.is_file():
        return "Chưa có dữ liệu nhật ký hệ thống."
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = lines[-max_lines:] if len(lines) > max_lines else lines
        return "\n".join(tail)
    except Exception as exc:
        return f"Không thể đọc tệp log: {exc}"


def clear_logs() -> bool:
    """Clear primary log file contents."""
    log_path = get_log_file_path()
    try:
        if log_path.exists():
            log_path.write_text("", encoding="utf-8")
        return True
    except Exception:
        return False
