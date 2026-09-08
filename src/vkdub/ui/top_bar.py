"""VK Dub Studio — Cyber Obsidian Top Bar.

Pro Studio header containing:
- Branding (VK Dub Studio · PRO STUDIO)
- Active project filename (with dirty indicator)
- Browser bridge live status pills (Edge, ChatGPT, Vbee)
- Quick Save & Open actions + Settings button
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import time

from vkdub.bridge.protocol import BridgeStatus
from vkdub.version import APP_CREDIT, __version__


class TopBar(QFrame):
    """Clean, high-tech creative suite top bar."""

    new_requested = Signal()
    settings_requested = Signal()
    save_requested = Signal()
    open_requested = Signal()
    open_edge_requested = Signal()
    refresh_bridge_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setFixedHeight(50)
        self.setStyleSheet("""
            QFrame#topBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #060a10, stop:1 #080d16);
                border-bottom: 1px solid #131b2a;
            }
            QPushButton.topBtn {
                background-color: #0c111c;
                color: #94a3b8;
                border: 1px solid #1a2436;
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton.topBtn:hover {
                background-color: #131b2c;
                color: #38bdf8;
                border-color: #0284c7;
            }
            QPushButton.topBtn:pressed {
                background-color: #0a0e16;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(12)

        # ---------------------------------------------------------
        # 1. Left: Branding & Project name
        # ---------------------------------------------------------
        brand_box = QHBoxLayout()
        brand_box.setSpacing(8)

        self.lbl_title = QLabel("VK Dub Studio")
        self.lbl_title.setStyleSheet("""
            font-size: 14px;
            font-weight: 900;
            color: #f1f5f9;
            letter-spacing: 1px;
            font-family: 'Segoe UI', sans-serif;
        """)
        brand_box.addWidget(self.lbl_title)

        # Pro badge
        self.badge_pro = QLabel("PRO STUDIO")
        self.badge_pro.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6);
            color: #ffffff;
            font-size: 8px;
            font-weight: 800;
            padding: 2px 8px;
            border-radius: 3px;
            letter-spacing: 1px;
        """)
        brand_box.addWidget(self.badge_pro)

        self.lbl_version = QLabel(f"v{__version__}")
        self.lbl_version.setStyleSheet("font-size: 10px; color: #475569; font-weight: 600;")
        brand_box.addWidget(self.lbl_version)

        sep = QLabel("│")
        sep.setStyleSheet("color: #1a2436; font-size: 12px;")
        brand_box.addWidget(sep)

        # Nút Project mới
        self.btn_new = QPushButton("✨ Project mới")
        self.btn_new.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b45309, stop:1 #d97706);
                color: #ffffff;
                border: 1px solid #f59e0b;
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #f59e0b);
                border-color: #fde68a;
            }
            QPushButton:pressed {
                background-color: #92400e;
            }
        """)
        self.btn_new.setToolTip("Khởi tạo dự án mới (Ctrl+N)")
        self.btn_new.clicked.connect(self.new_requested.emit)
        brand_box.addWidget(self.btn_new)

        self.lbl_project_name = QLabel("📄 Project mới")
        self.lbl_project_name.setStyleSheet("""
            font-size: 11px;
            font-weight: 600;
            color: #38bdf8;
            background-color: #0c1424;
            border: 1px solid #16263f;
            padding: 3px 8px;
            border-radius: 4px;
        """)
        brand_box.addWidget(self.lbl_project_name)

        # Quick Save & Open buttons
        self.btn_save = QPushButton("💾 Lưu")
        self.btn_save.setProperty("class", "topBtn")
        self.btn_save.setToolTip("Lưu dự án hiện tại (Ctrl+S)")
        self.btn_save.clicked.connect(self.save_requested.emit)
        brand_box.addWidget(self.btn_save)

        self.btn_open = QPushButton("📂 Mở")
        self.btn_open.setProperty("class", "topBtn")
        self.btn_open.setToolTip("Mở dự án .vkdub đã lưu (Ctrl+O)")
        self.btn_open.clicked.connect(self.open_requested.emit)
        brand_box.addWidget(self.btn_open)

        layout.addLayout(brand_box)
        layout.addStretch(1)

        # Center branding credit with special romantic glow effect
        self.credit_card = QFrame()
        self.credit_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(225, 29, 72, 0.10), stop:0.5 rgba(236, 72, 153, 0.16), stop:1 rgba(147, 51, 234, 0.10));
                border: 1px solid qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f43f5e, stop:0.5 #ec4899, stop:1 #a855f7);
                border-radius: 7px;
                padding: 1px 12px;
            }
        """)
        credit_layout = QVBoxLayout(self.credit_card)
        credit_layout.setContentsMargins(8, 2, 8, 2)
        credit_layout.setSpacing(1)

        self.lbl_credit_author = QLabel("✨ Sản phẩm tạo bởi <b style='color: #67e8f9;'>vanhkhuc.dev</b>")
        self.lbl_credit_author.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_credit_author.setStyleSheet("font-size: 9px; color: #94a3b8; font-weight: 600; background: transparent;")
        credit_layout.addWidget(self.lbl_credit_author)

        self.lbl_credit = QLabel("💖 Dành tặng em bé <b style='color: #ffe4e6;'>Trang Vũ</b> &lt;3")
        self.lbl_credit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_credit.setStyleSheet("font-size: 10px; color: #f472b6; font-weight: 700; background: transparent;")
        credit_layout.addWidget(self.lbl_credit)

        layout.addWidget(self.credit_card)
        layout.addStretch(1)

        # ---------------------------------------------------------
        # 2. Center/Right: Browser connection statuses (Edge, ChatGPT, Vbee)
        # ---------------------------------------------------------
        status_box = QHBoxLayout()
        status_box.setSpacing(8)

        self.badge_edge = QLabel("🟡 Edge")
        self.badge_edge.setStyleSheet("""
            color: #fbbf24;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 9px;
            border-radius: 4px;
            background-color: #451a03;
            border: 1px solid #78350f;
        """)
        self.badge_edge.setToolTip("Trình duyệt Microsoft Edge: Đang chờ kết nối (Click để mở Edge)")
        self.badge_edge.setCursor(Qt.CursorShape.PointingHandCursor)
        self.badge_edge.mousePressEvent = lambda _: self.open_edge_requested.emit()
        status_box.addWidget(self.badge_edge)

        self.badge_chatgpt = QLabel("⚪ ChatGPT")
        self.badge_chatgpt.setStyleSheet("""
            color: #94a3b8;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 9px;
            border-radius: 4px;
            background-color: #0f172a;
            border: 1px solid #1e293b;
        """)
        self.badge_chatgpt.setToolTip("ChatGPT: Chưa kiểm tra")
        status_box.addWidget(self.badge_chatgpt)

        self.badge_vbee = QLabel("⚪ Vbee")
        self.badge_vbee.setStyleSheet("""
            color: #94a3b8;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 9px;
            border-radius: 4px;
            background-color: #0f172a;
            border: 1px solid #1e293b;
        """)
        self.badge_vbee.setToolTip("Vbee Studio: Chưa kiểm tra")
        status_box.addWidget(self.badge_vbee)

        self.btn_refresh_bridge = QPushButton("🔄")
        self.btn_refresh_bridge.setProperty("class", "topBtn")
        self.btn_refresh_bridge.setToolTip("Kiểm tra lại trạng thái kết nối Edge, ChatGPT, Vbee")
        self.btn_refresh_bridge.setFixedWidth(28)
        self.btn_refresh_bridge.clicked.connect(self.refresh_bridge_requested.emit)
        status_box.addWidget(self.btn_refresh_bridge)

        # Execution clock badge (Đồng hồ đếm thời gian từ chọn video đến xuất CapCut)
        self.timer_badge = QLabel("⏱ 00:00")
        self.timer_badge.setObjectName("timerBadge")
        self.timer_badge.setStyleSheet("""
            QLabel#timerBadge {
                color: #94a3b8;
                font-size: 11px;
                font-weight: 700;
                font-family: 'Consolas', 'Segoe UI', monospace;
                padding: 3px 10px;
                border-radius: 5px;
                background-color: #0c1424;
                border: 1px solid #1e293b;
            }
        """)
        self.timer_badge.setToolTip("Đồng hồ đếm thời gian thực hiện (từ lúc chọn video đến khi xuất CapCut xong)")
        status_box.addWidget(self.timer_badge)

        layout.addLayout(status_box)

        # ---------------------------------------------------------
        # 3. Far Right: Settings button
        # ---------------------------------------------------------
        self.btn_settings = QPushButton("⚙ Cài đặt")
        self.btn_settings.setProperty("class", "topBtn")
        self.btn_settings.setStyleSheet("""
            QPushButton {
                background-color: #0c111c;
                color: #94a3b8;
                border: 1px solid #1a2436;
                border-radius: 5px;
                padding: 5px 14px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #131b2c;
                border-color: #38bdf8;
                color: #38bdf8;
            }
        """)
        self.btn_settings.setToolTip("Mở bảng Cài đặt chi tiết (AI, Voice, CapCut, Hệ thống)")
        self.btn_settings.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.btn_settings)

        # Pulse timer for active connections
        self._pulse_state = False
        self._last_status: BridgeStatus | None = None
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(1200)
        self._pulse_timer.timeout.connect(self._on_pulse)
        self._pulse_timer.start()

        # Execution Clock state
        self._timer_start_time: float | None = None
        self._timer_running = False
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._on_clock_tick)

        # Romantic heartbeat animation timer
        self._heart_state = False
        self._heart_timer = QTimer(self)
        self._heart_timer.setInterval(1200)
        self._heart_timer.timeout.connect(self._on_heart_pulse)
        self._heart_timer.start()

    def _on_heart_pulse(self) -> None:
        self._heart_state = not self._heart_state
        heart = "💖" if self._heart_state else "💗"
        self.lbl_credit.setText(f"{heart} Dành tặng em bé <b style='color: #ffe4e6;'>Trang Vũ</b> &lt;3")

    def start_timer(self) -> None:
        self._timer_start_time = time.monotonic()
        self._timer_running = True
        self._clock_timer.start(1000)
        self._update_timer_style(running=True)
        self._on_clock_tick()

    def stop_timer(self) -> None:
        if not self._timer_running and not self._timer_start_time:
            return
        self._timer_running = False
        self._clock_timer.stop()
        if self._timer_start_time:
            elapsed_s = int(time.monotonic() - self._timer_start_time)
            mm = elapsed_s // 60
            ss = elapsed_s % 60
            self.timer_badge.setText(f"🎉 Hoàn tất: {mm:02d}:{ss:02d}")
        self._update_timer_style(finished=True)

    def reset_timer(self) -> None:
        self._timer_running = False
        self._timer_start_time = None
        self._clock_timer.stop()
        self.timer_badge.setText("⏱ 00:00")
        self._update_timer_style(running=False, finished=False)

    def _on_clock_tick(self) -> None:
        if not self._timer_running or not self._timer_start_time:
            return
        elapsed_s = int(time.monotonic() - self._timer_start_time)
        mm = elapsed_s // 60
        ss = elapsed_s % 60
        self.timer_badge.setText(f"⏱ {mm:02d}:{ss:02d}")

    def _update_timer_style(self, running: bool = False, finished: bool = False) -> None:
        if finished:
            self.timer_badge.setStyleSheet("""
                QLabel#timerBadge {
                    color: #34d399;
                    font-size: 11px;
                    font-weight: 800;
                    font-family: 'Consolas', 'Segoe UI', monospace;
                    padding: 3px 10px;
                    border-radius: 5px;
                    background-color: #064e3b;
                    border: 1px solid #059669;
                }
            """)
        elif running:
            self.timer_badge.setStyleSheet("""
                QLabel#timerBadge {
                    color: #38bdf8;
                    font-size: 11px;
                    font-weight: 800;
                    font-family: 'Consolas', 'Segoe UI', monospace;
                    padding: 3px 10px;
                    border-radius: 5px;
                    background-color: #082f49;
                    border: 1px solid #0284c7;
                }
            """)
        else:
            self.timer_badge.setStyleSheet("""
                QLabel#timerBadge {
                    color: #94a3b8;
                    font-size: 11px;
                    font-weight: 700;
                    font-family: 'Consolas', 'Segoe UI', monospace;
                    padding: 3px 10px;
                    border-radius: 5px;
                    background-color: #0c1424;
                    border: 1px solid #1e293b;
                }
            """)

    def _on_pulse(self) -> None:
        self._pulse_state = not self._pulse_state
        if self._last_status is not None:
            self.update_bridge_status(self._last_status)

    def set_project_name(self, name: str, dirty: bool = False) -> None:
        dirty_flag = " *" if dirty else ""
        self.lbl_project_name.setText(f"📄 {name}{dirty_flag}")
        if dirty:
            self.lbl_project_name.setStyleSheet("""
                font-size: 11px;
                font-weight: 700;
                color: #fbbf24;
                background-color: #451a03;
                border: 1px solid #b45309;
                padding: 3px 8px;
                border-radius: 4px;
            """)
        else:
            self.lbl_project_name.setStyleSheet("""
                font-size: 11px;
                font-weight: 600;
                color: #38bdf8;
                background-color: #0c1424;
                border: 1px solid #16263f;
                padding: 3px 8px;
                border-radius: 4px;
            """)

    def update_bridge_status(self, status: BridgeStatus) -> None:
        """Update top bar badges with glowing pills and status tooltips."""
        self._last_status = status
        pulse_border_success = "#34d399" if self._pulse_state else "#059669"
        pulse_bg_success = "#083327" if self._pulse_state else "#064e3b"

        # 1. Edge
        if status.browser_connected:
            self.badge_edge.setText("🟢 Edge")
            self.badge_edge.setStyleSheet(f"""
                color: #34d399;
                font-size: 11px;
                font-weight: 700;
                padding: 3px 9px;
                border-radius: 4px;
                background-color: {pulse_bg_success};
                border: 1px solid {pulse_border_success};
            """)
            self.badge_edge.setToolTip(f"Microsoft Edge: Đã kết nối ({status.browser_name or 'Edge'})")
        else:
            self.badge_edge.setText("🟡 Edge")
            self.badge_edge.setStyleSheet("""
                color: #fbbf24;
                font-size: 11px;
                font-weight: 700;
                padding: 3px 9px;
                border-radius: 4px;
                background-color: #451a03;
                border: 1px solid #78350f;
            """)
            self.badge_edge.setToolTip("Microsoft Edge: Đang chờ mở (Click để mở Edge)")

        # 2. ChatGPT
        if not status.browser_connected:
            self.badge_chatgpt.setText("⚪ ChatGPT")
            self.badge_chatgpt.setStyleSheet("""
                color: #64748b;
                font-size: 11px;
                font-weight: 700;
                padding: 3px 9px;
                border-radius: 4px;
                background-color: #0b101b;
                border: 1px solid #1e293b;
            """)
            self.badge_chatgpt.setToolTip("ChatGPT: Chờ kết nối trình duyệt Edge")
        elif status.chatgpt_logged_in:
            tabs = f" ({status.chatgpt_tabs})" if status.chatgpt_tabs > 0 else ""
            self.badge_chatgpt.setText(f"🟢 ChatGPT{tabs}")
            self.badge_chatgpt.setStyleSheet(f"""
                color: #34d399;
                font-size: 11px;
                font-weight: 700;
                padding: 3px 9px;
                border-radius: 4px;
                background-color: {pulse_bg_success};
                border: 1px solid {pulse_border_success};
            """)
            self.badge_chatgpt.setToolTip("ChatGPT: Đã đăng nhập và sẵn sàng dịch tự động")
        else:
            self.badge_chatgpt.setText("🔴 ChatGPT")
            self.badge_chatgpt.setStyleSheet("""
                color: #f87171;
                font-size: 11px;
                font-weight: 700;
                padding: 3px 9px;
                border-radius: 4px;
                background-color: #450a0a;
                border: 1px solid #991b1b;
            """)
            self.badge_chatgpt.setToolTip("ChatGPT: Chưa đăng nhập trong Edge. Vui lòng mở Edge và đăng nhập chatgpt.com")

        # 3. Vbee
        if not status.browser_connected:
            self.badge_vbee.setText("⚪ Vbee")
            self.badge_vbee.setStyleSheet("""
                color: #64748b;
                font-size: 11px;
                font-weight: 700;
                padding: 3px 9px;
                border-radius: 4px;
                background-color: #0b101b;
                border: 1px solid #1e293b;
            """)
            self.badge_vbee.setToolTip("Vbee: Chờ kết nối trình duyệt Edge")
        elif status.vbee_logged_in:
            tabs = f" ({status.vbee_tabs})" if status.vbee_tabs > 0 else ""
            self.badge_vbee.setText(f"🟢 Vbee{tabs}")
            self.badge_vbee.setStyleSheet(f"""
                color: #34d399;
                font-size: 11px;
                font-weight: 700;
                padding: 3px 9px;
                border-radius: 4px;
                background-color: {pulse_bg_success};
                border: 1px solid {pulse_border_success};
            """)
            self.badge_vbee.setToolTip("Vbee: Đã đăng nhập và sẵn sàng tạo giọng lồng tiếng")
        else:
            self.badge_vbee.setText("🔴 Vbee")
            self.badge_vbee.setStyleSheet("""
                color: #f87171;
                font-size: 11px;
                font-weight: 700;
                padding: 3px 9px;
                border-radius: 4px;
                background-color: #450a0a;
                border: 1px solid #991b1b;
            """)
            self.badge_vbee.setToolTip("Vbee: Chưa đăng nhập trong Edge. Vui lòng mở Edge và đăng nhập vbee.vn")
