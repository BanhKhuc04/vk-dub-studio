import wave
from pathlib import Path

import pytest

from vkdub.domain.mask import MaskItem
from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.domain.voice import VoiceAsset, VoiceSettings
from vkdub.media.process import find_tool
from vkdub.services.audio_mix_service import (
    build_audio_mix_filter,
    build_speech_track_wav,
    fit_voice_wav,
)
from vkdub.services.render_service import (
    RenderConfig,
    build_render_command,
    escape_ffmpeg_filter_path,
    parse_ffmpeg_progress,
)
from vkdub.ui.export_dialog import ExportDialog


def test_escape_ffmpeg_filter_path():
    p = Path("C:/Users/test/subtitles.ass")
    escaped = escape_ffmpeg_filter_path(p)
    assert "C\\:/" in escaped or "c\\:/" in escaped.lower()
    assert "'" not in escaped or "\\'" in escaped


def test_build_audio_mix_filter():
    # Ducking active
    f1 = build_audio_mix_filter(original_volume=0.2, voice_volume=1.0, has_original_audio=True)
    assert "[0:a]volume=0.20[aorig]" in f1
    assert "[1:a]volume=1.00[avoice]" in f1
    assert "amix=inputs=2" in f1

    # Original audio muted
    f2 = build_audio_mix_filter(original_volume=0.0, voice_volume=1.0, has_original_audio=True)
    assert f2 == "[1:a]volume=1.00[aout]"

    # No original audio in video
    f3 = build_audio_mix_filter(original_volume=0.2, voice_volume=1.0, has_original_audio=False)
    assert f3 == "[1:a]volume=1.00[aout]"


def test_parse_ffmpeg_progress():
    line = (
        "frame=  120 fps= 24 q=28.0 size=    1024kB time=00:00:05.50 "
        "bitrate=1524.0kbits/s speed=1.2x"
    )
    pct = parse_ffmpeg_progress(line, total_duration_s=10.0)
    assert pct is not None
    assert round(pct, 1) == 55.0

    # No match line
    assert parse_ffmpeg_progress("Some log line without time", 10.0) is None


def test_build_speech_track_wav(tmp_path):
    # Create fake WAV chunk
    chunk_wav = tmp_path / "chunk.wav"
    with wave.open(str(chunk_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        # 1 second of audio = 24000 samples = 48000 bytes
        wf.writeframes(b"\x00\x01" * 24000)

    from uuid import uuid4

    from vkdub.domain.voice import audio_key, digest, normalized_text

    settings = VoiceSettings()
    line = ScriptLine(id=str(uuid4()), start_ms=1000, end_ms=2000, text="Xin chào")
    script = ScriptDocument(lines=(line,))
    asset = VoiceAsset(
        cache_key=audio_key(line.text, settings),
        text_hash=digest(normalized_text(line.text)),
        provider=settings.provider,
        voice_id=settings.voice_id,
        speed=settings.speed,
        duration_ms=1000,
        output_path=chunk_wav,
        audio_sha256="0" * 64,
        generated_at="2026-09-04T12:00:00+00:00",
    )
    fake_vid = tmp_path / "video.mp4"
    fake_vid.write_bytes(b"vid")
    project = Project(
        voice=settings,
        video_path=fake_vid,
        video_duration_ms=5000,
        script=script,
        voice_assets={line.id: asset},
    )
    project.approve(True)

    out_speech = tmp_path / "speech.wav"
    result_path = build_speech_track_wav(project, out_speech, total_duration_ms=3000)
    assert result_path.is_file()

    with wave.open(str(result_path), "rb") as out_wf:
        assert out_wf.getframerate() == 24000
        assert out_wf.getnchannels() == 1
        # 3 seconds = 72000 frames
        assert out_wf.getnframes() == 72000


def test_fit_voice_wav_keeps_48khz_and_fits_slot_without_pitch_resampling(tmp_path):
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg is not installed")
    source = tmp_path / "long-voice.wav"
    with wave.open(str(source), "wb") as output:
        output.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        output.writeframes(b"\0\0" * 96000)
    target = tmp_path / "fitted.wav"
    duration_ms = fit_voice_wav(source, target, str(ffmpeg), 1000)
    with wave.open(str(target), "rb") as fitted:
        assert fitted.getframerate() == 48000
        assert fitted.getnchannels() == 1
        assert fitted.getsampwidth() == 2
        actual_ms = round(fitted.getnframes() * 1000 / fitted.getframerate())
    assert 950 <= actual_ms <= 1000
    assert duration_ms == actual_ms


def test_build_render_command(tmp_path):
    vid = tmp_path / "video.mp4"
    vid.write_bytes(b"mp4data")
    speech_wav = tmp_path / "speech.wav"
    speech_wav.write_bytes(b"wavdata")
    ass_file = tmp_path / "sub.ass"
    ass_file.write_bytes(b"assdata")

    mask = MaskItem(name="Mask 1", mask_type="solid", x=0.1, y=0.8, width=0.8, height=0.1)
    project = Project(video_path=vid, masks=[mask])

    config = RenderConfig(
        output_path=tmp_path / "out.mp4",
        burn_subtitles=True,
        apply_masks=True,
        original_volume=0.2,
        voice_volume=1.0,
    )

    cmd = build_render_command(
        project=project,
        config=config,
        speech_wav_path=speech_wav,
        ass_subtitle_path=ass_file,
        ffmpeg_exe="ffmpeg",
        video_width=1920,
        video_height=1080,
        has_original_audio=True,
    )

    assert "ffmpeg" in cmd[0]
    assert "-i" in cmd
    assert str(vid) in cmd
    assert str(speech_wav) in cmd
    assert "-vf" in cmd
    # Video filters must contain drawbox and ass
    vf_index = cmd.index("-vf")
    vf_arg = cmd[vf_index + 1]
    assert "drawbox=" in vf_arg
    assert "ass=" in vf_arg
    assert "-filter_complex" in cmd
    assert str(config.output_path) in cmd


def test_export_dialog_checklist(qtbot, tmp_path):
    dialog = ExportDialog()
    qtbot.addWidget(dialog)

    # Initially not ready
    assert dialog.btn_start.isEnabled() is False

    # Simulate ready project
    vid = tmp_path / "sample.mp4"
    vid.write_bytes(b"vid")
    chunk = tmp_path / "voice.wav"
    chunk.write_bytes(b"RIFF")

    from uuid import uuid4

    from vkdub.domain.voice import audio_key, digest, normalized_text

    settings = VoiceSettings()
    line = ScriptLine(id=str(uuid4()), start_ms=0, end_ms=1000, text="Chào bạn")
    script = ScriptDocument(lines=(line,))
    asset = VoiceAsset(
        cache_key=audio_key(line.text, settings),
        text_hash=digest(normalized_text(line.text)),
        provider=settings.provider,
        voice_id=settings.voice_id,
        speed=settings.speed,
        duration_ms=1000,
        output_path=chunk,
        audio_sha256="0" * 64,
        generated_at="2026-09-04T12:00:00+00:00",
    )
    project = Project(
        voice=settings,
        video_path=vid,
        video_duration_ms=5000,
        script=script,
        voice_assets={line.id: asset},
    )
    project.approve(True)

    dialog.update_checklist(project=project, ffmpeg_available=True)
    assert dialog.btn_start.isEnabled() is True
