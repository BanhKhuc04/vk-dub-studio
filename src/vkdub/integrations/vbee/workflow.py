"""High-level workflow coordinator and state machine runner for Vbee Voice integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vkdub.domain.project import Project
from vkdub.domain.script import validate_script
from vkdub.integrations.vbee.errors import (
    VbeeValidationError,
)
from vkdub.integrations.vbee.importer import slice_and_import_vbee_audio
from vkdub.integrations.vbee.provider import VoiceProvider
from vkdub.integrations.vbee.state import WorkflowState
from vkdub.services.srt_service import write_srt
from vkdub.utils.paths import data_root, workspace_root

if TYPE_CHECKING:
    pass

logger = logging.getLogger("vkdub.vbee")


def validate_project_for_vbee(project: Project) -> None:
    """Ensure project satisfies all preconditions for Vbee voice automation."""
    if not project.video_path or not project.video_path.is_file():
        raise VbeeValidationError("Project chưa có video nguồn hợp lệ.")

    if not project.script or not project.script.lines:
        raise VbeeValidationError("Project chưa có kịch bản tiếng Việt.")

    if project.target_language != "vi":
        raise VbeeValidationError("Vbee Voice yêu cầu ngôn ngữ đích là tiếng Việt (vi).")

    issues = validate_script(project.script, project.duration_ms)
    errors = [i.message for i in issues if i.severity == "error"]
    if errors:
        raise VbeeValidationError(
            f"Kịch bản có lỗi: {errors[0]}. Vui lòng sửa trước khi tạo voice."
        )

    if not project.is_approved:
        raise VbeeValidationError("Kịch bản chưa được duyệt. Vui lòng bấm 'Duyệt kịch bản' trước.")


def export_vbee_srt(project: Project, output_dir: Path | None = None) -> Path:
    """Generate UTF-8 encoded SRT file from approved project script lines."""
    validate_project_for_vbee(project)
    assert project.script is not None

    target_dir = output_dir or (workspace_root() / "export")
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    srt_filename = f"vbee_subtitles_{timestamp_str}.srt"
    srt_path = target_dir / srt_filename

    write_srt(srt_path, project.script, project.duration_ms)

    if not srt_path.is_file() or srt_path.stat().st_size == 0:
        raise VbeeValidationError(f"Không thể xuất file SRT: {srt_path}")

    logger.info(
        "Đã xuất file SRT tiếng Việt cho Vbee: %s (%d bytes)",
        srt_path,
        srt_path.stat().st_size,
    )
    return srt_path


class VbeeVoiceWorkflow:
    """Orchestrates the entire Vbee Voice generation pipeline through its state machine."""

    def __init__(
        self,
        project: Project,
        provider: VoiceProvider,
        ffmpeg: str,
        ffprobe: str,
        state_callback: Callable[[WorkflowState, str], None] | None = None,
        progress_callback: Callable[[int, str], None] | None = None,
        check_cancel: Callable[[], None] | None = None,
        working_dir: Path | None = None,
    ) -> None:
        self.project = project
        self.provider = provider
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.state_callback = state_callback
        self.progress_callback = progress_callback
        self.check_cancel = check_cancel or (lambda: None)
        self.working_dir = working_dir or (data_root() / "vbee_staging")
        self.current_state = WorkflowState.IDLE
        self.srt_path: Path | None = None
        self.downloaded_audio_path: Path | None = None

    def _set_state(self, state: WorkflowState, message: str) -> None:
        self.current_state = state
        logger.info("Vbee State Transition: %s -> %s", state.value, message)
        if self.state_callback:
            self.state_callback(state, message)
        if self.progress_callback:
            pct = 0
            if state == WorkflowState.EXPORTING_SRT:
                pct = 5
            elif state == WorkflowState.OPENING_VBEE:
                pct = 20
            elif state == WorkflowState.LOGIN_REQUIRED:
                pct = 25
            elif state == WorkflowState.UPLOADING_SRT:
                pct = 40
            elif state == WorkflowState.SUBMITTING:
                pct = 50
            elif state == WorkflowState.PROCESSING:
                pct = 65
            elif state == WorkflowState.DOWNLOADING:
                pct = 85
            elif state == WorkflowState.IMPORTING_AUDIO:
                pct = 95
            elif state == WorkflowState.READY:
                pct = 100
            self.progress_callback(pct, message)

    async def run(self) -> dict[str, Any]:
        """Execute the complete Vbee workflow from validation to audio import."""
        self.working_dir.mkdir(parents=True, exist_ok=True)
        try:
            # 1. Validation
            self.check_cancel()
            validate_project_for_vbee(self.project)

            # 2. Export SRT
            self._set_state(WorkflowState.EXPORTING_SRT, "Đang xuất file SRT tiếng Việt…")
            self.check_cancel()
            self.srt_path = export_vbee_srt(self.project, self.working_dir)

            # 3. Provider execution (Browser / API)
            self._set_state(WorkflowState.OPENING_VBEE, "Đang mở Vbee Studio trên trình duyệt…")
            self.check_cancel()

            # The provider manages sub-states (login check, upload, submit, processing, download)
            # and passes progress through provider callbacks
            def on_provider_progress(pct: int, msg: str) -> None:
                self.check_cancel()
                # Map progress percentages to sub-states
                if "đăng nhập" in msg.lower():
                    self._set_state(WorkflowState.LOGIN_REQUIRED, msg)
                elif "tải file srt" in msg.lower() or pct <= 45:
                    self._set_state(WorkflowState.UPLOADING_SRT, msg)
                elif "chuyển phụ đề" in msg.lower() and pct <= 55:
                    self._set_state(WorkflowState.SUBMITTING, msg)
                elif "xử lý" in msg.lower() or (55 < pct < 85):
                    self._set_state(WorkflowState.PROCESSING, msg)
                elif "tải" in msg.lower() and pct >= 85:
                    self._set_state(WorkflowState.DOWNLOADING, msg)
                elif self.progress_callback:
                    self.progress_callback(pct, msg)

            self.downloaded_audio_path = await self.provider.execute_dubbing(
                project=self.project,
                srt_path=self.srt_path,
                progress_callback=on_provider_progress,
                check_cancel=self.check_cancel,
            )

            # 4. Import audio
            self._set_state(
                WorkflowState.IMPORTING_AUDIO,
                "Đang phân tách và nhập âm thanh vào project VK Dub Studio…",
            )
            self.check_cancel()

            import_result = await slice_and_import_vbee_audio(
                project=self.project,
                downloaded_audio=self.downloaded_audio_path,
                ffmpeg=self.ffmpeg,
                ffprobe=self.ffprobe,
            )

            # 5. Ready!
            self._set_state(
                WorkflowState.READY,
                f"Đã hoàn thành! Đã tạo và đồng bộ {import_result['lines_count']} câu thoại Vbee.",
            )

            return {
                "status": "success",
                "lines_count": import_result["lines_count"],
                "master_wav": import_result["master_wav"],
                "srt_path": str(self.srt_path),
            }

        except asyncio.CancelledError:
            self._set_state(WorkflowState.ERROR, "Đã dừng tiến trình tạo voice theo yêu cầu.")
            raise
        except Exception as exc:
            err_msg = str(exc)
            logger.error("Vbee workflow error: %s", exc, exc_info=True)
            self._set_state(WorkflowState.ERROR, f"Lỗi: {err_msg}")
            raise
        finally:
            await self.provider.close()
