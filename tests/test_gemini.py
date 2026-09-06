import asyncio
import json

import httpx
import pytest

from vkdub.domain.translation import GEMINI_MODEL
from vkdub.providers.gemini_translation import GeminiTranslationProvider, ProviderError, retry_delay
from vkdub.services.cost_service import estimate_usd, load_pricing
from vkdub.services.usage_service import UsageLedger, UsageRecorder

SAMPLE_KEY = "unit-test-key-not-a-credential"
REQUEST = {
    "segments": [{"id": 1, "start": 0, "end": 2, "text": "Hello"}],
    "source_language": "en",
    "target_language": "vi",
}


def response_document(text=None, reason="STOP"):
    return {
        "candidates": [
            {
                "finishReason": reason,
                "content": {
                    "parts": [{"text": text or '{"segments":[{"id":1,"translation":"Xin chào"}]}'}]
                },
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 100,
            "candidatesTokenCount": 20,
            "thoughtsTokenCount": 3,
        },
    }


def provider(tmp_path, handler):
    ledger = UsageLedger(tmp_path / "usage.db")
    return GeminiTranslationProvider(
        SAMPLE_KEY, UsageRecorder(ledger), lambda *a: None, httpx.MockTransport(handler)
    ), ledger


def test_actual_rest_contract_headers_schema_and_usage(tmp_path):
    def handler(request):
        assert request.url.host == "generativelanguage.googleapis.com"
        assert request.url.path.endswith(f"{GEMINI_MODEL}:generateContent")
        assert not request.url.query
        assert request.headers["x-goog-api-key"] == SAMPLE_KEY
        assert request.method == "POST"
        payload = json.loads(request.content)
        assert json.loads(payload["contents"][0]["parts"][0]["text"]) == REQUEST
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        assert payload["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "minimal"}
        assert "responseSchema" in payload["generationConfig"]
        assert SAMPLE_KEY not in request.content.decode()
        return httpx.Response(200, json=response_document())

    adapter, ledger = provider(tmp_path, handler)
    assert asyncio.run(adapter.translate(REQUEST))["segments"][0]["translation"] == "Xin chào"
    usage = ledger.monthly()
    assert usage["requests"] == 1 and usage["unknown"] == 0
    assert usage["input_tokens"] == 100 and usage["output_tokens"] == 23
    assert usage["usd"] == estimate_usd(100, 23, load_pricing())
    assert SAMPLE_KEY.encode() not in ledger.path.read_bytes()


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 503])
def test_http_errors_never_echo_key_or_provider_body(tmp_path, monkeypatch, status):
    count = 0

    async def no_sleep(seconds):
        pass

    monkeypatch.setattr("vkdub.providers.gemini_translation.asyncio.sleep", no_sleep)

    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(status, json={"error": {"message": SAMPLE_KEY}})

    adapter, ledger = provider(tmp_path, handler)
    with pytest.raises(ProviderError) as error:
        asyncio.run(adapter.translate(REQUEST))
    assert str(status) in str(error.value)
    assert SAMPLE_KEY not in str(error.value)
    assert count == (3 if status in (429, 503) else 1)
    assert ledger.monthly()["requests"] == count


def test_429_retry_after_honored_and_bounded(tmp_path, monkeypatch):
    delays = []

    async def no_sleep(seconds):
        delays.append(seconds)

    monkeypatch.setattr("vkdub.providers.gemini_translation.asyncio.sleep", no_sleep)
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        return (
            httpx.Response(429, headers={"Retry-After": "7"}, json={})
            if count == 1
            else httpx.Response(200, json=response_document())
        )

    adapter, _ = provider(tmp_path, handler)
    asyncio.run(adapter.translate(REQUEST))
    assert delays == [7]
    assert retry_delay(None, 1) == 2
    with pytest.raises(ProviderError):
        retry_delay("120", 0)


def test_network_timeout_is_not_retried_and_usage_remains_unknown(tmp_path):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        raise httpx.ReadTimeout(SAMPLE_KEY, request=request)

    adapter, ledger = provider(tmp_path, handler)
    with pytest.raises(ProviderError) as error:
        asyncio.run(adapter.translate(REQUEST))
    assert SAMPLE_KEY not in str(error.value)
    assert count == 1
    assert ledger.monthly()["unknown"] == 1


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"promptFeedback": {"blockReason": "SAFETY"}},
        response_document(reason="MAX_TOKENS"),
        response_document(text="not JSON"),
        response_document(text="[]"),
    ],
)
def test_blocked_truncated_invalid_responses_not_applied_but_usage_recorded(tmp_path, data):
    adapter, ledger = provider(tmp_path, lambda _: httpx.Response(200, json=data))
    with pytest.raises(ProviderError):
        asyncio.run(adapter.translate(REQUEST))
    assert ledger.monthly()["requests"] == 1
    if "usageMetadata" in data:
        assert ledger.monthly()["input_tokens"] == 100


def test_connection_reads_model_without_generation_or_transcript(tmp_path):
    def handler(request):
        assert request.method == "GET"
        assert not request.content
        assert request.url.path.endswith(GEMINI_MODEL)
        return httpx.Response(
            200,
            json={
                "name": f"models/{GEMINI_MODEL}",
                "supportedGenerationMethods": ["generateContent"],
            },
        )

    adapter, ledger = provider(tmp_path, handler)
    assert "Quota" in asyncio.run(adapter.test_connection())
    assert ledger.monthly()["requests"] == 0
