"""Home View for KAPPAK Studio V2 — Apple Glass Female Hero Layout."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from kappak.ui.icons import get_icon, get_pixmap
from kappak.ui.theme import (
    COLOR_PRIMARY,
    TINT_AMBER,
    TINT_BLUE,
    TINT_CYAN,
    TINT_MINT,
    TINT_PINK,
    TINT_VIOLET,
)


class HeroSection(QFrame):
    """Focal Hero Banner with young female creator visual and Apple Glass aesthetics."""

    cta_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("heroCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(315)
        self.setStyleSheet(
            "QFrame#heroCard { "
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FFFFFF, stop:0.48 #F1F6FF, stop:1 #E8F1FF); "
            "border: 1px solid rgba(76, 104, 153, 0.14); border-radius: 28px; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(42, 18, 14, 18)
        layout.setSpacing(10)

        # Left Text Content (~52% width)
        left_box = QWidget()
        left_box.setStyleSheet("background: transparent; border: none;")
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(0, 4, 0, 4)
        left_layout.setSpacing(12)

        # Eyebrow
        eyebrow = QLabel("K A P P A K   S T U D I O   W E B   V 2")
        eyebrow.setStyleSheet("font-size: 11px; font-weight: 800; color: #66779C; letter-spacing: 2px;")
        left_layout.addWidget(eyebrow)

        # Main Headline with gradient blue accent
        headline = QLabel(
            "Biến ý tưởng thành<br>"
            "những video <span style='color: #2777FF;'>tuyệt vời</span>"
        )
        headline.setStyleSheet("font-size: 38px; font-weight: 850; color: #0A1738; line-height: 1.15;")
        left_layout.addWidget(headline)

        # Subheading
        subtitle = QLabel(
            "Sức mạnh AI cho sáng tạo nội dung đa phương tiện.<br>"
            "Nhanh hơn. Đơn giản hơn. Hiệu quả hơn mỗi ngày."
        )
        subtitle.setStyleSheet("font-size: 13px; color: #5B6D94; font-weight: 500; line-height: 1.45;")
        left_layout.addWidget(subtitle)

        left_layout.addSpacing(4)

        # Interactive Pill CTA Button
        self.btn_cta = QPushButton("✦  Sáng tạo không giới hạn, với AI đồng hành   ›")
        self.btn_cta.setProperty("class", "heroCtaPill")
        self.btn_cta.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cta.setFixedHeight(40)
        self.btn_cta.setStyleSheet(
            "QPushButton { background-color: #FFFFFF; color: #0A1738; border: 1px solid rgba(76, 104, 153, 0.18); "
            "border-radius: 20px; padding: 6px 20px; font-size: 13px; font-weight: 600; } "
            "QPushButton:hover { border-color: #2777FF; color: #2777FF; }"
        )
        self.btn_cta.clicked.connect(self.cta_clicked.emit)
        left_layout.addWidget(self.btn_cta, alignment=Qt.AlignmentFlag.AlignLeft)

        left_layout.addStretch()
        layout.addWidget(left_box, 52)

        # Right Female Creator Visual (~48% width)
        hero_img_path = Path(r"D:\Work\Project_AI\ToolVideo\resources\kappak\hero_female_creator_hd.png")
        if not hero_img_path.is_file():
            hero_img_path = Path(r"D:\Work\Project_AI\ToolVideo\resources\kappak\hero_female_creator.png")
        if hero_img_path.is_file():
            img_lbl = QLabel()
            img_lbl.setStyleSheet("background: transparent; border: none;")
            pixmap = QPixmap(str(hero_img_path))
            scaled_pixmap = pixmap.scaledToHeight(
                275, Qt.TransformationMode.SmoothTransformation
            )
            img_lbl.setPixmap(scaled_pixmap)
            img_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(img_lbl, 48)
        else:
            layout.addStretch(48)


class ModuleCard(QFrame):
    """Interactive glass module card with pastel icon tile."""

    clicked = Signal(int)

    def __init__(
        self,
        module_id: int,
        icon_name: str,
        title: str,
        description: str,
        tint_color: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.module_id = module_id
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(185)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1px solid rgba(76, 104, 153, 0.12); "
            "border-radius: 22px; } "
            "QFrame:hover { border-color: rgba(39, 119, 255, 0.45); }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        # Pastel Rounded Icon Tile (48x48)
        icon_tile = QLabel()
        icon_tile.setFixedSize(46, 46)
        icon_tile.setStyleSheet(f"background-color: {tint_color}; border-radius: 14px; border: none;")
        icon_tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_tile.setPixmap(get_pixmap(icon_name, color="#0A1738", size=22))
        layout.addWidget(icon_tile)

        # Title
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #0A1738; border: none; background: transparent;")
        layout.addWidget(title_lbl)

        # Description
        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 12px; color: #66779C; line-height: 1.4; font-weight: 500; border: none; background: transparent;")
        layout.addWidget(desc_lbl)

        layout.addStretch()

        # Bottom Arrow Circle
        arrow_box = QWidget()
        arrow_box.setStyleSheet("background: transparent; border: none;")
        arrow_layout = QHBoxLayout(arrow_box)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        arrow_layout.addStretch()

        arrow_btn = QPushButton()
        arrow_btn.setFixedSize(30, 30)
        arrow_btn.setStyleSheet(
            "QPushButton { background-color: #F1F6FD; border: none; border-radius: 15px; } "
            "QPushButton:hover { background-color: #2777FF; }"
        )
        arrow_btn.setIcon(get_icon("arrow_right", color="#2777FF", active_color="#FFFFFF", size=13))
        arrow_btn.setIconSize(QSize(13, 13))
        arrow_btn.clicked.connect(lambda: self.clicked.emit(self.module_id))
        arrow_layout.addWidget(arrow_btn)

        layout.addWidget(arrow_box)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self.module_id)
        super().mousePressEvent(event)


class ModuleStrip(QWidget):
    """Horizontal strip of 6 KAPPAK module cards."""

    module_navigated = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        modules_data = [
            (2, "download", "Downloader", "Tải video đa nền tảng chất lượng cao, giữ nguyên metadata.", TINT_BLUE),
            (1, "folder", "Data Studio", "Quản lý dữ liệu, thư viện tài nguyên và kịch bản tập trung.", TINT_MINT),
            (3, "sparkles", "Auto Video", "Tự động hóa sản xuất video từ kịch bản và nguyên liệu.", TINT_VIOLET),
            (4, "mic", "Auto Dub", "Lồng tiếng, dịch thuật đa ngôn ngữ và phụ đề thông minh.", TINT_CYAN),
            (5, "share", "Social", "Quản lý kênh, lên lịch đăng và tối ưu hóa phân phối.", TINT_PINK),
            (6, "calendar", "Today", "Tiến độ công việc, gợi ý hàng ngày và nhiệm vụ ưu tiên.", TINT_AMBER),
        ]

        for mod_id, icon, title, desc, tint in modules_data:
            card = ModuleCard(mod_id, icon, title, desc, tint, self)
            card.clicked.connect(self.module_navigated.emit)
            layout.addWidget(card)


class RecentProjectsSection(QFrame):
    """Recent Projects card displaying recent media cards."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(225)
        self.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1px solid rgba(76, 104, 153, 0.12); "
            "border-radius: 22px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Header
        header = QWidget()
        header.setStyleSheet("background: transparent; border: none;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)

        left_h = QWidget()
        left_h.setStyleSheet("background: transparent; border: none;")
        lh_layout = QHBoxLayout(left_h)
        lh_layout.setContentsMargins(0, 0, 0, 0)
        lh_layout.setSpacing(8)

        clock_lbl = QLabel()
        clock_lbl.setPixmap(get_pixmap("clock", color="#0A1738", size=18))
        lh_layout.addWidget(clock_lbl)

        title = QLabel("Dự án gần đây")
        title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0A1738; background: transparent; border: none;")
        lh_layout.addWidget(title)
        h_layout.addWidget(left_h)

        h_layout.addStretch()

        view_all = QPushButton("Xem tất cả →")
        view_all.setStyleSheet(
            "background: transparent; border: none; color: #2777FF; font-size: 13px; font-weight: 700;"
        )
        view_all.setCursor(Qt.CursorShape.PointingHandCursor)
        h_layout.addWidget(view_all)

        layout.addWidget(header)

        # 3 Projects Cards Row
        cards_row = QWidget()
        cards_row.setStyleSheet("background: transparent; border: none;")
        row_layout = QHBoxLayout(cards_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(14)

        projects = [
            ("Hành trình Đà Lạt", "Cập nhật 16/09/2025", "thumb_sample_1.png"),
            ("Giới thiệu sản phẩm", "Cập nhật 15/09/2025", "thumb_sample_2.png"),
            ("Apple Minimalist Video", "Cập nhật 14/09/2025", "thumb_sample_3.png"),
        ]

        for p_title, p_date, p_thumb in projects:
            p_card = QWidget()
            p_card.setStyleSheet("background: transparent; border: none;")
            p_layout = QVBoxLayout(p_card)
            p_layout.setContentsMargins(0, 0, 0, 0)
            p_layout.setSpacing(6)

            # Thumbnail box (The duration pill is already in the cropped reference image)
            thumb_box = QLabel()
            thumb_box.setFixedHeight(86)
            thumb_box.setStyleSheet(
                "background-color: #E2E8F0; border-radius: 12px; border: none;"
            )
            thumb_path = Path(rf"D:\Work\Project_AI\ToolVideo\resources\kappak\{p_thumb}")
            if thumb_path.is_file():
                pix = QPixmap(str(thumb_path)).scaled(
                    230, 86, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
                )
                thumb_box.setPixmap(pix)
            thumb_box.setScaledContents(True)
            p_layout.addWidget(thumb_box)

            # Title and overflow menu row
            info_box = QWidget()
            info_box.setStyleSheet("background: transparent; border: none;")
            info_layout = QHBoxLayout(info_box)
            info_layout.setContentsMargins(0, 0, 0, 0)

            t_box = QWidget()
            t_box.setStyleSheet("background: transparent; border: none;")
            t_layout = QVBoxLayout(t_box)
            t_layout.setContentsMargins(0, 0, 0, 0)
            t_layout.setSpacing(1)

            pt_lbl = QLabel(p_title)
            pt_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #0A1738; background: transparent; border: none;")
            t_layout.addWidget(pt_lbl)

            pd_lbl = QLabel(p_date)
            pd_lbl.setStyleSheet("font-size: 11px; color: #66779C; font-weight: 500; background: transparent; border: none;")
            t_layout.addWidget(pd_lbl)
            info_layout.addWidget(t_box)

            info_layout.addStretch()

            btn_more = QPushButton()
            btn_more.setFixedSize(22, 22)
            btn_more.setStyleSheet("background: transparent; border: none;")
            btn_more.setIcon(get_icon("more", color="#8595B2", active_color="#0A1738", size=14))
            info_layout.addWidget(btn_more)

            p_layout.addWidget(info_box)
            row_layout.addWidget(p_card)

        layout.addWidget(cards_row)


class ContinueWorkSection(QFrame):
    """Continue Work section with status and quick action button."""

    create_project_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(225)
        self.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1px solid rgba(76, 104, 153, 0.12); "
            "border-radius: 22px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # Header
        header = QWidget()
        header.setStyleSheet("background: transparent; border: none;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_pixmap("video", color="#2777FF", size=18))
        h_layout.addWidget(icon_lbl)

        title = QLabel("Tiếp tục công việc")
        title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0A1738; background: transparent; border: none;")
        h_layout.addWidget(title)

        h_layout.addStretch()

        chev = QLabel()
        chev.setPixmap(get_pixmap("chevron_right", color="#66779C", size=14))
        h_layout.addWidget(chev)
        layout.addWidget(header)

        # Inner Content Box
        inner_box = QFrame()
        inner_box.setStyleSheet(
            "background-color: #F8FAFD; border: 1px dashed rgba(76, 104, 153, 0.22); border-radius: 16px;"
        )
        in_layout = QVBoxLayout(inner_box)
        in_layout.setContentsMargins(16, 12, 16, 12)
        in_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        in_layout.setSpacing(6)

        play_icon = QLabel()
        play_icon.setPixmap(get_pixmap("video", color="#8595B2", size=24))
        play_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        play_icon.setStyleSheet("border: none; background: transparent;")
        in_layout.addWidget(play_icon)

        status_lbl = QLabel("Chưa có phiên làm việc gần đây")
        status_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #0A1738; border: none; background: transparent;")
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        in_layout.addWidget(status_lbl)

        desc_lbl = QLabel(
            "Hãy bắt đầu một dự án hoặc khám phá các công cụ AI để tạo nội dung."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 11px; color: #66779C; font-weight: 500; border: none; background: transparent;")
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        in_layout.addWidget(desc_lbl)

        btn_new = QPushButton("+ Tạo dự án mới")
        btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new.setStyleSheet(
            "QPushButton { background-color: #2777FF; color: #FFFFFF; border: none; border-radius: 16px; "
            "padding: 8px 22px; font-size: 12px; font-weight: 700; } "
            "QPushButton:hover { background-color: #1B63E0; }"
        )
        btn_new.clicked.connect(self.create_project_clicked.emit)
        in_layout.addWidget(btn_new, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(inner_box)


class AiSuggestionSection(QFrame):
    """AI Suggestion section with sparkling pastel banner."""

    try_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(225)
        self.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1px solid rgba(76, 104, 153, 0.12); "
            "border-radius: 22px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # Header
        header = QWidget()
        header.setStyleSheet("background: transparent; border: none;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_pixmap("bulb", color="#EAB308", size=18))
        h_layout.addWidget(icon_lbl)

        title = QLabel("Gợi ý bởi AI")
        title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0A1738; background: transparent; border: none;")
        h_layout.addWidget(title)

        h_layout.addStretch()

        chev = QLabel()
        chev.setPixmap(get_pixmap("chevron_right", color="#66779C", size=14))
        h_layout.addWidget(chev)
        layout.addWidget(header)

        # Gradient Banner
        banner = QFrame()
        banner.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EAF3FF, stop:1 #F5EEFF); "
            "border: 1px solid rgba(139, 92, 246, 0.20); border-radius: 16px;"
        )
        b_layout = QVBoxLayout(banner)
        b_layout.setContentsMargins(16, 12, 16, 12)
        b_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b_layout.setSpacing(6)

        sparkle = QLabel()
        sparkle.setPixmap(get_pixmap("sparkles", color="#2777FF", size=22))
        sparkle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sparkle.setStyleSheet("border: none; background: transparent;")
        b_layout.addWidget(sparkle)

        prompt_lbl = QLabel("Biến ý tưởng thành video<br>chỉ trong vài phút")
        prompt_lbl.setStyleSheet("font-size: 13px; font-weight: 800; color: #1E3A8A; line-height: 1.3; border: none; background: transparent;")
        prompt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b_layout.addWidget(prompt_lbl)

        sub_lbl = QLabel("Thử tạo video từ một đoạn mô tả ngắn với AI của KAPPAK.")
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet("font-size: 11px; color: #5B6D94; font-weight: 500; border: none; background: transparent;")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b_layout.addWidget(sub_lbl)

        btn_try = QPushButton("Dùng thử ngay →")
        btn_try.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_try.setStyleSheet(
            "QPushButton { background-color: #FFFFFF; color: #0A1738; border: 1px solid rgba(76, 104, 153, 0.20); "
            "border-radius: 16px; padding: 6px 20px; font-size: 12px; font-weight: 700; } "
            "QPushButton:hover { border-color: #2777FF; color: #2777FF; }"
        )
        btn_try.clicked.connect(self.try_clicked.emit)
        b_layout.addWidget(btn_try, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(banner)


class HomeView(QWidget):
    """Complete Home View matching KAPPAK UI Female Hero Apple Glass V2."""

    navigate_to_module = Signal(int)
    ask_kappak_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("homeView")
        self.setStyleSheet("background-color: #F5F8FD; border: none;")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Scroll Area for responsive high DPI / smaller screens
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #F5F8FD; border: none;")
        scroll.viewport().setStyleSheet("background-color: #F5F8FD; border: none;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("homeContent")
        content.setStyleSheet("background-color: #F5F8FD; border: none;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 16, 28, 16)
        content_layout.setSpacing(16)

        # 1. Hero Section
        self.hero = HeroSection()
        self.hero.cta_clicked.connect(self.ask_kappak_requested.emit)
        content_layout.addWidget(self.hero)

        # 2. Module Cards Strip (6 Cards)
        self.module_strip = ModuleStrip()
        self.module_strip.module_navigated.connect(self.navigate_to_module.emit)
        content_layout.addWidget(self.module_strip)

        # 3. Bottom Dashboard (3 Columns: Recent Projects ~52%, Continue ~24%, AI Suggestion ~24%)
        bottom_row = QWidget()
        bottom_row.setStyleSheet("background: transparent; border: none;")
        bottom_layout = QHBoxLayout(bottom_row)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(16)

        self.recent_projects = RecentProjectsSection()
        bottom_layout.addWidget(self.recent_projects, 52)

        self.continue_work = ContinueWorkSection()
        self.continue_work.create_project_clicked.connect(lambda: self.navigate_to_module.emit(1))
        bottom_layout.addWidget(self.continue_work, 24)

        self.ai_suggestion = AiSuggestionSection()
        self.ai_suggestion.try_clicked.connect(self.ask_kappak_requested.emit)
        bottom_layout.addWidget(self.ai_suggestion, 24)

        content_layout.addWidget(bottom_row)

        scroll.setWidget(content)
        root_layout.addWidget(scroll)
