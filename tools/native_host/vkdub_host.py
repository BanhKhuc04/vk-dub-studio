"""VK Dub Studio — Native Messaging Host Bridge.

Relays messages between Chromium Native Messaging (stdio 32-bit framed JSON)
and VK Dub Local Agent (loopback TCP socket on 127.0.0.1:49814).
"""

from __future__ import annotations

import json
import logging
import os
import queue
import socket
import struct
import sys
import threading
import time
from pathlib import Path

# Configure binary mode for standard streams on Windows
if sys.platform == "win32":
    import msvcrt

    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

# Logging configuration (must log to file; stdout is reserved for binary protocol)
LOG_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "VKDubStudio" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "native_host.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (Host) %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger("vkdub.native_host")

DEFAULT_AGENT_PORT = 49814
DEFAULT_AGENT_HOST = "127.0.0.1"


def read_native_message() -> dict | None:
    """Read a 32-bit length-prefixed JSON message from stdin."""
    try:
        raw_length = sys.stdin.buffer.read(4)
        if not raw_length or len(raw_length) < 4:
            return None
        length = struct.unpack("<I", raw_length)[0]
        if length == 0:
            return None
        data = sys.stdin.buffer.read(length)
        if len(data) < length:
            logger.warning("Short read: expected %d bytes, got %d", length, len(data))
            return None
        return json.loads(data.decode("utf-8"))
    except Exception as exc:
        logger.error("Error reading native message: %s", exc)
        return None


def write_native_message(message: dict) -> bool:
    """Write a 32-bit length-prefixed JSON message to stdout."""
    try:
        encoded = json.dumps(message, separators=(",", ":")).encode("utf-8")
        header = struct.pack("<I", len(encoded))
        sys.stdout.buffer.write(header)
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()
        return True
    except Exception as exc:
        logger.error("Error writing native message: %s", exc)
        return False


class AgentBridge:
    """Manages connection to the VK Dub Local Agent TCP socket."""

    def __init__(self, host: str = DEFAULT_AGENT_HOST, port: int = DEFAULT_AGENT_PORT) -> None:
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self.connected = False
        self.running = True
        self.send_queue: queue.Queue[dict] = queue.Queue(maxsize=100)

    def connect_loop(self) -> None:
        """Continuously attempt connection to Local Agent TCP server."""
        while self.running:
            if not self.connected:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(5.0)
                    s.connect((self.host, self.port))
                    s.settimeout(None)
                    self.sock = s
                    self.connected = True
                    logger.info("Connected to Local Agent at %s:%d", self.host, self.port)
                    # Start receiver thread for this connection
                    threading.Thread(target=self._recv_from_agent, daemon=True).start()
                except Exception as exc:
                    logger.debug("Local Agent not reachable (%s), retrying in 2s...", exc)
                    time.sleep(2.0)
            else:
                time.sleep(1.0)

    def send_to_agent(self, msg: dict) -> None:
        """Enqueue message to be sent to Local Agent."""
        try:
            self.send_queue.put_nowait(msg)
        except queue.Full:
            logger.warning("Send queue full, dropping message: %s", msg.get("action"))

    def send_loop(self) -> None:
        """Flush queued messages to Local Agent socket."""
        while self.running:
            try:
                msg = self.send_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            sent = False
            for _ in range(3):
                if self.connected and self.sock:
                    try:
                        data = (json.dumps(msg) + "\n").encode("utf-8")
                        self.sock.sendall(data)
                        sent = True
                        break
                    except Exception as exc:
                        logger.warning("Socket send error: %s. Reconnecting...", exc)
                        self._disconnect_socket()
                        time.sleep(0.5)
                else:
                    time.sleep(0.5)

            if not sent:
                logger.error("Failed to deliver message to Local Agent: %s", msg.get("action"))

    def _recv_from_agent(self) -> None:
        """Read newline-delimited JSON messages from Local Agent and forward to extension."""
        assert self.sock is not None
        sock = self.sock
        buf = ""
        try:
            while self.running and self.connected:
                chunk = sock.recv(4096)
                if not chunk:
                    logger.info("Local Agent closed connection.")
                    break
                buf += chunk.decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        try:
                            parsed = json.loads(line)
                            write_native_message(parsed)
                        except Exception as parse_err:
                            logger.error("Error parsing message from Local Agent: %s", parse_err)
        except Exception as exc:
            logger.warning("Error receiving from Local Agent: %s", exc)
        finally:
            self._disconnect_socket()

    def _disconnect_socket(self) -> None:
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def stop(self) -> None:
        self.running = False
        self._disconnect_socket()


def main() -> None:
    logger.info("VK Dub Native Messaging Host started. PID=%d", os.getpid())
    bridge = AgentBridge()

    # Start background threads for Local Agent communication
    t_connect = threading.Thread(target=bridge.connect_loop, daemon=True)
    t_send = threading.Thread(target=bridge.send_loop, daemon=True)
    t_connect.start()
    t_send.start()

    try:
        while True:
            msg = read_native_message()
            if msg is None:
                logger.info("Standard input closed or EOF. Exiting host.")
                break

            logger.debug("Received from extension: %s", msg.get("action"))
            bridge.send_to_agent(msg)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received.")
    except Exception as exc:
        logger.error("Unexpected error in main loop: %s", exc)
    finally:
        bridge.stop()
        logger.info("Native Messaging Host stopped.")


if __name__ == "__main__":
    main()
