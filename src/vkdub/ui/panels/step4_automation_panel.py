"""VK Dub Studio — Step 04: Automation Console Panel v2.0.

Right contextual panel for automated pipeline execution:
- 4.1 Transcription (Whisper)
- 4.2 ChatGPT Translation
- 4.3 Script / Timeline Validation
- 4.4 Vbee Voice Generation
- Per-step state: PENDING, RUNNING, SUCCESS, FAILED
- Overall progress with animated gradient
- Health preflight strip with live status
- Pause / Cancel actions
- Clean human-readable error with expandable Technical Details
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from vkdub.orchestrator.pipeline_state import SubstepStatus


class SubstepConsoleCard(QFrame):
    """Card displaying a single automation sub-step (4.1 to 4.4)."""

    retry_requested = Signal(str)
    open_artifact_requested = Signal(object)
    import_srt_requested = Signal()

    STATUS_MAP = {
        SubstepStatus.PENDING: ("○", "#475569", "Chờ"),
        SubstepStatus.RUNNING: ("●", "#38bdf8", "Đang chạy"),
        SubstepStatus.WAITING: ("⏳", "#f59e0b", "Chờ phản hồi"),
        SubstepStatus.VALIDATING: ("🔍", "#a78bfa", "Kiểm tra"),
        SubstepStatus.SUCCESS: ("✓", "#34d399", "Hoàn thành"),
        SubstepStatus.FAILED: ("✖", "#f87171", "Thất bại"),
    }

    def __init__(self, step_id: str, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.step_id = step_id
        self.step_title = title
        self.artifact_path: Path | None = None
        self._raw_error: str | None = None
        self._current_status = SubstepStatus.PENDING

        self.setObjectName("substepCard")
        self.setMinimumHeight(78)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._apply_card_style(SubstepStatus.PENDING)

        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(200)
        self._spin_timer.timeout.connect(self._spin_step)
        self._spin_frames = ["◐", "◓", "◑", "◒"]
        self._spin_idx = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)

        # Header: Icon + Step ID & Title + Duration badge
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_row.setContentsMargins(0, 0, 0, 0)

        self.lbl_icon = QLabel("○")
        self.lbl_icon.setFixedSize(22, 22)
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_icon.setStyleSheet("""
            font-size: 12px; font-weight: bold; color: #475569;
            background-color: #0c111c; border: 2px solid #1e293b;
            border-radius: 11px;
        """)
        header_row.addWidget(self.lbl_icon)

        self.lbl_title = QLabel(f"<b>{step_id}</b> {title}")
        self.lbl_title.setMinimumHeight(20)
        self.lbl_title.setStyleSheet("font-size: 12px; color: #cbd5e1; font-weight: 500;")
        header_row.addWidget(self.lbl_title, 1)

        self.lbl_duration = QLabel("")
        self.lbl_duration.setStyleSheet("font-size: 10px; color: #475569; font-family: Consolas;")
        header_row.addWidget(self.lbl_duration)

        layout.addLayout(header_row)

        # Per-step progress bar
        self.step_progress = QProgressBar()
        self.step_progress.setRange(0, 100)
        self.step_progress.setValue(0)
        self.step_progress.setFixedHeight(4)
        self.step_progress.setTextVisible(False)
        self.step_progress.setStyleSheet("""
            QProgressBar {
                background-color: #0c111c;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #06b6d4);
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.step_progress)

        # Message / Summary line
        self.lbl_summary = QLabel("Đang chờ...")
        self.lbl_summary.setMinimumHeight(18)
        self.lbl_summary.setStyleSheet("font-size: 11px; color: #475569; padding-left: 30px;")
        self.lbl_summary.setWordWrap(True)
        layout.addWidget(self.lbl_summary)

        # Action row (Retry button, open artifact, tech details toggle, import srt)
        self.action_row = QHBoxLayout()
        self.action_row.setContentsMargins(30, 2, 0, 0)
        self.action_row.setSpacing(8)

        self.btn_open_file = QPushButton("📂 Mở file kết quả")
        self.btn_open_file.setStyleSheet("""
            QPushButton {
                background-color: #0c111c; color: #64748b; border: 1px solid #1a2436;
                border-radius: 4px; padding: 3px 10px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background-color: #131b2c; color: #38bdf8; border-color: #0284c7; }
        """)
        self.btn_open_file.hide()
        self.btn_open_file.clicked.connect(self._on_open_artifact)
        self.action_row.addWidget(self.btn_open_file)

        self.btn_retry = QPushButton("🔄 Thử lại")
        self.btn_retry.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #f59e0b);
                color: #ffffff; border: none; border-radius: 4px;
                padding: 3px 12px; font-size: 11px; font-weight: 700;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b45309, stop:1 #d97706);
            }
        """)
        self.btn_retry.hide()
        self.btn_retry.clicked.connect(lambda: self.retry_requested.emit(self.step_id))
        self.action_row.addWidget(self.btn_retry)

        if self.step_id == "4.2":
            self.btn_import_srt = QPushButton("📥 Nạp file SRT dịch")
            self.btn_import_srt.setToolTip(
                "Nạp file phụ đề dịch đã tải từ ChatGPT hoặc có sẵn để tiếp tục ngay không cần dịch lại"
            )
            self.btn_import_srt.setStyleSheet("""
                QPushButton {
                    background-color: #082f49; color: #38bdf8; border: 1px solid #0284c7;
                    border-radius: 4px; padding: 3px 10px; font-size: 11px; font-weight: 600;
                }
                QPushButton:hover { background-color: #0c4a6e; color: #ffffff; border-color: #38bdf8; }
            """)
            self.btn_import_srt.clicked.connect(self.import_srt_requested.emit)
            self.action_row.addWidget(self.btn_import_srt)

        self.btn_toggle_details = QPushButton("Technical details ›")
        self.btn_toggle_details.setStyleSheet("""
            QPushButton {
                background-color: #0c111c; color: #64748b; border: 1px solid #1a2436;
                border-radius: 4px; padding: 3px 10px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background-color: #131b2c; color: #94a3b8; border-color: #24334f; }
        """)
        self.btn_toggle_details.hide()
        self.btn_toggle_details.clicked.connect(self._toggle_tech_details)
        self.action_row.addWidget(self.btn_toggle_details)

        self.badge = self.lbl_icon
        self.msg = self.lbl_summary
        self.error_btn = self.btn_toggle_details
        self.status_badge = QLabel("PENDING")

        self.action_row.addStretch(1)
        layout.addLayout(self.action_row)

        # Collapsible Technical Details Container
        self.tech_details_box = QPlainTextEdit()
        self.tech_details_box.setReadOnly(True)
        self.tech_details_box.setMaximumBlockCount(100)
        self.tech_details_box.setFixedHeight(70)
        self.tech_details_box.setStyleSheet("""
            QPlainTextEdit {
                background-color: #070a10;
                border: 1px solid #1a1a2e;
                border-radius: 4px;
                color: #f87171;
                font-family: Consolas, monospace;
                font-size: 10px;
                padding: 4px;
            }
        """)
        self.tech_details_box.hide()
        layout.addWidget(self.tech_details_box)

    def _spin_step(self) -> None:
        if self._current_status == SubstepStatus.RUNNING:
            self._spin_idx += 1
            frame = self._spin_frames[self._spin_idx % len(self._spin_frames)]
            self.lbl_icon.setText(frame)

    def _apply_card_style(self, status: SubstepStatus) -> None:
        """Apply dynamic border color based on status."""
        if status == SubstepStatus.RUNNING:
            self.setStyleSheet("""
                QFrame#substepCard {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #091526, stop:1 #080d16);
                    border: 1px solid #0284c7;
                    border-left: 3px solid #06b6d4;
                    border-radius: 8px;
                }
            """)
            return

        border_colors = {
            SubstepStatus.PENDING: "#151d2e",
            SubstepStatus.WAITING: "#b45309",
            SubstepStatus.VALIDATING: "#6d28d9",
            SubstepStatus.SUCCESS: "#059669",
            SubstepStatus.FAILED: "#dc2626",
        }
        bc = border_colors.get(status, "#151d2e")
        bg = "#070b14" if status == SubstepStatus.PENDING else "#080d16"
        self.setStyleSheet(f"""
            QFrame#substepCard {{
                background-color: {bg};
                border: 1px solid {bc};
                border-radius: 8px;
            }}
        """)

    def update_info(
        self,
        status: SubstepStatus,
        progress: int,
        message: str,
        artifact: Path | None = None,
        error: str | None = None,
        duration_s: float | None = None,
    ) -> None:
        icon, color, _ = self.STATUS_MAP.get(status, ("○", "#475569", "Chờ"))
        self._current_status = status
        self._apply_card_style(status)

        self.lbl_icon.setText(icon)

        if status == SubstepStatus.RUNNING:
            if not self._spin_timer.isActive():
                self._spin_timer.start()
        else:
            if self._spin_timer.isActive():
                self._spin_timer.stop()

        # Icon pill styling based on status
        icon_styles = {
            SubstepStatus.SUCCESS: f"font-size: 13px; font-weight: bold; color: {color}; background: #0d2a1f; border: 2px solid #059669; border-radius: 12px;",
            SubstepStatus.FAILED: f"font-size: 12px; font-weight: bold; color: {color}; background: #2a0a0a; border: 2px solid #dc2626; border-radius: 12px;",
            SubstepStatus.RUNNING: f"font-size: 12px; font-weight: bold; color: {color}; background: #082f49; border: 2px solid #0284c7; border-radius: 12px;",
            SubstepStatus.WAITING: f"font-size: 12px; font-weight: bold; color: {color}; background: #451a03; border: 2px solid #b45309; border-radius: 12px;",
            SubstepStatus.VALIDATING: f"font-size: 12px; font-weight: bold; color: {color}; background: #1e0a3e; border: 2px solid #6d28d9; border-radius: 12px;",
        }
        self.lbl_icon.setStyleSheet(icon_styles.get(status,
            f"font-size: 12px; font-weight: bold; color: {color}; background-color: #0c111c; border: 2px solid #1e293b; border-radius: 12px;"
        ))

        self.status_badge.setText(status.value if hasattr(status, "value") else str(status))
        self.step_progress.setValue(progress)

        # Progress bar color changes based on status
        if status == SubstepStatus.SUCCESS:
            self.step_progress.setStyleSheet("""
                QProgressBar { background-color: #0c111c; border: none; border-radius: 2px; }
                QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #34d399); border-radius: 2px; }
            """)
        elif status == SubstepStatus.FAILED:
            self.step_progress.setStyleSheet("""
                QProgressBar { background-color: #0c111c; border: none; border-radius: 2px; }
                QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #f87171); border-radius: 2px; }
            """)
        else:
            self.step_progress.setStyleSheet("""
                QProgressBar { background-color: #0c111c; border: none; border-radius: 2px; }
                QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #06b6d4); border-radius: 2px; }
            """)

        # Format clean human-readable summary
        if duration_s is not None and duration_s > 0:
            if duration_s < 60:
                self.lbl_duration.setText(f"⏱ {duration_s:.1f}s")
            else:
                m, s = divmod(int(duration_s), 60)
                self.lbl_duration.setText(f"⏱ {m}m {s}s")
            self.lbl_duration.setStyleSheet("font-size: 10px; color: #64748b; font-family: Consolas;")
        else:
            self.lbl_duration.setText("")

        if error:
            # Human-readable message only on primary UI (never raw Traceback)
            human_msg = message or "Có sự cố xảy ra khi xử lý bước này"
            if len(human_msg) > 90:
                human_msg = human_msg[:87] + "..."
            self.lbl_summary.setText(f"✖ {human_msg}")
            self.lbl_summary.setStyleSheet("font-size: 11px; color: #f87171; font-weight: 600; padding-left: 32px;")
            self.btn_retry.show()

            # Technical details expandable
            self._raw_error = error
            self.tech_details_box.setPlainText(error)
            self.btn_toggle_details.show()
        else:
            self.lbl_summary.setText(message)
            msg_color = {
                SubstepStatus.SUCCESS: "#34d399",
                SubstepStatus.RUNNING: "#38bdf8",
                SubstepStatus.WAITING: "#f59e0b",
                SubstepStatus.VALIDATING: "#a78bfa",
            }.get(status, "#475569")
            self.lbl_summary.setStyleSheet(f"font-size: 11px; color: {msg_color}; padding-left: 32px;")
            self.btn_retry.hide()
            self.btn_toggle_details.hide()
            self.tech_details_box.hide()
            self._raw_error = None

        if artifact and artifact.exists():
            self.artifact_path = artifact
            self.btn_open_file.show()
            self.btn_open_file.setText(f"📂 {artifact.name}")
        else:
            self.btn_open_file.hide()

    def _toggle_tech_details(self) -> None:
        if self.tech_details_box.isVisible():
            self.tech_details_box.hide()
            self.btn_toggle_details.setText("Technical details ›")
        else:
            self.tech_details_box.show()
            self.btn_toggle_details.setText("Technical details ▾")

    def _on_open_artifact(self) -> None:
        if self.artifact_path and self.artifact_path.exists():
            if os.name == "nt":
                subprocess.Popen(
                    ["explorer", f"/select,{self.artifact_path}"],
                    creationflags=0x08000000,
                )
            self.open_artifact_requested.emit(self.artifact_path)


class Step4AutomationPanel(QFrame):
    """Contextual panel for Step 4: Automation Console."""

    start_requested = Signal()
    pause_requested = Signal()
    cancel_requested = Signal()
    retry_step_requested = Signal(str)
    continue_requested = Signal()
    open_log_requested = Signal()
    import_srt_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("step4Panel")
        self.setStyleSheet("""
            QFrame#step4Panel {
                background-color: #050810;
            }
            QLabel.eyebrowTag {
                font-size: 9px;
                font-weight: 800;
                color: #06b6d4;
                letter-spacing: 1.2px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #050810;
                width: 6px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: #1e293b;
                min-height: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #0284c7;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        container = QWidget()
        container.setObjectName("step4Container")
        container.setStyleSheet("QWidget#step4Container { background-color: #050810; }")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # 1. Header & Overall State Badge
        header_row = QHBoxLayout()
        header_col = QVBoxLayout()
        header_col.setSpacing(3)

        eyebrow = QLabel("PIPELINE · STEP 04")
        eyebrow.setProperty("class", "eyebrowTag")
        header_col.addWidget(eyebrow)

        title = QLabel("04 XỬ LÝ TỰ ĐỘNG")
        title.setStyleSheet("""
            font-size: 16px; font-weight: 800; color: #f8fafc;
            letter-spacing: 0.3px;
        """)
        header_col.addWidget(title)
        subtitle = QLabel("Bóc băng → Dịch ngữ cảnh → Kịch bản → Voice Vbee")
        subtitle.setStyleSheet("font-size: 11px; color: #64748b;")
        header_col.addWidget(subtitle)
        header_row.addLayout(header_col, 1)

        self.lbl_est_time = QLabel("")
        self.lbl_est_time.setStyleSheet("font-size: 11px; color: #38bdf8; font-weight: 600; padding-right: 6px;")
        header_row.addWidget(self.lbl_est_time)

        self.overall_badge = QLabel("○ Sẵn sàng")
        self.overall_badge.setStyleSheet("""
            color: #64748b; font-size: 11px; font-weight: bold;
            padding: 3px 10px; border-radius: 5px;
            background: #090f1b; border: 1px solid #1a273e;
        """)
        header_row.addWidget(self.overall_badge)
        layout.addLayout(header_row)

        # 2. Overall Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #0c111c;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #06b6d4);
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # 2b. Browser & Extension Pre-flight Health Strip
        self.health_strip = QFrame()
        self.health_strip.setStyleSheet("""
            QFrame {
                background-color: #0a0f18;
                border: 1px solid #151d2e;
                border-radius: 6px;
                padding: 4px 8px;
            }
        """)
        health_layout = QHBoxLayout(self.health_strip)
        health_layout.setContentsMargins(8, 6, 8, 6)
        health_layout.setSpacing(12)

        self.lbl_health_edge = QLabel("● Edge: Chưa kết nối")
        self.lbl_health_edge.setStyleSheet("color: #475569; font-size: 11px; font-weight: 500;")
        health_layout.addWidget(self.lbl_health_edge)

        self.lbl_health_chatgpt = QLabel("● ChatGPT: Chưa kiểm tra")
        self.lbl_health_chatgpt.setStyleSheet("color: #475569; font-size: 11px; font-weight: 500;")
        health_layout.addWidget(self.lbl_health_chatgpt)

        self.lbl_health_vbee = QLabel("● Vbee: Chưa kiểm tra")
        self.lbl_health_vbee.setStyleSheet("color: #475569; font-size: 11px; font-weight: 500;")
        health_layout.addWidget(self.lbl_health_vbee)

        health_layout.addStretch(1)

        self.btn_health_check = QPushButton("🔍 Kiểm tra sẵn sàng")
        self.btn_health_check.setStyleSheet("""
            QPushButton {
                background: #0c111c; color: #38bdf8; border: 1px solid #0284c7;
                border-radius: 4px; padding: 4px 10px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover {
                background: #0e1a2e; color: #ffffff; border-color: #38bdf8;
            }
        """)
        health_layout.addWidget(self.btn_health_check)
        layout.addWidget(self.health_strip)

        # 3. 4 Sub-step Cards
        self.substeps: dict[str, SubstepConsoleCard] = {}
        substep_configs = [
            ("4.1", "Bóc băng phụ đề gốc (Whisper)"),
            ("4.2", "Dịch ngữ cảnh (ChatGPT qua Edge)"),
            ("4.3", "Kiểm tra kịch bản & timeline"),
            ("4.4", "Tạo giọng đọc (Vbee Studio)"),
        ]

        cards_col = QVBoxLayout()
        cards_col.setSpacing(6)
        for s_id, s_title in substep_configs:
            card = SubstepConsoleCard(s_id, s_title)
            card.retry_requested.connect(self.retry_step_requested.emit)
            if s_id == "4.2":
                card.import_srt_requested.connect(self.import_srt_requested.emit)
            self.substeps[s_id] = card
            cards_col.addWidget(card)
        layout.addLayout(cards_col)
        self.substep_cards = self.substeps

        # 4. Action Buttons (Start, Pause, Cancel)
        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        self.btn_start = QPushButton("⚡ BẮT ĐẦU XỬ LÝ TOÀN BỘ")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                color: #ffffff; font-size: 13px; font-weight: 800;
                padding: 12px 18px; border: 1px solid #34d399; border-radius: 8px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
                border-color: #6ee7b7;
            }
            QPushButton:disabled {
                background: #0c111c; color: #475569; border: 1px solid #1a2436;
            }
        """)
        self.btn_start.setProperty("class", "primaryBtn")
        self.btn_start.clicked.connect(self.start_requested.emit)
        action_row.addWidget(self.btn_start, 1)

        self.btn_cancel = QPushButton("⏹ Dừng")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #450a0a; color: #fca5a5; font-size: 12px; font-weight: 700;
                padding: 10px 16px; border: 1px solid #991b1b; border-radius: 8px;
            }
            QPushButton:hover { background-color: #7f1d1d; color: #ffffff; border-color: #dc2626; }
        """)
        self.btn_cancel.hide()
        self.btn_cancel.clicked.connect(self.cancel_requested.emit)
        action_row.addWidget(self.btn_cancel)

        layout.addLayout(action_row)

        self.chk_auto_voice = QCheckBox("⚡ Tự động tạo giọng Vbee ngay sau khi dịch (không dừng duyệt)")
        self.chk_auto_voice.setChecked(False)
        self.chk_auto_voice.setToolTip(
            "Mặc định tắt để bạn có thể kiểm tra và sửa câu thoại tiếng Việt ở Bước 05 trước khi tổng hợp voice Vbee."
        )
        self.chk_auto_voice.setStyleSheet("color: #64748b; font-size: 11px; padding: 2px 0;")
        layout.addWidget(self.chk_auto_voice)

        layout.addStretch(1)

        # 5. Continue to Review & Export
        self.btn_continue = QPushButton("Tiếp tục: Duyệt kịch bản & Xuất →")
        self.btn_continue.setEnabled(False)
        self.btn_continue.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #06b6d4);
                color: #ffffff; font-size: 13px; font-weight: 800;
                padding: 11px 18px; border: 1px solid #38bdf8; border-radius: 8px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:1 #0891b2);
                border-color: #7dd3fc;
            }
            QPushButton:disabled {
                background: #0c111c; color: #475569; border: 1px solid #1a2436;
            }
        """)
        self.btn_continue.clicked.connect(self.continue_requested.emit)
        layout.addWidget(self.btn_continue)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def auto_voice_checked(self) -> bool:
        return self.chk_auto_voice.isChecked()

    def reset_state(self) -> None:
        for card in self.substeps.values():
            card.lbl_icon.setText("○")
            card.lbl_icon.setStyleSheet("font-size: 12px; font-weight: bold; color: #475569; background-color: #0c111c; border: 2px solid #1e293b; border-radius: 12px;")
            card.lbl_summary.setText("Đang chờ...")
            card.lbl_summary.setStyleSheet("font-size: 11px; color: #475569; padding-left: 32px;")
            card.lbl_duration.setText("")
            card.artifact_path = None
            card._raw_error = None
            card.btn_open_file.hide()
            card.btn_retry.hide()
            card.btn_toggle_details.hide()
            card.tech_details_box.hide()
            card.step_progress.setValue(0)
            card._apply_card_style(SubstepStatus.PENDING)
        self.lbl_est_time.setText("")
        self.update_overall("○ Sẵn sàng", "#475569", 0)
        self.btn_continue.setEnabled(False)

    def set_running_state(self, running: bool) -> None:
        if running:
            self.lbl_est_time.setText("⏱ ~30-60s")
            self.btn_start.setEnabled(False)
            self.btn_start.setText("⏳ Đang xử lý tự động...")
            self.btn_start.setStyleSheet("""
                QPushButton {
                    background-color: #0c111c; color: #475569;
                    border: 1px solid #1a2436; border-radius: 8px;
                    font-size: 13px; font-weight: 800; padding: 12px 18px;
                }
            """)
            self.btn_cancel.show()
            self.overall_badge.setText("● Đang chạy")
            self.overall_badge.setStyleSheet("""
                color: #38bdf8; font-size: 12px; font-weight: bold;
                padding: 4px 12px; border-radius: 6px;
                background: #082f49; border: 1px solid #0284c7;
            """)
        else:
            self.lbl_est_time.setText("")
            self.btn_start.setEnabled(True)
            self.btn_start.setText("⚡ BẮT ĐẦU XỬ LÝ TOÀN BỘ")
            self.btn_start.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                    color: #ffffff; font-size: 13px; font-weight: 800;
                    padding: 12px 18px; border: 1px solid #34d399; border-radius: 8px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
                    border-color: #6ee7b7;
                }
                QPushButton:disabled {
                    background: #0c111c; color: #475569; border: 1px solid #1a2436;
                }
            """)
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
        if step_id in self.substeps:
            self.substeps[step_id].update_info(
                status, progress, message, artifact, error, duration_s
            )

    def update_overall(self, badge_text: str, badge_color: str, progress: int = 0) -> None:
        self.overall_badge.setText(badge_text)
        # Choose background based on badge color
        bg_map = {
            "#3fb950": "#0d2a1f", "#34d399": "#0d2a1f",  # success
            "#58a6ff": "#082f49", "#38bdf8": "#082f49",  # running
            "#f85149": "#2a0a0a", "#f87171": "#2a0a0a",  # error
            "#d29922": "#451a03", "#f59e0b": "#451a03",  # warning
        }
        bg = bg_map.get(badge_color, "#0c111c")
        self.overall_badge.setStyleSheet(f"""
            color: {badge_color}; font-size: 12px; font-weight: bold;
            padding: 4px 12px; border-radius: 6px;
            background: {bg}; border: 1px solid {badge_color};
        """)
        self.progress_bar.setValue(progress)

    def automation_summary(self) -> str:
        done_count = sum(1 for c in self.substeps.values() if c.lbl_icon.text() == "✓")
        if done_count == 4:
            return "Hoàn tất (4/4)"
        if any(c.lbl_icon.text() == "●" for c in self.substeps.values()):
            return "Đang chạy..."
        if done_count == 3 and "4.4" in self.substeps and self.substeps["4.4"].lbl_icon.text() in ("⏳", "○"):
            return "Đã dịch (3/4)"
        if done_count > 0:
            return f"Đạt {done_count}/4 bước"
        return "Sẵn sàng"

    def update_health(self, status: any) -> None:
        if not status:
            return
        if getattr(status, "browser_connected", False):
            self.lbl_health_edge.setText("● Edge: Đã kết nối")
            self.lbl_health_edge.setStyleSheet("color: #34d399; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_health_edge.setText("● Edge: Chưa kết nối")
            self.lbl_health_edge.setStyleSheet("color: #f87171; font-size: 11px; font-weight: bold;")

        if getattr(status, "chatgpt_logged_in", False):
            self.lbl_health_chatgpt.setText("● ChatGPT: Sẵn sàng")
            self.lbl_health_chatgpt.setStyleSheet("color: #34d399; font-size: 11px; font-weight: bold;")
        elif getattr(status, "chatgpt_available", False):
            self.lbl_health_chatgpt.setText("● ChatGPT: Chưa đăng nhập")
            self.lbl_health_chatgpt.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_health_chatgpt.setText("● ChatGPT: Chưa mở tab")
            self.lbl_health_chatgpt.setStyleSheet("color: #475569; font-size: 11px;")

        if getattr(status, "vbee_logged_in", False):
            self.lbl_health_vbee.setText("● Vbee: Sẵn sàng")
            self.lbl_health_vbee.setStyleSheet("color: #34d399; font-size: 11px; font-weight: bold;")
        elif getattr(status, "vbee_available", False):
            self.lbl_health_vbee.setText("● Vbee: Chưa đăng nhập")
            self.lbl_health_vbee.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_health_vbee.setText("● Vbee: Chưa mở tab")
            self.lbl_health_vbee.setStyleSheet("color: #475569; font-size: 11px;")
