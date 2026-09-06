import asyncio
import json

import httpx
import pytest

from vkdub.domain.voice import DEFAULT_LABEL, DEFAULT_VOICE
from vkdub.providers.tts import TTSError
from vkdub.providers.vbee_tts import TTS_URL, VOICES_URL, VbeeTTSProvider
from vkdub.services.credential_service import redact
from vkdub.services.tts_usage import TTSUsage


def provider(tmp_path, handler):
    return VbeeTTSProvider(
        "test-app",
        "secret-test-token",
        TTSUsage(tmp_path / "usage.db"),
        httpx.MockTransport(handler),
    )


def voices_page(next_cursor=None, code=DEFAULT_VOICE, name=DEFAULT_LABEL):
    return {
        "status": 1,
        "result": {
            "voices": [{"code": code, "name": name, "language_code": "vi-VN"}],
            "pagination": {"has_next_page": next_cursor is not None, "next_cursor": next_cursor},
        },
    }


def test_official_sync_contract_and_usage(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        assert str(request.url) == TTS_URL
        assert request.headers["App-Id"] == "test-app"
        assert request.headers["Authorization"] == "Bearer secret-test-token"
        assert json.loads(request.content) == {
            "text": "Xin chào",
            "voiceCode": DEFAULT_VOICE,
            "speed": 1.1,
            "mode": "sync",
            "outputFormat": "mp3",
            "bitrate": 128,
        }
        return httpx.Response(
            200, headers={"content-type": "audio/mpeg"}, content=b"test audio bytes"
        )

    api = provider(tmp_path, handler)
    target = tmp_path / "audio.mp3"
    assert asyncio.run(api.synthesize("Xin chào", DEFAULT_VOICE, 1.1, target)) == target
    assert target.read_bytes() == b"test audio bytes"
    assert len(requests) == 1
    assert api.usage.monthly() == (1, 8, 0)
    assert "secret-test-token" not in redact("test-app secret-test-token")


@pytest.mark.parametrize("status", [301, 400, 401, 403, 429, 500, 503])
def test_errors_never_retry_post_or_expose_body(tmp_path, status):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            status,
            json={"error": {"message": "secret-test-token"}},
            headers={"Location": "https://example.com/private"},
        )

    api = provider(tmp_path, handler)
    with pytest.raises(TTSError) as failure:
        asyncio.run(api.synthesize("Xin chào", DEFAULT_VOICE, 1, tmp_path / "a.mp3"))
    assert "secret-test-token" not in str(failure.value)
    assert len(requests) == 1
    assert api.usage.monthly() == (1, 8, 1)


@pytest.mark.parametrize("text", ["", " ", "x" * 301])
def test_invalid_text_never_sends(tmp_path, text):
    def unexpected(_):
        pytest.fail("Invalid text sent to provider")

    api = provider(tmp_path, unexpected)
    with pytest.raises(TTSError):
        asyncio.run(api.synthesize(text, DEFAULT_VOICE, 1, tmp_path / "a.mp3"))
    assert api.usage.monthly() == (0, 0, 0)


@pytest.mark.parametrize("kind", ["timeout", "json", "empty", "too_large"])
def test_bad_download_is_not_success(tmp_path, monkeypatch, kind):
    monkeypatch.setattr("vkdub.providers.vbee_tts.MAX_AUDIO_BYTES", 10)

    def handler(request):
        if kind == "timeout":
            raise httpx.ReadTimeout("token secret-test-token", request=request)
        if kind == "json":
            return httpx.Response(200, json={"error": "no credits"})
        return httpx.Response(
            200,
            headers={"content-type": "audio/mpeg"},
            content=b"" if kind == "empty" else b"x" * 11,
        )

    api = provider(tmp_path, handler)
    with pytest.raises(TTSError) as failure:
        asyncio.run(api.synthesize("Xin chào", DEFAULT_VOICE, 1, tmp_path / "a.mp3"))
    assert "secret-test-token" not in str(failure.value)
    assert api.usage.monthly()[2] == 1


def test_voices_paginate_and_filter_supported_sync_names(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url).startswith(VOICES_URL)
        if len(calls) == 1:
            return httpx.Response(200, json=voices_page("page2"))
        assert request.url.params["cursor"] == "page2"
        return httpx.Response(200, json=voices_page(code="unsupported", name="Some other voice"))

    api = provider(tmp_path, handler)
    voices = asyncio.run(api.list_voices())
    assert len(voices) == 1 and voices[0].code == DEFAULT_VOICE
    assert api.usage.monthly() == (0, 0, 0)


@pytest.mark.parametrize("data", [{}, [], {"status": 0}, voices_page("repeated")])
def test_invalid_voice_response_fails(tmp_path, data):
    api = provider(tmp_path, lambda request: httpx.Response(200, json=data))
    with pytest.raises(TTSError):
        asyncio.run(api.list_voices())


def test_usage_reset_is_local_and_separate(tmp_path):
    usage = TTSUsage(tmp_path / "usage.db")
    first = usage.begin(15)
    usage.begin(20)
    usage.finish(first)
    assert usage.monthly() == (2, 35, 1)
    usage.reset()
    assert usage.monthly() == (0, 0, 0)
