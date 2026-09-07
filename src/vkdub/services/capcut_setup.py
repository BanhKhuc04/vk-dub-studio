"""Install and verify CapCut TTS SDK and Vietnamese voice catalog directly from bundled resources."""

import hashlib
import json
import logging
import shutil
from pathlib import Path

from vkdub.media.voice_audio import audio_duration
from vkdub.providers.base import Progress
from vkdub.services.cache_service import atomic_json
from vkdub.services.voice_catalog import save_catalog
from vkdub.utils.paths import data_root

logger = logging.getLogger("vkdub.capcut")

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


def _find_bundled_capcut_files() -> tuple[Path, Path]:
    """Locate bundled capcut_tts_api directory and Voice.json."""
    import vkdub.integrations.capcut as capcut_pkg

    base_dir = Path(capcut_pkg.__file__).parent
    api_dir = base_dir / "capcut_tts_api"
    voice_json = base_dir / "Voice.json"
    if api_dir.is_dir() and voice_json.is_file():
        return api_dir, voice_json

    # Fallback to local appdata if already exists
    root = capcut_root()
    return root / "capcut_tts_api", root / "Voice.json"


async def setup_capcut(ffmpeg: str, ffprobe: str, progress: Progress) -> list[dict]:
    from vkdub.providers.capcut_tts import CapCutTTSProvider

    root = capcut_root()
    dest_api = root / "capcut_tts_api"
    dest_api.mkdir(parents=True, exist_ok=True)
    marker = root / "ready.json"
    marker.unlink(missing_ok=True)

    progress(-1, "Đang chuẩn bị CapCut TTS và danh sách giọng tiếng Việt…")

    src_api, src_voice = _find_bundled_capcut_files()

    # Stage bundled SDK files into root engines directory
    if src_api.is_dir() and src_api != dest_api:
        for name in SDK_FILES:
            src_file = src_api / name
            if src_file.is_file():
                shutil.copy2(src_file, dest_api / name)

    if src_voice.is_file() and src_voice != (root / "Voice.json"):
        shutil.copy2(src_voice, root / "Voice.json")

    # Read voices
    voice_file = root / "Voice.json" if (root / "Voice.json").is_file() else src_voice
    if not voice_file.is_file():
        raise ValueError("Không tìm thấy danh sách giọng đọc CapCut tích hợp.")

    upstream = json.loads(voice_file.read_text(encoding="utf-8"))
    rows = []
    for voice in upstream:
        lang = (voice.get("lang") or voice.get("lan") or "").lower()
        if "vi-vn" not in lang and "vi" != lang:
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
        raise ValueError("Không tìm thấy danh sách giọng tiếng Việt trong Voice.json.")

    save_catalog(rows, "capcut_tts")

    progress(-1, "Đang tạo audio thử qua CapCut… Nội dung thử được gửi trực tuyến.")
    provider = CapCutTTSProvider(ffmpeg)
    try:
        probe = root / "setup-probe.wav"
        await provider.synthesize(
            "Xin chào, đây là giọng đọc thử của CapCut.", rows[0]["id"], 1.0, probe
        )
        duration = await audio_duration(probe, ffprobe)
    except Exception as exc:
        raise ValueError(f"Không thể kết nối dịch vụ CapCut TTS: {exc}. Kiểm tra kết nối mạng của bạn.") from exc
    finally:
        await provider.close()

    atomic_json(
        marker,
        {"revision": CAPCUT_REVISION, "duration_ms": duration, "tested_voice": rows[0]["id"]},
    )
    progress(100, f"CapCut đã tạo audio thử thành công! Có {len(rows)} giọng đọc tiếng Việt sẵn sàng.")
    return rows

