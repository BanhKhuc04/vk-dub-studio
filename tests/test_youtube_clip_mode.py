"""VK Dub Studio — Comprehensive YouTube Clip Mode Automated Test Suite.

Tiers Covered:
- Tier 1: Feature Coverage (>=5 tests per feature: URL parsing, clip validation,
  timecode formatting, filename sanitization, hardware probing, stream copy command,
  frame-accurate command, concat manifest, yt-dlp discovery, protocol serialization).
- Tier 2: Boundary & Corner Cases (>=5 tests per feature: empty title,
  Vietnamese/Unicode characters, Windows reserved names CON/NUL/PRN, start=0, start=end,
  end>duration, negative timestamps, missing yt-dlp, missing ffmpeg, AMF missing DLL fallback,
  cancellation mid-execution).

All tests are 100% offline, self-contained, fast, and deterministic.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vkdub.bridge.protocol import (
    Actions,
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
from vkdub.media.clip_engine import (
    ClipEngine,
    build_clip_filename,
    build_concat_command,
    build_frame_accurate_trim_command,
    build_merged_filename,
    build_stream_copy_trim_command,
    create_concat_manifest,
    format_timecode,
    format_timecode_for_filename,
    kill_process_tree,
    parse_timecode,
    sanitize_filename,
)
from vkdub.media.hardware import (
    HardwareEncoderDetector,
    probe_encoder,
    resolve_best_encoder,
)
from vkdub.media.hardware import (
    clear_cache as clear_hw_cache,
)
from vkdub.media.ytdlp import (
    YtDlpDownloader,
    find_ytdlp,
    validate_media_integrity,
)

# Canonical YouTube URL extractor conforming to project contract
YOUTUBE_URL_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:www\.|m\.)?(?:youtube\.com\/(?:watch\?.*?v=|embed\/|v\/|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
)


def parse_youtube_url(url: str) -> str | None:
    """Extract YouTube video ID (11 chars) from standard, short, embed, or shorts URLs."""
    if not url or not isinstance(url, str):
        return None
    m = YOUTUBE_URL_REGEX.search(url.strip())
    return m.group(1) if m else None


# ===========================================================================
# TIER 1: FEATURE COVERAGE (10 Features x >=5 tests each)
# ===========================================================================

# ---------------------------------------------------------------------------
# Feature 1: URL Parsing (7 tests)
# ---------------------------------------------------------------------------


def test_t1_f1_url_parsing_standard_watch():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert parse_youtube_url(url) == "dQw4w9WgXcQ"


def test_t1_f1_url_parsing_short_domain():
    url = "https://youtu.be/dQw4w9WgXcQ"
    assert parse_youtube_url(url) == "dQw4w9WgXcQ"


def test_t1_f1_url_parsing_embed_url():
    url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
    assert parse_youtube_url(url) == "dQw4w9WgXcQ"


def test_t1_f1_url_parsing_shorts_url():
    url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
    assert parse_youtube_url(url) == "dQw4w9WgXcQ"


def test_t1_f1_url_parsing_with_query_params():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120s&list=PL123&index=2"
    assert parse_youtube_url(url) == "dQw4w9WgXcQ"


def test_t1_f1_url_parsing_mobile_url():
    url = "https://m.youtube.com/watch?v=dQw4w9WgXcQ"
    assert parse_youtube_url(url) == "dQw4w9WgXcQ"


def test_t1_f1_url_parsing_invalid_urls():
    assert parse_youtube_url("https://vimeo.com/12345678") is None
    assert parse_youtube_url("not_a_url") is None
    assert parse_youtube_url("") is None


# ---------------------------------------------------------------------------
# Feature 2: Clip Validation (7 tests)
# ---------------------------------------------------------------------------


def test_t1_f2_clip_validation_valid_range():
    clip = ClipItem(id="c1", name="Segment 1", start=10.0, end=25.0)
    assert clip.is_valid() is True
    assert clip.duration == 15.0


def test_t1_f2_clip_validation_fractional_precision():
    clip = ClipItem(id="c2", name="Precise", start=1.234, end=5.678)
    assert clip.is_valid() is True
    assert clip.duration == 4.444


def test_t1_f2_clip_validation_start_equals_end():
    clip = ClipItem(id="c3", name="Zero Length", start=10.0, end=10.0)
    assert clip.is_valid() is False
    assert clip.duration == 0.0


def test_t1_f2_clip_validation_start_greater_than_end():
    clip = ClipItem(id="c4", name="Inverted", start=30.0, end=10.0)
    assert clip.is_valid() is False


def test_t1_f2_clip_validation_negative_start():
    clip = ClipItem(id="c5", name="Negative Start", start=-2.0, end=10.0)
    assert clip.is_valid() is False


def test_t1_f2_clip_validation_max_duration_enforced():
    clip = ClipItem(id="c6", name="Exceeds", start=10.0, end=120.0)
    assert clip.is_valid(max_duration=100.0) is False
    assert clip.is_valid(max_duration=150.0) is True


def test_t1_f2_clip_serialization_roundtrip():
    original = ClipItem(id="c7", name="Roundtrip", start=5.5, end=12.2, selected=True)
    d = original.to_dict(camel_case=False)
    restored = ClipItem.from_dict(d)
    assert restored.id == original.id
    assert restored.start == original.start
    assert restored.end == original.end
    assert restored.selected == original.selected


# ---------------------------------------------------------------------------
# Feature 3: Timecode Formatting & Parsing (7 tests)
# ---------------------------------------------------------------------------


def test_t1_f3_parse_timecode_hh_mm_ss_mmm():
    assert parse_timecode("01:23:45.678") == pytest.approx(5025.678)


def test_t1_f3_parse_timecode_mm_ss_mmm():
    assert parse_timecode("05:30.500") == pytest.approx(330.5)


def test_t1_f3_parse_timecode_mm_ss():
    assert parse_timecode("02:15") == pytest.approx(135.0)


def test_t1_f3_parse_timecode_numeric():
    assert parse_timecode(120) == 120.0
    assert parse_timecode(45.25) == 45.25
    assert parse_timecode("45.25") == 45.25
    assert parse_timecode("90s") == 90.0


def test_t1_f3_format_timecode_with_milliseconds():
    assert format_timecode(5025.678, include_ms=True) == "01:23:45.678"


def test_t1_f3_format_timecode_without_milliseconds():
    assert format_timecode(135.0, include_ms=False) == "00:02:15"


def test_t1_f3_format_timecode_filename_safe():
    assert format_timecode_for_filename(90.0) == "01m30s"
    assert format_timecode_for_filename(45.0) == "45s"
    assert format_timecode_for_filename(3665.0) == "01h01m05s"


# ---------------------------------------------------------------------------
# Feature 4: Filename Sanitization (7 tests)
# ---------------------------------------------------------------------------


def test_t1_f4_sanitize_windows_illegal_characters():
    raw = 'Test: <Video> "Quotes" & |Pipes| ?Questions? *Stars* /Slash\\Back'
    clean = sanitize_filename(raw)
    for illegal in '<>:"/\\|?*':
        assert illegal not in clean


def test_t1_f4_sanitize_windows_reserved_names():
    for name in ["CON", "prn", "AUX", "NUL", "COM1", "lpt9"]:
        clean = sanitize_filename(name)
        assert clean.startswith("_")


def test_t1_f4_sanitize_trailing_dots_and_spaces():
    raw = "My Video Title...   "
    clean = sanitize_filename(raw)
    assert not clean.endswith(".")
    assert not clean.endswith(" ")
    assert clean == "My Video Title"


def test_t1_f4_sanitize_max_length_truncation():
    long_title = "A" * 150
    clean = sanitize_filename(long_title, max_length=60)
    assert len(clean) <= 60


def test_t1_f4_sanitize_empty_string_fallback():
    assert sanitize_filename("") == "clip"
    assert sanitize_filename("   ") == "clip"
    assert sanitize_filename("...   ...") == "clip"


def test_t1_f4_build_clip_filename():
    fn = build_clip_filename(
        video_title="Epic: Video / Part 1",
        clip_index=1,
        start_sec=10.0,
        end_sec=25.0,
        container="mp4",
    )
    assert "Epic_ Video _ Part 1_clip_1_" in fn
    assert fn.endswith(".mp4")
    assert "10s-25s" in fn


def test_t1_f4_build_merged_filename():
    fn = build_merged_filename(video_title="Review: Tech 2026?", container="mkv")
    assert fn == "Review_ Tech 2026__selected_clips.mkv"


# ---------------------------------------------------------------------------
# Feature 5: Hardware Probing (7 tests)
# ---------------------------------------------------------------------------


def test_t1_f5_hardware_probe_nvenc_success():
    clear_hw_cache()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert probe_encoder("ffmpeg.exe", "h264_nvenc") is True


def test_t1_f5_hardware_probe_failure():
    clear_hw_cache()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        assert probe_encoder("ffmpeg.exe", "h264_amf") is False


def test_t1_f5_hardware_probe_cache_reuse():
    clear_hw_cache()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        # First call hits subprocess
        probe_encoder("ffmpeg.exe", "h264_qsv")
        assert mock_run.call_count == 1
        # Second call hits cache
        probe_encoder("ffmpeg.exe", "h264_qsv")
        assert mock_run.call_count == 1


def test_t1_f5_hardware_resolve_nvenc_priority():
    clear_hw_cache()
    with patch("vkdub.media.hardware.probe_encoder") as mock_probe:
        mock_probe.side_effect = lambda exe, enc: enc == "h264_nvenc"
        enc, params = resolve_best_encoder("ffmpeg.exe", codec_family="h264")
        assert enc == "h264_nvenc"
        assert "-cq" in params
        assert "18" in params


def test_t1_f5_hardware_resolve_qsv_priority():
    clear_hw_cache()
    with patch("vkdub.media.hardware.probe_encoder") as mock_probe:
        mock_probe.side_effect = lambda exe, enc: enc == "h264_qsv"
        enc, params = resolve_best_encoder("ffmpeg.exe", codec_family="h264")
        assert enc == "h264_qsv"
        assert "-global_quality" in params


def test_t1_f5_hardware_resolve_cpu_fallback():
    clear_hw_cache()
    with patch("vkdub.media.hardware.probe_encoder") as mock_probe:
        # All GPU encoders fail; libx264 software fallback succeeds
        mock_probe.side_effect = lambda exe, enc: enc == "libx264"
        enc, params = resolve_best_encoder("ffmpeg.exe", codec_family="h264")
        assert enc == "libx264"
        assert "-crf" in params
        assert "18" in params


def test_t1_f5_hardware_detector_class():
    detector = HardwareEncoderDetector(ffmpeg_exe="ffmpeg.exe")
    assert detector.is_hardware_accelerated("h264_nvenc") is True
    assert detector.is_hardware_accelerated("h264_qsv") is True
    assert detector.is_hardware_accelerated("libx264") is False
    assert detector.is_hardware_accelerated("libx265") is False


# ---------------------------------------------------------------------------
# Feature 6: Stream Copy Command Building (6 tests)
# ---------------------------------------------------------------------------


def test_t1_f6_stream_copy_cmd_basic_structure():
    cmd = build_stream_copy_trim_command(
        "ffmpeg.exe", Path("src.mp4"), Path("out.mp4"), 5.0, 15.0
    )
    assert cmd[0] == "ffmpeg.exe"
    assert "-nostdin" in cmd
    assert "-ss" in cmd
    assert "-to" in cmd
    assert "-i" in cmd
    assert "-c" in cmd
    c_idx = cmd.index("-c")
    assert cmd[c_idx + 1] == "copy"


def test_t1_f6_stream_copy_cmd_avoid_negative_ts():
    cmd = build_stream_copy_trim_command(
        "ffmpeg.exe", Path("src.mp4"), Path("out.mp4"), 0.0, 10.0
    )
    assert "-avoid_negative_ts" in cmd
    idx = cmd.index("-avoid_negative_ts")
    assert cmd[idx + 1] == "make_zero"


def test_t1_f6_stream_copy_cmd_mp4_faststart():
    cmd = build_stream_copy_trim_command(
        "ffmpeg.exe", Path("src.mp4"), Path("out.mp4"), 1.0, 5.0
    )
    assert "-movflags" in cmd
    idx = cmd.index("-movflags")
    assert cmd[idx + 1] == "+faststart"


def test_t1_f6_stream_copy_cmd_mkv_no_faststart():
    cmd = build_stream_copy_trim_command(
        "ffmpeg.exe", Path("src.mp4"), Path("out.mkv"), 1.0, 5.0
    )
    assert "+faststart" not in cmd


def test_t1_f6_stream_copy_cmd_timestamps_format():
    cmd = build_stream_copy_trim_command(
        "ffmpeg.exe", Path("src.mp4"), Path("out.mp4"), 2.5, 8.75
    )
    ss_idx = cmd.index("-ss")
    assert cmd[ss_idx + 1] == "2.500"
    to_idx = cmd.index("-to")
    assert cmd[to_idx + 1] == "8.750"


def test_t1_f6_stream_copy_cmd_output_at_end():
    out = Path("my_output_clip.mp4")
    cmd = build_stream_copy_trim_command("ffmpeg.exe", Path("src.mp4"), out, 0.0, 5.0)
    assert cmd[-1] == str(out)


# ---------------------------------------------------------------------------
# Feature 7: Frame-Accurate Command Building (6 tests)
# ---------------------------------------------------------------------------


def test_t1_f7_frame_accurate_cmd_nvenc():
    cmd = build_frame_accurate_trim_command(
        ffmpeg_exe="ffmpeg.exe",
        source_path=Path("src.mp4"),
        output_path=Path("out.mp4"),
        start_sec=10.0,
        end_sec=20.0,
        encoder_name="h264_nvenc",
        encoder_args=["-preset", "p5", "-cq", "18"],
    )
    assert "-c:v" in cmd
    assert cmd[cmd.index("-c:v") + 1] == "h264_nvenc"
    assert "-cq" in cmd and "18" in cmd


def test_t1_f7_frame_accurate_cmd_qsv():
    cmd = build_frame_accurate_trim_command(
        ffmpeg_exe="ffmpeg.exe",
        source_path=Path("src.mp4"),
        output_path=Path("out.mp4"),
        start_sec=10.0,
        end_sec=20.0,
        encoder_name="h264_qsv",
        encoder_args=["-global_quality", "18", "-preset", "medium"],
    )
    assert cmd[cmd.index("-c:v") + 1] == "h264_qsv"
    assert "-global_quality" in cmd


def test_t1_f7_frame_accurate_cmd_cpu_fallback():
    cmd = build_frame_accurate_trim_command(
        ffmpeg_exe="ffmpeg.exe",
        source_path=Path("src.mp4"),
        output_path=Path("out.mp4"),
        start_sec=0.0,
        end_sec=5.0,
        encoder_name="libx264",
        encoder_args=["-crf", "18", "-preset", "faster"],
    )
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "-crf" in cmd and "18" in cmd


def test_t1_f7_frame_accurate_cmd_audio_encoding():
    cmd = build_frame_accurate_trim_command(
        ffmpeg_exe="ffmpeg.exe",
        source_path=Path("src.mp4"),
        output_path=Path("out.mp4"),
        start_sec=0.0,
        end_sec=5.0,
        encoder_name="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
    )
    assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "aac"
    assert "-b:a" in cmd and cmd[cmd.index("-b:a") + 1] == "192k"


def test_t1_f7_frame_accurate_cmd_faststart_on_mp4():
    cmd = build_frame_accurate_trim_command(
        ffmpeg_exe="ffmpeg.exe",
        source_path=Path("src.mp4"),
        output_path=Path("out.mp4"),
        start_sec=0.0,
        end_sec=5.0,
        encoder_name="libx264",
    )
    assert "-movflags" in cmd and "+faststart" in cmd


def test_t1_f7_frame_accurate_cmd_no_faststart_on_mkv():
    cmd = build_frame_accurate_trim_command(
        ffmpeg_exe="ffmpeg.exe",
        source_path=Path("src.mp4"),
        output_path=Path("out.mkv"),
        start_sec=0.0,
        end_sec=5.0,
        encoder_name="libx264",
    )
    assert "+faststart" not in cmd


# ---------------------------------------------------------------------------
# Feature 8: Concat Manifest Generation (6 tests)
# ---------------------------------------------------------------------------


def test_t1_f8_concat_manifest_single_clip(tmp_path):
    clip = tmp_path / "clip1.mp4"
    clip.write_text("clip1")
    manifest = tmp_path / "manifest.txt"
    create_concat_manifest([clip], manifest)

    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "ffconcat version 1.0"
    assert f"file '{clip.as_posix()}'" in lines[1]


def test_t1_f8_concat_manifest_multiple_clips(tmp_path):
    clips = [tmp_path / f"clip_{i}.mp4" for i in range(3)]
    for c in clips:
        c.write_text("dummy")
    manifest = tmp_path / "manifest.txt"
    create_concat_manifest(clips, manifest)

    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    for i, c in enumerate(clips):
        assert f"file '{c.as_posix()}'" in lines[i + 1]


def test_t1_f8_concat_manifest_escapes_single_quotes(tmp_path):
    clip = tmp_path / "gamer's_clip.mp4"
    clip.write_text("dummy")
    manifest = tmp_path / "manifest.txt"
    create_concat_manifest([clip], manifest)

    content = manifest.read_text(encoding="utf-8")
    assert "\\'" in content


def test_t1_f8_concat_manifest_empty_raises_value_error(tmp_path):
    with pytest.raises(ValueError, match="cannot be empty"):
        create_concat_manifest([], tmp_path / "empty_manifest.txt")


def test_t1_f8_build_concat_command():
    cmd = build_concat_command("ffmpeg.exe", Path("manifest.txt"), Path("merged.mp4"))
    assert cmd[0] == "ffmpeg.exe"
    assert "-f" in cmd and "concat" in cmd
    assert "-safe" in cmd and "0" in cmd
    assert "-c" in cmd and "copy" in cmd
    assert "-movflags" in cmd and "+faststart" in cmd
    assert cmd[-1] == "merged.mp4"


def test_t1_f8_build_concat_command_mkv_no_faststart():
    cmd = build_concat_command("ffmpeg.exe", Path("manifest.txt"), Path("merged.mkv"))
    assert "+faststart" not in cmd


# ---------------------------------------------------------------------------
# Feature 9: yt-dlp Discovery (7 tests)
# ---------------------------------------------------------------------------


def test_t1_f9_ytdlp_env_override_authoritative(tmp_path, monkeypatch):
    custom_exe = tmp_path / "ytdlp_custom.exe"
    custom_exe.write_text("mock")
    monkeypatch.setenv("YTDLP_PATH", str(custom_exe))

    found = find_ytdlp()
    assert found == str(custom_exe.resolve())


def test_t1_f9_ytdlp_env_override_missing_returns_none(monkeypatch):
    monkeypatch.setenv("YTDLP_PATH", "D:/nonexistent/yt-dlp.exe")
    assert find_ytdlp() is None


def test_t1_f9_ytdlp_bundled_subdir_discovery(tmp_path, monkeypatch):
    monkeypatch.delenv("YTDLP_PATH", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)

    exe_name = "yt-dlp.exe" if os.name == "nt" else "yt-dlp"
    tool_dir = tmp_path / "tools" / "yt-dlp"
    tool_dir.mkdir(parents=True)
    tool = tool_dir / exe_name
    tool.write_text("bin")

    with patch("pathlib.Path.cwd", return_value=tmp_path):
        found = find_ytdlp(search_roots=[tmp_path])
        assert found is not None
        assert Path(found).resolve() == tool.resolve()


def test_t1_f9_ytdlp_bundled_root_discovery(tmp_path, monkeypatch):
    monkeypatch.delenv("YTDLP_PATH", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)

    exe_name = "yt-dlp.exe" if os.name == "nt" else "yt-dlp"
    tool_dir = tmp_path / "tools"
    tool_dir.mkdir(parents=True)
    tool = tool_dir / exe_name
    tool.write_text("bin")

    with patch("pathlib.Path.cwd", return_value=tmp_path):
        found = find_ytdlp(search_roots=[tmp_path])
        assert found is not None
        assert Path(found).resolve() == tool.resolve()


def test_t1_f9_ytdlp_system_path_discovery(monkeypatch):
    monkeypatch.delenv("YTDLP_PATH", raising=False)
    sys_exe = "C:/Windows/System32/yt-dlp.exe" if os.name == "nt" else "/usr/bin/yt-dlp"
    monkeypatch.setattr("shutil.which", lambda name: sys_exe if "yt-dlp" in name else None)

    with patch("pathlib.Path.is_file", return_value=False):
        found = find_ytdlp(search_roots=[])
        assert found is not None


def test_t1_f9_ytdlp_winget_shim_discovery(tmp_path, monkeypatch):
    monkeypatch.delenv("YTDLP_PATH", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)

    winget_dir = tmp_path / "Microsoft" / "WinGet" / "Links"
    winget_dir.mkdir(parents=True)
    winget_exe = winget_dir / "yt-dlp.exe"
    winget_exe.write_text("mock")

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    if os.name == "nt":
        found = find_ytdlp(search_roots=[])
        assert found is not None
        assert Path(found).resolve() == winget_exe.resolve()


def test_t1_f9_ytdlp_completely_missing_returns_none(monkeypatch):
    monkeypatch.delenv("YTDLP_PATH", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)
    with patch("pathlib.Path.is_file", return_value=False):
        assert find_ytdlp() is None


# ---------------------------------------------------------------------------
# Feature 10: Protocol Serialization & Schemas (8 tests)
# ---------------------------------------------------------------------------


def test_t1_f10_protocol_action_constants():
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


def test_t1_f10_youtube_context_sync_roundtrip():
    payload = {
        "videoId": "jNQXAC9IVRw",
        "title": "Me at the zoo",
        "duration": 19.08,
        "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "author": "jawed",
        "currentTime": 5.2,
        "tabId": 101,
    }
    sync = YouTubeContextSync.from_payload(payload)
    assert sync.video_id == "jNQXAC9IVRw"
    assert sync.duration == 19.08
    assert sync.current_time == 5.2

    camel = sync.to_dict(camel_case=True)
    assert camel["videoId"] == "jNQXAC9IVRw"
    assert camel["currentTime"] == 5.2


def test_t1_f10_clip_export_request_roundtrip():
    payload = {
        "requestId": "req_123",
        "videoId": "dQw4w9WgXcQ",
        "videoUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "videoTitle": "Never Gonna Give You Up",
        "duration": 212.0,
        "clips": [
            {"id": "c1", "name": "Intro", "start": 0.0, "end": 15.0},
            {"id": "c2", "name": "Chorus", "start": 43.0, "end": 65.0},
        ],
        "exportMode": "MERGED",
        "outputDir": "D:/Videos/Clips",
        "container": "mp4",
        "quality": "1080p",
        "cutMode": "FRAME_ACCURATE",
        "useCookies": True,
        "browser": "edge",
    }
    req = ClipExportRequest.from_payload(payload)
    assert req.request_id == "req_123"
    assert req.video_id == "dQw4w9WgXcQ"
    assert len(req.clips) == 2
    assert req.export_mode == ExportMode.MERGED
    assert req.cut_mode == CutMode.FRAME_ACCURATE
    assert req.use_cookies is True
    assert req.browser == "edge"


def test_t1_f10_clip_export_accepted_roundtrip():
    accepted = ClipExportAccepted.from_payload({
        "requestId": "req_1",
        "jobId": "job_1",
        "status": "QUEUED",
        "totalClips": 3,
        "message": "Queued 3 clips",
    })
    assert accepted.request_id == "req_1"
    assert accepted.total_clips == 3
    assert accepted.status == "QUEUED"


def test_t1_f10_clip_export_progress_roundtrip():
    prog = ClipExportProgress.from_payload({
        "requestId": "req_1",
        "stage": ExportStage.DOWNLOADING,
        "percent": 45.5,
        "speed": "5.2 MB/s",
        "downloadedBytes": 10485760,
        "totalBytes": 20971520,
        "currentClip": 1,
        "totalClips": 2,
        "message": "Downloading source...",
    })
    assert prog.stage == ExportStage.DOWNLOADING
    assert prog.percent == 45.5
    assert prog.speed == "5.2 MB/s"
    assert prog.downloaded_bytes == 10485760


def test_t1_f10_clip_export_result_roundtrip():
    res = ClipExportResult.from_payload({
        "requestId": "req_1",
        "status": "SUCCESS",
        "files": ["D:/Clips/clip1.mp4", "D:/Clips/clip2.mp4"],
        "mergedFile": "D:/Clips/merged.mp4",
        "outputDir": "D:/Clips",
        "elapsedSeconds": 4.5,
    })
    assert res.status == "SUCCESS"
    assert len(res.files) == 2
    assert res.merged_file == "D:/Clips/merged.mp4"
    assert res.elapsed_seconds == 4.5


def test_t1_f10_clip_export_error_and_cancel():
    err = ClipExportError.from_payload({
        "requestId": "req_1",
        "error": "Failed to download",
        "stage": ExportStage.DOWNLOADING,
    })
    assert err.error == "Failed to download"
    assert err.stage == ExportStage.DOWNLOADING

    cancel = ClipExportCancel.from_payload({"requestId": "req_1"})
    assert cancel.request_id == "req_1"


def test_t1_f10_open_output_folder_and_seek_to():
    folder = OpenOutputFolderPayload.from_payload({"path": "D:/Output/Clips"})
    assert folder.path == "D:/Output/Clips"

    seek = YouTubeSeekTo.from_payload({"seconds": 12.5, "play": True})
    assert seek.seconds == 12.5
    assert seek.play is True

    preview = YouTubePreviewClip.from_payload({"start": 5.0, "end": 15.0, "loop": True})
    assert preview.start == 5.0
    assert preview.end == 15.0
    assert preview.loop is True


# ===========================================================================
# TIER 2: BOUNDARY & CORNER CASES (11 Categories x >=5 tests each)
# ===========================================================================

# ---------------------------------------------------------------------------
# Corner 1: Empty Title & Whitespace (5 tests)
# ---------------------------------------------------------------------------


def test_t2_c1_empty_title_fallback_to_clip():
    assert sanitize_filename("") == "clip"


def test_t2_c1_spaces_only_fallback_to_clip():
    assert sanitize_filename("       ") == "clip"


def test_t2_c1_special_characters_replaced_with_underscores():
    clean = sanitize_filename(":::***???///\\\\\\")
    assert clean == "_" * 15
    for illegal in '<>:"/\\|?*':
        assert illegal not in clean


def test_t2_c1_dots_and_spaces_only_fallback():
    assert sanitize_filename(". . . .   ...") == "clip"


def test_t2_c1_build_clip_filename_empty_title():
    fn = build_clip_filename(video_title="", clip_index=1, start_sec=0.0, end_sec=5.0)
    assert fn.startswith("clip_clip_1_")
    assert fn.endswith(".mp4")


# ---------------------------------------------------------------------------
# Corner 2: Vietnamese & Unicode Characters (5 tests)
# ---------------------------------------------------------------------------


def test_t2_c2_vietnamese_diacritics_preserved():
    title = "Lồng tiếng AI & Video Tự Động Hóa (2026)"
    clean = sanitize_filename(title)
    assert "Lồng tiếng AI" in clean
    assert "Tự Động Hóa" in clean
    assert ":" not in clean


def test_t2_c2_cjk_characters_preserved():
    title = "日本語タイトル / 한국어 클립"
    clean = sanitize_filename(title)
    assert "日本語タイトル" in clean
    assert "한국어 클립" in clean
    assert "/" not in clean


def test_t2_c2_emoji_characters_handled():
    title = "🔥 Siêu Phẩm AI 2026 🚀"
    clean = sanitize_filename(title)
    assert "Siêu Phẩm AI 2026" in clean


def test_t2_c2_vietnamese_clip_filename_generation():
    fn = build_clip_filename(
        video_title="Dự Án: Đắc Nhân Tâm",
        clip_index=1,
        start_sec=10.0,
        end_sec=20.0,
    )
    assert "Dự Án_ Đắc Nhân Tâm_clip_1_" in fn
    assert ":" not in fn


def test_t2_c2_concat_manifest_utf8_encoding(tmp_path):
    clip = tmp_path / "video_tiếng_việt.mp4"
    clip.write_text("dummy", encoding="utf-8")
    manifest = tmp_path / "manifest_utf8.txt"
    create_concat_manifest([clip], manifest)

    content = manifest.read_text(encoding="utf-8")
    assert "video_tiếng_việt.mp4" in content


# ---------------------------------------------------------------------------
# Corner 3: Windows Reserved Names (6 tests)
# ---------------------------------------------------------------------------


def test_t2_c3_reserved_con():
    assert sanitize_filename("CON") == "_CON"
    assert sanitize_filename("con.mp4") == "_con.mp4"


def test_t2_c3_reserved_nul():
    assert sanitize_filename("NUL") == "_NUL"
    assert sanitize_filename("Nul.txt") == "_Nul.txt"


def test_t2_c3_reserved_prn():
    assert sanitize_filename("PRN") == "_PRN"
    assert sanitize_filename("prn.mp4") == "_prn.mp4"


def test_t2_c3_reserved_aux():
    assert sanitize_filename("AUX") == "_AUX"
    assert sanitize_filename("aux.mov") == "_aux.mov"


def test_t2_c3_reserved_com_ports():
    for i in range(1, 10):
        assert sanitize_filename(f"COM{i}") == f"_COM{i}"
        assert sanitize_filename(f"com{i}.mp4") == f"_com{i}.mp4"


def test_t2_c3_reserved_lpt_ports():
    for i in range(1, 10):
        assert sanitize_filename(f"LPT{i}") == f"_LPT{i}"
        assert sanitize_filename(f"lpt{i}.mkv") == f"_lpt{i}.mkv"


# ---------------------------------------------------------------------------
# Corner 4: Start = 0 Boundary (5 tests)
# ---------------------------------------------------------------------------


def test_t2_c4_parse_timecode_zero():
    assert parse_timecode(0) == 0.0
    assert parse_timecode("0") == 0.0
    assert parse_timecode("00:00:00") == 0.0
    assert parse_timecode("00:00:00.000") == 0.0


def test_t2_c4_clip_item_start_zero_is_valid():
    clip = ClipItem(id="c0", name="Beginning", start=0.0, end=10.0)
    assert clip.is_valid() is True
    assert clip.duration == 10.0


def test_t2_c4_stream_copy_trim_start_zero():
    cmd = build_stream_copy_trim_command(
        "ffmpeg.exe", Path("src.mp4"), Path("out.mp4"), 0.0, 10.0
    )
    ss_idx = cmd.index("-ss")
    assert cmd[ss_idx + 1] == "0.000"


def test_t2_c4_frame_accurate_trim_start_zero():
    cmd = build_frame_accurate_trim_command(
        "ffmpeg.exe", Path("src.mp4"), Path("out.mp4"), 0.0, 10.0, "libx264"
    )
    ss_idx = cmd.index("-ss")
    assert cmd[ss_idx + 1] == "0.000"


def test_t2_c4_format_timecode_zero():
    assert format_timecode(0.0, include_ms=True) == "00:00:00.000"
    assert format_timecode(0.0, include_ms=False) == "00:00:00"


# ---------------------------------------------------------------------------
# Corner 5: Start = End (Zero Duration Boundary) (5 tests)
# ---------------------------------------------------------------------------


def test_t2_c5_clip_item_start_equals_end_is_invalid():
    clip = ClipItem(id="zero", name="Point", start=15.0, end=15.0)
    assert clip.is_valid() is False


def test_t2_c5_clip_item_zero_duration_value():
    clip = ClipItem(id="zero", name="Point", start=45.2, end=45.2)
    assert clip.duration == 0.0


def test_t2_c5_clip_engine_trim_start_equals_end_raises(tmp_path):
    engine = ClipEngine(ffmpeg_exe="ffmpeg.exe")
    with pytest.raises(ValueError, match="strictly less"):
        engine.trim_clip(tmp_path / "src.mp4", tmp_path / "out.mp4", 10.0, 10.0)


def test_t2_c5_clip_export_request_filters_zero_duration():
    payload = {
        "requestId": "req_zero",
        "clips": [
            {"id": "c1", "name": "Zero", "start": 10.0, "end": 10.0},
            {"id": "c2", "name": "Valid", "start": 10.0, "end": 20.0},
        ],
    }
    req = ClipExportRequest.from_payload(payload)
    valid_clips = [c for c in req.clips if c.is_valid()]
    assert len(valid_clips) == 1
    assert valid_clips[0].id == "c2"


def test_t2_c5_timecode_zero_delta():
    t1 = parse_timecode("00:01:30")
    t2 = parse_timecode("00:01:30")
    assert t2 - t1 == 0.0


# ---------------------------------------------------------------------------
# Corner 6: End > Duration Boundary (5 tests)
# ---------------------------------------------------------------------------


def test_t2_c6_clip_item_end_exceeds_duration_is_invalid():
    clip = ClipItem(id="exceed", name="Too Long", start=10.0, end=120.0)
    assert clip.is_valid(max_duration=100.0) is False


def test_t2_c6_clip_item_start_exceeds_duration_is_invalid():
    clip = ClipItem(id="exceed", name="Past End", start=110.0, end=130.0)
    assert clip.is_valid(max_duration=100.0) is False


def test_t2_c6_clip_item_end_equals_duration_is_valid():
    clip = ClipItem(id="exact", name="Exact End", start=50.0, end=100.0)
    assert clip.is_valid(max_duration=100.0) is True


def test_t2_c6_export_request_validation_with_duration():
    payload = {
        "duration": 60.0,
        "clips": [
            {"id": "c1", "start": 0.0, "end": 30.0},
            {"id": "c2", "start": 45.0, "end": 90.0},  # Exceeds
        ],
    }
    req = ClipExportRequest.from_payload(payload)
    valid = [c for c in req.clips if c.is_valid(max_duration=req.duration)]
    assert len(valid) == 1
    assert valid[0].id == "c1"


def test_t2_c6_fractional_exceeded_duration():
    clip = ClipItem(start=0.0, end=100.001)
    assert clip.is_valid(max_duration=100.0) is False


# ---------------------------------------------------------------------------
# Corner 7: Negative Timestamps (5 tests)
# ---------------------------------------------------------------------------


def test_t2_c7_parse_timecode_negative_float_raises():
    with pytest.raises(ValueError, match="cannot be negative"):
        parse_timecode(-10.5)


def test_t2_c7_parse_timecode_negative_string_raises():
    with pytest.raises(ValueError, match="cannot be negative"):
        parse_timecode("-15s")


def test_t2_c7_parse_timecode_negative_parts_raises():
    with pytest.raises(ValueError, match="cannot be negative"):
        parse_timecode("-01:00:00")


def test_t2_c7_clip_item_negative_start_invalid():
    clip = ClipItem(start=-5.0, end=10.0)
    assert clip.is_valid() is False


def test_t2_c7_clip_item_both_negative_invalid():
    clip = ClipItem(start=-20.0, end=-5.0)
    assert clip.is_valid() is False


# ---------------------------------------------------------------------------
# Corner 8: Missing yt-dlp Handling (5 tests)
# ---------------------------------------------------------------------------


def test_t2_c8_ytdlp_downloader_missing_executable_raises():
    with patch("vkdub.media.ytdlp.find_ytdlp", return_value=None):
        downloader = YtDlpDownloader(ytdlp_path=None)
        with pytest.raises(FileNotFoundError, match="yt-dlp executable was not found"):
            downloader.download(
                video_url="https://youtube.com/watch?v=missing",
                video_id="missing",
            )


def test_t2_c8_ytdlp_empty_string_path_raises():
    with patch("vkdub.media.ytdlp.find_ytdlp", return_value=None):
        downloader = YtDlpDownloader(ytdlp_path="")
        with pytest.raises(FileNotFoundError):
            downloader.download(video_url="https://test", video_id="test")


def test_t2_c8_ytdlp_download_failure_removes_partial_files(tmp_path):
    downloader = YtDlpDownloader(ytdlp_path="dummy_ytdlp", cache_root=tmp_path)
    mock_proc = MagicMock()
    mock_proc.stdout.readline.side_effect = ["ERROR: Private video\n", ""]
    mock_proc.wait.return_value = 1
    mock_proc.returncode = 1
    mock_proc.poll.return_value = 1

    cache_dir = tmp_path / "cache" / "youtube" / "err_vid"
    cache_dir.mkdir(parents=True)
    part_file = cache_dir / "source_err_vid_1080p.mp4.part"
    part_file.write_text("partial")

    with patch("subprocess.Popen", return_value=mock_proc):
        with pytest.raises(RuntimeError, match="yt-dlp download failed"):
            downloader.download("https://test", "err_vid", quality="1080p")

    # Partial file should be removed
    assert not part_file.is_file()


def test_t2_c8_ytdlp_subprocess_stderr_in_exception(tmp_path):
    downloader = YtDlpDownloader(ytdlp_path="dummy_ytdlp", cache_root=tmp_path)
    mock_proc = MagicMock()
    mock_proc.stdout.readline.side_effect = [
        "ERROR: Sign in to confirm your age\n",
        "",
    ]
    mock_proc.wait.return_value = 1
    mock_proc.returncode = 1
    mock_proc.poll.return_value = 1

    with patch("subprocess.Popen", return_value=mock_proc):
        with pytest.raises(RuntimeError, match="Sign in to confirm your age"):
            downloader.download("https://test", "age_restricted")


def test_t2_c8_ytdlp_cache_corrupt_file_deleted(tmp_path):
    downloader = YtDlpDownloader(ytdlp_path="dummy", cache_root=tmp_path)
    cache_dir = tmp_path / "cache" / "youtube" / "corrupt_vid"
    cache_dir.mkdir(parents=True)
    corrupt_file = cache_dir / "source_corrupt_vid_1080p.mp4"
    corrupt_file.write_bytes(b"bad")  # < 1024 bytes -> corrupt

    # validate_media_integrity will return False
    with patch("vkdub.media.ytdlp.validate_media_integrity", return_value=False):
        cached = downloader.get_cached_source("corrupt_vid", "1080p")
        assert cached is None
        assert not corrupt_file.is_file()


# ---------------------------------------------------------------------------
# Corner 9: Missing FFmpeg / FFprobe Handling (5 tests)
# ---------------------------------------------------------------------------


def test_t2_c9_clip_engine_missing_ffmpeg_trim_raises(tmp_path):
    with patch("vkdub.media.clip_engine.find_tool", return_value=None):
        engine = ClipEngine(ffmpeg_exe=None)
        with pytest.raises(FileNotFoundError, match="FFmpeg executable not found"):
            engine.trim_clip(tmp_path / "src.mp4", tmp_path / "out.mp4", 0.0, 5.0)


def test_t2_c9_clip_engine_missing_ffmpeg_merge_raises(tmp_path):
    with patch("vkdub.media.clip_engine.find_tool", return_value=None):
        engine = ClipEngine(ffmpeg_exe=None)
        with pytest.raises(FileNotFoundError, match="FFmpeg executable not found"):
            engine.merge_clips([tmp_path / "clip.mp4"], tmp_path / "out.mp4")


def test_t2_c9_validate_media_integrity_nonexistent_file():
    assert validate_media_integrity(Path("nonexistent_video.mp4")) is False


def test_t2_c9_validate_media_integrity_zero_bytes(tmp_path):
    empty = tmp_path / "empty.mp4"
    empty.touch()
    assert validate_media_integrity(empty) is False


def test_t2_c9_hardware_detector_missing_ffmpeg_fallback():
    clear_hw_cache()
    with patch("vkdub.media.hardware.find_tool", return_value=None):
        enc, params = resolve_best_encoder(ffmpeg_exe=None, codec_family="h264")
        assert enc == "libx264"
        assert "-crf" in params


# ---------------------------------------------------------------------------
# Corner 10: AMF Missing DLL Fallback (5 tests)
# ---------------------------------------------------------------------------


def test_t2_c10_amf_probe_dll_missing_returns_false():
    clear_hw_cache()
    # Emulate exit code 1 when AMF runtime DLL (amfrt64.dll) is not installed
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        assert probe_encoder("ffmpeg.exe", "h264_amf") is False


def test_t2_c10_amf_failure_falls_back_to_libx264():
    clear_hw_cache()
    with patch("vkdub.media.hardware.probe_encoder") as mock_probe:
        # NVENC fails, QSV fails, AMF fails with DLL error
        mock_probe.side_effect = lambda exe, enc: not any(g in enc for g in ("amf", "nvenc", "qsv"))
        enc, params = resolve_best_encoder("ffmpeg.exe", codec_family="h264")
        assert enc == "libx264"
        assert "-crf" in params
        assert "18" in params


def test_t2_c10_amf_hevc_failure_falls_back_to_libx265():
    clear_hw_cache()
    with patch("vkdub.media.hardware.probe_encoder") as mock_probe:
        mock_probe.side_effect = lambda exe, enc: not any(g in enc for g in ("amf", "nvenc", "qsv"))
        enc, params = resolve_best_encoder("ffmpeg.exe", codec_family="hevc")
        assert enc == "libx265"
        assert "-crf" in params


def test_t2_c10_amf_probe_result_is_cached():
    clear_hw_cache()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        # Probe AMF twice
        probe_encoder("ffmpeg.exe", "h264_amf")
        probe_encoder("ffmpeg.exe", "h264_amf")
        # Subprocess should execute only once due to cache
        assert mock_run.call_count == 1


def test_t2_c10_clip_engine_uses_amf_fallback_without_crash(tmp_path):
    clear_hw_cache()
    src = tmp_path / "source.mp4"
    src.write_text("source")
    out = tmp_path / "clip.mp4"

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")
    mock_proc.returncode = 0

    def fake_comm(*args, **kwargs):
        out.write_text("trimmed")
        return ("", "")

    mock_proc.communicate = fake_comm

    with patch("vkdub.media.hardware.probe_encoder") as mock_probe, \
         patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        mock_probe.side_effect = lambda exe, enc: enc == "libx264"
        engine = ClipEngine(ffmpeg_exe="ffmpeg.exe")
        engine.trim_clip(src, out, 0.0, 5.0, cut_mode="FRAME_ACCURATE")

        args = mock_popen.call_args[0][0]
        assert "-c:v" in args
        assert args[args.index("-c:v") + 1] == "libx264"


# ---------------------------------------------------------------------------
# Corner 11: Cancellation Mid-Execution (5 tests)
# ---------------------------------------------------------------------------


def test_t2_c11_kill_process_tree_calls_taskkill_on_windows():
    with patch("os.name", "nt"), patch("subprocess.run") as mock_run:
        kill_process_tree(12345)
        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "taskkill"
        assert "/F" in cmd
        assert "/T" in cmd
        assert "/PID" in cmd
        assert "12345" in cmd


def test_t2_c11_trim_clip_cancellation_terminates_process(tmp_path):
    engine = ClipEngine(ffmpeg_exe="ffmpeg.exe")
    src = tmp_path / "src.mp4"
    src.write_text("src")
    out = tmp_path / "out.mp4"

    mock_proc = MagicMock()
    mock_proc.pid = 9876
    mock_proc.communicate.return_value = ("", "")
    mock_proc.returncode = 0

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("vkdub.media.clip_engine.kill_process_tree") as mock_kill:
        with pytest.raises(RuntimeError, match="Trimming cancelled"):
            engine.trim_clip(
                src, out, 0.0, 5.0,
                cut_mode="STREAM_COPY",
                cancel_check=lambda: True,
            )
        assert mock_kill.called


def test_t2_c11_merge_clips_cancellation_terminates_process(tmp_path):
    engine = ClipEngine(ffmpeg_exe="ffmpeg.exe")
    c1 = tmp_path / "c1.mp4"
    c1.write_text("dummy")
    out = tmp_path / "merged.mp4"

    mock_proc = MagicMock()
    mock_proc.pid = 9877
    mock_proc.communicate.return_value = ("", "")

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("vkdub.media.clip_engine.kill_process_tree") as mock_kill:
        with pytest.raises(RuntimeError, match="Merge cancelled"):
            engine.merge_clips(
                [c1], out,
                cancel_check=lambda: True,
            )
        assert mock_kill.called


def test_t2_c11_ytdlp_download_cancellation(tmp_path):
    downloader = YtDlpDownloader(ytdlp_path="dummy", cache_root=tmp_path)
    mock_proc = MagicMock()
    mock_proc.stdout.readline.side_effect = ["[download]  10.0%\n"]
    mock_proc.poll.return_value = None

    with patch("subprocess.Popen", return_value=mock_proc):
        with pytest.raises(RuntimeError, match="Download cancelled by user"):
            downloader.download(
                "https://youtube.com/watch?v=cancel",
                "cancel",
                cancel_check=lambda: True,
            )
        assert mock_proc.terminate.called


def test_t2_c11_clip_export_cancel_payload_validation():
    cancel = ClipExportCancel.from_payload({"requestId": "cancel_req_42", "jobId": "job_42"})
    assert cancel.request_id == "cancel_req_42"
    assert cancel.job_id == "job_42"
    d = cancel.to_dict(camel_case=True)
    assert d["requestId"] == "cancel_req_42"
    assert d["jobId"] == "job_42"
