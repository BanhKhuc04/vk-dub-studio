"""VK Dub Studio — YouTube Clip Export Service.

Orchestrates background download, hardware-accelerated trimming, multi-clip
merging, ToolVideo timeline import, process tree cancellation, and realtime
telemetry streaming to the Browser Bridge / Extension.
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from vkdub.bridge.local_agent import LocalAgent
from vkdub.bridge.protocol import (
    ClipExportAccepted,
    ClipExportCancel,
    ClipExportError,
    ClipExportProgress,
    ClipExportRequest,
    ClipExportResult,
    ClipItem,
    CutMode,
    ExportMode,
    ExportStage,
)
from vkdub.domain.project import Project
from vkdub.media.clip_engine import (
    ClipEngine,
    build_clip_filename,
    build_merged_filename,
    kill_process_tree,
    sanitize_filename,
)
from vkdub.media.hardware import HardwareEncoderDetector
from vkdub.media.ytdlp import YtDlpDownloader

logger = logging.getLogger("vkdub.services.clip_export")


class JobStatus:
    """Internal lifecycle states for ClipJob."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class JobCancelledError(RuntimeError):
    """Raised when an active export job is cancelled by user."""

    pass


def resolve_safe_output_dir(output_dir_str: str | None, default_dir: Path) -> Path:
    """Validate and sanitize output directory to prevent path traversal attacks.

    Guarantees:
    - Resolves relative paths and expansions.
    - Prevents overwriting drive roots (e.g. C:\\ or D:\\ or bare "D:") without subfolder.
    - Prevents writing into Windows system directories (e.g. C:\\Windows, System32).
    - Falls back to default_dir if invalid, empty, or dangerous.
    """
    if not output_dir_str or not output_dir_str.strip():
        return default_dir

    raw = output_dir_str.strip()
    # Check for bare drive specifiers like "C:", "C:\", "c:/", "D:"
    if len(raw) <= 3 and len(raw) >= 2 and raw[1] == ":":
        return default_dir / "clips"

    try:
        candidate = Path(raw).expanduser()
        resolved = candidate.resolve()
    except Exception:
        return default_dir

    # If resolved path is root of a drive or filesystem
    if resolved.parent == resolved:
        return default_dir / "clips"

    # Normalise for Windows path traversal checks
    resolved_str = str(resolved).replace("/", "\\").rstrip("\\")
    lower_str = resolved_str.lower()

    # Reject drive roots without subfolders (e.g. "c:" or "c:\")
    if len(lower_str) <= 3 and lower_str.endswith(":"):
        return default_dir / "clips"

    # Reject system directories
    windir = os.environ.get("WINDIR", "C:\\Windows").replace("/", "\\").rstrip("\\").lower()
    sysdrive = os.environ.get("SystemDrive", "C:").lower()
    if lower_str == windir or lower_str.startswith(windir + "\\"):
        return default_dir / "clips"
    if lower_str == f"{sysdrive}\\windows" or lower_str.startswith(f"{sysdrive}\\windows\\"):
        return default_dir / "clips"
    prog_files = os.environ.get("ProgramFiles", "C:\\Program Files").lower()
    if lower_str == prog_files or lower_str.startswith(prog_files + "\\"):
        return default_dir / "clips"

    return resolved


@dataclass
class ClipJob:
    """Represents a background clip export task."""

    request: ClipExportRequest
    status: str = JobStatus.QUEUED
    stage: str = ExportStage.PROBING
    percent: float = 0.0
    created_at: float = field(default_factory=time.monotonic)
    started_at: float | None = None
    completed_at: float | None = None
    active_process: subprocess.Popen | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    result: ClipExportResult | None = None
    error: str | None = None
    scratch_dir: Path | None = None
    trimmed_files: list[Path] = field(default_factory=list)
    merged_file: Path | None = None
    selected_clips: list[ClipItem] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    future: concurrent.futures.Future | None = None

    @property
    def request_id(self) -> str:
        return self.request.request_id

    @property
    def job_id(self) -> str:
        return self.request.job_id

    @property
    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set() or self.status == JobStatus.CANCELLED

    def set_active_process(self, proc: subprocess.Popen) -> None:
        """Register active child process for tree termination."""
        with self.lock:
            self.active_process = proc
        # If cancellation was requested before or during process start, terminate immediately
        if self.cancel_event.is_set() and proc.pid:
            try:
                kill_process_tree(proc.pid)
            except Exception:
                pass

    def clear_active_process(self) -> None:
        """Unregister active process once completed."""
        with self.lock:
            self.active_process = None

    def cancel(self) -> bool:
        """Signal job cancellation and immediately kill child process tree."""
        with self.lock:
            if self.status in (JobStatus.SUCCESS, JobStatus.ERROR, JobStatus.CANCELLED):
                return False
            self.status = JobStatus.CANCELLED
            self.stage = ExportStage.CANCELLED
            self.cancel_event.set()
            proc = self.active_process

        if proc and proc.pid:
            try:
                kill_process_tree(proc.pid)
            except Exception:
                pass
            try:
                proc.terminate()
            except Exception:
                pass
        return True


