"""Bounded health checks; selecting an engine never proves it is ready."""

import asyncio
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

from vkdub.domain.translation import GEMINI_MODEL
from vkdub.providers.gemini_translation import ENDPOINT
from vkdub.providers.tts_provider import HealthResult
from vkdub.services.app_settings import AppSettings
from vkdub.services.credential_service import CredentialStore, remember_secret
from vkdub.services.update_service import fetch_update_info, is_newer_version
from vkdub.version import __version__


def check_gemini(
    model: str = GEMINI_MODEL, key: str | None = None, transport: httpx.BaseTransport | None = None
) -> HealthResult:
    def failed(code: str, message: str) -> HealthResult:
        return HealthResult(
            False, code, "Gemini cần cấu hình lại", message, "Cài đặt AI", "open_settings_ai"
        )

    try:
        key = key if key is not None else CredentialStore().get()
    except RuntimeError:
        return failed("GEMINI_VAULT_ERROR", "Không đọc được kho khóa Windows. Hãy thử lại.")
    if not key:
        return failed("GEMINI_MISSING", "Chưa lưu Gemini API Key.")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", model):
        return failed("GEMINI_MODEL_INVALID", "Tên model Gemini không hợp lệ.")
    remember_secret(key)
    try:
        # Small metadata request, never a claim about generation quota.
        with httpx.Client(
            timeout=httpx.Timeout(8, connect=4), follow_redirects=False, transport=transport
        ) as client:
            response = client.get(ENDPOINT + model, headers={"x-goog-api-key": key})
        if response.status_code != 200:
            return failed(
                "GEMINI_HTTP_ERROR",
                f"Gemini trả HTTP {response.status_code}. "
                "Kiểm tra khóa, model và quyền truy cập rồi thử lại.",
            )
        data = response.json()
        if (
            not isinstance(data, dict)
            or data.get("name") != f"models/{model}"
            or ("generateContent" not in data.get("supportedGenerationMethods", []))
        ):
            return failed("GEMINI_RESPONSE_INVALID", "Model chưa xác nhận hỗ trợ tạo nội dung.")
    except (httpx.HTTPError, ValueError, TypeError):
        return failed("GEMINI_NETWORK_ERROR", "Không kiểm tra được Gemini (mạng/timeout). Thử lại.")
    return HealthResult(
        True, "GEMINI_OK", "Gemini", "Kết nối model hợp lệ. Quota dịch chưa xác minh."
    )


