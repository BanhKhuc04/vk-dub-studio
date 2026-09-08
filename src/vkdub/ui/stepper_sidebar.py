"""VK Dub Studio — Cyber Obsidian Stepper Sidebar v2.0.

Pro Studio 5-step workflow navigation:
- Glowing active cards with gradient left accent borders
- Vertical progress connector lines between steps
- Status pills with radiant completion checkmarks
- Clean modern typography with high contrast
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class StepItemWidget(QFrame):
    """Modern workflow step card with glowing state indicators."""

    clicked = Signal(int)

    def __init__(self, step_index: int, number_title: str, default_summary: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.step_index = step_index
        self.setObjectName("stepItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._is_active = False
        self._status_icon = "○"
        self._summary_text = default_summary
        self._is_complete = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Status / Step Icon pill
        self.icon_label = QLabel(self._status_icon)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(28, 28)
        self.icon_label.setStyleSheet("""
            font-size: 11px;
            font-weight: 800;
            color: #475569;
            background-color: #0c111c;
            border: 2px solid #1e293b;
            border-radius: 14px;
        """)
        layout.addWidget(self.icon_label)

        # Content Col (Title + Summary)
        content_col = QVBoxLayout()
        content_col.setSpacing(2)
        content_col.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel(number_title)
        self.title_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #cbd5e1;")
        content_col.addWidget(self.title_label)

        self.summary_label = QLabel(default_summary)
        self.summary_label.setStyleSheet("font-size: 11px; color: #64748b;")
        self.summary_label.setWordWrap(True)
        content_col.addWidget(self.summary_label)

        layout.addLayout(content_col, 1)

        # Active micro-badge
        self.active_badge = QLabel("CURRENT")
        self.active_badge.setStyleSheet("""
            color: #38bdf8;
            background-color: rgba(2, 132, 199, 0.20);
            border: 1px solid #0284c7;
            padding: 1px 4px;
            border-radius: 3px;
            font-size: 8px;
            font-weight: 800;
            letter-spacing: 0.5px;
        """)
        self.active_badge.hide()
        layout.addWidget(self.active_badge)

        self.arrow_indicator = QLabel("")
        self.arrow_indicator.hide()

        self._update_style()

    def set_active(self, active: bool) -> None:
        self._is_active = active
        self.active_badge.setVisible(active)
        self._update_style()

    def set_state(self, icon: str, summary: str | None = None, icon_color: str | None = None) -> None:
        self._status_icon = icon
        self.icon_label.setText(icon)
        self._is_complete = icon == "✓"
        if summary is not None:
            self._summary_text = summary
            self.summary_label.setText(summary)

        if icon_color:
            self.icon_label.setStyleSheet(f"""
                font-size: 12px;
                font-weight: bold;
                color: {icon_color};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #101726, stop:1 #0c111c);
                border: 2px solid {icon_color};
                border-radius: 14px;
            """)
        elif icon == "✓":
            self.icon_label.setStyleSheet("""
                font-size: 13px;
                font-weight: bold;
                color: #34d399;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0d2a1f, stop:1 #064e3b);
                border: 2px solid #059669;
                border-radius: 14px;
            """)
        elif icon == "●":
            self.icon_label.setStyleSheet("""
                font-size: 12px;
                font-weight: bold;
                color: #38bdf8;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0c2544, stop:1 #082f49);
                border: 2px solid #0284c7;
                border-radius: 14px;
            """)
        elif icon == "✖":
            self.icon_label.setStyleSheet("""
                font-size: 12px;
                font-weight: bold;
                color: #f87171;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2a0a0a, stop:1 #450a0a);
                border: 2px solid #dc2626;
                border-radius: 14px;
            """)
        else:
            self.icon_label.setStyleSheet("""
                font-size: 11px;
                font-weight: 800;
                color: #475569;
                background-color: #0c111c;
                border: 2px solid #1e293b;
                border-radius: 14px;
            """)

    def _update_style(self) -> None:
        if self._is_active:
            self.setStyleSheet("""
                QFrame#stepItem {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #101d33, stop:0.4 #0d1627, stop:1 #090f1a);
                    border: 1px solid #0284c7;
                    border-left: 3.5px solid #06b6d4;
                    border-radius: 8px;
                }
            """)
            self.title_label.setStyleSheet("font-size: 12px; font-weight: 800; color: #f8fafc;")
            self.summary_label.setStyleSheet("font-size: 11px; color: #38bdf8; font-weight: 600;")
        else:
            self.setStyleSheet("""
                QFrame#stepItem {
                    background-color: #080d17;
                    border: 1px solid #141f32;
                    border-left: 3.5px solid transparent;
                    border-radius: 8px;
                }
                QFrame#stepItem:hover {
                    background-color: #0e1626;
                    border-color: #1e2f4a;
                    border-left: 3.5px solid #243b5e;
                }
            """)
            self.title_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #cbd5e1;")
            self.summary_label.setStyleSheet("font-size: 11px; color: #64748b;")

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        self.clicked.emit(self.step_index)


class StepConnector(QWidget):
    """Vertical line connecting two step items — shows progress."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(10)
        self._completed = False

    def set_completed(self, completed: bool) -> None:
        self._completed = completed
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center_x = 26  # Align with icon center (12px margin + 14px half icon)
        if self._completed:
            pen = QPen(QColor("#059669"), 2)
            painter.setPen(pen)
            painter.drawLine(center_x, 0, center_x, self.height())
            # Little glowing node
            painter.setBrush(QColor("#34d399"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center_x - 2, self.height() // 2 - 2, 4, 4)
        else:
            pen = QPen(QColor("#1e293b"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(center_x, 0, center_x, self.height())
        painter.end()


class WorkflowStepper(QFrame):
    """Sidebar containing the 5 workflow stages with progress connectors."""

    step_selected = Signal(int)

    STEPS_CONFIG = [
        (0, "01 Source Video", "Chưa chọn video"),
        (1, "02 Voice & AI", "Ngọc Huyền · 1.1x"),
        (2, "03 Blur Regions", "Chưa tạo vùng"),
        (3, "04 Automation", "Sẵn sàng chạy"),
        (4, "05 Review & Export", "Chờ duyệt"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("stepperSidebar")
        self.setMinimumWidth(250)
        self.setMaximumWidth(290)
        self.setStyleSheet("""
            QFrame#stepperSidebar {
                background-color: #050810;
                border-right: 1px solid #131b2a;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(0)

        # Header section title
        header_row = QHBoxLayout()
        header_row.setSpacing(6)
        header_row.setContentsMargins(4, 0, 0, 12)

        dot = QLabel("●")
        dot.setStyleSheet("color: #06b6d4; font-size: 9px;")
        header_row.addWidget(dot)

        header_label = QLabel("WORKFLOW PIPELINE")
        header_label.setStyleSheet("""
            color: #475569;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1.2px;
            font-family: 'Segoe UI', sans-serif;
        """)
        header_row.addWidget(header_label)
        header_row.addStretch(1)
        layout.addLayout(header_row)

        # 5 Step Item Cards with Connectors
        self.step_items: list[StepItemWidget] = []
        self.connectors: list[StepConnector] = []

        for i, (idx, title, default_sub) in enumerate(self.STEPS_CONFIG):
            item = StepItemWidget(idx, title, default_sub)
            item.clicked.connect(self._on_step_clicked)
            self.step_items.append(item)
            layout.addWidget(item)

            # Add connector between steps (not after last)
            if i < len(self.STEPS_CONFIG) - 1:
                connector = StepConnector()
                self.connectors.append(connector)
                layout.addWidget(connector)

        layout.addStretch(1)

        # Bottom: status summary & mini progress bar
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 5)
        self.overall_progress.setValue(0)
        self.overall_progress.setFixedHeight(3)
        self.overall_progress.setTextVisible(False)
        self.overall_progress.setStyleSheet("""
            QProgressBar {
                background-color: #0c111c;
                border: none;
                border-radius: 1px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #06b6d4);
                border-radius: 1px;
            }
        """)
        layout.addWidget(self.overall_progress)

        self.bottom_status = QLabel("Quy trình: 0/5 bước")
        self.bottom_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bottom_status.setStyleSheet("""
            color: #475569;
            font-size: 10px;
            font-weight: 600;
            padding: 6px 0;
            border-top: 1px solid #131b2a;
        """)
        layout.addWidget(self.bottom_status)

        self._current_step = 0
        self.step_items[0].set_active(True)

    def _on_step_clicked(self, step_index: int) -> None:
        self.set_current_step(step_index)
        self.step_selected.emit(step_index)

    def set_current_step(self, step_index: int) -> None:
        if 0 <= step_index < len(self.step_items):
            self._current_step = step_index
            for i, item in enumerate(self.step_items):
                item.set_active(i == step_index)

    @property
    def current_step(self) -> int:
        return self._current_step

    def update_step_summary(self, step_index: int, icon: str, summary: str, icon_color: str | None = None) -> None:
        if 0 <= step_index < len(self.step_items):
            self.step_items[step_index].set_state(icon, summary, icon_color)

            # Update connectors based on step completion
            self._update_connectors()
            self._update_bottom_status()

    def _update_connectors(self) -> None:
        """Update connector lines based on step completion states."""
        for i, connector in enumerate(self.connectors):
            step = self.step_items[i]
            connector.set_completed(step._is_complete)

    def _update_bottom_status(self) -> None:
        """Update the bottom summary showing overall progress."""
        done_count = sum(1 for s in self.step_items if s._is_complete)
        self.overall_progress.setValue(done_count)
        if done_count == 5:
            self.bottom_status.setText("🎉 Hoàn tất tất cả bước!")
            self.bottom_status.setStyleSheet("""
                color: #34d399; font-size: 10px; font-weight: 700;
                padding: 6px 0; border-top: 1px solid #059669;
            """)
        elif done_count > 0:
            self.bottom_status.setText(f"Quy trình: {done_count}/5 bước hoàn tất")
            self.bottom_status.setStyleSheet("""
                color: #38bdf8; font-size: 10px; font-weight: 600;
                padding: 6px 0; border-top: 1px solid #131b2a;
            """)
        else:
            self.bottom_status.setText("Quy trình: 0/5 bước")
            self.bottom_status.setStyleSheet("""
                color: #475569; font-size: 10px; font-weight: 600;
                padding: 6px 0; border-top: 1px solid #131b2a;
            """)
