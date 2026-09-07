"""Unit tests for Native Messaging binary framing."""

import io
import json
import struct


def pack_native_message(message: dict) -> bytes:
    encoded = json.dumps(message, separators=(",", ":")).encode("utf-8")
    header = struct.pack("<I", len(encoded))
    return header + encoded


def unpack_native_message(stream: io.BytesIO) -> dict | None:
    raw_length = stream.read(4)
    if len(raw_length) < 4:
        return None
    length = struct.unpack("<I", raw_length)[0]
    data = stream.read(length)
    if len(data) < length:
        return None
    return json.loads(data.decode("utf-8"))


def test_native_messaging_roundtrip_simple():
    msg = {"action": "PING", "timestamp": 1741334000}
    packed = pack_native_message(msg)

    assert len(packed) == 4 + len(json.dumps(msg, separators=(",", ":")).encode("utf-8"))
    stream = io.BytesIO(packed)
    unpacked = unpack_native_message(stream)
    assert unpacked == msg


def test_native_messaging_unicode_vietnamese():
    msg = {
        "action": "STATUS_REPORT",
        "payload": {
            "browser_connected": True,
            "browser_name": "Microsoft Edge",
            "status_text": "Đã đăng nhập thành công vào ChatGPT và Vbee!",
            "character_sample": "Tiếng Việt có dấu: ắ, ằ, ẳ, ẵ, ặ, ê, ô, ơ, ư",
        },
    }
    packed = pack_native_message(msg)
    stream = io.BytesIO(packed)
    unpacked = unpack_native_message(stream)
    assert unpacked == msg
    assert unpacked["payload"]["status_text"] == "Đã đăng nhập thành công vào ChatGPT và Vbee!"


def test_native_messaging_large_payload():
    large_text = "Dòng phụ đề tiếng Việt " * 5000
    msg = {"action": "CHATGPT_TRANSLATE_RESULT", "payload": {"srt": large_text}}
    packed = pack_native_message(msg)
    assert len(packed) > 100_000

    stream = io.BytesIO(packed)
    unpacked = unpack_native_message(stream)
    assert unpacked == msg


def test_native_messaging_incomplete_stream():
    packed = pack_native_message({"action": "TEST"})
    # Truncate to make stream incomplete
    stream = io.BytesIO(packed[:6])
    assert unpack_native_message(stream) is None
