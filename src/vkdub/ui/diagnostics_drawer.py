"""VK Dub Studio — Cyber Terminal & Diagnostics Console v2.0.

Provides real-time system monitoring, color-coded syntax logs,
filtering tabs, and quick diagnostic actions in a modern pro-studio drawer.
"""

from __future__ import annotations

import re
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class _FilterTab(QPushButton):
    """Individual filter tab button for log categories."""

    def __init__(self, label: str, category: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.category = category
        self._count = 0
        self._active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(24)
        self._refresh_style()

    def set_active(self, active: bool) -> None:
        self._active = active
        self._refresh_style()

    def set_count(self, count: int) -> None:
        self._count = count
        if self.category == "ALL":
            self.setText(f"Tất cả ({count})")
        elif count > 0:
            self.setText(f"{self._base_text()} ({count})")
        else:
            self.setText(self._base_text())

    def _base_text(self) -> str:
        return {"ALL": "Tất cả", "SUCCESS": "✓ Thành công", "ERROR": "✖ Lỗi",
                "WARN": "⚠ Cảnh báo", "BRIDGE": "🔗 Bridge"}.get(self.category, self.category)

    def _refresh_style(self) -> None:
        if self._active:
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #06b6d4);
                    color: #ffffff;
                    border: 1px solid #38bdf8;
                    border-radius: 4px;
                    padding: 2px 12px;
                    font-size: 10px;
                    font-weight: 700;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #0c121e;
                    color: #8b9bb4;
                    border: 1px solid #1a2538;
                    border-radius: 4px;
                    padding: 2px 12px;
                    font-size: 10px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #121c2d;
                    color: #38bdf8;
                    border-color: #0284c7;
                }
            """)


class DiagnosticsDrawer(QFrame):
    """Collapsible cyber terminal console hosting real-time activity logs."""

    open_log_viewer_requested = Signal()

    CATEGORIES = {
        "ALL": lambda _: True,
        "SUCCESS": lambda l: any(w in l.lower() for w in ("thành công", "hoàn tất", "🎉", "✓", "ready", "usable", "pass")),
        "ERROR": lambda l: any(w in l.lower() for w in ("lỗi", "thất bại", "failed", "error", "exception", "✖")),
        "WARN": lambda l: any(w in l.lower() for w in ("cảnh báo", "warning", "warn", "chờ", "waiting", "⏳")),
        "BRIDGE": lambda l: any(w in l.lower() for w in ("edge", "bridge", "browser", "extension", "chatgpt", "vbee")),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("diagnosticsDrawer")
        self.setStyleSheet("""
            QFrame#diagnosticsDrawer {
                background-color: #050810;
                border-top: 1px solid #131b2a;
            }
        """)

        self._is_expanded = False
        self._all_logs: list[str] = []
        self._current_filter: str = "ALL"

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------------------------------------------------
        # Header bar (always visible)
        # ---------------------------------------------------------
        self.header_bar = QFrame()
        self.header_bar.setFixedHeight(36)
        self.header_bar.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #060a12, stop:0.5 #0d1524, stop:1 #080d16);
                border-bottom: 1px solid #162438;
            }
        """)
        self.header_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(14, 0, 14, 0)
        header_layout.setSpacing(10)

        # Live Indicator & Title
        self.toggle_btn = QLabel("▶  ⚡ LIVE TERMINAL")
        self.toggle_btn.setStyleSheet("""
            color: #475569;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            font-family: 'Segoe UI', sans-serif;
        """)
        header_layout.addWidget(self.toggle_btn)

        # Status badge (Pill)
        self.live_pill = QLabel("● READY")
        self.live_pill.setStyleSheet("""
            color: #06b6d4;
            background-color: #082f49;
            border: 1px solid #0284c7;
            padding: 1px 8px;
            border-radius: 4px;
            font-size: 9px;
            font-weight: bold;
            letter-spacing: 0.5px;
        """)
        header_layout.addWidget(self.live_pill)

        # Single line preview of the latest activity
        self.preview_lbl = QLabel("")
        self.preview_lbl.setStyleSheet("""
            color: #475569;
            font-size: 11px;
            font-family: 'Consolas', 'JetBrains Mono', monospace;
        """)
        header_layout.addWidget(self.preview_lbl, 1)

        # Log count badge
        self.log_count_lbl = QLabel("0")
        self.log_count_lbl.setStyleSheet("""
            color: #64748b;
            background-color: #0c111c;
            border: 1px solid #1a2436;
            padding: 0px 6px;
            border-radius: 3px;
            font-size: 9px;
            font-weight: bold;
        """)
        header_layout.addWidget(self.log_count_lbl)

        # Quick Actions
        self.btn_clear = QPushButton("Xóa")
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #0c111c; color: #64748b; border: 1px solid #1a2436;
                border-radius: 4px; padding: 2px 10px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background-color: #131b2c; color: #94a3b8; border-color: #24334f; }
        """)
        self.btn_clear.setToolTip("Xóa trắng nhật ký màn hình")
        self.btn_clear.clicked.connect(self.clear_logs)
        header_layout.addWidget(self.btn_clear)

        self.btn_copy = QPushButton("Sao chép")
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #0c111c; color: #64748b; border: 1px solid #1a2436;
                border-radius: 4px; padding: 2px 10px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background-color: #131b2c; color: #94a3b8; border-color: #24334f; }
        """)
        self.btn_copy.setToolTip("Sao chép toàn bộ nhật ký vào clipboard")
        self.btn_copy.clicked.connect(self.copy_logs)
        header_layout.addWidget(self.btn_copy)

        self.btn_viewer = QPushButton("F12 Toàn màn hình")
        self.btn_viewer.setStyleSheet("""
            QPushButton {
                background-color: #0c111c; color: #64748b; border: 1px solid #1a2436;
                border-radius: 4px; padding: 2px 10px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background-color: #131b2c; color: #38bdf8; border-color: #0284c7; }
        """)
        self.btn_viewer.setToolTip("Mở cửa sổ chi tiết log hệ thống (F12)")
        self.btn_viewer.clicked.connect(self.open_log_viewer_requested.emit)
        header_layout.addWidget(self.btn_viewer)

        self.header_bar.mousePressEvent = lambda _: self.toggle_drawer()
        main_layout.addWidget(self.header_bar)

        # ---------------------------------------------------------
        # Body Container (Expanded Console View)
        # ---------------------------------------------------------
        self.body_container = QWidget()
        body_layout = QVBoxLayout(self.body_container)
        body_layout.setContentsMargins(10, 6, 10, 6)
        body_layout.setSpacing(4)

        # Filter tab bar
        filter_row = QHBoxLayout()
        filter_row.setSpacing(4)
        filter_row.setContentsMargins(0, 0, 0, 4)

        self._filter_tabs: dict[str, _FilterTab] = {}
        for cat_key, cat_label in [
            ("ALL", "Tất cả"),
            ("SUCCESS", "✓ Thành công"),
            ("ERROR", "✖ Lỗi"),
            ("WARN", "⚠ Cảnh báo"),
            ("BRIDGE", "🔗 Bridge"),
        ]:
            tab = _FilterTab(cat_label, cat_key)
            tab.clicked.connect(lambda checked=False, k=cat_key: self._set_filter(k))
            self._filter_tabs[cat_key] = tab
            filter_row.addWidget(tab)

        filter_row.addStretch(1)
        body_layout.addLayout(filter_row)

        self._filter_tabs["ALL"].set_active(True)

        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumBlockCount(1000)
        self.logs.setFixedHeight(180)
        self.logs.setStyleSheet("""
            QPlainTextEdit {
                font-family: 'Consolas', 'JetBrains Mono', 'Courier New', monospace;
                font-size: 11px;
                background-color: #040710;
                color: #94a3b8;
                border: 1px solid #131b2a;
                border-radius: 6px;
                padding: 6px 10px;
                line-height: 1.4;
            }
        """)
        body_layout.addWidget(self.logs)

        main_layout.addWidget(self.body_container)
        self.body_container.hide()

    def toggle_drawer(self) -> None:
        self.set_expanded(not self._is_expanded)

    def set_expanded(self, expanded: bool) -> None:
        self._is_expanded = expanded
        if expanded:
            self.body_container.show()
            self.toggle_btn.setText("▼  ⚡ LIVE TERMINAL")
            self.toggle_btn.setStyleSheet("""
                color: #38bdf8;
                font-size: 11px;
                font-weight: 800;
                letter-spacing: 0.5px;
            """)
            self.live_pill.setText("● ACTIVE")
            self.live_pill.setStyleSheet("""
                color: #34d399; background-color: #064e3b;
                border: 1px solid #059669; padding: 1px 8px;
                border-radius: 4px; font-size: 9px; font-weight: bold;
                letter-spacing: 0.5px;
            """)
        else:
            self.body_container.hide()
            self.toggle_btn.setText("▶  ⚡ LIVE TERMINAL")
            self.toggle_btn.setStyleSheet("""
                color: #475569;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            """)
            self.live_pill.setText("● READY")
            self.live_pill.setStyleSheet("""
                color: #06b6d4; background-color: #082f49;
                border: 1px solid #0284c7; padding: 1px 8px;
                border-radius: 4px; font-size: 9px; font-weight: bold;
                letter-spacing: 0.5px;
            """)

    def append_log(self, message: str) -> None:
        """Append log with rich HTML syntax coloring."""
        self._all_logs.append(message)
        self._update_filter_counts()

        # Only append if passes current filter
        if self._passes_filter(message):
            formatted_html = self._colorize_log_line(message)
            self.logs.appendHtml(formatted_html)
            self.logs.moveCursor(QTextCursor.MoveOperation.End)
            self.logs.ensureCursorVisible()

        # Update preview label in header bar
        clean_msg = message.strip()
        self.preview_lbl.setText(f"— {clean_msg[:75]}")
        self.log_count_lbl.setText(str(len(self._all_logs)))

    def _passes_filter(self, message: str) -> bool:
        checker = self.CATEGORIES.get(self._current_filter)
        return checker(message) if checker else True

    def _set_filter(self, category: str) -> None:
        self._current_filter = category
        for key, tab in self._filter_tabs.items():
            tab.set_active(key == category)

        # Re-render logs matching filter
        self.logs.clear()
        for msg in self._all_logs:
            if self._passes_filter(msg):
                self.logs.appendHtml(self._colorize_log_line(msg))
        self.logs.moveCursor(QTextCursor.MoveOperation.End)
        self.logs.ensureCursorVisible()

    def _update_filter_counts(self) -> None:
        for key, tab in self._filter_tabs.items():
            checker = self.CATEGORIES.get(key)
            if checker:
                count = sum(1 for m in self._all_logs if checker(m))
                tab.set_count(count)

    def _colorize_log_line(self, line: str) -> str:
        """Transform a raw log line into styled HTML with syntax highlights."""
        # Match time format: "10:15:20  +00:15  Message..."
        m = re.match(r"^(\d{2}:\d{2}:\d{2})\s+(\+\d+:\d+)\s+(.*)$", line)
        if m:
            t_str, elapsed_str, body = m.group(1), m.group(2), m.group(3)
            time_part = f"<span style='color: #0ea5e9; font-weight: 600;'>{t_str}</span> <span style='color: #334155;'>{elapsed_str}</span>"
        else:
            time_part = "<span style='color: #0ea5e9;'>●</span>"
            body = line

        # Colorize keywords
        lowered = body.lower()
        if any(w in lowered for w in ("thành công", "hoàn tất", "🎉", "✓", "ready", "usable")):
            body_colored = f"<span style='color: #34d399; font-weight: 600;'>{body}</span>"
        elif any(w in lowered for w in ("lỗi", "thất bại", "failed", "error", "exception", "✖", "redact")):
            body_colored = f"<span style='color: #f87171; font-weight: bold;'>{body}</span>"
        elif any(w in lowered for w in ("cảnh báo", "warning", "warn", "chờ", "waiting", "⏳")):
            body_colored = f"<span style='color: #fbbf24; font-weight: 600;'>{body}</span>"
        elif any(w in lowered for w in ("vbee", "voice", "giọng", "dubbing", "audio")):
            body_colored = f"<span style='color: #c084fc;'>{body}</span>"
        elif any(w in lowered for w in ("chatgpt", "translate", "dịch")):
            body_colored = f"<span style='color: #60a5fa;'>{body}</span>"
        elif any(w in lowered for w in ("edge", "bridge", "browser", "extension")):
            body_colored = f"<span style='color: #06b6d4;'>{body}</span>"
        else:
            body_colored = f"<span style='color: #94a3b8;'>{body}</span>"

        return f"<div style='margin-bottom: 2px;'>{time_part} &nbsp;{body_colored}</div>"

    @property
    def is_expanded(self) -> bool:
        return self._is_expanded

    @property
    def header_btn(self) -> QLabel:
        return self.toggle_btn

    @property
    def content_frame(self) -> QWidget:
        return self.body_container

    @property
    def log_edit(self) -> QPlainTextEdit:
        return self.logs

    def clear_logs(self) -> None:
        self.logs.clear()
        self._all_logs.clear()
        self.preview_lbl.setText("")
        self.log_count_lbl.setText("0")
        self._update_filter_counts()

    def copy_logs(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.logs.toPlainText())
