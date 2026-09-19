"""Process tree cleanup utilities for reliable child process termination."""

from __future__ import annotations

import logging
import subprocess
import sys

logger = logging.getLogger("vkdub.process_tree")


def kill_process_tree(pid: int, timeout_s: float = 5.0) -> bool:
    """Kill a process and all its descendants.

    Uses psutil if available for reliable cross-platform tree termination,
    falls back to Windows taskkill on failure.
    """
    try:
        import psutil

        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            parent.terminate()
            gone, alive = psutil.wait_procs(children + [parent], timeout=timeout_s)
            for proc in alive:
                try:
                    proc.kill()
                except psutil.NoSuchProcess:
                    pass
            return True
        except psutil.NoSuchProcess:
            logger.debug("Process %d already terminated", pid)
            return True
    except ImportError:
        pass

    return _kill_via_taskkill(pid)


def _kill_via_taskkill(pid: int) -> bool:
    """Fallback: use Windows taskkill to kill process tree."""
    if sys.platform != "win32":
        return False
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            logger.debug("Killed process tree for PID %d via taskkill", pid)
            return True
        logger.debug("taskkill returned %d: %s", result.returncode, result.stderr)
        return False
    except Exception as exc:
        logger.debug("taskkill failed for PID %d: %s", pid, exc)
        return False


def kill_qprocess_tree(qprocess) -> None:
    """Kill a QProcess and its entire child tree.

    QProcess.kill() only kills the immediate process.
    This ensures all child processes (spawned by ffmpeg etc.) are also terminated.
    """
    if qprocess is None:
        return
    pid = qprocess.processId()
    if pid > 0:
        kill_process_tree(pid)
    qprocess.kill()