class ClipExportService:
    """Manages YouTube clip export jobs, background worker queue,

    realtime telemetry streaming, and ToolVideo project import.
    """

    def __init__(
        self,
        local_agent: LocalAgent | None = None,
        downloader: YtDlpDownloader | None = None,
        clip_engine: ClipEngine | None = None,
        hw_detector: HardwareEncoderDetector | None = None,
        project: Project | None = None,
        workspace_dir: Path | None = None,
        output_dir: Path | None = None,
        scratch_dir: Path | None = None,
        cache_dir: Path | None = None,
        max_workers: int = 2,
        import_handler: Callable[[Path], None] | None = None,
    ) -> None:
        # Determine base workspace directory
        if workspace_dir is not None:
            base_dir = workspace_dir
        else:
            try:
                from vkdub.utils.paths import workspace_root

                base_dir = workspace_root()
            except Exception:
                base_dir = Path.cwd()

        self.workspace_dir = Path(base_dir).resolve()
        self.output_dir = (
            Path(output_dir).resolve() if output_dir else (self.workspace_dir / "exports" / "clips")
        )
        self.scratch_dir = (
            Path(scratch_dir).resolve()
            if scratch_dir
            else (self.workspace_dir / "scratch" / "clips")
        )
        self.cache_dir = (
            Path(cache_dir).resolve() if cache_dir else (self.workspace_dir / "cache" / "youtube")
        )

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.scratch_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.downloader = downloader or YtDlpDownloader(cache_root=self.workspace_dir)
        self.clip_engine = clip_engine or ClipEngine()
        self.hw_detector = hw_detector or HardwareEncoderDetector()
        self.project = project
        self.import_handler = import_handler

        self.active_jobs: dict[str, ClipJob] = {}
        self.job_id_to_request_id: dict[str, str] = {}
        self._jobs_lock = threading.RLock()

        self.max_workers = max(1, max_workers)
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="ClipExportWorker",
        )
        self._progress_listeners: list[Callable[[ClipExportProgress], None]] = []

        self.local_agent: LocalAgent | None = None
        if local_agent is not None:
            self.attach_local_agent(local_agent)

    def attach_local_agent(self, local_agent: LocalAgent) -> None:
        """Hook into LocalAgent protocol routing for export and cancel actions."""
        self.local_agent = local_agent
        self.local_agent.set_clip_export_handler(self.handle_clip_export_request)
        self.local_agent.set_clip_cancel_handler(self.handle_clip_cancel_request)
        self.local_agent.set_clip_import_handler(self.handle_clip_import_request)

    def set_import_handler(self, handler: Callable[[Path], None]) -> None:
        """Register a callback for IMPORT mode deliveries."""
        self.import_handler = handler

    def add_progress_listener(self, listener: Callable[[ClipExportProgress], None]) -> None:
        """Register external listener for realtime progress broadcasts."""
        with self._jobs_lock:
            if listener not in self._progress_listeners:
                self._progress_listeners.append(listener)

    def remove_progress_listener(self, listener: Callable[[ClipExportProgress], None]) -> None:
        """Unregister external progress listener."""
        with self._jobs_lock:
            if listener in self._progress_listeners:
                self._progress_listeners.remove(listener)

    def get_job_scratch_dir(self, job_id: str) -> Path:
        """Return unique scratch directory path for a specific job."""
        safe_job_id = sanitize_filename(job_id, max_length=40)
        return self.scratch_dir / safe_job_id

    def cleanup_job_scratch(self, job_id: str) -> None:
        """Safely delete temporary scratch directory and files for a job."""
        scratch = self.get_job_scratch_dir(job_id)
        if scratch.is_dir():
            try:
                shutil.rmtree(scratch, ignore_errors=True)
            except OSError as exc:
                logger.warning("Failed to delete scratch dir %s: %s", scratch, exc)

    def get_job(self, request_id_or_job_id: str) -> ClipJob | None:
        """Lookup job by request_id or job_id."""
        with self._jobs_lock:
            if request_id_or_job_id in self.active_jobs:
                return self.active_jobs[request_id_or_job_id]
            req_id = self.job_id_to_request_id.get(request_id_or_job_id)
            if req_id and req_id in self.active_jobs:
                return self.active_jobs[req_id]
            for job in self.active_jobs.values():
                if job.request.job_id == request_id_or_job_id:
                    return job
        return None

    def list_jobs(self) -> list[ClipJob]:
        """Return list of all tracked jobs."""
        with self._jobs_lock:
            return list(self.active_jobs.values())

    def handle_clip_export_request(self, payload: dict[str, Any] | ClipExportRequest) -> ClipJob:
        """Handler for CLIP_EXPORT_REQUEST actions from Native Bridge."""
        if isinstance(payload, ClipExportRequest):
            req = payload
        else:
            req = ClipExportRequest.from_payload(payload)
        return self.submit_job(req)

    def handle_clip_cancel_request(self, payload: dict[str, Any] | ClipExportCancel) -> bool:
        """Handler for CLIP_EXPORT_CANCEL actions from Native Bridge."""
        if isinstance(payload, ClipExportCancel):
            req_id = payload.request_id
            job_id = payload.job_id
        else:
            req_id = str(payload.get("request_id") or payload.get("requestId") or "")
            job_id = str(payload.get("job_id") or payload.get("jobId") or "")
        return self.cancel_job(request_id=req_id, job_id=job_id)

    def handle_clip_import_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Import a previously completed result selected in the extension.

        If the job is still known, the requested path must be one of its actual
        outputs.  After an application restart the extension may restore its last
        successful result, so an existing local media file is also accepted.
        """
        request_id = str(payload.get("request_id") or payload.get("requestId") or "")
        job_id = str(payload.get("job_id") or payload.get("jobId") or request_id)
        raw_path = str(payload.get("file_path") or payload.get("filePath") or "").strip()
        if not raw_path:
            raise ValueError("Thiếu đường dẫn clip cần đưa vào ToolVideo.")

        target = Path(raw_path).expanduser().resolve()
        if target.suffix.lower() not in {".mp4", ".mkv", ".webm", ".mov"}:
            raise ValueError("Định dạng clip không được ToolVideo hỗ trợ.")
        if not target.is_file():
            raise FileNotFoundError(f"Không tìm thấy clip đã xuất: {target}")

        job = self.get_job(request_id or job_id)
        if job is not None and job.result is not None:
            known_paths = {
                Path(item).expanduser().resolve() for item in job.result.files if item
            }
            if job.result.merged_file:
                known_paths.add(Path(job.result.merged_file).expanduser().resolve())
            if target not in known_paths:
                raise ValueError("Tệp được chọn không thuộc kết quả của tác vụ xuất clip.")
            request = job.request
        else:
            request = ClipExportRequest(
                request_id=request_id,
                job_id=job_id,
                video_id=str(payload.get("video_id") or payload.get("videoId") or ""),
            )

        self._import_into_toolvideo(target, request)
        return {
            "success": True,
            "request_id": request_id,
            "job_id": job_id,
            "file_path": str(target),
        }

    def submit_job(self, request: ClipExportRequest | dict[str, Any]) -> ClipJob:
        """Submit an export job to the asynchronous background worker queue.

        Implements idempotency checking: duplicate requests return the existing job.
        """
        if isinstance(request, dict):
            req = ClipExportRequest.from_payload(request)
        else:
            req = request

        # Ensure unique request_id and job_id
        if not req.request_id:
            req.request_id = f"clip_req_{int(time.time())}_{uuid4().hex[:6]}"
        if not req.job_id:
            req.job_id = req.request_id

        req_id = req.request_id
        job_id = req.job_id

        with self._jobs_lock:
            # Idempotency check: if job already exists
            if req_id in self.active_jobs:
                existing = self.active_jobs[req_id]
                logger.info(
                    "Duplicate export request received: request_id=%s (status=%s)",
                    req_id,
                    existing.status,
                )
                if existing.status in (JobStatus.QUEUED, JobStatus.RUNNING):
                    if self.local_agent:
                        self.local_agent.send_clip_accepted(
                            ClipExportAccepted(
                                request_id=req_id,
                                job_id=job_id,
                                status=existing.status,
                                total_clips=len(existing.selected_clips or req.clips),
                                message="Yêu cầu xuất clip đã có trong hàng đợi/đang xử lý.",
                            )
                        )
                    return existing
                if existing.status == JobStatus.SUCCESS and existing.result:
                    if self.local_agent:
                        self.local_agent.send_clip_result(existing.result)
                    return existing

            # Validate selected clips
            selected_clips = [
                c
                for c in req.clips
                if c.selected and c.is_valid(req.duration if req.duration > 0 else None)
            ]

            job = ClipJob(request=req, selected_clips=selected_clips)
            self.active_jobs[req_id] = job
            self.job_id_to_request_id[job_id] = req_id

        if not selected_clips:
            err_msg = "Không có đoạn clip hợp lệ nào được chọn để xuất."
            job.status = JobStatus.ERROR
            job.stage = ExportStage.ERROR
            job.error = err_msg
            if self.local_agent:
                self.local_agent.send_clip_error(
                    ClipExportError(
                        request_id=req_id,
                        job_id=job_id,
                        status="ERROR",
                        error=err_msg,
                        stage=ExportStage.ERROR,
                        details=err_msg,
                        success=False,
                    )
                )
            return job

        # Acknowledge acceptance
        if self.local_agent:
            self.local_agent.send_clip_accepted(
                ClipExportAccepted(
                    request_id=req_id,
                    job_id=job_id,
                    status="QUEUED",
                    total_clips=len(selected_clips),
                    message="Yêu cầu xuất clip đã được tiếp nhận.",
                )
            )

        # Dispatch to thread worker pool
        future = self._executor.submit(self._run_job, job)
        job.future = future
        return job

    def execute_job(
        self,
        request: ClipExportRequest | dict[str, Any],
        progress_callback: Callable[[ClipExportProgress], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> ClipExportResult:
        """Execute an export job synchronously on the current thread.

        Primarily used for testing, direct invocation, or CLI tooling.
        """
        if isinstance(request, dict):
            req = ClipExportRequest.from_payload(request)
        else:
            req = request

        if not req.request_id:
            req.request_id = f"clip_sync_{int(time.time())}_{uuid4().hex[:6]}"
        if not req.job_id:
            req.job_id = req.request_id

        req_id = req.request_id
        job_id = req.job_id

        with self._jobs_lock:
            selected_clips = [
                c
                for c in req.clips
                if c.selected and c.is_valid(req.duration if req.duration > 0 else None)
            ]
            job = ClipJob(request=req, selected_clips=selected_clips)
            self.active_jobs[req_id] = job
            self.job_id_to_request_id[job_id] = req_id

        if cancel_check is not None:
            # Poll cancel_check or link to job cancel_event
            def check_and_cancel():
                if cancel_check():
                    job.cancel()

            # We hook cancellation check into the run loop
        return self._run_job(
            job, extra_progress_callback=progress_callback, extra_cancel_check=cancel_check
        )

    def cancel_job(self, request_id: str | None = None, job_id: str | None = None) -> bool:
        """Cancel an active or queued job by request_id or job_id."""
        job = None
        with self._jobs_lock:
            if request_id and request_id in self.active_jobs:
                job = self.active_jobs[request_id]
            elif job_id and job_id in self.job_id_to_request_id:
                req_id = self.job_id_to_request_id[job_id]
                job = self.active_jobs.get(req_id)
            elif job_id:
                for j in self.active_jobs.values():
                    if j.request.job_id == job_id:
                        job = j
                        break

        if not job:
            logger.warning(
                "Cannot cancel unknown job: request_id=%s, job_id=%s", request_id, job_id
            )
            return False

        cancelled = job.cancel()
        if cancelled:
            logger.info("Job cancelled: request_id=%s, job_id=%s", job.request_id, job.job_id)
        return cancelled

    def _notify_progress(self, job: ClipJob, progress: ClipExportProgress) -> None:
        """Broadcast progress telemetry to LocalAgent and registered listeners."""
        if self.local_agent:
            try:
                self.local_agent.send_clip_progress(progress)
            except Exception as exc:
                logger.debug("Failed to send clip progress over LocalAgent: %s", exc)

        listeners = []
        with self._jobs_lock:
            listeners = list(self._progress_listeners)

        for listener in listeners:
            try:
                listener(progress)
            except Exception as exc:
                logger.warning("Error in progress listener: %s", exc)

    def _run_job(
        self,
        job: ClipJob,
        extra_progress_callback: Callable[[ClipExportProgress], None] | None = None,
        extra_cancel_check: Callable[[], bool] | None = None,
    ) -> ClipExportResult:
        """Core execution pipeline running in worker thread."""
        start_time = time.monotonic()
        req = job.request
        req_id = req.request_id
        job_id = req.job_id

        scratch_dir = self.get_job_scratch_dir(job_id)
        job.scratch_dir = scratch_dir
        scratch_dir.mkdir(parents=True, exist_ok=True)

        with job.lock:
            job.status = JobStatus.RUNNING
            job.started_at = start_time

        def is_cancelled() -> bool:
            if job.is_cancelled:
                return True
            if extra_cancel_check and extra_cancel_check():
                job.cancel()
                return True
            return False

        def check_cancelled():
            if is_cancelled():
                raise JobCancelledError("Tiến trình xuất clip đã bị hủy bởi người dùng.")

        def emit_progress(
            stage: str,
            percent: float,
            message: str,
            speed: str = "",
            downloaded_bytes: int = 0,
            total_bytes: int = 0,
            cur_clip: int = 0,
        ):
            with job.lock:
                job.stage = stage
                job.percent = percent

            p = ClipExportProgress(
                request_id=req_id,
                job_id=job_id,
                stage=stage,
                percent=round(percent, 1),
                speed=speed,
                downloaded_bytes=downloaded_bytes,
                total_bytes=total_bytes,
                current_clip=cur_clip,
                total_clips=len(job.selected_clips),
                message=message,
            )
            self._notify_progress(job, p)
            if extra_progress_callback:
                try:
                    extra_progress_callback(p)
                except Exception:
                    pass

        try:
            check_cancelled()

            # 1. Output directory resolution & sanitization
            target_out_dir = resolve_safe_output_dir(req.output_dir, self.output_dir)
            target_out_dir.mkdir(parents=True, exist_ok=True)

            if not job.selected_clips:
                job.selected_clips = [
                    c
                    for c in req.clips
                    if c.selected and c.is_valid(req.duration if req.duration > 0 else None)
                ]
            if not job.selected_clips:
                raise ValueError("Không có đoạn clip hợp lệ nào được chọn để xuất.")

            # 2. Stage: PROBING & full-source cache inspection
            emit_progress(ExportStage.PROBING, 5.0, "Kiểm tra cache video nguồn...")
            source_file = self.downloader.get_cached_source(req.video_id, req.quality)
            section_sources: dict[str, Path] = {}

            # 3. Stage: DOWNLOADING (if a full source is not already cached)
            # Download only each selected time range. This is the critical fast
            # path for long/high-resolution videos: a one-minute selection from
            # a 90-minute source transfers roughly one minute, not all 90.
            if not source_file:
                check_cancelled()
                emit_progress(
                    ExportStage.DOWNLOADING,
                    10.0,
                    "Đang tải trực tiếp các đoạn đã chọn bằng yt-dlp...",
                )

                section_count = len(job.selected_clips)
                for section_index, clip in enumerate(job.selected_clips, start=1):
                    check_cancelled()

                    def on_dl_progress(
                        p: dict[str, Any],
                        current_index: int = section_index,
                    ):
                        check_cancelled()
                        stage = p.get("stage", ExportStage.DOWNLOADING)
                        raw_pct = max(0.0, min(100.0, float(p.get("percent", 0.0))))
                        speed = str(p.get("speed", ""))
                        completed_fraction = ((current_index - 1) + raw_pct / 100.0) / section_count
                        scaled_pct = 10.0 + completed_fraction * 38.0
                        if stage in (ExportStage.REMUXING, "REMUXING"):
                            emit_progress(
                                ExportStage.REMUXING,
                                scaled_pct,
                                f"Đang ghép luồng đoạn {current_index}/{section_count}...",
                                speed=speed,
                                cur_clip=current_index,
                            )
                        else:
                            emit_progress(
                                ExportStage.DOWNLOADING,
                                scaled_pct,
                                f"Đang tải đoạn {current_index}/{section_count}: {raw_pct:.1f}%",
                                speed=speed,
                                cur_clip=current_index,
                            )

                    section_file = self.downloader.download(
                        video_url=req.video_url,
                        video_id=req.video_id,
                        quality=req.quality,
                        use_cookies=req.use_cookies,
                        cookie_browser=req.browser if req.use_cookies else None,
                        progress_callback=on_dl_progress,
                        cancel_check=is_cancelled,
                        on_process_start=job.set_active_process,
                        section_start=clip.start,
                        section_end=clip.end,
                        force_keyframes_at_cuts=req.cut_mode == CutMode.FRAME_ACCURATE,
                        prefer_segmented=req.quality != "source_best",
                    )
                    job.clear_active_process()
                    section_sources[clip.id] = section_file

                emit_progress(
                    ExportStage.DOWNLOADING,
                    48.0,
                    "Đã tải xong các đoạn đã chọn; không cần tải toàn bộ video.",
                )
            else:
                emit_progress(
                    ExportStage.DOWNLOADING, 48.0, "Sử dụng video nguồn đã lưu trong cache."
                )

            check_cancelled()

            # 4. Stage: TRIMMING
            trimmed_files: list[Path] = []
            total_clips = len(job.selected_clips)

            for idx, clip in enumerate(job.selected_clips, start=1):
                check_cancelled()
                trim_pct = 50.0 + ((idx - 1) / total_clips) * 30.0
                clip_label = clip.name or f"Clip {idx}"
                emit_progress(
                    ExportStage.TRIMMING,
                    trim_pct,
                    f"Đang cắt clip {idx}/{total_clips}: {clip_label}",
                    cur_clip=idx,
                )

                clip_filename = build_clip_filename(
                    video_title=req.video_title,
                    clip_index=idx,
                    start_sec=clip.start,
                    end_sec=clip.end,
                    container=req.container,
                )
                clip_out_path = target_out_dir / clip_filename

                if source_file:
                    self.clip_engine.trim_clip(
                        source_path=source_file,
                        output_path=clip_out_path,
                        start_sec=clip.start,
                        end_sec=clip.end,
                        cut_mode=req.cut_mode,
                        on_process_start=job.set_active_process,
                        cancel_check=is_cancelled,
                    )
                    job.clear_active_process()
                else:
                    section_file = section_sources.get(clip.id)
                    if not section_file or not section_file.is_file():
                        raise FileNotFoundError(f"Không tìm thấy đoạn tải tạm cho {clip_label}.")

                    # yt-dlp already produced the exact selected MP4. Copying it
                    # to the requested output name avoids a second encode pass.
                    if req.container.lower().lstrip(".") == "mp4":
                        shutil.copy2(section_file, clip_out_path)
                    else:
                        self.clip_engine.trim_clip(
                            source_path=section_file,
                            output_path=clip_out_path,
                            start_sec=0.0,
                            end_sec=clip.duration,
                            cut_mode=req.cut_mode,
                            on_process_start=job.set_active_process,
                            cancel_check=is_cancelled,
                        )
                        job.clear_active_process()
                trimmed_files.append(clip_out_path)

            job.trimmed_files = trimmed_files
            check_cancelled()

            # 5. Stage: MERGING (if MERGED or IMPORT with multiple clips)
            merged_file_path: Path | None = None
            should_merge = (req.export_mode == ExportMode.MERGED and len(trimmed_files) > 0) or (
                req.export_mode == ExportMode.IMPORT and len(trimmed_files) > 1
            )

            if should_merge:
                emit_progress(
                    ExportStage.MERGING, 85.0, "Đang ghép các đoạn clip vào một video duy nhất..."
                )
                merged_filename = build_merged_filename(
                    video_title=req.video_title, container=req.container
                )
                merged_file_path = target_out_dir / merged_filename
                manifest_path = scratch_dir / f"{merged_file_path.stem}_concat_manifest.txt"

                self.clip_engine.merge_clips(
                    clip_paths=trimmed_files,
                    output_path=merged_file_path,
                    manifest_path=manifest_path,
                    on_process_start=job.set_active_process,
                    cancel_check=is_cancelled,
                )
                job.clear_active_process()
                job.merged_file = merged_file_path

            check_cancelled()

            # 6. Stage: IMPORT into ToolVideo (if IMPORT mode)
            if req.export_mode == ExportMode.IMPORT:
                emit_progress(ExportStage.PIPELINE_FEED, 95.0, "Nạp clip vào timeline ToolVideo...")
                chosen_import = merged_file_path if merged_file_path else trimmed_files[0]
                self._import_into_toolvideo(chosen_import, req)

            # 7. Stage: COMPLETE
            emit_progress(
                ExportStage.COMPLETE,
                100.0,
                "Xuất video clip hoàn tất!",
                cur_clip=total_clips,
            )

            elapsed = max(0.01, round(time.monotonic() - start_time, 2))
            result = ClipExportResult(
                request_id=req_id,
                job_id=job_id,
                status="SUCCESS",
                files=[str(f) for f in trimmed_files],
                merged_file=str(merged_file_path) if merged_file_path else None,
                output_dir=str(target_out_dir),
                elapsed_seconds=elapsed,
                success=True,
            )

            with job.lock:
                job.status = JobStatus.SUCCESS
                job.result = result
                job.completed_at = time.monotonic()

            self.cleanup_job_scratch(job_id)

            if self.local_agent:
                self.local_agent.send_clip_result(result)

            return result

        except JobCancelledError as exc:
            with job.lock:
                job.status = JobStatus.CANCELLED
                job.stage = ExportStage.CANCELLED
                job.error = str(exc)
                job.completed_at = time.monotonic()

            if job.active_process and job.active_process.pid:
                try:
                    kill_process_tree(job.active_process.pid)
                except Exception:
                    pass
                job.clear_active_process()

            self.cleanup_job_scratch(job_id)

            emit_progress(
                ExportStage.CANCELLED, job.percent, "Tiến trình xuất clip đã bị hủy bởi người dùng."
            )
            err_payload = ClipExportError(
                request_id=req_id,
                job_id=job_id,
                status="CANCELLED",
                error="Tiến trình xuất clip đã bị hủy bởi người dùng.",
                stage=ExportStage.CANCELLED,
                details=str(exc),
                success=False,
            )
            if self.local_agent:
                self.local_agent.send_clip_error(err_payload)
            raise

        except Exception as exc:
            with job.lock:
                job.status = JobStatus.ERROR
                job.stage = ExportStage.ERROR
                job.error = str(exc)
                job.completed_at = time.monotonic()

            if job.active_process and job.active_process.pid:
                try:
                    kill_process_tree(job.active_process.pid)
                except Exception:
                    pass
                job.clear_active_process()

            self.cleanup_job_scratch(job_id)

            emit_progress(ExportStage.ERROR, job.percent, f"Lỗi xuất clip: {exc}")
            err_payload = ClipExportError(
                request_id=req_id,
                job_id=job_id,
                status="ERROR",
                error=str(exc),
                stage=job.stage,
                details=str(exc),
                success=False,
            )
            if self.local_agent:
                self.local_agent.send_clip_error(err_payload)
            raise

    def _import_into_toolvideo(self, chosen_file: Path, req: ClipExportRequest) -> None:
        """Import the exported media file into ToolVideo Project state."""
        # 1. Custom import handler
        if self.import_handler is not None:
            try:
                self.import_handler(chosen_file)
            except Exception as exc:
                logger.warning("Error in custom import_handler: %s", exc)

        # 2. Update provided Project instance if present
        if self.project is not None:
            self.project.video_path = chosen_file

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown background worker thread pool and cancel active jobs."""
        with self._jobs_lock:
            for job in self.active_jobs.values():
                if job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
                    job.cancel()
        self._executor.shutdown(wait=wait)
        logger.info("ClipExportService executor shut down.")
