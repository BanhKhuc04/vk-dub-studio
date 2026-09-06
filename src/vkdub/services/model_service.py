import importlib.util
from pathlib import Path

from vkdub.domain.transcript import MODELS
from vkdub.utils.paths import data_root


def model_directory(name: str) -> Path:
    if name not in MODELS:
        raise ValueError("Model không được hỗ trợ.")
    return data_root() / "models" / name


def model_ready(name: str) -> bool:
    directory = model_directory(name)
    return all(
        (directory / file).is_file()
        for file in (
            "model.bin",
            "config.json",
            "tokenizer.json",
            ".vkdub-ready",
        )
    )


def dependency_ready() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None
