import hashlib
import json
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from vkdub.domain.project import Project
from vkdub.domain.voice import VoiceAsset, VoiceSettings, audio_key, digest, normalized_text
from vkdub.media.voice_audio import assemble_audio, audio_duration
from vkdub.providers.base import Progress
from vkdub.providers.tts import TextToSpeechProvider
from vkdub.services.cache_service import atomic_json


def split_text(text: str, limit: int = 300) -> tuple[str, ...]:
    remaining = normalized_text(text)
    if limit < 1 or not remaining:
        raise ValueError("Nội dung voice trống hoặc giới hạn không hợp lệ.")
    chunks: list[str] = []
    while len(remaining) > limit:
        cut = max(
            (remaining.rfind(mark, 0, limit) + 1 for mark in (". ", "! ", "? ", "\n")), default=0
        )
        if cut < limit // 3:
            cut = remaining.rfind(" ", 0, limit + 1)
        if cut <= 0:
            cut = limit
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        chunks.append(remaining)
    return tuple(chunks)


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


async def cached_asset(
    root: Path, text: str, settings: VoiceSettings, ffprobe: str
) -> VoiceAsset | None:
    key = audio_key(text, settings)
    metadata = root / f"{key}.json"
    if not metadata.is_file():
        return None
    try:
        if metadata.stat().st_size > 8192:
            raise ValueError
        asset = VoiceAsset.from_dict(json.loads(metadata.read_text(encoding="utf-8")), root)
        # Cache metadata cannot redirect us to an unrelated local file.
        if (
            asset.output_path.parent != root.resolve()
            or not asset.output_path.name.startswith(key + "-")
            or not asset.matches(text, settings)
            or file_hash(asset.output_path) != asset.audio_sha256
        ):
            raise ValueError
        if abs(await audio_duration(asset.output_path, ffprobe) - asset.duration_ms) > 20:
            raise ValueError
        return asset
    except (ValueError, OSError):
        raise ValueError(
            "Cache voice hỏng/thiếu audio. Chọn Tạo lại voice cho câu này; chưa tự tính phí lại."
        ) from None


async def generate_voice(
    project: Project,
    provider: TextToSpeechProvider,
    root: Path,
    ffmpeg: str,
    ffprobe: str,
    progress: Progress,
    check_cancel: Callable[[], None],
    completed: Callable[[str, VoiceAsset | None, str], None],
    line_ids: set[str] | None = None,
    force: bool | set[str] = False,
) -> None:
    revision = project.require_approval()
    script, settings = project.script, project.voice
    assert script is not None
    if provider.name != settings.provider:
        raise ValueError("Provider không khớp cấu hình voice.")

    def guard() -> None:
        check_cancel()
        if project.require_approval() != revision or project.voice != settings:
            raise ValueError("Kịch bản/cấu hình voice đã đổi. Dừng tạo voice và duyệt lại.")

    root.mkdir(parents=True, exist_ok=True)
    chunk_root = root / "chunks"
    chunk_root.mkdir(exist_ok=True)
    lines = [line for line in script.lines if line_ids is None or line.id in line_ids]
    for index, line in enumerate(lines):
        guard()
        regenerate = force is True or (isinstance(force, set) and line.id in force)
        progress(round(index * 100 / max(1, len(lines))), f"Voice câu {index + 1}/{len(lines)}…")
        try:
            asset = None if regenerate else await cached_asset(root, line.text, settings, ffprobe)
            if asset is None:
                with tempfile.TemporaryDirectory(prefix="voice-", dir=root) as temporary:
                    staging = Path(temporary)
                    parts: list[Path] = []
                    for number, chunk in enumerate(split_text(line.text, provider.max_characters)):
                        guard()
                        key = audio_key(chunk, settings)
                        extension = getattr(provider, "audio_suffix", ".mp3")
                        cached = chunk_root / f"{key}{extension}"
                        checksum = chunk_root / f"{key}.sha256"
                        if cached.exists() and not regenerate:
                            if not checksum.is_file() or checksum.read_text() != file_hash(cached):
                                raise ValueError(
                                    "Cache đoạn voice hỏng. Chọn Tạo lại voice; chưa gửi lại API."
                                )
                            await audio_duration(cached, ffprobe)
                        else:
                            downloaded = staging / f"chunk-{number}{extension}"
                            await provider.synthesize(
                                chunk, settings.voice_id, settings.speed, downloaded
                            )
                            guard()
                            await audio_duration(downloaded, ffprobe)
                            downloaded.replace(cached)
                            checksum.write_text(file_hash(cached), encoding="ascii")
                        parts.append(cached)
                    wav, duration = await assemble_audio(
                        parts,
                        staging,
                        ffmpeg,
                        ffprobe,
                        sample_rate=getattr(provider, "sample_rate", 24000),
                    )
                    guard()
                    key, checksum_text = audio_key(line.text, settings), file_hash(wav)
                    # Content-named audio preserves old project references during regeneration.
                    destination = root / f"{key}-{checksum_text}.wav"
                    if destination.is_file() and file_hash(destination) == checksum_text:
                        wav.unlink()
                    else:
                        wav.replace(destination)
                    asset = VoiceAsset(
                        key,
                        digest(normalized_text(line.text)),
                        provider.name,
                        settings.voice_id,
                        settings.speed,
                        duration,
                        destination.resolve(),
                        checksum_text,
                        datetime.now(UTC).isoformat(),
                    )
                    atomic_json(root / f"{key}.json", asset.to_dict())
            guard()
            completed(line.id, asset, "")
        except (ValueError, OSError) as exc:
            guard()
            completed(line.id, None, str(exc))
    progress(100, "Đã xử lý các câu voice. Kiểm tra câu lỗi và cảnh báo thời lượng.")
