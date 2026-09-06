import asyncio
from pathlib import Path

import httpx

from vkdub.domain.voice import Voice
from vkdub.providers.tts import TTSError
from vkdub.services.credential_service import remember_secret
from vkdub.services.tts_usage import TTSUsage

TTS_URL = "https://api.vbee.vn/v1/tts"
VOICES_URL = "https://vbee.vn/api/public/v1/voices"
# Official Realtime API supports these five labels. Other voices require Batch + webhook.
SYNC_LABELS = {
    "HN - Ngọc Huyền",
    "SG - Tường Vy",
    "HN - Mai Phương",
    "SG - Lan Trinh",
    "SG - Thảo Trinh",
}
MAX_AUDIO_BYTES = 32 * 1024 * 1024


def response_error(status: int) -> TTSError:
    if status in (401, 403):
        return TTSError(
            "Vbee từ chối xác thực/quyền API. Kiểm tra App ID, token, hạn token và gói API."
        )
    if status == 429:
        return TTSError("Vbee giới hạn yêu cầu đồng thời/quota. Chờ rồi thử lại câu lỗi.")
    if status == 400:
        return TTSError("Vbee từ chối yêu cầu: kiểm tra credit, mã giọng và quyền Realtime API.")
    return TTSError(
        f"Vbee trả lỗi HTTP {status}. Kiểm tra credit/gói API rồi thử lại; chưa tự gửi lại."
    )


class VbeeTTSProvider:
    name = "vbee"
    max_characters = 300

    def __init__(
        self,
        app_id: str,
        token: str,
        usage: TTSUsage,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not app_id or not token or any(c.isspace() for c in app_id + token):
            raise TTSError("Thiếu App ID hoặc token Vbee hợp lệ.")
        remember_secret(token)
        remember_secret(app_id)
        self.headers = {"Authorization": f"Bearer {token}", "App-Id": app_id}
        self.transport, self.usage = transport, usage

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=self.headers,
            transport=self.transport,
            timeout=httpx.Timeout(60, connect=15),
            follow_redirects=False,
        )

    async def list_voices(self) -> tuple[Voice, ...]:
        voices: dict[str, Voice] = {}
        cursor = ""
        seen: set[str] = set()
        try:
            async with self.client() as client:
                for _ in range(100):
                    response = await client.get(VOICES_URL, params={"limit": 100, "cursor": cursor})
                    if response.status_code != 200:
                        raise response_error(response.status_code)
                    if len(response.content) > 2 * 1024 * 1024:
                        raise TTSError("Danh sách giọng Vbee quá lớn.")
                    data = response.json()
                    if not isinstance(data, dict) or data.get("status") != 1:
                        raise TTSError("Không đọc được danh sách giọng Vbee. Kiểm tra gói API.")
                    result = data["result"]
                    for row in result["voices"]:
                        if (
                            row["language_code"] == "vi-VN"
                            and row["name"] in SYNC_LABELS
                            and isinstance(row["code"], str)
                            and row["code"]
                        ):
                            voices[row["code"]] = Voice(
                                row["code"], row["name"], row["language_code"]
                            )
                    page = result["pagination"]
                    if page["has_next_page"] is False:
                        return tuple(voices.values())
                    cursor = page["next_cursor"]
                    if not isinstance(cursor, str) or not cursor or cursor in seen:
                        break
                    seen.add(cursor)
        except httpx.HTTPError:
            raise TTSError("Không kết nối được Vbee. Kiểm tra mạng; chưa tạo voice.") from None
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, TTSError):
                raise
            raise TTSError("Danh sách giọng Vbee sai cấu trúc; chưa áp dụng.") from None
        raise TTSError("Phân trang danh sách giọng Vbee không hợp lệ hoặc vượt giới hạn.")

    async def synthesize(self, text: str, voice_id: str, speed: float, output_path: Path) -> Path:
        if not text.strip() or len(text) > self.max_characters:
            raise TTSError("Vbee Realtime yêu cầu 1–300 ký tự mỗi lượt.")
        if not 0.8 <= speed <= 1.3:
            raise TTSError("Tốc độ voice phải trong khoảng 0.8–1.3x.")
        # Do not retry POST automatically: a timeout may already have consumed credit.
        identifier = self.usage.begin(len(text))
        try:
            async with asyncio.timeout(120), self.client() as client:
                async with client.stream(
                    "POST",
                    TTS_URL,
                    json={
                        "text": text,
                        "voiceCode": voice_id,
                        "speed": speed,
                        "mode": "sync",
                        "outputFormat": "mp3",
                        "bitrate": 128,
                    },
                ) as response:
                    if response.status_code != 200:
                        raise response_error(response.status_code)
                    content_type = response.headers.get("content-type", "").split(";")[0].lower()
                    if content_type not in ("audio/mpeg", "audio/mp3", "application/octet-stream"):
                        raise TTSError(
                            "Vbee không trả audio MP3. Kiểm tra credit và quyền Realtime API."
                        )
                    count = 0
                    with output_path.open("wb") as stream:
                        async for chunk in response.aiter_bytes():
                            count += len(chunk)
                            if count > MAX_AUDIO_BYTES:
                                raise TTSError("Audio Vbee vượt giới hạn 32 MB mỗi lượt.")
                            stream.write(chunk)
                    if count == 0:
                        raise TTSError("Vbee trả audio trống.")
            self.usage.finish(identifier)
            return output_path
        except (httpx.HTTPError, TimeoutError):
            raise TTSError(
                "Kết nối Vbee gián đoạn/hết thời gian. Có thể đã tính phí; "
                "thử lại câu lỗi khi sẵn sàng."
            ) from None
