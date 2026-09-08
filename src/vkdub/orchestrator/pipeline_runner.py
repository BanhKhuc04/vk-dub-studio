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
from vkdub.media.timeline_audio import build_master_timeline_audio, get_audio_duration_ms
from vkdub.orchestrator.checkpoint import load_checkpoint, save_checkpoint
from vkdub.orchestrator.pipeline_state import (
    ArtifactRegistry,
    PipelineState,
    SubstepInfo,
    SubstepStatus,
)
from vkdub.domain.transcript import srt_timestamp
from vkdub.services.srt_service import parse_srt, write_srt
from vkdub.services.srt_validator import (
    Cue,
    format_cues_to_srt,
    parse_cues,
    validate_and_repair_srt,
)
from vkdub.utils.paths import workspace_root

logger = logging.getLogger("vkdub.pipeline_runner")


def _timeline_audio_is_usable(path: Path, target_duration_ms: int | None) -> bool:
    if not path.is_file():
        return False
    if not target_duration_ms:
        return True
    actual_duration_ms = get_audio_duration_ms(path)
    # Keep the artifact when probing is unavailable, but rebuild any measured
    # output that drifts enough to be visible/audible in the final video.
    return actual_duration_ms <= 0 or abs(actual_duration_ms - target_duration_ms) <= 250


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
        auto_voice: bool = True,
        target_step: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.local_agent = local_agent
        self.output_dir = output_dir or (workspace_root() / "export")
        self.voice_name = voice_name
        self.speed = speed
        self.auto_voice = auto_voice
        self.target_step = target_step
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
        self.log_emitted.emit(f"[{step_id}] {message}")
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
            if self.target_step != "4.4":
                # =======================================================
                # 4.1 TRANSCRIPTION (Whisper / Existing Script)
                # =======================================================
                orig_srt_path = self.artifacts.original_srt or (self.output_dir / "original.srt")
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

                        wav_path = self.output_dir / "audio_source.wav"
                        self.log_emitted.emit(
                            f"🎵 Đang trích xuất âm thanh từ video: {self.project.video_path.name}..."
                        )
                        extract_audio(self.project.video_path, wav_path)
                        wav_size_kb = wav_path.stat().st_size / 1024 if wav_path.exists() else 0
                        self.log_emitted.emit(
                            f"✓ Đã trích xuất audio nguồn ({wav_size_kb:.1f} KB)."
                        )

                        self._update_substep(
                            "4.1",
                            SubstepStatus.RUNNING,
                            65,
                            "Đang nhận diện giọng nói (Whisper)...",
                        )
                        from faster_whisper import WhisperModel

                        model_size = "base"
                        if (
                            hasattr(self.project, "transcription_settings")
                            and self.project.transcription_settings
                        ):
                            model_size = (
                                getattr(self.project.transcription_settings, "model", "base") or "base"
                            )

                        whisper = WhisperModel(model_size, device="cpu", compute_type="int8")
                        segments_gen, info = whisper.transcribe(str(wav_path), beam_size=5)
                        total_dur = (
                            info.duration
                            if (info and getattr(info, "duration", 0) > 0)
                            else (
                                self.project.video_duration_ms / 1000
                                if getattr(self.project, "video_duration_ms", None)
                                else 60.0
                            )
                        )
                        self.log_emitted.emit(
                            f"🎙 Bắt đầu bóc băng Whisper ({model_size}) cho video độ dài {total_dur:.1f}s..."
                        )

                        cues = []
                        for idx, seg in enumerate(segments_gen, 1):
                            start_tc = srt_timestamp(seg.start)
                            end_tc = srt_timestamp(seg.end)
                            text = seg.text.strip()
                            if text:
                                cues.append(f"{idx}\n{start_tc} --> {end_tc}\n{text}\n")
                                pct = min(98, 65 + int((seg.end / total_dur) * 33))
                                self._update_substep(
                                    "4.1",
                                    SubstepStatus.RUNNING,
                                    pct,
                                    f"Đang bóc băng: [{start_tc[:8]} ➔ {end_tc[:8]}] ({idx} câu)",
                                )
                                self.log_emitted.emit(
                                    f"  🎙 [Bóc băng #{idx}] Đang xử lý đoạn {start_tc[:8]} ➔ {end_tc[:8]}: \"{text}\""
                                )

                        orig_srt_content = "\n".join(cues)
                        orig_srt_path = self.output_dir / "original.srt"
                        orig_srt_path.write_text(orig_srt_content, encoding="utf-8")
                        self.log_emitted.emit(
                            f"✓ Bóc băng hoàn tất: Đã nhận diện toàn bộ {len(cues)} câu thoại."
                        )
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
                    self.artifacts.original_srt = orig_srt_path
                    logger.info("Reusing existing original.srt: %s", orig_srt_path)
                    try:
                        raw_c = orig_srt_path.read_text(encoding="utf-8", errors="replace")
                        d_orig = parse_srt(raw_c)
                        c_cnt = len(d_orig.lines)
                        if c_cnt > 0:
                            f_tc = srt_timestamp(d_orig.lines[0].start_ms / 1000)
                            l_tc = srt_timestamp(d_orig.lines[-1].end_ms / 1000)
                            self.log_emitted.emit(
                                f"ℹ Tái sử dụng phụ đề gốc có sẵn: {c_cnt} câu thoại (từ đoạn {f_tc[:8]} ➔ {l_tc[:8]}). Bỏ qua bóc băng."
                            )
                            self.log_emitted.emit(f"  → Đoạn đầu [{f_tc[:8]}]: \"{d_orig.lines[0].text}\"")
                            self.log_emitted.emit(f"  → Đoạn cuối [{l_tc[:8]}]: \"{d_orig.lines[-1].text}\"")
                        else:
                            self.log_emitted.emit("ℹ Tái sử dụng phụ đề gốc có sẵn (0 câu thoại).")
                    except Exception:
                        self.log_emitted.emit(f"ℹ Tái sử dụng phụ đề gốc có sẵn ({orig_srt_path.name}).")

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
                trans_srt_path = self.artifacts.translated_srt or (self.output_dir / "translated.srt")
                if not (trans_srt_path and trans_srt_path.is_file()):
                    self.state = PipelineState.TRANSLATING
                    self.state_changed.emit(self.state, "Đang chuẩn bị gửi phụ đề sang ChatGPT...")
                    t0 = time.monotonic()

                    assert orig_srt_path is not None
                    raw_original_srt = orig_srt_path.read_text(encoding="utf-8", errors="replace")

                    orig_cues = parse_cues(raw_original_srt)
                    total_cues = len(orig_cues)
                    if total_cues == 0:
                        raise ValueError("File phụ đề gốc (original.srt) rỗng hoặc không có câu thoại nào.")

                    f_tc = orig_cues[0].start_raw[:8]
                    l_tc = orig_cues[-1].end_raw[:8]
                    range_str = f"từ đoạn {f_tc} ➔ {l_tc}"

                    CHUNK_SIZE = 35
                    if total_cues <= 40:
                        chunks = [orig_cues]
                    else:
                        chunks = [
                            orig_cues[i : i + CHUNK_SIZE]
                            for i in range(0, total_cues, CHUNK_SIZE)
                        ]

                    total_chunks = len(chunks)
                    if total_chunks > 1:
                        self.log_emitted.emit(
                            f"📝 Phụ đề dài ({total_cues} câu, {range_str}): "
                            f"Tự động chia thành {total_chunks} đoạn (mỗi đoạn ~{CHUNK_SIZE} câu) "
                            f"để ChatGPT dịch trọn vẹn không bị tràn giới hạn token..."
                        )
                    else:
                        self.log_emitted.emit(
                            f"📝 Gửi {total_cues} câu phụ đề ({range_str}) sang ChatGPT qua Edge để dịch ngữ cảnh..."
                        )

                    all_trans_cues: list[Cue] = []

                    for chunk_idx, chunk in enumerate(chunks, 1):
                        if self.cancel_event.is_set():
                            self.pipeline_cancelled.emit()
                            return

                        start_num = chunk[0].index
                        end_num = chunk[-1].index
                        chunk_count = len(chunk)
                        chunk_srt_text = format_cues_to_srt(chunk, preserve_indices=True)

                        pct = int(15 + ((chunk_idx - 1) / total_chunks) * 70)
                        if total_chunks > 1:
                            chunk_msg = f"ChatGPT đang dịch đoạn {chunk_idx}/{total_chunks} (câu {start_num}-{end_num})..."
                            self.log_emitted.emit(
                                f"  🤖 [Đoạn {chunk_idx}/{total_chunks}] Gửi {chunk_count} câu "
                                f"(từ câu #{start_num} đến #{end_num}) sang ChatGPT..."
                            )
                        else:
                            chunk_msg = f"ChatGPT đang dịch ({total_cues} câu)..."

                        self._update_substep("4.2", SubstepStatus.WAITING, pct, chunk_msg)

                        prompt_instr = (
                            f"Dịch đoạn phụ đề SRT sau đây sang tiếng Việt (từ câu {start_num} đến câu {end_num}, đúng {chunk_count} câu):\n"
                            "- Sát nghĩa, tự nhiên, đúng bối cảnh và cảm xúc câu chuyện.\n"
                            f"- Giữ nguyên 100% định dạng SRT, số thứ tự câu ({start_num} đến {end_num}) và toàn bộ mốc thời gian (timecode).\n"
                            "- Không gộp câu, không tách câu, không bỏ sót bất kỳ câu nào.\n"
                            "- Tuyệt đối không thay đổi mốc thời gian.\n"
                            "- Xuất toàn bộ kết quả trong khối mã ```srt."
                        )

                        raw_chunk_trans = self.local_agent.translate_srt_sync(
                            chunk_srt_text,
                            prompt_instruction=prompt_instr,
                            timeout_s=360.0,
                        )

                        parsed_chunk_cues = parse_cues(raw_chunk_trans)
                        if not parsed_chunk_cues:
                            raise ValueError(
                                f"Không trích xuất được câu phụ đề nào từ kết quả dịch đoạn {chunk_idx}/{total_chunks}."
                            )

                        if len(parsed_chunk_cues) != chunk_count:
                            self.log_emitted.emit(
                                f"  ℹ Đoạn {chunk_idx}: bản dịch có {len(parsed_chunk_cues)} câu "
                                f"(gốc có {chunk_count} câu). Đang tự động đối soát và khớp timecode gốc..."
                            )

                        for k, orig_c in enumerate(chunk):
                            if k < len(parsed_chunk_cues):
                                trans_c = parsed_chunk_cues[k]
                                cue_text = trans_c.text.strip() or orig_c.text.strip()
                            else:
                                cue_text = orig_c.text.strip()

                            all_trans_cues.append(
                                Cue(
                                    index=orig_c.index,
                                    start_raw=orig_c.start_raw,
                                    end_raw=orig_c.end_raw,
                                    text=cue_text,
                                    start_ms=orig_c.start_ms,
                                    end_ms=orig_c.end_ms,
                                )
                            )

                        if total_chunks > 1:
                            self.log_emitted.emit(
                                f"  ✓ Đã hoàn thành đoạn {chunk_idx}/{total_chunks} ({chunk_count} câu)."
                            )
                        if chunk_idx < total_chunks:
                            time.sleep(1.0)

                    raw_translated_srt = format_cues_to_srt(all_trans_cues)
                    self.log_emitted.emit(
                        f"✓ Đã hoàn tất toàn bộ {total_chunks} đoạn dịch. Đang đối soát và chuẩn hóa 100% timecode..."
                    )

                    self._update_substep(
                        "4.2", SubstepStatus.VALIDATING, 90, "Đang kiểm tra và hoàn thiện file phụ đề..."
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
                    self.log_emitted.emit(
                        f"✓ Phụ đề dịch hợp lệ 100%: Khớp toàn bộ {val_res.cue_count} câu thoại ({range_str})."
                    )

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
                    self.artifacts.translated_srt = trans_srt_path
                    logger.info("Reusing existing translated.srt: %s", trans_srt_path)
                    try:
                        raw_c = trans_srt_path.read_text(encoding="utf-8", errors="replace")
                        d_trans = parse_srt(raw_c)
                        c_cnt = len(d_trans.lines)
                        if c_cnt > 0:
                            f_tc = srt_timestamp(d_trans.lines[0].start_ms / 1000)
                            l_tc = srt_timestamp(d_trans.lines[-1].end_ms / 1000)
                            self.log_emitted.emit(
                                f"ℹ Tái sử dụng phụ đề dịch có sẵn: {c_cnt} câu thoại (từ đoạn {f_tc[:8]} ➔ {l_tc[:8]})."
                            )
                            self.log_emitted.emit(f"  → Đoạn đầu dịch [{f_tc[:8]}]: \"{d_trans.lines[0].text}\"")
                            self.log_emitted.emit(f"  → Đoạn cuối dịch [{l_tc[:8]}]: \"{d_trans.lines[-1].text}\"")
                        else:
                            self.log_emitted.emit("ℹ Tái sử dụng phụ đề dịch có sẵn (0 câu thoại).")
                    except Exception:
                        self.log_emitted.emit(f"ℹ Tái sử dụng phụ đề dịch có sẵn ({trans_srt_path.name}).")

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
                if self.project.duration_ms:
                    from dataclasses import replace as dc_replace
                    clamped_lines = []
                    clamped_any = False
                    for line in script_doc.lines:
                        if line.end_ms > self.project.duration_ms and line.start_ms < self.project.duration_ms:
                            clamped_lines.append(dc_replace(line, end_ms=self.project.duration_ms))
                            clamped_any = True
                        else:
                            clamped_lines.append(line)
                    if clamped_any:
                        from vkdub.domain.script import ScriptDocument
                        from vkdub.services.srt_service import script_to_srt
                        script_doc = ScriptDocument(tuple(clamped_lines))
                        trans_srt_path.write_text(script_to_srt(script_doc), encoding="utf-8")
                        self.log_emitted.emit(
                            f"ℹ Tự động khớp thời lượng câu cuối ({script_doc.lines[-1].end_ms}ms) với thời lượng video ({self.project.duration_ms}ms)."
                        )
                self.project.script = script_doc
                self.project.target_language = "vi"
                self.log_emitted.emit(
                    f"📋 Đã nạp {len(script_doc.lines)} câu thoại vào kịch bản dự án."
                )
                if self.auto_voice:
                    try:
                        self.project.approved_revision_hash = self.project.revision_hash
                    except Exception as e:
                        logger.warning("Could not calculate approved_revision_hash: %s", e)
                        self.project.approved_revision_hash = None
                else:
                    self.project.approved_revision_hash = None

                # Save plain text voice script
                voice_txt_path = self.output_dir / "voice_script.txt"
                voice_txt_path.write_text(
                    "\n".join(line.text for line in script_doc.lines),
                    encoding="utf-8",
                )
                self.artifacts.voice_script = voice_txt_path
                self.log_emitted.emit(
                    f"💾 Đã lưu file voice_script.txt ({voice_txt_path.stat().st_size} bytes)."
                )

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

                if not self.auto_voice:
                    self._update_substep(
                        "4.4",
                        SubstepStatus.WAITING,
                        0,
                        "Chờ duyệt kịch bản tại Bước 05",
                    )
                    self.state = PipelineState.SCRIPT_READY
                    self.state_changed.emit(
                        self.state, "Dịch hoàn tất! Vui lòng duyệt kịch bản tại Bước 05 trước khi tạo giọng đọc."
                    )
                    self.log_emitted.emit(
                        "⏸ [Tạm dừng duyệt kịch bản] Hệ thống dừng lại ở Bước 05 để bạn kiểm tra và chốt kịch bản trước khi tạo giọng đọc Vbee."
                    )
                    self._save_current_checkpoint()
                    self.pipeline_completed.emit(self.artifacts)
                    return

            # =======================================================
            # 4.4 VBEE VOICE GENERATION (via Edge Extension)
            # =======================================================
            if self.project.script and self.project.script.lines:
                trans_srt_path = self.output_dir / "translated.srt"
                write_srt(trans_srt_path, self.project.script, self.project.duration_ms)
                script_content = trans_srt_path.read_text(encoding="utf-8", errors="replace")
                voice_txt_path = self.output_dir / "voice_script.txt"
                voice_txt_path.write_text(
                    "\n".join(line.text for line in self.project.script.lines),
                    encoding="utf-8",
                )
                self.artifacts.translated_srt = trans_srt_path
                self.artifacts.voice_script = voice_txt_path
            else:
                trans_srt_path = self.artifacts.translated_srt or (self.output_dir / "translated.srt")
                if trans_srt_path and trans_srt_path.is_file():
                    script_content = trans_srt_path.read_text(encoding="utf-8", errors="replace")
                else:
                    raise ValueError("Không tìm thấy kịch bản để tạo giọng đọc Vbee.")
            master_audio_path = self.artifacts.vbee_master_audio or (
                self.output_dir / "vbee_master_raw.mp3"
            )
            timeline_audio_path = self.artifacts.timeline_master_audio or (
                self.output_dir / "master_narration_timeline.mp3"
            )

            timeline_ready = bool(
                timeline_audio_path
                and _timeline_audio_is_usable(
                    timeline_audio_path, self.project.duration_ms
                )
            )
            if not timeline_ready:
                self.state = PipelineState.VOICE_GENERATING
                self.state_changed.emit(
                    self.state, f"Đang gửi kịch bản sang Vbee ({self.voice_name} {self.speed})..."
                )
                self._update_substep(
                    "4.4",
                    SubstepStatus.RUNNING,
                    15,
                    f"Vbee đang tạo giọng {self.voice_name} {self.speed}...",
                )
                num_v = len(self.project.script.lines) if (self.project.script and self.project.script.lines) else 0
                range_str = ""
                if num_v > 0:
                    f_tc = srt_timestamp(self.project.script.lines[0].start_ms / 1000)
                    l_tc = srt_timestamp(self.project.script.lines[-1].end_ms / 1000)
                    range_str = f" ({num_v} câu thoại, từ đoạn {f_tc[:8]} ➔ {l_tc[:8]})"

                self.log_emitted.emit(
                    f"🎙 Gửi kịch bản sang Vbee qua Edge: Giọng '{self.voice_name}', Tốc độ '{self.speed}'{range_str}..."
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
                    audio_size_kb = saved_vbee_audio.stat().st_size // 1024 if saved_vbee_audio.exists() else 0
                    self.log_emitted.emit(
                        f"✓ Đã nhận file audio từ Vbee ({audio_size_kb} KB). Đang dùng FFmpeg căn chỉnh timeline master..."
                    )
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
                dur_total_s = (self.project.duration_ms or 0) / 1000
                self.log_emitted.emit(
                    f"🎉 Master timeline audio hoàn thành: {timeline_audio_path.name} ({dur_total_s:.1f}s, bắt đầu tại 00:00:00.000)."
                )
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
                self.log_emitted.emit(
                    f"ℹ Tái sử dụng master narration timeline có sẵn: {timeline_audio_path.name}"
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
