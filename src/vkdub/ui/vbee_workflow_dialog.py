"""Dialog displaying real-time Vbee Voice workflow progress and checklist."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vkdub.integrations.vbee.state import CHECKLIST_STEPS, WorkflowState

if TYPE_CHECKING:
    from vkdub.ui.vbee_controller import VbeeController


class VbeeWorkflowDialog(QDialog):
    """Visual progress dialog for the Vbee Dubbing workflow."""

    cancel_requested = Signal()

    def __init__(self, controller: VbeeController, parent: QWidget | None = None) -> None:
        effective_parent = parent or (
            controller.window if isinstance(controller.window, QWidget) else None
        )
        super().__init__(effective_parent)
        self.controller = controller
        self.setWindowTitle("VK Dub Studio — Tạo Voice bằng Vbee Dubbing")
        self.resize(580, 480)
        self.setMinimumSize(500, 420)
        self.setWindowModality(Qt.WindowModality.WindowModal)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(12)

        # Title & Subtitle
        header = QVBoxLayout()
        header.setSpacing(4)
        title_lbl = QLabel("TẠO VOICE TỰ ĐỘNG BẰNG VBEE")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8;")
        header.addWidget(title_lbl)

        desc_lbl = QLabel(
            "Tự động xuất phụ đề SRT tiếng Việt, mở Vbee Dubbing, tải SRT, theo dõi "
            "xử lý, tải âm thanh và đồng bộ trực tiếp vào project."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        header.addWidget(desc_lbl)
        main_layout.addLayout(header)

        # Current status banner
        self.status_banner = QLabel("Trạng thái: Sẵn sàng khởi động…")
        self.status_banner.setStyleSheet(
            "background: #1e293b; color: #f8fafc; border: 1px solid #334155; "
            "border-radius: 6px; padding: 8px 12px; font-weight: 600; font-size: 13px;"
        )
        main_layout.addWidget(self.status_banner)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background: #0f172a; border: 1px solid #334155; "
            "border-radius: 4px; height: 12px; text-align: center; } "
            "QProgressBar::chunk { background: #0284c7; border-radius: 3px; }"
        )
        main_layout.addWidget(self.progress_bar)

        # Checklist Box
        checklist_box = QFrame()
        checklist_box.setStyleSheet(
            "background: #0b1120; border: 1px solid #1e293b; border-radius: 6px; padding: 10px;"
        )
        checklist_layout = QVBoxLayout(checklist_box)
        checklist_layout.setContentsMargins(8, 6, 8, 6)
        checklist_layout.setSpacing(6)

        self.step_labels: dict[str, QLabel] = {}
        for key, text in CHECKLIST_STEPS:
            row = QLabel(f"○  {text}")
            row.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 500;")
            self.step_labels[key] = row
            checklist_layout.addWidget(row)

        main_layout.addWidget(checklist_box)

        # Activity log
        log_header = QLabel("Nhật ký chi tiết:")
        log_header.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        main_layout.addWidget(log_header)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setStyleSheet(
            "background: #020617; color: #cbd5e1; border: 1px solid #1e293b; "
            "font-family: Consolas, monospace; font-size: 11px; border-radius: 4px; padding: 6px;"
        )
        self.log_edit.setMaximumHeight(100)
        main_layout.addWidget(self.log_edit)

        # Buttons
        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.stop_button = QPushButton("⏹ Dừng / Hủy")
        self.stop_button.setStyleSheet(
            "background: #475569; color: #f8fafc; font-weight: 600; padding: 6px 14px;"
        )
        self.stop_button.clicked.connect(self._on_stop_clicked)
        button_row.addWidget(self.stop_button)

        button_row.addStretch()

        self.close_button = QPushButton("Đóng")
        self.close_button.setEnabled(False)
        self.close_button.setStyleSheet(
            "background: #334155; color: #f8fafc; font-weight: 600; padding: 6px 18px;"
        )
        self.close_button.clicked.connect(self.accept)
        button_row.addWidget(self.close_button)

        main_layout.addLayout(button_row)

    def _on_stop_clicked(self) -> None:
        self.stop_button.setEnabled(False)
        self.append_log("Đang yêu cầu dừng tiến trình Vbee…")
        self.cancel_requested.emit()

    def append_log(self, text: str) -> None:
        self.log_edit.appendPlainText(text)
        self.log_edit.verticalScrollBar().setValue(self.log_edit.verticalScrollBar().maximum())

    def update_state(self, state: WorkflowState, message: str) -> None:
        """Update progress bar, checklist icons, and status text based on workflow state."""
        if state == WorkflowState.LOGIN_REQUIRED:
            banner_text = "Vui lòng đăng nhập Vbee trên cửa sổ Edge. Chỉ cần thực hiện một lần."
            self.status_banner.setText(f"Trạng thái: {banner_text}")
            self.status_banner.setStyleSheet(
                "background: #78350f; color: #fef3c7; border: 1px solid #d97706; "
                "border-radius: 6px; padding: 8px 12px; font-weight: bold; font-size: 13px;"
            )
        else:
            self.status_banner.setText(f"Trạng thái: {message}")
            if not state.is_terminal:
                self.status_banner.setStyleSheet(
                    "background: #1e293b; color: #f8fafc; border: 1px solid #334155; "
                    "border-radius: 6px; padding: 8px 12px; font-weight: 600; font-size: 13px;"
                )

        self.append_log(f"[{state.value}] {message}")

        # Map state to current step index in checklist
        state_mapping = {
            WorkflowState.VALIDATING: 0,
            WorkflowState.EXPORTING_SRT: 0,
            WorkflowState.OPENING_VBEE: 1,
            WorkflowState.LOGIN_REQUIRED: 1,
            WorkflowState.UPLOADING_SRT: 2,
            WorkflowState.CONFIGURING_VOICE: 3,
            WorkflowState.SUBMITTING: 3,
            WorkflowState.PROCESSING: 3,
            WorkflowState.DOWNLOADING: 4,
            WorkflowState.PROCESSING_AUDIO: 5,
            WorkflowState.IMPORTING_AUDIO: 5,
            WorkflowState.READY: 6,
        }

        active_idx = state_mapping.get(state, -1)

        for idx, (key, label_text) in enumerate(CHECKLIST_STEPS):
            lbl = self.step_labels[key]
            if state == WorkflowState.READY or idx < active_idx:
                lbl.setText(f"✓  {label_text}")
                lbl.setStyleSheet("color: #34d399; font-weight: 600; font-size: 12px;")
            elif idx == active_idx:
                if state == WorkflowState.LOGIN_REQUIRED:
                    lbl.setText(f"⚠  {label_text} (Cần đăng nhập trên trình duyệt)")
                    lbl.setStyleSheet("color: #fbbf24; font-weight: bold; font-size: 12px;")
                elif state == WorkflowState.ERROR:
                    lbl.setText(f"✕  {label_text} (Thất bại)")
                    lbl.setStyleSheet("color: #f87171; font-weight: bold; font-size: 12px;")
                else:
                    lbl.setText(f"●  {label_text}…")
                    lbl.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 12px;")
            else:
                lbl.setText(f"○  {label_text}")
                lbl.setStyleSheet("color: #475569; font-size: 12px; font-weight: 400;")

        if state.is_terminal:
            self.stop_button.setEnabled(False)
            self.close_button.setEnabled(True)
            if state == WorkflowState.READY:
                self.progress_bar.setValue(100)
                self.status_banner.setStyleSheet(
                    "background: #064e3b; color: #a7f3d0; border: 1px solid #059669; "
                    "border-radius: 6px; padding: 8px 12px; font-weight: bold; font-size: 13px;"
                )
            elif state == WorkflowState.ERROR:
                self.status_banner.setStyleSheet(
                    "background: #450a0a; color: #fecaca; border: 1px solid #dc2626; "
                    "border-radius: 6px; padding: 8px 12px; font-weight: bold; font-size: 13px;"
                )

    def set_progress(self, percent: int, message: str) -> None:
        self.progress_bar.setValue(percent)
        if message:
            self.status_banner.setText(f"Trạng thái: {message}")
