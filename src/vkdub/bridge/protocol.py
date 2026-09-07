"""VK Dub Studio — Browser Bridge Protocol & Status Models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PROTOCOL_VERSION = "1.0.0"
NATIVE_HOST_NAME = "com.vkdub.bridge"


class Actions:
    PING = "PING"
    PONG = "PONG"
    HELLO = "HELLO"
    GET_STATUS = "GET_STATUS"
    STATUS_REPORT = "STATUS_REPORT"
    LOG_EVENT = "LOG_EVENT"
    CHATGPT_TRANSLATE = "CHATGPT_TRANSLATE"
    CHATGPT_TRANSLATE_RESULT = "CHATGPT_TRANSLATE_RESULT"
    VBEE_GENERATE_VOICE = "VBEE_GENERATE_VOICE"
    VBEE_VOICE_RESULT = "VBEE_VOICE_RESULT"


@dataclass
class BridgeStatus:
    """Live status reported by the VK Dub Browser Extension."""

    browser_connected: bool = False
    chatgpt_available: bool = False
    chatgpt_logged_in: bool = False
    vbee_available: bool = False
    vbee_logged_in: bool = False
    browser_name: str = "Chưa kết nối"
    chatgpt_tabs: int = 0
    vbee_tabs: int = 0
    timestamp: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> BridgeStatus:
        active_tabs = payload.get("active_tabs", {})
        return cls(
            browser_connected=bool(payload.get("browser_connected", False)),
            chatgpt_available=bool(payload.get("chatgpt_available", False)),
            chatgpt_logged_in=bool(payload.get("chatgpt_logged_in", False)),
            vbee_available=bool(payload.get("vbee_available", False)),
            vbee_logged_in=bool(payload.get("vbee_logged_in", False)),
            browser_name=str(payload.get("browser_name", "Microsoft Edge")),
            chatgpt_tabs=int(active_tabs.get("chatgpt", 0)),
            vbee_tabs=int(active_tabs.get("vbee", 0)),
            timestamp=float(payload.get("timestamp", 0.0)),
            details=dict(payload.get("details", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "browser_connected": self.browser_connected,
            "chatgpt_available": self.chatgpt_available,
            "chatgpt_logged_in": self.chatgpt_logged_in,
            "vbee_available": self.vbee_available,
            "vbee_logged_in": self.vbee_logged_in,
            "browser_name": self.browser_name,
            "chatgpt_tabs": self.chatgpt_tabs,
            "vbee_tabs": self.vbee_tabs,
            "timestamp": self.timestamp,
            "details": self.details,
        }
