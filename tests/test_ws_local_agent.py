"""Unit test for LocalAgent direct WebSocket client support."""

import base64
import json
import socket
import time
from PySide6.QtCore import QCoreApplication

from vkdub.bridge.local_agent import LocalAgent
from vkdub.bridge.protocol import Actions
from vkdub.bridge.ws_framing import (
    decode_ws_frame,
    encode_ws_frame,
    make_websocket_accept,
)


def test_local_agent_websocket_handshake_and_flow():
    app = QCoreApplication.instance() or QCoreApplication([])

    test_port = 49825
    agent = LocalAgent(port=test_port)
    assert agent.start() is True

    time.sleep(0.1)

    # 1. Connect via client socket and perform WebSocket handshake
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", test_port))

    dummy_key = "dGhlIHNhbXBsZSBub25jZQ=="
    handshake_request = (
        f"GET /ws HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{test_port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {dummy_key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
    )
    client.sendall(handshake_request.encode("utf-8"))

    # Read handshake response
    resp = client.recv(4096).decode("utf-8")
    assert "101 Switching Protocols" in resp
    expected_accept = make_websocket_accept(dummy_key)
    assert expected_accept in resp

    time.sleep(0.1)
    assert agent.status.browser_connected is True

    # 2. Client sends HELLO in WebSocket frame
    hello_msg = json.dumps({"action": Actions.HELLO, "version": "1.0.0"}).encode("utf-8")
    client.sendall(encode_ws_frame(hello_msg, opcode=1))

    # Read server command (request_status / GET_STATUS)
    incoming = bytearray(client.recv(4096))
    frame = decode_ws_frame(incoming)
    assert frame is not None
    opcode, payload, _ = frame
    assert opcode == 1
    received_cmd = json.loads(payload.decode("utf-8"))
    assert received_cmd.get("action") == Actions.GET_STATUS

    # 3. Client responds with STATUS_REPORT
    status_report = json.dumps({
        "action": Actions.STATUS_REPORT,
        "payload": {
            "browser_connected": True,
            "chatgpt_available": True,
            "chatgpt_logged_in": True,
            "vbee_available": True,
            "vbee_logged_in": True,
            "browser_name": "Microsoft Edge",
        }
    }).encode("utf-8")
    client.sendall(encode_ws_frame(status_report, opcode=1))

    time.sleep(0.1)
    assert agent.status.chatgpt_logged_in is True
    assert agent.status.vbee_logged_in is True

    # 4. Disconnect client
    client.close()
    time.sleep(0.1)
    assert agent.status.browser_connected is False

    agent.stop()
