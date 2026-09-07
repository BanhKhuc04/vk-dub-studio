import json
import sys
import threading
import time

import pytest
from PySide6.QtCore import QTimer

from vkdub.services.transcription_service import JobCancelled, LocalJob, run_process


def test_cancel_running_process_is_prompt_and_reaps_child(tmp_path):
    event = threading.Event()
    timer = threading.Timer(0.2, event.set)
    started = time.monotonic()
    timer.start()
    try:
        with pytest.raises(JobCancelled):
            run_process(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                tmp_path,
                event,
                lambda *a: None,
            )
    finally:
        timer.cancel()
    assert time.monotonic() - started < 3
    # Windows permits removal only after the child process has closed its handles.
    (tmp_path / "stderr.txt").unlink()
    (tmp_path / "progress.jsonl").unlink()


def test_process_progress_and_offline_environment(tmp_path):
    received = []
    script = (
        "import os,json; print(json.dumps({'percent':42,'message':os.environ['HF_HUB_OFFLINE']}))"
    )
    assert (
        run_process(
            [sys.executable, "-c", script],
            tmp_path,
            threading.Event(),
            lambda *args: received.append(args),
        )
        == 0
    )
    assert received == [(42, "1")]


def test_cancel_before_worker_start_has_no_network(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
    job = LocalJob({"kind": "model", "model": "tiny"})
    job.cancel()
    with qtbot.waitSignal(job.cancelled, timeout=5000):
        job.start()
    assert job.wait(3000)
    assert list((tmp_path / "temp").iterdir()) == []


def test_worker_error_cleans_temporary_files(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
    job = LocalJob(
        {"kind": "transcript", "ffmpeg": str(tmp_path / "missing.exe"), "video": "a.mp4"}
    )
    with qtbot.waitSignal(job.failed, timeout=5000):
        job.start()
    assert job.wait(3000)
    assert list((tmp_path / "temp").iterdir()) == []


def test_worker_runs_off_ui_thread(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
    ui_thread = threading.get_ident()
    observed = []

    def process(args, directory, cancel, report, **kwargs):
        observed.append(threading.get_ident())
        time.sleep(0.2)
        (directory / "result.json").write_text(json.dumps({"kind": "model", "model": "tiny"}))
        return 0

    monkeypatch.setattr("vkdub.services.transcription_service.run_process", process)
    job = LocalJob({"kind": "model", "model": "tiny"})
    ticks = []
    timer = QTimer()
    timer.setInterval(20)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    with qtbot.waitSignal(job.succeeded, timeout=5000):
        job.start()
    timer.stop()
    assert job.wait(3000)
    assert observed[0] != ui_thread
    assert len(ticks) >= 3
    assert list((tmp_path / "temp").iterdir()) == []


def test_frozen_worker_uses_explicit_dispatch_flag(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("VKDUB_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    commands = []

    def process(args, directory, cancel, report, **kwargs):
        commands.append(args)
        (directory / "result.json").write_text(
            json.dumps({"kind": "model", "model": "tiny"}), encoding="utf-8"
        )
        return 0

    monkeypatch.setattr("vkdub.services.transcription_service.run_process", process)
    job = LocalJob({"kind": "model", "model": "tiny"})
    with qtbot.waitSignal(job.succeeded, timeout=5000):
        job.start()
    assert job.wait(3000)
    assert commands[0][1] == "--vkdub-transcription-worker"
