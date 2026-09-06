"""CapCut v360000 draft writer derived from a read-only local compatibility probe."""

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from vkdub.domain.project import Project
from vkdub.domain.subtitle import SUBTITLE_REFERENCE_HEIGHT, SubtitleStyle
from vkdub.services.audio_mix_service import fit_voice_wav, voice_slot_duration_ms
from vkdub.services.cache_service import atomic_json
from vkdub.services.mask_service import build_ffmpeg_mask_filter

TIME_SCALE = 1000  # local CapCut v360000: microseconds; VKDub uses milliseconds


@dataclass(frozen=True)
class CapCutExportResult:
    path: Path
    draft_id: str
    video_segments: int
    audio_segments: int
    caption_segments: int
    omitted_blur_count: int
    applied_mask_count: int = 0


def _template_path() -> Path:
    source = Path(__file__).parents[3] / "resources" / "capcut_v360000_template.json"
    installed = Path(sys.prefix) / "share" / "vk-dub-studio" / source.name
    path = source if source.is_file() else installed
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("Thiếu mẫu CapCut đã xác minh cho phiên bản này.")
    return path


def _replace_ids(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _replace_ids(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_ids(item, mapping) for item in value]
    return mapping.get(value, value) if isinstance(value, str) else value


def _clone_bundle(template: dict[str, Any]) -> dict[str, Any]:
    ids = {template["track"]["id"], template["segment"]["id"]}
    ids.update(row["id"] for rows in template["materials"].values() for row in rows if "id" in row)
    return _replace_ids(copy.deepcopy(template), {old: str(uuid4()).upper() for old in ids})


def _append_bundle(content: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    for name, rows in bundle["materials"].items():
        content["materials"].setdefault(name, []).extend(rows)
    return bundle["segment"]


def _probe_video(path: Path, ffprobe: str) -> tuple[int, int, int, bool]:
    run = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type,width,height:format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
    try:
        data = json.loads(run.stdout)
        video = next(row for row in data["streams"] if row.get("codec_type") == "video")
        return (
            int(video["width"]),
            int(video["height"]),
            round(float(data["format"]["duration"]) * 1000),
            any(row.get("codec_type") == "audio" for row in data["streams"]),
        )
    except (ValueError, KeyError, IndexError, TypeError, StopIteration, json.JSONDecodeError):
        raise ValueError("Không đọc được kích thước video để tạo project CapCut.") from None


def _render_masked_video(
    source: Path,
    target: Path,
    project: Project,
    width: int,
    height: int,
    ffmpeg: str,
) -> None:
    mask_filter = build_ffmpeg_mask_filter(project.masks, width, height)
    if not mask_filter:
        raise ValueError("Không tạo được bộ lọc xóa chữ cho CapCut.")
    run = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-vf",
            mask_filter,
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(target),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=3600,
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
    if run.returncode or not target.is_file():
        detail = run.stderr.strip().splitlines()[-1] if run.stderr.strip() else "FFmpeg thất bại."
        raise ValueError(f"Không áp dụng được vùng xóa chữ vào video CapCut: {detail}")


def _set_range(segment: dict[str, Any], start_ms: int, duration_ms: int) -> None:
    segment["target_timerange"] = {
        "start": start_ms * TIME_SCALE,
        "duration": duration_ms * TIME_SCALE,
    }
    if segment.get("source_timerange") is not None:
        segment["source_timerange"] = {"start": 0, "duration": duration_ms * TIME_SCALE}


def _text_material(bundle: dict[str, Any]) -> dict[str, Any]:
    return next(
        row for row in bundle["materials"]["texts"] if row["id"] == bundle["segment"]["material_id"]
    )


def _set_text(material: dict[str, Any], text: str) -> None:
    value = json.loads(material["content"])
    value["text"] = text
    for style in value.get("styles", []):
        style["range"] = [0, len(text)]
    material["content"] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    material["name"] = text[:80]
    material["text_size"] = len(text)


def _rgb_unit(hex_color: str) -> list[float]:
    raw = hex_color.lstrip("#")[-6:]
    try:
        return [int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    except (ValueError, IndexError):
        return [1.0, 1.0, 1.0]


def _capcut_font_size(style: SubtitleStyle) -> float:
    """Map the 1080p preview pixel scale to CapCut's text-size scale."""
    return round(max(1.0, style.font_size * 8.0 / 42.0), 3)


def _capcut_transform_y(style: SubtitleStyle) -> float:
    """Place the caption's lower edge at the same 1080p-relative margin as preview/ASS."""
    half_line = style.font_size * style.line_spacing / 2
    center_from_bottom = style.margin_bottom + half_line
    return round(
        max(-1.0, min(1.0, -1.0 + 2.0 * center_from_bottom / SUBTITLE_REFERENCE_HEIGHT)),
        6,
    )


def _set_text_style(
    material: dict[str, Any], segment: dict[str, Any], style: SubtitleStyle
) -> None:
    """Copy VKDub's visible subtitle style and position into a CapCut text material."""
    value = json.loads(material["content"])
    size = _capcut_font_size(style)
    fill = _rgb_unit(style.text_color)
    stroke = _rgb_unit(style.outline_color)
    for row in value.get("styles", []):
        row.update(size=size, bold=style.bold, italic=style.italic)
        row["font"] = {"id": "", "path": ""}
        row["fill"] = {
            "alpha": 1.0,
            "content": {"render_type": "solid", "solid": {"alpha": 1.0, "color": fill}},
        }
        row["strokes"] = (
            [
                {
                    "alpha": 1.0,
                    "content": {
                        "render_type": "solid",
                        "solid": {"alpha": 1.0, "color": stroke},
                    },
                    "width": round(style.outline_width / max(1, style.font_size), 4),
                }
            ]
            if style.outline_width > 0
            else []
        )
    value.update(
        font_size=size,
        font_name=style.font_family,
        font_title=style.font_family,
        text_color=style.text_color,
        text_alpha=1.0,
        border_color=style.outline_color,
        border_alpha=1.0,
        border_width=round(style.outline_width / max(1, style.font_size), 4),
        has_shadow=style.shadow_offset > 0,
        shadow_color=style.shadow_color,
        shadow_alpha=0.8 if style.shadow_offset > 0 else 0.0,
        shadow_distance=style.shadow_offset,
        background_color=style.background_color,
        background_alpha=style.background_opacity if style.background_box else 0.0,
        background_style=1 if style.background_box else 0,
        background_round_radius=0.2 if style.background_box else 0.0,
        background_width=0.12,
        background_height=0.12,
        background_horizontal_offset=0.5,
        background_vertical_offset=0.5,
        line_max_width=style.max_width_ratio,
        alignment=1,
    )
    material.update(
        content=json.dumps(value, ensure_ascii=False, separators=(",", ":")),
        font_name=style.font_family,
        font_title=style.font_family,
        font_size=size,
        text_color=style.text_color,
        text_alpha=1.0,
        border_color=style.outline_color,
        border_alpha=1.0,
        border_width=round(style.outline_width / max(1, style.font_size), 4),
        has_shadow=style.shadow_offset > 0,
        shadow_color=style.shadow_color,
        shadow_alpha=0.8 if style.shadow_offset > 0 else 0.0,
        shadow_distance=style.shadow_offset,
        background_color=style.background_color,
        background_alpha=style.background_opacity if style.background_box else 0.0,
        background_style=1 if style.background_box else 0,
        background_round_radius=0.2 if style.background_box else 0.0,
        line_max_width=style.max_width_ratio,
        fonts=[],
    )
    clip = segment.get("clip")
    if isinstance(clip, dict):
        clip["scale"] = {"x": 1.0, "y": 1.0}
        clip["transform"] = {"x": 0.0, "y": _capcut_transform_y(style)}
    segment["uniform_scale"] = {"on": True, "value": 1.0}


def _set_local_voice_material(
    material: dict[str, Any], path: Path, text: str, duration_ms: int
) -> None:
    """Turn the probed online-music template into an imported local WAV material."""
    material.update(
        path=str(path),
        name=f"VI — {text[:70]}",
        duration=duration_ms * TIME_SCALE,
        type="extract_music",
        app_id=0,
        music_id="",
        resource_id="",
        category_id="",
        category_name="local",
        request_id="",
    )


def export_capcut_project(
    project: Project,
    draft_root: Path,
    ffprobe: str,
    ffmpeg: str | None = None,
    name: str | None = None,
) -> CapCutExportResult:
    project.require_approval()
    if not project.voice_ready or not project.video_path or not project.video_path.is_file():
        raise ValueError("Cần video, kịch bản đã duyệt và đủ voice trước khi xuất CapCut.")
    if not draft_root.is_dir():
        raise ValueError("Chưa tìm thấy thư mục project CapCut. Mở Cài đặt → CapCut.")
    template = json.loads(_template_path().read_text(encoding="utf-8"))
    if template.get("schema") != "VKDub.CapCut.v360000":
        raise ValueError("Mẫu CapCut không đúng phiên bản đã xác minh.")
    width, height, media_duration, has_original_audio = _probe_video(project.video_path, ffprobe)
    duration_ms = project.duration_ms or media_duration
    draft_id = str(uuid4()).upper()
    safe_name = (name or f"VKDub {project.video_path.stem}").strip()[:80]
    folder_name = time.strftime("VKDub %Y%m%d-%H%M%S-") + draft_id[:8]
    final = draft_root / folder_name
    if final.exists():
        raise FileExistsError("Tên project CapCut mới đã tồn tại; hãy thử lại.")
    staging = Path(tempfile.mkdtemp(prefix=".vkdub-export-", dir=draft_root))
    try:
        assets = staging / "Assets"
        assets.mkdir()
        content = copy.deepcopy(template["content"])
        content.update(
            id=draft_id,
            name=safe_name,
            duration=duration_ms * TIME_SCALE,
            path=str(final).replace("\\", "/"),
        )
        content["canvas_config"] = {
            "ratio": "original",
            "width": width,
            "height": height,
            "background": None,
        }
        now = int(time.time())
        content["create_time"] = content["update_time"] = now

        video_source = project.video_path
        final_video_source = project.video_path
        if project.masks:
            if not ffmpeg:
                raise ValueError("Cần FFmpeg để áp dụng vùng xóa chữ trước khi xuất CapCut.")
            video_source = assets / "video-da-xoa-chu.mp4"
            final_video_source = final / "Assets" / video_source.name
            _render_masked_video(
                project.video_path, video_source, project, width, height, ffmpeg
            )

        video = _clone_bundle(template["bundles"]["video"])
        vseg = _append_bundle(content, video)
        _set_range(vseg, 0, duration_ms)
        # CapCut opens with only the translated voice audible. The source audio is
        # retained in the video clip and can be raised manually if background sound is wanted.
        vseg["volume"] = 0.0
        vmat = next(row for row in video["materials"]["videos"] if row["id"] == vseg["material_id"])
        vmat.update(
            path=str(final_video_source),
            media_path=str(final_video_source),
            duration=media_duration * TIME_SCALE,
            width=width,
            height=height,
            has_audio=has_original_audio,
        )
        video["track"].update(name="VIDEO — ÂM THANH GỐC ĐÃ TẮT", is_default_name=False)
        video["track"]["segments"] = [vseg]
        content["tracks"].append(video["track"])

        audio_track = copy.deepcopy(template["bundles"]["audio"]["track"])
        audio_track["id"] = str(uuid4()).upper()
        audio_track.update(name="VOICE TIẾNG VIỆT — ĐÃ DỊCH", is_default_name=False)
        audio_track["segments"] = []
        text_track = copy.deepcopy(template["bundles"]["text"]["track"])
        text_track["id"] = str(uuid4()).upper()
        text_track.update(name="PHỤ ĐỀ TIẾNG VIỆT", is_default_name=False)
        text_track["segments"] = []
        assert project.script
        current = project.current_voices()
        for index, line in enumerate(project.script.lines, 1):
            asset = current[line.id]
            copied = assets / f"voice-{index:04}.wav"
            slot_ms = voice_slot_duration_ms(project, index - 1, duration_ms)
            fitted_duration_ms = fit_voice_wav(
                asset.output_path, copied, ffmpeg, slot_ms
            )
            final_audio = final / "Assets" / copied.name
            audio = _clone_bundle(template["bundles"]["audio"])
            aseg = _append_bundle(content, audio)
            _set_range(aseg, line.start_ms, fitted_duration_ms)
            aseg["volume"] = project.voice.volume
            amat = next(
                row for row in audio["materials"]["audios"] if row["id"] == aseg["material_id"]
            )
            _set_local_voice_material(amat, final_audio, line.text, fitted_duration_ms)
            audio_track["segments"].append(aseg)
            caption = _clone_bundle(template["bundles"]["text"])
            tseg = _append_bundle(content, caption)
            _set_range(tseg, line.start_ms, line.end_ms - line.start_ms)
            text_material = _text_material(caption)
            _set_text(text_material, line.text)
            _set_text_style(text_material, tseg, project.subtitle_style)
            text_track["segments"].append(tseg)
        content["tracks"].extend([audio_track, text_track])

        meta = copy.deepcopy(template["meta"])
        meta.update(
            draft_id=draft_id,
            draft_name=safe_name,
            draft_fold_path=str(final).replace("\\", "/"),
            draft_root_path=str(draft_root).replace("\\", "/"),
            tm_draft_create=now,
            tm_draft_modified=now,
            tm_duration=duration_ms * TIME_SCALE,
        )
        atomic_json(staging / "draft_content.json", content)
        atomic_json(staging / "draft_meta_info.json", meta)
        staging.replace(final)
        _register_root(
            draft_root, final, draft_id, safe_name, duration_ms, template["root_entry"], now
        )
        return CapCutExportResult(
            final,
            draft_id,
            1,
            len(audio_track["segments"]),
            len(text_track["segments"]),
            0,
            len(project.masks),
        )
    except Exception:
        if staging.exists() and staging.resolve().parent == draft_root.resolve():
            shutil.rmtree(staging)
        raise


def load_original_volume() -> float:
    from vkdub.services.app_settings import load_app_settings

    return load_app_settings().original_volume / 100


def _register_root(
    root: Path,
    folder: Path,
    identifier: str,
    name: str,
    duration_ms: int,
    entry_template: dict[str, Any],
    now: int,
) -> None:
    index_path = root / "root_meta_info.json"
    data = (
        json.loads(index_path.read_text(encoding="utf-8"))
        if index_path.is_file()
        else {"all_draft_store": [], "draft_ids": 0, "root_path": str(root).replace("\\", "/")}
    )
    stores = data.get("all_draft_store")
    if not isinstance(stores, list):
        raise ValueError("Chỉ mục CapCut không có danh sách project hợp lệ.")
    # CapCut can leave this cached counter stale after its own cleanup. The list is
    # authoritative; normalize the counter while registering the new unique draft.
    data["draft_ids"] = len(stores)
    item = copy.deepcopy(entry_template)
    item.update(
        draft_id=identifier,
        draft_name=name,
        draft_fold_path=str(folder).replace("\\", "/"),
        draft_root_path=str(root).replace("\\", "/"),
        draft_json_file="draft_content.json",
        tm_draft_create=now,
        tm_draft_modified=now,
        tm_duration=duration_ms * TIME_SCALE,
    )
    stores.append(item)
    data["draft_ids"] = len(stores)
    backup = index_path.with_suffix(".vkdub-backup.json")
    if index_path.is_file() and not backup.exists():
        shutil.copy2(index_path, backup)
    atomic_json(index_path, data)
