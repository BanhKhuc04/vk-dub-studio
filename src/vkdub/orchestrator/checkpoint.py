"""Atomic checkpoint persistence for pipeline resumption."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from vkdub.orchestrator.pipeline_state import (
    ArtifactRegistry,
    PipelineState,
    SubstepInfo,
    SubstepStatus,
)

logger = logging.getLogger("vkdub.checkpoint")


def checkpoint_path_for_project(project_dir: Path) -> Path:
    return project_dir / ".pipeline_checkpoint.json"


def save_checkpoint(
    project_dir: Path,
    state: PipelineState,
    artifacts: ArtifactRegistry,
    substeps: list[SubstepInfo],
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Atomically persist pipeline checkpoint to disk."""
    project_dir.mkdir(parents=True, exist_ok=True)
    target_file = checkpoint_path_for_project(project_dir)
    temp_file = target_file.with_suffix(".tmp")

    data = {
        "state": state.value,
        "timestamp": time.time(),
        "artifacts": artifacts.to_dict(),
        "substeps": [s.to_dict() for s in substeps],
        "metadata": metadata or {},
    }

    try:
        temp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        temp_file.replace(target_file)
        logger.debug(
            "Checkpoint saved successfully: state=%s, file=%s",
            state.value,
            target_file,
        )
        return target_file
    except Exception as exc:
        logger.error("Failed to save checkpoint: %s", exc)
        if temp_file.exists():
            temp_file.unlink(missing_ok=True)
        return target_file


def load_checkpoint(
    project_dir: Path,
) -> tuple[PipelineState, ArtifactRegistry, list[SubstepInfo]] | None:
    """Load latest checkpoint if available."""
    target_file = checkpoint_path_for_project(project_dir)
    if not target_file.is_file():
        return None

    try:
        content = target_file.read_text(encoding="utf-8")
        data = json.loads(content)

        state = PipelineState(data.get("state", PipelineState.PROJECT_CREATED.value))
        artifacts = ArtifactRegistry.from_dict(data.get("artifacts", {}))

        substeps: list[SubstepInfo] = []
        for s_dict in data.get("substeps", []):
            art_path = Path(s_dict["artifact_path"]) if s_dict.get("artifact_path") else None
            substeps.append(
                SubstepInfo(
                    id=s_dict["id"],
                    name=s_dict["name"],
                    status=SubstepStatus(s_dict.get("status", SubstepStatus.PENDING.value)),
                    progress=int(s_dict.get("progress", 0)),
                    message=s_dict.get("message", ""),
                    duration_s=float(s_dict.get("duration_s", 0.0)),
                    error=s_dict.get("error"),
                    artifact_path=art_path,
                )
            )

        logger.info("Loaded checkpoint from %s: state=%s", target_file, state.value)
        return state, artifacts, substeps
    except Exception as exc:
        logger.warning("Could not read checkpoint from %s: %s", target_file, exc)
        return None


def clear_checkpoint(project_dir: Path) -> None:
    """Remove checkpoint file."""
    target_file = checkpoint_path_for_project(project_dir)
    if target_file.is_file():
        try:
            target_file.unlink()
        except Exception as exc:
            logger.warning("Could not delete checkpoint %s: %s", target_file, exc)
