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
      logger.error("Failed to start Local Agent server on %s:%d: %s", self.host, self.port, exc)
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
      except socket.timeout:
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
    elif action == Actions.HELLO:
      self.log_emitted.emit("Trình duyệt Microsoft Edge đã kết nối thành công.")
      self.request_status()

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
