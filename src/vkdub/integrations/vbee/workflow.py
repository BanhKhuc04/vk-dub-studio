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

    import re

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    if project.video_path:
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", project.video_path.stem)
    else:
        slug = "project"
    slug = slug.strip("_")[:30] or "project"
    srt_filename = f"vkdub_{slug}_{timestamp_str}.srt"
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
        speed: float | None = None,
    ) -> None:
        self.project = project
        self.provider = provider
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.state_callback = state_callback
        self.progress_callback = progress_callback
        self.check_cancel = check_cancel or (lambda: None)
        self.working_dir = working_dir or (data_root() / "vbee_staging")
        self.speed = speed if speed is not None else (
            getattr(project.voice, "speed", 1.1) if project and project.voice else 1.1
        )
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
            logger.info("[VBEE][START] Bắt đầu quy trình tạo Voice tự động bằng Vbee Dubbing")

            # 1. Validation
            self._set_state(WorkflowState.VALIDATING, "Đang kiểm tra điều kiện kịch bản và công cụ…")
            self.check_cancel()
            validate_project_for_vbee(self.project)

            # 2. Export SRT
            self._set_state(WorkflowState.EXPORTING_SRT, "Đang xuất file SRT tiếng Việt…")
            self.check_cancel()
            self.srt_path = export_vbee_srt(self.project, self.working_dir)
            logger.info("[VBEE][SRT] Đã xuất file SRT thành công: %s", self.srt_path)

            # 3. Provider execution (Browser / API)
            is_api = getattr(self.provider, "name", "") == "vbee_api"
            if is_api:
                self._set_state(WorkflowState.OPENING_VBEE, "Đang kết nối Vbee API…")
            else:
                self._set_state(WorkflowState.OPENING_VBEE, "Đang mở Vbee Studio trên trình duyệt…")
            self.check_cancel()

            def on_provider_progress(pct: int, msg: str) -> None:
                self.check_cancel()
                # Map progress percentages to semantic sub-states
                msg_lower = msg.lower()
                if "kết nối" in msg_lower:
                    self._set_state(WorkflowState.OPENING_VBEE, msg)
                elif "đăng nhập" in msg_lower:
                    self._set_state(WorkflowState.LOGIN_REQUIRED, msg)
                elif "tải file srt" in msg_lower:
                    self._set_state(WorkflowState.UPLOADING_SRT, msg)
                elif "cấu hình" in msg_lower:
                    self._set_state(WorkflowState.CONFIGURING_VOICE, msg)
                elif "bắt đầu chuyển" in msg_lower or "chuyển phụ đề" in msg_lower and pct <= 60:
                    self._set_state(WorkflowState.SUBMITTING, msg)
                elif "đang tạo voice" in msg_lower or "xử lý" in msg_lower or (60 < pct < 85):
                    self._set_state(WorkflowState.PROCESSING, msg)
                elif "tải" in msg_lower and pct >= 85:
                    self._set_state(WorkflowState.DOWNLOADING, msg)
                elif "tổng hợp" in msg_lower or "chuẩn hóa" in msg_lower:
                    self._set_state(WorkflowState.PROCESSING_AUDIO, msg)
                elif self.progress_callback:
                    self.progress_callback(pct, msg)

            if is_api and hasattr(self.provider, "execute_api_dubbing"):
                import_result = await self.provider.execute_api_dubbing(
                    project=self.project,
                    ffmpeg=self.ffmpeg,
                    ffprobe=self.ffprobe,
                    progress_callback=on_provider_progress,
                    check_cancel=self.check_cancel,
                    speed=self.speed,
                )
                self.downloaded_audio_path = Path(import_result["master_wav"])
            else:
                self.downloaded_audio_path = await self.provider.execute_dubbing(
                    project=self.project,
                    srt_path=self.srt_path,
                    progress_callback=on_provider_progress,
                    check_cancel=self.check_cancel,
                    speed=self.speed,
                )
                logger.info("[VBEE][DOWNLOAD] File âm thanh tải về hoàn tất: %s", self.downloaded_audio_path)

                # 4. Import audio
                self._set_state(
                    WorkflowState.PROCESSING_AUDIO,
                    "Đang chuẩn hóa âm thanh qua FFmpeg…",
                )
                self.check_cancel()

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
            logger.info("[VOICE][IMPORT] Đã nhập xong %d câu thoại vào project.", import_result["lines_count"])

            # 5. Ready!
            self._set_state(
                WorkflowState.READY,
                f"Đã hoàn thành! Đã tạo và đồng bộ {import_result['lines_count']} câu thoại Vbee.",
            )
            logger.info("[VOICE][READY] Hoàn thành toàn bộ quy trình Voice Vbee.")

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
