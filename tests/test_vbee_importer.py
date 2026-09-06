"""Tests for audio validation, slicing, and VoiceAsset import for Vbee Dubbing."""

import wave
from pathlib import Path

import pytest

from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.integrations.vbee.errors import VbeeImportError
from vkdub.integrations.vbee.importer import (
    slice_and_import_vbee_audio,
    validate_downloaded_audio,
)
from vkdub.media.process import find_tool
from vkdub.services.project_service import load_project, save_project


def _create_synthetic_wav(
    path: Path, duration_seconds: float = 3.0, sample_rate: int = 24000
) -> Path:
    """Generate a valid PCM 16-bit mono WAV file for testing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    num_frames = int(duration_seconds * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_frames)
    return path


def test_validate_downloaded_audio_checks(tmp_path: Path) -> None:
    """Verify validation detects missing, empty, or wrong extension files."""
    # Missing file
    with pytest.raises(VbeeImportError, match="không tồn tại"):
        validate_downloaded_audio(tmp_path / "missing.mp3")

    # Tiny file (< 2048 bytes)
    tiny = tmp_path / "tiny.mp3"
    tiny.write_bytes(b"short")
    with pytest.raises(VbeeImportError, match="quá nhỏ"):
        validate_downloaded_audio(tiny)

    # Invalid extension
    bad_ext = tmp_path / "file.txt"
    bad_ext.write_bytes(b"\x00" * 4096)
    with pytest.raises(VbeeImportError, match="không được hỗ trợ"):
        validate_downloaded_audio(bad_ext)

    # Valid file
    valid = _create_synthetic_wav(tmp_path / "valid.wav", duration_seconds=1.0)
    assert validate_downloaded_audio(valid) == valid


@pytest.mark.anyio
async def test_slice_and_import_vbee_audio_and_persistence(tmp_path: Path) -> None:
    """Verify slicing audio creates valid VoiceAssets and project persists and reloads them."""
    ffmpeg = find_tool("ffmpeg")
    ffprobe = find_tool("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("Cần FFmpeg và ffprobe để chạy test cắt audio thực tế.")

    # 1. Setup project with approved script
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\x00" * 1024)

    lines = (
        ScriptLine.new(0, 1500, "Câu thứ nhất."),
        ScriptLine.new(1600, 3000, "Câu thứ hai."),
    )
    project = Project(
        video_path=video,
        target_language="vi",
        script=ScriptDocument(lines),
    )
    project.approve(True)

    # 2. Create synthetic 4-second WAV
    master_audio = _create_synthetic_wav(tmp_path / "vbee_download.wav", duration_seconds=4.0)

    # 3. Import and slice
    out_dir = tmp_path / "sliced_voice"
    result = await slice_and_import_vbee_audio(
        project=project,
        downloaded_audio=master_audio,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        output_dir=out_dir,
    )

    assert result["lines_count"] == 2
    assert project.voice.provider == "vbee"
    assert project.voice.voice_id == "vbee_studio"
    assert len(project.voice_assets) == 2

    # Verify voice_ready is satisfied
    assert project.voice_ready is True
    current_voices = project.current_voices()
    assert len(current_voices) == 2
    for line in lines:
        asset = current_voices.get(line.id)
        assert asset is not None
        assert asset.output_path.is_file()
        assert asset.duration_ms > 0

    # 4. Verify Project persistence roundtrip (save and load)
    project_file = tmp_path / "my_project.vkdub"
    save_project(project, project_file)
    assert project_file.is_file()

    loaded = load_project(project_file)
    assert loaded.voice.provider == "vbee"
    assert loaded.voice_ready is True
    assert len(loaded.voice_assets) == 2
    assert loaded.current_voice(lines[0].id) is not None
