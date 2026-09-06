import importlib.util
from pathlib import Path

from vkdub.domain.transcript import MODELS
from vkdub.utils.paths import data_root


def model_directory(name: str) -> Path:
    if name not in MODELS:
        raise ValueError("Model không được hỗ trợ.")
    # 1. User data directory (downloaded or custom models)
    user_dir = data_root() / "models" / name
    if (user_dir / "model.bin").is_file() and (user_dir / "config.json").is_file():
        return user_dir

    # 2. Bundled models in application resources/internal models directory
    try:
        from vkdub.utils.paths import resource_path

        bundled = resource_path(f"models/{name}")
        if (bundled / "model.bin").is_file() and (bundled / "config.json").is_file():
            return bundled
    except Exception:
        pass

    return user_dir


def model_ready(name: str) -> bool:
    directory = model_directory(name)
    required = ("model.bin", "config.json", "tokenizer.json")
    return all((directory / file).is_file() for file in required)


def dependency_ready() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None
