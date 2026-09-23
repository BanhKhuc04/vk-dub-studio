"""KAPPAK Ask AI — LLM chat service with streaming response and conversation history."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

logger = logging.getLogger("kappak.services.ask_kappak")

GEMINI_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/"
DEFAULT_MODEL = "gemini-3.5-flash"
SYSTEM_PROMPT = (
    "Bạn là trợ lý AI của KAPPAK Studio — một công cụ tạo video ngắn viral "
    "và lồng tiếng tự động tiếng Việt. "
    "Hỗ trợ người dùng: tạo kịch bản video, tối ưu nội dung, gợi ý hook viral, "
    "hướng dẫn quy trình dựng video 9:16, trả lời câu hỏi về sản xuất nội dung. "
    "Trả lời ngắn gọn, thực tế, có ví dụ cụ thể khi phù hợp. "
    "Luôn trả lời bằng tiếng Việt."
)


@dataclass
class ChatMessage:
    role: str  # "user" | "model"
    content: str
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content, "timestamp": self.timestamp}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> ChatMessage:
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", ""),
        )


def _get_gemini_key() -> str | None:
    """Load Gemini API key from Windows Credential Manager or env."""
    try:
        from vkdub.services.credential_service import CredentialStore

        key = CredentialStore().get()
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY") or None


async def _stream_gemini(
    api_key: str,
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
):
    """Call Gemini with SSE streaming. Yields (chunk_text, error_msg) tuples."""
    url = f"{GEMINI_API_ENDPOINT}{model}:streamGenerateContent?key={api_key}&alt=sse"

    contents = [
        {"role": msg["role"], "parts": [{"text": msg["content"]}]}
        for msg in messages
        if msg["role"] != "system"
    ]

    payload = {
        "contents": contents,
        "systemInstruction": {"role": "system", "parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
            "topP": 0.95,
            "topK": 40,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            async with client.stream("POST", url, json=payload) as resp:
                if resp.status_code != 200:
                    try:
                        err_body = await resp.aread()
                        err_json = json.loads(err_body)
                        err_msg = err_json.get("error", {}).get(
                            "message", f"HTTP {resp.status_code}"
                        )
                    except Exception:
                        err_msg = f"HTTP {resp.status_code}"
                    yield "", err_msg
                    return

                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("{"):
                        continue
                    try:
                        chunk = json.loads(line)
                        parts = (
                            chunk.get("candidates", [{}])[0]
                            .get("content", {})
                            .get("parts", [])
                        )
                        for part in parts:
                            if "text" in part:
                                yield part["text"], ""
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
    except httpx.TimeoutException:
        yield "", "Yêu cầu bị timeout. Vui lòng thử lại."
    except Exception as exc:
        logger.error("Gemini streaming error: %s", exc)
        yield "", f"Lỗi kết nối Gemini: {exc}"


async def _non_stream_gemini(
    api_key: str,
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
) -> tuple[str, str]:
    """Call Gemini without streaming. Returns (text, error)."""
    url = f"{GEMINI_API_ENDPOINT}{model}:generateContent?key={api_key}"

    contents = [
        {"role": msg["role"], "parts": [{"text": msg["content"]}]}
        for msg in messages
        if msg["role"] != "system"
    ]

    payload = {
        "contents": contents,
        "systemInstruction": {"role": "system", "parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                try:
                    err_json = resp.json()
                    err_msg = err_json.get("error", {}).get("message", f"HTTP {resp.status_code}")
                except Exception:
                    err_msg = f"HTTP {resp.status_code}"
                return "", err_msg

            data = resp.json()
            parts = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [])
            )
            text = "".join(p.get("text", "") for p in parts)
            return text, ""
    except httpx.TimeoutException:
        return "", "Yêu cầu bị timeout. Vui lòng thử lại."
    except Exception as exc:
        logger.error("Gemini non-stream error: %s", exc)
        return "", f"Lỗi kết nối Gemini: {exc}"


# Global service instance (lazy-initialized per server process)
_ask_service: AskKappakService | None = None


def get_ask_service() -> AskKappakService:
    global _ask_service
    if _ask_service is None:
        _ask_service = AskKappakService()
        _ask_service.load_history()
    return _ask_service


class AskKappakService:
    """Conversation service for Ask KAPPAK AI chat."""

    MAX_HISTORY = 20  # Keep last N user+assistant exchanges

    def __init__(self, max_history: int = MAX_HISTORY) -> None:
        self._history: list[ChatMessage] = []
        self._max_history = max_history
        self._history_file = self._get_history_path()

    @staticmethod
    def _get_history_path() -> Path:
        from vkdub.utils.paths import workspace_root

        return workspace_root() / "auto_save" / "ask_kappak_history.json"

    def _prune_history(self) -> None:
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def add_user_message(self, content: str) -> ChatMessage:
        msg = ChatMessage(role="user", content=content)
        self._history.append(msg)
        self._prune_history()
        return msg

    def add_ai_message(self, content: str) -> ChatMessage:
        msg = ChatMessage(role="model", content=content)
        self._history.append(msg)
        self._prune_history()
        return msg

    def get_history_dicts(self) -> list[dict[str, str]]:
        return [m.to_dict() for m in self._history]

    def clear_history(self) -> None:
        self._history.clear()

    def get_history(self) -> list[ChatMessage]:
        return list(self._history)

    def load_history(self) -> bool:
        """Load history from disk. Returns True if successful."""
        path = self._history_file
        if not path.is_file():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._history = [ChatMessage.from_dict(m) for m in data]
            return True
        except Exception:
            return False

    def save_history(self) -> None:
        """Persist history to disk."""
        try:
            self._history_file.parent.mkdir(parents=True, exist_ok=True)
            self._history_file.write_text(
                json.dumps([m.to_dict() for m in self._history], ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Could not save Ask KAPPAK history: %s", exc)

    async def chat(
        self,
        user_message: str,
        model: str = DEFAULT_MODEL,
        stream: bool = True,
    ):
        """Send message, get AI response. Yields (chunk_text, is_done, error)."""
        self.add_user_message(user_message)

        api_key = _get_gemini_key()
        if not api_key:
            yield "", True, "Chưa có Gemini API key. Vui lòng mở Cài đặt để nhập key."
            return

        msgs_for_llm = [{"role": m.role, "content": m.content} for m in self._history]
        full_text = ""

        async for chunk, err in _stream_gemini(api_key, msgs_for_llm, model):
            if err:
                yield "", True, err
                return
            full_text += chunk
            yield chunk, False, ""

        self.add_ai_message(full_text)
        self.save_history()
        yield "", True, ""

    async def chat_nonstream(
        self,
        user_message: str,
        model: str = DEFAULT_MODEL,
    ) -> tuple[str, str]:
        """Non-streaming: send message, get full AI response. Returns (text, error)."""
        self.add_user_message(user_message)

        api_key = _get_gemini_key()
        if not api_key:
            return "", "Chưa có Gemini API key. Vui lòng mở Cài đặt → API & Chi phí để nhập key."

        msgs_for_llm = [{"role": m.role, "content": m.content} for m in self._history]
        full_text, error = await _non_stream_gemini(api_key, msgs_for_llm, model)

        if error:
            return "", error

        self.add_ai_message(full_text)
        self.save_history()
        return full_text, ""

    def has_api_key(self) -> bool:
        return bool(_get_gemini_key())
