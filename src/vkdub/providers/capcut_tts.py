"""CapCut TTS provider using httpx and the bundled SDK in-process."""

import asyncio
import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from vkdub.domain.voice import Voice
from vkdub.integrations.capcut.capcut_tts_api import CapCutClient
from vkdub.media.voice_audio import run_audio_command
from vkdub.providers.tts import TTSError
from vkdub.services.voice_catalog import find_voice, read_catalog

logger = logging.getLogger("vkdub.capcut")


def _speech_url(task: dict[str, Any]) -> str:
    payload = task["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    rows = payload.get("audio_subtitles", [])
    if len(rows) != 1 or str(rows[0].get("code", 0)) != "0" or rows[0].get("invalid_input"):
        raise ValueError("CapCut không tạo được âm thanh cho câu này.")
    url = rows[0]["speech_url"]
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("CapCut trả địa chỉ audio không hợp lệ.")
    return str(url)


def _sync_synthesize_to_file(
    text: str, upstream_id: str, resource_id: str, output_file: Path
) -> None:
    """Synchronous execution of CapCut TTS requests using httpx client."""
    sdk = CapCutClient(session=object())

    with httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=False) as client:

        def post(arguments: tuple) -> dict:
            url, headers, body = arguments
            response = client.post(url, headers=headers, content=body.encode())
            if response.status_code != 200:
                raise TTSError(
                    f"CapCut trả HTTP {response.status_code}. Thử lại hoặc dùng Vbee / VieNeu."
                )
            result = response.json()
            if str(result.get("ret", 0)) != "0":
                raise TTSError("CapCut từ chối yêu cầu. Thử lại hoặc dùng Vbee.")
            return dict(result)

        created = post(sdk.build_tts_new_request(text, upstream_id, resource_id, "1.0"))
        tasks = (created.get("data") or {}).get("tasks") or []
        if not tasks:
            raise TTSError("CapCut không nhận yêu cầu tạo giọng. Hãy thử lại hoặc dùng Vbee.")

        submitted = tasks[0]
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            result = post(sdk.build_query_request(submitted["id"], submitted["token"]))
            tasks = (result.get("data") or {}).get("tasks") or []
            if tasks and tasks[0].get("status") in ("succeed", "success"):
                url = _speech_url(tasks[0])
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    size = 0
                    with output_file.open("wb") as output:
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > 25_000_000:
                                raise TTSError("Audio CapCut quá lớn cho một câu.")
                            output.write(chunk)
                    if size < 100:
                        raise TTSError("CapCut trả audio trống.")
                return

            if tasks and tasks[0].get("status") in ("failed", "fail", "cancelled"):
                raise TTSError("CapCut không tạo được giọng này. Chọn giọng khác hoặc dùng Vbee.")

            time.sleep(0.5)

        raise TTSError("CapCut chờ quá lâu (timeout). Thử lại hoặc dùng Vbee / VieNeu.")


class CapCutTTSProvider:
    id = name = "capcut_tts"
    display_name = "CapCut TTS"
    max_characters = 500
    sample_rate = 48000

    def __init__(self, ffmpeg: str = "") -> None:
        self.ffmpeg = ffmpeg

    async def close(self) -> None:
        pass

    async def list_voices(self) -> tuple[Voice, ...]:
        return tuple(Voice(r["id"], r["name"], "vi") for r in read_catalog(self.name))

    async def synthesize(self, text: str, voice_id: str, speed: float, output_path: Path) -> Path:
        if not text.strip() or not 0.8 <= speed <= 1.3:
            raise TTSError("Nội dung hoặc tốc độ đọc không hợp lệ.")

        voice = find_voice(voice_id, self.name)
        upstream_id = voice.get("upstream_id", "")
        resource_id = voice.get("resource_id", "")
        if not upstream_id or not resource_id:
            raise TTSError(f"Không tìm thấy cấu hình giọng CapCut: {voice_id}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="capcut-", dir=output_path.parent) as folder:
            raw = Path(folder) / "source.mp3"

            # Execute in background thread to never block Qt main thread
            try:
                await asyncio.to_thread(
                    _sync_synthesize_to_file, text, upstream_id, resource_id, raw
                )
            except Exception as exc:
                if isinstance(exc, TTSError):
                    raise
                raise TTSError(f"Lỗi tạo giọng CapCut: {exc}") from exc

            # Normalize to PCM WAV with speed adjustment using FFmpeg
            await run_audio_command(
                [
                    self.ffmpeg,
                    "-y",
                    "-nostdin",
                    "-v",
                    "error",
                    "-i",
                    str(raw),
                    "-af",
                    f"atempo={speed}",
                    "-ar",
                    str(self.sample_rate),
                    "-c:a",
                    "pcm_s16le",
                    str(output_path),
                ]
            )

        return output_path
