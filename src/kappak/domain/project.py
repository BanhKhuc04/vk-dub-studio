"""Project domain entity and standardized 8-tier local directory hierarchy."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Standard 8-tier media production directory structure required by Brief (Section 6)
STANDARD_PROJECT_FOLDERS = [
    "00_Inbox",
    "01_Source/Video",
    "01_Source/Image",
    "01_Source/Audio",
    "01_Source/Document",
    "01_Source/Link",
    "02_Working/Video",
    "02_Working/Subtitle",
    "02_Working/Voice",
    "02_Working/Thumbnail",
    "02_Working/Design",
    "03_Review",
    "04_Final",
    "05_Published",
    "99_Archive",
]


@dataclass
class Project:
    """Project representation in KAPPAK Studio."""

    name: str
    root_path: Path
    description: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def create_folders(self) -> dict[str, Path]:
        """Create the canonical 8-tier folder hierarchy for this project."""
        self.root_path.mkdir(parents=True, exist_ok=True)
        created = {}
        for sub in STANDARD_PROJECT_FOLDERS:
            p = self.root_path / sub
            p.mkdir(parents=True, exist_ok=True)
            created[sub] = p
        return created

    @classmethod
    def create(cls, name: str, base_dir: Path, description: str = "") -> Project:
        """Factory method to initialize project model and scaffold physical disk structure."""
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in name).strip()
        project_root = base_dir / safe_name
        project = cls(name=name, root_path=project_root, description=description)
        project.create_folders()
        return project
