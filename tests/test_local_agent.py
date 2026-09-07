"""Unit and integration tests for LocalAgent socket server and Qt signals."""

import json
import socket
import time

import pytest
from PySide6.QtWidgets import QApplication

from vkdub.bridge.local_agent import LocalAgent
from vkdub.bridge.protocol import Actions, BridgeStatus

TEST_PORT = 59814


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_local_agent_start_and_stop(qapp):
    agent = LocalAgent(port=TEST_PORT)
    assert agent.start() is True
    assert agent.running is True
    agent.stop()
    assert agent.running is False
    assert agent.status.browser_connected is False


def test_local_agent_client_connection_and_status(qapp):
    agent = LocalAgent(port=TEST_PORT + 1)
    assert agent.start() is True

    connection_events = []
    status_events = []

    agent.browser_connection_changed.connect(lambda connected: connection_events.append(connected))
    agent.status_updated.connect(lambda status: status_events.append(status))

    # Connect mock client socket (representing vkdub_host.py)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", TEST_PORT + 1))

    # Wait for connection handshake
    time.sleep(0.3)
    qapp.processEvents()

    assert True in connection_events
    assert agent.status.browser_connected is True

    # Send STATUS_REPORT from mock client
    report = {
        "action": Actions.STATUS_REPORT,
        "payload": {
            "browser_connected": True,
            "chatgpt_available": True,
            "chatgpt_logged_in": True,
            "vbee_available": True,
            "vbee_logged_in": True,
            "browser_name": "Microsoft Edge",
        },
    }
    client.sendall((json.dumps(report) + "\n").encode("utf-8"))

    # Process events to allow agent thread to emit signal
    time.sleep(0.3)
    qapp.processEvents()

    assert len(status_events) > 0
    latest_status: BridgeStatus = status_events[-1]
    assert latest_status.browser_connected is True
    assert latest_status.chatgpt_logged_in is True
    assert latest_status.vbee_logged_in is True

    # Disconnect client
    client.close()
    time.sleep(0.3)
    qapp.processEvents()

    assert False in connection_events
    assert agent.status.browser_connected is False

    agent.stop()


def test_local_agent_translate_and_vbee_sync(qapp, tmp_path):
    import base64
    import threading

    agent = LocalAgent(port=TEST_PORT + 2)
    assert agent.start() is True

    # Connect mock client socket
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", TEST_PORT + 2))
    time.sleep(0.2)
    agent.status.browser_connected = True

    # Mock server responder thread simulating extension replies
    def mock_extension_responder():
        buf = ""
        while True:
            try:
                data = client.recv(4096)
                if not data:
                    break
                buf += data.decode("utf-8")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    action = msg.get("action")
                    payload = msg.get("payload", {})
                    req_id = payload.get("request_id")

                    if action == Actions.CHATGPT_TRANSLATE:
                        reply = {
                            "action": Actions.CHATGPT_TRANSLATE_RESULT,
                            "payload": {
                                "success": True,
                                "translated_srt": "1\n00:00:01,000 --> 00:00:02,000\nXin chào\n",
                                "request_id": req_id,
                            },
                        }
                        client.sendall((json.dumps(reply) + "\n").encode("utf-8"))
                    elif action == Actions.VBEE_GENERATE_VOICE:
                        fake_audio = b"ID3\x03\x00\x00\x00FAKE_AUDIO_DATA"
                        reply = {
                            "action": Actions.VBEE_VOICE_RESULT,
                            "payload": {
                                "success": True,
                                "audio_base64": base64.b64encode(fake_audio).decode("ascii"),
                                "request_id": req_id,
                            },
                        }
                        client.sendall((json.dumps(reply) + "\n").encode("utf-8"))
            except Exception:
                break

    t = threading.Thread(target=mock_extension_responder, daemon=True)
    t.start()

    # 1. Test translation sync
    res_srt = agent.translate_srt_sync("1\n00:00:01,000 --> 00:00:02,000\nHello\n", timeout_s=5.0)
    assert "Xin chào" in res_srt

    # 2. Test Vbee audio generation sync
    target_audio = tmp_path / "vbee_master.mp3"
    saved_path = agent.generate_vbee_sync(res_srt, target_audio, timeout_s=5.0)
    assert saved_path.is_file()
    assert saved_path.read_bytes().startswith(b"ID3")

    client.close()
    agent.stop()
