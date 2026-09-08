import hashlib
import json
import shutil
import subprocess
import wave
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from vkdub.domain.mask import MaskItem
from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.domain.subtitle import SubtitleStyle
from vkdub.domain.voice import VoiceAsset, VoiceSettings, audio_key, digest
from vkdub.services.capcut_export import TIME_SCALE, export_capcut_project


def ready_project(tmp_path: Path) -> Project:
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg
    video = tmp_path / "source.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=size=320x180:duration=2",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        capture_output=True,
        check=True,
    )
    line = ScriptLine(str(uuid4()), 100, 1600, "Xin chào CapCut")
    voice = VoiceSettings("vieneu_local", "fixture", "Fixture", 1, 0.75)
    audio = tmp_path / "voice.wav"
    with wave.open(str(audio), "wb") as output:
        output.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        output.writeframes(b"\0\0" * 48000)
    project = Project(
        video_path=video,
        video_duration_ms=2000,
        script=ScriptDocument((line,)),
        voice=voice,
        subtitle_style=SubtitleStyle(
            font_family="Arial",
            font_size=54,
            text_color="#FFE600",
            outline_color="#112233",
            outline_width=4,
            background_box=True,
            background_color="#000000",
            background_opacity=0.65,
            margin_bottom=180,
        ),
    )
    project.approve(True)
    project.voice_assets[line.id] = VoiceAsset(
        audio_key(line.text, voice),
        digest(line.text),
        voice.provider,
        voice.voice_id,
        voice.speed,
        1000,
        audio,
        hashlib.sha256(audio.read_bytes()).hexdigest(),
        "2026-09-05T00:00:00+00:00",
    )
    project.masks.append(MaskItem(x=0.1, y=0.1, width=0.2, height=0.2))
    return project


def test_export_creates_unique_editable_tracks_and_registers_index(tmp_path):
    root = tmp_path / "drafts"
    root.mkdir()
    result = export_capcut_project(
        ready_project(tmp_path), root, shutil.which("ffprobe"), shutil.which("ffmpeg")
    )
    assert result.path.is_dir() and result.omitted_blur_count == 0
    assert result.applied_mask_count == 1
    content = json.loads((result.path / "draft_content.json").read_text(encoding="utf-8"))
    assert Path(content["path"]) == result.path
    tracks = {row["type"]: row for row in content["tracks"]}
    assert set(tracks) == {"video", "audio", "text"}
    assert tracks["video"]["segments"][0]["target_timerange"]["duration"] == 2000 * TIME_SCALE
    assert tracks["audio"]["segments"][0]["target_timerange"]["start"] == 100 * TIME_SCALE
    assert tracks["text"]["segments"][0]["target_timerange"]["duration"] == 1500 * TIME_SCALE
    text_id = tracks["text"]["segments"][0]["material_id"]
    text = next(row for row in content["materials"]["texts"] if row["id"] == text_id)
    text_content = json.loads(text["content"])
    assert text_content["text"] == "Xin chào CapCut"
    assert text_content["background_alpha"] == 0.65
    assert text_content["background_style"] == 1
    assert text_content["text_color"] == "#FFE600"
    assert text_content["font_name"] == "Arial"
    assert tracks["text"]["name"] == "PHỤ ĐỀ TIẾNG VIỆT"
    assert tracks["text"]["segments"][0]["clip"]["transform"]["y"] == pytest.approx(
        -0.611667, abs=0.000001
    )
    copied_voice = result.path / "Assets" / "voice-0001.wav"
    assert copied_voice.is_file()
    audio_id = tracks["audio"]["segments"][0]["material_id"]
    audio = next(row for row in content["materials"]["audios"] if row["id"] == audio_id)
    assert Path(audio["path"]) == copied_voice
    assert Path(audio["path"]).is_file()
    assert audio["type"] == "extract_music"
    assert audio["category_name"] == "local"
    assert audio["music_id"] == audio["resource_id"] == audio["request_id"] == ""
    assert audio["name"].startswith("VI — Xin chào CapCut")
    assert tracks["audio"]["name"] == "VOICE TIẾNG VIỆT — ĐÃ DỊCH"
    video_id = tracks["video"]["segments"][0]["material_id"]
    video = next(row for row in content["materials"]["videos"] if row["id"] == video_id)
    assert Path(video["path"]) == result.path / "Assets" / "video-da-xoa-chu.mp4"
    assert Path(video["path"]).is_file()
    assert tracks["video"]["segments"][0]["volume"] == 0
    assert tracks["video"]["name"] == "VIDEO — ÂM THANH GỐC ĐÃ TẮT"
    index = json.loads((root / "root_meta_info.json").read_text(encoding="utf-8"))
    assert index["draft_ids"] == 1 and index["all_draft_store"][0]["draft_id"] == result.draft_id
    index["draft_ids"] = 99  # CapCut can leave this cached counter stale.
    (root / "root_meta_info.json").write_text(json.dumps(index), encoding="utf-8")
    second = export_capcut_project(
        ready_project(tmp_path), root, shutil.which("ffprobe"), shutil.which("ffmpeg")
    )
    assert second.path != result.path
    repaired = json.loads((root / "root_meta_info.json").read_text(encoding="utf-8"))
    assert repaired["draft_ids"] == len(repaired["all_draft_store"]) == 2


