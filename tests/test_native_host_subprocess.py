"""End-to-End subprocess test of vkdub_host.py simulating Chromium Edge Native Messaging."""

import json
import struct
import subprocess
import sys
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from vkdub.bridge.local_agent import LocalAgent
from vkdub.bridge.protocol import Actions, BridgeStatus

HOST_SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "native_host" / "vkdub_host.py"
PYTHON_EXE = sys.executable


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_vkdub_host_stdio_relay(qapp):
    # 1. Start LocalAgent on standard port 49814
    agent = LocalAgent(port=49814)
    assert agent.start() is True

    connection_events = []
    status_events = []
    agent.browser_connection_changed.connect(lambda connected: connection_events.append(connected))
    agent.status_updated.connect(lambda status: status_events.append(status))

    # 2. Launch vkdub_host.py as a subprocess with piped stdin/stdout
    proc = subprocess.Popen(
        [PYTHON_EXE, "-u", str(HOST_SCRIPT)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Wait for vkdub_host.py to connect to LocalAgent (up to 4s)
        for _ in range(40):
            qapp.processEvents()
            if agent.status.browser_connected:
                break
            time.sleep(0.1)

        assert agent.status.browser_connected is True
        assert True in connection_events

        # 3. Send STATUS_REPORT from simulated extension to host stdin
        report_msg = {
            "action": Actions.STATUS_REPORT,
            "payload": {
                "browser_connected": True,
                "chatgpt_available": True,
                "chatgpt_logged_in": True,
                "vbee_available": True,
                "vbee_logged_in": True,
                "browser_name": "Microsoft Edge",
                "active_tabs": {"chatgpt": 1, "vbee": 1},
            },
        }
        encoded = json.dumps(report_msg).encode("utf-8")
        header = struct.pack("<I", len(encoded))
        proc.stdin.write(header + encoded)
        proc.stdin.flush()

        time.sleep(0.5)
        qapp.processEvents()

        # Check that LocalAgent received and processed the status report
        assert len(status_events) > 0
        latest: BridgeStatus = status_events[-1]
        assert latest.chatgpt_logged_in is True
        assert latest.vbee_logged_in is True
        assert latest.chatgpt_tabs == 1
        assert latest.vbee_tabs == 1

        # 4. Test sending command from LocalAgent -> host -> stdout
        agent.request_status()
        time.sleep(0.5)

        # Read 4-byte length from proc.stdout
        raw_len = proc.stdout.read(4)
        assert len(raw_len) == 4
        msg_len = struct.unpack("<I", raw_len)[0]
        raw_data = proc.stdout.read(msg_len)
        resp = json.loads(raw_data.decode("utf-8"))

        assert resp.get("action") == Actions.GET_STATUS

    finally:
        # Close stdin to signal host to exit
        proc.stdin.close()
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except Exception:
            proc.kill()
        agent.stop()
