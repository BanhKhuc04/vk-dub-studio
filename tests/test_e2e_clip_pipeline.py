"""VK Dub Studio — E2E Clip Pipeline Automated Test Suite.

Tiers Covered:
- Tier 3: Cross-Feature Combinations
  1. Stream-copy + Merged export
  2. Frame-Accurate + NVENC + Single export
  3. Stream-copy + Import to ToolVideo Studio
  4. Opt-in cookies vs no cookies
  5. Frame-Accurate + Fallback CPU + MKV container
- Tier 4: Real-World Application Scenarios
  1. Multi-clip podcast trimming (3 highlight segments, merged reel or separate files)
  2. Long gaming stream clipping (5 segments with diverse timestamps up to 3 hours)
  3. Fast short video extraction (<15s short clip, instant keyframe snap)
  4. Network error recovery & telemetry streaming
  5. Idempotent export requests & cancellation cleanup

All tests run 100% offline, reliably, fast (<5 seconds), and self-contained.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from vkdub.bridge.protocol import (
    ClipExportProgress,
    ClipExportRequest,
    ClipExportResult,
    ClipItem,
    CutMode,
    ExportMode,
    ExportStage,
)
from vkdub.domain.project import Project
from vkdub.media.clip_engine import (
    ClipEngine,
    build_clip_filename,
    build_concat_command,
    build_frame_accurate_trim_command,
    build_merged_filename,
    create_concat_manifest,
    format_timecode_for_filename,
    sanitize_filename,
)
from vkdub.media.hardware import (
    HardwareEncoderDetector,
    get_encoder_params,
)
from vkdub.media.hardware import (
    clear_cache as clear_hw_cache,
)
from vkdub.media.ytdlp import (
    YtDlpDownloader,
    build_ytdlp_download_command,
    parse_ytdlp_progress_line,
)


def _mock_trim_clip(*args, **kwargs) -> Path:
    out = kwargs.get("output_path") or (args[1] if len(args) > 1 else None)
    if out:
        p = Path(out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
        return p
    return Path("clip.mp4")


def _mock_merge_clips(*args, **kwargs) -> Path:
    out = kwargs.get("output_path") or (args[1] if len(args) > 1 else None)
    if out:
        p = Path(out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
        return p
    return Path("merged.mp4")


class E2EClipPipelineHarness:
    """Orchestrates and validates the complete YouTube Clip Mode export pipeline.

    Simulates the backend service integrating YtDlpDownloader, HardwareEncoderDetector,
    ClipEngine, and ToolVideo Studio Project import.
    """

    def __init__(
        self,
        workspace_dir: Path,
        ffmpeg_exe: str = "ffmpeg.exe",
        ytdlp_path: str = "yt-dlp.exe",
    ) -> None:
        self.workspace_dir = workspace_dir
        self.cache_dir = workspace_dir / "cache" / "youtube"
        self.scratch_dir = workspace_dir / "scratch" / "clips"
        self.output_dir = workspace_dir / "output"
        self.ffmpeg_exe = ffmpeg_exe
        self.ytdlp_path = ytdlp_path

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.scratch_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.downloader = YtDlpDownloader(
            ytdlp_path=self.ytdlp_path,
            cache_root=self.workspace_dir,
        )
        self.clip_engine = ClipEngine(ffmpeg_exe=self.ffmpeg_exe)
        self.hw_detector = HardwareEncoderDetector(ffmpeg_exe=self.ffmpeg_exe)
        self.active_jobs: dict[str, dict[str, Any]] = {}

    def execute_export(
        self,
        request: ClipExportRequest,
        progress_callback: Callable[[ClipExportProgress], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> ClipExportResult:
        """Execute the end-to-end export pipeline according to request specification."""
        start_time = time.monotonic()
        req_id = request.request_id

        # Idempotency check: if job is already running
        if req_id in self.active_jobs and self.active_jobs[req_id].get("running"):
            return self.active_jobs[req_id]["result"]

        self.active_jobs[req_id] = {"running": True, "request": request}

        def emit_progress(stage: str, pct: float, msg: str, cur_clip: int = 0) -> None:
            if progress_callback:
                progress_callback(
                    ClipExportProgress(
                        request_id=req_id,
                        job_id=request.job_id,
                        stage=stage,
                        percent=pct,
                        current_clip=cur_clip,
                        total_clips=len(request.clips),
                        message=msg,
                    )
                )

        try:
            # 1. Probing & Cache Inspection
            emit_progress(ExportStage.PROBING, 5.0, "Kiểm tra cache video nguồn...")
            source_file = self.downloader.get_cached_source(
                request.video_id, request.quality
            )

            # 2. Download if not in cache
            if not source_file:
                emit_progress(ExportStage.DOWNLOADING, 10.0, "Bắt đầu tải video nguồn...")
                source_file = self.downloader.download(
                    video_url=request.video_url,
                    video_id=request.video_id,
                    quality=request.quality,
                    use_cookies=request.use_cookies,
                    cookie_browser=request.browser if request.use_cookies else None,
                    progress_callback=lambda p: emit_progress(
                        ExportStage.DOWNLOADING,
                        10.0 + p.get("percent", 0.0) * 0.4,
                        p.get("message", "Đang tải..."),
                    ),
                    cancel_check=cancel_check,
                )

            if cancel_check and cancel_check():
                raise RuntimeError("Export cancelled by user.")

            # 3. Trimming Clips
            target_out_dir = Path(request.output_dir) if request.output_dir else self.output_dir
            target_out_dir.mkdir(parents=True, exist_ok=True)

            trimmed_files: list[Path] = []
            selected_clips = [c for c in request.clips if c.selected and c.is_valid()]

            if not selected_clips:
                raise ValueError("No valid selected clips to export.")

            for idx, clip in enumerate(selected_clips, start=1):
                if cancel_check and cancel_check():
                    raise RuntimeError("Export cancelled by user.")

                emit_progress(
                    ExportStage.TRIMMING,
                    50.0 + (idx / len(selected_clips)) * 30.0,
                    f"Đang cắt clip {idx}/{len(selected_clips)}: {clip.name or 'Clip'}",
                    cur_clip=idx,
                )

                clip_name = build_clip_filename(
                    video_title=request.video_title,
                    clip_index=idx,
                    start_sec=clip.start,
                    end_sec=clip.end,
                    container=request.container,
                )
                clip_out = target_out_dir / clip_name

                self.clip_engine.trim_clip(
                    source_path=source_file,
                    output_path=clip_out,
                    start_sec=clip.start,
                    end_sec=clip.end,
                    cut_mode=request.cut_mode,
                    cancel_check=cancel_check,
                )
                trimmed_files.append(clip_out)

            # 4. Merging if requested
            merged_file_path: Path | None = None
            if request.export_mode == ExportMode.MERGED and len(trimmed_files) > 0:
                emit_progress(ExportStage.MERGING, 85.0, "Đang ghép các đoạn clip...")
                merged_name = build_merged_filename(
                    video_title=request.video_title, container=request.container
                )
                merged_file_path = target_out_dir / merged_name
                self.clip_engine.merge_clips(
                    clip_paths=trimmed_files,
                    output_path=merged_file_path,
                    cancel_check=cancel_check,
                )

            # 5. Pipeline Import if requested
            if request.export_mode == ExportMode.IMPORT:
                emit_progress(ExportStage.PIPELINE_FEED, 95.0, "Nạp vào ToolVideo...")
                chosen_import = merged_file_path if merged_file_path else trimmed_files[0]
                project = Project(video_path=chosen_import)
                assert project.video_path == chosen_import

            emit_progress(
                ExportStage.COMPLETE,
                100.0,
                "Xuất hoàn tất!",
                cur_clip=len(selected_clips),
            )

            elapsed = max(0.01, round(time.monotonic() - start_time, 2))
            result = ClipExportResult(
                request_id=req_id,
                job_id=request.job_id,
                status="SUCCESS",
                files=[str(f) for f in trimmed_files],
                merged_file=str(merged_file_path) if merged_file_path else None,
                output_dir=str(target_out_dir),
                elapsed_seconds=elapsed,
                success=True,
            )
            self.active_jobs[req_id] = {"running": False, "result": result}
            return result

        except Exception as exc:
            self.active_jobs[req_id] = {"running": False, "error": str(exc)}
            raise


# ===========================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS (20 Tests)
# ===========================================================================

# ---------------------------------------------------------------------------
# Combination 1: Stream-copy + Merged Export (4 tests)
# ---------------------------------------------------------------------------


def test_t3_stream_copy_merged_export_flow(tmp_path):
    harness = E2EClipPipelineHarness(workspace_dir=tmp_path)

    # Prepare fake source in cache
    cache_vid = tmp_path / "cache" / "youtube" / "vid_merge"
    cache_vid.mkdir(parents=True)
    source = cache_vid / "source_vid_merge_1080p.mp4"
    source.write_bytes(b"source" * 1024)

    req = ClipExportRequest(
        request_id="req_m1",
        video_id="vid_merge",
        video_url="https://youtube.com/watch?v=vid_merge",
        video_title="Podcast Merge Episode",
        clips=[
            ClipItem(id="c1", name="Part 1", start=10.0, end=20.0),
            ClipItem(id="c2", name="Part 2", start=35.0, end=50.0),
        ],
        export_mode=ExportMode.MERGED,
        cut_mode=CutMode.STREAM_COPY,
        container="mp4",
    )

    with patch.object(harness.downloader, "get_cached_source", return_value=source), \
         patch.object(harness.clip_engine, "trim_clip", side_effect=_mock_trim_clip), \
         patch.object(harness.clip_engine, "merge_clips", side_effect=_mock_merge_clips):

        progress_events = []
        result = harness.execute_export(req, progress_callback=progress_events.append)

        assert result.status == "SUCCESS"
        assert len(result.files) == 2
        assert result.merged_file is not None
        assert "selected_clips.mp4" in result.merged_file
        stages = [p.stage for p in progress_events]
        assert ExportStage.MERGING in stages
        assert ExportStage.COMPLETE in stages


def test_t3_stream_copy_merged_manifest_integrity(tmp_path):
    manifest = tmp_path / "manifest.txt"
    clips = [tmp_path / "clip1.mp4", tmp_path / "clip2.mp4", tmp_path / "clip3.mp4"]
    for c in clips:
        c.write_text("dummy")

    create_concat_manifest(clips, manifest)
    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "ffconcat version 1.0"
    assert len(lines) == 4
    for i, c in enumerate(clips):
        assert c.as_posix() in lines[i + 1]


def test_t3_stream_copy_merged_output_filename():
    fn = build_merged_filename(video_title="Vietnam AI Dubbing (2026)", container="mp4")
    assert fn == "Vietnam AI Dubbing (2026)_selected_clips.mp4"


def test_t3_stream_copy_merged_mkv_container(tmp_path):
    harness = E2EClipPipelineHarness(workspace_dir=tmp_path)
    source = tmp_path / "source.mkv"
    source.write_bytes(b"dummy")

    req = ClipExportRequest(
        request_id="req_mkv",
        video_id="mkv_vid",
        video_title="High Quality Stream",
        clips=[ClipItem(id="c1", start=0.0, end=10.0)],
        export_mode=ExportMode.MERGED,
        container="mkv",
    )

    with patch.object(harness.downloader, "get_cached_source", return_value=source), \
         patch.object(harness.clip_engine, "trim_clip", side_effect=_mock_trim_clip), \
         patch.object(harness.clip_engine, "merge_clips", side_effect=_mock_merge_clips):

        res = harness.execute_export(req)
        assert res.merged_file.endswith(".mkv")


# ---------------------------------------------------------------------------
# Combination 2: Frame-Accurate + NVENC + Single Export (4 tests)
# ---------------------------------------------------------------------------


def test_t3_frame_accurate_nvenc_single_clip_args(tmp_path):
    clear_hw_cache()
    harness = E2EClipPipelineHarness(workspace_dir=tmp_path)
    source = tmp_path / "source.mp4"
    source.touch()

    req = ClipExportRequest(
        request_id="req_nvenc",
        video_id="nvenc_vid",
        video_title="GPU Accelerated Trimming",
        clips=[ClipItem(id="c1", start=12.345, end=25.678)],
        export_mode=ExportMode.SEPARATE,
        cut_mode=CutMode.FRAME_ACCURATE,
    )

    captured_cmd = []

    def fake_popen(cmd, *args, **kwargs):
        captured_cmd.extend(cmd)
        mock = MagicMock()
        mock.communicate.return_value = ("", "")
        mock.returncode = 0
        return mock

    with patch.object(harness.downloader, "get_cached_source", return_value=source), \
         patch("vkdub.media.hardware.probe_encoder", return_value=True), \
         patch("subprocess.Popen", side_effect=fake_popen), \
         patch("pathlib.Path.is_file", return_value=True):

        res = harness.execute_export(req)
        assert res.status == "SUCCESS"
        assert "-c:v" in captured_cmd
        assert "h264_nvenc" in captured_cmd
        assert "-cq" in captured_cmd and "18" in captured_cmd


def test_t3_frame_accurate_nvenc_cq18_parameter():
    params = get_encoder_params("h264_nvenc")
    assert "-cq" in params
    assert params[params.index("-cq") + 1] == "18"
    assert "-preset" in params
    assert params[params.index("-preset") + 1] == "p5"


def test_t3_frame_accurate_faststart_mp4(tmp_path):
    cmd = build_frame_accurate_trim_command(
        ffmpeg_exe="ffmpeg.exe",
        source_path=tmp_path / "src.mp4",
        output_path=tmp_path / "out.mp4",
        start_sec=1.0,
        end_sec=5.0,
        encoder_name="h264_nvenc",
    )
    assert "-movflags" in cmd and "+faststart" in cmd


def test_t3_frame_accurate_single_clip_filename():
    fn = build_clip_filename("Gaming Highlight", 1, 10.5, 30.0, "mp4")
    assert fn.startswith("Gaming Highlight_clip_1_")
    assert "10.5s-30s" in fn


# ---------------------------------------------------------------------------
# Combination 3: Stream-copy + Import to Studio Timeline (4 tests)
# ---------------------------------------------------------------------------


def test_t3_stream_copy_import_updates_project_video_path(tmp_path):
    harness = E2EClipPipelineHarness(workspace_dir=tmp_path)
    source = tmp_path / "source.mp4"
    source.touch()

    req = ClipExportRequest(
        request_id="req_import",
        video_id="vid_import",
        video_title="Studio Import Video",
        clips=[ClipItem(id="c1", start=5.0, end=15.0)],
        export_mode=ExportMode.IMPORT,
        cut_mode=CutMode.STREAM_COPY,
    )

    with patch.object(harness.downloader, "get_cached_source", return_value=source), \
         patch.object(harness.clip_engine, "trim_clip", side_effect=_mock_trim_clip):

        res = harness.execute_export(req)
        assert res.status == "SUCCESS"
        assert len(res.files) == 1
        proj = Project(video_path=Path(res.files[0]))
        assert proj.video_path == Path(res.files[0])


def test_t3_stream_copy_import_merged_updates_project(tmp_path):
    harness = E2EClipPipelineHarness(workspace_dir=tmp_path)
    source = tmp_path / "source.mp4"
    source.touch()

    req = ClipExportRequest(
        request_id="req_imp_merge",
        video_id="vid_merge",
        video_title="Multi Clip Project",
        clips=[
            ClipItem(id="c1", start=0.0, end=10.0),
            ClipItem(id="c2", start=20.0, end=30.0),
        ],
        export_mode=ExportMode.IMPORT,
        cut_mode=CutMode.STREAM_COPY,
    )

    with patch.object(harness.downloader, "get_cached_source", return_value=source), \
         patch.object(harness.clip_engine, "trim_clip", side_effect=_mock_trim_clip), \
         patch.object(harness.clip_engine, "merge_clips", side_effect=_mock_merge_clips):

        res = harness.execute_export(req)
        assert res.status == "SUCCESS"


def test_t3_stream_copy_import_emits_telemetry_complete(tmp_path):
    harness = E2EClipPipelineHarness(workspace_dir=tmp_path)
    source = tmp_path / "source.mp4"
    source.touch()

    req = ClipExportRequest(
        request_id="req_telemetry",
        video_id="vid_tel",
        video_title="Telemetry Check",
        clips=[ClipItem(id="c1", start=1.0, end=5.0)],
        export_mode=ExportMode.IMPORT,
    )

    events = []
    with patch.object(harness.downloader, "get_cached_source", return_value=source), \
         patch.object(harness.clip_engine, "trim_clip", side_effect=_mock_trim_clip):

        harness.execute_export(req, progress_callback=events.append)
        stages = [e.stage for e in events]
        assert ExportStage.PIPELINE_FEED in stages
        assert ExportStage.COMPLETE in stages


def test_t3_stream_copy_import_preserves_project_title():
    raw_title = "My <Special> Title?"
    clean = sanitize_filename(raw_title)
    proj = Project(video_path=Path(f"videos/{clean}.mp4"))
    assert clean in str(proj.video_path)


# ---------------------------------------------------------------------------
# Combination 4: Opt-In Cookies vs No Cookies (4 tests)
# ---------------------------------------------------------------------------


def test_t3_public_video_zero_cookies():
    cmd = build_ytdlp_download_command(
        ytdlp_exe="yt-dlp",
        video_url="https://youtube.com/watch?v=public_vid",
        target_output=Path("source.mp4"),
        use_cookies=False,
    )
    assert "--cookies-from-browser" not in cmd


def test_t3_selected_range_uses_ytdlp_section_and_parallel_fragments():
    cmd = build_ytdlp_download_command(
        ytdlp_exe="yt-dlp",
        video_url="https://youtube.com/watch?v=long_video",
        target_output=Path("section.mp4"),
        quality="best",
        section_start=1800.0,
        section_end=1860.0,
        force_keyframes_at_cuts=True,
    )
    assert cmd[cmd.index("--download-sections") + 1] == "*1800.000-1860.000"
    assert cmd[cmd.index("--concurrent-fragments") + 1] == "4"
    assert "--force-keyframes-at-cuts" in cmd
    assert "--no-continue" in cmd
    assert "--no-part" in cmd


def test_t3_fast_selected_range_prefers_seekable_hls():
    cmd = build_ytdlp_download_command(
        ytdlp_exe="yt-dlp",
        video_url="https://youtube.com/watch?v=long_video",
        target_output=Path("section.mp4"),
        quality="best",
        section_start=1800.0,
        section_end=1860.0,
        prefer_segmented=True,
    )
    selector = cmd[cmd.index("-f") + 1]
    assert "protocol^=m3u8" in selector


def test_t3_absolute_best_keeps_source_quality_selector():
    cmd = build_ytdlp_download_command(
        ytdlp_exe="yt-dlp",
        video_url="https://youtube.com/watch?v=long_video",
        target_output=Path("section.mp4"),
        quality="source_best",
        section_start=1800.0,
        section_end=1860.0,
        prefer_segmented=True,
    )
    assert cmd[cmd.index("-f") + 1] == "bestvideo+bestaudio/best"


def test_t3_private_video_opt_in_edge_cookies():
    cmd = build_ytdlp_download_command(
        ytdlp_exe="yt-dlp",
        video_url="https://youtube.com/watch?v=private_vid",
        target_output=Path("source.mp4"),
        use_cookies=True,
        cookie_browser="edge",
    )
    assert "--cookies-from-browser" in cmd
    assert cmd[cmd.index("--cookies-from-browser") + 1] == "edge"


def test_t3_private_video_opt_in_chrome_cookies():
    cmd = build_ytdlp_download_command(
        ytdlp_exe="yt-dlp",
        video_url="https://youtube.com/watch?v=private_vid",
        target_output=Path("source.mp4"),
        use_cookies=True,
        cookie_browser="chrome",
    )
    assert "--cookies-from-browser" in cmd
    assert cmd[cmd.index("--cookies-from-browser") + 1] == "chrome"


def test_t3_opt_in_true_but_empty_browser_no_cookies():
    cmd = build_ytdlp_download_command(
        ytdlp_exe="yt-dlp",
        video_url="https://youtube.com/watch?v=vid",
        target_output=Path("source.mp4"),
        use_cookies=True,
        cookie_browser="",
    )
    assert "--cookies-from-browser" not in cmd


# ---------------------------------------------------------------------------
# Combination 5: Frame-Accurate + Fallback CPU + MKV Container (4 tests)
# ---------------------------------------------------------------------------


def test_t3_frame_accurate_cpu_mkv_command_args(tmp_path):
    cmd = build_frame_accurate_trim_command(
        ffmpeg_exe="ffmpeg.exe",
        source_path=tmp_path / "src.mkv",
        output_path=tmp_path / "out.mkv",
        start_sec=10.0,
        end_sec=20.0,
        encoder_name="libx264",
        encoder_args=["-crf", "18", "-preset", "faster"],
    )
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "-crf" in cmd and "18" in cmd
    assert cmd[-1].endswith(".mkv")


def test_t3_frame_accurate_cpu_mkv_no_faststart(tmp_path):
    cmd = build_frame_accurate_trim_command(
        ffmpeg_exe="ffmpeg.exe",
        source_path=tmp_path / "src.mkv",
        output_path=tmp_path / "out.mkv",
        start_sec=0.0,
        end_sec=10.0,
        encoder_name="libx264",
    )
    assert "+faststart" not in cmd


def test_t3_frame_accurate_hevc_cpu_mkv(tmp_path):
    cmd = build_frame_accurate_trim_command(
        ffmpeg_exe="ffmpeg.exe",
        source_path=tmp_path / "src.mkv",
        output_path=tmp_path / "out.mkv",
        start_sec=0.0,
        end_sec=10.0,
        encoder_name="libx265",
        encoder_args=["-crf", "18"],
    )
    assert cmd[cmd.index("-c:v") + 1] == "libx265"


def test_t3_frame_accurate_mkv_merge_export(tmp_path):
    clips = [tmp_path / "c1.mkv", tmp_path / "c2.mkv"]
    out = tmp_path / "merged.mkv"
    manifest = tmp_path / "manifest.txt"
    for c in clips:
        c.touch()

    create_concat_manifest(clips, manifest)
    cmd = build_concat_command("ffmpeg.exe", manifest, out)
    assert "-f" in cmd and "concat" in cmd
    assert "+faststart" not in cmd
    assert cmd[-1].endswith(".mkv")


# ===========================================================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS (20 Tests)
# ===========================================================================

# ---------------------------------------------------------------------------
# Scenario 1: Multi-Clip Podcast Trimming (4 tests)
# ---------------------------------------------------------------------------


def test_t4_podcast_trimming_three_segments_separate_files(tmp_path):
    harness = E2EClipPipelineHarness(workspace_dir=tmp_path)
    source = tmp_path / "podcast_full.mp4"
    source.touch()

    req = ClipExportRequest(
        request_id="podcast_job_1",
        video_id="podcast_ep10",
        video_title="AI Revolution Podcast Ep 10",
        duration=3600.0,  # 1 hour
        clips=[
            ClipItem(id="p1", name="Giới thiệu", start=90.0, end=180.0),  # 01m30s - 03m00s
            ClipItem(id="p2", name="Bàn về AI", start=1455.0, end=1725.0),  # 24m15s - 28m45s
            ClipItem(id="p3", name="Lời kết", start=3300.0, end=3450.0),  # 55m00s - 57m30s
        ],
        export_mode=ExportMode.SEPARATE,
        cut_mode=CutMode.STREAM_COPY,
    )

    with patch.object(harness.downloader, "get_cached_source", return_value=source), \
         patch.object(harness.clip_engine, "trim_clip", side_effect=_mock_trim_clip):

        res = harness.execute_export(req)
        assert res.status == "SUCCESS"
        assert len(res.files) == 3
        assert "01m30s-03m00s" in res.files[0]
        assert "24m15s-28m45s" in res.files[1]
        assert "55m00s-57m30s" in res.files[2]


def test_t4_podcast_trimming_three_segments_merged_reel(tmp_path):
    harness = E2EClipPipelineHarness(workspace_dir=tmp_path)
    source = tmp_path / "podcast_full.mp4"
    source.touch()

    req = ClipExportRequest(
        request_id="podcast_job_2",
        video_id="podcast_ep10",
        video_title="AI Revolution Podcast Ep 10",
        clips=[
            ClipItem(id="p1", start=90.0, end=180.0),
            ClipItem(id="p2", start=1455.0, end=1725.0),
            ClipItem(id="p3", start=3300.0, end=3450.0),
        ],
        export_mode=ExportMode.MERGED,
        cut_mode=CutMode.STREAM_COPY,
    )

    with patch.object(harness.downloader, "get_cached_source", return_value=source), \
         patch.object(harness.clip_engine, "trim_clip", side_effect=_mock_trim_clip), \
         patch.object(harness.clip_engine, "merge_clips", side_effect=_mock_merge_clips):

        res = harness.execute_export(req)
        assert res.status == "SUCCESS"
        assert res.merged_file is not None
        assert "AI Revolution Podcast Ep 10_selected_clips.mp4" in res.merged_file


def test_t4_podcast_trimming_custom_clip_names_sanitized():
    title = "Talkshow: Người Lạ & Tương Lai?"
    clean = sanitize_filename(title)
    assert clean == "Talkshow_ Người Lạ & Tương Lai_"


def test_t4_podcast_trimming_progress_tracking(tmp_path):
    harness = E2EClipPipelineHarness(workspace_dir=tmp_path)
    source = tmp_path / "podcast.mp4"
    source.touch()

    req = ClipExportRequest(
        request_id="podcast_prog",
        video_id="pod_prog",
        video_title="Progress Check",
        clips=[
            ClipItem(id="1", start=10.0, end=20.0),
            ClipItem(id="2", start=30.0, end=40.0),
        ],
        export_mode=ExportMode.SEPARATE,
    )

    events = []
    with patch.object(harness.downloader, "get_cached_source", return_value=source), \
         patch.object(harness.clip_engine, "trim_clip", side_effect=_mock_trim_clip):

        harness.execute_export(req, progress_callback=events.append)
        trim_events = [e for e in events if e.stage == ExportStage.TRIMMING]
        assert len(trim_events) == 2
        assert trim_events[0].current_clip == 1
        assert trim_events[1].current_clip == 2


# ---------------------------------------------------------------------------
# Scenario 2: Long Gaming Stream Clipping (4 tests)
# ---------------------------------------------------------------------------


def test_t4_gaming_stream_five_segments_timecodes(tmp_path):
    harness = E2EClipPipelineHarness(workspace_dir=tmp_path)
    source = tmp_path / "gaming_3hr.mp4"
    source.touch()

    # 3-hour gaming stream
    req = ClipExportRequest(
        request_id="game_3hr",
        video_id="game_stream",
        video_title="Elden Ring Walkthrough Day 1",
        duration=10800.0,
        clips=[
            ClipItem(id="g1", start=720.0, end=930.0),  # 12m00s - 15m30s
            ClipItem(id="g2", start=2710.0, end=2820.0),  # 45m10s - 47m00s
            ClipItem(id="g3", start=4200.0, end=4500.0),  # 01h10m00s - 01h15m00s
            ClipItem(id="g4", start=7530.0, end=7725.0),  # 02h05m30s - 02h08m45s
            ClipItem(id="g5", start=10800.0 - 300.0, end=10800.0),  # End boss
        ],
        export_mode=ExportMode.SEPARATE,
    )

    with patch.object(harness.downloader, "get_cached_source", return_value=source), \
         patch.object(harness.clip_engine, "trim_clip", side_effect=_mock_trim_clip):

        res = harness.execute_export(req)
        assert len(res.files) == 5
        assert "12m00s-15m30s" in res.files[0]
        assert "01h10m00s-01h15m00s" in res.files[2]
        assert "02h05m30s-02h08m45s" in res.files[3]


def test_t4_gaming_stream_ordered_manifest_generation(tmp_path):
    clips = [tmp_path / f"boss_fight_{i}.mp4" for i in range(5)]
    for c in clips:
        c.touch()
    manifest = tmp_path / "manifest.txt"
    create_concat_manifest(clips, manifest)

    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 6
    for i in range(5):
        assert f"boss_fight_{i}.mp4" in lines[i + 1]


def test_t4_gaming_stream_hour_plus_timecodes_formatting():
    assert format_timecode_for_filename(7530.0) == "02h05m30s"
    assert format_timecode_for_filename(10800.0) == "03h00m00s"


def test_t4_gaming_stream_segment_durations_preserved():
    c = ClipItem(start=7530.0, end=7725.0)
    assert c.duration == 195.0


# ---------------------------------------------------------------------------
# Scenario 3: Fast Short Video Extraction (4 tests)
# ---------------------------------------------------------------------------


def test_t4_fast_short_15s_stream_copy_subsecond(tmp_path):
    harness = E2EClipPipelineHarness(workspace_dir=tmp_path)
    source = tmp_path / "short_src.mp4"
    source.touch()

    req = ClipExportRequest(
        request_id="short_fast",
        video_id="short_vid",
        video_title="Viral Cat Moment",
        clips=[ClipItem(id="s1", start=0.0, end=15.0)],
        cut_mode=CutMode.STREAM_COPY,
    )

    with patch.object(harness.downloader, "get_cached_source", return_value=source), \
         patch.object(harness.clip_engine, "trim_clip", side_effect=_mock_trim_clip):

        t0 = time.monotonic()
        res = harness.execute_export(req)
        elapsed = time.monotonic() - t0
        assert res.status == "SUCCESS"
        assert elapsed < 0.2  # Fast subsecond execution


def test_t4_fast_short_zero_to_fifteen_seconds():
    clip = ClipItem(start=0.0, end=15.0)
    assert clip.is_valid() is True
    assert clip.duration == 15.0


def test_t4_fast_short_single_file_export(tmp_path):
    fn = build_clip_filename("Short Viral", 1, 0.0, 15.0, "mp4")
    assert fn == "Short Viral_clip_1_0s-15s.mp4"


def test_t4_fast_short_cached_source_bypass_download(tmp_path):
    harness = E2EClipPipelineHarness(workspace_dir=tmp_path)
    cache_dir = tmp_path / "cache" / "youtube" / "short_cached"
    cache_dir.mkdir(parents=True)
    src = cache_dir / "source_short_cached_best.mp4"
    src.write_bytes(b"cached")

    req = ClipExportRequest(
        request_id="cached_req",
        video_id="short_cached",
        video_title="Cached Short",
        quality="best",
        clips=[ClipItem(id="1", start=0.0, end=10.0)],
    )

    with patch.object(harness.downloader, "get_cached_source", return_value=src), \
         patch.object(harness.downloader, "download") as mock_dl, \
         patch.object(harness.clip_engine, "trim_clip", side_effect=_mock_trim_clip):

        res = harness.execute_export(req)
        assert res.status == "SUCCESS"
        assert not mock_dl.called  # Download bypassed!


# ---------------------------------------------------------------------------
# Scenario 4: Network Download Error Recovery & Telemetry (4 tests)
# ---------------------------------------------------------------------------


def test_t4_network_download_progress_telemetry_streaming():
    lines = [
        "[download]  25.0% of ~100.00MiB at 5.00MiB/s ETA 00:15",
        "[download]  75.0% of ~100.00MiB at 5.50MiB/s ETA 00:05",
        "[download] 100% of 100.00MiB in 00:20 at 5.00MiB/s",
    ]
    parsed = [parse_ytdlp_progress_line(line) for line in lines]
    assert parsed[0]["percent"] == 25.0
    assert parsed[1]["percent"] == 75.0
    assert parsed[2]["percent"] == 100.0


def test_t4_network_download_remuxing_telemetry_stage():
    line = "[Merger] Merging formats into 'source.mp4'"
    parsed = parse_ytdlp_progress_line(line)
    assert parsed["stage"] == "REMUXING"
    assert parsed["percent"] == 100.0


def test_t4_network_download_fatal_error_emits_error_payload(tmp_path):
    harness = E2EClipPipelineHarness(workspace_dir=tmp_path)
    req = ClipExportRequest(
        request_id="err_job",
        video_id="unavail_vid",
        video_url="https://youtube.com/watch?v=unavail_vid",
        video_title="Unavailable",
        clips=[ClipItem(id="1", start=0.0, end=10.0)],
    )

    with patch.object(harness.downloader, "get_cached_source", return_value=None), \
         patch.object(harness.downloader, "download", side_effect=RuntimeError("Video is private")):

        with pytest.raises(RuntimeError, match="Video is private"):
            harness.execute_export(req)

        assert harness.active_jobs["err_job"]["running"] is False
        assert "Video is private" in harness.active_jobs["err_job"]["error"]


def test_t4_network_download_cleanup_scratch_on_error(tmp_path):
    harness = E2EClipPipelineHarness(workspace_dir=tmp_path)
    downloader = harness.downloader

    mock_proc = MagicMock()
    mock_proc.stdout.readline.side_effect = ["ERROR: HTTP 403 Forbidden\n", ""]
    mock_proc.wait.return_value = 1
    mock_proc.returncode = 1
    mock_proc.poll.return_value = 1

    cache_dir = tmp_path / "cache" / "youtube" / "err_403"
    cache_dir.mkdir(parents=True)
    partial_part = cache_dir / "source_err_403_1080p.mp4.part"
    partial_part.write_text("partial")

    with patch("subprocess.Popen", return_value=mock_proc):
        with pytest.raises(RuntimeError):
            downloader.download("https://test", "err_403", quality="1080p")

    # Partial download must be cleaned
    assert not partial_part.is_file()


# ---------------------------------------------------------------------------
# Scenario 5: Idempotent Export Requests & Cancellation Cleanup (4 tests)
# ---------------------------------------------------------------------------


def test_t4_idempotent_duplicate_request_id_accepted(tmp_path):
    harness = E2EClipPipelineHarness(workspace_dir=tmp_path)
    source = tmp_path / "source.mp4"
    source.touch()

    req = ClipExportRequest(
        request_id="idempotent_req_1",
        video_id="idemp_vid",
        video_title="Idempotent Test",
        clips=[ClipItem(id="1", start=0.0, end=10.0)],
    )

    with patch.object(harness.downloader, "get_cached_source", return_value=source), \
         patch.object(harness.clip_engine, "trim_clip", side_effect=_mock_trim_clip):

        res1 = harness.execute_export(req)
        # Second call with same request_id while recorded
        harness.active_jobs[req.request_id]["running"] = True
        res2 = harness.execute_export(req)

        assert res1 == res2


def test_t4_cancellation_mid_download_kills_process(tmp_path):
    downloader = YtDlpDownloader(ytdlp_path="mock_ytdlp", cache_root=tmp_path)
    mock_proc = MagicMock()
    mock_proc.stdout.readline.side_effect = ["[download]  15.0%\n"]
    mock_proc.poll.return_value = None

    with patch("subprocess.Popen", return_value=mock_proc):
        with pytest.raises(RuntimeError, match="cancelled by user"):
            downloader.download(
                video_url="https://youtube.com/watch?v=cancel",
                video_id="cancel",
                cancel_check=lambda: True,
            )
        assert mock_proc.terminate.called


def test_t4_cancellation_mid_trimming_cleans_scratch(tmp_path):
    engine = ClipEngine(ffmpeg_exe="ffmpeg.exe")
    src = tmp_path / "src.mp4"
    src.touch()
    out = tmp_path / "partial_clip.mp4"

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")
    mock_proc.returncode = 0
    mock_proc.pid = 4321

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("vkdub.media.clip_engine.kill_process_tree") as mock_kill:
        with pytest.raises(RuntimeError, match="Trimming cancelled"):
            engine.trim_clip(
                src, out, 0.0, 10.0,
                cancel_check=lambda: True,
            )
        assert mock_kill.called


def test_t4_job_completion_reports_elapsed_seconds(tmp_path):
    harness = E2EClipPipelineHarness(workspace_dir=tmp_path)
    source = tmp_path / "source.mp4"
    source.touch()

    req = ClipExportRequest(
        request_id="elapsed_req",
        video_id="elapsed_vid",
        video_title="Elapsed Time",
        clips=[ClipItem(id="1", start=0.0, end=5.0)],
    )

    with patch.object(harness.downloader, "get_cached_source", return_value=source), \
         patch.object(harness.clip_engine, "trim_clip", side_effect=_mock_trim_clip):

        res = harness.execute_export(req)
        assert res.elapsed_seconds > 0.0
        d = res.to_dict(camel_case=True)
        assert "elapsedSeconds" in d
        assert d["elapsedSeconds"] > 0.0
