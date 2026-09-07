"""VK Dub Studio — Browser Bridge Status Widget.

Displays real-time connection and authentication state for Microsoft Edge,
ChatGPT, and Vbee without launching secondary browsers.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vkdub.bridge.protocol import BridgeStatus


class BrowserBridgeWidget(QFrame):
  """UI widget displaying live status of the Edge Browser Bridge."""

  open_browser_requested = Signal()
  refresh_requested = Signal()

  def __init__(self, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self.setObjectName("browserBridgeWidget")
    self.setStyleSheet("""
            QFrame#browserBridgeWidget {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 8px 10px;
                margin: 2px 0;
            }
            QLabel.sectionTitle {
                font-size: 11px;
                font-weight: bold;
                color: #8b949e;
                letter-spacing: 0.5px;
            }
            QLabel.statusBadge {
                font-size: 12px;
                font-weight: 500;
                padding: 2px 0;
            }
            QPushButton.bridgeBtn {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton.bridgeBtn:hover {
                background-color: #30363d;
                color: #ffffff;
            }
        """)

    layout = QVBoxLayout(self)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(6)

    # Header Row
    header_row = QHBoxLayout()
    header_title = QLabel("CẦU NỐI TRÌNH DUYỆT (H6 BRIDGE)")
    header_title.setProperty("class", "sectionTitle")
    header_title.setStyleSheet(
        "font-size: 11px; font-weight: bold; color: #58a6ff;"
    )
    header_row.addWidget(header_title, 1)

    self.btn_refresh = QPushButton("🔄 Làm mới")
    self.btn_refresh.setProperty("class", "bridgeBtn")
    self.btn_refresh.setToolTip(
        "Kiểm tra trạng thái kết nối và phiên đăng nhập hiện tại trong Edge"
    )
    self.btn_refresh.clicked.connect(self.refresh_requested.emit)
    header_row.addWidget(self.btn_refresh)
    layout.addLayout(header_row)

    # Status Rows Container
    status_box = QVBoxLayout()
    status_box.setSpacing(3)

    # 1. Edge Connection
    self.lbl_browser = QLabel("○ Trình duyệt Edge: Đang chờ mở...")
    self.lbl_browser.setStyleSheet("color: #d29922; font-size: 11px;")
    status_box.addWidget(self.lbl_browser)

    # 2. ChatGPT Auth
    self.lbl_chatgpt = QLabel("○ ChatGPT: Chưa kiểm tra")
    self.lbl_chatgpt.setStyleSheet("color: #8b949e; font-size: 11px;")
    status_box.addWidget(self.lbl_chatgpt)

    # 3. Vbee Auth
    self.lbl_vbee = QLabel("○ Vbee Công ty: Chưa kiểm tra")
    self.lbl_vbee.setStyleSheet("color: #8b949e; font-size: 11px;")
    status_box.addWidget(self.lbl_vbee)

    layout.addLayout(status_box)

    # Action Row
    action_row = QHBoxLayout()
    self.btn_open_browser = QPushButton("🌐 Mở Microsoft Edge")
    self.btn_open_browser.setProperty("class", "bridgeBtn")
    self.btn_open_browser.setStyleSheet(
        "background-color: #1f6feb; color: white; font-weight: bold;"
    )
    self.btn_open_browser.setToolTip(
        "Mở trình duyệt Microsoft Edge bình thường của bạn"
    )
    self.btn_open_browser.clicked.connect(self.open_browser_requested.emit)
    action_row.addWidget(self.btn_open_browser)
    layout.addLayout(action_row)

  def update_status(self, status: BridgeStatus) -> None:
    """Update UI labels based on live status report."""
    if status.browser_connected:
      b_name = status.browser_name or "Microsoft Edge"
      self.lbl_browser.setText(f"● {b_name}: Đã kết nối")
      self.lbl_browser.setStyleSheet(
          "color: #3fb950; font-weight: bold; font-size: 11px;"
      )
      self.btn_open_browser.setText("🌐 Mở Tab Mới Edge")
      self.btn_open_browser.setStyleSheet(
          "background-color: #21262d; color: #c9d1d9;"
      )
    else:
      self.lbl_browser.setText("○ Trình duyệt Edge: Đang chờ mở...")
      self.lbl_browser.setStyleSheet(
          "color: #d29922; font-weight: normal; font-size: 11px;"
      )
      self.btn_open_browser.setText("🌐 Mở Microsoft Edge")
      self.btn_open_browser.setStyleSheet(
          "background-color: #1f6feb; color: white; font-weight: bold;"
      )

    # ChatGPT status
    if not status.browser_connected:
      self.lbl_chatgpt.setText("○ ChatGPT: Chờ kết nối trình duyệt")
      self.lbl_chatgpt.setStyleSheet("color: #8b949e; font-size: 11px;")
    elif status.chatgpt_logged_in:
      tab_info = f" ({status.chatgpt_tabs} tab)" if status.chatgpt_tabs > 0 else ""
      self.lbl_chatgpt.setText(f"● ChatGPT: Đã đăng nhập{tab_info}")
      self.lbl_chatgpt.setStyleSheet(
          "color: #3fb950; font-weight: 500; font-size: 11px;"
      )
    else:
      self.lbl_chatgpt.setText("▲ ChatGPT: Chưa đăng nhập trong Edge")
      self.lbl_chatgpt.setStyleSheet(
          "color: #f85149; font-weight: bold; font-size: 11px;"
      )

    # Vbee status
    if not status.browser_connected:
      self.lbl_vbee.setText("○ Vbee: Chờ kết nối trình duyệt")
      self.lbl_vbee.setStyleSheet("color: #8b949e; font-size: 11px;")
    elif status.vbee_logged_in:
      tab_info = f" ({status.vbee_tabs} tab)" if status.vbee_tabs > 0 else ""
      self.lbl_vbee.setText(f"● Vbee Công ty: Đã đăng nhập{tab_info}")
      self.lbl_vbee.setStyleSheet(
          "color: #3fb950; font-weight: 500; font-size: 11px;"
      )
    else:
      self.lbl_vbee.setText("▲ Vbee Công ty: Chưa đăng nhập trong Edge")
      self.lbl_vbee.setStyleSheet(
          "color: #f85149; font-weight: bold; font-size: 11px;"
      )
