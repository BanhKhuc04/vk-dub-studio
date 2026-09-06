import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

from vkdub.domain.transcript import SubtitleSegment, Transcript
from vkdub.domain.translation import PROMPT_VERSION, Translation, source_digest, validate_response
from vkdub.providers.base import Progress
from vkdub.services.cache_service import atomic_json
from vkdub.utils.paths import data_root

MAX_BATCH_CHARS = 6000
MAX_BATCH_SEGMENTS = 30


class TranslationProvider(Protocol):
    name: str
    model: str

    async def translate(self, request: dict[str, Any]) -> dict[str, Any]: ...


def batches(transcript: Transcript) -> list[tuple[SubtitleSegment, ...]]:
    result: list[tuple[SubtitleSegment, ...]] = []
    current: list[SubtitleSegment] = []
    count = 0
    for segment in transcript.segments:
        size = len(segment.text)
        if size > MAX_BATCH_CHARS:
            raise ValueError("Một câu vượt 6.000 ký tự. Chưa hỗ trợ chia câu tự động.")
        if current and (count + size > MAX_BATCH_CHARS or len(current) >= MAX_BATCH_SEGMENTS):
            result.append(tuple(current))
            current, count = [], 0
        current.append(segment)
        count += size
    if current:
        result.append(tuple(current))
    return result


def batch_request(rows: tuple[SubtitleSegment, ...], language: str) -> dict[str, Any]:
    return {
        "segments": [asdict(row) for row in rows],
        "source_language": language,
        "target_language": "vi",
    }


def translation_key(request: dict[str, Any], provider: str, model: str) -> str:
    return hashlib.sha256(
        json.dumps(
            [provider, model, PROMPT_VERSION, request], sort_keys=True, ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


async def translate_transcript(
    transcript: Transcript,
    provider: TranslationProvider,
    directory: Path,
    reuse: bool,
    progress: Progress,
    check_cancel: Callable[[], None],
) -> Translation:
    groups = batches(transcript)
    if not groups:
        raise ValueError("Chưa có lời nói để dịch.")
    texts: list[str] = []
    for index, rows in enumerate(groups):
        check_cancel()
        request = batch_request(rows, transcript.language)
        key = translation_key(request, provider.name, provider.model)
        path = directory / f"{key}.json"
        legacy_path = data_root() / "cache" / "translation" / f"{key}.json"
        if reuse and not path.exists() and legacy_path.is_file():
            path = legacy_path
        ids = [row.id for row in rows]
        response = None
        if reuse and path.exists():
            try:
                if path.stat().st_size > 2_000_000:
                    raise ValueError
                cached = json.loads(path.read_text(encoding="utf-8"))
                if cached["key"] != key:
                    raise ValueError
                validate_response(cached["response"], ids)
                response = cached["response"]
            except (ValueError, KeyError, TypeError, OSError):
                # Never turn a broken cache into an unexpected paid request.
                raise ValueError("Cache dịch bị hỏng. Bỏ chọn dùng cache để dịch lại.") from None
        if response is None:
            progress(
                round(index * 100 / len(groups)),
                f"Gemini: đang dịch nhóm {index + 1}/{len(groups)}…",
            )
            response = await provider.translate(request)
            validate_response(response, ids)
            # Keep paid, validated batches even if a later batch fails or is cancelled.
            atomic_json(path, {"key": key, "response": response})
        else:
            progress(
                round(index * 100 / len(groups)), f"Dùng cache dịch nhóm {index + 1}/{len(groups)}."
            )
        check_cancel()
        texts.extend(validate_response(response, ids))
    return Translation(source_digest(transcript), tuple(texts), provider.name, provider.model)
