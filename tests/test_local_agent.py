"""Unit and integration tests for LocalAgent socket server and Qt signals."""

import json
import socket
import time
import pytest
from PySide6.QtCore import QCoreApplication

from vkdub.bridge.local_agent import LocalAgent
from vkdub.bridge.protocol import Actions, BridgeStatus

TEST_PORT = 59814


@pytest.fixture(scope="session")
def qapp():
    app = QCoreApplication.instance()
    if not app:
        app = QCoreApplication([])
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
