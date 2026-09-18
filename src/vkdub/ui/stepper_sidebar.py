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

from vkdub.ui.theme import apply_brutalist_shadow


class StepItemWidget(QFrame):
    """Modern Neo Brutalism workflow step card with high contrast indicators."""

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
        self.setMinimumHeight(70)
        layout.setContentsMargins(12, 11, 10, 11)
        layout.setSpacing(11)


        # Status / Step Icon pill
        self.icon_label = QLabel(self._status_icon)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(34, 34)
        self.icon_label.setStyleSheet("""
            font-size: 13px;
            font-weight: 800;
            color: #0f172a;
            background-color: #ffffff;
            border: 2px solid #0f172a;
            border-radius: 17px;
        """)
        layout.addWidget(self.icon_label)

        # Content Col (Title + Summary)
        content_col = QVBoxLayout()
        content_col.setSpacing(2)
        content_col.setContentsMargins(0, 0, 0, 0)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        title_row.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel(number_title)
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 900; color: #101828;")
        title_row.addWidget(self.title_label)
        title_row.addStretch()

        # Active micro-badge
        self.active_badge = QLabel("ĐANG CHỌN")
        self.active_badge.setStyleSheet("""
            color: #0f172a;
            background-color: #b9f227;
            border: 2px solid #101828;
            padding: 1px 5px;
            border-radius: 5px;
            font-size: 8px;
            font-weight: 900;
            letter-spacing: 0.4px;
        """)
        self.active_badge.hide()
        title_row.addWidget(self.active_badge)
        content_col.addLayout(title_row)

        self.summary_label = QLabel(default_summary)
        self.summary_label.setStyleSheet("font-size: 12px; color: #667085; font-weight: 600;")
        self.summary_label.setWordWrap(True)
        content_col.addWidget(self.summary_label)

        layout.addLayout(content_col, 1)

        self.arrow_indicator = QLabel("")
        self.arrow_indicator.hide()

        self._update_style()
        apply_brutalist_shadow(self, offset=3)

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

        if icon == "✓":
            self.icon_label.setStyleSheet("""
                font-size: 13px;
                font-weight: 900;
                color: #ffffff;
                background-color: #22c55e;
                border: 2px solid #0f172a;
                border-radius: 17px;
            """)
        elif icon == "●":
            self.icon_label.setStyleSheet("""
                font-size: 12px;
                font-weight: 900;
                color: #ffffff;
                background-color: #2563eb;
                border: 2px solid #0f172a;
                border-radius: 17px;
            """)
        elif icon == "✖":
            self.icon_label.setStyleSheet("""
                font-size: 12px;
                font-weight: 900;
                color: #ffffff;
                background-color: #ef4444;
                border: 2px solid #0f172a;
                border-radius: 17px;
            """)
        elif icon_color:
            self.icon_label.setStyleSheet(f"""
                font-size: 12px;
                font-weight: 900;
                color: {icon_color};
                background-color: #ffffff;
                border: 2px solid #0f172a;
                border-radius: 17px;
            """)
        else:
            self.icon_label.setStyleSheet("""
                font-size: 11px;
                font-weight: 800;
                color: #0f172a;
                background-color: #ffffff;
                border: 2px solid #0f172a;
                border-radius: 17px;
            """)

    def _update_style(self) -> None:
        if self._is_active:
            self.setStyleSheet("""
                QFrame#stepItem {
                    background-color: #eef4ff;
                    border: 3px solid #101828;
                    border-radius: 14px;
                }
            """)
            self.title_label.setStyleSheet("font-size: 13px; font-weight: 900; color: #173fb8;")
            self.summary_label.setStyleSheet("font-size: 12px; color: #344054; font-weight: 700;")
        else:
            self.setStyleSheet("""
                QFrame#stepItem {
                    background-color: #ffffff;
                    border: 2px solid #101828;
                    border-radius: 14px;
                }
                QFrame#stepItem:hover {
                    background-color: #f8fafc;
                }
            """)
            self.title_label.setStyleSheet("font-size: 13px; font-weight: 850; color: #344054;")
            self.summary_label.setStyleSheet("font-size: 12px; color: #667085; font-weight: 600;")

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        self.clicked.emit(self.step_index)


