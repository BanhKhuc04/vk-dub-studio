"""Install the reviewed upstream SDK revision; verify with actual speech, not a catalog."""

import hashlib
import json
from pathlib import Path

import httpx

from vkdub.media.voice_audio import audio_duration
from vkdub.providers.base import Progress
from vkdub.services.cache_service import atomic_json
from vkdub.services.voice_catalog import save_catalog
from vkdub.utils.paths import data_root

CAPCUT_REVISION = "e06da1f4e0c0010354f4e7702f02c18cbdd419a2"
SDK_FILES = (
    "__init__.py",
    "client.py",
    "config.py",
    "exceptions.py",
    "models.py",
    "signer.py",
    "uploader.py",
)


def capcut_root() -> Path:
    return data_root() / "engines" / "capcut"


async def setup_capcut(ffmpeg: str, ffprobe: str, progress: Progress) -> list[dict]:
    from vkdub.providers.capcut_tts import CapCutTTSProvider

    root = capcut_root()
    (root / "capcut_tts_api").mkdir(parents=True, exist_ok=True)
    marker = root / "ready.json"
    marker.unlink(missing_ok=True)
    progress(-1, "Đang chuẩn bị CapCut TTS và danh sách giọng tiếng Việt…")
    base = f"https://raw.githubusercontent.com/K07VN/capcut-tts-api/{CAPCUT_REVISION}/"
    files = [f"capcut_tts_api/{name}" for name in SDK_FILES] + [
        "Voice.json",
        "pyproject.toml",
        "README.md",
    ]
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            for name in files:
                response = await client.get(base + name)
                response.raise_for_status()
                if len(response.content) > 2_000_000:
                    raise ValueError("Tệp CapCut TTS vượt kích thước cho phép.")
                temp = (root / name).with_suffix(".download")
                temp.write_bytes(response.content)
                temp.replace(root / name)
        upstream = json.loads((root / "Voice.json").read_text(encoding="utf-8"))
        rows = []
        for voice in upstream:
            if "vi-vn" not in (voice["lang"].lower(), voice["lan"].lower()):
                continue
            key = hashlib.sha256(
                (voice["voice_type"] + ":" + voice["resource_id"]).encode()
            ).hexdigest()[:24]
            rows.append(
                {
                    "id": "capcut-" + key,
                    "name": voice["display_name"].strip(),
                    "custom": False,
                    "upstream_id": voice["voice_type"],
                    "resource_id": voice["resource_id"],
                }
            )
        if not rows:
            raise ValueError("Repo CapCut chưa trả danh sách giọng tiếng Việt.")
        save_catalog(rows, "capcut_tts")
        progress(-1, "Đang tạo audio thử qua CapCut… Nội dung thử được gửi trực tuyến.")
        provider = CapCutTTSProvider(ffmpeg)
        try:
            probe = root / "setup-probe.wav"
            await provider.synthesize(
                "Xin chào, đây là giọng đọc thử của CapCut.", rows[0]["id"], 1, probe
            )
            duration = await audio_duration(probe, ffprobe)
        finally:
            await provider.close()
        atomic_json(
            marker,
            {"revision": CAPCUT_REVISION, "duration_ms": duration, "tested_voice": rows[0]["id"]},
        )
        progress(100, f"CapCut đã tạo audio thử. Có {len(rows)} giọng trong catalog của repo.")
        return rows
    except httpx.HTTPError:
        raise ValueError(
            "Không tải được CapCut TTS. Kiểm tra mạng hoặc dùng VieNeu offline."
        ) from None
