"""VoiceProvider abstraction and extensible provider implementations for Vbee."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from vkdub.domain.project import Project
    from vkdub.integrations.vbee.automation import VbeeBrowserAutomation

from vkdub.integrations.vbee.importer import convert_to_pcm_wav
from vkdub.media.voice_audio import audio_duration

logger = logging.getLogger("vkdub.vbee")


class VoiceProvider(Protocol):
    """General protocol for voice synthesis providers (Browser automation, API, etc.)."""

    name: str

    async def execute_dubbing(
        self,
        project: Project,
        srt_path: Path,
        progress_callback: Callable[[int, str], None],
        check_cancel: Callable[[], None],
        speed: float | None = None,
    ) -> Path:
        """Execute the dubbing workflow and return the path to the downloaded audio."""
        ...

    async def close(self) -> None:
        """Release any held network or browser resources."""
        ...


class VbeeBrowserProvider:
    """Vbee Voice Provider implementation backed by Playwright browser automation."""

    name = "vbee_browser"

    def __init__(
        self,
        downloads_dir: Path | None = None,
        headless: bool = False,
    ) -> None:
        self.downloads_dir = downloads_dir
        self.headless = headless
        self._automation: VbeeBrowserAutomation | None = None

    async def execute_dubbing(
        self,
        project: Project,
        srt_path: Path,
        progress_callback: Callable[[int, str], None],
        check_cancel: Callable[[], None],
        speed: float | None = None,
    ) -> Path:
        """Coordinate browser automation steps from upload to download."""
        from playwright.async_api import async_playwright

        from vkdub.integrations.vbee.automation import VbeeBrowserAutomation
        from vkdub.integrations.vbee.session import create_vbee_browser_context

        logger.info("[VBEE][BROWSER] Đang khởi chạy trình duyệt…")
        progress_callback(15, "Đang khởi chạy trình duyệt…")
        check_cancel()
        target_dir = self.downloads_dir or Path(srt_path.parent)
        target_dir.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as playwright:
            context = await create_vbee_browser_context(
                playwright=playwright,
                downloads_path=self.downloads_dir,
                headless=self.headless,
            )
            automation = VbeeBrowserAutomation(context, self.downloads_dir)
            automation.cleanup_partial_downloads(target_dir)
            self._automation = automation
            completed = False

            try:
                progress_callback(25, "Đang mở Vbee Dubbing Studio…")
                await automation.open_dubbing_studio()
                check_cancel()

                # Verify authentication
                logger.info("[VBEE][LOGIN] Kiểm tra trạng thái đăng nhập Vbee…")
                logged_in = await automation.is_logged_in()
                if not logged_in:
                    logger.info("[VBEE][LOGIN] Chưa đăng nhập — chờ người dùng đăng nhập…")
                    progress_callback(30, "Chờ đăng nhập Vbee trên trình duyệt…")
                    # Wait for user to log in interactively
                    await automation.wait_for_user_login(
                        check_cancel=check_cancel,
                        progress_callback=lambda msg: progress_callback(35, msg),
                    )

                logger.info("[VBEE][LOGIN] Phiên đăng nhập hợp lệ.")
                progress_callback(42, "Cấu hình giọng đọc HN - Ngọc Huyền…")
                check_cancel()
                logger.info("[VBEE][VOICE] Thiết lập giọng đọc 'HN - Ngọc Huyền'…")
                await automation.ensure_voice_ngoc_huyen()

                target_speed = (
                    speed
                    if speed is not None
                    else (
                        getattr(project.voice, "speed", 1.1) if project and project.voice else 1.1
                    )
                )
                speed_label = f"{target_speed:.2f}".rstrip("0").rstrip(".") + "x"
                progress_callback(48, f"Cấu hình tốc độ {speed_label} & định dạng MP3…")
                check_cancel()
                logger.info("[VBEE][SPEED] Thiết lập tốc độ đọc %s…", speed_label)
                await automation.ensure_speed(target_speed)
                logger.info("[VBEE][FORMAT] Thiết lập định dạng MP3…")
                await automation.ensure_format_mp3()

                # Upload last because Vbee rebuilds and clears its file input when
                # voice/speed/format settings change.
                progress_callback(54, "Đang tải file SRT lên hệ thống Vbee…")
                check_cancel()
                logger.info("[VBEE][UPLOAD] Đang tải file phụ đề lên Vbee: %s", srt_path.name)
                await automation.upload_srt(srt_path)

                progress_callback(58, "Đang bắt đầu chuyển phụ đề…")
                check_cancel()
                previous_rows = await automation.snapshot_job_rows()
                logger.info("[VBEE][SUBMIT] Bắt đầu chuyển phụ đề…")
                await automation.submit_conversion()

                progress_callback(65, "Đang định vị dòng công việc…")
                check_cancel()
                logger.info("[VBEE][JOB] Định vị dòng công việc khớp với: %s", srt_path.name)
                job_row = await automation.find_job_row(
                    srt_path.name,
                    timeout_s=45.0,
                    previous_rows=previous_rows,
                )
                progress_callback(70, "Vbee đang chuyển đổi phụ đề thành voice…")
                await automation.wait_job_completion(
                    job_row=job_row,
                    unique_name=srt_path.name,
                    check_cancel=check_cancel,
                    progress_callback=progress_callback,
                )
                progress_callback(90, "Đang tải file âm thanh kết quả…")
                check_cancel()
                logger.info("[VBEE][DOWNLOAD] Bắt đầu tải file âm thanh từ dòng công việc…")
                audio_path = await automation.download_from_job_row(
                    job_row=job_row,
                    target_dir=target_dir,
                )

                progress_callback(95, "Tải file hoàn tất!")
                completed = True
                return audio_path

            except Exception as exc:
                logger.error("[VBEE] Lỗi trong quá trình automation: %s", exc, exc_info=True)
                await automation.capture_debug_screenshot("vbee_error")
                raise
            finally:
                if not completed:
                    automation.cleanup_partial_downloads(target_dir)
                await automation.close()
                self._automation = None

    async def close(self) -> None:
        if self._automation:
            await self._automation.close()
            self._automation = None


VBEE_API_VOICE_MAP: dict[str, tuple[str, str]] = {
    "vbee-ngoc-huyen": ("hn_female_ngochuyen_full_48k-fhg", "HN - Ngọc Huyền"),
    "vbee-tuong-vy": ("sg_female_tuongvy_news_48k-fhg", "SG - Tường Vy"),
    "vbee-mai-phuong": ("hn_female_maiphuong_news_48k-fhg", "HN - Mai Phương"),
    "vbee-lan-trinh": ("sg_female_lantrinh_news_48k-fhg", "SG - Lan Trinh"),
    "vbee-thao-trinh": ("sg_female_thaotrinh_news_48k-fhg", "SG - Thảo Trinh"),
}


class VbeeApiProvider:
    """Vbee Voice Provider implementation backed by the official Vbee Realtime API."""

    name = "vbee_api"

    def __init__(
        self,
        app_id: str,
        token: str,
        ffmpeg: str = "ffmpeg",
        ffprobe: str = "ffprobe",
        voice_id: str = "hn_female_ngochuyen_full_48k-fhg",
        display_name: str = "HN - Ngọc Huyền",
        output_dir: Path | None = None,
        transport: Any = None,
    ) -> None:
        self.app_id = app_id
        self.token = token
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.voice_id = voice_id
        self.display_name = display_name
        self.output_dir = output_dir
        self.transport = transport
        self._tts_provider: Any = None

    def _get_tts(self) -> Any:
        if self._tts_provider is None:
            from vkdub.providers.vbee_tts import VbeeTTSProvider
            from vkdub.services.tts_usage import TTSUsage

            self._tts_provider = VbeeTTSProvider(
                app_id=self.app_id,
                token=self.token,
                usage=TTSUsage(),
                transport=self.transport,
            )
        return self._tts_provider

    async def execute_dubbing(
        self,
        project: Project,
        srt_path: Path,
        progress_callback: Callable[[int, str], None],
        check_cancel: Callable[[], None],
        speed: float | None = None,
    ) -> Path:
        """VoiceProvider protocol method: executes API dubbing and returns master audio path."""
        result = await self.execute_api_dubbing(
            project=project,
            ffmpeg=self.ffmpeg,
            ffprobe=self.ffprobe,
            progress_callback=progress_callback,
            check_cancel=check_cancel,
            speed=speed,
        )
        return Path(result["master_wav"])

    async def execute_api_dubbing(
        self,
        project: Project,
        ffmpeg: str,
        ffprobe: str,
        progress_callback: Callable[[int, str], None],
        check_cancel: Callable[[], None],
        speed: float | None = None,
    ) -> dict[str, Any]:
        """Synthesize script lines via Vbee API, generate VoiceAssets, and assemble master WAV."""
        import wave
        from datetime import UTC, datetime

        from vkdub.domain.voice import VoiceAsset, VoiceSettings, audio_key, digest, normalized_text
        from vkdub.services.tts_service import file_hash, split_text
        from vkdub.utils.paths import data_root

        if not project.script or not project.script.lines:
            raise ValueError("Project chưa có kịch bản để tạo voice.")

        # Determine voice code & display name
        voice_id = self.voice_id
        display_name = self.display_name
        if project.voice and project.voice.voice_id:
            vid = project.voice.voice_id
            if vid in VBEE_API_VOICE_MAP:
                voice_id, display_name = VBEE_API_VOICE_MAP[vid]
            elif not vid.startswith("vbee-"):
                voice_id = vid
                display_name = project.voice.display_name or "HN - Ngọc Huyền"

        # Speed: default 1.1x
        effective_speed = 1.1
        if speed is not None:
            effective_speed = float(speed)
        elif project.voice and getattr(project.voice, "speed", None) is not None:
            effective_speed = float(project.voice.speed)
        effective_speed = max(0.8, min(1.3, effective_speed))

        voice_settings = VoiceSettings(
            provider="vbee",
            voice_id=voice_id,
            display_name=display_name,
            speed=effective_speed,
            volume=getattr(project.voice, "volume", 1.0) if project.voice else 1.0,
        )
        project.voice = voice_settings

        # Determine target directory
        if self.output_dir is not None:
            target_dir = self.output_dir
        elif project.output_directory and project.output_directory.is_dir():
            target_dir = project.output_directory / "audio" / "vbee"
        else:
            target_dir = data_root() / "cache" / "tts" / "vbee"

        target_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = target_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "[VBEE][API] Bắt đầu tổng hợp voice qua Vbee API: giọng=%s, tốc độ=%.1fx, tổng câu=%d",
            voice_id,
            effective_speed,
            len(project.script.lines),
        )
        progress_callback(10, f"Đang kết nối Vbee API ({display_name}, {effective_speed}x)…")
        check_cancel()

        tts = self._get_tts()
        lines = project.script.lines
        imported_assets: dict[str, VoiceAsset] = {}

        for index, line in enumerate(lines):
            check_cancel()
            pct = 15 + int((index / max(1, len(lines))) * 70)
            progress_callback(pct, f"Đang tạo voice Vbee câu {index + 1}/{len(lines)}…")

            line_text = (getattr(line, "vietnamese", None) or line.text).strip()
            if not line_text:
                continue

            key = audio_key(line.text, voice_settings)
            line_wav = target_dir / f"{key}-{index:04d}.wav"

            # Check if valid cached audio exists
            if line_wav.is_file() and line_wav.stat().st_size > 100:
                try:
                    dur_ms = await audio_duration(line_wav, ffprobe)
                except Exception:
                    dur_ms = 0
            else:
                dur_ms = 0

            if dur_ms <= 0:
                chunks = split_text(line_text, 300)
                chunk_wavs: list[Path] = []

                for c_idx, chunk in enumerate(chunks):
                    check_cancel()
                    temp_mp3 = temp_dir / f"chunk_{index}_{c_idx}.mp3"
                    temp_pcm = temp_dir / f"chunk_{index}_{c_idx}.wav"
                    try:
                        await tts.synthesize(chunk, voice_id, effective_speed, temp_mp3)
                        await convert_to_pcm_wav(temp_mp3, temp_pcm, ffmpeg)
                        chunk_wavs.append(temp_pcm)
                    finally:
                        if temp_mp3.is_file():
                            temp_mp3.unlink(missing_ok=True)

                if len(chunk_wavs) == 1:
                    chunk_wavs[0].replace(line_wav)
                elif len(chunk_wavs) > 1:
                    with wave.open(str(line_wav), "wb") as joined:
                        joined.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
                        for cw in chunk_wavs:
                            with wave.open(str(cw), "rb") as src:
                                while data := src.readframes(65536):
                                    joined.writeframesraw(data)
                            cw.unlink(missing_ok=True)

                dur_ms = await audio_duration(line_wav, ffprobe)

            asset = VoiceAsset(
                cache_key=key,
                text_hash=digest(normalized_text(line.text)),
                provider="vbee",
                voice_id=voice_id,
                speed=effective_speed,
                duration_ms=dur_ms,
                output_path=line_wav.resolve(),
                audio_sha256=file_hash(line_wav),
                generated_at=datetime.now(UTC).isoformat(),
            )
            imported_assets[line.id] = asset

        # Assemble master WAV with exact timeline silence padding
        progress_callback(88, "Đang tổng hợp timeline âm thanh master…")
        check_cancel()
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        master_wav = target_dir / f"master_vbee_{timestamp_str}.wav"

        with wave.open(str(master_wav), "wb") as master:
            master.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            current_sample = 0

            for line in lines:
                timeline_asset = imported_assets.get(line.id)
                if not timeline_asset or not timeline_asset.output_path.is_file():
                    continue

                target_sample = max(0, int(round((line.start_ms / 1000.0) * 24000)))
                if target_sample > current_sample:
                    silence_bytes = (target_sample - current_sample) * 2
                    chunk_size = 65536
                    while silence_bytes > 0:
                        batch = min(silence_bytes, chunk_size)
                        master.writeframesraw(b"\x00" * batch)
                        silence_bytes -= batch
                    current_sample = target_sample

                with wave.open(str(timeline_asset.output_path), "rb") as line_src:
                    while frame_data := line_src.readframes(65536):
                        master.writeframesraw(frame_data)
                        current_sample += len(frame_data) // 2

        # Populate project assets
        project.voice_assets.update(imported_assets)
        logger.info(
            "[VBEE][API] Hoàn tất tạo voice Vbee API: %d câu thoại, master=%s",
            len(imported_assets),
            master_wav.name,
        )
        progress_callback(95, "Đã hoàn tất tổng hợp âm thanh!")

        return {
            "status": "success",
            "lines_count": len(imported_assets),
            "master_wav": str(master_wav),
            "assets": imported_assets,
        }

    async def close(self) -> None:
        self._tts_provider = None
