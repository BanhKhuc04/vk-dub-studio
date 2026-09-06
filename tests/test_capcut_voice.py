import json
import sys
from types import SimpleNamespace

import httpx
import pytest

from vkdub.providers.capcut_worker import CapCutWorkerError, speech_url, synthesize


@pytest.mark.parametrize("status", ["succeed", "success"])
def test_actual_wire_status_string_ret_and_download(status, tmp_path, monkeypatch):
    calls = []

    class SDK:
        def __init__(self, **kwargs):
            pass

        def build_tts_new_request(self, text, voice, resource, rate):
            assert (text, voice, resource, rate) == ("Xin chào", "upstream", "resource", "1.0")
            return "https://api.test/new", {}, "{}"

        def build_query_request(self, identifier, token):
            assert (identifier, token) == ("task", "private-token")
            return "https://api.test/query", {}, "{}"

    def respond(request):
        calls.append(request.url.path)
        if request.url.path == "/new":
            return httpx.Response(
                200,
                json={"ret": "0", "data": {"tasks": [{"id": "task", "token": "private-token"}]}},
            )
        if request.url.path == "/query":
            return httpx.Response(
                200,
                json={
                    "ret": "0",
                    "data": {
                        "tasks": [
                            {
                                "status": status,
                                "payload": json.dumps(
                                    {
                                        "audio_subtitles": [
                                            {"code": "0", "speech_url": "https://cdn.test/audio"}
                                        ]
                                    }
                                ),
                            }
                        ]
                    },
                },
            )
        return httpx.Response(200, content=b"audio" * 100)

    original = httpx.Client
    monkeypatch.setitem(sys.modules, "capcut_tts_api", SimpleNamespace(CapCutClient=SDK))
    monkeypatch.setattr(
        "vkdub.providers.capcut_worker.httpx.Client",
        lambda **kw: original(transport=httpx.MockTransport(respond), **kw),
    )
    target = tmp_path / "audio.mp3"
    synthesize(
        {
            "text": "Xin chào",
            "voice": {"upstream_id": "upstream", "resource_id": "resource"},
            "output": str(target),
        }
    )
    assert target.read_bytes() == b"audio" * 100
    assert calls == ["/new", "/query", "/audio"]


@pytest.mark.parametrize(
    "row",
    [
        {"code": 1, "speech_url": "https://cdn.test/audio"},
        {"code": 0, "speech_url": "file:///secret"},
        {"invalid_input": True},
    ],
)
def test_reject_failed_or_invalid_audio(row):
    with pytest.raises(CapCutWorkerError):
        speech_url({"payload": {"audio_subtitles": [row]}})
