"""Comprehensive unit and integration test suite for Video Engine:

- yt-dlp discovery (5-step search order), single-download caching, opt-in cookies
- Hardware encoder detection (active 1-frame probe, NVENC/QSV/AMF/CPU fallback)
- ClipEngine trimming (stream-copy, frame-accurate), concat demuxer,
  path sanitization, timecode parser
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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
    get_encoder_params,
    probe_encoder,
    resolve_best_encoder,
)
from vkdub.media.hardware import (
    clear_cache as clear_hw_cache,
)
from vkdub.media.process import find_tool
from vkdub.media.ytdlp import (
    YtDlpDownloader,
    build_ytdlp_download_command,
    find_ytdlp,
    get_youtube_cache_dir,
    parse_ytdlp_progress_line,
    validate_media_integrity,
)

# ---------------------------------------------------------------------------
# Task 1 Tests: yt-dlp Discovery, Download Command & Caching
# ---------------------------------------------------------------------------


def test_find_ytdlp_step1_env_override_valid(tmp_path, monkeypatch):
    dummy_exe = tmp_path / "custom_ytdlp.exe"
    dummy_exe.write_text("dummy")
    monkeypatch.setenv("YTDLP_PATH", str(dummy_exe))

    found = find_ytdlp()
    assert found == str(dummy_exe.resolve())
    # Parent directory should be injected into PATH
    assert str(tmp_path.resolve()).lower() in os.environ["PATH"].lower()


def test_youtube_cache_dir_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError, match="Invalid YouTube video ID"):
        get_youtube_cache_dir("../../outside", custom_base=tmp_path)


def test_find_ytdlp_step1_env_override_missing(monkeypatch):
    monkeypatch.setenv("YTDLP_PATH", "C:/nonexistent/path/yt-dlp.exe")
    # Authoritative override: missing configured path returns None without fallback
    assert find_ytdlp() is None


def test_find_ytdlp_step2_bundled_subdir(tmp_path, monkeypatch):
    monkeypatch.delenv("YTDLP_PATH", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)

    # Mock base directory with tools/yt-dlp/yt-dlp.exe
    exe_name = "yt-dlp.exe" if os.name == "nt" else "yt-dlp"
    tool_dir = tmp_path / "tools" / "yt-dlp"
    tool_dir.mkdir(parents=True)
    tool_exe = tool_dir / exe_name
    tool_exe.write_text("binary")

    with patch("pathlib.Path.cwd", return_value=tmp_path):
        found = find_ytdlp(search_roots=[tmp_path])
        assert found is not None
        assert Path(found).resolve() == tool_exe.resolve()


def test_find_ytdlp_step3_bundled_root(tmp_path, monkeypatch):
    monkeypatch.delenv("YTDLP_PATH", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)

    exe_name = "yt-dlp.exe" if os.name == "nt" else "yt-dlp"
    tool_dir = tmp_path / "tools"
    tool_dir.mkdir(parents=True)
    tool_exe = tool_dir / exe_name
    tool_exe.write_text("binary")

    with patch("pathlib.Path.cwd", return_value=tmp_path):
        found = find_ytdlp(search_roots=[tmp_path])
        assert found is not None
        assert Path(found).resolve() == tool_exe.resolve()


def test_find_ytdlp_step4_system_path(monkeypatch):
    monkeypatch.delenv("YTDLP_PATH", raising=False)
    fake_path = "C:/System32/yt-dlp.exe" if os.name == "nt" else "/usr/bin/yt-dlp"
    monkeypatch.setattr("shutil.which", lambda name: fake_path if "yt-dlp" in name else None)

    with patch("pathlib.Path.is_file", return_value=False):
        found = find_ytdlp(search_roots=[])
        assert found is not None
        assert "yt-dlp" in found.lower()


def test_find_ytdlp_step5_winget_scoop(tmp_path, monkeypatch):
    monkeypatch.delenv("YTDLP_PATH", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)

    exe_name = "yt-dlp.exe"
    winget_dir = tmp_path / "Microsoft" / "WinGet" / "Links"
    winget_dir.mkdir(parents=True)
    winget_exe = winget_dir / exe_name
    winget_exe.write_text("winget binary")

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    if os.name == "nt":
        found = find_ytdlp(search_roots=[])
        assert found is not None
        assert Path(found).resolve() == winget_exe.resolve()


def test_build_ytdlp_download_command_formats():
    ytdlp = "yt-dlp"
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    out = Path("C:/cache/source.mp4")

    # 1080p
    cmd_1080 = build_ytdlp_download_command(ytdlp, url, out, quality="1080p")
    assert "-f" in cmd_1080
    f_idx = cmd_1080.index("-f")
    assert "height<=1080" in cmd_1080[f_idx + 1]
    assert "--merge-output-format" in cmd_1080
    assert "mp4" in cmd_1080

    # 720p
    cmd_720 = build_ytdlp_download_command(ytdlp, url, out, quality="720p")
    assert "height<=720" in cmd_720[cmd_720.index("-f") + 1]

    # Best
    cmd_best = build_ytdlp_download_command(ytdlp, url, out, quality="best")
    assert "bestvideo+bestaudio/best" in cmd_best[cmd_best.index("-f") + 1]

    # ffmpeg-location
    cmd_ffmpeg = build_ytdlp_download_command(
        ytdlp, url, out, ffmpeg_location="D:/tools/ffmpeg"
    )
    assert "--ffmpeg-location" in cmd_ffmpeg
    assert "D:/tools/ffmpeg" in cmd_ffmpeg


def test_build_ytdlp_download_command_opt_in_cookies():
    ytdlp = "yt-dlp"
    url = "https://www.youtube.com/watch?v=test"
    out = Path("C:/cache/source.mp4")

    # Public video: use_cookies=False -> MUST NOT contain --cookies-from-browser
    cmd_public = build_ytdlp_download_command(
        ytdlp, url, out, use_cookies=False, cookie_browser="chrome"
    )
    assert "--cookies-from-browser" not in cmd_public

    # Explicit opt-in: use_cookies=True with browser
    cmd_opt_in = build_ytdlp_download_command(
        ytdlp, url, out, use_cookies=True, cookie_browser="edge"
    )
    assert "--cookies-from-browser" in cmd_opt_in
    cookie_idx = cmd_opt_in.index("--cookies-from-browser")
    assert cmd_opt_in[cookie_idx + 1] == "edge"

    # use_cookies=True but empty browser -> no cookies flag
    cmd_empty = build_ytdlp_download_command(
        ytdlp, url, out, use_cookies=True, cookie_browser=""
    )
    assert "--cookies-from-browser" not in cmd_empty


def test_parse_ytdlp_progress_line():
    line1 = "[download]  45.2% of ~150.20MiB at 4.25MiB/s ETA 00:19"
    res1 = parse_ytdlp_progress_line(line1)
    assert res1 is not None
    assert res1["stage"] == "DOWNLOADING"
    assert res1["percent"] == 45.2
    assert res1["speed"] == "4.25MiB/s"
    assert res1["eta"] == "00:19"

    line2 = "[download] 100% of 150.20MiB in 00:35 at 4.29MiB/s"
    res2 = parse_ytdlp_progress_line(line2)
    assert res2 is not None
    assert res2["percent"] == 100.0

    line3 = "[Merger] Merging formats into 'source.mp4'"
    res3 = parse_ytdlp_progress_line(line3)
    assert res3 is not None
    assert res3["stage"] == "REMUXING"
    assert res3["percent"] == 100.0

    assert parse_ytdlp_progress_line("Random log output") is None
    assert parse_ytdlp_progress_line("") is None


def test_ytdlp_downloader_caching_hit(tmp_path):
    cache_dir = tmp_path / "cache" / "youtube" / "vid123"
    cache_dir.mkdir(parents=True)
    target = cache_dir / "source_vid123_1080p.mp4"
    target.write_bytes(b"0" * 4096)  # > 1KB dummy

    downloader = YtDlpDownloader(
        ytdlp_path="dummy_ytdlp", cache_root=tmp_path
    )
    # Mock validate_media_integrity to return True for our dummy
    with patch("vkdub.media.ytdlp.validate_media_integrity", return_value=True):
        cached = downloader.get_cached_source("vid123", "1080p")
        assert cached == target

        progress_calls = []
        result = downloader.download(
            video_url="https://youtube.com/watch?v=vid123",
            video_id="vid123",
            quality="1080p",
            progress_callback=progress_calls.append,
        )
        assert result == target
        assert len(progress_calls) == 1
        assert progress_calls[0]["cached"] is True


def test_ytdlp_downloader_execution_and_cancellation(tmp_path):
    downloader = YtDlpDownloader(ytdlp_path="fake_ytdlp", cache_root=tmp_path)

    # Subprocess execution error
    mock_proc = MagicMock()
    mock_proc.stdout.readline.side_effect = [
        "[download]  10.0% of 10.00MiB at 1.00MiB/s\n",
        "ERROR: Video unavailable\n",
        "",
    ]
    mock_proc.wait.return_value = 1
    mock_proc.returncode = 1
    mock_proc.poll.return_value = 1

    with patch("subprocess.Popen", return_value=mock_proc):
        with pytest.raises(RuntimeError, match="yt-dlp download failed"):
            downloader.download(
                video_url="https://youtube.com/watch?v=fail",
                video_id="fail",
            )

    # Cancellation check
    mock_proc_cancel = MagicMock()
    mock_proc_cancel.stdout.readline.side_effect = [
        "[download]  20.0%\n",
    ]
    with patch("subprocess.Popen", return_value=mock_proc_cancel):
        with pytest.raises(RuntimeError, match="cancelled"):
            downloader.download(
                video_url="https://youtube.com/watch?v=cancel",
                video_id="cancel",
                cancel_check=lambda: True,
            )


# ---------------------------------------------------------------------------
# Task 2 Tests: Hardware Acceleration Active Probe & Priority
# ---------------------------------------------------------------------------


def test_probe_encoder_active(monkeypatch):
    clear_hw_cache()

    # Success case
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert probe_encoder("ffmpeg.exe", "h264_nvenc") is True
        # Verify 1-frame probe arguments
        args = mock_run.call_args[0][0]
        assert "-f" in args and "lavfi" in args
        assert "color=s=256x256:d=0.04" in args
        assert "-frames:v" in args and "1" in args
        assert "-f" in args and "null" in args

    clear_hw_cache()
    # Failure case
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        assert probe_encoder("ffmpeg.exe", "h264_amf") is False


def test_resolve_best_encoder_nvenc_priority():
    clear_hw_cache()
    with patch("vkdub.media.hardware.probe_encoder") as mock_probe:
        # NVENC succeeds
        mock_probe.side_effect = lambda exe, enc: enc == "h264_nvenc"
        enc, params = resolve_best_encoder("ffmpeg.exe", codec_family="h264")
        assert enc == "h264_nvenc"
        assert "-cq" in params
        assert "18" in params
        assert "-rc" in params and "vbr" in params


def test_resolve_best_encoder_qsv_fallback():
    clear_hw_cache()
    with patch("vkdub.media.hardware.probe_encoder") as mock_probe:
        # NVENC fails, QSV succeeds
        mock_probe.side_effect = lambda exe, enc: enc == "h264_qsv"
        enc, params = resolve_best_encoder("ffmpeg.exe", codec_family="h264")
        assert enc == "h264_qsv"
        assert "-global_quality" in params
        assert "18" in params


def test_resolve_best_encoder_amf_fallback():
    clear_hw_cache()
    with patch("vkdub.media.hardware.probe_encoder") as mock_probe:
        # NVENC and QSV fail, AMF succeeds
        mock_probe.side_effect = lambda exe, enc: enc == "h264_amf"
        enc, params = resolve_best_encoder("ffmpeg.exe", codec_family="h264")
        assert enc == "h264_amf"
        assert "-rc" in params and "cqp" in params


def test_resolve_best_encoder_cpu_fallback():
    clear_hw_cache()
    with patch("vkdub.media.hardware.probe_encoder") as mock_probe:
        # All hardware encoders fail
        mock_probe.side_effect = lambda exe, enc: enc == "libx264"
        enc, params = resolve_best_encoder("ffmpeg.exe", codec_family="h264")
        assert enc == "libx264"
        assert "-crf" in params
        assert "18" in params


def test_resolve_best_encoder_hevc():
    clear_hw_cache()
    with patch("vkdub.media.hardware.probe_encoder") as mock_probe:
        mock_probe.side_effect = lambda exe, enc: enc == "hevc_nvenc"
        enc, params = resolve_best_encoder("ffmpeg.exe", codec_family="hevc")
        assert enc == "hevc_nvenc"


def test_hardware_encoder_detector_class():
    clear_hw_cache()
    detector = HardwareEncoderDetector(ffmpeg_exe="ffmpeg.exe")
    with patch("vkdub.media.hardware.probe_encoder", return_value=True):
        enc, params = detector.detect("h264")
        assert enc == "h264_nvenc"
        assert detector.is_hardware_accelerated(enc) is True
        assert detector.is_hardware_accelerated("libx264") is False


# ---------------------------------------------------------------------------
# Task 3 Tests: Clip Engine, Sanitization, Timecodes & Trimming
# ---------------------------------------------------------------------------


def test_sanitize_filename_windows_illegal_chars():
    dirty = 'Video: "Best / Worst" <2026> | Part? *Test*'
    clean = sanitize_filename(dirty)
    assert ":" not in clean
    assert '"' not in clean
    assert "/" not in clean
    assert "<" not in clean
    assert ">" not in clean
    assert "|" not in clean
    assert "?" not in clean
    assert "*" not in clean


def test_sanitize_filename_reserved_words():
    for reserved in ["CON", "prn", "Aux", "nul", "COM1", "com9", "LPT1", "lpt9"]:
        clean = sanitize_filename(reserved)
        assert clean.startswith("_")
        clean_with_ext = sanitize_filename(f"{reserved}.mp4")
        assert clean_with_ext.startswith("_")


def test_sanitize_filename_trailing_dots_spaces_and_truncation():
    name = "My Long Title with trailing dots and spaces...   "
    clean = sanitize_filename(name, max_length=20)
    assert len(clean) <= 20
    assert not clean.endswith(".")
    assert not clean.endswith(" ")

    # Empty string fallback
    assert sanitize_filename("") == "clip"
    assert sanitize_filename("   ...  ") == "clip"


def test_build_clip_and_merged_filename():
    clip_fn = build_clip_filename(
        video_title="Amazing: Title!",
        clip_index=2,
        start_sec=10.5,
        end_sec=25.0,
        container="mp4",
    )
    assert clip_fn.startswith("Amazing_ Title!_clip_2_")
    assert clip_fn.endswith(".mp4")
    assert "10.5s-25s" in clip_fn

    merged_fn = build_merged_filename(video_title="Amazing: Title!", container="mkv")
    assert merged_fn == "Amazing_ Title!_selected_clips.mkv"


def test_parse_timecode():
    assert parse_timecode(12.5) == 12.5
    assert parse_timecode("12.5") == 12.5
    assert parse_timecode("12s") == 12.0
    assert parse_timecode("05:30.500") == 330.5
    assert parse_timecode("01:02:03.456") == 3723.456
    assert parse_timecode("00:00:10") == 10.0

    with pytest.raises(ValueError):
        parse_timecode(-5)
    with pytest.raises(ValueError):
        parse_timecode("-00:05")
    with pytest.raises(ValueError):
        parse_timecode("invalid_time")
    with pytest.raises(ValueError):
        parse_timecode("")


def test_format_timecode():
    assert format_timecode(3723.456, include_ms=True) == "01:02:03.456"
    assert format_timecode(135.0, include_ms=False) == "00:02:15"
    assert format_timecode(0.0) == "00:00:00.000"


def test_build_stream_copy_trim_command():
    ffmpeg = "ffmpeg.exe"
    src = Path("C:/video.mp4")
    out = Path("C:/clip1.mp4")
    cmd = build_stream_copy_trim_command(ffmpeg, src, out, 5.0, 15.0)

    assert cmd[0] == ffmpeg
    assert "-ss" in cmd and "5.000" in cmd
    assert "-to" in cmd and "15.000" in cmd
    assert "-i" in cmd and str(src) in cmd
    assert "-c" in cmd and "copy" in cmd
    assert "-avoid_negative_ts" in cmd and "make_zero" in cmd
    assert "-movflags" in cmd and "+faststart" in cmd
    assert cmd[-1] == str(out)


def test_build_frame_accurate_trim_command():
    ffmpeg = "ffmpeg.exe"
    src = Path("C:/video.mp4")
    out = Path("C:/clip1.mp4")
    cmd = build_frame_accurate_trim_command(
        ffmpeg,
        src,
        out,
        5.0,
        15.0,
        encoder_name="h264_nvenc",
        encoder_args=["-cq", "18", "-preset", "p5"],
    )

    assert "-c:v" in cmd and "h264_nvenc" in cmd
    assert "-cq" in cmd and "18" in cmd
    assert "-c:a" in cmd and "aac" in cmd
    assert "-b:a" in cmd and "192k" in cmd
    assert "-movflags" in cmd and "+faststart" in cmd


def test_concat_manifest_and_command(tmp_path):
    clips = [tmp_path / "clip1.mp4", tmp_path / "clip2.mp4"]
    for c in clips:
        c.write_text("dummy")

    manifest = tmp_path / "manifest.txt"
    create_concat_manifest(clips, manifest)

    content = manifest.read_text(encoding="utf-8")
    assert "ffconcat version 1.0" in content
    assert f"file '{clips[0].as_posix()}'" in content
    assert f"file '{clips[1].as_posix()}'" in content

    out = tmp_path / "merged.mp4"
    cmd = build_concat_command("ffmpeg.exe", manifest, out)
    assert "-f" in cmd and "concat" in cmd
    assert "-safe" in cmd and "0" in cmd
    assert "-c" in cmd and "copy" in cmd
    assert cmd[-1] == str(out)


def test_clip_engine_trim_and_merge(tmp_path):
    engine = ClipEngine(ffmpeg_exe="ffmpeg.exe")

    # Validation: start >= end
    with pytest.raises(ValueError, match="Start time.*must be strictly less"):
        engine.trim_clip(tmp_path / "src.mp4", tmp_path / "out.mp4", 10.0, 5.0)

    # Empty clip_paths for merge
    with pytest.raises(ValueError, match="clip_paths cannot be empty"):
        engine.merge_clips([], tmp_path / "merged.mp4")

    # Mocked trim execution
    src = tmp_path / "src.mp4"
    src.write_text("src")
    out = tmp_path / "out.mp4"

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")
    mock_proc.returncode = 0
    # Create output file so engine sees it
    def fake_communicate(*args, **kwargs):
        out.write_text("trimmed")
        return ("", "")

    mock_proc.communicate = fake_communicate

    with patch("subprocess.Popen", return_value=mock_proc):
        res = engine.trim_clip(src, out, 0.0, 5.0, cut_mode="STREAM_COPY")
        assert res == out
        assert out.is_file()


def test_kill_process_tree():
    # Calling kill_process_tree with an invalid PID should not crash
    kill_process_tree(999999)


# ---------------------------------------------------------------------------
# Real FFmpeg Integration Test (Uses bundled tools/ffmpeg.exe if present)
# ---------------------------------------------------------------------------


def test_real_ffmpeg_end_to_end_trim_and_merge(tmp_path):
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg or not Path(ffmpeg).is_file():
        pytest.skip("FFmpeg executable not available for real integration test")

    # 1. Generate a tiny 1-second synthetic video with audio using lavfi
    src_video = tmp_path / "synthetic_source.mp4"
    gen_cmd = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=2.0:size=320x240:rate=24",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=1000:duration=2.0",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-c:a",
        "aac",
        str(src_video),
    ]
    res = subprocess.run(gen_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if res.returncode != 0:
        pytest.skip("Failed to generate test video with FFmpeg")

    engine = ClipEngine(ffmpeg_exe=ffmpeg)

    # 2. Trim clip 1 (Stream Copy): 0.0s to 1.0s
    clip1 = tmp_path / "clip1.mp4"
    engine.trim_clip(src_video, clip1, start_sec=0.0, end_sec=1.0, cut_mode="STREAM_COPY")
    assert clip1.is_file() and clip1.stat().st_size > 0

    # 3. Trim clip 2 (Frame Accurate): 1.0s to 2.0s
    clip2 = tmp_path / "clip2.mp4"
    engine.trim_clip(
        src_video, clip2, start_sec=1.0, end_sec=2.0, cut_mode="FRAME_ACCURATE"
    )
    assert clip2.is_file() and clip2.stat().st_size > 0

    # 4. Merge clips 1 & 2
    merged = tmp_path / "merged_output.mp4"
    engine.merge_clips([clip1, clip2], merged)
    assert merged.is_file() and merged.stat().st_size > 0


def test_format_timecode_for_filename():
    assert format_timecode_for_filename(90.0) == "01m30s"
    assert format_timecode_for_filename(10.5) == "10.5s"
    assert format_timecode_for_filename(3665.0) == "01h01m05s"


def test_get_encoder_params():
    params = get_encoder_params("h264_nvenc")
    assert "-cq" in params
    assert "18" in params
    unknown = get_encoder_params("unknown_codec")
    assert "-crf" in unknown


def test_get_youtube_cache_dir_and_validate_media(tmp_path):
    cdir = get_youtube_cache_dir("vid_test", custom_base=tmp_path)
    assert cdir.is_dir()
    assert cdir.name == "vid_test"

    non_file = tmp_path / "nonexistent.mp4"
    assert validate_media_integrity(non_file) is False

    tiny_file = tmp_path / "tiny.mp4"
    tiny_file.write_bytes(b"small")
    assert validate_media_integrity(tiny_file) is False
