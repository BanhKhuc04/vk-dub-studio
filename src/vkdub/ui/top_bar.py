"""VK Dub Studio — Cyber Obsidian Top Bar.

Pro Studio header containing:
- Branding (VK Dub Studio · PRO STUDIO)
- Active project filename (with dirty indicator)
- Browser bridge live status pills (Edge, ChatGPT, Vbee)
- Quick Save & Open actions + Settings button
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vkdub.bridge.protocol import BridgeStatus
from vkdub.ui.theme import apply_widget_theme, normalize_theme
from vkdub.utils.paths import resource_path
from vkdub.version import __version__


class TopBar(QFrame):
    """Clean, high-tech creative suite top bar."""

    new_requested = Signal()
    settings_requested = Signal()
    save_requested = Signal()
    open_requested = Signal()
    open_edge_requested = Signal()
    refresh_bridge_requested = Signal()
    theme_requested = Signal(str)
    notifications_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setFixedHeight(94)
        self.setStyleSheet("""
            QFrame#topBar {
                background-color: #ffffff;
                border-bottom: 3px solid #101828;
            }
            QPushButton.topBtn {
                background-color: #ffffff;
                color: #0f172a;
                border: 2px solid #101828;
                border-radius: 9px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 800;
            }
            QPushButton.topBtn:hover {
                background-color: #f1f5f9;
            }
            QPushButton.topBtn:pressed {
                background-color: #e2e8f0;
            }
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 7, 16, 7)
        root_layout.setSpacing(5)
        layout = QHBoxLayout()
        layout.setSpacing(10)
        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        root_layout.addLayout(layout, 1)
        root_layout.addLayout(meta_row, 1)

        # ---------------------------------------------------------
        # 1. Left: Branding & Project name
        # ---------------------------------------------------------
        brand_box = QHBoxLayout()
        brand_box.setSpacing(8)

        # Logo Icon
        self.lbl_logo = QLabel()
        icon_path = resource_path("icon.png")
        if icon_path.is_file():
            pix = QPixmap(str(icon_path)).scaled(
                38,
                38,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.lbl_logo.setPixmap(pix)
            self.lbl_logo.setFixedSize(44, 44)
            self.lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lbl_logo.setStyleSheet(
                "border: 2px solid #101828; border-radius: 10px; background: #ffffff; padding: 1px;"
            )
            brand_box.addWidget(self.lbl_logo)

        self.lbl_title = QLabel("KAPPAK")
        self.lbl_title.setStyleSheet("""
            font-size: 20px;
            font-weight: 900;
            color: #101828;
            letter-spacing: 0.5px;
            font-family: 'Plus Jakarta Sans', 'Segoe UI', sans-serif;
        """)
        brand_box.addWidget(self.lbl_title)

        # Compatibility-only branding widgets.  They are intentionally hidden:
        # KAPPAK and the requested creator card already provide enough identity,
        # while these decorative labels made the working header feel crowded.
        self.badge_pro = QLabel("PRO STUDIO")
        self.badge_pro.setStyleSheet("""
            background-color: #eef4ff;
            color: #173fb8;
            border: 2px solid #2457f5;
            font-size: 9px;
            font-weight: 800;
            padding: 3px 7px;
            border-radius: 6px;
            letter-spacing: 0.5px;
        """)
        brand_box.addWidget(self.badge_pro)
        self.badge_pro.hide()

        self.lbl_version = QLabel(f"v{__version__}")
        self.lbl_version.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 700;")
        self.lbl_version.setToolTip(f"Phiên bản KAPPAK {__version__}")
        brand_box.addWidget(self.lbl_version)
        self.lbl_version.hide()

        # Kept as an attribute for compatibility, but the header now prioritises
        # the two user-requested creator/dedication badges on the second row.
        self.badge_doodle = QLabel("Good Content 👑")
        self.badge_doodle.setStyleSheet("""
            background-color: #fff0f5;
            color: #c51652;
            border: 2px solid #101828;
            font-size: 10px;
            font-weight: 800;
            padding: 2px 8px;
            border-radius: 6px;
        """)
        self.badge_doodle.hide()

        # Nút Project mới
        self.btn_new = QPushButton("✨ Dự án mới")
        self.btn_new.setStyleSheet("""
            QPushButton {
                background-color: #b9f227;
                color: #101828;
                border: 2px solid #101828;
                border-radius: 9px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 900;
            }
            QPushButton:hover {
                background-color: #a7df18;
            }
            QPushButton:pressed {
                background-color: #95c916;
            }
        """)
        self.btn_new.setToolTip("Khởi tạo dự án mới (Ctrl+N)")
        self.btn_new.clicked.connect(self.new_requested.emit)
        brand_box.addWidget(self.btn_new)

        self.lbl_project_name = QLabel("📁 Mới")
        self.lbl_project_name.setStyleSheet("""
            font-size: 11px;
            font-weight: 800;
            color: #0f172a;
            background-color: #ffffff;
            border: 2px solid #101828;
            padding: 5px 10px;
            border-radius: 9px;
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

        # Center branding credit
        self.credit_card = QFrame()
        self.credit_card.setObjectName("creditCard")
        self.credit_card.setStyleSheet("""
            QFrame#creditCard {
                background-color: #fff0f5;
                border: 2px solid #101828;
                border-radius: 9px;
                padding: 1px 12px;
            }
        """)
        credit_layout = QHBoxLayout(self.credit_card)
        credit_layout.setContentsMargins(8, 2, 8, 2)
        credit_layout.setSpacing(10)

        self.lbl_credit_author = QLabel("✨ Sản phẩm tạo bởi <b>vanhkhuc.dev</b>")
        self.lbl_credit_author.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_credit_author.setStyleSheet(
            "font-size: 10px; color: #344054; font-weight: 700; background: transparent;"
        )
        credit_layout.addWidget(self.lbl_credit_author)

        credit_separator = QLabel("•")
        credit_separator.setStyleSheet(
            "font-size: 11px; color: #ff5c8a; font-weight: 900; background: transparent;"
        )
        credit_layout.addWidget(credit_separator)

        self.lbl_credit = QLabel("💖 Dành tặng em bé <b style='color: #e11d48;'>Trang Vũ</b> &lt;3")
        self.lbl_credit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_credit.setStyleSheet(
            "font-size: 10px; color: #d91d5c; font-weight: 800; background: transparent;"
        )
        credit_layout.addWidget(self.lbl_credit)

        meta_row.addWidget(self.credit_card)
        meta_row.addStretch(1)

        # ---------------------------------------------------------
        # 2. Center/Right: Browser connection statuses (Edge, ChatGPT, Vbee)
        # ---------------------------------------------------------
        status_box = QHBoxLayout()
        status_box.setSpacing(8)

        self.badge_edge = QLabel("🟡 Edge")
        self.badge_edge.setStyleSheet("""
            color: #854d0e;
            font-size: 11px;
            font-weight: 800;
            padding: 3px 9px;
            border-radius: 6px;
            background-color: #fef9c3;
            border: 2px solid #0f172a;
        """)
        self.badge_edge.setToolTip(
            "Trình duyệt Microsoft Edge: Đang chờ kết nối (Click để mở Edge)"
        )
        self.badge_edge.setCursor(Qt.CursorShape.PointingHandCursor)
        self.badge_edge.mousePressEvent = lambda _: self.open_edge_requested.emit()
        status_box.addWidget(self.badge_edge)

        self.badge_chatgpt = QLabel("⚪ ChatGPT")
        self.badge_chatgpt.setStyleSheet("""
            color: #64748b;
            font-size: 11px;
            font-weight: 800;
            padding: 3px 9px;
            border-radius: 6px;
            background-color: #f1f5f9;
            border: 2px solid #0f172a;
        """)
        self.badge_chatgpt.setToolTip("ChatGPT: Chưa kiểm tra")
        status_box.addWidget(self.badge_chatgpt)

        self.badge_vbee = QLabel("⚪ Vbee")
        self.badge_vbee.setStyleSheet("""
            color: #64748b;
            font-size: 11px;
            font-weight: 800;
            padding: 3px 9px;
            border-radius: 6px;
            background-color: #f1f5f9;
            border: 2px solid #0f172a;
        """)
        self.badge_vbee.setToolTip("Vbee Studio: Chưa kiểm tra")
        status_box.addWidget(self.badge_vbee)

        self.btn_refresh_bridge = QPushButton("🔄")
        self.btn_refresh_bridge.setProperty("class", "topBtn")
        self.btn_refresh_bridge.setToolTip("Kiểm tra lại trạng thái kết nối Edge, ChatGPT, Vbee")
        self.btn_refresh_bridge.setFixedWidth(32)
        self.btn_refresh_bridge.clicked.connect(self.refresh_bridge_requested.emit)
        status_box.addWidget(self.btn_refresh_bridge)

        # Execution clock badge (Đồng hồ đếm thời gian từ chọn video đến xuất CapCut)
        self.timer_badge = QLabel("⏱ 00:00")
        self.timer_badge.setObjectName("timerBadge")
        self.timer_badge.setStyleSheet("""
            QLabel#timerBadge {
                color: #0f172a;
                font-size: 11px;
                font-weight: 800;
                font-family: 'Consolas', 'Segoe UI', monospace;
                padding: 3px 10px;
                border-radius: 6px;
                background-color: #f1f5f9;
                border: 2px solid #0f172a;
            }
        """)
        self.timer_badge.setToolTip(
            "Đồng hồ đếm thời gian thực hiện (từ lúc chọn video đến khi xuất CapCut xong)"
        )
        status_box.addWidget(self.timer_badge)

        meta_row.addLayout(status_box)

        # ---------------------------------------------------------
        # 3. Far Right: Theme and Settings
        # ---------------------------------------------------------
        current_theme = normalize_theme(
            QApplication.instance().property("kappakTheme") if QApplication.instance() else "light"
        )
        self.btn_theme = QPushButton()
        self.btn_theme.setProperty("class", "topBtn")
        self.btn_theme.setFixedWidth(34)
        self.btn_theme.clicked.connect(self._toggle_theme)
        layout.addWidget(self.btn_theme)

        self.btn_notifications = QPushButton("🔔")
        self.btn_notifications.setProperty("class", "topBtn")
        self.btn_notifications.setFixedWidth(38)
        self.btn_notifications.setToolTip("Mở thông báo và nhật ký hoạt động")
        self.btn_notifications.setAccessibleName("Thông báo và nhật ký hoạt động")
        self.btn_notifications.clicked.connect(self.notifications_requested.emit)
        layout.addWidget(self.btn_notifications)

        self.avatar_chip = QLabel("VK")
        self.avatar_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_chip.setFixedSize(36, 36)
        self.avatar_chip.setToolTip("vanhkhuc.dev · KAPPAK Creator")
        self.avatar_chip.setStyleSheet("""
            color: #ffffff;
            background-color: #2457f5;
            border: 2px solid #101828;
            border-radius: 18px;
            font-size: 12px;
            font-weight: 900;
        """)
        layout.addWidget(self.avatar_chip)
        self.avatar_chip.hide()

        self.btn_settings = QPushButton("⚙ Cài đặt")
        self.btn_settings.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #0f172a;
                border: 2px solid #101828;
                border-radius: 9px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #b9f227;
            }
            QPushButton:pressed {
                background-color: #a7df18;
            }
        """)
        self.btn_settings.setToolTip("Mở bảng Cài đặt chi tiết (AI, Voice, CapCut, Hệ thống)")
        self.btn_settings.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.btn_settings)

        self.set_theme(current_theme)

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

    def set_theme(self, theme: str) -> None:
        """Update the compact theme switch without changing application state."""
        self._theme = normalize_theme(theme)
        if self._theme == "dark":
            self.btn_theme.setText("☀")
            self.btn_theme.setToolTip("Chuyển sang giao diện sáng")
        else:
            self.btn_theme.setText("☾")
            self.btn_theme.setToolTip("Chuyển sang giao diện tối")
        apply_widget_theme(self, self._theme)

    def _toggle_theme(self) -> None:
        self.theme_requested.emit("light" if self._theme == "dark" else "dark")

    def _on_heart_pulse(self) -> None:
        self._heart_state = not self._heart_state
        heart = "💖" if self._heart_state else "💗"
        self.lbl_credit.setText(
            f"{heart} Dành tặng em bé <b style='color: #e11d48;'>Trang Vũ</b> &lt;3"
        )

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
                    color: #15803d;
                    font-size: 11px;
                    font-weight: 800;
                    font-family: 'Consolas', 'Segoe UI', monospace;
                    padding: 3px 10px;
            border-radius: 8px;
                    background-color: #dcfce7;
            border: 2px solid #101828;
                }
            """)
        elif running:
            self.timer_badge.setStyleSheet("""
                QLabel#timerBadge {
                    color: #1e40af;
            font-size: 12px;
                    font-weight: 800;
                    font-family: 'Consolas', 'Segoe UI', monospace;
                    padding: 3px 10px;
            border-radius: 8px;
                    background-color: #dbeafe;
            border: 2px solid #101828;
                }
            """)
        else:
            self.timer_badge.setStyleSheet("""
                QLabel#timerBadge {
                    color: #0f172a;
            font-size: 12px;
                    font-weight: 800;
                    font-family: 'Consolas', 'Segoe UI', monospace;
                    padding: 3px 10px;
            border-radius: 8px;
                    background-color: #f1f5f9;
            border: 2px solid #101828;
                }
            """)
        apply_widget_theme(self)

    def _on_pulse(self) -> None:
        self._pulse_state = not self._pulse_state
        if self._last_status is not None:
            self.update_bridge_status(self._last_status)

    def set_project_name(self, name: str, dirty: bool = False) -> None:
        dirty_flag = " ●" if dirty else ""
        self.lbl_project_name.setText(f"📁 Dự án: {name}{dirty_flag}")
        if dirty:
            self.lbl_project_name.setStyleSheet("""
                font-size: 11px;
                font-weight: 800;
                color: #854d0e;
                background-color: #fef08a;
                border: 2px solid #0f172a;
                padding: 3px 10px;
                border-radius: 6px;
            """)
        else:
            self.lbl_project_name.setStyleSheet("""
                font-size: 11px;
                font-weight: 800;
                color: #0f172a;
                background-color: #ffffff;
                border: 2px solid #0f172a;
                padding: 3px 10px;
                border-radius: 6px;
            """)
        apply_widget_theme(self)

    def update_bridge_status(self, status: BridgeStatus) -> None:
        """Update top bar badges with Neo Brutalism status pills."""
        self._last_status = status
        pulse_bg_success = "#bbf7d0" if self._pulse_state else "#dcfce7"

        # 1. Edge
        if status.browser_connected:
            self.badge_edge.setText("🟢 Edge")
            self.badge_edge.setStyleSheet(f"""
                color: #15803d;
                font-size: 11px;
                font-weight: 800;
                padding: 3px 9px;
                border-radius: 6px;
                background-color: {pulse_bg_success};
                border: 2px solid #0f172a;
            """)
            self.badge_edge.setToolTip(
                f"Microsoft Edge: Đã kết nối ({status.browser_name or 'Edge'})"
            )
        else:
            self.badge_edge.setText("🟡 Edge")
            self.badge_edge.setStyleSheet("""
                color: #854d0e;
                font-size: 11px;
                font-weight: 800;
                padding: 3px 9px;
                border-radius: 6px;
                background-color: #fef9c3;
                border: 2px solid #0f172a;
            """)
            self.badge_edge.setToolTip("Microsoft Edge: Đang chờ mở (Click để mở Edge)")

        # 2. ChatGPT
        if not status.browser_connected:
            self.badge_chatgpt.setText("⚪ ChatGPT")
            self.badge_chatgpt.setStyleSheet("""
                color: #64748b;
                font-size: 11px;
                font-weight: 800;
                padding: 3px 9px;
                border-radius: 6px;
                background-color: #f1f5f9;
                border: 2px solid #0f172a;
            """)
            self.badge_chatgpt.setToolTip("ChatGPT: Chờ kết nối trình duyệt Edge")
        elif status.chatgpt_logged_in:
            tabs = f" ({status.chatgpt_tabs})" if status.chatgpt_tabs > 0 else ""
            self.badge_chatgpt.setText(f"🟢 ChatGPT{tabs}")
            self.badge_chatgpt.setStyleSheet(f"""
                color: #15803d;
                font-size: 11px;
                font-weight: 800;
                padding: 3px 9px;
                border-radius: 6px;
                background-color: {pulse_bg_success};
                border: 2px solid #0f172a;
            """)
            self.badge_chatgpt.setToolTip("ChatGPT: Đã đăng nhập và sẵn sàng dịch tự động")
        else:
            self.badge_chatgpt.setText("🔴 ChatGPT")
            self.badge_chatgpt.setStyleSheet("""
                color: #b91c1c;
                font-size: 11px;
                font-weight: 800;
                padding: 3px 9px;
                border-radius: 6px;
                background-color: #fee2e2;
                border: 2px solid #0f172a;
            """)
            self.badge_chatgpt.setToolTip(
                "ChatGPT: Chưa đăng nhập trong Edge. Vui lòng mở Edge và đăng nhập chatgpt.com"
            )

        # 3. Vbee
        if not status.browser_connected:
            self.badge_vbee.setText("⚪ Vbee")
            self.badge_vbee.setStyleSheet("""
                color: #64748b;
                font-size: 11px;
                font-weight: 800;
                padding: 3px 9px;
                border-radius: 6px;
                background-color: #f1f5f9;
                border: 2px solid #0f172a;
            """)
            self.badge_vbee.setToolTip("Vbee: Chờ kết nối trình duyệt Edge")
        elif status.vbee_logged_in:
            tabs = f" ({status.vbee_tabs})" if status.vbee_tabs > 0 else ""
            self.badge_vbee.setText(f"🟢 Vbee{tabs}")
            self.badge_vbee.setStyleSheet(f"""
                color: #15803d;
                font-size: 11px;
                font-weight: 800;
                padding: 3px 9px;
                border-radius: 6px;
                background-color: {pulse_bg_success};
                border: 2px solid #0f172a;
            """)
            self.badge_vbee.setToolTip("Vbee: Đã đăng nhập và sẵn sàng tạo giọng lồng tiếng")
        else:
            self.badge_vbee.setText("🔴 Vbee")
            self.badge_vbee.setStyleSheet("""
                color: #b91c1c;
                font-size: 11px;
                font-weight: 800;
                padding: 3px 9px;
                border-radius: 6px;
                background-color: #fee2e2;
                border: 2px solid #0f172a;
            """)
            self.badge_vbee.setToolTip(
                "Vbee: Chưa đăng nhập trong Edge. Vui lòng mở Edge và đăng nhập vbee.vn"
            )
        apply_widget_theme(self)
