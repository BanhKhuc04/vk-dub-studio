"""Isolated CLI worker. No Qt imports; model inference never performs network calls."""

import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any

from vkdub.domain.transcript import Transcript, TranscriptionSettings
from vkdub.providers.base import SpeechToTextProvider
from vkdub.providers.faster_whisper_stt import FasterWhisperSTT
from vkdub.services.cache_service import atomic_json, cache_key, read_cached
from vkdub.services.model_service import model_directory, model_ready
from vkdub.utils.paths import data_root, workspace_root


def progress(percent: int, message: str) -> None:
    print(json.dumps({"percent": percent, "message": message}, ensure_ascii=True), flush=True)


def download_model(name: str, staging: Path) -> dict[str, Any]:
    if model_ready(name):
        return {"kind": "model", "model": name}
    from huggingface_hub import HfApi, snapshot_download

    destination = model_directory(name)
    if destination.exists():
        raise ValueError(
            f"Thư mục model chưa hoàn chỉnh: {destination}. Đổi tên thư mục rồi tải lại."
        )
    progress(-1, f"Đang tải model {name}; có thể cần vài phút. Không gửi video lên mạng.")
    repository = f"Systran/faster-whisper-{name}"
    revision = HfApi().model_info(repository, token=False).sha
    snapshot_download(
        repository,
        revision=revision,
        local_dir=staging,
        token=False,
        allow_patterns=["config.json", "model.bin", "tokenizer.json", "vocabulary.*"],
    )
    if not all(
        (staging / name).is_file() for name in ("config.json", "model.bin", "tokenizer.json")
    ):
        raise ValueError("Model tải xuống thiếu tệp cần thiết. Hãy thử lại.")
    (staging / ".vkdub-ready").write_text(str(revision), encoding="utf-8")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging.replace(destination)
    return {"kind": "model", "model": name}


def transcribe(request: dict[str, Any], audio: Path) -> dict[str, Any]:
    settings = TranscriptionSettings(**request["settings"])
    if not model_ready(settings.model):
        raise ValueError("Model chưa được tải. Chọn TẢI MODEL trước khi bóc băng.")
    model_path = model_directory(settings.model)
    progress(-1, "Đang tính dấu vân tay âm thanh…")
    with audio.open("rb") as stream:
        fingerprint = hashlib.file_digest(stream, "sha256").hexdigest()
    # Auto deliberately uses the portable CPU path. CUDA is an explicit opt-in,
    # because detecting a GPU alone does not establish that CUDA/cuDNN DLLs work.
    device = "cpu" if settings.device == "auto" else settings.device
    key = cache_key(
        fingerprint,
        settings.model,
        request["language"],
        device,
        importlib.metadata.version("faster-whisper"),
        (model_path / ".vkdub-ready").read_text(encoding="utf-8"),
    )
    cached_file = workspace_root() / "cache" / "transcript" / f"{key}.json"
    legacy_cache = data_root() / "cache" / "transcript" / f"{key}.json"
    if not cached_file.exists() and legacy_cache.is_file():
        cached_file = legacy_cache
    if request.get("reuse_cache", True):
        try:
            cached = read_cached(cached_file, key)
        except (OSError, ValueError) as exc:
            progress(-1, f"Cache không hợp lệ, sẽ bóc băng lại: {exc}")
        else:
            if cached is not None:
                return {"kind": "transcript", "transcript": cached.to_dict(), "reused": True}
    progress(-1, f"Đang nạp model {settings.model} trên {device.upper()}…")
    provider: SpeechToTextProvider = FasterWhisperSTT(model_path, device)
    progress(0, "Đang nhận dạng giọng nói cục bộ…")
    segments, language, duration = provider.transcribe(audio, request["language"], progress)
    result = Transcript(
        segments, language, request["language"], duration, settings.model, device, fingerprint, key
    )
    try:
        atomic_json(cached_file, result.to_dict())
    except OSError as exc:
        progress(100, f"Đã bóc băng, nhưng không lưu được cache: {exc}")
    return {"kind": "transcript", "transcript": result.to_dict(), "reused": False}


def main() -> int:
    request_file = Path(sys.argv[1])
    result_file = Path(sys.argv[2])
    try:
        request = json.loads(request_file.read_text(encoding="utf-8"))
        if request["kind"] == "model":
            result = download_model(request["model"], request_file.parent / "model-download")
        else:
            result = transcribe(request, request_file.parent / "audio.wav")
        atomic_json(result_file, result)
        return 0
    except Exception as exc:
        # No authentication is used. Emit a concise error instead of dumping HTTP headers.
        atomic_json(result_file, {"error": f"{type(exc).__name__}: {exc}"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
