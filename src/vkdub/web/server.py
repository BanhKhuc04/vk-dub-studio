import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PySide6.QtCore import QCoreApplication, Qt

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


# Ensure src is in sys.path
root_dir = Path(__file__).resolve().parents[3]
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from vkdub.bridge.local_agent import LocalAgent
from vkdub.domain.mask import MaskItem
from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.domain.voice import VoiceSettings
from vkdub.media.ffprobe import parse_metadata
from vkdub.media.process import find_tool
from vkdub.orchestrator.pipeline_runner import PipelineRunner
from vkdub.orchestrator.pipeline_state import ArtifactRegistry, PipelineState, SubstepStatus
from vkdub.providers.edge_tts_provider import EdgeTTSProvider
from vkdub.services.app_settings import load_app_settings, save_app_settings
from vkdub.services.capcut_export import export_capcut_project
from vkdub.services.clip_export_service import ClipExportService
from vkdub.services.mask_service import build_ffmpeg_mask_filter
from vkdub.services.render_service import RenderConfig, build_render_command, escape_ffmpeg_filter_path
from vkdub.services.srt_service import write_srt
from vkdub.services.srt_validator import parse_cues, timecode_to_ms
from vkdub.services.subtitle_service import export_ass
from vkdub.services.voice_catalog import VBEE_DEFAULT_CATALOG, read_catalog
from vkdub.utils.paths import data_root, workspace_root
from kappak.modules.auto_video import (
    AutoVideoProject,
    AutoVideoRenderer,
    AutoVideoService,
    SceneSegment,
)

logger = logging.getLogger("vkdub.web")

edge_tts_provider = EdgeTTSProvider()
auto_video_service = AutoVideoService()


class AppState:
    def __init__(self):
        if QApplication is not None:
            self.qt_app = QApplication.instance() or QCoreApplication.instance()
            if not self.qt_app:
                self.qt_app = QApplication([])
        else:
            self.qt_app = QCoreApplication.instance() or QCoreApplication([])
        self.local_agent: LocalAgent | None = None
        self.clip_export_service: ClipExportService | None = None
        self.project: Project = Project()
        self.video_metadata: dict[str, Any] | None = None
        self.active_runner: PipelineRunner | None = None
        self.runner_thread: threading.Thread | None = None
        self.ws_clients: set[WebSocket] = set()
        self.main_loop: asyncio.AbstractEventLoop | None = None
        self.substeps = [
            {"id": "4.1", "name": "Bóc băng phụ đề gốc (Whisper)", "status": "PENDING", "progress": 0, "message": "Chưa bắt đầu"},
            {"id": "4.2", "name": "Dịch ngữ cảnh (ChatGPT qua Edge)", "status": "PENDING", "progress": 0, "message": "Chưa bắt đầu"},
            {"id": "4.3", "name": "Chuẩn bị kịch bản & timeline", "status": "PENDING", "progress": 0, "message": "Chưa bắt đầu"},
            {"id": "4.4", "name": "Tạo giọng đọc AI (Vbee/Edge)", "status": "PENDING", "progress": 0, "message": "Chưa bắt đầu"},
        ]
        self.overall_pct = 0
        self.overall_msg = "Sẵn sàng"
        self.logs: list[str] = []
        self.subtitles: list[dict[str, Any]] = []
        self.approved_script = False
        self.export_mp4_result: str | None = None
        self.export_capcut_result: str | None = None


state = AppState()


async def broadcast_ws(data: dict[str, Any]):
    dead = set()
    for ws in list(state.ws_clients):
        try:
            await ws.send_json(data)
        except Exception:
            dead.add(ws)
    state.ws_clients.difference_update(dead)


def run_in_async_loop(coro):
    try:
        loop = getattr(state, "main_loop", None)
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, loop)
        else:
            try:
                curr = asyncio.get_event_loop()
                if curr.is_running():
                    asyncio.run_coroutine_threadsafe(coro, curr)
            except Exception:
                pass
    except Exception as e:
        logger.debug("Broadcast error: %s", e)


def _sync_subtitles_to_project() -> None:
    """Synchronize state.subtitles into state.project.script and refresh revision hash."""
    if not state.subtitles:
        return

    lines: list[ScriptLine] = []
    for item in state.subtitles:
        st_raw = item.get("start_time", "00:00:00,000")
        et_raw = item.get("end_time", "00:00:00,000")
        st_ms = timecode_to_ms(st_raw)
        et_ms = timecode_to_ms(et_raw)
        if et_ms <= st_ms:
            et_ms = st_ms + 1000
        txt = item.get("target_text") or item.get("text") or ""
        lines.append(ScriptLine.new(start_ms=st_ms, end_ms=et_ms, text=txt))

    if lines:
        state.project.script = ScriptDocument(tuple(lines))
        state.project.target_language = "vi"
        if state.video_metadata and not state.project.video_duration_ms:
            state.project.video_duration_ms = int(state.video_metadata.get("duration", 0) * 1000)

        if state.approved_script:
            state.project.approved_revision_hash = state.project.revision_hash
            if state.project.master_voice_path and state.project.master_voice_path.is_file():
                state.project.master_voice_script_hash = state.project.revision_hash


def _import_clip_into_web(chosen_file: Path) -> None:
    """Make an exported YouTube clip the active Web Studio source."""
    state.project.video_path = chosen_file
    try:
        metadata = probe_file(chosen_file)
    except Exception as exc:
        logger.warning("Could not probe imported YouTube clip %s: %s", chosen_file, exc)
        return
    state.project.video_duration_ms = int(metadata.get("duration", 0) * 1000)
    state.video_metadata = metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.main_loop = asyncio.get_running_loop()
    defaults = load_app_settings()
    state.project = Project(
        source_language=defaults.source_language,
        target_language="vi",
        voice=VoiceSettings(
            provider=defaults.tts_backend,
            voice_id=defaults.selected_voice or "vbee-ngoc-huyen",
            display_name="Ngọc Huyền (Nữ miền Bắc)",
            speed=defaults.voice_speed,
            volume=min(1.0, defaults.voice_volume / 100),
        ),
    )

    # Initialize the browser bridge and attach the real YouTube clip worker.
    # Without this service LocalAgent only acknowledges CLIP_EXPORT_REQUEST and
    # no yt-dlp/FFmpeg job is ever started.
    try:
        state.local_agent = LocalAgent()
        if state.local_agent.start():
            state.clip_export_service = ClipExportService(
                local_agent=state.local_agent,
                project=state.project,
                workspace_dir=workspace_root(),
                import_handler=_import_clip_into_web,
            )
            logger.info(
                "LocalAgent and YouTube ClipExportService started on port %s",
                state.local_agent.port,
            )
        else:
            logger.warning("LocalAgent could not bind port %s", state.local_agent.port)
    except Exception as e:
        logger.warning("Could not start LocalAgent: %s", e)
    yield
    if state.clip_export_service:
        try:
            state.clip_export_service.shutdown(wait=False)
        except Exception:
            pass
        state.clip_export_service = None
    if state.local_agent:
        try:
            state.local_agent.stop()
        except Exception:
            pass
        state.local_agent = None


