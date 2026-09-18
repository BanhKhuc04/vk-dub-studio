"""Media asset entity with deduplication hashing and smart collection categorization."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def calculate_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """Calculate SHA-256 hash of a file for exact duplicate detection."""
    if not file_path.is_file():
        return ""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


@dataclass
class Asset:
    """Representation of a media asset in the KAPPAK Data Studio."""

    name: str
    local_path: Path
    project_id: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_url: str = ""
    platform: str = ""
    creator: str = ""
    duration_sec: float = 0.0
    resolution: str = ""
    file_size: int = 0
    sha256_hash: str = ""
    tags: list[str] = field(default_factory=list)
    category: str = "00_Inbox"
    status: str = "Unused"  # "Unused" | "Need Review" | "Approved" | "Published" | "Archived"
    is_favorite: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def refresh_file_metadata(self) -> None:
        """Read file size and calculate SHA-256 if file exists."""
        if self.local_path.is_file():
            self.file_size = self.local_path.stat().st_size
            if not self.sha256_hash:
                self.sha256_hash = calculate_sha256(self.local_path)
