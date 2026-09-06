from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from vkdub.providers.tts_provider import HealthResult


class HealthBanner(QFrame):
    action_requested = Signal(str)
    dismissed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("healthBanner")
        self.setStyleSheet(
            "QFrame#healthBanner { "
            "  background-color: #2a1f10; "
            "  border: 1px solid #d97706; "
            "  border-radius: 6px; "
            "  margin: 4px 10px; "
            "}"
        )
        self._current_action_id: str | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        self.icon_label = QLabel("⚠️")
        self.icon_label.setStyleSheet("font-size: 18px;")
        layout.addWidget(self.icon_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-weight: bold; color: #fbbf24; font-size: 13px;")
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        text_col.addWidget(self.title_label)
        text_col.addWidget(self.message_label)
        layout.addLayout(text_col, 1)

        self.action_button = QPushButton()
        self.action_button.setStyleSheet(
            "QPushButton { "
            "  background-color: #d97706; "
            "  color: #ffffff; "
            "  font-weight: bold; "
            "  border-radius: 4px; "
            "  padding: 6px 14px; "
            "  font-size: 12px; "
            "} "
            "QPushButton:hover { background-color: #b45309; }"
        )
        self.action_button.clicked.connect(self._on_action_clicked)
        layout.addWidget(self.action_button)

        self.close_button = QPushButton("✕")
        self.close_button.setStyleSheet(
            "QPushButton { "
            "  background: transparent; "
            "  color: #94a3b8; "
            "  font-size: 14px; "
            "  font-weight: bold; "
            "  border: none; "
            "  padding: 4px 8px; "
            "} "
            "QPushButton:hover { color: #f1f5f9; }"
        )
        self.close_button.clicked.connect(self._on_dismiss)
        layout.addWidget(self.close_button)

        self.hide()

    def set_result(self, result: HealthResult) -> None:
        self._current_action_id = result.action_id
        self.title_label.setText(result.title)
        self.message_label.setText(result.message)
        if result.action_label and result.action_id:
            self.action_button.setText(result.action_label)
            self.action_button.show()
        else:
            self.action_button.hide()
        self.show()

    def _on_action_clicked(self) -> None:
        if self._current_action_id:
            self.action_requested.emit(self._current_action_id)

    def _on_dismiss(self) -> None:
        self.hide()
        self.dismissed.emit()
