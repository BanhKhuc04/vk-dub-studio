"""Explicit, cancellable local engine setup and custom voice enrollment."""

import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

from vkdub.media.voice_audio import audio_duration, run_audio_command
from vkdub.providers.base import Progress
from vkdub.providers.vieneu_local import VieNeuLocalProvider, stop_owned_process
from vkdub.services.cache_service import atomic_json
from vkdub.services.voice_catalog import (
    VIENEU_VERSION,
    engine_python,
    engine_root,
    install_presets,
    read_catalog,
    save_catalog,
)
from vkdub.utils.paths import data_root


async def _setup_command(arguments: list[str], progress: Progress, message: str) -> None:
    root = engine_root()
    root.mkdir(parents=True, exist_ok=True)
    with (root / "setup.log").open("ab") as output:
        process = await asyncio.create_subprocess_exec(
            *arguments,
            stdout=output,
            stderr=output,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        try:
            async with asyncio.timeout(1800):
                while process.returncode is None:
                    progress(-1, message)
                    try:
                        await asyncio.wait_for(process.wait(), 3)
                    except TimeoutError:
                        continue
                if process.returncode:
                    raise ValueError(
                        "Chưa cài được VieNeu. Kiểm tra mạng và log cài đặt, rồi thử lại."
                    )
        finally:
            if process.returncode is None:
                await stop_owned_process(process)


async def setup_vieneu(ffmpeg: str, ffprobe: str, progress: Progress) -> list[dict]:
    root = engine_root()
    if not engine_python().is_file():
        await _setup_command(
            [sys.executable, "-m", "venv", str(root)],
            progress,
            "Đang chuẩn bị môi trường riêng cho VieNeu…",
        )
    await _setup_command(
        [
            str(engine_python()),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            f"vieneu=={VIENEU_VERSION}",
        ],
        progress,
        "Đang cài VieNeu và các thư viện cần thiết…",
    )
    progress(-1, "Đang tải/kiểm tra model VieNeu v3 Turbo. Lần đầu có thể mất vài phút…")
    provider = VieNeuLocalProvider(ffmpeg, allow_download=True)
    try:
        result = await provider.request("catalog")
        presets = result["voices"]
        if not presets:
            raise ValueError("VieNeu chưa có danh sách giọng.")
        # Probe synthesis with the SDK's actual returned ID before publishing readiness.
        probe = root / "setup-probe.wav"
        await provider.request(
            "synthesize",
            text="Xin chào, giọng đọc đã sẵn sàng.",
            voice={"custom": False, "upstream_id": presets[0][1]},
            output=str(probe),
        )
        duration = await audio_duration(probe, ffprobe)
        rows = install_presets(presets)
        model_files = [
            {"path": str(path.relative_to(root)), "size": path.stat().st_size}
            for path in (root / "models").rglob("*")
            if path.is_file() and "snapshots" in path.parts
        ]
        atomic_json(
            root / "ready.json",
            {
                "version": VIENEU_VERSION,
                "duration_ms": duration,
                "model_files": model_files,
            },
        )
        progress(100, f"VieNeu đã tạo audio kiểm thử thành công. Có {len(rows)} giọng.")
        return rows
    finally:
        await provider.close()


async def register_voice(name: str, reference: Path, ffmpeg: str, ffprobe: str) -> str:
    name = name.strip()
    if not name or len(name) > 100 or not reference.is_file():
        raise ValueError("Nhập tên giọng và chọn tệp âm thanh hợp lệ.")
    duration = await audio_duration(reference, ffprobe)
    if not 3000 <= duration <= 30000:
        raise ValueError("Chọn mẫu giọng rõ, dài từ 3 đến 30 giây; app sẽ dùng tối đa 8 giây.")
    identifier = "custom-" + uuid4().hex
    folder = data_root() / "voices" / identifier
    folder.mkdir(parents=True)
    copied = folder / "reference.wav"
    profile = folder / "profile.json"
    await run_audio_command(
        [
            ffmpeg,
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(reference),
            "-t",
            "8",
            "-ac",
            "1",
            "-ar",
            "48000",
            str(copied),
        ]
    )
    provider = VieNeuLocalProvider(ffmpeg, allow_download=True)
    try:
        await provider.request(
            "register", name=identifier, reference=str(copied), profile=str(profile)
        )
        rows = read_catalog()
        rows.append(
            {
                "id": identifier,
                "name": name,
                "custom": True,
                "reference": str(copied),
                "profile": str(profile),
            }
        )
        save_catalog(rows)
    finally:
        await provider.close()
    return identifier
