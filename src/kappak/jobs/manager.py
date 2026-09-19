"""Local Job Manager: SQLite persistence, thread pool, restart recovery, and job cancellation."""

from __future__ import annotations

import concurrent.futures
import json
import logging
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from kappak.core.db import db_session
from kappak.domain.job import Job, JobStatus

logger = logging.getLogger("kappak.jobs")


class LocalJobManager:
    """Orchestrates persistent local tasks (FFmpeg, ASR, yt-dlp, TTS)."""

    def __init__(self, db_path: Path | None = None, max_workers: int = 3) -> None:
        self.db_path = db_path
        self.max_workers = max_workers
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="kappak_job"
        )
        self._lock = threading.Lock()
        self._active_futures: dict[str, concurrent.futures.Future] = {}
        self._active_cancel_events: dict[str, threading.Event] = {}
        self._listeners: list[Callable[[Job], None]] = []

        # Automatic crash recovery on startup: mark orphan RUNNING jobs as ERROR
        self.recover_interrupted_jobs()

    def add_listener(self, callback: Callable[[Job], None]) -> None:
        """Register progress listener."""
        with self._lock:
            self._listeners.append(callback)

    def _notify(self, job: Job) -> None:
        for cb in self._listeners:
            try:
                cb(job)
            except Exception as e:
                logger.debug("Error in job listener: %s", e)

    def recover_interrupted_jobs(self) -> int:
        """Identify jobs that were RUNNING when app last terminated and mark them as ERROR."""
        with db_session(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE jobs SET status = ?, error = ?, finished_at = CURRENT_TIMESTAMP WHERE status = ?",
                (JobStatus.ERROR, "Tác vụ bị gián đoạn do khởi động lại ứng dụng.", JobStatus.RUNNING),
            )
            count = cursor.rowcount
            if count > 0:
                logger.info("Recovered %d interrupted jobs from previous session.", count)
            return count

    def submit(
        self,
        job_type: str,
        payload: dict[str, Any],
        handler: Callable[[Job, Callable[[float, str], None]], dict[str, Any]],
        target_id: str = "",
    ) -> Job:
        """Persist new job to SQLite and schedule execution on thread pool."""
        job = Job(job_type=job_type, payload=payload, target_id=target_id)
        with db_session(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, job_type, target_id, status, progress_pct, message, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.job_type,
                    job.target_id,
                    job.status,
                    job.progress_pct,
                    job.message,
                    json.dumps(job.payload, ensure_ascii=False),
                ),
            )

        self._notify(job)
        cancel_event = threading.Event()
        future = self._executor.submit(self._worker, job, handler, cancel_event)
        with self._lock:
            self._active_futures[job.id] = future
            self._active_cancel_events[job.id] = cancel_event
        return job

    def _worker(
        self,
        job: Job,
        handler: Callable[[Job, Callable[[float, str], None]], dict[str, Any]],
        cancel_event: threading.Event,
    ) -> None:
        def update_progress(pct: float, msg: str) -> None:
            if cancel_event.is_set():
                return
            job.progress_pct = round(pct, 1)
            job.message = msg
            with db_session(self.db_path) as conn:
                conn.execute(
                    "UPDATE jobs SET progress_pct = ?, message = ? WHERE id = ?",
                    (job.progress_pct, job.message, job.id),
                )
            self._notify(job)

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()
        with db_session(self.db_path) as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, started_at = CURRENT_TIMESTAMP WHERE id = ?",
                (JobStatus.RUNNING, job.id),
            )
        self._notify(job)

        try:
            result = handler(job, update_progress, cancel_event)
            if cancel_event.is_set():
                job.status = JobStatus.CANCELLED
                job.error = "Tác vụ bị hủy bởi người dùng."
                job.finished_at = datetime.now()
                with db_session(self.db_path) as conn:
                    conn.execute(
                        "UPDATE jobs SET status = ?, error = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (JobStatus.CANCELLED, job.error, job.id),
                    )
            else:
                job.status = JobStatus.SUCCESS
                job.progress_pct = 100.0
                job.result = result or {}
                job.finished_at = datetime.now()
                with db_session(self.db_path) as conn:
                    conn.execute(
                        """
                        UPDATE jobs
                        SET status = ?, progress_pct = 100.0, result_json = ?, finished_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (JobStatus.SUCCESS, json.dumps(job.result, ensure_ascii=False), job.id),
                    )
        except Exception as exc:
            job.status = JobStatus.ERROR
            job.error = str(exc)
            job.finished_at = datetime.now()
            logger.exception("Job %s failed: %s", job.id, exc)
            with db_session(self.db_path) as conn:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = ?, error = ?, finished_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (JobStatus.ERROR, job.error, job.id),
                )
        finally:
            with self._lock:
                self._active_futures.pop(job.id, None)
                self._active_cancel_events.pop(job.id, None)
            self._notify(job)

    def get_job(self, job_id: str) -> Job | None:
        """Fetch job state from SQLite."""
        with db_session(self.db_path) as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return None
            return Job(
                id=row["id"],
                job_type=row["job_type"],
                target_id=row["target_id"],
                status=row["status"],
                progress_pct=row["progress_pct"],
                message=row["message"],
                payload=json.loads(row["payload_json"] or "{}"),
                result=json.loads(row["result_json"] or "{}"),
                error=row["error"],
            )

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job by setting its cancellation event.

        Returns True if the job was found and cancellation was requested,
        False if the job was not found or already completed.
        """
        with self._lock:
            cancel_event = self._active_cancel_events.get(job_id)
            if cancel_event is not None:
                cancel_event.set()
                logger.info("Cancellation requested for job %s", job_id)
                return True
        return False

    def get_active_job_ids(self) -> list[str]:
        """Return list of currently running job IDs."""
        with self._lock:
            return list(self._active_futures.keys())

    def shutdown(self, wait: bool = True) -> None:
        """Gracefully shutdown worker pool."""
        self._executor.shutdown(wait=wait)
