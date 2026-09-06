import sys

from PySide6.QtCore import QTimer

from vkdub.media.process import MediaTools, ProcessJob, find_tool


def test_find_tool_honors_explicit_path(monkeypatch, tmp_path):
    tool = tmp_path / "media tool.exe"
    tool.write_bytes(b"test")
    monkeypatch.setenv("FFPROBE_PATH", str(tool))
    assert find_tool("ffprobe") == str(tool)
    monkeypatch.setenv("FFPROBE_PATH", str(tmp_path / "missing.exe"))
    assert find_tool("ffprobe") is None


def test_missing_tools_report_both_and_finish(qtbot, monkeypatch):
    monkeypatch.setattr("vkdub.media.process.find_tool", lambda _: None)
    tools = MediaTools()
    statuses = []
    tools.tool_status.connect(lambda *args: statuses.append(args))
    with qtbot.waitSignal(tools.detection_finished):
        tools.detect()
    assert len(statuses) == 2
    assert all(not result[1] for result in statuses)
    tools.shutdown()


def test_process_does_not_block_ui(qtbot):
    job = ProcessJob()
    ticks = []
    timer = QTimer()
    timer.setInterval(20)
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start()
    with qtbot.waitSignal(job.completed, timeout=5000) as result:
        job.start(sys.executable, ["-c", "import time; time.sleep(0.3); print('ok')"])
    timer.stop()
    assert result.args == ["ok\r\n"] or result.args == ["ok\n"]
    assert len(ticks) >= 3
    job.shutdown()


def test_process_timeout_emits_once(qtbot):
    job = ProcessJob()
    errors = []
    job.failed.connect(errors.append)
    with qtbot.waitSignal(job.failed, timeout=5000):
        job.start(sys.executable, ["-c", "import time; time.sleep(10)"], timeout_ms=100)
    job.shutdown()
    assert len(errors) == 1


def test_invalid_executable_is_actionable(qtbot, tmp_path):
    job = ProcessJob()
    with qtbot.waitSignal(job.failed, timeout=5000) as result:
        job.start(str(tmp_path / "missing.exe"), [])
    assert "khởi động" in result.args[0]
    job.shutdown()
