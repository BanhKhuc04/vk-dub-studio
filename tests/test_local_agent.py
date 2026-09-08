"""Unit and integration tests for LocalAgent socket server and Qt signals."""

import json
import socket
import time

import pytest
from PySide6.QtWidgets import QApplication

from vkdub.bridge.local_agent import LocalAgent, _looks_like_audio, _wait_for_correlated_audio
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
                        fake_audio = b"ID3\x03\x00\x00\x00" + (b"FAKE_AUDIO_DATA" * 100)
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


def test_audio_payload_validation_rejects_empty_or_html():
    assert not _looks_like_audio(b"")
    assert not _looks_like_audio(b"<html>not audio</html>" * 100)
    assert _looks_like_audio(b"ID3\x04\x00\x00" + (b"\0" * 2048))


def test_wait_for_correlated_audio_accepts_only_matching_stable_download(
    monkeypatch, tmp_path
):
    import vkdub.bridge.local_agent as local_agent_module

    unrelated = tmp_path / "other_job.mp3"
    unrelated.write_bytes(b"ID3" + (b"x" * 2048))
    # Vbee sanitizes the uploaded job title and removes underscores.
    expected = tmp_path / "vkdubabc123_result.mp3.crdownload"
    expected.write_bytes(b"ID3" + (b"y" * 2048))
    monkeypatch.setattr(local_agent_module, "_edge_download_directories", lambda: [tmp_path])

    found = _wait_for_correlated_audio("vkdub_abc123", timeout_s=2.0)

    assert found == expected


def test_generate_vbee_sync_recovers_correlated_edge_partial_download(
    qapp, monkeypatch, tmp_path
):
    import vkdub.bridge.local_agent as local_agent_module

    agent = LocalAgent()
    agent.status.browser_connected = True
    monkeypatch.setattr(local_agent_module, "_edge_download_directories", lambda: [tmp_path])

    def fake_send(action, payload=None):
        assert action == Actions.VBEE_GENERATE_VOICE
        assert payload is not None
        job_name = payload["job_name"]
        downloaded = tmp_path / f"{job_name}_result.mp3.crdownload"
        downloaded.write_bytes(b"ID3" + (b"voice" * 500))
        agent._process_message(
            json.dumps(
                {
                    "action": Actions.VBEE_VOICE_RESULT,
                    "payload": {
                        "success": True,
                        "download_triggered": True,
                        "download_path": str(downloaded)[: -len(".crdownload")],
                        "job_name": job_name,
                        "request_id": payload["request_id"],
                    },
                }
            )
        )
        return True

    monkeypatch.setattr(agent, "send_command", fake_send)
    target = tmp_path / "master.mp3"

    saved = agent.generate_vbee_sync("1\n00:00:00,000 --> 00:00:01,000\nXin chào", target)

    assert saved == target
    assert saved.read_bytes().startswith(b"ID3")


def test_generate_vbee_sync_rejects_success_without_audio(qapp, monkeypatch, tmp_path):
    agent = LocalAgent()
    agent.status.browser_connected = True

    def fake_send(action, payload=None):
        assert payload is not None
        agent._process_message(
            json.dumps(
                {
                    "action": Actions.VBEE_VOICE_RESULT,
                    "payload": {
                        "success": True,
                        "request_id": payload["request_id"],
                    },
                }
            )
        )
        return True

    monkeypatch.setattr(agent, "send_command", fake_send)

    with pytest.raises(RuntimeError, match="không trả audio"):
        agent.generate_vbee_sync("valid srt", tmp_path / "must-not-exist.mp3")
