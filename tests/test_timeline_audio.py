from vkdub.media.timeline_audio import _ffprobe_executable, build_master_timeline_audio


def test_ffprobe_is_resolved_beside_ffmpeg_without_changing_parent_folder():
    ffmpeg = r"C:\tools\ffmpeg-8.1\bin\ffmpeg.exe"

    assert _ffprobe_executable(ffmpeg) == r"C:\tools\ffmpeg-8.1\bin\ffprobe.exe"


def test_master_audio_is_fitted_and_trimmed_to_video_duration(monkeypatch, tmp_path):
    source = tmp_path / "voice.mp3"
    source.write_bytes(b"ID3" + b"x" * 2048)
    srt = tmp_path / "script.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:01:03,560\nXin chào\n",
        encoding="utf-8",
    )
    output = tmp_path / "timeline.mp3"
    calls: list[list[str]] = []

    monkeypatch.setattr(
        "vkdub.media.timeline_audio.get_audio_duration_ms", lambda *_: 66_872
    )

    def fake_run(command, **_kwargs):
        calls.append(command)
        output.write_bytes(b"ID3" + b"y" * 2048)

    monkeypatch.setattr("vkdub.media.timeline_audio.subprocess.run", fake_run)

    result = build_master_timeline_audio(source, srt, output, total_duration_ms=63_646)

    assert result == output
    filter_value = calls[0][calls[0].index("-filter_complex") + 1]
    assert "atempo=" not in filter_value
    assert "atrim=start=0:end=63.646" in filter_value
    assert "apad=whole_dur=63.646" in filter_value
