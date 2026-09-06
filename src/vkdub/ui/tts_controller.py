from dataclasses import replace
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from vkdub.domain.voice import (
    DEFAULT_ELEVENLABS_LABEL,
    DEFAULT_ELEVENLABS_VOICE,
    DEFAULT_LABEL,
    DEFAULT_VOICE,
    POPULAR_ELEVENLABS_VOICES,
    Voice,
    VoiceAsset,
    timing_warning,
)
from vkdub.providers.elevenlabs_tts import ElevenLabsTTSProvider
from vkdub.providers.tts import TextToSpeechProvider
from vkdub.providers.vbee_tts import VbeeTTSProvider
from vkdub.services.cloud_job import CloudJob
from vkdub.services.credential_service import (
    ElevenLabsKeyStore,
    VbeeAppStore,
    VbeeTokenStore,
)
from vkdub.services.tts_service import file_hash, generate_voice
from vkdub.services.tts_usage import TTSUsage
from vkdub.ui.vbee_dialog import VbeeDialog
from vkdub.ui.voice_panel import VoicePanel
from vkdub.utils.paths import data_root

if TYPE_CHECKING:
    from vkdub.ui.main_window import MainWindow


class TTSController(QObject):
    line_finished = Signal(str, object, str)

    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self.panel = VoicePanel()
        window.left.configuration_layout.addWidget(self.panel)
        self.job: CloudJob | None = None
        self.dialog: VbeeDialog | None = None
        self.close_after_job = False
        self.kind = ""
        self.credential_reason = ""
        self.configured = False
        self.errors: dict[str, str] = {}
        self.force_retry_ids: set[str] = set()
        self.verified_codes: set[str] | None = None
        self.bound_project: object = None
        self.snapshot: str | None = None
        self.audio = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio)
        self.player.errorOccurred.connect(
            lambda *_: window.log("Không phát được voice. Kiểm tra tệp cache và thiết bị âm thanh.")
        )
        self.panel.provider.currentIndexChanged.connect(self.provider_changed)
        self.panel.settings.clicked.connect(self.open_manager)
        self.panel.voice.currentIndexChanged.connect(self.settings_changed)
        self.panel.speed.valueChanged.connect(self.settings_changed)
        self.panel.volume.valueChanged.connect(self.volume_changed)
        self.panel.retry.clicked.connect(lambda: self.start())
        self.panel.listen.clicked.connect(self.listen)
        window.left.voice_settings_changed.connect(self.left_settings_changed)
        window.left.stop_button.clicked.connect(self.stop)
        window.review.voice_requested.connect(lambda identifier: self.start(identifier, force=True))
        window.review.listen_requested.connect(self.listen)
        self.line_finished.connect(self._line_finished)
        self.read_credentials()

    def read_credentials(self) -> None:
        self.verified_codes = None
        if not getattr(self.window, "legacy_tts_enabled", False):
            self.configured = False
            self.credential_reason = (
                "Voice Engine chưa được tích hợp. Có thể lưu và duyệt kịch bản."
            )
            return
        provider = (
            self.window.project.voice.provider
            if hasattr(self, "window") and hasattr(self.window, "project")
            else "vbee"
        )
        try:
            if provider == "elevenlabs":
                self.configured = bool(ElevenLabsKeyStore().get())
                self.credential_reason = (
                    "Đã cấu hình ElevenLabs • 10.000 ký tự Free/tháng."
                    if self.configured
                    else "Thiếu ElevenLabs API Key. Mở Cài đặt để nhập."
                )
            else:
                self.configured = bool(VbeeAppStore().get() and VbeeTokenStore().get())
                self.credential_reason = (
                    "Đã cấu hình • quyền/credit do Vbee quyết định."
                    if self.configured
                    else "Thiếu App ID / token Vbee. Mở Cấu hình Vbee."
                )
        except RuntimeError as exc:
            self.configured = False
            self.credential_reason = str(exc)

    def provider_changed(self) -> None:
        if self.window.busy:
            return
        provider = self.panel.provider.currentData() or "vbee"
        project = self.window.project
        if project.voice.provider == provider:
            return

        self.panel.voice.blockSignals(True)
        self.panel.voice.clear()
        if provider == "elevenlabs":
            for v in POPULAR_ELEVENLABS_VOICES:
                self.panel.voice.addItem(v.name, v.code)
            voice_id = DEFAULT_ELEVENLABS_VOICE
            display_name = DEFAULT_ELEVENLABS_LABEL
            self.panel.settings.setText("Cấu hình / Kiểm tra ElevenLabs")
        else:
            self.panel.voice.addItem(DEFAULT_LABEL, DEFAULT_VOICE)
            voice_id = DEFAULT_VOICE
            display_name = DEFAULT_LABEL
            self.panel.settings.setText("Cấu hình / Kiểm tra Vbee")
        self.panel.voice.blockSignals(False)

        project.voice = replace(
            project.voice,
            provider=provider,
            voice_id=voice_id,
            display_name=display_name,
            speed=self.panel.speed.value(),
        )
        self.read_credentials()
        self._sync_left_panel()
        self.player.stop()
        self.window.dirty = True
        self.window._refresh()

    def open_manager(self) -> None:
        if not getattr(self.window, "legacy_tts_enabled", False):
            self.window.open_settings(2)
            return
        if self.window.busy:
            return
        if self.window.project.voice.provider == "elevenlabs":
            self.window.open_settings(2)
            return
        if self.dialog is None:
            self.dialog = VbeeDialog(self)
        self.dialog.status.setText(self.credential_reason)
        self.dialog.refresh()
        self.dialog.show()
        self.dialog.raise_()

    def settings_changed(self) -> None:
        if self.window.busy:
            return
        project = self.window.project
        project.voice = replace(
            project.voice,
            voice_id=self.panel.voice.currentData(),
            display_name=self.panel.voice.currentText(),
            speed=self.panel.speed.value(),
        )
        self._sync_left_panel()
        self.player.stop()
        self.window.dirty = True
        self.window._refresh()

    def left_settings_changed(self) -> None:
        if not getattr(self.window, "legacy_tts_enabled", False):
            from vkdub.services.app_settings import load_app_settings, save_app_settings

            settings = load_app_settings()
            settings.voice_speed = self.window.left.speed_combo.currentData()
            save_app_settings(settings)
            if self.window.project.voice.provider in ("vieneu_local", "capcut_tts"):
                self.window.project.voice = replace(
                    self.window.project.voice, speed=settings.voice_speed
                )
                self.window.dirty = True
            return
        if self.window.busy:
            return
        left = self.window.left
        voice_id = left.voice_combo.currentData() or DEFAULT_VOICE
        display_name = left.voice_combo.currentText() or DEFAULT_LABEL
        speed_raw = left.speed_combo.currentData()
        speed = float(speed_raw) if speed_raw is not None else 1.0
        project = self.window.project
        project.voice = replace(
            project.voice,
            voice_id=voice_id,
            display_name=display_name,
            speed=speed,
        )
        self.panel.voice.blockSignals(True)
        idx = self.panel.voice.findData(voice_id)
        if idx >= 0:
            self.panel.voice.setCurrentIndex(idx)
        self.panel.voice.blockSignals(False)
        self.panel.speed.blockSignals(True)
        self.panel.speed.setValue(speed)
        self.panel.speed.blockSignals(False)
        self.player.stop()
        self.window.dirty = True
        self.window._refresh()

    def _sync_left_panel(self) -> None:
        if not getattr(self.window, "legacy_tts_enabled", False):
            return
        left = self.window.left
        project = self.window.project
        left.voice_combo.blockSignals(True)
        idx = left.voice_combo.findData(project.voice.voice_id)
        if idx < 0:
            left.voice_combo.addItem(project.voice.display_name, project.voice.voice_id)
            idx = left.voice_combo.count() - 1
        left.voice_combo.setCurrentIndex(idx)
        left.voice_combo.blockSignals(False)

        left.speed_combo.blockSignals(True)
        speed_val = project.voice.speed
        for i in range(left.speed_combo.count()):
            val = left.speed_combo.itemData(i)
            if val is not None and abs(float(val) - speed_val) < 0.01:
                left.speed_combo.setCurrentIndex(i)
                break
        left.speed_combo.blockSignals(False)
        left.voice_combo.setEnabled(not self.window.busy)
        left.speed_combo.setEnabled(not self.window.busy)

    def volume_changed(self) -> None:
        self.window.project.voice = replace(
            self.window.project.voice, volume=self.panel.volume.value() / 100
        )
        self.audio.setVolume(self.window.project.voice.volume)
        self.window.dirty = True

    def refresh(self) -> None:
        project = self.window.project
        if self.bound_project is not project:
            self.bound_project = project
            self.errors.clear()
            self.force_retry_ids.clear()
            self.player.stop()

        provider_idx = self.panel.provider.findData(project.voice.provider)
        if provider_idx >= 0 and self.panel.provider.currentIndex() != provider_idx:
            self.panel.provider.blockSignals(True)
            self.panel.provider.setCurrentIndex(provider_idx)
            self.panel.provider.blockSignals(False)

        self.panel.settings.setText(
            "Cấu hình / Kiểm tra ElevenLabs"
            if project.voice.provider == "elevenlabs"
            else "Cấu hình / Kiểm tra Vbee"
        )

        for widget in (self.panel.voice, self.panel.speed, self.panel.volume):
            widget.blockSignals(True)
        index = self.panel.voice.findData(project.voice.voice_id)
        if index < 0:
            self.panel.voice.addItem(project.voice.display_name, project.voice.voice_id)
            index = self.panel.voice.count() - 1
        self.panel.voice.setCurrentIndex(index)
        self.panel.speed.setValue(project.voice.speed)
        self.panel.volume.setValue(project.voice.volume * 100)
        for widget in (self.panel.voice, self.panel.speed, self.panel.volume):
            widget.blockSignals(False)
            widget.setEnabled(not self.window.busy)
        self.audio.setVolume(project.voice.volume)
        self._sync_left_panel()
        ready = (
            self.configured
            and bool(self.window.tools.paths["ffmpeg"])
            and bool(self.window.tools.paths["ffprobe"])
        )
        reason = self.credential_reason
        if self.verified_codes is not None and project.voice.voice_id not in self.verified_codes:
            ready = False
            reason = "API không liệt kê giọng đang chọn. Chọn giọng khác hoặc kiểm tra gói API."
        if self.configured and (
            not self.window.tools.paths["ffmpeg"] or not self.window.tools.paths["ffprobe"]
        ):
            reason = "Thiếu FFmpeg/ffprobe để kiểm tra và ghép voice."
        self.panel.status.setText(reason)
        self.panel.settings.setEnabled(not self.window.busy)
        self.panel.retry.setEnabled(ready and project.is_approved and not self.window.busy)
        self.panel.retry.setToolTip(
            reason if not ready else "Tạo câu thiếu/lỗi, dùng lại cache hợp lệ."
        )
        panel = self.window.review
        current_voices = project.current_voices()
        if not project.is_approved:
            self.player.stop()
        if panel.editor:
            identifier = panel.editor.line_id
            asset = current_voices.get(identifier)
            panel.editor.voice_button.setEnabled(
                ready and project.is_approved and not self.window.busy
            )
            provider_title = "ElevenLabs" if project.voice.provider == "elevenlabs" else "Vbee"
            btn_tip = (
                f"Tạo lại câu qua {provider_title}; bỏ qua cache và có thể tính phí."
                if ready
                else reason
            )
            panel.editor.voice_button.setToolTip(btn_tip)
            panel.editor.listen_button.setEnabled(bool(asset) and not self.window.busy)
            line = (
                next(line for line in project.script.lines if line.id == identifier)
                if project.script
                else None
            )
            warning = (
                timing_warning(asset.duration_ms, line.end_ms - line.start_ms)
                if asset and line
                else ""
            )
            text = (
                f"Voice: {asset.duration_ms / 1000:.2f}s"
                if asset
                else "Chưa có voice cho nội dung/giọng hiện tại."
            )
            panel.editor.voice_status.setText(self.errors.get(identifier, "") or warning or text)
            panel.editor.voice_status.setToolTip(self.errors.get(identifier, "") or warning or text)
        current = panel.editor.line_id if panel.editor else ""
        self.panel.listen.setEnabled(bool(current_voices.get(current)) and not self.window.busy)
        count = len(current_voices)
        total = len(project.script.lines) if project.script else 0
        note_suffix = (
            reason
            if not ready
            else ("Sẵn sàng xuất video." if project.voice_ready else "Chỉ tạo voice sau khi duyệt.")
        )
        panel.voice_note.setText(
            f"Voice: {count}/{total} câu • {len(self.errors)} câu lỗi. {note_suffix}"
        )
        panel.export_button.setEnabled(not self.window.busy and project.voice_ready)
        if project.script:
            for index, line in enumerate(project.script.lines):
                if error := self.errors.get(line.id):
                    item = panel.rows.item(index)
                    item.setText(item.text().split("\n⚠ Voice lỗi:")[0] + "\n⚠ Voice lỗi: " + error)
        if project.is_approved:
            panel.stage.setText(f"{self.window.workflow_state} • Voice {count}/{total}")
        if self.job:
            self.window.left.stop_button.setEnabled(not self.job.cancel_event.is_set())
        if self.dialog:
            self.dialog.refresh()

    def test_connection(self) -> bool:
        return self._launch("test")

    def start(self, line_id: str | None = None, force: bool = False) -> bool:
        if not getattr(self.window, "legacy_tts_enabled", False):
            self.window.log("Voice Engine chưa được tích hợp trong bản này.")
            return False
        if self.window.busy:
            return False
        if (
            self.verified_codes is not None
            and self.window.project.voice.voice_id not in self.verified_codes
        ):
            self.window.log(
                "Giọng đang chọn không được API liệt kê. Chọn giọng khác hoặc kiểm tra lại."
            )
            return False
        try:
            self.window.project.require_approval()
        except ValueError as exc:
            self.window.log(str(exc))
            return False
        if not self.window.tools.paths["ffmpeg"] or not self.window.tools.paths["ffprobe"]:
            self.window.log("Thiếu FFmpeg/ffprobe để tạo và đo voice.")
            return False
        if line_id and (
            not self.window.project.script
            or line_id not in {line.id for line in self.window.project.script.lines}
        ):
            return False
        return self._launch("voice", line_id, force)

    def _launch(self, kind: str, line_id: str | None = None, force: bool = False) -> bool:
        if not getattr(self.window, "legacy_tts_enabled", False):
            self.window.log("Voice Engine chưa được tích hợp; không tạo voice trong bản này.")
            return False
        if self.window.busy:
            return False
        if not self.configured:
            self.window.log(self.credential_reason)
            self.window._refresh()
            return False
        provider_name = self.window.project.voice.provider
        display_provider = "ElevenLabs" if provider_name == "elevenlabs" else "Vbee"
        provider: TextToSpeechProvider
        try:
            if provider_name == "elevenlabs":
                key = ElevenLabsKeyStore().get()
                assert key
                provider = ElevenLabsTTSProvider(key, TTSUsage())
            else:
                app_id, token = VbeeAppStore().get(), VbeeTokenStore().get()
                assert app_id and token
                provider = VbeeTTSProvider(app_id, token, TTSUsage())
        except (RuntimeError, ValueError, OSError, AssertionError):
            self.window.log(f"Không mở được thông tin {display_provider}/thống kê cục bộ.")
            return False
        project = self.window.project
        self.snapshot = project.revision_hash
        self.kind = kind
        if force and line_id:
            self.force_retry_ids.add(line_id)
        force_ids = set(self.force_retry_ids) if not line_id else ({line_id} if force else set())

        async def operation() -> Any:
            if kind == "test":
                return await provider.list_voices()
            return await generate_voice(
                project,
                provider,
                data_root() / "cache" / "tts",
                str(self.window.tools.paths["ffmpeg"]),
                str(self.window.tools.paths["ffprobe"]),
                job.progress.emit,
                job.check_cancel,
                self.line_finished.emit,
                {line_id} if line_id else None,
                force_ids,
            )

        job = CloudJob(operation)
        self.job = job
        job.progress.connect(self.window.transcription._progress)
        job.succeeded.connect(self._succeeded)
        job.failed.connect(self._failed)
        cancel_msg = (
            f"Đã dừng {display_provider}. "
            "Yêu cầu đã gửi vẫn có thể tính phí; cache hoàn tất được giữ lại."
        )
        job.cancelled.connect(lambda: self._failed(cancel_msg))
        job.finished.connect(self._finished)
        self.window.busy = True
        self.player.stop()
        self.window.preview.player.pause()
        self.player.setSource(QUrl())
        self.window.log(
            f"Đang kiểm tra {display_provider}…"
            if kind == "test"
            else f"Đang tạo voice từ kịch bản đã duyệt qua {display_provider}…"
        )
        self.window._refresh()
        job.start()
        return True

    def _line_finished(self, identifier: str, asset: VoiceAsset | None, error: str) -> None:
        project = self.window.project
        if project.revision_hash != self.snapshot or not project.is_approved:
            return
        if asset:
            project.voice_assets[identifier] = asset
            self.errors.pop(identifier, None)
            self.force_retry_ids.discard(identifier)
            self.window.dirty = True
        else:
            self.errors[identifier] = error
            self.window.log(f"Voice câu lỗi: {error}")
        self.window._refresh()

    def _succeeded(self, result: Any) -> None:
        if self.kind == "test":
            voices: tuple[Voice, ...] = result
            self.verified_codes = {voice.code for voice in voices}
            self.panel.voice.blockSignals(True)
            self.window.left.voice_combo.blockSignals(True)
            for voice in voices:
                if self.panel.voice.findData(voice.code) < 0:
                    self.panel.voice.addItem(voice.name, voice.code)
                if self.window.left.voice_combo.findData(voice.code) < 0:
                    self.window.left.voice_combo.addItem(voice.name, voice.code)
            self.panel.voice.blockSignals(False)
            self.window.left.voice_combo.blockSignals(False)
            selected = self.window.project.voice.voice_id
            provider_title = (
                "ElevenLabs" if self.window.project.voice.provider == "elevenlabs" else "Realtime"
            )
            self.credential_reason = (
                f"Kết nối đã kiểm tra • {len(voices)} giọng {provider_title}. Credit chưa xác minh."
                if any(v.code == selected for v in voices)
                else "API không liệt kê giọng đang chọn. Chọn giọng khác hoặc kiểm tra gói API."
            )
            if self.dialog:
                self.dialog.status.setText(self.credential_reason)
            self.window.log(self.credential_reason)
        else:
            self.window.log(
                "Hoàn tất lượt tạo voice. Kiểm tra audio và các cảnh báo; chưa xuất video."
            )

    def _failed(self, message: str) -> None:
        self.window.log(message)
        if self.dialog:
            self.dialog.status.setText(message)

    def _finished(self) -> None:
        if self.job:
            self.job.deleteLater()
        self.job = None
        self.window.busy = False
        self.window._refresh()
        if self.close_after_job:
            self.close_after_job = False
            self.window.close()

    def stop(self) -> None:
        if self.job:
            self.job.cancel()
            self.window.log("Đang dừng Vbee…")
            self.refresh()

    def listen(self) -> None:
        if self.window.busy:
            return
        project = self.window.project
        editor = self.window.review.editor
        target_line_id: str | None = None
        if editor is not None:
            target_line_id = editor.line_id
        elif project.script and project.script.lines:
            row = self.window.review.rows.currentRow()
            if 0 <= row < len(project.script.lines):
                target_line_id = project.script.lines[row].id
            else:
                current_voices = project.current_voices()
                for line in project.script.lines:
                    if line.id in current_voices:
                        target_line_id = line.id
                        break
                if target_line_id is None:
                    target_line_id = project.script.lines[0].id

        if target_line_id is None:
            self.window.log("Chưa có câu kịch bản để nghe thử.")
            return

        asset = project.current_voice(target_line_id)
        if asset is None:
            self.window.log("Chưa có voice cho câu đã duyệt đang chọn.")
            return

        # Hash verification is delegated to a worker before playback to keep large files off UI.
        async def verify() -> VoiceAsset:
            if file_hash(asset.output_path) != asset.audio_sha256:
                raise ValueError("Tệp voice đã đổi/hỏng. Hãy tạo lại câu.")
            return asset

        job = CloudJob(verify)
        self.job, self.kind = job, "listen"

        def play(result: VoiceAsset) -> None:
            if (
                self.job is None
                or self.job.cancel_event.is_set()
                or self.window.project.current_voice(target_line_id) != result
            ):
                return
            self.window.preview.player.pause()
            self.player.setSource(QUrl.fromLocalFile(str(result.output_path)))
            self.player.play()

        job.succeeded.connect(play)
        job.failed.connect(self._failed)
        job.finished.connect(self._finished)
        self.window.busy = True
        self.window._refresh()
        job.start()
