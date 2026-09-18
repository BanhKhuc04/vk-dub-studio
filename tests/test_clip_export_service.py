"""VK Dub Studio — Unit & Integration Test Suite for ClipExportService."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vkdub.bridge.local_agent import LocalAgent
from vkdub.bridge.protocol import (
    ClipExportCancel,
    ClipExportProgress,
    ClipExportRequest,
    ClipItem,
    CutMode,
    ExportMode,
    ExportStage,
)
from vkdub.domain.project import Project
from vkdub.media.clip_engine import ClipEngine
from vkdub.media.hardware import HardwareEncoderDetector
from vkdub.media.ytdlp import YtDlpDownloader
from vkdub.services.clip_export_service import (
    ClipExportService,
    JobCancelledError,
    JobStatus,
    resolve_safe_output_dir,
)


def _fake_trim_clip(*args, **kwargs) -> Path:
    out = kwargs.get("output_path") or (args[1] if len(args) > 1 else None)
    if out:
        p = Path(out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
        return p
    return Path("clip.mp4")


def _fake_merge_clips(*args, **kwargs) -> Path:
    out = kwargs.get("output_path") or (args[1] if len(args) > 1 else None)
    if out:
        p = Path(out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
        return p
    return Path("merged.mp4")


# ===========================================================================
# 1. Path Resolution & Directory Traversal Prevention Tests
# ===========================================================================


def test_resolve_safe_output_dir_normal(tmp_path):
    default_dir = tmp_path / "default_out"
    custom_dir = tmp_path / "custom_out"
    resolved = resolve_safe_output_dir(str(custom_dir), default_dir)
    assert resolved == custom_dir.resolve()


def test_resolve_safe_output_dir_empty_or_none(tmp_path):
    default_dir = tmp_path / "default_out"
    assert resolve_safe_output_dir(None, default_dir) == default_dir
    assert resolve_safe_output_dir("", default_dir) == default_dir
    assert resolve_safe_output_dir("   ", default_dir) == default_dir


def test_resolve_safe_output_dir_drive_root(tmp_path):
    default_dir = tmp_path / "default_out"
    # Root of drive like C:\ or D:\ should fall back to default_dir / "clips"
    resolved = resolve_safe_output_dir("C:\\", default_dir)
    assert resolved == default_dir / "clips"
    resolved_d = resolve_safe_output_dir("D:", default_dir)
    assert resolved_d == default_dir / "clips"


def test_resolve_safe_output_dir_system_windows_folder(tmp_path):
    default_dir = tmp_path / "default_out"
    resolved = resolve_safe_output_dir("C:\\Windows", default_dir)
    assert resolved == default_dir / "clips"
    resolved_sys32 = resolve_safe_output_dir("C:\\Windows\\System32", default_dir)
    assert resolved_sys32 == default_dir / "clips"


# ===========================================================================
# 2. Service Initialization & Defaults Tests
# ===========================================================================


def test_service_initialization_defaults(tmp_path):
    service = ClipExportService(workspace_dir=tmp_path)
    assert service.workspace_dir == tmp_path.resolve()
    assert service.output_dir == (tmp_path / "exports" / "clips").resolve()
    assert service.scratch_dir == (tmp_path / "scratch" / "clips").resolve()
    assert service.cache_dir == (tmp_path / "cache" / "youtube").resolve()
    assert service.output_dir.is_dir()
    assert service.scratch_dir.is_dir()
    assert service.cache_dir.is_dir()
    assert isinstance(service.downloader, YtDlpDownloader)
    assert isinstance(service.clip_engine, ClipEngine)
    assert isinstance(service.hw_detector, HardwareEncoderDetector)
    service.shutdown(wait=False)


def test_service_attach_local_agent():
    mock_agent = MagicMock(spec=LocalAgent)
    service = ClipExportService()
    service.attach_local_agent(mock_agent)
    assert service.local_agent is mock_agent
    mock_agent.set_clip_export_handler.assert_called_once_with(service.handle_clip_export_request)
    mock_agent.set_clip_cancel_handler.assert_called_once_with(service.handle_clip_cancel_request)
    mock_agent.set_clip_import_handler.assert_called_once_with(service.handle_clip_import_request)
    service.shutdown(wait=False)


# ===========================================================================
# 3. Synchronous & Asynchronous Execution Modes
# ===========================================================================


def test_execute_job_separate_mode(tmp_path):
    service = ClipExportService(workspace_dir=tmp_path)
    source_file = tmp_path / "source.mp4"
    source_file.touch()

    req = ClipExportRequest(
        request_id="req_sep_1",
        video_id="test_vid",
        video_title="My Test Video",
        clips=[
            ClipItem(id="c1", name="Intro", start=0.0, end=10.0),
            ClipItem(id="c2", name="Middle", start=20.0, end=30.0),
        ],
        export_mode=ExportMode.SEPARATE,
        cut_mode=CutMode.STREAM_COPY,
    )

    events: list[ClipExportProgress] = []
    with (
        patch.object(service.downloader, "get_cached_source", return_value=source_file),
        patch.object(service.clip_engine, "trim_clip", side_effect=_fake_trim_clip),
    ):
        result = service.execute_job(req, progress_callback=events.append)
        assert result.status == "SUCCESS"
        assert len(result.files) == 2
        assert result.merged_file is None
        assert "clip_1" in result.files[0]
        assert "clip_2" in result.files[1]
        assert result.elapsed_seconds >= 0.0

        stages = [e.stage for e in events]
        assert ExportStage.PROBING in stages
        assert ExportStage.DOWNLOADING in stages
        assert ExportStage.TRIMMING in stages
        assert ExportStage.COMPLETE in stages
    service.shutdown(wait=False)


def test_execute_job_merged_mode(tmp_path):
    service = ClipExportService(workspace_dir=tmp_path)
    source_file = tmp_path / "source.mp4"
    source_file.touch()

    req = ClipExportRequest(
        request_id="req_merge_1",
        video_id="merge_vid",
        video_title="Merge Show",
        clips=[
            ClipItem(id="1", start=5.0, end=15.0),
            ClipItem(id="2", start=25.0, end=35.0),
        ],
        export_mode=ExportMode.MERGED,
    )

    events: list[ClipExportProgress] = []
    with (
        patch.object(service.downloader, "get_cached_source", return_value=source_file),
        patch.object(service.clip_engine, "trim_clip", side_effect=_fake_trim_clip),
        patch.object(service.clip_engine, "merge_clips", side_effect=_fake_merge_clips),
    ):
        result = service.execute_job(req, progress_callback=events.append)
        assert result.status == "SUCCESS"
        assert len(result.files) == 2
        assert result.merged_file is not None
        assert "selected_clips.mp4" in result.merged_file

        stages = [e.stage for e in events]
        assert ExportStage.MERGING in stages
        assert ExportStage.COMPLETE in stages
    service.shutdown(wait=False)


def test_execute_job_import_mode_single_clip(tmp_path):
    proj = Project()
    service = ClipExportService(workspace_dir=tmp_path, project=proj)
    source_file = tmp_path / "source.mp4"
    source_file.touch()

    req = ClipExportRequest(
        request_id="req_import_1",
        video_id="import_vid",
        video_title="Import Track",
        clips=[ClipItem(id="1", start=10.0, end=20.0)],
        export_mode=ExportMode.IMPORT,
    )

    with (
        patch.object(service.downloader, "get_cached_source", return_value=source_file),
        patch.object(service.clip_engine, "trim_clip", side_effect=_fake_trim_clip),
    ):
        result = service.execute_job(req)
        assert result.status == "SUCCESS"
        assert proj.video_path == Path(result.files[0])
    service.shutdown(wait=False)


def test_execute_job_import_mode_multiple_clips_merged(tmp_path):
    imported_target: list[Path] = []
    proj = Project()
    service = ClipExportService(
        workspace_dir=tmp_path,
        project=proj,
        import_handler=imported_target.append,
    )
    source_file = tmp_path / "source.mp4"
    source_file.touch()

    req = ClipExportRequest(
        request_id="req_import_multi",
        video_id="import_multi",
        video_title="Multi Import",
        clips=[
            ClipItem(id="1", start=0.0, end=10.0),
            ClipItem(id="2", start=15.0, end=25.0),
        ],
        export_mode=ExportMode.IMPORT,
    )

    with (
        patch.object(service.downloader, "get_cached_source", return_value=source_file),
        patch.object(service.clip_engine, "trim_clip", side_effect=_fake_trim_clip),
        patch.object(service.clip_engine, "merge_clips", side_effect=_fake_merge_clips),
    ):
        result = service.execute_job(req)
        assert result.status == "SUCCESS"
        assert result.merged_file is not None
        assert proj.video_path == Path(result.merged_file)
        assert len(imported_target) == 1
        assert imported_target[0] == Path(result.merged_file)
    service.shutdown(wait=False)


# ===========================================================================
# 4. Idempotency & Duplicate Request Tests
# ===========================================================================


def test_idempotent_duplicate_request_returns_existing_job(tmp_path):
    mock_agent = MagicMock(spec=LocalAgent)
    service = ClipExportService(workspace_dir=tmp_path, local_agent=mock_agent)
    source_file = tmp_path / "source.mp4"
    source_file.touch()

    req = ClipExportRequest(
        request_id="dup_req_123",
        video_id="dup_vid",
        video_title="Duplicate Video",
        clips=[ClipItem(id="1", start=0.0, end=10.0)],
        export_mode=ExportMode.SEPARATE,
    )

    with (
        patch.object(service.downloader, "get_cached_source", return_value=source_file),
        patch.object(service.clip_engine, "trim_clip", side_effect=_fake_trim_clip),
    ):
        # 1. Submit initial job
        job1 = service.submit_job(req)
        assert job1.request_id == "dup_req_123"

        # 2. Duplicate submission immediately
        job2 = service.submit_job(req)
        assert job1 is job2

        # Wait for completion
        if job1.future:
            job1.future.result(timeout=5.0)

        assert job1.status == JobStatus.SUCCESS

        # 3. Third submission after completion returns same job and re-sends result
        job3 = service.submit_job(req)
        assert job3 is job1
        assert mock_agent.send_clip_result.called
    service.shutdown(wait=False)


# ===========================================================================
# 5. Invalid Clips & Error Validation
# ===========================================================================


def test_submit_job_no_valid_clips_fails_gracefully(tmp_path):
    mock_agent = MagicMock(spec=LocalAgent)
    service = ClipExportService(workspace_dir=tmp_path, local_agent=mock_agent)

    req = ClipExportRequest(
        request_id="err_clips",
        video_id="vid_invalid",
        clips=[
            ClipItem(id="1", start=10.0, end=5.0),  # start > end
            ClipItem(id="2", start=20.0, end=20.0),  # start == end
            ClipItem(id="3", start=-5.0, end=10.0),  # negative
        ],
    )

    job = service.submit_job(req)
    assert job.status == JobStatus.ERROR
    assert "Không có đoạn clip hợp lệ" in (job.error or "")
    mock_agent.send_clip_error.assert_called_once()
    err = mock_agent.send_clip_error.call_args[0][0]
    assert err.status == "ERROR"
    service.shutdown(wait=False)


def test_download_failure_propagates_error_and_cleans_scratch(tmp_path):
    mock_agent = MagicMock(spec=LocalAgent)
    service = ClipExportService(workspace_dir=tmp_path, local_agent=mock_agent)

    req = ClipExportRequest(
        request_id="dl_err",
        video_id="dl_err_vid",
        video_url="https://youtube.com/watch?v=dl_err_vid",
        clips=[ClipItem(id="1", start=0.0, end=10.0)],
    )

    with (
        patch.object(service.downloader, "get_cached_source", return_value=None),
        patch.object(
            service.downloader, "download", side_effect=RuntimeError("yt-dlp 403 Forbidden")
        ),
    ):
        with pytest.raises(RuntimeError, match="403 Forbidden"):
            service.execute_job(req)

        job = service.get_job("dl_err")
        assert job is not None
        assert job.status == JobStatus.ERROR
        scratch = service.get_job_scratch_dir("dl_err")
        assert not scratch.exists()  # Scratch cleaned
        mock_agent.send_clip_error.assert_called_once()
    service.shutdown(wait=False)


def test_trim_failure_propagates_error(tmp_path):
    mock_agent = MagicMock(spec=LocalAgent)
    service = ClipExportService(workspace_dir=tmp_path, local_agent=mock_agent)
    source = tmp_path / "source.mp4"
    source.touch()

    req = ClipExportRequest(
        request_id="trim_err",
        video_id="trim_err_vid",
        clips=[ClipItem(id="1", start=0.0, end=10.0)],
    )

    with (
        patch.object(service.downloader, "get_cached_source", return_value=source),
        patch.object(
            service.clip_engine, "trim_clip", side_effect=RuntimeError("FFmpeg decode error")
        ),
    ):
        with pytest.raises(RuntimeError, match="FFmpeg decode error"):
            service.execute_job(req)

        job = service.get_job("trim_err")
        assert job is not None
        assert job.status == JobStatus.ERROR
        mock_agent.send_clip_error.assert_called_once()
    service.shutdown(wait=False)


# ===========================================================================
# 6. Cancellation & Process Tree Termination
# ===========================================================================


def test_cancel_job_by_request_id_kills_process_tree(tmp_path):
    mock_agent = MagicMock(spec=LocalAgent)
    service = ClipExportService(workspace_dir=tmp_path, local_agent=mock_agent)

    req = ClipExportRequest(
        request_id="cancel_test_1",
        job_id="job_cancel_1",
        video_id="vid_cancel",
        clips=[ClipItem(id="1", start=0.0, end=10.0)],
    )

    mock_proc = MagicMock(spec=subprocess.Popen)
    mock_proc.pid = 9876

    with patch("vkdub.services.clip_export_service.kill_process_tree") as mock_kill:
        job = service.submit_job(req)
        job.set_active_process(mock_proc)

        cancelled = service.cancel_job(request_id="cancel_test_1")
        assert cancelled is True
        assert job.status == JobStatus.CANCELLED
        assert job.is_cancelled is True
        mock_kill.assert_called_once_with(9876)
    service.shutdown(wait=False)


def test_cancel_job_by_job_id(tmp_path):
    service = ClipExportService(workspace_dir=tmp_path)
    req = ClipExportRequest(
        request_id="req_cid",
        job_id="custom_job_id",
        clips=[ClipItem(id="1", start=0.0, end=10.0)],
    )
    job = service.submit_job(req)
    assert service.cancel_job(job_id="custom_job_id") is True
    assert job.status == JobStatus.CANCELLED
    service.shutdown(wait=False)


def test_cancel_during_execution_cleans_scratch_and_files(tmp_path):
    mock_agent = MagicMock(spec=LocalAgent)
    service = ClipExportService(workspace_dir=tmp_path, local_agent=mock_agent)
    source = tmp_path / "source.mp4"
    source.touch()

    req = ClipExportRequest(
        request_id="cancel_mid_run",
        video_id="mid_vid",
        clips=[
            ClipItem(id="1", start=0.0, end=10.0),
            ClipItem(id="2", start=20.0, end=30.0),
        ],
    )

    def trim_with_cancel(*args, **kwargs):
        service.cancel_job(request_id="cancel_mid_run")
        raise JobCancelledError("Tiến trình xuất clip đã bị hủy bởi người dùng.")

    with (
        patch.object(service.downloader, "get_cached_source", return_value=source),
        patch.object(service.clip_engine, "trim_clip", side_effect=trim_with_cancel),
    ):
        with pytest.raises(JobCancelledError):
            service.execute_job(req)

        job = service.get_job("cancel_mid_run")
        assert job is not None
        assert job.status == JobStatus.CANCELLED
        assert not service.get_job_scratch_dir("cancel_mid_run").exists()
        mock_agent.send_clip_error.assert_called_once()
        err = mock_agent.send_clip_error.call_args[0][0]
        assert err.status == "CANCELLED"
    service.shutdown(wait=False)


# ===========================================================================
# 7. Realtime Telemetry Streaming & Progress Listeners
# ===========================================================================


def test_progress_listeners_receive_events(tmp_path):
    service = ClipExportService(workspace_dir=tmp_path)
    source = tmp_path / "source.mp4"
    source.touch()

    req = ClipExportRequest(
        request_id="listener_test",
        video_id="listener_vid",
        clips=[ClipItem(id="1", start=0.0, end=5.0)],
        export_mode=ExportMode.SEPARATE,
    )

    received: list[ClipExportProgress] = []
    service.add_progress_listener(received.append)

    with (
        patch.object(service.downloader, "get_cached_source", return_value=source),
        patch.object(service.clip_engine, "trim_clip", side_effect=_fake_trim_clip),
    ):
        res = service.execute_job(req)
        assert res.status == "SUCCESS"
        assert len(received) >= 3
        stages = [p.stage for p in received]
        assert ExportStage.PROBING in stages
        assert ExportStage.COMPLETE in stages

    service.remove_progress_listener(received.append)
    service.shutdown(wait=False)


def test_download_progress_scaling_and_remux_event(tmp_path):
    mock_agent = MagicMock(spec=LocalAgent)
    service = ClipExportService(workspace_dir=tmp_path, local_agent=mock_agent)

    req = ClipExportRequest(
        request_id="dl_stream_test",
        video_id="stream_vid",
        clips=[ClipItem(id="1", start=0.0, end=5.0)],
    )

    def fake_download(**kwargs):
        cb = kwargs.get("progress_callback")
        if cb:
            cb(
                {
                    "stage": "DOWNLOADING",
                    "percent": 50.0,
                    "speed": "10MB/s",
                    "message": "Downloading 50%",
                }
            )
            cb({"stage": "REMUXING", "percent": 100.0, "speed": "", "message": "Merging"})
        out = tmp_path / "downloaded.mp4"
        out.touch()
        return out

    with (
        patch.object(service.downloader, "get_cached_source", return_value=None),
        patch.object(service.downloader, "download", side_effect=fake_download),
        patch.object(service.clip_engine, "trim_clip", side_effect=_fake_trim_clip),
    ):
        res = service.execute_job(req)
        assert res.status == "SUCCESS"

        calls = mock_agent.send_clip_progress.call_args_list
        stages = [call[0][0].stage for call in calls]
        assert ExportStage.DOWNLOADING in stages
        assert ExportStage.REMUXING in stages
        assert ExportStage.TRIMMING in stages
        assert ExportStage.COMPLETE in stages
    service.shutdown(wait=False)


def test_long_video_downloads_only_selected_time_range(tmp_path):
    """A short clip from a long video must not trigger a full-source download."""
    service = ClipExportService(workspace_dir=tmp_path)
    req = ClipExportRequest(
        request_id="partial_range",
        video_id="long_video",
        video_url="https://www.youtube.com/watch?v=long_video",
        video_title="Long video",
        duration=5400.0,
        clips=[ClipItem(id="one_minute", start=1800.0, end=1860.0)],
        quality="best",
        container="mp4",
    )
    downloaded = tmp_path / "selected_section.mp4"
    downloaded.write_bytes(b"section")

    with (
        patch.object(service.downloader, "get_cached_source", return_value=None),
        patch.object(service.downloader, "download", return_value=downloaded) as download_mock,
        patch.object(service.clip_engine, "trim_clip") as trim_mock,
    ):
        result = service.execute_job(req)

    kwargs = download_mock.call_args.kwargs
    assert kwargs["section_start"] == 1800.0
    assert kwargs["section_end"] == 1860.0
    assert kwargs["quality"] == "best"
    assert kwargs["prefer_segmented"] is True
    assert result.success is True
    assert Path(result.files[0]).read_bytes() == b"section"
    trim_mock.assert_not_called()
    service.shutdown(wait=False)


# ===========================================================================
# 8. LocalAgent Signal / Action Routing Tests
# ===========================================================================


def test_handle_clip_export_and_cancel_requests_from_dict(tmp_path):
    mock_agent = MagicMock(spec=LocalAgent)
    service = ClipExportService(workspace_dir=tmp_path, local_agent=mock_agent)

    payload = {
        "requestId": "dict_req_1",
        "jobId": "dict_job_1",
        "videoId": "dict_vid",
        "videoTitle": "Dict Video",
        "clips": [{"id": "1", "start": 0.0, "end": 10.0, "selected": True}],
        "exportMode": "SEPARATE",
    }

    job = service.handle_clip_export_request(payload)
    assert job.request_id == "dict_req_1"
    assert job.status in (JobStatus.QUEUED, JobStatus.RUNNING)

    cancel_payload = {"requestId": "dict_req_1", "jobId": "dict_job_1"}
    cancelled = service.handle_clip_cancel_request(cancel_payload)
    assert cancelled is True
    assert job.status == JobStatus.CANCELLED
    service.shutdown(wait=False)


def test_handle_clip_cancel_request_object(tmp_path):
    service = ClipExportService(workspace_dir=tmp_path)
    req = ClipExportRequest(request_id="obj_req", clips=[ClipItem(id="1", start=0.0, end=5.0)])
    job = service.submit_job(req)

    cancel_obj = ClipExportCancel(request_id="obj_req", job_id="obj_req")
    assert service.handle_clip_cancel_request(cancel_obj) is True
    assert job.status == JobStatus.CANCELLED
    service.shutdown(wait=False)


def test_import_completed_result_updates_project(tmp_path):
    project = Project()
    service = ClipExportService(workspace_dir=tmp_path, project=project)
    clip = tmp_path / "exports" / "clips" / "ready.mp4"
    clip.parent.mkdir(parents=True, exist_ok=True)
    clip.touch()

    response = service.handle_clip_import_request({"file_path": str(clip)})

    assert response["success"] is True
    assert project.video_path == clip.resolve()
    service.shutdown(wait=False)


def test_import_completed_result_rejects_non_media(tmp_path):
    service = ClipExportService(workspace_dir=tmp_path)
    text_file = tmp_path / "not-media.txt"
    text_file.write_text("no", encoding="utf-8")

    with pytest.raises(ValueError, match="không được ToolVideo hỗ trợ"):
        service.handle_clip_import_request({"file_path": str(text_file)})
    service.shutdown(wait=False)


# ===========================================================================
# 9. Asynchronous Concurrent Queue Tests
# ===========================================================================


def test_multiple_concurrent_jobs_queued_and_completed(tmp_path):
    service = ClipExportService(workspace_dir=tmp_path, max_workers=2)
    source = tmp_path / "source.mp4"
    source.touch()

    jobs = []
    with (
        patch.object(service.downloader, "get_cached_source", return_value=source),
        patch.object(service.clip_engine, "trim_clip", side_effect=_fake_trim_clip),
    ):
        for i in range(3):
            req = ClipExportRequest(
                request_id=f"concurrent_job_{i}",
                video_id=f"vid_{i}",
                clips=[ClipItem(id="1", start=float(i), end=float(i + 5))],
            )
            jobs.append(service.submit_job(req))

        for j in jobs:
            if j.future:
                j.future.result(timeout=5.0)
            assert j.status == JobStatus.SUCCESS
            assert j.result is not None

        all_tracked = service.list_jobs()
        assert len(all_tracked) >= 3
    service.shutdown(wait=False)
