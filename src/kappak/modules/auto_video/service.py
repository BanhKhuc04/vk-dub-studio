"""Service orchestrator for Auto Video Generator module."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kappak.core.db import db_session
from kappak.modules.auto_video.domain import AutoVideoProject, SceneSegment
from kappak.modules.auto_video.templates import AVAILABLE_TEMPLATES
from vkdub.media.process import find_tool
from vkdub.providers.edge_tts_provider import EdgeTTSProvider
from vkdub.utils.paths import workspace_root

logger = logging.getLogger("kappak.modules.auto_video.service")


def probe_duration_sec(file_path: Path | str) -> float:
    """Probe media file duration in seconds using ffprobe."""
    p = Path(file_path)
    if not p.is_file():
        return 0.0
    ffprobe = find_tool("ffprobe")
    if not ffprobe:
        return 0.0
    try:
        cmd = [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(p),
        ]
        flags = 0x08000000 if os.name == "nt" else 0
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=flags)
        if res.returncode == 0 and res.stdout.strip():
            return max(0.0, float(res.stdout.strip()))
    except Exception as exc:
        logger.debug("Không thể probe thời lượng %s: %s", p, exc)
    return 0.0


def current_timestamp_str() -> str:
    """Return SQLite compatible UTC timestamp string."""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class AutoVideoService:
    """Core business service for Auto Video generation."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or (workspace_root() / "auto_video")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tts_provider = EdgeTTSProvider()

    def get_templates(self) -> list[dict[str, Any]]:
        """Return list of available templates for UI."""
        return [t.to_dict() for t in AVAILABLE_TEMPLATES]

    def parse_script_to_scenes(self, script_text: str) -> list[SceneSegment]:
        """Break raw script text into scene segments by sentence/paragraph."""
        if not script_text or not script_text.strip():
            return []

        # Split on line breaks or strong sentence punctuation
        raw_lines = re.split(r"[\r\n]+", script_text.strip())
        scenes: list[SceneSegment] = []
        idx = 0

        for line in raw_lines:
            line = re.sub(r"^\s*[\d\.\-\*\#\>]+", "", line).strip()  # Clean bullets/numbering
            if not line:
                continue

            # If a line is too long (> 120 chars), break into shorter sentence chunks
            if len(line) > 120:
                sub_parts = re.split(r"([.!?;]+(?:\s+|$))", line)
                chunks = []
                buf = ""
                for part in sub_parts:
                    buf += part
                    if len(buf) >= 40 or re.search(r"[.!?;]$", buf.strip()):
                        if buf.strip():
                            chunks.append(buf.strip())
                        buf = ""
                if buf.strip():
                    chunks.append(buf.strip())
            else:
                chunks = [line]

            for chunk in chunks:
                if not chunk:
                    continue
                # Estimate speech time: ~3.5 syllables/sec (~14-16 chars/sec)
                est_dur = max(2.0, round(len(chunk) / 14.0, 1))
                scenes.append(
                    SceneSegment(
                        id=f"scene_{idx + 1}_{uuid.uuid4().hex[:4]}",
                        order_index=idx,
                        text=chunk,
                        duration_sec=est_dur,
                        voice_duration_sec=0.0,
                    )
                )
                idx += 1

        return scenes

    def list_available_assets(self) -> list[dict[str, Any]]:
        """List media assets from KAPPAK Data Studio / assets database."""
        try:
            with db_session() as conn:
                rows = conn.execute(
                    """SELECT id, name, local_path, duration_sec, resolution, file_size, category, status
                       FROM assets
                       ORDER BY created_at DESC LIMIT 50"""
                ).fetchall()
                results = []
                for r in rows:
                    p = Path(r["local_path"])
                    if p.is_file():
                        results.append(
                            {
                                "id": r["id"],
                                "name": r["name"],
                                "path": str(p),
                                "duration_sec": r["duration_sec"],
                                "resolution": r["resolution"],
                                "file_size": r["file_size"],
                                "category": r["category"],
                            }
                        )
                return results
        except Exception as exc:
            logger.warning("Không thể lấy danh sách assets: %s", exc)
            return []

    def create_project(
        self,
        name: str = "Short Video Mới",
        template_id: str = "blur_bg",
        voice_id: str = "vi-VN-HoaiMyNeural",
        voice_speed: float = 1.0,
        script_text: str = "",
        bgm_asset_id: str | None = None,
        bgm_volume: float = 0.15,
        project_id: str | None = None,
    ) -> AutoVideoProject:
        """Create and persist a new Auto Video project."""
        scenes = self.parse_script_to_scenes(script_text)
        proj = AutoVideoProject(
            id=str(uuid.uuid4()),
            name=name,
            project_id=project_id,
            template_id=template_id,
            voice_id=voice_id,
            voice_speed=voice_speed,
            bgm_asset_id=bgm_asset_id,
            bgm_volume=bgm_volume,
            script_text=script_text,
            scenes=scenes,
            status="DRAFT",
            progress_pct=0.0,
        )
        self.save_project(proj)
        return proj

    def save_project(self, project: AutoVideoProject) -> None:
        """Persist or update AutoVideoProject in SQLite."""
        scenes_json = json.dumps([s.to_dict() for s in project.scenes], ensure_ascii=False)
        with db_session() as conn:
            conn.execute(
                """INSERT INTO auto_video_projects (
                    id, name, project_id, template_id, voice_id, voice_speed,
                    bgm_asset_id, bgm_volume, script_text, scenes_json, status,
                    progress_pct, output_video_path, error_message, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    project_id = excluded.project_id,
                    template_id = excluded.template_id,
                    voice_id = excluded.voice_id,
                    voice_speed = excluded.voice_speed,
                    bgm_asset_id = excluded.bgm_asset_id,
                    bgm_volume = excluded.bgm_volume,
                    script_text = excluded.script_text,
                    scenes_json = excluded.scenes_json,
                    status = excluded.status,
                    progress_pct = excluded.progress_pct,
                    output_video_path = excluded.output_video_path,
                    error_message = excluded.error_message,
                    updated_at = excluded.updated_at
                """,
                (
                    project.id,
                    project.name,
                    project.project_id,
                    project.template_id,
                    project.voice_id,
                    project.voice_speed,
                    project.bgm_asset_id,
                    project.bgm_volume,
                    project.script_text,
                    scenes_json,
                    project.status,
                    project.progress_pct,
                    project.output_video_path,
                    project.error_message,
                    current_timestamp_str(),
                ),
            )

    def get_project(self, project_id: str) -> AutoVideoProject | None:
        """Fetch project by ID from SQLite."""
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM auto_video_projects WHERE id = ?", (project_id,)
            ).fetchone()
            if not row:
                return None
            data = dict(row)
            if hasattr(data.get("created_at"), "strftime"):
                data["created_at"] = data["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            if hasattr(data.get("updated_at"), "strftime"):
                data["updated_at"] = data["updated_at"].strftime("%Y-%m-%d %H:%M:%S")
            data["scenes"] = data.get("scenes_json", "[]")
            return AutoVideoProject.from_dict(data)

    def list_projects(self) -> list[dict[str, Any]]:
        """List all auto video projects ordered by recency."""
        with db_session() as conn:
            rows = conn.execute(
                """SELECT id, name, template_id, voice_id, status, progress_pct,
                          output_video_path, created_at, updated_at
                   FROM auto_video_projects
                   ORDER BY updated_at DESC LIMIT 30"""
            ).fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if hasattr(item.get("created_at"), "strftime"):
                    item["created_at"] = item["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                if hasattr(item.get("updated_at"), "strftime"):
                    item["updated_at"] = item["updated_at"].strftime("%Y-%m-%d %H:%M:%S")
                results.append(item)
            return results

    def delete_project(self, project_id: str) -> bool:
        """Delete an auto video project."""
        with db_session() as conn:
            cur = conn.execute("DELETE FROM auto_video_projects WHERE id = ?", (project_id,))
            return cur.rowcount > 0

    def generate_scene_voiceovers(
        self,
        project: AutoVideoProject,
        progress_cb: Callable[[float, str], None] | None = None,
    ) -> AutoVideoProject:
        """Synthesize TTS audio for each scene in project."""
        if not project.scenes:
            return project

        voice_dir = self.output_dir / project.id / "voices"
        voice_dir.mkdir(parents=True, exist_ok=True)

        total_scenes = len(project.scenes)
        for i, scene in enumerate(project.scenes):
            if not scene.text.strip():
                continue
            if progress_cb:
                pct = round((i / total_scenes) * 100, 1)
                progress_cb(pct, f"Tạo giọng đọc cảnh {i + 1}/{total_scenes}...")

            out_audio = voice_dir / f"scene_{i + 1}_{scene.id}.mp3"
            try:
                self.tts_provider.synthesize(
                    text=scene.text,
                    voice_id=project.voice_id,
                    speed=project.voice_speed,
                    output_path=out_audio,
                )
                dur = probe_duration_sec(out_audio)
                scene.voice_audio_path = str(out_audio)
                scene.voice_duration_sec = dur
                # Ensure visual duration at least matches voice + 0.3s padding
                scene.duration_sec = max(scene.duration_sec, round(dur + 0.3, 2))
            except Exception as exc:
                logger.error("Lỗi khi sinh giọng cảnh %s: %s", i + 1, exc)

        self.save_project(project)
        if progress_cb:
            progress_cb(100.0, "Đã hoàn thành tạo giọng đọc cho tất cả các cảnh!")
        return project
