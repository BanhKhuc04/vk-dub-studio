"""Typed exceptions for Vbee automation integration."""


class VbeeError(Exception):
    """Base exception for all Vbee integration errors."""


class VbeeAutomationError(VbeeError):
    """Raised when browser automation interaction fails."""


class VbeeValidationError(VbeeError):
    """Raised when preconditions for Vbee voice automation are not satisfied."""


class VbeeBrowserNotFoundError(VbeeError):
    """Raised when neither Microsoft Edge nor Google Chrome is found on system."""


class VbeeBrowserLaunchFailedError(VbeeError):
    """Raised when launching Playwright persistent browser context fails."""


class VbeeProfileLockedError(VbeeError):
    """Raised when browser profile directory is locked by another running process."""


class VbeeNavigationFailedError(VbeeError):
    """Raised when navigating to Vbee Studio fails or times out."""


class VbeeLoginRequiredError(VbeeError):
    """Raised when Vbee requires user authentication before proceeding."""


class VbeeUploadError(VbeeError):
    """Raised when uploading SRT subtitle file to Vbee fails."""


class VbeeVoiceNotFoundError(VbeeError):
    """Raised when voice HN - Ngọc Huyền cannot be selected or verified."""


class VbeeSubmitError(VbeeError):
    """Raised when clicking convert button or submitting fails."""


class VbeeJobNotFoundError(VbeeError):
    """Raised when the specific uploaded job cannot be identified in Vbee table."""


class VbeeProcessingFailedError(VbeeError):
    """Raised when Vbee reports failure during job processing."""


class VbeeQuotaExceededError(VbeeError):
    """Raised when Vbee reports insufficient credits, characters, or quota."""


class VbeeConversionFailedError(VbeeError):
    """Raised when Vbee subtitle conversion fails or returns an error status."""


class VbeeTimeoutError(VbeeError):
    """Raised when an operation or job processing exceeds configured timeout."""


class VbeeDownloadError(VbeeError):
    """Raised when downloading audio from Vbee fails or produces an invalid file."""


class VoiceStorageFailedError(VbeeError):
    """Raised when local filesystem operations for voice storage fail."""


class VoiceFFmpegFailedError(VbeeError):
    """Raised when FFmpeg audio conversion or slicing fails."""


class VbeeImportError(VbeeError):
    """Raised when importing or slicing downloaded audio into the project fails."""


class VoiceImportFailedError(VbeeImportError):
    """Alias for voice import failure."""

