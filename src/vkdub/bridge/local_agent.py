"""VK Dub Studio — Local Agent.

Runs inside the Desktop application, managing local IPC communication
with the Native Messaging Host and Browser Extension.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from vkdub.bridge.protocol import Actions, BridgeStatus
from vkdub.bridge.registry import ensure_host_registered

logger = logging.getLogger("vkdub.local_agent")

DEFAULT_PORT = 49814
DEFAULT_HOST = "127.0.0.1"


class LocalAgent(QObject):
    """Desktop Local Agent managing the Browser Bridge connection."""

    browser_connection_changed = Signal(bool)
    status_updated = Signal(object)  # BridgeStatus
    message_received = Signal(dict)
    chatgpt_result_received = Signal(dict)
    vbee_result_received = Signal(dict)
    log_emitted = Signal(str)

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.host = host
        self.port = port
        self.server_sock: socket.socket | None = None
        self.client_sock: socket.socket | None = None
        self.running = False
        self.status = BridgeStatus(browser_connected=False)
        self._lock = threading.Lock()
        self._pending_requests: dict[str, tuple[threading.Event, dict[str, Any]]] = {}

    def start(self) -> bool:
        """Initialize registry keys and start background socket listener."""
        if self.running:
            return True

        # Ensure host is registered in Windows registry
        ensure_host_registered()

        try:
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind((self.host, self.port))
            self.server_sock.listen(2)
            self.server_sock.settimeout(1.0)
            self.running = True

            thread = threading.Thread(target=self._accept_loop, daemon=True)
            thread.name = "LocalAgentAccept"
            thread.start()
            logger.info("Local Agent listening on %s:%d", self.host, self.port)
            return True
        except Exception as exc:
            logger.error(
                "Failed to start Local Agent server on %s:%d: %s", self.host, self.port, exc
            )
            self.stop()
            return False

    def _accept_loop(self) -> None:
        """Accept incoming connection from vkdub_host.py."""
        assert self.server_sock is not None
        while self.running:
            try:
                sock, addr = self.server_sock.accept()
                logger.info("Native host connected from %s", addr)
                with self._lock:
                    if self.client_sock:
                        try:
                            self.client_sock.close()
                        except Exception:
                            pass
                    self.client_sock = sock

                self.status.browser_connected = True
                self.browser_connection_changed.emit(True)
                self.status_updated.emit(self.status)

                # Request full status report from extension
                self.request_status()

                # Handle communication with this client
                self._handle_client(sock)
            except TimeoutError:
                continue
            except Exception as exc:
                if self.running:
                    logger.warning("Error in Local Agent accept loop: %s", exc)

    def _handle_client(self, sock: socket.socket) -> None:
        """Read newline-delimited JSON messages from native host."""
        buf = ""
        try:
            while self.running:
                chunk = sock.recv(4096)
                if not chunk:
                    logger.info("Native host disconnected.")
                    break
                buf += chunk.decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._process_message(line)
        except Exception as exc:
            logger.debug("Socket read ended: %s", exc)
        finally:
            with self._lock:
                if self.client_sock is sock:
                    self.client_sock = None
                try:
                    sock.close()
                except Exception:
                    pass

            self.status.browser_connected = False
            self.browser_connection_changed.emit(False)
            self.status_updated.emit(self.status)

    def _process_message(self, raw_json: str) -> None:
        """Process incoming JSON message from native host / extension."""
        try:
            msg = json.loads(raw_json)
        except Exception as exc:
            logger.warning("Failed to parse message JSON: %s", exc)
            return

        action = msg.get("action")
        logger.debug("Local Agent received action: %s", action)
        self.message_received.emit(msg)

        if action == Actions.STATUS_REPORT:
            payload = msg.get("payload", {})
            new_status = BridgeStatus.from_payload(payload)
            new_status.browser_connected = True
            self.status = new_status
            self.status_updated.emit(self.status)
            self.log_emitted.emit(
                f"Cập nhật trạng thái trình duyệt: ChatGPT="
                f"{'Đã đăng nhập' if new_status.chatgpt_logged_in else 'Chưa đăng nhập'}, "
                f"Vbee={'Đã đăng nhập' if new_status.vbee_logged_in else 'Chưa đăng nhập'}"
            )
        elif action == Actions.CHATGPT_TRANSLATE_RESULT:
            payload = msg.get("payload", {})
            req_id = payload.get("request_id")
            self.chatgpt_result_received.emit(payload)
            if req_id and req_id in self._pending_requests:
                event, container = self._pending_requests[req_id]
                container.update(payload)
                event.set()
        elif action == Actions.VBEE_VOICE_RESULT:
            payload = msg.get("payload", {})
            req_id = payload.get("request_id")
            self.vbee_result_received.emit(payload)
            if req_id and req_id in self._pending_requests:
                event, container = self._pending_requests[req_id]
                container.update(payload)
                event.set()
        elif action == Actions.HELLO:
            self.log_emitted.emit("Trình duyệt Microsoft Edge đã kết nối thành công.")
            self.request_status()

    def translate_srt_sync(
        self,
        srt_content: str,
        prompt_instruction: str = "",
        timeout_s: float = 360.0,
    ) -> str:
        """Execute ChatGPT translation through the browser extension synchronously.

        Returns the extracted translated SRT string. Raises RuntimeError on failure or timeout.
        """
        import uuid

        if not self.status.browser_connected:
            raise RuntimeError(
                "Trình duyệt Microsoft Edge chưa kết nối. Vui lòng mở Microsoft Edge trước khi dịch."
            )

        req_id = str(uuid.uuid4())
        event = threading.Event()
        container: dict[str, Any] = {}
        self._pending_requests[req_id] = (event, container)

        try:
            sent = self.send_command(
                Actions.CHATGPT_TRANSLATE,
                {
                    "srt_content": srt_content,
                    "prompt_instruction": prompt_instruction,
                    "request_id": req_id,
                },
            )
            if not sent:
                raise RuntimeError("Không thể gửi lệnh dịch sang extension Microsoft Edge.")

            logger.info("Đã gửi yêu cầu dịch sang ChatGPT (request_id=%s). Đang chờ...", req_id)
            completed = event.wait(timeout=timeout_s)
            if not completed:
                raise TimeoutError(f"Quá thời gian chờ phản hồi dịch từ ChatGPT ({timeout_s}s).")

            if not container.get("success", False):
                err = container.get("error", "Lỗi không xác định từ extension.")
                raise RuntimeError(f"ChatGPT dịch thất bại: {err}")

            translated_srt = container.get("translated_srt", "").strip()
            if not translated_srt:
                raise ValueError("Kết quả dịch từ ChatGPT rỗng hoặc không hợp lệ.")

            return translated_srt
        finally:
            self._pending_requests.pop(req_id, None)

    def generate_vbee_sync(
        self,
        srt_content: str,
        target_audio_path: Path,
        voice_name: str = "Ngọc Huyền",
        speed: str = "1.1x",
        timeout_s: float = 600.0,
    ) -> Path:
        """Execute Vbee dubbing synthesis through the browser extension synchronously.

        Downloads or writes the master audio to target_audio_path.
        """
        import base64
        import uuid

        if not self.status.browser_connected:
            raise RuntimeError(
                "Trình duyệt Microsoft Edge chưa kết nối. Vui lòng mở Microsoft Edge trước khi tạo voice."
            )

        req_id = str(uuid.uuid4())
        event = threading.Event()
        container: dict[str, Any] = {}
        self._pending_requests[req_id] = (event, container)

        try:
            sent = self.send_command(
                Actions.VBEE_GENERATE_VOICE,
                {
                    "srt_content": srt_content,
                    "voice_name": voice_name,
                    "speed": speed,
                    "request_id": req_id,
                },
            )
            if not sent:
                raise RuntimeError("Không thể gửi lệnh tạo voice sang extension Vbee.")

            logger.info("Đã gửi yêu cầu tạo voice Vbee (request_id=%s). Đang xử lý...", req_id)
            completed = event.wait(timeout=timeout_s)
            if not completed:
                raise TimeoutError(f"Quá thời gian chờ tạo voice từ Vbee ({timeout_s}s).")

            if not container.get("success", False):
                err = container.get("error", "Lỗi không xác định từ extension Vbee.")
                raise RuntimeError(f"Vbee tạo voice thất bại: {err}")

            audio_b64 = container.get("audio_base64")
            if audio_b64:
                target_audio_path.parent.mkdir(parents=True, exist_ok=True)
                raw_bytes = base64.b64decode(audio_b64)
                target_audio_path.write_bytes(raw_bytes)
                logger.info("Đã lưu master audio Vbee thành công vào: %s", target_audio_path)
                return target_audio_path

            # If audio_b64 not directly returned, check audio_url
            audio_url = container.get("audio_url")
            if audio_url and audio_url.startswith("http"):
                import httpx

                target_audio_path.parent.mkdir(parents=True, exist_ok=True)
                with httpx.Client(timeout=30.0) as client:
                    resp = client.get(audio_url)
                    resp.raise_for_status()
                    target_audio_path.write_bytes(resp.content)
                logger.info("Đã tải master audio Vbee từ URL: %s", target_audio_path)
                return target_audio_path

            raise RuntimeError("Extension báo thành công nhưng không có dữ liệu audio hợp lệ.")
        finally:
            self._pending_requests.pop(req_id, None)

    def send_command(self, action: str, payload: dict[str, Any] | None = None) -> bool:
        """Send command to Browser Extension via native host."""
        with self._lock:
            if not self.client_sock:
                logger.warning("Cannot send command %s: no native host connected", action)
                return False
            sock = self.client_sock

        msg = {
            "action": action,
            "payload": payload or {},
            "timestamp": time.time(),
        }
        try:
            data = (json.dumps(msg) + "\n").encode("utf-8")
            sock.sendall(data)
            return True
        except Exception as exc:
            logger.error("Failed to send command %s: %s", action, exc)
            return False

    def request_status(self) -> bool:
        """Request immediate status refresh from browser extension."""
        return self.send_command(Actions.GET_STATUS)

    def open_browser(self, target_url: str = "https://chatgpt.com") -> bool:
        """Open target URL in user's default browser."""
        try:
            if sys.platform == "win32":
                os.startfile(target_url)  # type: ignore[attr-defined]
                return True
        except Exception:
            pass

        try:
            return webbrowser.open(target_url)
        except Exception as exc:
            logger.error("Failed to open browser URL %s: %s", target_url, exc)
            return False

    def stop(self) -> None:
        """Shut down server and disconnect all sockets."""
        self.running = False
        with self._lock:
            if self.client_sock:
                try:
                    self.client_sock.close()
                except Exception:
                    pass
                self.client_sock = None

            if self.server_sock:
                try:
                    self.server_sock.close()
                except Exception:
                    pass
                self.server_sock = None

        self.status.browser_connected = False
        self.browser_connection_changed.emit(False)
        self.status_updated.emit(self.status)
        logger.info("Local Agent stopped.")
