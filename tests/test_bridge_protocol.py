"""Unit tests for Browser Bridge protocol and BridgeStatus model."""

from vkdub.bridge.protocol import Actions, BridgeStatus, PROTOCOL_VERSION


def test_bridge_status_defaults():
    status = BridgeStatus()
    assert not status.browser_connected
    assert not status.chatgpt_available
    assert not status.chatgpt_logged_in
    assert not status.vbee_available
    assert not status.vbee_logged_in
    assert status.browser_name == "Chưa kết nối"
    assert status.chatgpt_tabs == 0
    assert status.vbee_tabs == 0


def test_bridge_status_from_payload():
    payload = {
        "browser_connected": True,
        "chatgpt_available": True,
        "chatgpt_logged_in": True,
        "vbee_available": False,
        "vbee_logged_in": True,
        "browser_name": "Microsoft Edge",
        "active_tabs": {
            "chatgpt": 2,
            "vbee": 0,
        },
        "timestamp": 1741334500.0,
        "details": {"test": 123},
    }
    status = BridgeStatus.from_payload(payload)

    assert status.browser_connected is True
    assert status.chatgpt_available is True
    assert status.chatgpt_logged_in is True
    assert status.vbee_available is False
    assert status.vbee_logged_in is True
    assert status.browser_name == "Microsoft Edge"
    assert status.chatgpt_tabs == 2
    assert status.vbee_tabs == 0
    assert status.details == {"test": 123}


def test_bridge_status_to_dict():
    status = BridgeStatus(
        browser_connected=True,
        chatgpt_available=True,
        chatgpt_logged_in=False,
        vbee_available=True,
        vbee_logged_in=True,
        browser_name="Google Chrome",
    )
    d = status.to_dict()
    assert d["browser_connected"] is True
    assert d["chatgpt_available"] is True
    assert d["chatgpt_logged_in"] is False
    assert d["vbee_logged_in"] is True
    assert d["browser_name"] == "Google Chrome"


def test_actions_constants():
    assert Actions.GET_STATUS == "GET_STATUS"
    assert Actions.STATUS_REPORT == "STATUS_REPORT"
    assert Actions.PING == "PING"
    assert Actions.PONG == "PONG"
    assert PROTOCOL_VERSION == "1.0.0"
