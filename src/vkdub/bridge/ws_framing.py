"""WebSocket RFC 6455 lightweight framing and handshake utilities.

Allows LocalAgent to accept direct WebSocket connections from browser extensions
without requiring any third-party dependencies (pure standard library).
"""

from __future__ import annotations

import base64
import hashlib
import struct


def is_websocket_request(data: bytes) -> bool:
    """Return True if initial incoming bytes look like a WebSocket upgrade request."""
    if not data or not data.startswith(b"GET "):
        return False
    lower = data.lower()
    return b"upgrade: websocket" in lower or (b"upgrade" in lower and b"websocket" in lower)


def extract_websocket_key(data: bytes) -> str | None:
    """Extract Sec-WebSocket-Key from HTTP header bytes."""
    for line in data.split(b"\r\n"):
        if line.lower().startswith(b"sec-websocket-key:"):
            parts = line.split(b":", 1)
            if len(parts) == 2:
                return parts[1].strip().decode("utf-8", errors="replace")
    return None


def make_websocket_accept(key: str) -> str:
    """Compute RFC 6455 Sec-WebSocket-Accept value from client key."""
    guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    sha1 = hashlib.sha1((key.strip() + guid).encode("utf-8")).digest()
    return base64.b64encode(sha1).decode("utf-8")


def create_websocket_handshake_response(key: str) -> bytes:
    """Generate the HTTP 101 Switching Protocols response for WebSocket upgrade."""
    accept_val = make_websocket_accept(key)
    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept_val}\r\n"
        "\r\n"
    )
    return response.encode("utf-8")


def encode_ws_frame(data: bytes, opcode: int = 1) -> bytes:
    """Encode binary or text payload into an unmasked server-to-client WebSocket frame (RFC 6455)."""
    length = len(data)
    header = bytearray([0x80 | (opcode & 0x0F)])
    if length <= 125:
        header.append(length)
    elif length <= 65535:
        header.append(126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", length))
    return bytes(header) + data


def decode_ws_frame(buffer: bytearray) -> tuple[int, bytes, int] | None:
    """Decode a single WebSocket frame from buffer.

    Returns:
        (opcode, payload_bytes, total_bytes_consumed) or None if incomplete.
    """
    if len(buffer) < 2:
        return None
    b1 = buffer[0]
    b2 = buffer[1]
    opcode = b1 & 0x0F
    is_masked = bool(b2 & 0x80)
    payload_len = b2 & 0x7F

    offset = 2
    if payload_len == 126:
        if len(buffer) < offset + 2:
            return None
        payload_len = struct.unpack("!H", buffer[offset : offset + 2])[0]
        offset += 2
    elif payload_len == 127:
        if len(buffer) < offset + 8:
            return None
        payload_len = struct.unpack("!Q", buffer[offset : offset + 8])[0]
        offset += 8

    mask_key = b""
    if is_masked:
        if len(buffer) < offset + 4:
            return None
        mask_key = buffer[offset : offset + 4]
        offset += 4

    if len(buffer) < offset + payload_len:
        return None

    raw_data = buffer[offset : offset + payload_len]
    if is_masked:
        unmasked = bytearray(payload_len)
        for i in range(payload_len):
            unmasked[i] = raw_data[i] ^ mask_key[i % 4]
        payload = bytes(unmasked)
    else:
        payload = bytes(raw_data)

    return (opcode, payload, offset + payload_len)
