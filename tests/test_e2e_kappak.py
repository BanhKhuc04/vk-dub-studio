"""Tier 3 & Tier 4 E2E Test Suite: Pipeline Simulation & Output Export Integrity.

Covers:
- Tier 3: 5-Step workflow lifecycle simulation (Video -> Voice -> Mask -> Pipeline -> Review)
- Tier 3: PipelineRunner signal contracts (substep_updated, state_changed, artifact_ready, etc.)
- Tier 3: Regression prevention: verification that invalid signals from Survey 2 are removed
- Tier 3: Approved revision hash computation, tampering invalidation, and re-approval
- Tier 3: Checkpoint atomic persistence and recovery without re-running completed steps
- Tier 4: Authentic MP4 render command verification (audio ducking amix, mask filter, ass subtitles)
- Tier 4: Rejection of raw video copy fallback when narration audio is present
- Tier 4: Authentic CapCut draft folder structure (draft_content.json, video/audio/text tracks)
- Tier 4: CapCut export strict rejection on unapproved projects or missing voices
- Tier 4: Windows path escaping (colons, apostrophes, spaces, Vietnamese Unicode diacritics)
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest

from vkdub.bridge.local_agent import LocalAgent
from vkdub.domain.mask import MaskItem
from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.domain.voice import VoiceSettings
from vkdub.orchestrator.checkpoint import load_checkpoint, save_checkpoint
from vkdub.orchestrator.pipeline_runner import PipelineRunner
from vkdub.orchestrator.pipeline_state import (
    ArtifactRegistry,
    PipelineState,
    SubstepInfo,
    SubstepStatus,
)
from vkdub.services.capcut_export import export_capcut_project
from vkdub.services.render_service import (
    RenderConfig,
    build_render_command,
    escape_ffmpeg_filter_path,
)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def sample_video(tmp_path: Path) -> Path:
    """Provide a verified video file path for testing."""
    real_video = Path("docs/evidence/media/sample.mp4")
    if real_video.is_file():
        return real_video.resolve()
    # Fallback to dummy MP4 in tmp_path
    dummy = tmp_path / "sample_test.mp4"
    dummy.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42")
    return dummy


@pytest.fixture
def master_audio(tmp_path: Path) -> Path:
    """Provide a valid WAV file for master narration."""
    audio_file = tmp_path / "master_narration.wav"
    # Write canonical RIFF WAV header (44 bytes, 24kHz mono 16-bit)
    header = (
        b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"\xc0]\x00\x00\x80\xbb\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )
    audio_file.write_bytes(header)
    return audio_file


@pytest.fixture
def sample_script() -> ScriptDocument:
    """Provide a canonical 2-line Vietnamese dubbed script."""
    return ScriptDocument(
        lines=(
            ScriptLine(
                id=str(uuid4()),
                start_ms=500,
                end_ms=2500,
                text="Chào mừng bạn đến với KAPPAK Studio Web v2.",
            ),
            ScriptLine(
                id=str(uuid4()),
                start_ms=3000,
                end_ms=5500,
                text="Hệ thống lồng tiếng tự động 1 chạm phong cách Apple.",
            ),
        )
    )


# ===========================================================================
# Tier 3: 5-Step Pipeline Simulation & Signal Wiring Tests
# ===========================================================================

def test_e2e_5step_workflow_simulation(
    tmp_path: Path, sample_video: Path, master_audio: Path, sample_script: ScriptDocument
):
    """Simulate complete 5-step lifecycle from video ingestion to approved export."""
    # Step 1: Video Ingestion
    project = Project(
        video_path=sample_video,
        video_duration_ms=6000,
        output_directory=tmp_path / "output",
    )
    assert project.video_path.is_file()
    assert project.duration_ms == 6000

    # Step 2: Voice Configuration
    project.voice = VoiceSettings(
        provider="vbee",
        voice_id="vbee-ngoc-huyen",
        speed=1.1,
    )
    assert project.voice.voice_id == "vbee-ngoc-huyen"

    # Step 3: Blur Regions
    mask = MaskItem(
        id="mask_sub_bottom",
        mask_type="erase",
        x=0.08,
        y=0.82,
        width=0.84,
        height=0.14,
    )
    project.masks = [mask]
    assert len(project.masks) == 1

    # Step 4: Pipeline Execution Simulation
    project.script = sample_script
    project.master_voice_path = master_audio

    # Verify initial unapproved state
    assert project.is_approved is False
    assert project.voice_ready is False

    # Step 5: Review & Approval
    revision = project.approve(True)
    assert revision is not None
    assert project.is_approved is True
    assert project.approved_revision_hash == project.revision_hash
    assert project.voice_ready is True
    assert project.state == "VOICE_READY"


def test_pipeline_runner_signal_contracts():
    """Verify that PipelineRunner defines all valid signals and NO invalid signals."""
    # Valid signals expected by backend and websocket architecture
    expected_signals = [
        "state_changed",
        "substep_updated",
        "artifact_ready",
        "log_emitted",
        "pipeline_completed",
        "pipeline_failed",
        "pipeline_cancelled",
    ]
    for sig_name in expected_signals:
        assert hasattr(PipelineRunner, sig_name), f"Missing expected signal: {sig_name}"

    # Regression test for Survey Report 2: runner.overall_progress & runner.pipeline_finished
    # were obsolete signals that caused AttributeError crashes in server.py
    assert not hasattr(
        PipelineRunner, "overall_progress"
    ), "overall_progress must not exist on PipelineRunner (replaced by substep_updated)"
    assert not hasattr(
        PipelineRunner, "pipeline_finished"
    ), "pipeline_finished must not exist on PipelineRunner (replaced by pipeline_completed)"


def test_pipeline_runner_signal_emission_mock(tmp_path: Path, sample_video: Path):
    """Test connecting slots to PipelineRunner signals and verifying emission payload types."""
    project = Project(video_path=sample_video)
    mock_agent = MagicMock(spec=LocalAgent)
    runner = PipelineRunner(
        project=project,
        local_agent=mock_agent,
        output_dir=tmp_path / "export",
    )

    received_substeps = []
    received_states = []
    received_artifacts = []

    def on_substep(step_id, status, progress, message):
        received_substeps.append((step_id, status, progress, message))

    def on_state(new_state, msg):
        received_states.append((new_state, msg))

    def on_artifact(key, path):
        received_artifacts.append((key, path))

    runner.substep_updated.connect(on_substep)
    runner.state_changed.connect(on_state)
    runner.artifact_ready.connect(on_artifact)

    # Emit simulated signals
    runner.substep_updated.emit("4.1", SubstepStatus.RUNNING, 50, "Bóc băng 50%")
    runner.state_changed.emit(PipelineState.TRANSCRIBING, "Đang bóc băng...")
    test_srt = tmp_path / "original.srt"
    test_srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello", encoding="utf-8")
    runner.artifact_ready.emit("original_srt", test_srt)

    assert len(received_substeps) == 1
    assert received_substeps[0] == ("4.1", SubstepStatus.RUNNING, 50, "Bóc băng 50%")
    assert len(received_states) == 1
    assert received_states[0][0] == PipelineState.TRANSCRIBING
    assert len(received_artifacts) == 1
    assert received_artifacts[0] == ("original_srt", test_srt)


def test_revision_hash_tamper_invalidation(sample_video: Path, sample_script: ScriptDocument):
    """Modifying script content or timing invalidates approval until explicitly re-approved."""
    project = Project(
        video_path=sample_video,
        video_duration_ms=6000,
        script=sample_script,
    )
    # 1. Approve
    initial_hash = project.approve(True)
    assert project.is_approved is True
    assert project.approved_revision_hash == initial_hash

    # 2. Tamper with script text
    modified_lines = list(sample_script.lines)
    modified_lines[0] = ScriptLine(
        id=modified_lines[0].id,
        start_ms=modified_lines[0].start_ms,
        end_ms=modified_lines[0].end_ms,
        text="Văn bản đã bị chỉnh sửa!",
    )
    project.script = ScriptDocument(lines=tuple(modified_lines))

    # Revision hash must change and invalidate approval
    assert project.revision_hash != initial_hash
    assert project.is_approved is False

    # 3. Re-approve
    new_hash = project.approve(True)
    assert new_hash == project.revision_hash
    assert project.is_approved is True


def test_pipeline_checkpoint_persistence(tmp_path: Path, sample_video: Path):
    """Pipeline state and artifact registry save and recover atomically from checkpoint."""
    artifacts = ArtifactRegistry(
        source_video=sample_video,
        original_srt=tmp_path / "orig.srt",
        translated_srt=tmp_path / "trans.srt",
    )
    substeps = [
        SubstepInfo(id="4.1", name="Whisper", status=SubstepStatus.SUCCESS, progress=100),
        SubstepInfo(id="4.2", name="Translation", status=SubstepStatus.SUCCESS, progress=100),
        SubstepInfo(id="4.3", name="Script", status=SubstepStatus.PENDING, progress=0),
        SubstepInfo(id="4.4", name="Voice", status=SubstepStatus.PENDING, progress=0),
    ]

    # Save checkpoint
    saved_file = save_checkpoint(
        project_dir=tmp_path,
        state=PipelineState.TRANSLATED,
        artifacts=artifacts,
        substeps=substeps,
    )
    assert saved_file.is_file()

    # Load and resume
    loaded = load_checkpoint(tmp_path)
    assert loaded is not None
    loaded_state, loaded_artifacts, loaded_substeps = loaded

    assert loaded_state == PipelineState.TRANSLATED
    substep_map = {s.id: s for s in loaded_substeps}
    assert substep_map["4.1"].status == SubstepStatus.SUCCESS
    assert substep_map["4.2"].status == SubstepStatus.SUCCESS
    assert substep_map["4.3"].status == SubstepStatus.PENDING
    assert loaded_artifacts.source_video == sample_video


# ===========================================================================
# Tier 4: Output Export Integrity Tests (MP4 & CapCut)
# ===========================================================================

def test_build_render_command_authentic_filter_composition(
    tmp_path: Path, sample_video: Path, master_audio: Path
):
    """build_render_command must synthesize authentic MP4 with video filters, ass, and audio ducking."""
    ass_path = tmp_path / "subtitles.ass"
    ass_path.write_text("[Script Info]\nTitle: Test Sub", encoding="utf-8")
    output_mp4 = tmp_path / "output_final.mp4"

    masks = [
        MaskItem(id="m1", mask_type="erase", x=0.1, y=0.8, width=0.8, height=0.15),
        MaskItem(id="m2", mask_type="solid", x=0.8, y=0.05, width=0.15, height=0.1),
    ]
    project = Project(
        video_path=sample_video,
        masks=masks,
        master_voice_path=master_audio,
    )

    config = RenderConfig(
        output_path=output_mp4,
        burn_subtitles=True,
        apply_masks=True,
        original_volume=0.15,  # 15% ducking
        voice_volume=1.0,      # 100% voice
        video_codec="libx264",
        audio_codec="aac",
    )

    cmd = build_render_command(
        project=project,
        config=config,
        speech_wav_path=master_audio,
        ass_subtitle_path=ass_path,
        ffmpeg_exe="ffmpeg",
        video_width=1920,
        video_height=1080,
        has_original_audio=True,
    )

    # Verification assertions:
    assert cmd[0] == "ffmpeg"
    assert "-nostdin" in cmd
    assert "-y" in cmd

    # Must contain both video input and speech wav input
    assert "-i" in cmd
    i_indices = [idx for idx, arg in enumerate(cmd) if arg == "-i"]
    assert len(i_indices) == 2
    assert cmd[i_indices[0] + 1] == str(sample_video)
    assert cmd[i_indices[1] + 1] == str(master_audio)

    # Video filter verification (-vf)
    assert "-vf" in cmd
    vf_arg = cmd[cmd.index("-vf") + 1]
    assert "delogo=" in vf_arg
    assert "drawbox=" in vf_arg
    assert "ass=" in vf_arg

    # Audio filter complex verification (-filter_complex)
    assert "-filter_complex" in cmd
    af_arg = cmd[cmd.index("-filter_complex") + 1]
    assert "amix=inputs=2" in af_arg
    assert "volume=0.15" in af_arg
    assert "volume=1.00" in af_arg
    assert "-map" in cmd
    assert "[aout]" in cmd

    # Codecs and output
    assert "-c:v" in cmd
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "-c:a" in cmd
    assert cmd[cmd.index("-c:a") + 1] == "aac"
    assert "-shortest" in cmd
    assert str(output_mp4) in cmd

    # Raw copy fallback must NEVER be used when speech wav is supplied
    assert "copy" not in cmd


def test_capcut_export_authentic_draft_structure(
    tmp_path: Path, sample_video: Path, master_audio: Path, sample_script: ScriptDocument
):
    """export_capcut_project generates authentic CapCut draft with video, audio, and text tracks."""
    draft_root = tmp_path / "CapCutDrafts"
    draft_root.mkdir()

    project = Project(
        video_path=sample_video,
        video_duration_ms=6000,
        script=sample_script,
        master_voice_path=master_audio,
    )
    # Approve project
    project.approve(True)
    assert project.voice_ready is True

    with patch("vkdub.services.capcut_export._probe_video") as mock_probe:
        # Mock probe: (width, height, duration_ms, has_audio)
        mock_probe.return_value = (1920, 1080, 6000, True)

        result = export_capcut_project(
            project=project,
            draft_root=draft_root,
            ffprobe="ffprobe",
            name="KAPPAK_E2E_Test",
        )

        assert result.path.is_dir()
        assert result.audio_segments == 1
        assert result.caption_segments == len(sample_script.lines)

        content_file = result.path / "draft_content.json"
        assert content_file.is_file()

        content = json.loads(content_file.read_text(encoding="utf-8"))
        assert "tracks" in content
        assert "materials" in content
        assert content.get("name") == "KAPPAK_E2E_Test"

        tracks = content["tracks"]
        track_names = [t.get("name") for t in tracks]
        assert "VOICE TIẾNG VIỆT — ĐÃ DỊCH" in track_names
        assert "PHỤ ĐỀ TIẾNG VIỆT" in track_names

        # Subtitle track verification
        sub_track = next(t for t in tracks if t.get("name") == "PHỤ ĐỀ TIẾNG VIỆT")
        assert len(sub_track["segments"]) == 2

        # Materials text check
        texts = content["materials"].get("texts", [])
        assert len(texts) >= 2
        joined_texts = " ".join([t.get("name", "") for t in texts])
        assert "Chào mừng bạn" in joined_texts


def test_capcut_export_rejects_unapproved_project(
    tmp_path: Path, sample_video: Path, master_audio: Path, sample_script: ScriptDocument
):
    """export_capcut_project must strictly reject projects that are not approved."""
    draft_root = tmp_path / "CapCutDrafts"
    draft_root.mkdir()

    project = Project(
        video_path=sample_video,
        video_duration_ms=6000,
        script=sample_script,
        master_voice_path=master_audio,
    )
    # Intentionally do NOT call project.approve(True)
    assert project.is_approved is False

    with pytest.raises(ValueError, match="Kịch bản chưa được duyệt"):
        export_capcut_project(
            project=project,
            draft_root=draft_root,
            ffprobe="ffprobe",
        )

    # Ensure no draft was created
    assert len(list(draft_root.iterdir())) == 0


def test_capcut_export_rejects_missing_voice(
    tmp_path: Path, sample_video: Path, sample_script: ScriptDocument
):
    """export_capcut_project rejects projects without voice assets or master voice."""
    draft_root = tmp_path / "CapCutDrafts"
    draft_root.mkdir()

    project = Project(
        video_path=sample_video,
        video_duration_ms=6000,
        script=sample_script,
        master_voice_path=None,  # No voice
    )
    project.approve(True)
    assert project.voice_ready is False

    with pytest.raises(ValueError, match="Cần video, kịch bản đã duyệt và đủ voice"):
        export_capcut_project(
            project=project,
            draft_root=draft_root,
            ffprobe="ffprobe",
        )


def test_render_path_escaping_windows_and_unicode():
    """escape_ffmpeg_filter_path escapes colons and single quotes across Windows and Unicode paths."""
    # Windows path with drive letter, single quote, spaces, and Vietnamese diacritics
    test_path = Path("C:/KAPPAK's Studio/Tiếng Việt — Lồng tiếng/sub.ass")
    escaped = escape_ffmpeg_filter_path(test_path)

    # Colon in drive letter C: must be escaped to C\:
    assert "C\\:/" in escaped or "c\\:/" in escaped.lower()
    # Single quote must be escaped
    assert "\\'" in escaped
    # Unicode text must be preserved
    assert "Tiếng Việt" in escaped
