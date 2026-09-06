"""Isolated upstream request builder with bounded HTTP and actual task status handling."""

import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx


class CapCutWorkerError(ValueError):
    """Only our own safe messages may cross the worker boundary."""


def speech_url(task: dict[str, Any]) -> str:
    payload = task["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    rows = payload["audio_subtitles"]
    if len(rows) != 1 or str(rows[0].get("code", 0)) != "0" or rows[0].get("invalid_input"):
        raise CapCutWorkerError("CapCut không tạo được âm thanh cho câu này.")
    url = rows[0]["speech_url"]
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise CapCutWorkerError("CapCut trả địa chỉ audio không hợp lệ.")
    return str(url)


def synthesize(request: dict[str, Any]) -> None:
    from capcut_tts_api import CapCutClient

    sdk = CapCutClient(session=object())
    voice = request["voice"]
    with httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=False) as client:

        def post(arguments: tuple) -> dict:
            url, headers, body = arguments
            response = client.post(url, headers=headers, content=body.encode())
            if response.status_code != 200:
                raise CapCutWorkerError(
                    f"CapCut trả HTTP {response.status_code}. Thử lại hoặc dùng VieNeu."
                )
            result = response.json()
            if str(result.get("ret", 0)) != "0":
                raise CapCutWorkerError("CapCut từ chối yêu cầu. Thử lại hoặc dùng VieNeu offline.")
            return dict(result)

        created = post(
            sdk.build_tts_new_request(
                request["text"], voice["upstream_id"], voice["resource_id"], "1.0"
            )
        )
        tasks = (created.get("data") or {}).get("tasks") or []
        if not tasks:
            raise ValueError("CapCut không nhận yêu cầu tạo giọng. Hãy thử VieNeu.")
        submitted = tasks[0]
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            result = post(sdk.build_query_request(submitted["id"], submitted["token"]))
            tasks = (result.get("data") or {}).get("tasks") or []
            if tasks and tasks[0].get("status") in ("succeed", "success"):
                url = speech_url(tasks[0])
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    size = 0
                    with Path(request["output"]).open("wb") as output:
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > 25_000_000:
                                raise ValueError("Audio CapCut quá lớn cho một câu.")
                            output.write(chunk)
                    if size < 100:
                        raise ValueError("CapCut trả audio trống.")
                return
            if tasks and tasks[0].get("status") in ("failed", "fail", "cancelled"):
                raise ValueError(
                    "CapCut không tạo được giọng này. Chọn giọng khác hoặc dùng VieNeu."
                )
            time.sleep(1)
        raise ValueError("CapCut chờ quá lâu. Thử lại hoặc dùng VieNeu offline.")


def main() -> None:
    for line in sys.stdin:
        try:
            synthesize(json.loads(line))
            result = {"ok": True, "result": {}}
        except (httpx.HTTPError, OSError):
            result = {
                "ok": False,
                "error": "Không kết nối được CapCut TTS. Kiểm tra mạng hoặc dùng VieNeu.",
            }
        except CapCutWorkerError as exc:
            result = {"ok": False, "error": str(exc)}
        except Exception:
            # Never expose task tokens, signed URLs, upstream responses or input text.
            result = {
                "ok": False,
                "error": "CapCut chưa tạo được audio. Thử giọng khác hoặc dùng VieNeu offline.",
            }
        print("VKDUB_RESULT " + json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
