"""KAPPAK Auto Video Generator Module.

Provides automated script-to-video composition, 9:16 vertical presets,
AI voiceover synchronization, and dynamic subtitle rendering.
"""

from kappak.modules.auto_video.domain import AutoVideoProject, SceneSegment, TemplatePreset
from kappak.modules.auto_video.renderer import AutoVideoRenderer
from kappak.modules.auto_video.service import AutoVideoService
from kappak.modules.auto_video.templates import AVAILABLE_TEMPLATES, get_template_by_id

__all__ = [
    "AutoVideoProject",
    "AutoVideoRenderer",
    "AutoVideoService",
    "AVAILABLE_TEMPLATES",
    "get_template_by_id",
    "SceneSegment",
    "TemplatePreset",
]