def test_export_requires_current_approval_and_writes_nothing(tmp_path):
    root = tmp_path / "drafts"
    root.mkdir()
    project = ready_project(tmp_path)
    project.voice = replace(project.voice, speed=1.2)
    with pytest.raises(ValueError, match="duyệt"):
        export_capcut_project(project, root, shutil.which("ffprobe"))
    assert list(root.iterdir()) == []


def test_export_without_masks_keeps_source_video_and_voice_paths_valid(tmp_path):
    root = tmp_path / "drafts"
    root.mkdir()
    project = ready_project(tmp_path)
    project.masks.clear()
    result = export_capcut_project(project, root, shutil.which("ffprobe"), shutil.which("ffmpeg"))
    content = json.loads((result.path / "draft_content.json").read_text(encoding="utf-8"))
    tracks = {row["type"]: row for row in content["tracks"]}
    video_id = tracks["video"]["segments"][0]["material_id"]
    video = next(row for row in content["materials"]["videos"] if row["id"] == video_id)
    assert Path(video["path"]) == project.video_path
    assert result.applied_mask_count == 0


def test_export_accepts_single_master_audio_track(tmp_path):
    root = tmp_path / "drafts"
    root.mkdir()
    project = ready_project(tmp_path)
    master = next(iter(project.voice_assets.values())).output_path
    project.master_voice_path = master
    project.voice_assets.clear()

    result = export_capcut_project(
        project, root, shutil.which("ffprobe"), shutil.which("ffmpeg")
    )

    content = json.loads((result.path / "draft_content.json").read_text(encoding="utf-8"))
    tracks = {row["type"]: row for row in content["tracks"]}
    assert len(tracks["audio"]["segments"]) == 1
    assert len(tracks["text"]["segments"]) == 1
    assert (result.path / "Assets" / f"master-voice{master.suffix}").is_file()


def test_export_adapts_to_local_capcut_draft_version(tmp_path):
    root = tmp_path / "drafts"
    root.mkdir()

    # Simulate an existing CapCut draft from an older version (e.g. CapCut 8.5.0)
    existing_draft = root / "0511_user_project"
    existing_draft.mkdir()
    existing_content = {
        "version": 360000,
        "new_version": "167.0.0",
        "platform": {"os": "windows", "app_version": "8.5.0"},
        "last_modified_platform": {"os": "windows", "app_version": "8.5.0"},
    }
    (existing_draft / "draft_content.json").write_text(
        json.dumps(existing_content), encoding="utf-8"
    )

    project = ready_project(tmp_path)
    result = export_capcut_project(
        project, root, shutil.which("ffprobe"), shutil.which("ffmpeg")
    )

    exported_content = json.loads((result.path / "draft_content.json").read_text(encoding="utf-8"))
    assert exported_content["new_version"] == "167.0.0"
    assert exported_content["platform"]["app_version"] == "8.5.0"
    assert exported_content["last_modified_platform"]["app_version"] == "8.5.0"


def test_patch_existing_vkdub_drafts(tmp_path):
    root = tmp_path / "drafts"
    root.mkdir()

    # Create an old VKDub draft that was saved with a newer version
    old_vkdub = root / "VKDub 20260901-120000-TEST001"
    old_vkdub.mkdir()
    (old_vkdub / "draft_content.json").write_text(
        json.dumps({
            "version": 360000,
            "new_version": "181.0.0",
            "platform": {"app_version": "9.2.0"},
            "last_modified_platform": {"app_version": "9.2.0"},
        }),
        encoding="utf-8",
    )

    from vkdub.services.capcut_export import patch_existing_vkdub_drafts

    profile = {
        "version": 360000,
        "new_version": "167.0.0",
        "platform": {"app_version": "8.5.0"},
        "last_modified_platform": {"app_version": "8.5.0"},
    }
    count = patch_existing_vkdub_drafts(root, profile)
    assert count == 1

    patched = json.loads((old_vkdub / "draft_content.json").read_text(encoding="utf-8"))
    assert patched["new_version"] == "167.0.0"
    assert patched["platform"]["app_version"] == "8.5.0"
    assert patched["last_modified_platform"]["app_version"] == "8.5.0"

