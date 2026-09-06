import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from vkdub.domain.transcript import Transcript


def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def cache_key(
    fingerprint: str,
    model: str,
    language: str,
    device: str,
    provider_version: str,
    model_revision: str,
) -> str:
    payload = [
        "transcript-v1",
        fingerprint,
        model,
        language,
        device,
        provider_version,
        model_revision,
        "beam5-vad-int8",
    ]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def read_cached(path: Path, key: str) -> Transcript | None:
    if not path.is_file():
        return None
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Cache bản chép lời quá lớn.")
    result = Transcript.from_dict(json.loads(path.read_text(encoding="utf-8")))
    if result.cache_key != key:
        raise ValueError("Cache bản chép lời không khớp nguồn/cấu hình.")
    return result
