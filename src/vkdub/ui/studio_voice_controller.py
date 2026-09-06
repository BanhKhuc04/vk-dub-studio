"""The v2 local voice workflow, retaining the legacy controller for old test harnesses."""

from collections.abc import Callable, Coroutine
from dataclasses import replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl

from vkdub.domain.voice import VoiceSettings, audio_key, timing_warning
from vkdub.media.voice_audio import audio_duration
from vkdub.providers.capcut_tts import CapCutTTSProvider
from vkdub.providers.vieneu_local import VieNeuLocalProvider
from vkdub.services.app_settings import load_app_settings, save_app_settings
from vkdub.services.capcut_setup import setup_capcut
from vkdub.services.cloud_job import CloudJob
from vkdub.services.health_service import check_tts_backend
from vkdub.services.tts_service import generate_voice
from vkdub.services.vieneu_setup import register_voice, setup_vieneu
from vkdub.services.voice_catalog import read_catalog
from vkdub.ui.tts_controller import TTSController
from vkdub.utils.paths import workspace_root


class StudioVoiceController(TTSController):
    def read_credentials(self) -> None:
        if getattr(self.window, "legacy_tts_enabled", False):
            super().read_credentials()
            return
        try:
            self.backend = self.window.project.voice.provider
            self.catalog = read_catalog(self.backend)
            health = check_tts_backend(self.backend)
            self.configured = health.ok and bool(self.catalog)
            self.credential_reason = health.message
        except ValueError as exc:
            self.catalog = []
            self.configured = False
            self.credential_reason = str(exc)

    def _sync_left_panel(self) -> None:
        if getattr(self.window, "legacy_tts_enabled", False):
            super()._sync_left_panel()
            return
        left, project = self.window.left, self.window.project
        rows = self.catalog if self.configured else []
        left.voice_combo.blockSignals(True)
        left.voice_combo.clear()
        for row in rows:
            left.voice_combo.addItem(row["name"], row["id"])
        if not rows:
            left.voice_combo.addItem("Mở Quản lý giọng để kết nối / cài giọng", "")
        elif project.voice.voice_id == "unconfigured":
            project.voice = replace(
                project.voice, voice_id=rows[0]["id"], display_name=rows[0]["name"]
            )
        index = left.voice_combo.findData(project.voice.voice_id)
        if index >= 0 and rows and project.voice.display_name != left.voice_combo.itemText(index):
            project.voice = replace(project.voice, display_name=left.voice_combo.itemText(index))
        left.voice_combo.setCurrentIndex(index if index >= 0 else 0 if not rows else -1)
        left.voice_combo.setToolTip(project.voice.display_name)
        left.voice_combo.blockSignals(False)
        left.voice_combo.setEnabled(bool(rows) and not self.window.busy)

    def left_settings_changed(self) -> None:
        if getattr(self.window, "legacy_tts_enabled", False):
            super().left_settings_changed()
            return
        if self.window.busy:
            return
        left = self.window.left
        settings = load_app_settings()
        settings.voice_speed = left.speed_combo.currentData()
        identifier = left.voice_combo.currentData()
        if identifier:
            settings.selected_voice = identifier
            settings.tts_backend = self.backend
            self.window.project.voice = VoiceSettings(
                provider=self.backend,
                voice_id=identifier,
                display_name=left.voice_combo.currentText(),
                speed=settings.voice_speed,
                volume=min(1, settings.voice_volume / 100),
            )
        else:
            self.window.project.voice = replace(
                self.window.project.voice, speed=settings.voice_speed
            )
        save_app_settings(settings)
        self.player.stop()
        self.window.dirty = True
        self.window._refresh()

    def refresh(self) -> None:
        if getattr(self.window, "legacy_tts_enabled", False):
            super().refresh()
            return
        project, panel = self.window.project, self.window.review
        if self.bound_project is not project:
            self.read_credentials()
            self.bound_project = project
            self.errors.clear()
            self.force_retry_ids.clear()
            self.player.stop()
        self._sync_left_panel()
        self.audio.setVolume(project.voice.volume)
        ready = self.can_generate()
        current = project.current_voices()
        if panel.editor:
            identifier = panel.editor.line_id
            asset = current.get(identifier)
            panel.editor.voice_button.setEnabled(
                ready and project.is_approved and not self.window.busy
            )
            panel.editor.voice_button.setToolTip("Tạo lại câu bằng giọng đang chọn.")
            panel.editor.listen_button.setEnabled(bool(asset) and not self.window.busy)
            line = (
                next((r for r in project.script.lines if r.id == identifier), None)
                if project.script
                else None
            )
            warning = (
                timing_warning(asset.duration_ms, line.end_ms - line.start_ms)
                if asset and line
                else ""
            )
            panel.editor.voice_status.setText(
                self.errors.get(identifier)
                or warning
                or (
                    f"Voice: {asset.duration_ms / 1000:.2f}s"
                    if asset
                    else "Chưa có voice cho câu này."
                )
            )
        total = len(project.script.lines) if project.script else 0
        panel.voice_note.setText(
            f"Voice: {len(current)}/{total} câu • {len(self.errors)} câu lỗi. "
            + (
                "Có thể nghe voice từng câu."
                if project.voice_ready
                else "Bấm tạo voice để tiếp tục các câu còn thiếu."
                if project.is_approved and ready
                else "Duyệt kịch bản để tạo voice."
                if ready
                else self.credential_reason
            )
        )
        if project.is_approved:
            panel.stage.setText(f"Đã tạo voice {len(current)}/{total} câu")
        panel.export_button.setEnabled(False)
        if self.job:
            self.window.left.stop_button.setEnabled(not self.job.cancel_event.is_set())

    def can_generate(self) -> bool:
        if self.backend == "vbee":
            return bool(
                self.configured
                and self.window.project.voice.provider == "vbee"
                and self.window.tools.paths.get("ffmpeg")
                and self.window.tools.paths.get("ffprobe")
            )
        return bool(
            self.configured
            and self.window.project.voice.provider == self.backend
            and any(r["id"] == self.window.project.voice.voice_id for r in self.catalog)
            and self.window.tools.paths.get("ffmpeg")
            and self.window.tools.paths.get("ffprobe")
        )

    def _local_job(self, kind: str, operation: Callable[[], Coroutine[Any, Any, Any]]) -> bool:
        if self.window.busy:
            return False
        job = CloudJob(operation)
        self.job, self.kind = job, kind
        self.snapshot = self.window.project.revision_hash
        job.progress.connect(self.window.transcription._progress)
        job.succeeded.connect(self._succeeded)
        job.failed.connect(self._failed)
        job.cancelled.connect(
            lambda: self._failed("Đã dừng tạo voice. Các câu đã tạo được giữ lại.")
        )
        job.finished.connect(self._finished)
        self.window.busy = True
        self.player.stop()
        self.window.preview.player.pause()
        self.window.left.job_progress.setRange(0, 0)
        self.window._refresh()
        if self.window.settings_dialog is not None:
            self.window.settings_dialog.refresh_voice_catalog()
        job.start()
        return True

    def start(self, line_id: str | None = None, force: bool = False) -> bool:
        if getattr(self.window, "legacy_tts_enabled", False):
            return super().start(line_id, force)
        if self.window.busy:
            return False
        try:
            self.window.project.require_approval()
        except ValueError as exc:
            self.window.log(str(exc))
            return False
        if not self.can_generate():
            self.window.log(self.credential_reason)
            self.window.open_settings(2)
            return False
        project = self.window.project

        # If active voice provider is Vbee, run Vbee workflow automation!
        if project.voice.provider == "vbee":
            if hasattr(self.window, "vbee_controller") and self.window.vbee_controller:
                return self.window.vbee_controller.start_workflow()
            self.window.log("Chưa sẵn sàng bộ điều khiển Vbee.")
            return False

        if line_id and (not project.script or line_id not in {r.id for r in project.script.lines}):
            return False
        if force and line_id:
            self.force_retry_ids.add(line_id)

        async def operation() -> None:
            assert self.job
            provider = self.provider(project.voice.provider)
            try:
                await generate_voice(
                    project,
                    provider,
                    workspace_root() / "cache" / "tts",
                    str(self.window.tools.paths["ffmpeg"]),
                    str(self.window.tools.paths["ffprobe"]),
                    self.job.progress.emit,
                    self.job.check_cancel,
                    self.line_finished.emit,
                    {line_id} if line_id else None,
                    set(self.force_retry_ids),
                )
            finally:
                await provider.close()

        self.window.log("Đang tạo voice từ kịch bản đã duyệt bằng giọng đang chọn…")
        return self._local_job("voice", operation)

    def provider(self, backend: str) -> VieNeuLocalProvider:
        factory = CapCutTTSProvider if backend == "capcut_tts" else VieNeuLocalProvider
        return factory(str(self.window.tools.paths["ffmpeg"]))

    def select_voice(self, backend: str, identifier: str) -> bool:
        if self.window.busy or not check_tts_backend(backend).ok:
            return False
        row = next((r for r in read_catalog(backend) if r["id"] == identifier), None)
        if row is None:
            return False
        settings = load_app_settings()
        settings.tts_backend, settings.selected_voice = backend, identifier
        save_app_settings(settings)
        self.window.project.voice = replace(
            self.window.project.voice,
            provider=backend,
            voice_id=identifier,
            display_name=row["name"],
        )
        self.player.stop()
        self.window.dirty = True
        self.read_credentials()
        self.window._refresh()
        return True

    def setup_engine(self, backend: str = "vieneu_local") -> bool:
        if self.window.busy:
            return False
        if backend == "vbee":
            async def vbee_test_operation() -> list[dict]:
                assert self.job
                from playwright.async_api import async_playwright

                from vkdub.integrations.vbee.automation import VbeeBrowserAutomation
                from vkdub.integrations.vbee.session import create_vbee_browser_context
                from vkdub.services.voice_catalog import read_catalog

                self.job.progress.emit("Đang mở trình duyệt Vbee Dubbing Studio...")
                async with async_playwright() as p:
                    context = await create_vbee_browser_context(p, headless=False)
                    try:
                        automation = VbeeBrowserAutomation(context)
                        await automation.open_dubbing_studio()
                        self.job.progress.emit("Đang kiểm tra trạng thái đăng nhập Vbee...")
                        logged_in = await automation.is_logged_in()
                        if logged_in:
                            self.job.progress.emit("✓ Vbee đã đăng nhập sẵn. Sẵn sàng sử dụng!")
                        else:
                            self.job.progress.emit(
                                "Vbee chưa đăng nhập. Vui lòng đăng nhập trên cửa sổ vừa mở..."
                            )
                            await automation.wait_for_user_login(
                                timeout_s=90,
                                check_cancel=self.job.check_cancel,
                                progress_callback=self.job.progress.emit,
                            )
                            self.job.progress.emit("✓ Đăng nhập Vbee thành công!")
                    finally:
                        await context.close()
                return read_catalog("vbee")

            self.setup_backend = backend
            return self._local_job("setup", vbee_test_operation)

        if not self.window.tools.paths.get("ffmpeg") or not self.window.tools.paths.get("ffprobe"):
            self.window.log("Cần FFmpeg/ffprobe trước khi kiểm tra Voice Engine.")
            return False

        async def operation() -> list[dict]:
            assert self.job
            setup = setup_capcut if backend == "capcut_tts" else setup_vieneu
            return await setup(
                str(self.window.tools.paths["ffmpeg"]),
                str(self.window.tools.paths["ffprobe"]),
                self.job.progress.emit,
            )

        self.setup_backend = backend
        return self._local_job("setup", operation)

    def add_voice(self, name: str, reference: Path) -> bool:
        if not self.configured or not self.window.tools.paths.get("ffmpeg"):
            return False

        async def operation() -> str:
            return await register_voice(
                name,
                reference,
                str(self.window.tools.paths["ffmpeg"]),
                str(self.window.tools.paths["ffprobe"]),
            )

        return self._local_job("register", operation)

    def preview_voice(self, identifier: str | None = None, backend: str | None = None) -> bool:
        backend = backend or self.window.project.voice.provider
        if backend == "vbee":
            self.window.log(
                "Vbee tạo voice qua trình duyệt; bấm Duyệt kịch bản để tạo voice tự động."
            )
            return False
        if (
            not check_tts_backend(backend).ok
            or self.window.busy
            or not self.window.tools.paths.get("ffmpeg")
            or not self.window.tools.paths.get("ffprobe")
        ):
            return False
        settings = replace(
            self.window.project.voice,
            provider=backend,
            voice_id=identifier or self.window.project.voice.voice_id,
        )

        async def operation() -> Path:
            text = "Xin chào, đây là giọng đọc của VK Dub Studio. Chúc bạn một ngày tốt lành."
            folder = workspace_root() / "cache" / "voice-preview"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{audio_key(text, settings)}.wav"
            if path.is_file():
                await audio_duration(path, str(self.window.tools.paths["ffprobe"]))
                return path
            provider = self.provider(settings.provider)
            temporary = path.with_suffix(".pending.wav")
            try:
                await provider.synthesize(text, settings.voice_id, settings.speed, temporary)
                await audio_duration(temporary, str(self.window.tools.paths["ffprobe"]))
                temporary.replace(path)
            finally:
                await provider.close()
                temporary.unlink(missing_ok=True)
            return path

        return self._local_job("preview", operation)

    def _succeeded(self, result: Any) -> None:
        if getattr(self.window, "legacy_tts_enabled", False):
            super()._succeeded(result)
            return
        if self.kind in ("setup", "register"):
            backend = self.setup_backend if self.kind == "setup" else "vieneu_local"
            rows = read_catalog(backend)
            settings = load_app_settings()
            identifier = result if self.kind == "register" else rows[0]["id"]
            row = next(r for r in rows if r["id"] == identifier)
            settings.tts_backend, settings.selected_voice = backend, identifier
            save_app_settings(settings)
            self.window.project.voice = replace(
                self.window.project.voice,
                provider=backend,
                voice_id=identifier,
                display_name=row["name"],
            )
            self.read_credentials()
            self.window.dirty = True
            self.window.log(
                "Vbee Dubbing Studio đã kết nối và sẵn sàng tạo voice tự động."
                if backend == "vbee"
                else "Giọng đọc đã sẵn sàng. Bạn có thể chọn giọng và nghe thử."
            )
        elif self.kind == "preview":
            self.last_preview_path = result
            self.player.setSource(QUrl.fromLocalFile(str(result)))
            self.player.play()
            self.window.log("Đang phát mẫu giọng đã chọn.")
        else:
            super()._succeeded(result)

    def _finished(self) -> None:
        super()._finished()
        dialog = self.window.settings_dialog
        if dialog is not None and hasattr(dialog, "refresh_voice_catalog"):
            dialog.refresh_voice_catalog()

    def _failed(self, message: str) -> None:
        super()._failed(message)
        if not getattr(self.window, "legacy_tts_enabled", False):
            from vkdub.providers.tts_provider import HealthResult

            self.last_error = message
            self.window.health_banner.set_result(
                HealthResult(
                    False,
                    "VIENEU_FAILED",
                    "Voice chưa hoàn thành",
                    message,
                    "Cài đặt Voice",
                    "open_settings_voice",
                )
            )

    def _line_finished(self, identifier: str, asset: Any, error: str) -> None:
        if not getattr(self.window, "legacy_tts_enabled", False) and (
            self.job is None or self.job.cancel_event.is_set()
        ):
            return
        super()._line_finished(identifier, asset, error)

    def stop(self) -> None:
        if getattr(self.window, "legacy_tts_enabled", False):
            super().stop()
        elif self.job:
            self.job.cancel()
            self.window.log("Đang dừng Voice Engine…")
