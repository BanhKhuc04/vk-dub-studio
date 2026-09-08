"""VK Dub Studio — Toast Notification System.

Provides sleek, floating status notifications (Success, Info, Warning, Error)
with modern glassmorphism styling, glowing accent borders, and auto-dismiss.
"""

from __future__ import annotations

from enum import Enum
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ToastType(Enum):
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ToastNotification(QFrame):
    """Single floating toast notification card."""

    THEMES = {
        ToastType.SUCCESS: {
            "border": "#10b981",
            "glow": "rgba(16, 185, 129, 0.25)",
            "icon": "✓",
            "icon_color": "#34d399",
            "icon_bg": "#064e3b",
            "title_color": "#ecfdf5",
        },
        ToastType.INFO: {
            "border": "#06b6d4",
            "glow": "rgba(6, 182, 212, 0.25)",
            "icon": "⚡",
            "icon_color": "#38bdf8",
            "icon_bg": "#164e63",
            "title_color": "#f0fdfa",
        },
        ToastType.WARNING: {
            "border": "#f59e0b",
            "glow": "rgba(245, 158, 11, 0.25)",
            "icon": "⚠",
            "icon_color": "#fbbf24",
            "icon_bg": "#78350f",
            "title_color": "#fffbeb",
        },
        ToastType.ERROR: {
            "border": "#ef4444",
            "glow": "rgba(239, 68, 68, 0.25)",
            "icon": "✖",
            "icon_color": "#f87171",
            "icon_bg": "#7f1d1d",
            "title_color": "#fef2f2",
        },
    }

    def __init__(
        self,
        title: str,
        message: str = "",
        toast_type: ToastType = ToastType.INFO,
        duration_ms: int = 4000,
        parent: QWidget | None = None,
        on_close_callback=None,
    ) -> None:
        super().__init__(parent)
        self.on_close_callback = on_close_callback
        theme = self.THEMES.get(toast_type, self.THEMES[ToastType.INFO])

        self.setFixedWidth(340)
        self.setObjectName("toastCard")
        self.setStyleSheet(f"""
            QFrame#toastCard {{
                background-color: #0f172a;
                border: 1px solid {theme['border']};
                border-left: 4px solid {theme['border']};
                border-radius: 8px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 10, 10)
        layout.setSpacing(10)

        # Icon pill
        icon_lbl = QLabel(theme["icon"])
        icon_lbl.setFixedSize(26, 26)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(f"""
            background-color: {theme['icon_bg']};
            color: {theme['icon_color']};
            font-size: 13px;
            font-weight: bold;
            border-radius: 13px;
        """)
        layout.addWidget(icon_lbl)

        # Text column (Title + Message)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"""
            color: {theme['title_color']};
            font-size: 12px;
            font-weight: 700;
            font-family: 'Segoe UI', sans-serif;
        """)
        text_col.addWidget(title_lbl)

        if message:
            msg_lbl = QLabel(message)
            msg_lbl.setWordWrap(True)
            msg_lbl.setStyleSheet("""
                color: #94a3b8;
                font-size: 11px;
                font-weight: 500;
                font-family: 'Segoe UI', sans-serif;
            """)
            text_col.addWidget(msg_lbl)

        layout.addLayout(text_col, 1)

        # Close button
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(18, 18)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #64748b;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #f8fafc;
            }
        """)
        btn_close.clicked.connect(self.dismiss)
        layout.addWidget(btn_close, 0, Qt.AlignmentFlag.AlignTop)

        # Auto-dismiss timer
        if duration_ms > 0:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.dismiss)
            self._timer.start(duration_ms)

        # Opacity effect for fade in/out
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.opacity_anim.setDuration(220)
        self.opacity_anim.setStartValue(0.0)
        self.opacity_anim.setEndValue(1.0)
        self.opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.opacity_anim.start()

    def dismiss(self) -> None:
        """Fade out and destroy toast."""
        self.opacity_anim.stop()
        self.opacity_anim.setStartValue(self.opacity_effect.opacity())
        self.opacity_anim.setEndValue(0.0)
        self.opacity_anim.finished.connect(self._on_fade_out_finished)
        self.opacity_anim.start()

    def _on_fade_out_finished(self) -> None:
        if self.on_close_callback:
            self.on_close_callback(self)
        self.deleteLater()


class ToastManager:
    """Manages stacked floating toast notifications on top of a parent window."""

    def __init__(self, parent: QWidget) -> None:
        self.parent = parent
        self.active_toasts: list[ToastNotification] = []

    def show_toast(
        self,
        title: str,
        message: str = "",
        toast_type: ToastType = ToastType.INFO,
        duration_ms: int = 4000,
    ) -> ToastNotification:
        """Display a new toast notification."""
        toast = ToastNotification(
            title=title,
            message=message,
            toast_type=toast_type,
            duration_ms=duration_ms,
            parent=self.parent,
            on_close_callback=self._remove_toast,
        )
        self.active_toasts.append(toast)
        toast.show()
        self.reposition()
        return toast

    def _remove_toast(self, toast: ToastNotification) -> None:
        if toast in self.active_toasts:
            self.active_toasts.remove(toast)
            self.reposition()

    def reposition(self) -> None:
        """Position all active toasts in the top-right corner of the parent."""
        if not self.parent:
            return
        parent_width = self.parent.width()
        margin_right = 24
        margin_top = 58
        spacing = 10

        y_offset = margin_top
        for toast in self.active_toasts:
            toast.adjustSize()
            x = parent_width - toast.width() - margin_right
            toast.move(x, y_offset)
            toast.raise_()
            y_offset += max(toast.height(), 46) + spacing
