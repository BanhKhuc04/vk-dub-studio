import asyncio
from pathlib import Path

import httpx

from vkdub.domain.voice import POPULAR_ELEVENLABS_VOICES, Voice
from vkdub.providers.tts import TTSError
from vkdub.services.credential_service import remember_secret
from vkdub.services.tts_usage import TTSUsage

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"
MAX_AUDIO_BYTES = 32 * 1024 * 1024


def response_error(status: int) -> TTSError:
    if status == 401:
        return TTSError("ElevenLabs từ chối xác thực. Kiểm tra lại API Key trong Cài đặt.")
    if status == 429:
        return TTSError(
            "ElevenLabs đã hết hạn mức (Quota Exceeded). "
            "Gói 10.000 ký tự miễn phí của tháng này đã dùng hết."
        )
    if status == 400:
        return TTSError("ElevenLabs từ chối yêu cầu. Kiểm tra mã giọng và nội dung văn bản.")
    return TTSError(f"ElevenLabs trả lỗi HTTP {status}. Vui lòng thử lại sau.")


class ElevenLabsTTSProvider:
    name = "elevenlabs"
    max_characters = 1000

    def __init__(
        self,
        api_key: str,
        usage: TTSUsage | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        api_key = api_key.strip()
        if not api_key:
            raise TTSError("Thiếu ElevenLabs API Key. Hãy nhập trong Cài đặt.")
        remember_secret(api_key)
        self.api_key = api_key
        self.headers = {
            "xi-api-key": api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        self.transport = transport
        self.usage = usage or TTSUsage()

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=self.headers,
            transport=self.transport,
            timeout=httpx.Timeout(60, connect=15),
            follow_redirects=True,
        )

    async def list_voices(self) -> tuple[Voice, ...]:
        """Fetch available voices from ElevenLabs API or fallback to popular defaults."""
        try:
            async with self.client() as client:
                response = await client.get(f"{ELEVENLABS_API_BASE}/voices")
                if response.status_code != 200:
                    return POPULAR_ELEVENLABS_VOICES
                data = response.json()
                voices_list = data.get("voices", [])
                result = []
                for v in voices_list:
                    vid = v.get("voice_id")
                    name = v.get("name", "Unnamed")
                    cat = v.get("category", "")
                    label = f"{name} ({cat})" if cat else name
                    if vid:
                        result.append(Voice(code=vid, name=label, language="vi"))
                if result:
                    return tuple(result)
        except Exception:
            pass
        return POPULAR_ELEVENLABS_VOICES

    async def synthesize(self, text: str, voice_id: str, speed: float, output_path: Path) -> Path:
        """Synthesize speech using ElevenLabs Multilingual v2 model."""
        if not text.strip() or len(text) > self.max_characters:
            raise TTSError(f"ElevenLabs yêu cầu văn bản 1–{self.max_characters} ký tự mỗi lượt.")

        identifier = self.usage.begin(len(text))
        url = f"{ELEVENLABS_API_BASE}/text-to-speech/{voice_id}"
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "speed": max(0.7, min(1.3, speed)),
            },
        }

        try:
            async with asyncio.timeout(120), self.client() as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        raise response_error(response.status_code)
                    count = 0
                    with output_path.open("wb") as stream:
                        async for chunk in response.aiter_bytes():
                            count += len(chunk)
                            if count > MAX_AUDIO_BYTES:
                                raise TTSError("Audio ElevenLabs vượt giới hạn dung lượng 32 MB.")
                            stream.write(chunk)
                    if count == 0:
                        raise TTSError("ElevenLabs trả về dữ liệu audio rỗng.")

            self.usage.finish(identifier)
            return output_path
        except (httpx.HTTPError, TimeoutError):
            raise TTSError(
                "Kết nối ElevenLabs bị gián đoạn hoặc hết thời gian. "
                "Vui lòng kiểm tra mạng và thử lại."
            ) from None
