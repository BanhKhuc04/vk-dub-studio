"""VK Dub Studio — Step 4 Automatic Processing Widget.

Displays real-time execution state for:
4.1 Transcription
4.2 ChatGPT translation
4.3 Script preparation
4.4 Vbee voice generation

Each sub-step exposes:
- Status (PENDING, RUNNING, WAITING, VALIDATING, SUCCESS, FAILED)
- Progress % and current action description
- Duration and generated artifact link
- Error message and per-step Retry action
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vkdub.orchestrator.pipeline_state import SubstepStatus


class SubstepRowWidget(QFrame):
    """Individual row component for 4.1 - 4.4 sub-steps."""

    retry_requested = Signal(str)  # step_id
    open_artifact_requested = Signal(object)  # Path

    STATUS_COLORS = {
        SubstepStatus.PENDING: ("#8b949e", "○ Chờ"),
        SubstepStatus.RUNNING: ("#58a6ff", "● Đang chạy"),
        SubstepStatus.WAITING: ("#d29922", "⏳ Chờ phản hồi"),
        SubstepStatus.VALIDATING: ("#bc8cff", "🔍 Kiểm tra"),
        SubstepStatus.SUCCESS: ("#3fb950", "✔ Xong"),
        SubstepStatus.FAILED: ("#f85149", "✖ Lỗi"),
    }

    def __init__(self, step_id: str, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.step_id = step_id
        self.name = name
        self.artifact_path: Path | None = None

        self.setObjectName("substepRow")
        self.setStyleSheet("""
            QFrame#substepRow {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 8px;
                margin: 2px 0;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Line 1: Step ID, Name, Status Badge, Duration
        top_row = QHBoxLayout()
        self.title_label = QLabel(f"<b>{step_id}</b> {name}")
        self.title_label.setStyleSheet("color: #c9d1d9; font-size: 11px;")
        top_row.addWidget(self.title_label, 1)

        self.duration_label = QLabel("")
        self.duration_label.setStyleSheet("color: #8b949e; font-size: 10px;")
        top_row.addWidget(self.duration_label)

        self.status_badge = QLabel("○ Chờ")
        self.status_badge.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: bold;")
        top_row.addWidget(self.status_badge)
        layout.addLayout(top_row)

        # Line 2: Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #21262d;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #238636;
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Line 3: Action Message & Action Buttons
        bottom_row = QHBoxLayout()
        self.message_label = QLabel("Đang chờ...")
        self.message_label.setStyleSheet("color: #8b949e; font-size: 10px;")
        self.message_label.setWordWrap(True)
        bottom_row.addWidget(self.message_label, 1)

        self.btn_open_artifact = QPushButton("📂 Mở file")
        self.btn_open_artifact.setStyleSheet(
            "padding: 2px 6px; font-size: 10px; background-color: #21262d; color:"
            " #c9d1d9; border: 1px solid #30363d; border-radius: 3px;"
        )
        self.btn_open_artifact.hide()
        self.btn_open_artifact.clicked.connect(self._on_open_artifact)
        bottom_row.addWidget(self.btn_open_artifact)

        self.btn_retry = QPushButton("🔄 Thử lại")
        self.btn_retry.setStyleSheet(
            "padding: 2px 6px; font-size: 10px; background-color: #d29922; color:"
            " black; font-weight: bold; border-radius: 3px;"
        )
        self.btn_retry.hide()
        self.btn_retry.clicked.connect(lambda: self.retry_requested.emit(self.step_id))
        bottom_row.addWidget(self.btn_retry)

        layout.addLayout(bottom_row)

    def update_info(
        self,
        status: SubstepStatus,
        progress: int,
        message: str,
        artifact: Path | None = None,
        error: str | None = None,
        duration_s: float | None = None,
    ) -> None:
        color, text = self.STATUS_COLORS.get(status, ("#8b949e", status.value))
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")

        self.progress_bar.setValue(progress)
        self.message_label.setText(message)

        if error:
            self.message_label.setStyleSheet("color: #f85149; font-size: 10px; font-weight: bold;")
            self.btn_retry.show()
        else:
            self.message_label.setStyleSheet("color: #8b949e; font-size: 10px;")
            self.btn_retry.hide()

        if duration_s is not None and duration_s > 0:
            if duration_s < 60:
                self.duration_label.setText(f"⏱ {duration_s:.1f}s")
            else:
                mins = int(duration_s // 60)
                secs = int(duration_s % 60)
                self.duration_label.setText(f"⏱ {mins}m {secs}s")

        if artifact:
            self.artifact_path = artifact
            self.btn_open_artifact.show()
            self.btn_open_artifact.setToolTip(str(artifact))

    def _on_open_artifact(self) -> None:
        if self.artifact_path and self.artifact_path.exists():
            if os.name == "nt":
                subprocess.Popen(
                    ["explorer", f"/select,{self.artifact_path}"],
                    creationflags=0x08000000,
                )
            self.open_artifact_requested.emit(self.artifact_path)


class Step4PipelineWidget(QFrame):
    """Complete Step 4 widget with all 4.1 - 4.4 rows and runner controls."""

    start_requested = Signal()
    cancel_requested = Signal()
    retry_step_requested = Signal(str)
    view_log_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("step4Widget")
        self.setStyleSheet("""
            QFrame#step4Widget {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 10px;
                margin: 4px 0;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Title & Global Status
        header = QHBoxLayout()
        title = QLabel("BƯỚC 4: XỬ LÝ TỰ ĐỘNG (END-TO-END)")
        title.setStyleSheet("color: #58a6ff; font-weight: bold; font-size: 12px;")
        header.addWidget(title, 1)

        self.overall_badge = QLabel("○ Sẵn sàng")
        self.overall_badge.setStyleSheet("color: #8b949e; font-size: 11px;")
        header.addWidget(self.overall_badge)
        layout.addLayout(header)

        # Sub-step Rows Container
        self.rows: dict[str, SubstepRowWidget] = {}
        row_configs = [
            ("4.1", "Bóc băng phụ đề gốc (Whisper)"),
            ("4.2", "Dịch ngữ cảnh (ChatGPT qua Edge)"),
            ("4.3", "Chuẩn bị kịch bản & timeline"),
            ("4.4", "Tạo giọng đọc (Vbee Ngọc Huyền 1.1x)"),
        ]

        for s_id, s_name in row_configs:
            row = SubstepRowWidget(s_id, s_name)
            row.retry_requested.connect(self.retry_step_requested.emit)
            self.rows[s_id] = row
            layout.addWidget(row)

        # Action Buttons
        action_box = QVBoxLayout()
        action_box.setSpacing(6)

        self.btn_primary = QPushButton("⚡ BƯỚC 4: BẮT ĐẦU XỬ LÝ TOÀN BỘ")
        self.btn_primary.setObjectName("primary")
        self.btn_primary.setStyleSheet(
            "padding: 10px; font-weight: bold; font-size: 12px; background-color:"
            " #238636; color: white; border-radius: 6px;"
        )
        self.btn_primary.clicked.connect(self._on_primary_clicked)
        action_box.addWidget(self.btn_primary)

        tools_row = QHBoxLayout()
        self.btn_cancel = QPushButton("⏹ Dừng")
        self.btn_cancel.setStyleSheet(
            "padding: 4px 10px; background-color: #da3633; color: white; border:"
            " none; border-radius: 4px;"
        )
        self.btn_cancel.hide()
        self.btn_cancel.clicked.connect(self.cancel_requested.emit)
        tools_row.addWidget(self.btn_cancel)

        self.btn_view_log = QPushButton("📄 Xem log xử lý")
        self.btn_view_log.setStyleSheet(
            "padding: 4px 10px; background-color: #21262d; color: #c9d1d9; border:"
            " 1px solid #30363d; border-radius: 4px;"
        )
        self.btn_view_log.clicked.connect(self.view_log_requested.emit)
        tools_row.addWidget(self.btn_view_log)

        action_box.addLayout(tools_row)
        layout.addLayout(action_box)

        self._is_running = False

    def _on_primary_clicked(self) -> None:
        if not self._is_running:
            self.start_requested.emit()

    def set_running_state(self, running: bool) -> None:
        self._is_running = running
        if running:
            self.btn_primary.setEnabled(False)
            self.btn_primary.setText("⏳ Đang xử lý tự động...")
            self.btn_primary.setStyleSheet("background-color: #21262d; color: #8b949e;")
            self.btn_cancel.show()
            self.overall_badge.setText("● Đang chạy")
            self.overall_badge.setStyleSheet("color: #58a6ff; font-weight: bold;")
        else:
            self.btn_primary.setEnabled(True)
            self.btn_primary.setText("⚡ BƯỚC 4: BẮT ĐẦU XỬ LÝ TOÀN BỘ")
            self.btn_primary.setStyleSheet(
                "padding: 10px; font-weight: bold; font-size: 12px; background-color:"
                " #238636; color: white; border-radius: 6px;"
            )
            self.btn_cancel.hide()

    def update_substep(
        self,
        step_id: str,
        status: SubstepStatus,
        progress: int,
        message: str,
        artifact: Path | None = None,
        error: str | None = None,
        duration_s: float | None = None,
    ) -> None:
        if step_id in self.rows:
            self.rows[step_id].update_info(status, progress, message, artifact, error, duration_s)