def check_tts_backend(backend: str) -> HealthResult:
    if backend == "capcut_tts":
        import json

        from vkdub.services.capcut_setup import CAPCUT_REVISION, SDK_FILES, capcut_root
        from vkdub.services.voice_catalog import read_catalog

        try:
            root = capcut_root()
            marker = json.loads((root / "ready.json").read_text(encoding="utf-8"))
            ready = (
                marker["revision"] == CAPCUT_REVISION
                and marker["duration_ms"] > 0
                and (root / "setup-probe.wav").stat().st_size > 100
                and bool(read_catalog(backend))
                and all((root / "capcut_tts_api" / name).is_file() for name in SDK_FILES)
            )
        except (ValueError, OSError, KeyError, TypeError):
            ready = False
        return HealthResult(
            ready,
            "CAPCUT_READY" if ready else "CAPCUT_SETUP_REQUIRED",
            "CapCut TTS",
            "Đã tạo audio thử. Cần mạng khi đọc; từng giọng có thể thay đổi theo dịch vụ."
            if ready
            else "Bấm Kết nối CapCut để tải danh sách giọng và tạo audio kiểm tra.",
            None if ready else "Cài đặt Voice",
            None if ready else "open_settings_voice",
        )
    if backend == "vieneu_local":
        import json

        from vkdub.services.voice_catalog import (
            VIENEU_VERSION,
            engine_python,
            engine_root,
            read_catalog,
        )

        try:
            marker = json.loads((engine_root() / "ready.json").read_text(encoding="utf-8"))
            ready = (
                engine_python().is_file()
                and marker["duration_ms"] > 0
                and marker["version"] == VIENEU_VERSION
                and bool(read_catalog())
                and bool(marker["model_files"])
                and all(
                    (engine_root() / item["path"]).stat().st_size == item["size"]
                    for item in marker["model_files"]
                )
            )
        except (ValueError, OSError, KeyError, TypeError):
            ready = False
        return HealthResult(
            ready,
            "VIENEU_READY" if ready else "VIENEU_SETUP_REQUIRED",
            "VieNeu Local",
            "Đã cài model và tạo audio kiểm thử. Sẵn sàng dùng offline."
            if ready
            else "VieNeu chưa được cài hoặc kiểm thử. Bấm Cài VieNeu trong Cài đặt Voice.",
            None if ready else "Cài đặt Voice",
            None if ready else "open_settings_voice",
        )
    if backend == "vbee":
        from vkdub.services.app_settings import load_app_settings

        mode = load_app_settings().vbee_mode
        if mode == "api":
            try:
                from vkdub.services.credential_service import VbeeAppStore, VbeeTokenStore

                has_app = bool(VbeeAppStore().get())
                has_token = bool(VbeeTokenStore().get())
                ready = has_app and has_token
                return HealthResult(
                    ready,
                    "VBEE_API_READY" if ready else "VBEE_API_KEY_MISSING",
                    "Vbee API",
                    (
                        "Vbee API đã sẵn sàng (Đã lưu App ID & Token)."
                        if ready
                        else (
                            "Chưa cấu hình App ID hoặc Token cho Vbee API. "
                            "Vui lòng vào Cài đặt -> Voice."
                        )
                    ),
                    None if ready else "Cài đặt Voice",
                    None if ready else "open_settings_voice",
                )
            except Exception as exc:
                return HealthResult(
                    False,
                    "VBEE_API_ERROR",
                    "Vbee API",
                    f"Lỗi kiểm tra Vbee API: {exc}",
                    "Cài đặt Voice",
                    "open_settings_voice",
                )
        try:
            import playwright  # noqa: F401

            from vkdub.integrations.vbee.session import detect_browser_channel

            channel = detect_browser_channel()
            ready = channel is not None
            browser_name = (
                "Microsoft Edge"
                if channel == "msedge"
                else ("Google Chrome" if channel == "chrome" else "Trình duyệt")
            )
            return HealthResult(
                ready,
                "VBEE_READY" if ready else "VBEE_BROWSER_MISSING",
                "Vbee Dubbing Studio",
                (
                    f"Trình duyệt {browser_name} & Playwright đã sẵn sàng. "
                    "Bấm Mở / Kiểm tra để xem hoặc đăng nhập Vbee."
                )
                if ready
                else "Chưa phát hiện Microsoft Edge hoặc Google Chrome để tự động hóa Vbee.",
                None if ready else "Cài đặt Voice",
                None if ready else "open_settings_voice",
            )
        except Exception as exc:
            return HealthResult(
                False,
                "VBEE_ERROR",
                "Vbee Dubbing Studio",
                f"Lỗi kiểm tra Vbee: {exc}",
                "Cài đặt Voice",
                "open_settings_voice",
            )
    title = "CapCut TTS" if backend == "capcut_tts" else "VieNeu Local"
    return HealthResult(
        False,
        "TTS_NOT_INTEGRATED",
        f"{title} chưa sẵn sàng",
        "Bản này chưa tích hợp Voice Engine. Có thể tiếp tục biên tập kịch bản.",
        "Cài đặt Voice",
        "open_settings_voice",
    )


def check_gemini_generation(model: str, key: str | None = None) -> HealthResult:
    """Explicit user connection test: metadata access alone does not prove translation."""
    from vkdub.domain.translation import validate_response
    from vkdub.providers.gemini_translation import GeminiTranslationProvider, ProviderError
    from vkdub.services.usage_service import UsageLedger, UsageRecorder

    try:
        key = key or CredentialStore().get()
        if not key:
            raise ProviderError("Chưa lưu Gemini API Key.")
        provider = GeminiTranslationProvider(
            key, UsageRecorder(UsageLedger()), lambda *_: None, model=model
        )
        response = asyncio.run(
            provider.translate(
                {
                    "source_language": "en",
                    "target_language": "vi",
                    "segments": [
                        {"id": 1, "start": 0, "end": 2, "text": "Hello, have a nice day."}
                    ],
                }
            )
        )
        translated = validate_response(response, [1])[0]
        return HealthResult(
            True, "GEMINI_GENERATION_OK", "Gemini", f"Dịch thử thành công: {translated}"
        )
    except (ValueError, RuntimeError, OSError) as exc:
        return HealthResult(
            False,
            "GEMINI_GENERATION_FAILED",
            "Chưa dịch được",
            str(exc),
            "Cài đặt AI",
            "open_settings_ai",
        )