class StepConnector(QWidget):
    """Vertical line connecting two step items — shows progress."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(13)
        self._completed = False

    def set_completed(self, completed: bool) -> None:
        self._completed = completed
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center_x = 26  # Align with icon center (12px margin + 14px half icon)
        if self._completed:
            pen = QPen(QColor("#0f172a"), 2)
            painter.setPen(pen)
            painter.drawLine(center_x, 0, center_x, self.height())
            # Little glowing green node
            painter.setBrush(QColor("#22c55e"))
            painter.setPen(QPen(QColor("#0f172a"), 1.5))
            painter.drawEllipse(center_x - 3, self.height() // 2 - 3, 6, 6)
        else:
            pen = QPen(QColor("#94a3b8"), 2, Qt.PenStyle.DashLine)
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
        (4, "05 Duyệt & Xuất", "Chờ duyệt"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("stepperSidebar")
        self.setMinimumWidth(290)
        self.setMaximumWidth(350)
        self.setStyleSheet("""
            QFrame#stepperSidebar {
                background-color: #f5f7fb;
                border-right: 3px solid #101828;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 18, 16, 14)
        layout.setSpacing(0)

        # Header section title
        header_row = QHBoxLayout()
        header_row.setSpacing(6)
        header_row.setContentsMargins(4, 0, 0, 10)

        dot = QLabel("🎬")
        dot.setStyleSheet("font-size: 12px;")
        header_row.addWidget(dot)

        header_label = QLabel("QUY TRÌNH 5 BƯỚC")
        header_label.setStyleSheet("""
            color: #0f172a;
            font-size: 12px;
            font-weight: 900;
            letter-spacing: 0.8px;
            font-family: 'Segoe UI', sans-serif;
        """)
        header_row.addWidget(header_label)

        self.sticker_badge = QLabel("PRO")
        self.sticker_badge.setStyleSheet("""
            background-color: #b9f227;
            color: #0f172a;
            border: 2px solid #101828;
            font-size: 10px;
            font-weight: 900;
            padding: 1px 5px;
            border-radius: 4px;
        """)
        header_row.addWidget(self.sticker_badge)
        self.sticker_badge.hide()
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

        # Creative sticker clapperboard card
        self.card_clapper = QFrame()
        self.card_clapper.setObjectName("studioBadgeCard")
        self.card_clapper.setStyleSheet("""
            QFrame#studioBadgeCard {
                background-color: #ffffff;
                border: 2px solid #101828;
                border-radius: 14px;
                padding: 6px;
            }
        """)
        card_layout = QVBoxLayout(self.card_clapper)
        card_layout.setContentsMargins(6, 6, 6, 6)
        card_layout.setSpacing(2)

        lbl_c1 = QLabel("🎬 KAPPAK STUDIO")
        lbl_c1.setStyleSheet("font-size: 12px; font-weight: 900; color: #101828; background: transparent;")
        lbl_c2 = QLabel("Sáng tạo video nhanh & thông minh")
        lbl_c2.setStyleSheet("font-size: 11px; color: #667085; font-weight: 600; background: transparent;")
        card_layout.addWidget(lbl_c1)
        card_layout.addWidget(lbl_c2)
        layout.addWidget(self.card_clapper)
        # Decorative only; keep the widget for compatibility but remove it from
        # the normal workflow so the progress controls stay visually dominant.
        self.card_clapper.hide()

        layout.addSpacing(10)

        # Bottom: status summary & mini progress bar
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 5)
        self.overall_progress.setValue(0)
        self.overall_progress.setFixedHeight(8)
        self.overall_progress.setTextVisible(False)
        self.overall_progress.setStyleSheet("""
            QProgressBar {
                background-color: #e2e8f0;
                border: 1.5px solid #0f172a;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #22c55e;
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.overall_progress)

        self.bottom_status = QLabel("Tiến độ: 0/5 bước hoàn tất")
        self.bottom_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bottom_status.setStyleSheet("""
            color: #0f172a;
            font-size: 10px;
            font-weight: 800;
            padding: 6px 0;
            border-top: 1.5px solid #cbd5e1;
            margin-top: 6px;
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
            self.bottom_status.setText("🎉 Đã hoàn tất tất cả các bước!")
            self.bottom_status.setStyleSheet("""
                color: #15803d; font-size: 10px; font-weight: 800;
                padding: 6px 0; border-top: 1.5px solid #0f172a; margin-top: 6px;
            """)
        elif done_count > 0:
            self.bottom_status.setText(f"Tiến độ: {done_count}/5 bước hoàn tất")
            self.bottom_status.setStyleSheet("""
                color: #0f172a; font-size: 10px; font-weight: 800;
                padding: 6px 0; border-top: 1.5px solid #cbd5e1; margin-top: 6px;
            """)
        else:
            self.bottom_status.setText("Tiến độ: 0/5 bước hoàn tất")
            self.bottom_status.setStyleSheet("""
                color: #64748b; font-size: 10px; font-weight: 700;
                padding: 6px 0; border-top: 1.5px solid #cbd5e1; margin-top: 6px;
            """)
