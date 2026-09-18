"""Downloader Module View for KAPPAK Studio — Apple Glass Aesthetics."""

from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path
from urllib.request import urlopen

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from kappak.core.config import get_default_projects_root, get_kappak_home
from kappak.core.db import db_session
from kappak.modules.downloader.service import (
    VideoMetadata,
    detect_platform,
    download_media,
    fetch_video_metadata,
)
from kappak.ui.icons import get_icon, get_pixmap


class DownloaderView(QWidget):
    """Full-featured Apple Glass Downloader View."""

    metadata_ready = Signal(object)
    download_progress = Signal(float, str)
    download_finished = Signal(object)
    download_failed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("downloaderView")
        self.setStyleSheet("background-color: #F5F8FD;")

        self.current_metadata: VideoMetadata | None = None

        # Connect internal async signals
        self.metadata_ready.connect(self._on_metadata_loaded)
        self.download_progress.connect(self._on_download_progress)
        self.download_finished.connect(self._on_download_completed)
        self.download_failed.connect(self._on_download_error)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Scroll container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #F5F8FD; border: none;")
        scroll.viewport().setStyleSheet("background-color: #F5F8FD; border: none;")

        content = QWidget()
        content.setStyleSheet("background-color: #F5F8FD;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 28)
        layout.setSpacing(18)

        # 1. Header with Platform Badges
        header_box = QWidget()
        h_layout = QHBoxLayout(header_box)
        h_layout.setContentsMargins(0, 0, 0, 0)

        title_box = QWidget()
        t_layout = QVBoxLayout(title_box)
        t_layout.setContentsMargins(0, 0, 0, 0)
        t_layout.setSpacing(2)

        title = QLabel("📥 Downloader")
        title.setStyleSheet("font-size: 24px; font-weight: 850; color: #0A1738;")
        t_layout.addWidget(title)

        subtitle = QLabel("Tải video đa nền tảng chất lượng cao, giữ nguyên metadata và tự động chống trùng lặp.")
        subtitle.setStyleSheet("font-size: 13px; color: #66779C; font-weight: 500;")
        t_layout.addWidget(subtitle)
        h_layout.addWidget(title_box)

        h_layout.addStretch()

        # Supported platforms pills
        platforms_box = QWidget()
        p_layout = QHBoxLayout(platforms_box)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setSpacing(8)
        p_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        for p_name, p_bg, p_fg in [
            ("TikTok", "#FFE4F1", "#BE185D"),
            ("YouTube", "#FEE2E2", "#B91C1C"),
            ("Facebook", "#EFF6FF", "#1D4ED8"),
            ("Instagram", "#FDF2F8", "#A21CAF"),
            ("Douyin", "#ECFDF5", "#047857"),
        ]:
            pill = QLabel(p_name)
            pill.setFixedHeight(26)
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setStyleSheet(
                f"background-color: {p_bg}; color: {p_fg}; border-radius: 13px; padding: 4px 12px; "
                "font-size: 11px; font-weight: 700;"
            )
            p_layout.addWidget(pill)
        h_layout.addWidget(platforms_box, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(header_box)

        # 2. Input Card (URL Paste & Analysis)
        input_card = QFrame()
        input_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        input_card.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1px solid rgba(76, 104, 153, 0.12); border-radius: 20px; }"
        )
        in_layout = QVBoxLayout(input_card)
        in_layout.setContentsMargins(24, 20, 24, 20)
        in_layout.setSpacing(14)

        in_title = QLabel("Nhập liên kết video")
        in_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #0A1738;")
        in_layout.addWidget(in_title)

        bar_row = QWidget()
        bar_layout = QHBoxLayout(bar_row)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(10)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Dán URL video (vd: https://www.tiktok.com/@... hoặc https://youtu.be/...)")
        self.url_input.setStyleSheet(
            "QLineEdit { background-color: #F8FAFD; border: 1.5px solid rgba(76, 104, 153, 0.15); "
            "border-radius: 14px; padding: 10px 16px; font-size: 13px; color: #0A1738; } "
            "QLineEdit:focus { border-color: #2777FF; background-color: #FFFFFF; }"
        )
        self.url_input.returnPressed.connect(self._analyze_link)
        bar_layout.addWidget(self.url_input, 1)

        self.btn_paste = QPushButton("Dán")
        self.btn_paste.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_paste.setStyleSheet(
            "QPushButton { background-color: #F1F6FD; color: #2777FF; border: none; border-radius: 12px; "
            "padding: 10px 18px; font-size: 13px; font-weight: 700; } "
            "QPushButton:hover { background-color: #E2EAFD; }"
        )
        self.btn_paste.clicked.connect(self._paste_clipboard)
        bar_layout.addWidget(self.btn_paste)

        self.btn_analyze = QPushButton("Phân tích Link")
        self.btn_analyze.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_analyze.setStyleSheet(
            "QPushButton { background-color: #2777FF; color: #FFFFFF; border: none; border-radius: 14px; "
            "padding: 10px 24px; font-size: 13px; font-weight: 700; } "
            "QPushButton:hover { background-color: #1B63E0; }"
        )
        self.btn_analyze.clicked.connect(self._analyze_link)
        bar_layout.addWidget(self.btn_analyze)

        in_layout.addWidget(bar_row)
        layout.addWidget(input_card)

        # 3. Preview Card (Hidden until link is analyzed)
        self.preview_card = QFrame()
        self.preview_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.preview_card.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1.5px solid rgba(39, 119, 255, 0.25); "
            "border-radius: 20px; }"
        )
        self.preview_card.setVisible(False)
        prev_layout = QVBoxLayout(self.preview_card)
        prev_layout.setContentsMargins(24, 20, 24, 20)
        prev_layout.setSpacing(14)

        prev_title = QLabel("Kết quả phân tích video")
        prev_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0A1738;")
        prev_layout.addWidget(prev_title)

        prev_row = QWidget()
        prow_layout = QHBoxLayout(prev_row)
        prow_layout.setContentsMargins(0, 0, 0, 0)
        prow_layout.setSpacing(20)

        # Thumbnail Box
        self.thumb_preview = QLabel()
        self.thumb_preview.setFixedSize(220, 125)
        self.thumb_preview.setStyleSheet("background-color: #E2E8F0; border-radius: 14px;")
        self.thumb_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_preview.setScaledContents(True)
        prow_layout.addWidget(self.thumb_preview)

        # Info & Formats
        info_col = QWidget()
        icol_layout = QVBoxLayout(info_col)
        icol_layout.setContentsMargins(0, 0, 0, 0)
        icol_layout.setSpacing(8)

        self.lbl_video_title = QLabel("Tiêu đề video")
        self.lbl_video_title.setWordWrap(True)
        self.lbl_video_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0A1738;")
        icol_layout.addWidget(self.lbl_video_title)

        tags_row = QWidget()
        trow_layout = QHBoxLayout(tags_row)
        trow_layout.setContentsMargins(0, 0, 0, 0)
        trow_layout.setSpacing(10)

        self.lbl_creator = QLabel("Kênh / Tác giả")
        self.lbl_creator.setStyleSheet("font-size: 12px; color: #66779C; font-weight: 600;")
        trow_layout.addWidget(self.lbl_creator)

        self.lbl_duration = QLabel("00:00")
        self.lbl_duration.setStyleSheet(
            "background-color: #F1F5F9; color: #0A1738; font-size: 11px; font-weight: 700; "
            "padding: 2px 8px; border-radius: 6px;"
        )
        trow_layout.addWidget(self.lbl_duration)

        self.lbl_platform = QLabel("Nền tảng")
        self.lbl_platform.setStyleSheet(
            "background-color: #E7F1FF; color: #2777FF; font-size: 11px; font-weight: 700; "
            "padding: 2px 8px; border-radius: 6px;"
        )
        trow_layout.addWidget(self.lbl_platform)
        trow_layout.addStretch()

        icol_layout.addWidget(tags_row)

        # Options Row: Quality & Project Destination
        opts_row = QWidget()
        opts_layout = QHBoxLayout(opts_row)
        opts_layout.setContentsMargins(0, 0, 0, 0)
        opts_layout.setSpacing(12)

        # Quality choice
        q_box = QWidget()
        ql_layout = QVBoxLayout(q_box)
        ql_layout.setContentsMargins(0, 0, 0, 0)
        ql_layout.setSpacing(4)
        ql_lbl = QLabel("Định dạng & Chất lượng:")
        ql_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #66779C;")
        ql_layout.addWidget(ql_lbl)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems([
            "Chất lượng tốt nhất (Best Video+Audio)",
            "1080p Full HD",
            "720p HD",
            "Chỉ lấy âm thanh (Audio MP3)",
        ])
        self.quality_combo.setStyleSheet(
            "QComboBox { background-color: #F8FAFD; border: 1px solid rgba(76, 104, 153, 0.2); "
            "border-radius: 10px; padding: 6px 12px; font-size: 12px; color: #0A1738; font-weight: 600; }"
        )
        ql_layout.addWidget(self.quality_combo)
        opts_layout.addWidget(q_box)

        # Project choice
        p_box = QWidget()
        pl_layout = QVBoxLayout(p_box)
        pl_layout.setContentsMargins(0, 0, 0, 0)
        pl_layout.setSpacing(4)
        pl_lbl = QLabel("Lưu vào Dự án:")
        pl_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #66779C;")
        pl_layout.addWidget(pl_lbl)

        self.project_combo = QComboBox()
        self.project_combo.addItem("00_Inbox (Mặc định)", None)
        self._load_projects()
        self.project_combo.setStyleSheet(
            "QComboBox { background-color: #F8FAFD; border: 1px solid rgba(76, 104, 153, 0.2); "
            "border-radius: 10px; padding: 6px 12px; font-size: 12px; color: #0A1738; font-weight: 600; }"
        )
        pl_layout.addWidget(self.project_combo)
        opts_layout.addWidget(p_box)

        icol_layout.addWidget(opts_row)
        prow_layout.addWidget(info_col, 1)

        # Big Download CTA
        self.btn_start_download = QPushButton("Tải ngay vào Dự án")
        self.btn_start_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start_download.setFixedHeight(44)
        self.btn_start_download.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2777FF, stop:1 #1D4ED8); "
            "color: #FFFFFF; border: none; border-radius: 14px; padding: 0 24px; font-size: 13px; font-weight: 800; } "
            "QPushButton:hover { background: #1B63E0; }"
        )
        self.btn_start_download.clicked.connect(self._start_download)
        prev_layout.addWidget(prev_row)
        prev_layout.addWidget(self.btn_start_download, alignment=Qt.AlignmentFlag.AlignRight)

        # Progress bar inside preview card
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background-color: #E2E8F0; border-radius: 4px; text-align: right; } "
            "QProgressBar::chunk { background-color: #2777FF; border-radius: 4px; }"
        )
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        prev_layout.addWidget(self.progress_bar)

        self.lbl_progress_status = QLabel("")
        self.lbl_progress_status.setStyleSheet("font-size: 12px; color: #2777FF; font-weight: 600;")
        self.lbl_progress_status.setVisible(False)
        prev_layout.addWidget(self.lbl_progress_status)

        layout.addWidget(self.preview_card)

        # 4. Download History & Recent Assets Table
        history_card = QFrame()
        history_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        history_card.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1px solid rgba(76, 104, 153, 0.12); border-radius: 20px; }"
        )
        hist_layout = QVBoxLayout(history_card)
        hist_layout.setContentsMargins(24, 20, 24, 20)
        hist_layout.setSpacing(14)

        hist_header = QWidget()
        hist_header.setStyleSheet("background: transparent; border: none;")
        hh_layout = QHBoxLayout(hist_header)
        hh_layout.setContentsMargins(0, 0, 0, 0)

        htitle = QLabel("Tài nguyên đã tải gần đây (Thư viện Data Studio)")
        htitle.setStyleSheet("font-size: 15px; font-weight: 800; color: #0A1738; background: transparent;")
        hh_layout.addWidget(htitle)
        hh_layout.addStretch()

        self.btn_refresh = QPushButton("Làm mới")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #2777FF; font-size: 12px; font-weight: 700; } "
            "QPushButton:hover { color: #1B63E0; }"
        )
        self.btn_refresh.clicked.connect(self._refresh_history)
        hh_layout.addWidget(self.btn_refresh)
        hist_layout.addWidget(hist_header)

        self.empty_history_lbl = QLabel("Chưa có tài nguyên nào được tải. Hãy dán một liên kết video ở trên để bắt đầu tải về.")
        self.empty_history_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_history_lbl.setStyleSheet(
            "font-size: 13px; color: #8595B2; padding: 40px; background-color: #F8FAFD; "
            "border: 1px dashed rgba(76, 104, 153, 0.20); border-radius: 14px;"
        )
        hist_layout.addWidget(self.empty_history_lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Tên tệp", "Nền tảng", "Thời lượng", "Dung lượng", "Mã SHA-256", "Thao tác"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet(
            "QTableWidget { background-color: #FFFFFF; border: 1px solid rgba(76, 104, 153, 0.10); "
            "border-radius: 12px; gridline-color: rgba(76, 104, 153, 0.08); font-size: 12px; } "
            "QHeaderView::section { background-color: #F8FAFD; padding: 8px; font-weight: 700; color: #66779C; "
            "border: none; border-bottom: 1px solid rgba(76, 104, 153, 0.12); }"
        )
        self.table.setFixedHeight(240)
        self.table.setVisible(False)
        hist_layout.addWidget(self.table)

        layout.addWidget(history_card)

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

        # Initial load of history
        self._refresh_history()

    def _paste_clipboard(self) -> None:
        from PySide6.QtWidgets import QApplication
        cb = QApplication.clipboard()
        text = cb.text().strip()
        if text:
            self.url_input.setText(text)
            self._analyze_link()

    def _load_projects(self) -> None:
        """Load projects from SQLite into project destination dropdown."""
        try:
            with db_session() as conn:
                rows = conn.execute("SELECT id, name, root_path FROM projects ORDER BY updated_at DESC").fetchall()
                for row in rows:
                    self.project_combo.addItem(f"📁 {row['name']}", row["id"])
        except Exception:
            pass

    def _analyze_link(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Chưa nhập liên kết", "Vui lòng dán liên kết video cần tải.")
            return

        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setText("Đang phân tích...")

        def _worker():
            try:
                meta = fetch_video_metadata(url)
                self.metadata_ready.emit(meta)
            except Exception as e:
                self.download_failed.emit(f"Không thể phân tích liên kết: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _on_metadata_loaded(self, meta: VideoMetadata) -> None:
        self.current_metadata = meta
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("Phân tích Link")

        self.lbl_video_title.setText(meta.title)
        self.lbl_creator.setText(f"👤 {meta.creator}")
        self.lbl_duration.setText(f"⏱️ {meta.duration_str}")
        self.lbl_platform.setText(meta.platform)

        # Load thumbnail async
        if meta.thumbnail_url:
            def _load_thumb():
                try:
                    data = urlopen(meta.thumbnail_url, timeout=5).read()
                    qimg = QImage.fromData(data)
                    pm = QPixmap.fromImage(qimg)
                    self.thumb_preview.setPixmap(pm)
                except Exception:
                    self.thumb_preview.setText("Không tải được ảnh xem trước")

            threading.Thread(target=_load_thumb, daemon=True).start()

        self.preview_card.setVisible(True)
        self.progress_bar.setVisible(False)
        self.lbl_progress_status.setVisible(False)
        self.btn_start_download.setEnabled(True)

    def _start_download(self) -> None:
        if not self.current_metadata:
            return

        self.btn_start_download.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_progress_status.setVisible(True)
        self.lbl_progress_status.setText("Đang chuẩn bị tải xuống...")

        url = self.current_metadata.url
        quality = self.quality_combo.currentText()
        project_id = self.project_combo.currentData()

        # Target directory: Project 00_Inbox or default inbox
        if project_id:
            try:
                with db_session() as conn:
                    row = conn.execute("SELECT root_path FROM projects WHERE id = ?", (project_id,)).fetchone()
                    if row:
                        dest_dir = Path(row["root_path"]) / "00_Inbox"
                    else:
                        dest_dir = get_default_projects_root() / "Default_Project" / "00_Inbox"
            except Exception:
                dest_dir = get_default_projects_root() / "Default_Project" / "00_Inbox"
        else:
            dest_dir = get_default_projects_root() / "Default_Project" / "00_Inbox"

        def _worker():
            try:
                def _prog(pct: float, msg: str):
                    self.download_progress.emit(pct, msg)

                asset = download_media(
                    url=url,
                    output_dir=dest_dir,
                    quality_choice=quality,
                    project_id=project_id,
                    progress_callback=_prog,
                )
                self.download_finished.emit(asset)
            except Exception as e:
                self.download_failed.emit(f"Lỗi khi tải video: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _on_download_progress(self, pct: float, msg: str) -> None:
        self.progress_bar.setValue(int(pct))
        self.lbl_progress_status.setText(msg)

    def _on_download_completed(self, asset) -> None:
        self.progress_bar.setValue(100)
        self.lbl_progress_status.setText("✅ Đã tải và lưu thành công vào thư viện!")
        self.btn_start_download.setEnabled(True)
        self._refresh_history()

        QMessageBox.information(
            self,
            "Tải thành công",
            f"Video đã được tải thành công và lưu vào:\n{asset.local_path}\n\n"
            f"Mã chống trùng SHA-256: {asset.sha256_hash[:12]}...",
        )

    def _on_download_error(self, err_msg: str) -> None:
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("Phân tích Link")
        self.btn_start_download.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_progress_status.setVisible(False)
        QMessageBox.critical(self, "Lỗi tải video", err_msg)

    def _refresh_history(self) -> None:
        """Fetch downloaded assets from SQLite and display in history table."""
        try:
            with db_session() as conn:
                rows = conn.execute(
                    "SELECT name, platform, duration_sec, file_size, sha256_hash, local_path "
                    "FROM assets ORDER BY created_at DESC LIMIT 20"
                ).fetchall()

            has_rows = len(rows) > 0
            self.empty_history_lbl.setVisible(not has_rows)
            self.table.setVisible(has_rows)

            self.table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                # Name
                item_name = QTableWidgetItem(r["name"])
                item_name.setToolTip(r["local_path"])
                self.table.setItem(i, 0, item_name)

                # Platform
                self.table.setItem(i, 1, QTableWidgetItem(r["platform"] or "Generic"))

                # Duration
                dur = int(r["duration_sec"] or 0)
                dur_str = f"{dur // 60:02d}:{dur % 60:02d}"
                self.table.setItem(i, 2, QTableWidgetItem(dur_str))

                # File Size
                sz_mb = (r["file_size"] or 0) / (1024 * 1024)
                self.table.setItem(i, 3, QTableWidgetItem(f"{sz_mb:.1f} MB"))

                # Hash
                h_str = (r["sha256_hash"] or "")[:10]
                self.table.setItem(i, 4, QTableWidgetItem(h_str))

                # Action button "Mở thư mục"
                p_path = r["local_path"]
                btn_open = QPushButton("Mở")
                btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_open.setStyleSheet(
                    "background-color: #F1F6FD; color: #2777FF; border: none; border-radius: 6px; padding: 2px 8px;"
                )
                btn_open.clicked.connect(lambda _, p=p_path: self._open_file_folder(p))
                self.table.setCellWidget(i, 5, btn_open)
        except Exception:
            pass

    def _open_file_folder(self, file_path_str: str) -> None:
        p = Path(file_path_str)
        folder = p.parent if p.exists() else p
        if os.name == "nt":
            os.startfile(folder)
        else:
            subprocess.run(["xdg-open", str(folder)])
