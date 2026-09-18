"""Main application window shell for KAPPAK Studio V2 — Apple Glass Female Hero Edition."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from kappak.core.config import get_database_path
from kappak.core.db import init_db
from kappak.jobs.manager import LocalJobManager
from kappak.ui.modules.auto_dub_view import AutoDubView
from kappak.ui.modules.auto_video_view import AutoVideoView
from kappak.ui.modules.data_studio_view import DataStudioView
from kappak.ui.modules.downloader_view import DownloaderView
from kappak.ui.modules.home_view import HomeView
from kappak.ui.modules.social_view import SocialView
from kappak.ui.modules.today_view import TodayView
from kappak.ui.theme import APPLE_GLASS_STYLESHEET
from kappak.ui.widgets.ask_kappak_drawer import AskKappakDrawer
from kappak.ui.widgets.icon_rail import IconRail
from kappak.ui.widgets.top_bar import TopBar


class KappakShell(QMainWindow):
    """Main window hosting Apple Glass navigation, Home view, 6 modules and Ask KAPPAK drawer."""

    def __init__(self, job_manager: LocalJobManager | None = None) -> None:
        super().__init__()
        self.setWindowTitle("KAPPAK Studio — Video tools for creators")
        self.resize(1600, 940)
        self.setMinimumSize(1180, 750)
        self.setStyleSheet(APPLE_GLASS_STYLESHEET)

        # Set Window Icon
        icon_path = Path(r"D:\Work\Project_AI\ToolVideo\resources\icon.png")
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Initialize Core DB & Persistent Job Manager (Preserved 100%)
        init_db()
        self.job_manager = job_manager or LocalJobManager()

        # Central Root Layout
        central = QWidget()
        central.setObjectName("centralRoot")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Top Bar
        self.top_bar = TopBar(self)
        self.top_bar.ask_kappak_requested.connect(self._toggle_ask_drawer)
        self.top_bar.search_triggered.connect(self._on_search)
        root_layout.addWidget(self.top_bar)

        # 2. Main Middle Workspace: Left Icon Rail + Center Stack + Right Ask Drawer
        middle_container = QWidget()
        middle_container.setObjectName("middleContainer")
        middle_container.setStyleSheet("background-color: #F5F8FD;")
        middle_layout = QHBoxLayout(middle_container)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)

        # 2a. Left Icon Rail (74px)
        self.icon_rail = IconRail(self)
        self.icon_rail.module_selected.connect(self._switch_module)
        self.icon_rail.help_requested.connect(self._on_help_clicked)
        middle_layout.addWidget(self.icon_rail)

        # 2b. Center QStackedWidget for Views
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: #F5F8FD; border: none;")

        # View 0: Home View (Target Apple Glass Female Hero Layout)
        self.view_home = HomeView()
        self.view_home.navigate_to_module.connect(self._switch_module)
        self.view_home.ask_kappak_requested.connect(self._toggle_ask_drawer)

        # Module Views 1 to 6
        self.view_data_studio = DataStudioView()
        self.view_downloader = DownloaderView()
        self.view_auto_video = AutoVideoView()
        self.view_auto_dub = AutoDubView()
        self.view_social = SocialView()
        self.view_today = TodayView()

        # Add to stack:
        # 0: Home, 1: Data Studio, 2: Downloader, 3: Auto Video, 4: Auto Dub, 5: Social, 6: Today
        self.stack.addWidget(self.view_home)          # idx 0
        self.stack.addWidget(self.view_data_studio)   # idx 1
        self.stack.addWidget(self.view_downloader)    # idx 2
        self.stack.addWidget(self.view_auto_video)    # idx 3
        self.stack.addWidget(self.view_auto_dub)      # idx 4
        self.stack.addWidget(self.view_social)        # idx 5
        self.stack.addWidget(self.view_today)         # idx 6

        middle_layout.addWidget(self.stack, 1)

        # 2c. Right Slide-over Ask KAPPAK Drawer (Hidden by default)
        self.ask_drawer = AskKappakDrawer(self)
        self.ask_drawer.close_requested.connect(self._hide_ask_drawer)
        self.ask_drawer.setVisible(False)
        middle_layout.addWidget(self.ask_drawer)

        root_layout.addWidget(middle_container, 1)

        # 3. Footer Bar
        footer = QFrame()
        footer.setObjectName("footerBar")
        footer.setFixedHeight(36)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 0, 24, 0)

        f_left = QLabel("KAPPAK Studio Web v2  •  Sáng tạo không giới hạn")
        f_left.setStyleSheet("color: #8595B2; font-size: 11px; font-weight: 600;")
        footer_layout.addWidget(f_left)

        footer_layout.addStretch()

        f_right = QLabel("Better Tools. Brighter Stories.")
        f_right.setStyleSheet("color: #8595B2; font-size: 11px; font-weight: 500;")
        footer_layout.addWidget(f_right)

        root_layout.addWidget(footer)

    def _switch_module(self, idx: int) -> None:
        """Switch views and update icon rail."""
        if 0 <= idx < self.stack.count():
            self.stack.setCurrentIndex(idx)
            self.icon_rail.select_module(idx)

    def _toggle_ask_drawer(self) -> None:
        """Toggle right-hand Ask KAPPAK assistant drawer."""
        is_visible = self.ask_drawer.isVisible()
        self.ask_drawer.setVisible(not is_visible)

    def _hide_ask_drawer(self) -> None:
        self.ask_drawer.setVisible(False)

    def _on_search(self, query: str) -> None:
        """Handle search in top bar."""
        # For prototype, open Ask KAPPAK with the query
        self.ask_drawer.setVisible(True)
        self.ask_drawer.input_field.setText(query)
        self.ask_drawer._send_prompt()

    def _on_help_clicked(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "KAPPAK Studio Help",
            "Hướng dẫn sử dụng KAPPAK Studio V2:\n\n"
            "• Trang chủ: Khởi tạo dự án, xem tài nguyên gần đây và gợi ý AI.\n"
            "• 6 Module: Downloader, Data Studio, Auto Video, Auto Dub, Social, Today.\n"
            "• ✦ Ask KAPPAK: Trợ lý thông minh điều khiển toàn hệ thống.",
        )