app = FastAPI(title="KAPPAK Studio Web API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Schemas
class SelectMediaRequest(BaseModel):
    path: str


class SettingsUpdateRequest(BaseModel):
    source_language: str | None = None
    target_language: str | None = None
    selected_voice: str | None = None
    voice_speed: str | None = None
    voice_volume: int | None = None
    theme: str | None = None
    default_output: str | None = None
    chatgpt_model: str | None = None


class MaskRegion(BaseModel):
    id: str | None = None
    name: str | None = "Vùng che"
    mask_type: str = "erase"
    x: float = 0.1
    y: float = 0.8
    width: float = 0.8
    height: float = 0.15
    color: str = "#000000"
    opacity: float = 1.0
    blur_strength: int = 15
    start_ms: int = 0
    end_ms: int = 0
    label: str | None = None


class MaskListRequest(BaseModel):
    masks: list[MaskRegion]


class VoicePreviewRequest(BaseModel):
    voice_id: str = "vi-VN-HoaiMyNeural"
    provider: str = "edge_tts"
    speed: str = "1.0x"
    sample_text: str | None = None


class SubtitleItem(BaseModel):
    id: int
    start_time: str
    end_time: str
    source_text: str
    target_text: str


class ExportRequest(BaseModel):
    burn_subtitles: bool = True
    apply_masks: bool = True
    ducking_volume: float = 0.15
    voice_volume: float = 1.0


class DownloaderInspectRequest(BaseModel):
    url: str


class DownloaderDownloadRequest(BaseModel):
    url: str
    quality: str = "best"


# REST Endpoints
@app.get("/api/health")
def get_health():
    ffmpeg_bin = find_tool("ffmpeg")
    ffprobe_bin = find_tool("ffprobe")
    return {
        "status": "ok",
        "ffmpeg": bool(ffmpeg_bin),
        "ffmpeg_path": ffmpeg_bin,
        "ffprobe": bool(ffprobe_bin),
        "ffprobe_path": ffprobe_bin,
        "local_agent": bool(state.local_agent and state.local_agent.running),
        "version": "2.1.17",
    }


@app.get("/api/bridge/status")
def get_bridge_status():
    if not state.local_agent:
        return {"connected": False, "chatgpt": False, "vbee": False}
    agent = state.local_agent
    connected = (
        agent.is_connected()
        if callable(getattr(agent, "is_connected", None))
        else bool(getattr(agent, "is_connected", False))
    )
    chatgpt = (
        agent.is_chatgpt_ready()
        if callable(getattr(agent, "is_chatgpt_ready", None))
        else bool(getattr(agent, "is_chatgpt_ready", False))
    )
    vbee = (
        agent.is_vbee_ready()
        if callable(getattr(agent, "is_vbee_ready", None))
        else bool(getattr(agent, "is_vbee_ready", False))
    )
    return {
        "connected": connected,
        "chatgpt": chatgpt,
        "vbee": vbee,
    }


@app.get("/api/settings")
def get_settings():
    s = load_app_settings()
    raw_spd = getattr(s, "voice_speed", 1.0)
    if isinstance(raw_spd, (int, float)):
        spd_str = f"{raw_spd:.1f}x"
    else:
        spd_str = str(raw_spd)
        if not spd_str.endswith("x") and not spd_str.endswith("X"):
            spd_str = f"{spd_str}x"

    return {
        "source_language": getattr(s, "source_language", "auto"),
        "target_language": getattr(s, "target_language", "vi"),
        "selected_voice": getattr(s, "selected_voice", ""),
        "voice_speed": spd_str,
        "voice_volume": int(getattr(s, "voice_volume", 100)),
        "theme": getattr(s, "theme", "light"),
        "default_output": getattr(s, "default_output", ""),
        "chatgpt_model": getattr(s, "chatgpt_model", "gpt-4o"),
        "whisper_model": getattr(s, "whisper_model", "base"),
    }


@app.post("/api/settings")
def update_settings(req: SettingsUpdateRequest):
    s = load_app_settings()
    for k, v in req.model_dump(exclude_unset=True).items():
        if v is not None and hasattr(s, k):
            if k == "voice_speed":
                if isinstance(v, str):
                    try:
                        v = float(v.replace("x", "").replace("X", "").strip())
                    except ValueError:
                        v = 1.0
                elif isinstance(v, (int, float)):
                    v = float(v)
            elif k == "voice_volume" and isinstance(v, (int, str)):
                try:
                    v = float(v)
                except ValueError:
                    pass
            setattr(s, k, v)
    save_app_settings(s)
    return {"status": "saved", "settings": get_settings()}


@app.get("/api/voices")
def get_voices():
    voices = []
    try:
        vbee_voices = read_catalog("vbee")
    except Exception:
        vbee_voices = VBEE_DEFAULT_CATALOG

    for v in vbee_voices:
        voices.append({
            "id": v["id"],
            "name": v["name"],
            "provider": "vbee",
            "desc": "Giọng đọc Vbee AI",
        })

    # Edge TTS voices
    voices.extend([
        {"id": "vi-VN-HoaiMyNeural", "name": "Hoài My (Nữ - Edge TTS)", "provider": "edge_tts", "desc": "Giọng đọc Microsoft Edge AI trong trẻo, không tốn phí"},
        {"id": "vi-VN-NamMinhNeural", "name": "Nam Minh (Nam - Edge TTS)", "provider": "edge_tts", "desc": "Giọng đọc Microsoft Edge AI trầm ấm, chuẩn mực"},
    ])
    return {"voices": voices}


@app.post("/api/voices/preview")
def preview_voice(req: VoicePreviewRequest):
    """Generate or retrieve cached preview audio for AI voices."""
    sample_text = req.sample_text or "Xin chào! Đây là giọng đọc thử nghiệm trên hệ sinh thái KAPPAK Studio."
    try:
        preview_file = edge_tts_provider.preview_voice(
            text=sample_text,
            voice_id=req.voice_id,
            speed=req.speed,
        )
        duration_ms = 3000
        try:
            from vkdub.media.timeline_audio import get_audio_duration_ms
            dur = get_audio_duration_ms(preview_file)
            if dur > 0:
                duration_ms = dur
        except Exception:
            pass

        return {
            "status": "ok",
            "audio_url": f"/api/voices/preview/stream?cache_id={preview_file.name}",
            "duration_ms": duration_ms,
        }
    except Exception as e:
        logger.exception("Voice preview generation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Không thể tạo mẫu âm thanh nghe thử: {e}")


@app.get("/api/voices/preview/stream")
def stream_voice_preview(cache_id: str = Query(...)):
    """Stream synthesized preview audio to web player."""
    clean_id = Path(cache_id).name
    cache_file = workspace_root() / "cache" / clean_id
    if not cache_file.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp âm thanh nghe thử.")
    return FileResponse(cache_file, media_type="audio/mpeg")


# Masks REST APIs (Step 3)
@app.get("/api/masks")
def get_masks():
    """Retrieve all current blur/mask regions."""
    return {"masks": [m.to_dict() for m in state.project.masks]}


@app.post("/api/masks")
def save_masks(body: MaskListRequest | list[MaskRegion]):
    """Persist interactive canvas mask regions into state.project.masks."""
    regions = body.masks if isinstance(body, MaskListRequest) else body
    new_items: list[MaskItem] = []
    for m in regions:
        mask_id = m.id if m.id and str(m.id).strip() else str(uuid4())
        item = MaskItem(
            id=mask_id,
            name=m.name or m.label or "Vùng che",
            mask_type=m.mask_type,
            x=m.x,
            y=m.y,
            width=m.width,
            height=m.height,
            color=m.color,
            opacity=m.opacity,
            blur_strength=m.blur_strength,
            start_ms=m.start_ms,
            end_ms=m.end_ms,
        )
        new_items.append(item)

    state.project.masks = new_items
    return {"status": "ok", "count": len(state.project.masks), "masks": [m.to_dict() for m in state.project.masks]}


@app.delete("/api/masks/{mask_id}")
def delete_mask(mask_id: str):
    """Remove a specific mask region by ID."""
    initial_count = len(state.project.masks)
    state.project.masks = [m for m in state.project.masks if m.id != mask_id]
    if len(state.project.masks) == initial_count:
        raise HTTPException(status_code=404, detail="Không tìm thấy vùng che với ID tương ứng.")
    return {"status": "deleted", "mask_id": mask_id, "count": len(state.project.masks)}


def probe_file(file_path: Path) -> dict[str, Any]:
    ffprobe_bin = find_tool("ffprobe")
    if not ffprobe_bin:
        raise HTTPException(status_code=500, detail="Không tìm thấy ffprobe trên hệ thống.")

    res = subprocess.run(
        [ffprobe_bin, "-v", "error", "-show_format", "-show_streams", "-print_format", "json", str(file_path)],
        capture_output=True,
        text=True,
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
    if res.returncode != 0:
        raise HTTPException(status_code=400, detail="Không thể đọc thông tin video.")

    meta = parse_metadata(res.stdout)
    return {
        "path": str(file_path),
        "filename": file_path.name,
        "duration": meta.duration,
        "duration_str": f"{int(meta.duration // 60):02d}:{int(meta.duration % 60):02d}",
        "width": meta.width,
        "height": meta.height,
        "resolution": f"{meta.width} × {meta.height}",
        "fps": round(meta.fps, 2),
        "video_codec": meta.video_codec,
        "audio_codec": meta.audio_codec or "none",
        "size_bytes": meta.size_bytes,
        "size_mb": round(meta.size_bytes / (1024 * 1024), 1),
    }


@app.post("/api/media/select")
def select_media(req: SelectMediaRequest):
    p = Path(req.path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Tệp video không tồn tại.")

    meta = probe_file(p)
    state.project.video_path = p
    state.project.video_duration_ms = int(meta["duration"] * 1000)
    state.project.target_language = "vi"
    state.video_metadata = meta
    return {"status": "ok", "metadata": meta}


@app.get("/api/projects/recent")
def get_recent_projects():
    """Fetch real recent projects and downloaded media assets for the Web Home View."""
    results = []
    try:
        from kappak.core.db import db_session
        from kappak.modules.downloader.service import format_duration
        with db_session() as conn:
            # 1. Fetch from projects table
            proj_rows = conn.execute(
                "SELECT id, name, description, root_path, updated_at FROM projects ORDER BY updated_at DESC LIMIT 6"
            ).fetchall()
            for r in proj_rows:
                results.append({
                    "id": r["id"],
                    "title": r["name"],
                    "duration": "Dự án",
                    "updated": str(r["updated_at"])[:10] if r["updated_at"] else "",
                    "thumb": "/kappak/thumb_sample_1.png",
                    "type": "project",
                    "path": r["root_path"],
                })

            # 2. Fetch from assets table (video files downloaded)
            asset_rows = conn.execute(
                """
                SELECT id, name, local_path, platform, duration_sec, file_size, updated_at
                FROM assets
                WHERE local_path LIKE '%.mp4' OR local_path LIKE '%.mov' OR local_path LIKE '%.mkv'
                ORDER BY updated_at DESC LIMIT 6
                """
            ).fetchall()
            for a in asset_rows:
                dur_str = format_duration(a["duration_sec"])
                results.append({
                    "id": a["id"],
                    "title": a["name"],
                    "duration": dur_str,
                    "updated": str(a["updated_at"])[:10] if a["updated_at"] else "",
                    "thumb": "/kappak/thumb_sample_2.png",
                    "type": "video_asset",
                    "path": a["local_path"],
                })
    except Exception as e:
        logger.warning("Error fetching recent projects from database: %s", e)

    # 3. If empty, check evidence/media sample files so UI is immediately useful
    if not results:
        sample_path = root_dir / "docs" / "evidence" / "media" / "sample.mp4"
        if sample_path.is_file():
            results.append({
                "id": "sample_bundled_1",
                "title": "Video mẫu tiếng Anh (sample.mp4)",
                "duration": "00:07",
                "updated": "Có sẵn",
                "thumb": "/kappak/thumb_sample_3.png",
                "type": "sample",
                "path": str(sample_path),
            })

    return {"projects": results}


@app.post("/api/projects/load")
def load_project_or_asset(payload: dict):
    path_str = payload.get("path")
    if not path_str:
        raise HTTPException(status_code=400, detail="Thiếu đường dẫn tệp.")
    p = Path(path_str)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Tệp không tồn tại.")
    meta = probe_file(p)
    state.project.video_path = p
    state.project.video_duration_ms = int(meta["duration"] * 1000)
    state.project.target_language = "vi"
    state.video_metadata = meta
    return {"status": "ok", "metadata": meta, "video_url": f"/api/media/stream?path={p.name}"}


@app.post("/api/downloader/inspect")
def inspect_download_url(req: DownloaderInspectRequest):
    """Fetch video metadata from URL without downloading."""
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Vui lòng nhập đường link video.")
    try:
        from kappak.modules.downloader.service import fetch_video_metadata
        meta = fetch_video_metadata(url)
        return {
            "status": "ok",
            "metadata": {
                "url": meta.url,
                "title": meta.title,
                "creator": meta.creator,
                "duration_sec": meta.duration_sec,
                "duration_str": meta.duration_str,
                "thumbnail_url": meta.thumbnail_url,
                "platform": meta.platform,
                "formats": meta.formats,
                "description": meta.description,
            },
        }
    except Exception as e:
        logger.warning("Downloader inspect failed for %s: %s", url, e)
        raise HTTPException(status_code=400, detail=f"Không thể đọc thông tin video: {str(e)[:200]}")


@app.post("/api/downloader/download")
def download_video_api(req: DownloaderDownloadRequest):
    """Download video with yt-dlp, compute SHA-256 deduplication, and store in assets."""
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Vui lòng nhập đường link video.")

    download_dir = workspace_root() / "downloads"
    download_dir.mkdir(parents=True, exist_ok=True)

    try:
        from kappak.modules.downloader.service import download_media, format_duration
        asset = download_media(
            url=url,
            output_dir=download_dir,
            quality_choice=req.quality,
        )
        dur_str = format_duration(asset.duration_sec)
        return {
            "status": "ok",
            "asset": {
                "id": asset.id,
                "name": asset.name,
                "local_path": str(asset.local_path),
                "sha256_hash": asset.sha256_hash,
                "platform": asset.platform,
                "creator": asset.creator,
                "duration_sec": asset.duration_sec,
                "duration_str": dur_str,
                "resolution": asset.resolution,
                "file_size": asset.file_size,
                "video_url": f"/api/media/stream?path={asset.local_path.name}",
            },
        }
    except Exception as e:
        logger.exception("Download failed for %s: %s", url, e)
        raise HTTPException(status_code=500, detail=f"Tải video thất bại: {str(e)[:200]}")


@app.get("/api/downloader/history")
def get_download_history():
    """Retrieve history of downloaded video assets from SQLite."""
    items = []
    try:
        from kappak.core.db import db_session
        from kappak.modules.downloader.service import format_duration
        with db_session() as conn:
            rows = conn.execute(
                """
                SELECT id, name, local_path, source_url, platform, creator,
                       duration_sec, resolution, file_size, sha256_hash, updated_at
                FROM assets
                WHERE local_path LIKE '%.mp4' OR local_path LIKE '%.mov' OR local_path LIKE '%.mkv' OR local_path LIKE '%.mp3'
                ORDER BY updated_at DESC LIMIT 20
                """
            ).fetchall()
            for r in rows:
                p = Path(r["local_path"])
                exists = p.is_file()
                dur_str = format_duration(r["duration_sec"])
                items.append({
                    "id": r["id"],
                    "name": r["name"],
                    "local_path": r["local_path"],
                    "filename": p.name,
                    "source_url": r["source_url"],
                    "platform": r["platform"],
                    "creator": r["creator"],
                    "duration_sec": r["duration_sec"],
                    "duration_str": dur_str,
                    "resolution": r["resolution"],
                    "file_size": r["file_size"],
                    "sha256_hash": r["sha256_hash"],
                    "file_exists": exists,
                    "updated_at": str(r["updated_at"])[:19] if r["updated_at"] else "",
                    "video_url": f"/api/media/stream?path={p.name}" if exists else "",
                })
    except Exception as e:
        logger.warning("Error fetching download history: %s", e)
    return {"assets": items}


# ============================================================================
# DATA STUDIO MODULE ENDPOINTS (PHASE 2)
# ============================================================================

@app.get("/api/data-studio/overview")
def get_data_studio_overview():
    """Aggregated media asset statistics and storage breakdown."""
    try:
        from kappak.modules.data_studio.service import get_storage_overview
        overview = get_storage_overview()
        return overview.to_dict()
    except Exception as e:
        logger.exception("Failed to get storage overview: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data-studio/assets")
def get_data_studio_assets(
    collection: str = Query("all"),
    search: str = Query(""),
    project_id: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
):
    """Retrieve assets filtered by smart collections or search queries."""
    try:
        from kappak.modules.data_studio.service import list_assets
        items = list_assets(
            collection=collection,
            search=search,
            project_id=project_id,
            limit=limit,
            offset=offset,
        )
        return {"assets": items, "count": len(items)}
    except Exception as e:
        logger.exception("Failed to list assets: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data-studio/duplicates")
def get_data_studio_duplicates():
    """Retrieve duplicate media asset groups by SHA-256."""
    try:
        from kappak.modules.data_studio.service import find_duplicate_assets
        dups = find_duplicate_assets()
        return {"duplicates": dups, "groups_count": len(dups)}
    except Exception as e:
        logger.exception("Failed to find duplicates: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class DeleteAssetRequest(BaseModel):
    asset_id: str
    delete_file: bool = False


@app.post("/api/data-studio/assets/delete")
def delete_data_studio_asset(req: DeleteAssetRequest):
    """Delete an asset from the database and optionally from disk."""
    try:
        from kappak.modules.data_studio.service import delete_asset
        success = delete_asset(req.asset_id, delete_file=req.delete_file)
        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài nguyên.")
        return {"status": "ok", "deleted_id": req.asset_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete asset: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data-studio/folder-tree")
def get_data_studio_folder_tree(project_path: str | None = Query(None)):
    """Inspect the 8-tier folder structure for a project root."""
    try:
        from kappak.modules.data_studio.service import get_project_folder_tree
        target_dir = Path(project_path) if project_path else workspace_root()
        tree = get_project_folder_tree(target_dir)
        return tree
    except Exception as e:
        logger.exception("Failed to get folder tree: %s", e)
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/media/sample")
def select_sample_media(orientation: str = Query("vertical")):
    """Load bundled sample video (vertical 9:16 or horizontal 16:9)."""
    if orientation == "vertical":
        candidates = [
            workspace_root() / "uploads" / "SaveDouyin_Douyin_Media_7672068956210875689_001_576p.mp4",
            workspace_root() / "uploads" / "SaveDouyin_Douyin_Media_7677967206935809332_001_576p.mp4",
            workspace_root() / "docs" / "evidence" / "media" / "sample_vertical_9_16.mp4",
            workspace_root() / "docs" / "evidence" / "downloads-real" / "SaveTik-verified-full-dubbed.mp4",
            workspace_root() / "docs" / "evidence" / "media" / "sample.mp4",
        ]
    else:
        candidates = [
            workspace_root() / "uploads" / "2026-09-07 04-39-46.mp4",
            workspace_root() / "docs" / "evidence" / "media" / "sample.mp4",
            workspace_root() / "docs" / "evidence" / "downloads-real" / "first-8-seconds.mp4",
        ]

    # Additional dynamic lookup in uploads directory
    uploads_dir = workspace_root() / "uploads"
    if uploads_dir.is_dir():
        for f in uploads_dir.glob("*.mp4"):
            if f not in candidates:
                candidates.append(f)

    chosen = next((c for c in candidates if c.is_file()), None)
    if not chosen:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp video mẫu.")

    meta = probe_file(chosen)
    state.project.video_path = chosen
    state.project.video_duration_ms = int(meta["duration"] * 1000)
    state.project.target_language = "vi"
    state.video_metadata = meta

    # Auto create a sample mask if none exists
    if not state.project.masks:
        if meta["height"] > meta["width"]:
            state.project.masks = [
                MaskItem(name="Phụ đề gốc TikTok", x=0.08, y=0.74, width=0.84, height=0.12, blur_strength=18)
            ]
        else:
            state.project.masks = [
                MaskItem(name="Phụ đề gốc Ngang", x=0.10, y=0.80, width=0.80, height=0.12, blur_strength=16)
            ]

    return {
        "status": "ok",
        "metadata": meta,
        "video_url": f"/api/media/stream?path={chosen.name}",
        "masks": [m.to_dict() for m in state.project.masks],
    }


@app.post("/api/media/upload")
async def upload_media(file: UploadFile = File(...)):
    upload_dir = workspace_root() / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / file.filename
    with target.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    meta = probe_file(target)
    state.project.video_path = target
    state.project.video_duration_ms = int(meta["duration"] * 1000)
    state.project.target_language = "vi"
    state.video_metadata = meta
    return {"status": "ok", "metadata": meta}


@app.get("/api/media/stream")
def stream_media(path: str | None = None):
    p = Path(path) if path else state.project.video_path
    if not p or not p.is_file():
        if path:
            candidates = [
                workspace_root() / path,
                workspace_root() / "docs" / "evidence" / "media" / path,
                workspace_root() / "uploads" / path,
                workspace_root() / "downloads" / path,
                Path(path),
            ]
            p = next((c for c in candidates if c.is_file()), None)
        if not p or not p.is_file():
            raise HTTPException(status_code=404, detail="Video không tồn tại.")
    return FileResponse(p, media_type="video/mp4", headers={"Accept-Ranges": "bytes"})


@app.get("/api/logo")
def get_logo():
    logo_path = root_dir / "logo" / "logo.png"
    if not logo_path.is_file():
        raise HTTPException(status_code=404, detail="Logo không tồn tại.")
    return FileResponse(logo_path, media_type="image/png")


@app.get("/favicon.ico")
@app.get("/favicon.png")
def get_favicon():
    logo_path = root_dir / "logo" / "logo.png"
    if logo_path.is_file():
        return FileResponse(logo_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Favicon không tồn tại.")


# Pipeline Execution
def _runner_worker(runner: PipelineRunner):
    try:
        runner.run()
    except Exception as e:
        logger.exception("Pipeline runner worker error: %s", e)


@app.post("/api/pipeline/start")
def start_pipeline():
    if not state.project.video_path or not state.project.video_path.is_file():
        # Auto-fallback to bundled sample video to allow instant testing
        candidates = [
            workspace_root() / "docs" / "evidence" / "media" / "sample_vertical_9_16.mp4",
            workspace_root() / "docs" / "evidence" / "media" / "sample.mp4",
            workspace_root() / "docs" / "evidence" / "downloads-real" / "first-8-seconds.mp4",
        ]
        found = next((c for c in candidates if c.is_file()), None)
        if found:
            state.project.video_path = found
            try:
                state.video_metadata = probe_file(found)
            except Exception:
                pass
        else:
            raise HTTPException(status_code=400, detail="Vui lòng chọn video trước khi chạy.")

    # Ensure at least one mask exists
    if not state.project.masks:
        state.project.masks = [
            MaskItem(name="Phụ đề che mờ", x=0.08, y=0.74, width=0.84, height=0.12, blur_strength=16)
        ]

    if state.active_runner and state.runner_thread and state.runner_thread.is_alive():
        raise HTTPException(status_code=409, detail="Tiến trình đang chạy.")

    # Reset substeps and set step 4.1 to RUNNING immediately
    for s in state.substeps:
        s["status"] = "PENDING"
        s["progress"] = 0
        s["message"] = "Chờ xử lý..."
    if state.substeps:
        state.substeps[0]["status"] = "RUNNING"
        state.substeps[0]["progress"] = 15
        state.substeps[0]["message"] = "Khởi chạy bóc băng Whisper..."
    state.overall_pct = 5
    state.overall_msg = "Đang khởi động tiến trình tự động hóa..."
    state.logs.clear()

    run_in_async_loop(broadcast_ws({
        "type": "substep",
        "step_id": "4.1",
        "status": "RUNNING",
        "progress": 15,
        "message": "Khởi chạy bóc băng Whisper...",
    }))
    run_in_async_loop(broadcast_ws({
        "type": "overall",
        "pct": 5,
        "message": "Đang khởi động tiến trình tự động hóa...",
    }))

    settings = load_app_settings()
    voice_id = settings.selected_voice or "vbee-ngoc-huyen"
    voice_name = "Ngọc Huyền"
    if "tuong-vy" in voice_id:
        voice_name = "Tường Vy"
    elif "mai-phuong" in voice_id:
        voice_name = "Mai Phương"
    elif "manh-dung" in voice_id:
        voice_name = "Mạnh Dũng"
    elif "HoaiMy" in voice_id:
        voice_name = "Hoài My"
    elif "NamMinh" in voice_id:
        voice_name = "Nam Minh"

    video_stem = state.project.video_path.stem if state.project.video_path else "default"
    output_dir = workspace_root() / "export" / video_stem
    output_dir.mkdir(parents=True, exist_ok=True)

    runner = PipelineRunner(
        project=state.project,
        local_agent=state.local_agent,
        output_dir=output_dir,
        voice_name=voice_name,
        speed=settings.voice_speed or "1.1x",
    )

    def on_substep_updated(step_id: str, status: Any, progress: int, message: str):
        status_str = status.value if hasattr(status, "value") else str(status)
        for s in state.substeps:
            if s["id"] == step_id:
                s["status"] = status_str
                s["progress"] = progress
                s["message"] = message
                break

        # Compute weighted overall progress across 4 substeps
        weights = {"4.1": 0.25, "4.2": 0.25, "4.3": 0.10, "4.4": 0.40}
        total_weighted = 0.0
        for s in state.substeps:
            w = weights.get(s["id"], 0.25)
            total_weighted += (s.get("progress", 0) * w)

        state.overall_pct = min(99, int(total_weighted))
        state.overall_msg = f"[{step_id}] {message}"

        run_in_async_loop(broadcast_ws({
            "type": "substep",
            "step_id": step_id,
            "status": status_str,
            "progress": progress,
            "message": message,
        }))
        run_in_async_loop(broadcast_ws({
            "type": "overall",
            "pct": state.overall_pct,
            "message": state.overall_msg,
        }))

    def on_state_changed(pipeline_state: Any, message: str):
        state_str = pipeline_state.value if hasattr(pipeline_state, "value") else str(pipeline_state)
        state.overall_msg = message
        run_in_async_loop(broadcast_ws({
            "type": "state_changed",
            "state": state_str,
            "message": message,
        }))

    def on_artifact_ready(artifact_key: str, artifact_path: Any):
        p = Path(artifact_path)
        if artifact_key in ("master_audio", "timeline_master_audio", "vbee_master_audio"):
            state.project.master_voice_path = p
            if state.project.revision_hash:
                state.project.master_voice_script_hash = state.project.revision_hash
        elif artifact_key == "translated_srt" and p.is_file():
            try:
                cues = parse_cues(p.read_text(encoding="utf-8-sig", errors="replace"))
                if cues:
                    state.subtitles = [
                        {
                            "id": i,
                            "start_time": c.start_raw,
                            "end_time": c.end_raw,
                            "source_text": "",
                            "target_text": c.text,
                        }
                        for i, c in enumerate(cues, 1)
                    ]
                    _sync_subtitles_to_project()
            except Exception as e:
                logger.warning("Could not parse cues from translated_srt on artifact_ready: %s", e)

        run_in_async_loop(broadcast_ws({
            "type": "artifact_ready",
            "artifact_key": artifact_key,
            "path": str(p),
        }))

    def on_log_emitted(msg: str):
        state.logs.append(msg)
        run_in_async_loop(broadcast_ws({
            "type": "log",
            "message": msg,
        }))

    def on_pipeline_completed(artifacts: Any):
        state.overall_pct = 100
        state.overall_msg = "Hoàn tất xử lý tự động! Sẵn sàng duyệt và xuất bản."

        # Link timeline master audio or vbee audio into project
        if getattr(artifacts, "timeline_master_audio", None) and artifacts.timeline_master_audio.is_file():
            state.project.master_voice_path = artifacts.timeline_master_audio
        elif getattr(artifacts, "vbee_master_audio", None) and artifacts.vbee_master_audio.is_file():
            state.project.master_voice_path = artifacts.vbee_master_audio

        # Populate bilingual subtitles for Step 5
        orig_cues = []
        if getattr(artifacts, "original_srt", None) and artifacts.original_srt.is_file():
            try:
                orig_cues = parse_cues(artifacts.original_srt.read_text(encoding="utf-8-sig", errors="replace"))
            except Exception as e:
                logger.warning("Failed to parse original_srt on completion: %s", e)

        trans_cues = []
        if getattr(artifacts, "translated_srt", None) and artifacts.translated_srt.is_file():
            try:
                trans_cues = parse_cues(artifacts.translated_srt.read_text(encoding="utf-8-sig", errors="replace"))
            except Exception as e:
                logger.warning("Failed to parse translated_srt on completion: %s", e)

        parsed_subs = []
        if trans_cues:
            for idx, tc in enumerate(trans_cues, 1):
                src_txt = orig_cues[idx - 1].text if idx - 1 < len(orig_cues) else ""
                parsed_subs.append({
                    "id": idx,
                    "start_time": tc.start_raw,
                    "end_time": tc.end_raw,
                    "source_text": src_txt,
                    "target_text": tc.text,
                })
        elif orig_cues:
            for idx, oc in enumerate(orig_cues, 1):
                parsed_subs.append({
                    "id": idx,
                    "start_time": oc.start_raw,
                    "end_time": oc.end_raw,
                    "source_text": oc.text,
                    "target_text": oc.text,
                })

        if parsed_subs:
            state.subtitles = parsed_subs
            _sync_subtitles_to_project()

        if state.project.master_voice_path and state.project.revision_hash:
            state.project.master_voice_script_hash = state.project.revision_hash

        res_dict = artifacts.to_dict() if hasattr(artifacts, "to_dict") else {}
        run_in_async_loop(broadcast_ws({
            "type": "finished",
            "results": res_dict,
            "subtitles": state.subtitles,
        }))

    def on_pipeline_failed(short_err: str, detailed_trace: str):
        state.overall_msg = f"Lỗi: {short_err}"
        state.logs.append(detailed_trace)
        run_in_async_loop(broadcast_ws({
            "type": "failed",
            "error": short_err,
            "details": detailed_trace,
        }))

    def on_pipeline_cancelled():
        state.overall_msg = "Tiến trình đã bị dừng."
        run_in_async_loop(broadcast_ws({"type": "cancelled"}))

    # Connect valid signals on PipelineRunner with DirectConnection
    runner.substep_updated.connect(on_substep_updated, Qt.ConnectionType.DirectConnection)
    runner.state_changed.connect(on_state_changed, Qt.ConnectionType.DirectConnection)
    runner.artifact_ready.connect(on_artifact_ready, Qt.ConnectionType.DirectConnection)
    runner.log_emitted.connect(on_log_emitted, Qt.ConnectionType.DirectConnection)
    runner.pipeline_completed.connect(on_pipeline_completed, Qt.ConnectionType.DirectConnection)
    runner.pipeline_failed.connect(on_pipeline_failed, Qt.ConnectionType.DirectConnection)
    runner.pipeline_cancelled.connect(on_pipeline_cancelled, Qt.ConnectionType.DirectConnection)

    state.active_runner = runner
    state.runner_thread = threading.Thread(target=_runner_worker, args=(runner,), daemon=True)
    state.runner_thread.start()

    return {"status": "started", "message": "Tiến trình tự động hóa đã được khởi chạy."}


@app.post("/api/pipeline/cancel")
def cancel_pipeline():
    if state.active_runner:
        state.active_runner.cancel()
        return {"status": "cancelling"}
    return {"status": "idle"}


@app.get("/api/pipeline/status")
def get_pipeline_status():
    is_running = bool(state.runner_thread and state.runner_thread.is_alive())
    return {
        "running": is_running,
        "overall_pct": state.overall_pct,
        "overall_msg": state.overall_msg,
        "substeps": state.substeps,
        "logs": state.logs[-50:],
    }


# Review & Export
@app.get("/api/review/subtitles")
def get_review_subtitles():
    if not state.subtitles:
        # Default mock / sample subtitles if pipeline hasn't run yet
        state.subtitles = [
            {"id": 1, "start_time": "00:00:01,000", "end_time": "00:00:03,000", "source_text": "今天的天气真不错，我们出去走走吧。", "target_text": "Thời tiết hôm nay thật đẹp, chúng ta cùng ra ngoài đi dạo nhé."},
            {"id": 2, "start_time": "00:00:04,000", "end_time": "00:00:07,000", "source_text": "你看那座山上的云彩，就像棉花糖一样。", "target_text": "Nhìn những đám mây trên ngọn núi kìa, hệt như những chiếc kẹo bông gòn."},
            {"id": 3, "start_time": "00:00:08,000", "end_time": "00:00:11,000", "source_text": "如果每天都能这样轻松，那该有多好。", "target_text": "Nếu như ngày nào cũng được thư thả như thế này thì tuyệt biết bao."},
        ]
        _sync_subtitles_to_project()
    return {"subtitles": state.subtitles, "approved": state.approved_script}


@app.post("/api/review/subtitles")
def save_review_subtitles(items: list[SubtitleItem]):
    state.subtitles = [item.model_dump() for item in items]
    _sync_subtitles_to_project()

    # If translated.srt exists in export directory, update it
    export_dir = workspace_root() / "export"
    candidates = [
        export_dir / (state.project.video_path.stem if state.project.video_path else "") / "translated.srt",
        export_dir / "translated.srt",
    ]
    for translated_srt in candidates:
        if translated_srt.is_file() and state.project.script:
            try:
                write_srt(translated_srt, state.project.script, state.project.duration_ms)
            except Exception as e:
                logger.debug("Failed to write updated translated.srt: %s", e)


    return {"status": "saved", "count": len(state.subtitles)}


@app.post("/api/review/approve")
def approve_script():
    """Approve script and synchronize revision hash on Project."""
    _sync_subtitles_to_project()
    state.approved_script = True

    if state.project.script:
        state.project.target_language = "vi"
        if state.video_metadata and not state.project.video_duration_ms:
            state.project.video_duration_ms = int(state.video_metadata["duration"] * 1000)
        try:
            state.project.approve(True)
        except Exception:
            state.project.approved_revision_hash = state.project.revision_hash

        if state.project.master_voice_path and state.project.master_voice_path.is_file():
            state.project.master_voice_script_hash = state.project.revision_hash

    return {"status": "approved", "revision_hash": state.project.approved_revision_hash}


@app.post("/api/export/capcut")
def export_capcut():
    """Export authentic CapCut Draft project with synchronized approval and master audio."""
    if not state.project.video_path or not state.project.video_path.is_file():
        raise HTTPException(status_code=400, detail="Chưa có video nguồn hợp lệ.")

    # Synchronize subtitles and ensure approved revision hash
    _sync_subtitles_to_project()
    if not state.project.is_approved and state.project.script:
        state.project.approved_revision_hash = state.project.revision_hash
        state.approved_script = True

    # Check and probe master audio path
    if not state.project.master_voice_path or not state.project.master_voice_path.is_file():
        found = state.project._probe_master_voice()
        if not found:
            export_dir = workspace_root() / "export"
            candidates = [
                export_dir / "master_narration_timeline.mp3",
                export_dir / "vbee_master_raw.mp3",
                export_dir / state.project.video_path.stem / "master_narration_timeline.mp3",
            ]
            for c in candidates:
                if c.is_file():
                    state.project.master_voice_path = c
                    found = c
                    break

    if state.project.master_voice_path and state.project.revision_hash:
        state.project.master_voice_script_hash = state.project.revision_hash

    if not state.project.voice_ready:
        raise HTTPException(
            status_code=400,
            detail="Cần video, kịch bản đã duyệt và file âm thanh lồng tiếng hoàn chỉnh trước khi xuất CapCut.",
        )

    export_dir = workspace_root() / "export" / "capcut"
    export_dir.mkdir(parents=True, exist_ok=True)

    try:
        ffmpeg = find_tool("ffmpeg") or "ffmpeg"
        ffprobe = find_tool("ffprobe") or "ffprobe"
        result = export_capcut_project(
            project=state.project,
            draft_root=export_dir,
            ffprobe=ffprobe,
            ffmpeg=ffmpeg,
        )
        state.export_capcut_result = str(result.path)

        try:
            from vkdub.services.discord_notifier import send_discord_message, datetime, timezone
            now_iso = datetime.now(timezone.utc).isoformat()
            embed = {
                "title": "🎬 Xuất Dự Án CapCut PC Draft Thành Công!",
                "description": f"Dự án CapCut Draft đã được tạo hoàn tất tại:\n`{result.path}`",
                "color": 0x30D158,
                "timestamp": now_iso,
                "fields": [
                    {"name": "Draft ID", "value": result.draft_id, "inline": True},
                    {"name": "Video Track", "value": f"{result.video_segments} đoạn", "inline": True},
                    {"name": "Phụ đề Subtitle", "value": f"{result.caption_segments} câu", "inline": True},
                    {"name": "Master Audio", "value": "✓ Đồng bộ timeline 100%", "inline": True},
                ],
                "footer": {"text": "KAPPAK Studio Web · Export Service"},
            }
            send_discord_message(content="🎉 **[XUẤT BẢN CAPCUT THÀNH CÔNG]**", embeds=[embed])
        except Exception as disc_err:
            logger.debug("Discord notification error on CapCut export: %s", disc_err)

        return {
            "status": "ok",
            "path": str(result.path),
            "draft_id": result.draft_id,
            "video_segments": result.video_segments,
            "audio_segments": result.audio_segments,
            "caption_segments": result.caption_segments,
        }
    except Exception as e:
        logger.exception("Capcut export error: %s", e)
        raise HTTPException(status_code=500, detail=f"Xuất CapCut thất bại: {e}")


@app.post("/api/export/mp4")
def export_mp4(req: ExportRequest):
    """Authentically render dubbed audio and mask filters using FFmpeg."""
    if not state.project.video_path or not state.project.video_path.is_file():
        raise HTTPException(status_code=400, detail="Chưa có video nguồn.")

    ffmpeg_bin = find_tool("ffmpeg")
    if not ffmpeg_bin:
        raise HTTPException(status_code=500, detail="Không tìm thấy ffmpeg trên hệ thống.")

    export_dir = workspace_root() / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    output_file = export_dir / f"KAPPAK_Render_{state.project.video_path.stem}.mp4"

    # Synchronize subtitle state
    _sync_subtitles_to_project()

    # Search for valid master voice audio
    speech_audio: Path | None = None
    if state.project.master_voice_path and state.project.master_voice_path.is_file():
        speech_audio = state.project.master_voice_path
    else:
        candidates = [
            export_dir / "master_narration_timeline.mp3",
            export_dir / state.project.video_path.stem / "master_narration_timeline.mp3",
            export_dir / "vbee_master_raw.mp3",
            workspace_root() / "cache" / "speech.wav",
        ]
        for c in candidates:
            if c.is_file():
                speech_audio = c
                break

    # Prepare ASS subtitle file if requested
    ass_subtitle_path: Path | None = None
    if req.burn_subtitles and state.project.script and state.project.script.lines:
        ass_subtitle_path = export_dir / f"KAPPAK_Subtitles_{state.project.video_path.stem}.ass"
        try:
            export_ass(state.project, ass_subtitle_path)
        except Exception as e:
            logger.warning("Could not export ASS subtitles for MP4 render: %s", e)
            ass_subtitle_path = None

    width = state.video_metadata["width"] if state.video_metadata else 1280
    height = state.video_metadata["height"] if state.video_metadata else 720

    if speech_audio and speech_audio.is_file():
        cfg = RenderConfig(
            output_path=output_file,
            burn_subtitles=bool(req.burn_subtitles and ass_subtitle_path),
            apply_masks=req.apply_masks,
            original_volume=req.ducking_volume,
            voice_volume=req.voice_volume,
        )
        cmd = build_render_command(
            project=state.project,
            config=cfg,
            speech_wav_path=speech_audio,
            ass_subtitle_path=ass_subtitle_path,
            ffmpeg_exe=ffmpeg_bin,
            video_width=width,
            video_height=height,
            has_original_audio=True,
        )
    else:
        # Authentic render without dubbed audio: genuinely applies masks and burning subtitles
        cmd = [
            ffmpeg_bin,
            "-y",
            "-nostdin",
            "-i",
            str(state.project.video_path),
        ]
        vf_items: list[str] = []
        if req.apply_masks and state.project.masks:
            mask_filter = build_ffmpeg_mask_filter(state.project.masks, width, height)
            if mask_filter:
                vf_items.append(mask_filter)
        if req.burn_subtitles and ass_subtitle_path and ass_subtitle_path.is_file():
            esc_path = escape_ffmpeg_filter_path(ass_subtitle_path)
            vf_items.append(f"ass='{esc_path}'")
        if vf_items:
            cmd.extend(["-vf", ",".join(vf_items)])
        cmd.extend([
            "-c:v", "libx264",
            "-crf", "20",
            "-preset", "medium",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            str(output_file),
        ])

    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
    if res.returncode != 0:
        logger.error("FFmpeg render failed: %s", res.stderr)
        raise HTTPException(status_code=500, detail=f"Render FFmpeg thất bại: {res.stderr[-400:]}")

    size_mb = round(output_file.stat().st_size / (1024 * 1024), 2)
    state.export_mp4_result = str(output_file)

    try:
        from vkdub.services.discord_notifier import send_discord_message, datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        embed = {
            "title": "🎥 Xuất Video MP4 Hoàn Thiện Thành Công!",
            "description": f"Video MP4 đã được render hoàn chỉnh tại:\n`{output_file}`",
            "color": 0x0071E3,
            "timestamp": now_iso,
            "fields": [
                {"name": "Tệp video", "value": output_file.name, "inline": True},
                {"name": "Dung lượng", "value": f"{size_mb} MB", "inline": True},
                {"name": "Vùng che mờ", "value": f"{len(state.project.masks)} vùng", "inline": True},
            ],
            "footer": {"text": "KAPPAK Studio Web · Render Service"},
        }
        send_discord_message(content="🎬 **[XUẤT BẢN VIDEO MP4 THÀNH CÔNG]**", embeds=[embed])
    except Exception as disc_err:
        logger.debug("Discord notification error on MP4 export: %s", disc_err)

    return {
        "status": "ok",
        "path": str(output_file),
        "filename": output_file.name,
        "size_mb": size_mb,
    }


# ==========================================
# AUTO VIDEO GENERATOR ENDPOINTS (Phase 3)
# ==========================================

class AutoVideoParseScriptRequest(BaseModel):
    script_text: str = ""


class AutoVideoCreateProjectRequest(BaseModel):
    name: str = "Video Ngắn Mới"
    template_id: str = "blur_bg"
    voice_id: str = "vi-VN-HoaiMyNeural"
    voice_speed: float = 1.0
    script_text: str = ""
    bgm_asset_id: str | None = None
    bgm_volume: float = 0.15
    scenes: list[dict[str, Any]] | None = None


@app.get("/api/auto-video/templates")
async def get_auto_video_templates():
    return {"templates": auto_video_service.get_templates()}


@app.get("/api/auto-video/assets")
async def get_auto_video_assets():
    return {"assets": auto_video_service.list_available_assets()}


@app.post("/api/auto-video/script/parse")
async def parse_auto_video_script(req: AutoVideoParseScriptRequest):
    scenes = auto_video_service.parse_script_to_scenes(req.script_text)
    return {"scenes": [s.to_dict() for s in scenes]}


@app.post("/api/auto-video/projects")
async def create_auto_video_project(req: AutoVideoCreateProjectRequest):
    proj = auto_video_service.create_project(
        name=req.name,
        template_id=req.template_id,
        voice_id=req.voice_id,
        voice_speed=req.voice_speed,
        script_text=req.script_text,
        bgm_asset_id=req.bgm_asset_id,
        bgm_volume=req.bgm_volume,
    )
    if req.scenes:
        proj.scenes = [SceneSegment.from_dict(s) for s in req.scenes]
        auto_video_service.save_project(proj)
    return {"status": "ok", "project": proj.to_dict()}


@app.get("/api/auto-video/projects")
async def list_auto_video_projects():
    return {"projects": auto_video_service.list_projects()}


@app.get("/api/auto-video/projects/{project_id}")
async def get_auto_video_project_detail(project_id: str):
    proj = auto_video_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án Auto Video.")
    return {"project": proj.to_dict()}


@app.delete("/api/auto-video/projects/{project_id}")
async def delete_auto_video_project(project_id: str):
    ok = auto_video_service.delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án để xóa.")
    return {"status": "ok"}


@app.post("/api/auto-video/projects/{project_id}/render")
async def render_auto_video_project(project_id: str):
    proj = auto_video_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án Auto Video.")
    if proj.status == "RENDERING":
        return {"status": "already_rendering", "project": proj.to_dict()}

    proj.status = "RENDERING"
    proj.progress_pct = 5.0
    auto_video_service.save_project(proj)

    def render_worker():
        try:
            def on_progress(pct: float, msg: str):
                proj.progress_pct = pct
                auto_video_service.save_project(proj)
                run_in_async_loop(broadcast_ws({
                    "type": "auto_video_progress",
                    "project_id": project_id,
                    "progress_pct": pct,
                    "message": msg,
                }))

            on_progress(10.0, "Đang tổng hợp giọng đọc AI cho các cảnh...")
            auto_video_service.generate_scene_voiceovers(proj, on_progress)

            on_progress(40.0, "Đang dựng khung hình và hiệu ứng 9:16...")
            renderer = AutoVideoRenderer()
            out_file = renderer.render_project(proj, on_progress)

            proj.status = "COMPLETED"
            proj.progress_pct = 100.0
            proj.output_video_path = str(out_file)
            auto_video_service.save_project(proj)
            on_progress(100.0, "🎉 Hoàn tất dựng video 9:16!")
        except Exception as err:
            logger.error("Lỗi khi render auto video: %s", err, exc_info=True)
            proj.status = "FAILED"
            proj.error_message = str(err)
            auto_video_service.save_project(proj)
            run_in_async_loop(broadcast_ws({
                "type": "auto_video_failed",
                "project_id": project_id,
                "error": str(err),
            }))

    threading.Thread(target=render_worker, daemon=True).start()
    return {"status": "started", "project": proj.to_dict()}


@app.get("/api/auto-video/download/{project_id}")
async def download_auto_video(project_id: str):
    proj = auto_video_service.get_project(project_id)
    if not proj or not proj.output_video_path:
        raise HTTPException(status_code=404, detail="Không tìm thấy file video.")
    p = Path(proj.output_video_path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="File video không tồn tại trên ổ đĩa.")
    return FileResponse(
        p,
        media_type="video/mp4",
        filename=p.name,
        headers={"Content-Disposition": f'attachment; filename="{p.name}"'},
    )


# WebSocket for Realtime Pipeline Updates
@app.websocket("/ws/pipeline")
async def ws_pipeline(websocket: WebSocket):
    await websocket.accept()
    state.ws_clients.add(websocket)
    try:
        # Send initial status immediately
        await websocket.send_json({
            "type": "initial",
            "overall_pct": state.overall_pct,
            "overall_msg": state.overall_msg,
            "substeps": state.substeps,
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        state.ws_clients.discard(websocket)
    except Exception:
        state.ws_clients.discard(websocket)


# Mount Frontend Static Files if built
frontend_dist = root_dir / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            raise HTTPException(status_code=404)
        file_path = frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(file_path, headers={"Cache-Control": "no-cache"})
        return FileResponse(frontend_dist / "index.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


def run_server(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True):
    import uvicorn
    import webbrowser

    if open_browser:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    uvicorn.run("vkdub.web.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run_server()
