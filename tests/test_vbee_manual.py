"""Tests for manual Vbee workflow (exporting SRT and importing manual audio)."""

import wave
from pathlib import Path

import pytest

from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.integrations.vbee.importer import slice_and_import_vbee_audio
from vkdub.media.process import find_tool


class DummyMainWindow:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.busy = False
        self.dirty = False
        self.tools = type(
            "Tools",
            (),
            {
                "paths": {
                    "ffmpeg": find_tool("ffmpeg") or "ffmpeg",
                    "ffprobe": find_tool("ffprobe") or "ffprobe",
                }
            },
        )()
        self.left = type(
            "Left",
            (),
            {
                "stop_button": type(
                    "Btn",
                    (),
                    {
                        "setEnabled": lambda self, v: None,
                        "clicked": type("Sig", (), {"connect": lambda self, f: None})(),
                    },
                )(),
                "job_progress": type("Bar", (), {"setValue": lambda self, v: None})(),
            },
        )()

    def log(self, msg: str) -> None:
        pass

    def _error(self, msg: str) -> None:
        pass

    def _refresh(self) -> None:
        pass


def _create_wav(path: Path, duration_sec: float = 3.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(b"\x00\x00" * int(duration_sec * 24000))
    return path


@pytest.mark.anyio
async def test_manual_vbee_workflow_flow(tmp_path: Path) -> None:
    ffmpeg = find_tool("ffmpeg")
    ffprobe = find_tool("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("Requires FFmpeg and ffprobe.")

    video = tmp_path / "vid.mp4"
    video.write_bytes(b"\x00" * 1024)
    lines = (
        ScriptLine.new(0, 1500, "Chào mừng đến với VK Dub Studio."),
        ScriptLine.new(1600, 3200, "Thử nghiệm lồng tiếng thủ công Vbee."),
    )
    project = Project(
        video_path=video,
        target_language="vi",
        script=ScriptDocument(lines),
    )
    project.approve(True)

    master_audio = _create_wav(tmp_path / "vbee_manual_master.wav", 4.0)

    result = await slice_and_import_vbee_audio(
        project=project,
        downloaded_audio=master_audio,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        voice_id="vbee_manual",
        display_name="Vbee (Thủ công)",
    )

    assert result["lines_count"] == 2
    assert project.voice.provider == "vbee"
    assert project.voice.voice_id == "vbee_manual"
    assert project.voice.display_name == "Vbee (Thủ công)"
    assert project.voice_ready is True
    assert len(project.current_voices()) == 2
