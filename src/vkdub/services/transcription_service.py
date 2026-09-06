import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

from vkdub.utils.paths import workspace_root


class JobCancelled(Exception):
    pass


def run_process(
    arguments: list[str],
    directory: Path,
    cancel: threading.Event,
    report: Any,
    *,
    offline: bool = True,
) -> int:
    """Run one command at a time; cancellation also stops Windows venv launcher children."""
    environment = dict(os.environ)
    environment.update(
        PYTHONIOENCODING="utf-8",
        HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
        HF_HUB_DISABLE_TELEMETRY="1",
        DO_NOT_TRACK="1",
    )
    if offline:
        environment.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    output = directory / "progress.jsonl"
    errors = directory / "stderr.txt"
    with output.open("wb") as stdout, errors.open("wb") as stderr:
        if cancel.is_set():
            raise JobCancelled
        process = subprocess.Popen(
            arguments,
            stdout=stdout,
            stderr=stderr,
            env=environment,
            creationflags=flags,
            stdin=subprocess.DEVNULL,
        )
        try:
            with output.open("r", encoding="utf-8", errors="replace") as reader:
                pending = ""
                started = time.monotonic()
                while True:
                    if cancel.is_set():
                        raise JobCancelled
                    if time.monotonic() - started > 21600:
                        raise TimeoutError("Công việc vượt quá 6 giờ. Hãy thử video ngắn hơn.")
                    code = process.poll()
                    pending += reader.read()
                    lines = pending.split("\n")
                    pending = lines.pop()
                    for line in lines:
                        if line.strip():
                            data = json.loads(line)
                            report(int(data["percent"]), str(data["message"]))
                    if code is not None:
                        return code
                    cancel.wait(0.05)
        finally:
            if process.poll() is None:
                if sys.platform == "win32":
                    # Windows venv python.exe is a redirector with a child interpreter.
                    # Terminating only the redirector leaves inference and file handles alive.
                    taskkill = (
                        Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/taskkill.exe"
                    )
                    subprocess.run(
                        [str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=flags,
                        timeout=5,
                        check=False,
                    )
                else:
                    process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


class LocalJob(QThread):
    progress = Signal(int, str)
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, request: dict[str, Any]) -> None:
        super().__init__()
        self.request = request
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            root = workspace_root() / "temp"
            root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="stt-", dir=root) as folder:
                directory = Path(folder)
                if self.request["kind"] == "transcript":
                    self.progress.emit(-1, "Đang tách âm thanh WAV 16 kHz mono…")
                    code = run_process(
                        [
                            self.request["ffmpeg"],
                            "-hide_banner",
                            "-loglevel",
                            "error",
                            "-nostdin",
                            "-i",
                            self.request["video"],
                            "-map",
                            "0:a:0",
                            "-vn",
                            "-ac",
                            "1",
                            "-ar",
                            "16000",
                            "-c:a",
                            "pcm_s16le",
                            "-y",
                            str(directory / "audio.wav"),
                        ],
                        directory,
                        self.cancel_event,
                        self.progress.emit,
                    )
                    if code:
                        raise ValueError(
                            "Không tách được âm thanh. Video phải có luồng audio hợp lệ; "
                            "kiểm tra FFmpeg và quyền ghi thư mục tạm."
                        )
                request_file, result_file = directory / "request.json", directory / "result.json"
                request_file.write_text(json.dumps(self.request), encoding="utf-8")
                code = run_process(
                    [
                        sys.executable,
                        "-m",
                        "vkdub.services.transcription_runner",
                        str(request_file),
                        str(result_file),
                    ],
                    directory,
                    self.cancel_event,
                    self.progress.emit,
                    offline=self.request["kind"] != "model",
                )
                if self.cancel_event.is_set():
                    raise JobCancelled
                if not result_file.is_file():
                    raise RuntimeError(
                        f"Worker dừng bất thường ({code}). "
                        "Thử CPU; kiểm tra thư viện và dung lượng bộ nhớ."
                    )
                result = json.loads(result_file.read_text(encoding="utf-8"))
                if code or "error" in result:
                    raise RuntimeError(result.get("error", "Không hoàn thành công việc."))
            if self.cancel_event.is_set():
                raise JobCancelled
            self.succeeded.emit(result)
        except JobCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
