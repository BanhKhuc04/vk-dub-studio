import logging
import re
import sys
from typing import Any

_secrets: set[str] = set()


def remember_secret(value: str) -> None:
    if value:
        _secrets.add(value)


def redact(message: str) -> str:
    for secret in sorted(_secrets, key=len, reverse=True):
        message = message.replace(secret, "[REDACTED]")
    return re.sub(r"AIza[\w-]{20,}", "[REDACTED]", message)


class SecretFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        if record.exc_info:
            # Tracebacks may contain request headers. Preserve only the exception class.
            record.msg += f" ({record.exc_info[0].__name__ if record.exc_info[0] else 'error'})"
            record.exc_info = None
            record.exc_text = None
        return True


class CredentialStore:
    """Explicit OS backend; never fall back to a plaintext keyring plugin."""

    service = "VKDubStudio"
    account = "gemini-api-key"

    def __init__(self, backend: Any = None) -> None:
        self._backend = backend

    def _get_backend(self) -> Any:
        if self._backend is None:
            if sys.platform != "win32":
                raise RuntimeError("Lưu khóa yêu cầu Windows Credential Manager.")
            from keyring.backends.Windows import WinVaultKeyring

            self._backend = WinVaultKeyring()
        return self._backend

    def get(self) -> str | None:
        try:
            value: str | None = self._get_backend().get_password(self.service, self.account)
            if value:
                remember_secret(value)
            return value
        except Exception:
            raise RuntimeError("Không đọc được Windows Credential Manager.") from None

    def save(self, value: str) -> None:
        value = value.strip()
        if not value or len(value) > 1024 or any(c.isspace() for c in value):
            raise ValueError("API key trống hoặc không hợp lệ.")
        remember_secret(value)
        try:
            self._get_backend().set_password(self.service, self.account, value)
        except Exception:
            raise RuntimeError("Không lưu được khóa vào Windows Credential Manager.") from None

    def delete(self) -> None:
        try:
            if self.get():
                self._get_backend().delete_password(self.service, self.account)
        except Exception:
            raise RuntimeError("Không xóa được khóa khỏi Windows Credential Manager.") from None


class VbeeTokenStore(CredentialStore):
    account = "vbee-access-token"


class VbeeAppStore(CredentialStore):
    account = "vbee-app-id"


class ElevenLabsKeyStore(CredentialStore):
    account = "elevenlabs-api-key"