def check_media_tool(name: str, paths: dict[str, str | None] | None = None) -> HealthResult:
    from vkdub.media.process import find_tool

    available = False
    if paths is not None:
        available = bool(paths.get(name))  # MediaTools already ran -version asynchronously.
    else:
        path = find_tool(name)
        if path:
            try:
                result = subprocess.run(
                    [path, "-version"],
                    capture_output=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                available = result.returncode == 0 and result.stdout.lower().startswith(
                    f"{name} version".encode()
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
    return HealthResult(
        available,
        f"{name.upper()}_{'OK' if available else 'MISSING'}",
        name,
        "Đã kiểm tra phiên bản." if available else "Công cụ chưa chạy được. Kiểm tra cài đặt.",
        None if available else "Cài đặt Media",
        None if available else "open_settings_advanced",
    )


def check_ffmpeg(media_tools: Any | None = None) -> HealthResult:
    paths = getattr(media_tools, "paths", None)
    results = [check_media_tool(name, paths) for name in ("ffmpeg", "ffprobe")]
    return next((r for r in results if not r.ok), results[0])


def _directory_check(path_str: str, *, workspace: bool) -> HealthResult:
    title = "Workspace" if workspace else "CapCut"
    action = "open_settings_general" if workspace else "open_settings_capcut"
    try:
        if not path_str:
            raise OSError
        path = Path(path_str)
        if workspace:
            path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            raise OSError
        with tempfile.TemporaryFile(dir=path, prefix=".vkdub-check-") as probe:
            probe.write(b"ok")
            probe.flush()
        return HealthResult(True, f"{title.upper()}_OK", title, "Thư mục tồn tại và ghi được.")
    except (OSError, ValueError):
        return HealthResult(
            False,
            f"{title.upper()}_WRITE_ERROR",
            f"Kiểm tra thư mục {title}",
            "Thư mục không tồn tại hoặc không có quyền ghi. Chọn lại thư mục.",
            "Chọn thư mục",
            action,
        )


def check_capcut_root(path_str: str) -> HealthResult:
    return _directory_check(path_str, workspace=False)


def check_workspace(path_str: str) -> HealthResult:
    return _directory_check(path_str, workspace=True)


def check_update(enabled: bool) -> HealthResult:
    if not enabled:
        return HealthResult(True, "UPDATE_DISABLED", "Cập nhật", "Đã tắt tự động kiểm tra.")
    info = fetch_update_info(timeout_sec=5)
    if info is None:
        return HealthResult(
            False, "UPDATE_UNAVAILABLE", "Cập nhật", "Chưa kiểm tra được máy chủ cập nhật."
        )
    if is_newer_version(info.version, __version__):
        return HealthResult(
            False,
            "UPDATE_AVAILABLE",
            "Có phiên bản mới",
            f"Phiên bản {info.version} đã có.",
            "Xem cập nhật",
            "open_settings_update",
        )
    return HealthResult(True, "UPDATE_OK", "Cập nhật", "Đang dùng phiên bản mới nhất.")


def run_startup_health_checks(
    settings: AppSettings, media_tools: Any | None = None
) -> list[HealthResult]:
    paths = media_tools if isinstance(media_tools, dict) else getattr(media_tools, "paths", None)
    return [
        check_gemini(settings.gemini_model),
        check_tts_backend(settings.tts_backend),
        check_media_tool("ffmpeg", paths),
        check_media_tool("ffprobe", paths),
        check_capcut_root(settings.capcut_draft_root),
        check_workspace(settings.workspace_root),
        check_update(settings.auto_update),
    ]
