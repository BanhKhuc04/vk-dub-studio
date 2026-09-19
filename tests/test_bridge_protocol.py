"""Unit tests for Browser Bridge protocol, schemas, LocalAgent status and routing."""

import json
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from vkdub.bridge.local_agent import LocalAgent
from vkdub.bridge.protocol import (
    PROTOCOL_VERSION,
    Actions,
    BridgeStatus,
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
    OpenOutputFolderPayload,
    YouTubeContextSync,
    YouTubePreviewClip,
    YouTubeSeekTo,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_bridge_status_defaults():
    status = BridgeStatus()
    assert not status.browser_connected
    assert not status.chatgpt_available
    assert not status.chatgpt_logged_in
    assert not status.vbee_available
    assert not status.vbee_logged_in
    assert status.browser_name == "Chưa kết nối"
    assert status.chatgpt_tabs == 0
    assert status.vbee_tabs == 0


def test_bridge_status_from_payload():
    payload = {
        "browser_connected": True,
        "chatgpt_available": True,
        "chatgpt_logged_in": True,
        "vbee_available": False,
        "vbee_logged_in": True,
        "browser_name": "Microsoft Edge",
        "active_tabs": {
            "chatgpt": 2,
            "vbee": 0,
        },
        "timestamp": 1741334500.0,
        "details": {"test": 123},
    }
    status = BridgeStatus.from_payload(payload)

    assert status.browser_connected is True
    assert status.chatgpt_available is True
    assert status.chatgpt_logged_in is True
    assert status.vbee_available is False
    assert status.vbee_logged_in is True
    assert status.browser_name == "Microsoft Edge"
    assert status.chatgpt_tabs == 2
    assert status.vbee_tabs == 0
    assert status.details == {"test": 123}


def test_bridge_status_to_dict():
    status = BridgeStatus(
        browser_connected=True,
        chatgpt_available=True,
        chatgpt_logged_in=False,
        vbee_available=True,
        vbee_logged_in=True,
        browser_name="Google Chrome",
    )
    d = status.to_dict()
    assert d["browser_connected"] is True
    assert d["chatgpt_available"] is True
    assert d["chatgpt_logged_in"] is False
    assert d["vbee_logged_in"] is True
    assert d["browser_name"] == "Google Chrome"


def test_actions_constants():
    # Existing actions
    assert Actions.GET_STATUS == "GET_STATUS"
    assert Actions.STATUS_REPORT == "STATUS_REPORT"
    assert Actions.PING == "PING"
    assert Actions.PONG == "PONG"
    assert Actions.CHATGPT_TRANSLATE == "CHATGPT_TRANSLATE"
    assert Actions.CHATGPT_TRANSLATE_RESULT == "CHATGPT_TRANSLATE_RESULT"
    assert Actions.VBEE_GENERATE_VOICE == "VBEE_GENERATE_VOICE"
    assert Actions.VBEE_VOICE_RESULT == "VBEE_VOICE_RESULT"
    assert Actions.VBEE_PROGRESS == "VBEE_PROGRESS"
    assert PROTOCOL_VERSION == "1.0.0"

    # 10 new YouTube Clip Mode actions
    assert Actions.YOUTUBE_CONTEXT_SYNC == "YOUTUBE_CONTEXT_SYNC"
    assert Actions.YOUTUBE_SEEK_TO == "YOUTUBE_SEEK_TO"
    assert Actions.YOUTUBE_PREVIEW_CLIP == "YOUTUBE_PREVIEW_CLIP"
    assert Actions.CLIP_EXPORT_REQUEST == "CLIP_EXPORT_REQUEST"
    assert Actions.CLIP_EXPORT_ACCEPTED == "CLIP_EXPORT_ACCEPTED"
    assert Actions.CLIP_EXPORT_PROGRESS == "CLIP_EXPORT_PROGRESS"
    assert Actions.CLIP_EXPORT_RESULT == "CLIP_EXPORT_RESULT"
    assert Actions.CLIP_EXPORT_ERROR == "CLIP_EXPORT_ERROR"
    assert Actions.CLIP_EXPORT_CANCEL == "CLIP_EXPORT_CANCEL"
    assert Actions.OPEN_OUTPUT_FOLDER == "OPEN_OUTPUT_FOLDER"


def test_protocol_stage_and_mode_constants():
    assert ExportStage.PROBING == "PROBING"
    assert ExportStage.CHECKING_SOURCE == "CHECKING_SOURCE"
    assert ExportStage.DOWNLOADING == "DOWNLOADING"
    assert ExportStage.REMUXING == "REMUXING"
    assert ExportStage.TRIMMING == "TRIMMING"
    assert ExportStage.MERGING == "MERGING"
    assert ExportStage.COMPLETE == "COMPLETE"
    assert ExportStage.CANCELLED == "CANCELLED"
    assert ExportStage.ERROR == "ERROR"

    assert ExportMode.SEPARATE == "SEPARATE"
    assert ExportMode.MERGED == "MERGED"
    assert ExportMode.IMPORT == "IMPORT"

    assert CutMode.STREAM_COPY == "STREAM_COPY"
    assert CutMode.FRAME_ACCURATE == "FRAME_ACCURATE"


def test_clip_item_duration_and_validity():
    clip = ClipItem(id="clip_1", name="Segment 1", start=10.0, end=25.5)
    assert clip.duration == 15.5
    assert clip.is_valid() is True
    assert clip.is_valid(max_duration=30.0) is True
    assert clip.is_valid(max_duration=20.0) is False

    invalid_clip = ClipItem(id="clip_bad", start=30.0, end=20.0)
    assert invalid_clip.is_valid() is False
    negative_clip = ClipItem(id="clip_neg", start=-5.0, end=10.0)
    assert negative_clip.is_valid() is False


def test_clip_item_roundtrip_dict():
    raw = {"id": "c1", "name": "Test", "start": 5.0, "end": 12.0, "selected": True}
    clip = ClipItem.from_dict(raw)
    assert clip.id == "c1"
    assert clip.duration == 7.0

    d = clip.to_dict()
    assert d["id"] == "c1"
    assert d["duration"] == 7.0
    assert d["selected"] is True


def test_youtube_context_sync_payload():
    camel_payload = {
        "videoId": "abc123xyz",
        "title": "Sample YouTube Video",
        "duration": 360.5,
        "url": "https://www.youtube.com/watch?v=abc123xyz",
        "canonicalUrl": "https://www.youtube.com/watch?v=abc123xyz",
        "author": "Sample Channel",
        "currentTime": 45.2,
        "thumbnailUrl": "https://i.ytimg.com/vi/abc123xyz/hqdefault.jpg",
        "tabId": 101,
        "timestamp": 1741334600.0,
    }
    sync = YouTubeContextSync.from_payload(camel_payload)
    assert sync.video_id == "abc123xyz"
    assert sync.title == "Sample YouTube Video"
    assert sync.duration == 360.5
    assert sync.current_time == 45.2
    assert sync.tab_id == 101

    d_camel = sync.to_dict(camel_case=True)
    assert d_camel["videoId"] == "abc123xyz"
    assert d_camel["currentTime"] == 45.2

    d_snake = sync.to_dict(camel_case=False)
    assert d_snake["video_id"] == "abc123xyz"
    assert d_snake["current_time"] == 45.2


def test_clip_export_request_parsing_and_normalization():
    # 1. Test camelCase with flat fields and mode="INDIVIDUAL"
    payload_camel = {
        "requestId": "req_001",
        "videoId": "vid_xyz",
        "videoUrl": "https://youtube.com/watch?v=vid_xyz",
        "videoTitle": "Funny Cats",
        "duration": 120.0,
        "clips": [
            {"id": "c1", "name": "Cat 1", "start": 0.0, "end": 15.0},
            {"id": "c2", "name": "Cat 2", "start": 20.0, "end": 35.0},
        ],
        "exportMode": "INDIVIDUAL",
        "outputDir": "D:/export",
        "container": "mp4",
        "quality": "1080p",
        "cutMode": "FRAME_ACCURATE",
        "useCookies": True,
        "browser": "chrome",
    }
    req = ClipExportRequest.from_payload(payload_camel)
    assert req.request_id == "req_001"
    assert req.job_id == "req_001"
    assert req.video_id == "vid_xyz"
    assert len(req.clips) == 2
    assert req.clips[0].duration == 15.0
    assert req.export_mode == ExportMode.SEPARATE  # Normalized from INDIVIDUAL
    assert req.cut_mode == CutMode.FRAME_ACCURATE
    assert req.use_cookies is True
    assert req.browser == "chrome"

    # 2. Test nested export_config with mode="pipeline_dub"
    payload_nested = {
        "request_id": "req_002",
        "job_id": "job_custom_002",
        "video_id": "vid_abc",
        "video_url": "https://youtube.com/watch?v=vid_abc",
        "video_title": "Documentary",
        "duration": 500.0,
        "clips": [{"id": "c1", "name": "Intro", "start": 10.0, "end": 60.0}],
        "export_config": {
            "mode": "pipeline_dub",
            "output_dir": "D:/docs",
            "container": "mkv",
            "quality": "best",
            "cut_mode": "stream_copy",
            "use_cookies": False,
        },
    }
    req2 = ClipExportRequest.from_payload(payload_nested)
    assert req2.request_id == "req_002"
    assert req2.job_id == "job_custom_002"
    assert req2.export_mode == ExportMode.IMPORT  # Normalized from pipeline_dub
    assert req2.container == "mkv"
    assert req2.cut_mode == CutMode.STREAM_COPY
    assert req2.use_cookies is False

    d2 = req2.to_dict(camel_case=True)
    assert d2["requestId"] == "req_002"
    assert d2["exportMode"] == "IMPORT"


def test_clip_export_accepted_progress_result_error_cancel():
    # Accepted
    acc = ClipExportAccepted.from_payload(
        {"requestId": "req_1", "jobId": "job_1", "status": "QUEUED", "totalClips": 3}
    )
    assert acc.request_id == "req_1"
    assert acc.job_id == "job_1"
    assert acc.total_clips == 3
    assert acc.to_dict()["status"] == "QUEUED"

    # Progress
    prog = ClipExportProgress.from_payload(
        {
            "requestId": "req_1",
            "jobId": "job_1",
            "stage": ExportStage.DOWNLOADING,
            "percent": 55.5,
            "speed": "12 MB/s",
            "downloadedBytes": 50000000,
            "totalBytes": 90000000,
            "currentClip": 1,
            "totalClips": 3,
            "message": "Downloading video stream...",
        }
    )
    assert prog.stage == ExportStage.DOWNLOADING
    assert prog.percent == 55.5
    assert prog.downloaded_bytes == 50000000
    assert prog.to_dict()["speed"] == "12 MB/s"

    # Result
    res = ClipExportResult.from_payload(
        {
            "requestId": "req_1",
            "jobId": "job_1",
            "status": "SUCCESS",
            "files": ["D:/out/clip1.mp4", "D:/out/clip2.mp4"],
            "mergedFile": None,
            "outputDir": "D:/out",
            "elapsedSeconds": 14.2,
        }
    )
    assert res.success is True
    assert len(res.files) == 2
    assert res.elapsed_seconds == 14.2
    assert res.to_dict(camel_case=True)["outputDir"] == "D:/out"

    # Error
    err = ClipExportError.from_payload(
        {
            "requestId": "req_1",
            "jobId": "job_1",
            "error": "yt-dlp download failed",
            "stage": ExportStage.DOWNLOADING,
            "details": "Connection timed out",
        }
    )
    assert err.success is False
    assert err.error == "yt-dlp download failed"
    assert err.stage == ExportStage.DOWNLOADING

    # Cancel
    cancel = ClipExportCancel.from_payload({"requestId": "req_1", "jobId": "job_1"})
    assert cancel.request_id == "req_1"
    assert cancel.job_id == "job_1"

    # Open folder
    open_folder = OpenOutputFolderPayload.from_payload({"path": "D:/export/folder"})
    assert open_folder.path == "D:/export/folder"
    assert open_folder.to_dict()["folder_path"] == "D:/export/folder"


def test_youtube_seek_and_preview_dataclasses():
    seek = YouTubeSeekTo.from_payload({"seconds": 75.0, "play": False, "tabId": 99})
    assert seek.seconds == 75.0
    assert seek.play is False
    assert seek.tab_id == 99

    prev = YouTubePreviewClip.from_payload({"start": 10.0, "end": 20.0, "loop": True})
    assert prev.start == 10.0
    assert prev.end == 20.0
    assert prev.loop is True


def test_local_agent_status_methods(qapp):
    agent = LocalAgent()
    # Initially not running, not connected
    assert agent.is_connected() is False
    assert agent.is_chatgpt_ready() is False
    assert agent.is_vbee_ready() is False

    # Simulate running server with connected client socket
    agent.running = True
    agent.client_sock = MagicMock()
    agent.status.browser_connected = True

    assert agent.is_connected() is True
    assert agent.is_chatgpt_ready() is False
    assert agent.is_vbee_ready() is False

    # Mark ChatGPT available
    agent.status.chatgpt_available = True
    assert agent.is_chatgpt_ready() is True

    # Mark Vbee logged in
    agent.status.vbee_logged_in = True
    assert agent.is_vbee_ready() is True

    # If client disconnects
    agent.client_sock = None
    assert agent.is_connected() is False
    assert agent.is_chatgpt_ready() is False
    assert agent.is_vbee_ready() is False


def test_local_agent_message_routing_youtube_and_clips(qapp, monkeypatch):
    agent = LocalAgent()

    # Track signal emissions
    context_signals = []
    clip_request_signals = []
    clip_cancel_signals = []
    open_folder_signals = []

    agent.youtube_context_updated.connect(lambda ctx: context_signals.append(ctx))
    agent.clip_export_requested.connect(lambda req: clip_request_signals.append(req))
    agent.clip_export_cancelled.connect(lambda req: clip_cancel_signals.append(req))
    agent.open_output_folder_requested.connect(lambda path: open_folder_signals.append(path))

    # 1. Route YOUTUBE_CONTEXT_SYNC
    sync_msg = {
        "action": Actions.YOUTUBE_CONTEXT_SYNC,
        "payload": {
            "videoId": "vid_test",
            "title": "Test Title",
            "duration": 180.0,
        },
    }
    agent._process_message(json.dumps(sync_msg))
    assert len(context_signals) == 1
    assert context_signals[0]["videoId"] == "vid_test"
    assert agent.latest_youtube_context["title"] == "Test Title"

    # 2. Route CLIP_EXPORT_REQUEST with registered handler
    export_handled = []
    agent.set_clip_export_handler(lambda payload: export_handled.append(payload))

    req_msg = {
        "action": Actions.CLIP_EXPORT_REQUEST,
        "payload": {
            "requestId": "req_abc",
            "videoId": "vid_test",
            "clips": [{"id": "c1", "start": 0, "end": 10}],
        },
    }
    agent._process_message(json.dumps(req_msg))
    assert len(clip_request_signals) == 1
    assert len(export_handled) == 1
    assert export_handled[0]["requestId"] == "req_abc"

    # 3. Route CLIP_EXPORT_CANCEL with registered handler
    cancel_handled = []
    agent.set_clip_cancel_handler(lambda payload: cancel_handled.append(payload))

    cancel_msg = {
        "action": Actions.CLIP_EXPORT_CANCEL,
        "payload": {"requestId": "req_abc", "jobId": "job_abc"},
    }
    agent._process_message(json.dumps(cancel_msg))
    assert len(clip_cancel_signals) == 1
    assert len(cancel_handled) == 1
    assert cancel_handled[0]["jobId"] == "job_abc"

    # 4. Route OPEN_OUTPUT_FOLDER (mocking os.startfile to prevent actual GUI launch)
    monkeypatch.setattr(agent, "open_output_folder", lambda path: True)
    folder_msg = {
        "action": Actions.OPEN_OUTPUT_FOLDER,
        "payload": {"folder_path": "D:/test_folder"},
    }
    agent._process_message(json.dumps(folder_msg))
    assert len(open_folder_signals) == 1
    assert open_folder_signals[0] == "D:/test_folder"

    # 5. A completed-file import is routed to the service and acknowledged.
    import_handled = []
    sent_messages = []
    agent.set_clip_import_handler(
        lambda payload: import_handled.append(payload) or {"success": True}
    )
    monkeypatch.setattr(
        agent,
        "send_command",
        lambda action, payload=None: sent_messages.append((action, payload)) or True,
    )
    agent._process_message(
        json.dumps(
            {
                "action": Actions.IMPORT_TO_STUDIO,
                "payload": {
                    "request_id": "req_abc",
                    "job_id": "job_abc",
                    "file_path": "D:/clips/ready.mp4",
                },
            }
        )
    )
    assert import_handled[0]["file_path"].endswith("ready.mp4")
    assert sent_messages[-1][0] == Actions.IMPORT_TO_STUDIO_RESULT
    assert sent_messages[-1][1]["success"] is True


def test_server_status_endpoint_resilience():
    from vkdub.web.server import get_bridge_status, state

    # When state.local_agent is None
    original_agent = state.local_agent
    try:
        state.local_agent = None
        status = get_bridge_status()
        assert status["connected"] is False
        assert status["chatgpt"] is False
        assert status["vbee"] is False
        assert status["browser_name"] == "Chưa kết nối"

        # When state.local_agent is an actual LocalAgent instance
        agent = LocalAgent()
        agent.running = True
        agent.client_sock = MagicMock()
        agent.status.browser_connected = True
        agent.status.chatgpt_logged_in = True
        agent.status.vbee_available = True

        state.local_agent = agent
        status2 = get_bridge_status()
        assert status2["connected"] is True
        assert status2["chatgpt"] is True
        assert status2["vbee"] is True
        assert status2["chatgpt_logged_in"] is True
        assert status2["vbee_available"] is True
    finally:
        state.local_agent = original_agent
