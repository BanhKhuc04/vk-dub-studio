"""VK Dub Studio — Local Agent.

Runs inside the Desktop application, managing local IPC communication
with the Native Messaging Host and Browser Extension.
"""

from __future__ import annotations

import hashlib
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
from vkdub.bridge.ws_framing import (
    create_websocket_handshake_response,
    decode_ws_frame,
    encode_ws_frame,
    extract_websocket_key,
    is_websocket_request,
)

logger = logging.getLogger("vkdub.local_agent")

DEFAULT_PORT = 49814
DEFAULT_HOST = "127.0.0.1"
MIN_AUDIO_BYTES = 1024


def _looks_like_audio(data: bytes) -> bool:
    """Reject empty/HTML responses before they become a voice checkpoint."""
    if len(data) < MIN_AUDIO_BYTES:
        return False
    return bool(
        data.startswith((b"ID3", b"RIFF", b"OggS", b"fLaC"))
        or (len(data) >= 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)
        or (len(data) >= 12 and data[4:8] == b"ftyp")
    )


def _write_verified_audio(target: Path, data: bytes, source: str) -> Path:
    if not _looks_like_audio(data):
        raise RuntimeError(
            f"Dữ liệu audio Vbee không hợp lệ từ {source} ({len(data)} bytes)."
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    try:
        temporary.write_bytes(data)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def _edge_download_directories() -> list[Path]:
    """Read configured Edge download folders without assuming a profile name."""
    candidates = [
        Path.home() / "Downloads",
        Path.home() / "AppData" / "Local" / "VKDubStudio" / "vbee_staging" / "downloads",
    ]
    edge_root = Path.home() / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"
    preferences_files = edge_root.glob("*/Preferences") if edge_root.is_dir() else ()
    for preferences in preferences_files:
        try:
            payload = json.loads(preferences.read_text(encoding="utf-8", errors="ignore"))
            configured = payload.get("download", {}).get("default_directory")
            if configured:
                candidates.insert(0, Path(configured))
        except (OSError, ValueError, TypeError):
            logger.debug("Không đọc được Edge Preferences: %s", preferences)

    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def _matching_audio_candidates(job_name: str, explicit_path: str | None = None) -> list[Path]:
    paths: list[Path] = []
    if explicit_path:
        reported = Path(explicit_path)
        paths.extend([reported, Path(str(reported) + ".crdownload")])

    patterns = {job_name, job_name.replace("_", ""), job_name.replace("-", "")}
    parts = job_name.split("_")
    if len(parts) > 1 and parts[-1]:
        patterns.add(parts[-1])

    for directory in _edge_download_directories():
        if not directory.is_dir():
            continue
        for pat in patterns:
            paths.extend(directory.glob(f"*{pat}*.mp3"))
            paths.extend(directory.glob(f"*{pat}*.mp3.crdownload"))

    deduplicated: list[Path] = []
    for path in paths:
        if path not in deduplicated and "unconfirmed" not in path.name.lower():
            deduplicated.append(path)
    return deduplicated


def _wait_for_correlated_audio(
    job_name: str,
    explicit_path: str | None = None,
    timeout_s: float = 60.0,
) -> Path | None:
    """Wait for the exact Vbee job download, including a stable Edge .crdownload."""
    deadline = time.monotonic() + timeout_s
    observations: dict[Path, tuple[int, int]] = {}
    while True:
        for candidate in _matching_audio_candidates(job_name, explicit_path):
            try:
                size = candidate.stat().st_size
                previous_size, stable_count = observations.get(candidate, (-1, 0))
                stable_count = stable_count + 1 if size == previous_size else 0
                observations[candidate] = (size, stable_count)
                if size < MIN_AUDIO_BYTES:
                    continue
                if candidate.suffix == ".crdownload" and stable_count < 2:
                    continue
                with candidate.open("rb") as stream:
                    prefix = stream.read(16)
                if _looks_like_audio(prefix + b"\0" * MIN_AUDIO_BYTES):
                    return candidate
            except OSError:
                continue
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.5)


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
        self.is_client_ws = False
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
        """Accept incoming connection from browser extension or native host."""
        assert self.server_sock is not None
        while self.running:
            try:
                sock, addr = self.server_sock.accept()
                logger.info("Client connected from %s", addr)
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

                # Handle communication with this client
                self._handle_client(sock)
            except TimeoutError:
                continue
            except Exception as exc:
                if self.running:
                    logger.warning("Error in Local Agent accept loop: %s", exc)

    def _handle_client(self, sock: socket.socket) -> None:
        """Read messages from client, supporting both direct WebSocket and raw TCP native host."""
        raw_buf = bytearray()
        text_buf = ""
        is_ws = False
        handshake_done = False

        try:
            while self.running:
                chunk = sock.recv(4096)
                if not chunk:
                    logger.info("Client disconnected.")
                    break

                if not handshake_done:
                    if is_websocket_request(chunk):
                        is_ws = True
                        with self._lock:
                            self.is_client_ws = True
                        key = extract_websocket_key(chunk)
                        if key:
                            sock.sendall(create_websocket_handshake_response(key))
                            handshake_done = True
                            logger.info("Local Agent WebSocket client handshake completed.")
                            self.request_status()
                            continue
                        else:
                            logger.warning("WebSocket upgrade missing Sec-WebSocket-Key header.")
                            break
                    else:
                        is_ws = False
                        with self._lock:
                            self.is_client_ws = False
                        handshake_done = True
                        self.request_status()

                if is_ws:
                    raw_buf.extend(chunk)
                    while True:
                        frame = decode_ws_frame(raw_buf)
                        if frame is None:
                            break
                        opcode, payload, consumed = frame
                        del raw_buf[:consumed]
                        if opcode == 1:  # Text frame
                            line = payload.decode("utf-8", errors="replace").strip()
                            if line:
                                self._process_message(line)
                        elif opcode == 8:  # Close frame
                            logger.info("WebSocket close frame received.")
                            return
                        elif opcode == 9:  # Ping frame
                            sock.sendall(encode_ws_frame(payload, opcode=10))  # Pong
                else:
                    text_buf += chunk.decode("utf-8", errors="replace")
                    while "\n" in text_buf:
                        line, text_buf = text_buf.split("\n", 1)
                        line = line.strip()
                        if line:
                            self._process_message(line)
        except Exception as exc:
            logger.debug("Socket read ended: %s", exc)
        finally:
            with self._lock:
                self.is_client_ws = False
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
            status_changed = (
                new_status.chatgpt_logged_in != self.status.chatgpt_logged_in
                or new_status.vbee_logged_in != self.status.vbee_logged_in
                or new_status.browser_connected != self.status.browser_connected
            )
            self.status = new_status
            self.status_updated.emit(self.status)
            if status_changed:
                self.log_emitted.emit(
                    f"Trạng thái kết nối: Edge={'Kết nối' if new_status.browser_connected else 'Mất kết nối'}, "
                    f"ChatGPT={'Đã đăng nhập' if new_status.chatgpt_logged_in else 'Chưa đăng nhập'}, "
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
        elif action == Actions.LOG_EVENT:
            payload = msg.get("payload", {})
            log_msg = payload.get("message") if isinstance(payload, dict) else None
            if not log_msg:
                log_msg = msg.get("message")
            if log_msg:
                self.log_emitted.emit(f"🌐 [Edge] {log_msg}")
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
                "Trình duyệt Microsoft Edge chưa kết nối. "
                "Vui lòng mở Microsoft Edge trước khi dịch."
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
            self.log_emitted.emit("Đã gửi phụ đề sang ChatGPT qua Edge. Đang chờ phản hồi...")
            t_start = time.monotonic()
            completed = False
            while True:
                if event.wait(timeout=3.0):
                    completed = True
                    break
                elapsed = int(time.monotonic() - t_start)
                if elapsed >= timeout_s:
                    break
                self.log_emitted.emit(f"⏳ Đang chờ ChatGPT dịch ngữ cảnh ({elapsed}s)...")

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
        check_cancel: Any | None = None,
        progress_callback: Any | None = None,
    ) -> Path:
        """Execute Vbee dubbing synthesis through the browser extension synchronously.

        Downloads or writes the master audio to target_audio_path.
        """
        import base64
        import binascii
        import uuid

        if not self.status.browser_connected:
            raise RuntimeError(
                "Trình duyệt Microsoft Edge chưa kết nối. "
                "Vui lòng mở Microsoft Edge trước khi tạo voice."
            )

        req_id = str(uuid.uuid4())
        job_digest = hashlib.sha256(
            f"{voice_name}\0{speed}\0{srt_content}".encode()
        ).hexdigest()[:12]
        job_name = f"vkdub_{job_digest}"
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
                    "job_name": job_name,
                },
            )
            if not sent:
                raise RuntimeError("Không thể gửi lệnh tạo voice sang extension Vbee.")

            logger.info("Đã gửi yêu cầu tạo voice Vbee (request_id=%s). Đang xử lý...", req_id)
            self.log_emitted.emit(f"Đã gửi kịch bản sang Vbee (giọng {voice_name} {speed}). Đang xử lý...")
            t_start = time.monotonic()
            completed = False
            while True:
                if check_cancel:
                    check_cancel()
                if event.wait(timeout=1.0):
                    completed = True
                    break
                elapsed = int(time.monotonic() - t_start)
                if elapsed >= timeout_s:
                    break
                self.log_emitted.emit(f"⏳ Vbee đang tổng hợp và tải audio ({elapsed}s)...")
                if progress_callback:
                    pct = min(85, 40 + int((elapsed / 60.0) * 45))
                    progress_callback(pct, f"Vbee đang xử lý phụ đề thành voice ({elapsed}s)…")

            if not completed:
                raise TimeoutError(f"Quá thời gian chờ tạo voice từ Vbee ({timeout_s}s).")

            logger.info(
                "Vbee response: request_id=%s job=%s success=%s base64=%s url=%s "
                "download_triggered=%s download_path=%s",
                req_id,
                job_name,
                container.get("success"),
                bool(container.get("audio_base64")),
                bool(container.get("audio_url")),
                bool(container.get("download_triggered")),
                container.get("download_path") or "-",
            )

            audio_b64 = container.get("audio_base64")
            if audio_b64:
                try:
                    raw_bytes = base64.b64decode(audio_b64, validate=True)
                    saved = _write_verified_audio(target_audio_path, raw_bytes, "extension")
                    logger.info("Đã lưu master audio Vbee thành công vào: %s", saved)
                    return saved
                except (binascii.Error, RuntimeError) as exc:
                    logger.warning("Payload base64 Vbee không dùng được: %s", exc)

            # If audio_b64 not directly returned, check audio_url
            audio_url = container.get("audio_url")
            if audio_url and audio_url.startswith("http"):
                import httpx

                try:
                    with httpx.Client(timeout=45.0, follow_redirects=True) as client:
                        resp = client.get(audio_url)
                        resp.raise_for_status()
                    saved = _write_verified_audio(target_audio_path, resp.content, "audio_url")
                    logger.info("Đã tải master audio Vbee từ URL: %s", saved)
                    return saved
                except (httpx.HTTPError, RuntimeError) as exc:
                    logger.warning("Không tải được audio_url Vbee; thử file Edge: %s", exc)

            if container.get("download_triggered") or container.get("download_path"):
                downloaded = _wait_for_correlated_audio(
                    job_name=str(container.get("job_name") or job_name),
                    explicit_path=container.get("download_path"),
                )
                if downloaded:
                    saved = _write_verified_audio(
                        target_audio_path,
                        downloaded.read_bytes(),
                        str(downloaded),
                    )
                    logger.info("Đã nhận đúng audio Vbee job %s từ %s", job_name, downloaded)
                    return saved

            if not container.get("success", False):
                err = container.get("error", "Lỗi không xác định từ extension Vbee.")
                raise RuntimeError(f"Vbee tạo voice thất bại: {err}")

            raise RuntimeError(
                f"Extension Vbee báo thành công nhưng không trả audio cho job {job_name}. "
                "Không tạo checkpoint để có thể Thử lại an toàn."
            )
        finally:
            self._pending_requests.pop(req_id, None)

    def send_command(self, action: str, payload: dict[str, Any] | None = None) -> bool:
        """Send command to Browser Extension via WebSocket or native host."""
        with self._lock:
            if not self.client_sock:
                logger.warning("Cannot send command %s: no client connected", action)
                return False
            sock = self.client_sock
            is_ws = self.is_client_ws

        msg = {
            "action": action,
            "payload": payload or {},
            "timestamp": time.time(),
        }
        try:
            raw_text = json.dumps(msg)
            if is_ws:
                sock.sendall(encode_ws_frame(raw_text.encode("utf-8")))
            else:
                data = (raw_text + "\n").encode("utf-8")
                sock.sendall(data)
            return True
        except Exception as exc:
            logger.error("Failed to send command %s: %s", action, exc)
            return False

    def request_status(self) -> bool:
        """Request immediate status refresh from browser extension."""
        return self.send_command(Actions.GET_STATUS)

    def reload_extension(self) -> bool:
        """Request browser extension to reload its background service worker."""
        return self.send_command(Actions.RELOAD_EXTENSION)

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
