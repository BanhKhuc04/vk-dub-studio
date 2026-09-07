import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from vkdub.domain.mask import MaskItem
from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument
from vkdub.domain.subtitle import SubtitleStyle
from vkdub.domain.transcript import Transcript, TranscriptionSettings
from vkdub.domain.translation import Translation
from vkdub.domain.voice import VoiceAsset, VoiceSettings
from vkdub.version import __version__

MAX_PROJECT_BYTES = 16 * 1024 * 1024
VOICE = {
    "provider": "vbee",
    "voice_id": "hn-ngoc-huyen",
    "display_name": "HN - Ngọc Huyền",
    "speed": 1.0,
}
REVIEW = {"approved": False, "approved_revision_hash": None}
EXPORT = {"container": "mp4", "video_codec": "h264", "audio_codec": "aac"}


def _portable(path: Path | None, parent: Path) -> str | None:
    if path is None:
        return None
    try:
        return os.path.relpath(path.resolve(), parent.resolve())
    except ValueError:  # Windows cannot make relative paths between different drives.
        return str(path.resolve())


def save_project(project: Project, destination: Path) -> None:
    """Atomic replacement prevents a failed save from destroying the previous project."""
    transcript_data = project.transcript.to_dict() if project.transcript else None
    if project.translation:
        project.translation.validate_source(project.transcript)
        if project.target_language != project.translation.target_language:
            raise ValueError("Ngôn ngữ đích không khớp bản dịch.")
    segments = transcript_data.pop("segments") if transcript_data else []
    if project.script:
        project.script.validate_source(project.transcript)
    script_ids = {line.id for line in project.script.lines} if project.script else set()
    document = {
        "schema_version": 6,
        "legacy": {"voice_disabled": project.voice.provider in ("vbee", "elevenlabs")},
        "app_version": __version__,
        "project_id": project.project_id,
        "video_path": _portable(project.video_path, destination.parent),
        "output_directory": _portable(project.output_directory, destination.parent),
        "source_language": project.source_language,
        "target_language": project.target_language,
        "transcript": segments,
        "transcription": {
            "settings": asdict(project.transcription_settings),
            "result": transcript_data,
        },
        "subtitles": [],
        "subtitle_style": project.subtitle_style.to_dict(),
        "translation": project.translation.to_dict() if project.translation else None,
        "script": project.script.to_dict() if project.script is not None else None,
        "video_duration_ms": project.video_duration_ms,
        "masks": [mask.to_dict() for mask in project.masks],
        "voice": asdict(project.voice),
        "master_voice_path": _portable(project.master_voice_path, destination.parent)
        if project.master_voice_path
        else None,
        "voice_assets": {
            identifier: {
                **asset.to_dict(),
                "output_path": _portable(asset.output_path, destination.parent),
            }
            for identifier, asset in project.voice_assets.items()
            if identifier in script_ids
        },
        "script_review": {
            "approved": project.is_approved,
            "approved_revision_hash": project.approved_revision_hash
            if project.is_approved
            else None,
        },
        "export": EXPORT,
    }
    temporary: Path | None = None
    serialized = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if len(serialized.encode("utf-8")) > MAX_PROJECT_BYTES:
        raise ValueError("Project quá lớn (tối đa 16 MB); tệp đã lưu được giữ nguyên.")
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_project(source: Path) -> Project:
    if source.stat().st_size > MAX_PROJECT_BYTES:
        raise ValueError("Project quá lớn (tối đa 16 MB).")
    try:
        data = json.loads(source.read_text(encoding="utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Tệp .vkdub không phải JSON UTF-8 hợp lệ.") from exc
    if not isinstance(data, dict):
        raise ValueError("Nội dung project phải là một đối tượng JSON.")
    if type(data.get("schema_version")) is not int or data["schema_version"] not in (
        1,
        2,
        3,
        4,
        5,
        6,
    ):
        raise ValueError("Chưa hỗ trợ schema này. Hãy mở bằng phiên bản ứng dụng phù hợp.")
    allowed = {
        "schema_version",
        "legacy",
        "app_version",
        "project_id",
        "video_path",
        "output_directory",
        "source_language",
        "target_language",
        "transcript",
        "transcription",
        "translation",
        "script",
        "video_duration_ms",
        "subtitles",
        "subtitle_style",
        "masks",
        "voice",
        "master_voice_path",
        "voice_assets",
        "script_review",
        "export",
    }
    # Refuse later-phase data instead of silently discarding it on the next save.
    if "legacy" in data and data["legacy"] != {
        "voice_disabled": isinstance(data.get("voice"), dict)
        and data["voice"].get("provider") in ("vbee", "elevenlabs")
    }:
        raise ValueError("Metadata legacy không hợp lệ; giữ nguyên project.")
    if data.keys() - allowed or data.get("subtitles", []) != []:
        raise ValueError(
            "Project chứa dữ liệu ngoài phạm vi hỗ trợ; chưa hỗ trợ để tránh mất dữ liệu."
        )
    masks_data = data.get("masks", [])
    if not isinstance(masks_data, list) or len(masks_data) > 1000:
        raise ValueError("Dữ liệu vùng che không hợp lệ.")
    parsed_masks: list[MaskItem] = []
    for item in masks_data:
        if not isinstance(item, dict):
            raise ValueError("Cấu trúc vùng che không hợp lệ.")
        parsed_masks.append(MaskItem.from_dict(item))
    for key, default in (("export", EXPORT),):
        if data.get(key, default) != default:
            raise ValueError(f"Cấu hình {key} ngoài phạm vi Phase 5; project được giữ nguyên.")
    voice_data = data.get("voice", VOICE)
    if data["schema_version"] < 5:
        if voice_data != VOICE or data.get("voice_assets", {}) != {}:
            raise ValueError("Cấu hình voice cũ không được hỗ trợ; giữ nguyên project.")
        voice = VoiceSettings()
    else:
        voice = VoiceSettings.from_dict(voice_data)
    transcript = None
    settings = TranscriptionSettings()
    # Schema 1 skeletons migrate in memory; the original is only changed on explicit save.
    transcription = data.get("transcription", {"settings": asdict(settings), "result": None})
    try:
        if not isinstance(transcription, dict) or set(transcription) != {"settings", "result"}:
            raise ValueError("Cấu trúc bóc băng không hợp lệ.")
        settings = TranscriptionSettings(**transcription["settings"])
        metadata = transcription["result"]
        if metadata is not None:
            if not isinstance(metadata, dict) or "segments" in metadata:
                raise ValueError("Metadata bản chép lời không hợp lệ.")
            transcript = Transcript.from_dict({**metadata, "segments": data.get("transcript")})
        elif data.get("transcript", []) != []:
            raise ValueError("Bản chép lời thiếu metadata; project được giữ nguyên.")
    except TypeError as exc:
        raise ValueError("Cấu hình bóc băng không hợp lệ.") from exc
    identifier = data.get("project_id")
    translation = None
    if data.get("translation") is not None:
        translation = Translation.from_dict(data["translation"])
        translation.validate_source(transcript)
        if data.get("target_language") != translation.target_language:
            raise ValueError("Ngôn ngữ đích không khớp bản dịch.")
    try:
        if not isinstance(identifier, str):
            raise ValueError
        UUID(identifier)
    except ValueError as exc:
        raise ValueError("Project thiếu project_id UUID hợp lệ.") from exc
    for key in ("source_language", "target_language"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"Project thiếu {key} hợp lệ.")

    def resolve(key: str) -> Path | None:
        value = data.get(key)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip() or "\0" in value:
            raise ValueError(f"Đường dẫn {key} không hợp lệ.")
        path = Path(value)
        return (source.parent / path).resolve() if not path.is_absolute() else path.resolve()

    video_path = resolve("video_path")
    if video_path is not None and video_path.suffix.lower() != ".mp4":
        raise ValueError("Chỉ hỗ trợ video MP4.")
    if transcript is not None and video_path is None:
        raise ValueError("Bản chép lời thiếu tham chiếu video nguồn.")
    script = ScriptDocument.from_dict(data["script"]) if data.get("script") is not None else None
    if script is not None:
        script.validate_source(transcript)
        if video_path is None:
            raise ValueError("Kịch bản thiếu tham chiếu video.")
    duration = data.get("video_duration_ms")
    if duration is not None and (type(duration) is not int or not 0 < duration <= 3_600_000_000):
        raise ValueError("Thời lượng video không hợp lệ.")
    review = data.get("script_review", REVIEW)
    if (
        not isinstance(review, dict)
        or set(review) != set(REVIEW)
        or type(review["approved"]) is not bool
    ):
        raise ValueError("Trạng thái duyệt sai cấu trúc.")
    approved_hash = review["approved_revision_hash"]
    if approved_hash is not None and (
        not isinstance(approved_hash, str)
        or len(approved_hash) != 64
        or any(c not in "0123456789abcdef" for c in approved_hash)
    ):
        raise ValueError("Mã phiên bản duyệt không hợp lệ.")
    if review["approved"] != (approved_hash is not None):
        raise ValueError("Trạng thái duyệt không nhất quán.")
    subtitle_style_data = data.get("subtitle_style")
    subtitle_style = (
        SubtitleStyle.from_dict(subtitle_style_data)
        if isinstance(subtitle_style_data, dict)
        else SubtitleStyle()
    )
    project = Project(
        project_id=identifier,
        video_path=video_path,
        output_directory=resolve("output_directory"),
        source_language=data["source_language"],
        target_language=data["target_language"],
        transcription_settings=settings,
        transcript=transcript,
        translation=translation,
        script=script,
        video_duration_ms=duration,
        approved_revision_hash=approved_hash,
        voice=voice,
        subtitle_style=subtitle_style,
        masks=parsed_masks,
    )
    assets = data.get("voice_assets", {})
    if data.get("master_voice_path"):
        project.master_voice_path = resolve("master_voice_path")
    if (
        not isinstance(assets, dict)
        or len(assets) > 50_000
        or (
            assets
            and (not project.script or set(assets) - {line.id for line in project.script.lines})
        )
    ):
        raise ValueError("Danh sách voice không khớp các câu kịch bản.")
    project.voice_assets = {
        identifier: VoiceAsset.from_dict(value, source.parent)
        for identifier, value in assets.items()
    }
    # A stale hash never grants approval. Keep editable data when context/content has changed.
    if not project.is_approved:
        project.approved_revision_hash = None
    return project
