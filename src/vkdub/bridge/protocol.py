"""VK Dub Studio — Browser Bridge Protocol & Status Models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PROTOCOL_VERSION = "1.0.0"
NATIVE_HOST_NAME = "com.vkdub.bridge"


class Actions:
    # Existing
    PING = "PING"
    PONG = "PONG"
    HELLO = "HELLO"
    GET_STATUS = "GET_STATUS"
    STATUS_REPORT = "STATUS_REPORT"
    GET_AGENT_STATUS = "GET_AGENT_STATUS"
    AGENT_STATUS = "AGENT_STATUS"
    RELOAD_EXTENSION = "RELOAD_EXTENSION"
    LOG_EVENT = "LOG_EVENT"
    CHATGPT_TRANSLATE = "CHATGPT_TRANSLATE"
    CHATGPT_TRANSLATE_RESULT = "CHATGPT_TRANSLATE_RESULT"
    VBEE_GENERATE_VOICE = "VBEE_GENERATE_VOICE"
    VBEE_VOICE_RESULT = "VBEE_VOICE_RESULT"
    VBEE_PROGRESS = "VBEE_PROGRESS"

    # YouTube Clip Mode
    YOUTUBE_CONTEXT_SYNC = "YOUTUBE_CONTEXT_SYNC"
    YOUTUBE_SEEK_TO = "YOUTUBE_SEEK_TO"
    YOUTUBE_PREVIEW_CLIP = "YOUTUBE_PREVIEW_CLIP"
    CLIP_EXPORT_REQUEST = "CLIP_EXPORT_REQUEST"
    CLIP_EXPORT_ACCEPTED = "CLIP_EXPORT_ACCEPTED"
    CLIP_EXPORT_PROGRESS = "CLIP_EXPORT_PROGRESS"
    CLIP_EXPORT_RESULT = "CLIP_EXPORT_RESULT"
    CLIP_EXPORT_ERROR = "CLIP_EXPORT_ERROR"
    CLIP_EXPORT_CANCEL = "CLIP_EXPORT_CANCEL"
    OPEN_OUTPUT_FOLDER = "OPEN_OUTPUT_FOLDER"
    IMPORT_TO_STUDIO = "IMPORT_TO_STUDIO"
    IMPORT_TO_STUDIO_RESULT = "IMPORT_TO_STUDIO_RESULT"


class ExportStage:
    """Standard lifecycle stages for YouTube clip export jobs."""

    PROBING = "PROBING"
    CHECKING_SOURCE = "CHECKING_SOURCE"
    DOWNLOADING = "DOWNLOADING"
    REMUXING = "REMUXING"
    TRIMMING = "TRIMMING"
    MERGING = "MERGING"
    PIPELINE_FEED = "PIPELINE_FEED"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class ExportMode:
    """Export delivery modes."""

    SEPARATE = "SEPARATE"
    MERGED = "MERGED"
    IMPORT = "IMPORT"


class CutMode:
    """Trimming strategies."""

    STREAM_COPY = "STREAM_COPY"
    FRAME_ACCURATE = "FRAME_ACCURATE"


@dataclass
class BridgeStatus:
    """Live status reported by the VK Dub Browser Extension."""

    browser_connected: bool = False
    chatgpt_available: bool = False
    chatgpt_logged_in: bool = False
    vbee_available: bool = False
    vbee_logged_in: bool = False
    browser_name: str = "Chưa kết nối"
    chatgpt_tabs: int = 0
    vbee_tabs: int = 0
    timestamp: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> BridgeStatus:
        active_tabs = payload.get("active_tabs", {})
        return cls(
            browser_connected=bool(payload.get("browser_connected", False)),
            chatgpt_available=bool(payload.get("chatgpt_available", False)),
            chatgpt_logged_in=bool(payload.get("chatgpt_logged_in", False)),
            vbee_available=bool(payload.get("vbee_available", False)),
            vbee_logged_in=bool(payload.get("vbee_logged_in", False)),
            browser_name=str(payload.get("browser_name", "Microsoft Edge")),
            chatgpt_tabs=int(active_tabs.get("chatgpt", 0)),
            vbee_tabs=int(active_tabs.get("vbee", 0)),
            timestamp=float(payload.get("timestamp", 0.0)),
            details=dict(payload.get("details", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "browser_connected": self.browser_connected,
            "chatgpt_available": self.chatgpt_available,
            "chatgpt_logged_in": self.chatgpt_logged_in,
            "vbee_available": self.vbee_available,
            "vbee_logged_in": self.vbee_logged_in,
            "browser_name": self.browser_name,
            "chatgpt_tabs": self.chatgpt_tabs,
            "vbee_tabs": self.vbee_tabs,
            "timestamp": self.timestamp,
            "details": self.details,
        }


@dataclass
class ClipItem:
    """Individual segment in a YouTube video marked for export."""

    id: str = ""
    name: str = ""
    start: float = 0.0
    end: float = 0.0
    selected: bool = True

    @property
    def duration(self) -> float:
        """Duration in seconds, rounded to 3 decimal places."""
        return max(0.0, round(self.end - self.start, 3))

    def is_valid(self, max_duration: float | None = None) -> bool:
        """Validate that start is non-negative and strictly precedes end."""
        if self.start < 0.0 or self.end <= self.start:
            return False
        if max_duration is not None and (self.start > max_duration or self.end > max_duration):
            return False
        return True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClipItem:
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            selected=bool(data.get("selected", True)),
        )

    def to_dict(self, camel_case: bool = False) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "start": self.start,
            "end": self.end,
            "selected": self.selected,
            "duration": self.duration,
        }


@dataclass
class YouTubeContextSync:
    """Payload for YOUTUBE_CONTEXT_SYNC from extension to bridge."""

    video_id: str = ""
    title: str = ""
    duration: float = 0.0
    url: str = ""
    canonical_url: str = ""
    author: str = ""
    current_time: float = 0.0
    thumbnail_url: str = ""
    tab_id: int | None = None
    timestamp: float = 0.0

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> YouTubeContextSync:
        return cls(
            video_id=str(payload.get("video_id") or payload.get("videoId") or ""),
            title=str(payload.get("title", "")),
            duration=float(payload.get("duration", 0.0)),
            url=str(payload.get("url", "")),
            canonical_url=str(
                payload.get("canonical_url")
                or payload.get("canonicalUrl")
                or payload.get("url", "")
            ),
            author=str(payload.get("author", "")),
            current_time=float(payload.get("current_time") or payload.get("currentTime") or 0.0),
            thumbnail_url=str(payload.get("thumbnail_url") or payload.get("thumbnailUrl") or ""),
            tab_id=payload.get("tab_id")
            if payload.get("tab_id") is not None
            else payload.get("tabId"),
            timestamp=float(payload.get("timestamp", 0.0)),
        )

    def to_dict(self, camel_case: bool = False) -> dict[str, Any]:
        if camel_case:
            return {
                "videoId": self.video_id,
                "title": self.title,
                "duration": self.duration,
                "url": self.url,
                "canonicalUrl": self.canonical_url,
                "author": self.author,
                "currentTime": self.current_time,
                "thumbnailUrl": self.thumbnail_url,
                "tabId": self.tab_id,
                "timestamp": self.timestamp,
            }
        return {
            "video_id": self.video_id,
            "title": self.title,
            "duration": self.duration,
            "url": self.url,
            "canonical_url": self.canonical_url,
            "author": self.author,
            "current_time": self.current_time,
            "thumbnail_url": self.thumbnail_url,
            "tab_id": self.tab_id,
            "timestamp": self.timestamp,
        }


@dataclass
class ClipExportRequest:
    """Payload for CLIP_EXPORT_REQUEST triggering video download and trimming."""

    request_id: str = ""
    job_id: str = ""
    video_id: str = ""
    video_url: str = ""
    video_title: str = ""
    duration: float = 0.0
    clips: list[ClipItem] = field(default_factory=list)
    export_mode: str = ExportMode.SEPARATE
    output_dir: str = ""
    container: str = "mp4"
    quality: str = "best"
    cut_mode: str = CutMode.STREAM_COPY
    use_cookies: bool = False
    browser: str = "edge"
    timestamp: float = 0.0

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ClipExportRequest:
        cfg = (
            payload.get("export_config", {})
            if isinstance(payload.get("export_config"), dict)
            else {}
        )

        req_id = str(payload.get("request_id") or payload.get("requestId") or "")
        job_id = str(payload.get("job_id") or payload.get("jobId") or req_id)
        v_id = str(payload.get("video_id") or payload.get("videoId") or "")
        v_url = str(payload.get("video_url") or payload.get("videoUrl") or "")
        v_title = str(payload.get("video_title") or payload.get("videoTitle") or "")
        dur = float(payload.get("duration", 0.0))

        raw_clips = payload.get("clips", [])
        clips_list = [ClipItem.from_dict(c) for c in raw_clips if isinstance(c, dict)]

        raw_mode = str(
            cfg.get("mode")
            or cfg.get("export_mode")
            or payload.get("exportMode")
            or payload.get("export_mode")
            or ExportMode.SEPARATE
        ).upper()
        if raw_mode == "INDIVIDUAL":
            mode = ExportMode.SEPARATE
        elif raw_mode == "PIPELINE_DUB":
            mode = ExportMode.IMPORT
        elif raw_mode in (ExportMode.SEPARATE, ExportMode.MERGED, ExportMode.IMPORT):
            mode = raw_mode
        else:
            mode = ExportMode.SEPARATE

        out_dir = str(
            cfg.get("output_dir")
            or cfg.get("outputDir")
            or payload.get("outputDir")
            or payload.get("output_dir")
            or ""
        )
        cont = str(cfg.get("container") or payload.get("container") or "mp4").lower()
        qual = str(cfg.get("quality") or payload.get("quality") or "best").lower()

        raw_cut = str(
            cfg.get("cut_mode")
            or cfg.get("cutMode")
            or payload.get("cutMode")
            or payload.get("cut_mode")
            or CutMode.STREAM_COPY
        ).upper()
        if raw_cut not in (CutMode.STREAM_COPY, CutMode.FRAME_ACCURATE):
            raw_cut = CutMode.STREAM_COPY

        cookies = bool(
            cfg.get("use_cookies")
            if "use_cookies" in cfg
            else cfg.get("useCookies")
            if "useCookies" in cfg
            else payload.get("useCookies", payload.get("use_cookies", False))
        )
        browser = str(cfg.get("browser") or payload.get("browser") or "edge").lower()
        ts = float(payload.get("timestamp", 0.0))

        return cls(
            request_id=req_id,
            job_id=job_id,
            video_id=v_id,
            video_url=v_url,
            video_title=v_title,
            duration=dur,
            clips=clips_list,
            export_mode=mode,
            output_dir=out_dir,
            container=cont,
            quality=qual,
            cut_mode=raw_cut,
            use_cookies=cookies,
            browser=browser,
            timestamp=ts,
        )

    def to_dict(self, camel_case: bool = False) -> dict[str, Any]:
        if camel_case:
            return {
                "requestId": self.request_id,
                "jobId": self.job_id,
                "videoId": self.video_id,
                "videoUrl": self.video_url,
                "videoTitle": self.video_title,
                "duration": self.duration,
                "clips": [c.to_dict(camel_case=True) for c in self.clips],
                "exportMode": self.export_mode,
                "outputDir": self.output_dir,
                "container": self.container,
                "quality": self.quality,
                "cutMode": self.cut_mode,
                "useCookies": self.use_cookies,
                "browser": self.browser,
                "timestamp": self.timestamp,
            }
        return {
            "request_id": self.request_id,
            "job_id": self.job_id,
            "video_id": self.video_id,
            "video_url": self.video_url,
            "video_title": self.video_title,
            "duration": self.duration,
            "clips": [c.to_dict(camel_case=False) for c in self.clips],
            "export_mode": self.export_mode,
            "output_dir": self.output_dir,
            "container": self.container,
            "quality": self.quality,
            "cut_mode": self.cut_mode,
            "use_cookies": self.use_cookies,
            "browser": self.browser,
            "timestamp": self.timestamp,
        }


@dataclass
class ClipExportAccepted:
    """Immediate acknowledgment when an export request is queued."""

    request_id: str = ""
    job_id: str = ""
    status: str = "QUEUED"
    total_clips: int = 0
    message: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ClipExportAccepted:
        req_id = str(payload.get("request_id") or payload.get("requestId") or "")
        return cls(
            request_id=req_id,
            job_id=str(payload.get("job_id") or payload.get("jobId") or req_id),
            status=str(payload.get("status", "QUEUED")),
            total_clips=int(payload.get("total_clips") or payload.get("totalClips") or 0),
            message=str(payload.get("message", "")),
        )

    def to_dict(self, camel_case: bool = False) -> dict[str, Any]:
        if camel_case:
            return {
                "requestId": self.request_id,
                "jobId": self.job_id,
                "status": self.status,
                "totalClips": self.total_clips,
                "message": self.message,
            }
        return {
            "request_id": self.request_id,
            "job_id": self.job_id,
            "status": self.status,
            "total_clips": self.total_clips,
            "message": self.message,
        }


@dataclass
class ClipExportProgress:
    """Realtime export telemetry stream."""

    request_id: str = ""
    job_id: str = ""
    stage: str = ExportStage.PROBING
    percent: float = 0.0
    speed: str = ""
    downloaded_bytes: int = 0
    total_bytes: int = 0
    current_clip: int = 0
    total_clips: int = 0
    message: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ClipExportProgress:
        req_id = str(payload.get("request_id") or payload.get("requestId") or "")
        return cls(
            request_id=req_id,
            job_id=str(payload.get("job_id") or payload.get("jobId") or req_id),
            stage=str(payload.get("stage", ExportStage.PROBING)),
            percent=float(
                payload.get("percent") if "percent" in payload else payload.get("progress", 0.0)
            ),
            speed=str(payload.get("speed", "")),
            downloaded_bytes=int(
                payload.get("downloaded_bytes")
                if "downloaded_bytes" in payload
                else payload.get("downloadedBytes", 0)
            ),
            total_bytes=int(
                payload.get("total_bytes")
                if "total_bytes" in payload
                else payload.get("totalBytes", 0)
            ),
            current_clip=int(
                payload.get("current_clip")
                if "current_clip" in payload
                else payload.get("currentClip", payload.get("clip_index", 0))
            ),
            total_clips=int(
                payload.get("total_clips")
                if "total_clips" in payload
                else payload.get("totalClips", 0)
            ),
            message=str(payload.get("message", "")),
        )

    def to_dict(self, camel_case: bool = False) -> dict[str, Any]:
        if camel_case:
            return {
                "requestId": self.request_id,
                "jobId": self.job_id,
                "stage": self.stage,
                "percent": self.percent,
                "speed": self.speed,
                "downloadedBytes": self.downloaded_bytes,
                "totalBytes": self.total_bytes,
                "currentClip": self.current_clip,
                "totalClips": self.total_clips,
                "message": self.message,
            }
        return {
            "request_id": self.request_id,
            "job_id": self.job_id,
            "stage": self.stage,
            "percent": self.percent,
            "speed": self.speed,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "current_clip": self.current_clip,
            "total_clips": self.total_clips,
            "message": self.message,
        }


@dataclass
class ClipExportResult:
    """Final export result containing list of generated media files."""

    request_id: str = ""
    job_id: str = ""
    status: str = "SUCCESS"
    files: list[str] = field(default_factory=list)
    merged_file: str | None = None
    output_dir: str = ""
    elapsed_seconds: float = 0.0
    success: bool = True
    error: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ClipExportResult:
        req_id = str(payload.get("request_id") or payload.get("requestId") or "")
        raw_files = payload.get("files") or payload.get("generated_files") or []
        files = [str(f) for f in raw_files] if isinstance(raw_files, list) else []
        return cls(
            request_id=req_id,
            job_id=str(payload.get("job_id") or payload.get("jobId") or req_id),
            status=str(payload.get("status", "SUCCESS")),
            files=files,
            merged_file=payload.get("merged_file") or payload.get("mergedFile"),
            output_dir=str(payload.get("output_dir") or payload.get("outputDir") or ""),
            elapsed_seconds=float(
                payload.get("elapsed_seconds") or payload.get("elapsedSeconds") or 0.0
            ),
            success=bool(payload.get("success", True)),
            error=payload.get("error"),
        )

    def to_dict(self, camel_case: bool = False) -> dict[str, Any]:
        if camel_case:
            d: dict[str, Any] = {
                "requestId": self.request_id,
                "jobId": self.job_id,
                "status": self.status,
                "files": self.files,
                "outputDir": self.output_dir,
                "elapsedSeconds": self.elapsed_seconds,
                "success": self.success,
                "error": self.error,
            }
            if self.merged_file is not None:
                d["mergedFile"] = self.merged_file
            return d
        d = {
            "request_id": self.request_id,
            "job_id": self.job_id,
            "status": self.status,
            "files": self.files,
            "generated_files": self.files,
            "output_dir": self.output_dir,
            "elapsed_seconds": self.elapsed_seconds,
            "success": self.success,
            "error": self.error,
        }
        if self.merged_file is not None:
            d["merged_file"] = self.merged_file
        return d


@dataclass
class ClipExportError:
    """Error notification for failed export jobs."""

    request_id: str = ""
    job_id: str = ""
    status: str = "ERROR"
    error: str = ""
    stage: str = ""
    details: str = ""
    success: bool = False

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ClipExportError:
        req_id = str(payload.get("request_id") or payload.get("requestId") or "")
        return cls(
            request_id=req_id,
            job_id=str(payload.get("job_id") or payload.get("jobId") or req_id),
            status=str(payload.get("status", "ERROR")),
            error=str(payload.get("error", "")),
            stage=str(payload.get("stage", "")),
            details=str(payload.get("details", "")),
            success=bool(payload.get("success", False)),
        )

    def to_dict(self, camel_case: bool = False) -> dict[str, Any]:
        if camel_case:
            return {
                "requestId": self.request_id,
                "jobId": self.job_id,
                "status": self.status,
                "error": self.error,
                "stage": self.stage,
                "details": self.details,
                "success": self.success,
            }
        return {
            "request_id": self.request_id,
            "job_id": self.job_id,
            "status": self.status,
            "error": self.error,
            "stage": self.stage,
            "details": self.details,
            "success": self.success,
        }


@dataclass
class ClipExportCancel:
    """Cancellation request for a running export job."""

    request_id: str = ""
    job_id: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ClipExportCancel:
        req_id = str(payload.get("request_id") or payload.get("requestId") or "")
        return cls(
            request_id=req_id,
            job_id=str(payload.get("job_id") or payload.get("jobId") or req_id),
        )

    def to_dict(self, camel_case: bool = False) -> dict[str, Any]:
        if camel_case:
            return {"requestId": self.request_id, "jobId": self.job_id}
        return {"request_id": self.request_id, "job_id": self.job_id}


@dataclass
class OpenOutputFolderPayload:
    """Payload to open folder in OS file explorer."""

    path: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> OpenOutputFolderPayload:
        return cls(path=str(payload.get("path") or payload.get("folder_path") or ""))

    def to_dict(self, camel_case: bool = False) -> dict[str, Any]:
        return {"path": self.path, "folder_path": self.path}


@dataclass
class YouTubeSeekTo:
    """Command to seek YouTube player to specific seconds."""

    seconds: float = 0.0
    play: bool = True
    tab_id: int | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> YouTubeSeekTo:
        return cls(
            seconds=float(
                payload.get("seconds") if "seconds" in payload else payload.get("time", 0.0)
            ),
            play=bool(payload.get("play", True)),
            tab_id=payload.get("tab_id")
            if payload.get("tab_id") is not None
            else payload.get("tabId"),
        )

    def to_dict(self, camel_case: bool = False) -> dict[str, Any]:
        if camel_case:
            return {"seconds": self.seconds, "play": self.play, "tabId": self.tab_id}
        return {"seconds": self.seconds, "play": self.play, "tab_id": self.tab_id}


@dataclass
class YouTubePreviewClip:
    """Command to preview clip between [start, end] in YouTube player."""

    start: float = 0.0
    end: float = 0.0
    loop: bool = False
    tab_id: int | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> YouTubePreviewClip:
        return cls(
            start=float(payload.get("start", 0.0)),
            end=float(payload.get("end", 0.0)),
            loop=bool(payload.get("loop", False)),
            tab_id=payload.get("tab_id")
            if payload.get("tab_id") is not None
            else payload.get("tabId"),
        )

    def to_dict(self, camel_case: bool = False) -> dict[str, Any]:
        if camel_case:
            return {"start": self.start, "end": self.end, "loop": self.loop, "tabId": self.tab_id}
        return {"start": self.start, "end": self.end, "loop": self.loop, "tab_id": self.tab_id}
