import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QProcess, Signal

from vkdub.services.audio_mix_service import build_speech_track_wav
from vkdub.services.render_service import (
    RenderConfig,
    build_render_command,
    parse_ffmpeg_progress,
)
from vkdub.services.subtitle_service import export_ass
from vkdub.ui.export_dialog import ExportDialog

if TYPE_CHECKING:
    from vkdub.ui.main_window import MainWindow


class RenderController(QObject):
    """Coordinates video rendering using FFmpeg in a background process."""

    render_started = Signal()
    render_progress = Signal(float, str)
    render_completed = Signal(str)
    render_failed = Signal(str)

    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self.dialog: ExportDialog | None = None
        self.process = QProcess(self)
        self.process.readyReadStandardError.connect(self._on_stderr)
        self.process.finished.connect(self._on_finished)
        self._temp_dir: tempfile.TemporaryDirectory | None = None
        self._temp_output: Path | None = None
        self._final_output: Path | None = None
        self._total_duration_s: float = 0.0
        self._stderr_lines: list[str] = []

    def open_export_dialog(self) -> None:
        if self.dialog is None:
            self.dialog = ExportDialog(self.window)
            self.dialog.start_render_requested.connect(self.start_render)
            self.dialog.cancel_render_requested.connect(self.cancel_render)
        self.dialog.update_checklist()
        self.dialog.show()
        self.dialog.raise_()

    def start_render(self, config: RenderConfig) -> None:
        proj = self.window.project
        ffmpeg_exe = self.window.tools.paths.get("ffmpeg")
        if not ffmpeg_exe:
            self._fail("Không tìm thấy FFmpeg trên hệ thống.")
            return

        if not proj.video_path or not proj.video_path.is_file():
            self._fail("Video nguồn không tồn tại.")
            return

        self._final_output = config.output_path
        self._stderr_lines.clear()
        self._temp_dir = tempfile.TemporaryDirectory(prefix="vkdub_render_")
        temp_dir_path = Path(self._temp_dir.name)
        self._temp_output = temp_dir_path / "rendering.tmp.mp4"

        try:
            # 1. Build speech WAV track
            total_dur_ms = proj.duration_ms or (
                round(self.window.preview._last_metadata.duration * 1000)
                if self.window.preview._last_metadata
                else 60000
            )
            self._total_duration_s = total_dur_ms / 1000.0

            self.window.log("Đang tổng hợp dải âm thanh thuyết minh (WAV)…")
            speech_wav = temp_dir_path / "speech_track.wav"
            build_speech_track_wav(proj, speech_wav, total_dur_ms, ffmpeg=ffmpeg_exe)

            # 2. Build styled ASS subtitle file if requested
            ass_path: Path | None = None
            if config.burn_subtitles and proj.script:
                ass_path = temp_dir_path / "subtitles.ass"
                # Preview styling is defined on a 1920x1080 reference canvas.
                # Libass scales that canvas to the source frame, preserving the
                # exact relative size and bottom position seen in the preview.
                export_ass(proj, ass_path, proj.subtitle_style)

            # 3. Assemble FFmpeg render command
            temp_config = RenderConfig(
                output_path=self._temp_output,
                burn_subtitles=config.burn_subtitles,
                apply_masks=config.apply_masks,
                original_volume=config.original_volume,
                voice_volume=config.voice_volume,
                video_codec=config.video_codec,
                audio_codec=config.audio_codec,
                crf=config.crf,
                preset=config.preset,
            )

            has_audio = True
            if self.window.preview._last_metadata:
                has_audio = bool(self.window.preview._last_metadata.audio_codec)

            w = 1920
            h = 1080
            if self.window.preview._last_metadata:
                w = self.window.preview._last_metadata.width or 1920
                h = self.window.preview._last_metadata.height or 1080

            cmd_args = build_render_command(
                project=proj,
                config=temp_config,
                speech_wav_path=speech_wav,
                ass_subtitle_path=ass_path,
                ffmpeg_exe=ffmpeg_exe,
                video_width=w,
                video_height=h,
                has_original_audio=has_audio,
            )

            self.window.log(f"Bắt đầu xuất video qua FFmpeg: {config.output_path.name}")
            self.render_started.emit()
            self.process.start(cmd_args[0], cmd_args[1:])

        except Exception as exc:
            self._fail(f"Lỗi khởi tạo render: {exc}")

    def _on_stderr(self) -> None:
        data = bytes(self.process.readAllStandardError().data()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.strip():
                self._stderr_lines.append(line.strip())
                self._stderr_lines = self._stderr_lines[-80:]
            pct = parse_ffmpeg_progress(line, self._total_duration_s)
            if pct is not None:
                msg = f"Đang render… {pct:.1f}%"
                if self.dialog:
                    self.dialog.set_progress(pct, msg)
                self.render_progress.emit(pct, msg)

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._on_stderr()
        if exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit:
            # Move temp output to final output atomically
            if self._temp_output and self._temp_output.is_file() and self._final_output:
                try:
                    self._final_output.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(self._temp_output, self._final_output)
                    msg = f"Đã xuất video thành công: {self._final_output}"
                    self.window.log(msg)
                    if self.dialog:
                        self.dialog.render_finished(True, msg)
                    self.render_completed.emit(str(self._final_output))
                    self._cleanup()
                    return
                except Exception as exc:
                    self._fail(f"Không thể lưu file đích: {exc}")
                    return
            self._fail("Tệp video render không được tạo thành công.")
        else:
            keywords = ("error", "failed", "invalid", "unable", "no such")
            errors = [
                line for line in self._stderr_lines if any(key in line.lower() for key in keywords)
            ]
            detail = errors[-1:] or self._stderr_lines[-1:]
            suffix = f" Chi tiết: {detail[0][-600:]}" if detail else ""
            self._fail(f"FFmpeg kết thúc với mã lỗi {exit_code}.{suffix}")

    def _fail(self, message: str) -> None:
        self.window.log(f"Lỗi render: {message}")
        if self.dialog:
            self.dialog.render_finished(False, message)
        self.render_failed.emit(message)
        self._cleanup()

    def cancel_render(self) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.window.log("Đã hủy quá trình render video.")
        self._cleanup()

    def _cleanup(self) -> None:
        if self._temp_dir:
            try:
                self._temp_dir.cleanup()
            except Exception:
                pass
            self._temp_dir = None
