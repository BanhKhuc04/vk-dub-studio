"""Integration test for MainWindow and Step 4 PipelineRunner."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from vkdub.orchestrator.pipeline_state import (
    ArtifactRegistry,
    SubstepStatus,
)
from vkdub.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_main_window_pipeline_wiring(qapp, tmp_path: Path):
    with patch("vkdub.ui.main_window.QTimer.singleShot"):
        win = MainWindow()

    # Verify initial state
    assert win.pipeline_runner is None
    assert win.left.step4_pipeline is not None
    assert win.left.step4_pipeline.btn_primary.text() == "⚡ BƯỚC 4: BẮT ĐẦU XỬ LÝ TOÀN BỘ"

    # Simulate substep update
    win._on_pipeline_substep_updated("4.1", SubstepStatus.RUNNING, 50, "Đang bóc băng...")
    row_41 = win.left.step4_pipeline.rows["4.1"]
    assert row_41.progress_bar.value() == 50
    assert row_41.message_label.text() == "Đang bóc băng..."
    assert "Đang chạy" in row_41.status_badge.text()

    # Simulate substep success
    dummy_srt = tmp_path / "trans.srt"
    dummy_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nXin chào\n", encoding="utf-8")
    win._on_pipeline_substep_updated(
        "4.2", SubstepStatus.SUCCESS, 100, "Dịch thành công", artifact=dummy_srt, duration_s=4.5
    )
    row_42 = win.left.step4_pipeline.rows["4.2"]
    assert row_42.progress_bar.value() == 100
    assert "Xong" in row_42.status_badge.text()
    assert "4.5s" in row_42.duration_label.text()
    assert not row_42.btn_open_artifact.isHidden()

    # Simulate artifact ready
    master_audio = tmp_path / "master.mp3"
    master_audio.write_bytes(b"dummy mp3")
    win._on_pipeline_artifact_ready("master_audio", master_audio)
    assert win.project.master_voice_path == master_audio

    # Simulate pipeline completed
    artifacts = ArtifactRegistry(timeline_master_audio=master_audio)
    with patch("PySide6.QtWidgets.QMessageBox.information"):
        win._on_pipeline_completed(artifacts)

    assert win.busy is False
    assert "Hoàn thành" in win.left.step4_pipeline.overall_badge.text()
    assert "hoàn tất" in win.left.lbl_review_status.text().lower()

    # Clean up local agent server
    if win.local_agent:
        win.local_agent.stop()
