"""Typed exceptions for Vbee automation integration."""


class VbeeError(Exception):
    """Base exception for all Vbee integration errors."""


class VbeeAutomationError(VbeeError):
    """Raised when browser automation interaction fails."""


class VbeeValidationError(VbeeError):
    """Raised when preconditions for Vbee voice automation are not satisfied."""


class VbeeLoginRequiredError(VbeeError):
    """Raised when Vbee requires user authentication before proceeding."""


class VbeeQuotaExceededError(VbeeError):
    """Raised when Vbee reports insufficient credits, characters, or quota."""


class VbeeConversionFailedError(VbeeError):
    """Raised when Vbee subtitle conversion fails or returns an error status."""


class VbeeTimeoutError(VbeeError):
    """Raised when an operation or job processing exceeds configured timeout."""


class VbeeDownloadError(VbeeError):
    """Raised when downloading audio from Vbee fails or produces an invalid file."""


class VbeeImportError(VbeeError):
    """Raised when importing or slicing downloaded audio into the project fails."""
