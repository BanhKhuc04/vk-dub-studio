import os
import shutil
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from vkdub.media.ffprobe import parse_metadata


def find_tool(name: str) -> str | None:
    configured = os.environ.get(f"{name.upper()}_PATH")
    if configured:
        path = Path(configured).expanduser()
        return str(path.resolve()) if path.is_file() else None
    found = shutil.which(name)
    if found:
        return found
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        winget_links = Path(local_app_data) / "Microsoft" / "WinGet" / "Links" / f"{name}.exe"
        if winget_links.is_file():
            return str(winget_links.resolve())
        pkg_dir = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if pkg_dir.is_dir():
            for exe in pkg_dir.glob(f"**/{name}.exe"):
                if exe.is_file():
                    return str(exe.resolve())
    return None


class ProcessJob(QObject):
    """QProcess runs media tools asynchronously; no blocking subprocess on the UI thread."""

    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.process = QProcess(self)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._timeout)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._error)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self._done = False
        self._stdout = bytearray()
        self._stderr = bytearray()

    def start(self, program: str, arguments: list[str], timeout_ms: int = 15000) -> None:
        self.timer.start(timeout_ms)
        self.process.start(program, arguments)

    def _read_stdout(self) -> None:
        self._stdout.extend(self.process.readAllStandardOutput().data())
        if len(self._stdout) > 4 * 1024 * 1024:
            self._fail("Kết quả công cụ vượt giới hạn 4 MB.")

    def _read_stderr(self) -> None:
        self._stderr.extend(self.process.readAllStandardError().data())
        self._stderr = self._stderr[-8000:]

    def _finished(self, code: int, status: QProcess.ExitStatus) -> None:
        if self._done:
            return
        self._read_stdout()
        self._read_stderr()
        if self._done:
            return
        if code != 0 or status != QProcess.ExitStatus.NormalExit:
            self._fail("Công cụ media không đọc được tệp. Kiểm tra MP4 và bản cài FFmpeg.")
            return
        self._done = True
        self.timer.stop()
        self.completed.emit(self._stdout.decode("utf-8", errors="replace"))

    def _error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._fail("Không khởi động được công cụ media. Kiểm tra đường dẫn và quyền chạy.")
        elif error == QProcess.ProcessError.Crashed:
            self._fail("Công cụ media đã dừng bất thường.")

    def _timeout(self) -> None:
        self._fail("Công cụ media quá thời gian chờ. Kiểm tra tệp hoặc thử lại.")

    def _fail(self, message: str) -> None:
        if self._done:
            return
        self._done = True
        self.timer.stop()
        self.process.kill()
        self.failed.emit(message)

    def cancel(self) -> None:
        self._done = True
        self.timer.stop()
        self.process.kill()

    def shutdown(self) -> None:
        self.cancel()
        # Only used during application teardown, after asking the child to stop.
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.waitForFinished(1000)


class MediaTools(QObject):
    tool_status = Signal(str, bool, str)
    detection_finished = Signal()
    metadata_ready = Signal(str, object)
    probe_failed = Signal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.paths: dict[str, str | None] = {"ffmpeg": None, "ffprobe": None}
        self._jobs: list[ProcessJob] = []
        self._pending = 0

    def _job(self) -> ProcessJob:
        job = ProcessJob(self)
        self._jobs.append(job)
        job.process.finished.connect(lambda *_: self._release(job))
        job.failed.connect(lambda _: self._release_if_stopped(job))
        return job

    def _release_if_stopped(self, job: ProcessJob) -> None:
        if job.process.state() == QProcess.ProcessState.NotRunning:
            self._release(job)

    def _release(self, job: ProcessJob) -> None:
        if job in self._jobs:
            self._jobs.remove(job)
            job.deleteLater()

    def detect(self) -> None:
        self._pending = 2
        for name in ("ffmpeg", "ffprobe"):
            path = find_tool(name)
            if path is None:
                self._detected(
                    name, None, "Chưa tìm thấy — cài FFmpeg hoặc đặt đường dẫn môi trường."
                )
                continue
            job = self._job()
            job.completed.connect(lambda output, n=name, p=path: self._verify(n, p, output))
            job.failed.connect(lambda message, n=name: self._detected(n, None, message))
            job.start(path, ["-version"], timeout_ms=5000)

    def _verify(self, name: str, path: str, output: str) -> None:
        if output.lower().startswith(f"{name} version"):
            self._detected(name, path, output.splitlines()[0][:160])
        else:
            self._detected(name, None, "Công cụ không trả về phiên bản hợp lệ.")

    def _detected(self, name: str, path: str | None, message: str) -> None:
        self.paths[name] = path
        self.tool_status.emit(name, path is not None, message)
        self._pending -= 1
        if self._pending == 0:
            self.detection_finished.emit()

    def probe(self, path: Path) -> None:
        executable = self.paths["ffprobe"]
        if executable is None:
            self.probe_failed.emit(str(path), "Chưa có ffprobe; không thể đọc metadata.")
            return
        job = self._job()
        job.completed.connect(lambda output: self._parse(path, output))
        job.failed.connect(lambda message: self.probe_failed.emit(str(path), message))
        # argv is passed directly, so spaces and shell metacharacters in filenames are safe.
        job.start(
            executable,
            [
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
        )

    def _parse(self, path: Path, output: str) -> None:
        try:
            metadata = parse_metadata(output)
        except ValueError as exc:
            self.probe_failed.emit(str(path), str(exc))
        else:
            self.metadata_ready.emit(str(path), metadata)

    def shutdown(self) -> None:
        for job in list(self._jobs):
            job.shutdown()
