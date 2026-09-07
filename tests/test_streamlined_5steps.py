"""Unit and integration tests for the streamlined 5-step workflow."""

from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.services.capcut_export import export_capcut_project
from vkdub.services.chatgpt_bridge import (
    export_original_srt,
    import_translated_srt,
    prepare_chatgpt_translation,
)


def test_export_and_import_chatgpt_srt(tmp_path: Path):
    line1_id = str(uuid4())
    line2_id = str(uuid4())
    project = Project(
        video_path=tmp_path / "sample.mp4",
        output_directory=tmp_path / "output",
        script=ScriptDocument(
            lines=(
                ScriptLine(id=line1_id, start_ms=0, end_ms=2000, text="Hello world"),
                ScriptLine(id=line2_id, start_ms=2500, end_ms=5000, text="Welcome to VK Dub"),
            )
        ),
    )

    # 1. Export original SRT
    srt_file = export_original_srt(project, tmp_path)
    assert srt_file.is_file()
    content = srt_file.read_text(encoding="utf-8")
    assert "Hello world" in content
    assert "00:00:00,000 --> 00:00:02,000" in content

    # 2. Mock prepare_chatgpt_translation
    with (
        patch("vkdub.services.chatgpt_bridge.open_chatgpt_in_default_browser") as mock_open,
        patch("vkdub.services.chatgpt_bridge.reveal_in_explorer"),
        patch("vkdub.services.chatgpt_bridge.copy_to_clipboard") as mock_clip,
    ):
        mock_open.return_value = True
        mock_clip.return_value = True
        p_srt, prompt = prepare_chatgpt_translation(project)
        assert p_srt.is_file()
        assert "Dịch lại toàn bộ file phụ đề SRT này sang tiếng Việt" in prompt
        assert "Hello world" in prompt
        mock_open.assert_called_once()
        mock_clip.assert_called_once()

    # 3. Import translated SRT
    translated_content = (
        "1\n00:00:00,000 --> 00:00:02,000\nXin chào thế giới\n\n"
        "2\n00:00:02,500 --> 00:00:05,000\nChào mừng đến với VK Dub\n\n"
    )
    trans_file = tmp_path / "translated.srt"
    trans_file.write_text(translated_content, encoding="utf-8")

    doc = import_translated_srt(project, trans_file)
    assert len(doc.lines) == 2
    assert doc.lines[0].text == "Xin chào thế giới"
    assert doc.lines[1].text == "Chào mừng đến với VK Dub"
    assert project.script == doc
    assert project.target_language == "vi"


def test_master_voice_intact_audio_in_capcut_export(tmp_path: Path):
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"dummy mp4 video bytes")
    audio_path = tmp_path / "master_vbee.wav"
    audio_path.write_bytes(
        b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )

    draft_root = tmp_path / "drafts"
    draft_root.mkdir()

    line1_id = str(uuid4())
    line2_id = str(uuid4())
    script = ScriptDocument(
        lines=(
            ScriptLine(id=line1_id, start_ms=0, end_ms=2500, text="Câu thoại thứ nhất"),
            ScriptLine(id=line2_id, start_ms=3000, end_ms=5500, text="Câu thoại thứ hai"),
        )
    )

    project = Project(
        video_path=video_path,
        output_directory=tmp_path / "out",
        video_duration_ms=6000,
        script=script,
        master_voice_path=audio_path,
    )
    project.approved_revision_hash = project.revision_hash
    assert project.voice_ready is True

    # Mock FFprobe
    with patch("vkdub.services.capcut_export._probe_video") as mock_probe:
        # width, height, duration_ms, has_audio
        mock_probe.return_value = (1920, 1080, 6000, True)

        res = export_capcut_project(
            project=project,
            draft_root=draft_root,
            ffprobe="ffprobe",
            name="Test Intact Voice Draft",
        )
        assert res.path.is_dir()
        assert res.audio_segments == 1
        assert res.caption_segments == 2
        content_file = res.path / "draft_content.json"
        assert content_file.is_file()
        import json

        content = json.loads(content_file.read_text(encoding="utf-8"))

        tracks = content.get("tracks", [])
        assert len(tracks) >= 3  # Video, Audio, Subtitle

        # Audio track should contain exactly 1 intact segment spanning the duration
        audio_track = next(
            (t for t in tracks if t.get("name") == "VOICE TIẾNG VIỆT — ĐÃ DỊCH"), None
        )
        assert audio_track is not None
        assert len(audio_track["segments"]) == 1  # 1 intact segment, NOT 2 chopped slices!

        # Subtitle track should contain 2 segments for the 2 lines
        text_track = next((t for t in tracks if t.get("name") == "PHỤ ĐỀ TIẾNG VIỆT"), None)
        assert text_track is not None
        assert len(text_track["segments"]) == 2
