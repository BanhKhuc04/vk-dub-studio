"""Vbee Voice Automation Integration package."""

from vkdub.integrations.vbee.errors import (
    VbeeAutomationError,
    VbeeConversionFailedError,
    VbeeDownloadError,
    VbeeError,
    VbeeImportError,
    VbeeLoginRequiredError,
    VbeeQuotaExceededError,
    VbeeTimeoutError,
    VbeeValidationError,
)
from vkdub.integrations.vbee.importer import slice_and_import_vbee_audio
from vkdub.integrations.vbee.provider import VbeeBrowserProvider, VoiceProvider
from vkdub.integrations.vbee.state import CHECKLIST_STEPS, WorkflowState
from vkdub.integrations.vbee.workflow import (
    VbeeVoiceWorkflow,
    export_vbee_srt,
    validate_project_for_vbee,
)

__all__ = [
    "CHECKLIST_STEPS",
    "VbeeAutomationError",
    "VbeeBrowserProvider",
    "VbeeConversionFailedError",
    "VbeeDownloadError",
    "VbeeError",
    "VbeeImportError",
    "VbeeLoginRequiredError",
    "VbeeQuotaExceededError",
    "VbeeTimeoutError",
    "VbeeValidationError",
    "VbeeVoiceWorkflow",
    "VoiceProvider",
    "WorkflowState",
    "export_vbee_srt",
    "slice_and_import_vbee_audio",
    "validate_project_for_vbee",
]
