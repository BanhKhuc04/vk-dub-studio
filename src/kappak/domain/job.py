"""Job entity and persistent lifecycle statuses."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class JobStatus:
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


@dataclass
class Job:
    """Persistent background task executed by LocalJobManager."""

    job_type: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    target_id: str = ""
    status: str = JobStatus.QUEUED
    progress_pct: float = 0.0
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
