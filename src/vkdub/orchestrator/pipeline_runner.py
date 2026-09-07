"""VK Dub Studio — Automatic Pipeline Runner.

Coordinates 4.1 Transcription, 4.2 ChatGPT Translation, 4.3 Script Preparation,
and 4.4 Vbee Voice Generation with atomic checkpoints and instant resumption.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from vkdub.bridge.local_agent import LocalAgent
from vkdub.domain.project import Project
from vkdub.media.timeline_audio import build_master_timeline_audio
from vkdub.orchestrator.checkpoint import load_checkpoint, save_checkpoint
from vkdub.orchestrator.pipeline_state import (
    ArtifactRegistry,
    PipelineState,
    SubstepInfo,
    SubstepStatus,
)
from vkdub.services.srt_service import parse_srt, write_srt
from vkdub.services.srt_validator import validate_and_repair_srt
from vkdub.utils.paths import workspace_root

logger = logging.getLogger("vkdub.pipeline_runner")


class PipelineRunner(QThread):
    """Background worker thread running the 4-stage automated dubbing pipeline."""

    state_changed = Signal(object, str)  # PipelineState, message
    substep_updated = Signal(str, object, int, str)  # id, SubstepStatus, progress %, message
    artifact_ready = Signal(str, object)  # artifact_key, Path
    log_emitted = Signal(str)
    pipeline_completed = Signal(object)  # ArtifactRegistry
    pipeline_failed = Signal(str, str)  # (short_err, detailed_trace)
    pipeline_cancelled = Signal()

    def __init__(
        self,
        project: Project,
        local_agent: LocalAgent,
        output_dir: Path | None = None,
        voice_name: str = "Ngọc Huyền",
        speed: str = "1.1x",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.local_agent = local_agent
        self.output_dir = output_dir or (workspace_root() / "export")
        self.voice_name = voice_name
        self.speed = speed
        self.cancel_event = threading.Event()

        self.state = PipelineState.PROJECT_CREATED
        self.artifacts = ArtifactRegistry()
        if project.video_path:
            self.artifacts.source_video = project.video_path

        self.substeps: list[SubstepInfo] = [
            SubstepInfo(id="4.1", name="Bóc băng phụ đề gốc (Whisper)"),
            SubstepInfo(id="4.2", name="Dịch ngữ cảnh (ChatGPT qua Edge)"),
            SubstepInfo(id="4.3", name="Chuẩn bị kịch bản & timeline"),
            SubstepInfo(id="4.4", name="Tạo giọng đọc (Vbee Ngọc Huyền 1.1x)"),
        ]

    def cancel(self) -> None:
        self.cancel_event.set()

    def _update_substep(
        self,
        step_id: str,
        status: SubstepStatus,
        progress: int,
        message: str,
        artifact: Path | None = None,
        error: str | None = None,
        duration: float | None = None,
    ) -> None:
        for s in self.substeps:
            if s.id == step_id:
                s.status = status
                s.progress = progress
                s.message = message
                if artifact:
                    s.artifact_path = artifact
                if error:
                    s.error = error
                if duration is not None:
                    s.duration_s = duration
                break

        self.substep_updated.emit(step_id, status, progress, message)
        self._save_current_checkpoint()

    def _save_current_checkpoint(self) -> None:
        save_checkpoint(self.output_dir, self.state, self.artifacts, self.substeps)

    def run(self) -> None:
        logger.info("PipelineRunner started. Output directory: %s", self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cancel_event.clear()

        # Attempt to load existing checkpoint for resumption
        loaded = load_checkpoint(self.output_dir)
        if loaded:
            old_state, old_artifacts, _ = loaded
            self.artifacts = old_artifacts
            logger.info(
                "Found checkpoint with state=%s. Resuming existing artifacts...",
                old_state.value,
            )

        try:
            # =======================================================
            # 4.1 TRANSCRIPTION (Whisper / Existing Script)
            # =======================================================
            orig_srt_path = self.artifacts.original_srt
            if not (orig_srt_path and orig_srt_path.is_file()):
                self.state = PipelineState.TRANSCRIBING
                self.state_changed.emit(self.state, "Đang bóc băng phụ đề gốc...")
                self._update_substep("4.1", SubstepStatus.RUNNING, 10, "Đang khởi chạy Whisper...")
                t0 = time.monotonic()

                if self.project.script and self.project.script.lines:
                    # Use script already present in project
                    orig_srt_path = self.output_dir / "original.srt"
                    write_srt(orig_srt_path, self.project.script, self.project.duration_ms)
                elif self.project.video_path and self.project.video_path.is_file():
                    # Run local faster-whisper transcription
                    self._update_substep(
                        "4.1", SubstepStatus.RUNNING, 40, "Đang trích xuất audio..."
                    )
                    from vkdub.media.audio_extract import extract_audio
                    from vkdub.providers.transcription_provider import (
                        FasterWhisperProvider,
                    )

                    wav_path = self.output_dir / "audio_source.wav"
                    extract_audio(self.project.video_path, wav_path)

                    self._update_substep(
                        "4.1",
                        SubstepStatus.RUNNING,
                        65,
                        "Đang nhận diện giọng nói (Whisper)...",
                    )
                    provider = FasterWhisperProvider(model_size="base")
                    transcript = provider.transcribe(wav_path)
                    self.project.transcript = transcript

                    orig_srt_path = self.output_dir / "original.srt"
                    from vkdub.services.srt_service import write_transcript_to_srt

                    write_transcript_to_srt(orig_srt_path, transcript)
                else:
                    raise ValueError("Dự án chưa chọn video MP4 và chưa có phụ đề gốc để xử lý.")

                duration = time.monotonic() - t0
                self.artifacts.original_srt = orig_srt_path
                self.artifact_ready.emit("original_srt", orig_srt_path)
                self._update_substep(
                    "4.1",
                    SubstepStatus.SUCCESS,
                    100,
                    "Bóc băng thành công",
                    artifact=orig_srt_path,
                    duration=duration,
                )
                self.state = PipelineState.TRANSCRIBED
                self.state_changed.emit(self.state, "Bóc băng hoàn tất.")
            else:
                logger.info("Reusing existing original.srt from checkpoint: %s", orig_srt_path)
                self._update_substep(
                    "4.1",
                    SubstepStatus.SUCCESS,
                    100,
                    "Đã có sẵn phụ đề gốc",
                    artifact=orig_srt_path,
                )

            if self.cancel_event.is_set():
                self.pipeline_cancelled.emit()
                return

            # =======================================================
            # 4.2 CHATGPT TRANSLATION (via Edge Extension)
            # =======================================================
            trans_srt_path = self.artifacts.translated_srt
            if not (trans_srt_path and trans_srt_path.is_file()):
                self.state = PipelineState.TRANSLATING
                self.state_changed.emit(self.state, "Đang gửi phụ đề sang ChatGPT qua Edge...")
                self._update_substep(
                    "4.2",
                    SubstepStatus.RUNNING,
                    15,
                    "Đang kết nối ChatGPT trong Edge...",
                )
                t0 = time.monotonic()

                assert orig_srt_path is not None
                raw_original_srt = orig_srt_path.read_text(encoding="utf-8", errors="replace")

                self._update_substep(
                    "4.2",
                    SubstepStatus.WAITING,
                    45,
                    "ChatGPT đang dịch (giữ nguyên timecode)...",
                )
                raw_translated_srt = self.local_agent.translate_srt_sync(
                    raw_original_srt, timeout_s=360.0
                )

                self._update_substep(
                    "4.2", SubstepStatus.VALIDATING, 85, "Đang kiểm tra và sửa lỗi timecode..."
                )
                val_res = validate_and_repair_srt(
                    raw_original_srt, raw_translated_srt, auto_repair_timecodes=True
                )
                if not val_res.is_valid:
                    err_detail = " | ".join(val_res.errors)
                    raise ValueError(f"Kiểm tra phụ đề dịch thất bại: {err_detail}")

                final_srt_content = val_res.repaired_srt or raw_translated_srt
                trans_srt_path = self.output_dir / "translated.srt"
                trans_srt_path.write_text(final_srt_content, encoding="utf-8")

                duration = time.monotonic() - t0
                self.artifacts.translated_srt = trans_srt_path
                self.artifact_ready.emit("translated_srt", trans_srt_path)
                self._update_substep(
                    "4.2",
                    SubstepStatus.SUCCESS,
                    100,
                    f"Dịch thành công ({val_res.cue_count} câu)",
                    artifact=trans_srt_path,
                    duration=duration,
                )
                self.state = PipelineState.TRANSLATED
                self.state_changed.emit(self.state, "Dịch ChatGPT hoàn tất.")
            else:
                logger.info("Reusing existing translated.srt from checkpoint: %s", trans_srt_path)
                self._update_substep(
                    "4.2",
                    SubstepStatus.SUCCESS,
                    100,
                    "Đã có sẵn phụ đề dịch",
                    artifact=trans_srt_path,
                )

            if self.cancel_event.is_set():
                self.pipeline_cancelled.emit()
                return

            # =======================================================
            # 4.3 SCRIPT PREPARATION & ATTACHMENT
            # =======================================================
            self.state = PipelineState.SCRIPT_READY
            self.state_changed.emit(self.state, "Đang nạp kịch bản vào dự án...")
            self._update_substep("4.3", SubstepStatus.RUNNING, 30, "Đang phân tích câu phụ đề...")
            t0 = time.monotonic()

            assert trans_srt_path is not None
            script_content = trans_srt_path.read_text(encoding="utf-8", errors="replace")
            script_doc = parse_srt(script_content)
            self.project.script = script_doc
            self.project.approved_revision_hash = script_doc.content_hash()
            self.project.target_language = "vi"

            # Save plain text voice script
            voice_txt_path = self.output_dir / "voice_script.txt"
            voice_txt_path.write_text(
                "\n".join(line.vietnamese for line in script_doc.lines),
                encoding="utf-8",
            )
            self.artifacts.voice_script = voice_txt_path

            duration = time.monotonic() - t0
            self._update_substep(
                "4.3",
                SubstepStatus.SUCCESS,
                100,
                f"Kịch bản sẵn sàng ({len(script_doc.lines)} câu)",
                artifact=voice_txt_path,
                duration=duration,
            )

            if self.cancel_event.is_set():
                self.pipeline_cancelled.emit()
                return

            # =======================================================
            # 4.4 VBEE VOICE GENERATION (via Edge Extension)
            # =======================================================
            master_audio_path = self.artifacts.vbee_master_audio
            timeline_audio_path = self.artifacts.timeline_master_audio

            if not (timeline_audio_path and timeline_audio_path.is_file()):
                self.state = PipelineState.VOICE_GENERATING
                self.state_changed.emit(
                    self.state, "Đang gửi kịch bản sang Vbee (Ngọc Huyền 1.1x)..."
                )
                self._update_substep(
                    "4.4",
                    SubstepStatus.RUNNING,
                    15,
                    f"Vbee đang tạo giọng {self.voice_name} {self.speed}...",
                )
                t0 = time.monotonic()

                raw_vbee_path = self.output_dir / "vbee_master_raw.mp3"
                if not (master_audio_path and master_audio_path.is_file()):
                    saved_vbee_audio = self.local_agent.generate_vbee_sync(
                        script_content,
                        raw_vbee_path,
                        voice_name=self.voice_name,
                        speed=self.speed,
                        timeout_s=600.0,
                    )
                    self.artifacts.vbee_master_audio = saved_vbee_audio
                else:
                    saved_vbee_audio = master_audio_path

                self._update_substep(
                    "4.4",
                    SubstepStatus.RUNNING,
                    80,
                    "Đang tạo master timeline audio (đồng bộ khoảng lặng)...",
                )
                timeline_audio_path = self.output_dir / "master_narration_timeline.mp3"
                build_master_timeline_audio(
                    vbee_audio_path=saved_vbee_audio,
                    srt_path=trans_srt_path,
                    output_path=timeline_audio_path,
                    total_duration_ms=self.project.duration_ms,
                )

                duration = time.monotonic() - t0
                self.artifacts.timeline_master_audio = timeline_audio_path
                self.artifact_ready.emit("master_audio", timeline_audio_path)
                self._update_substep(
                    "4.4",
                    SubstepStatus.SUCCESS,
                    100,
                    "Hoàn thành âm thanh timeline",
                    artifact=timeline_audio_path,
                    duration=duration,
                )
                self.state = PipelineState.VOICE_READY
                self.state_changed.emit(self.state, "Tạo voice Vbee hoàn tất.")
            else:
                logger.info(
                    "Reusing existing master audio from checkpoint: %s",
                    timeline_audio_path,
                )
                self._update_substep(
                    "4.4",
                    SubstepStatus.SUCCESS,
                    100,
                    "Đã có sẵn master audio",
                    artifact=timeline_audio_path,
                )

            # =======================================================
            # FINAL REVIEW READY
            # =======================================================
            self.state = PipelineState.REVIEW_READY
            self.state_changed.emit(
                self.state, "Xử lý tự động hoàn tất! Sẵn sàng duyệt và xuất CapCut."
            )
            self._save_current_checkpoint()
            self.pipeline_completed.emit(self.artifacts)

        except Exception as exc:
            logger.exception("Pipeline execution failed: %s", exc)
            self.state = PipelineState.FAILED
            short_err = str(exc)
            import traceback

            trace = traceback.format_exc()

            # Mark currently running substep as failed
            for s in self.substeps:
                if s.status in (
                    SubstepStatus.RUNNING,
                    SubstepStatus.WAITING,
                    SubstepStatus.VALIDATING,
                ):
                    s.status = SubstepStatus.FAILED
                    s.error = short_err
                    self.substep_updated.emit(s.id, SubstepStatus.FAILED, 0, short_err)
                    break

            self._save_current_checkpoint()
            self.pipeline_failed.emit(short_err, trace)
