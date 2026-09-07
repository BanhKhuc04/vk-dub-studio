import threading

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from vkdub.services.update_service import (
    UpdateInfo,
    apply_update_and_restart,
    download_installer,
    launch_installer,
)
from vkdub.utils.paths import data_root
from vkdub.version import __version__


class UpdateDialog(QDialog):
    """Dialog displaying new release information, changelog and download progress (Phase 9)."""

    download_progress = Signal(int, int)  # downloaded_bytes, total_bytes
    download_finished = Signal(bool, str)  # success, message

    def __init__(self, update_info: UpdateInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.update_info = update_info
        self._cancelled = False
        self._download_thread: threading.Thread | None = None

        self.setWindowTitle("Đã có phiên bản mới — VK Dub Studio")
        self.resize(520, 420)
        self.setMinimumSize(480, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # 1. Header
        header = QLabel("🎉 ĐÃ CÓ BẢN CẬP NHẬT MỚI!")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #34d399;")
        layout.addWidget(header)

        # Version comparison
        # Version comparison & patch indicator
        ver_text = (
            f"Phiên bản hiện tại: <b>v{__version__}</b> ➔ "
            f"Phiên bản mới: <b style='color: #38bdf8;'>v{self.update_info.version}</b>"
        )
        if self.update_info.has_patch:
            patch_mb = self.update_info.patch_size_bytes / (1024 * 1024)
            ver_text += (
                f"<br><span style='color: #34d399; font-weight: bold; font-size: 11px;'>"
                f"⚡ Hỗ trợ Bản vá siêu nhẹ (~{patch_mb:.1f} MB) — Cập nhật tức thì không cần tải lại bộ cài 300MB</span>"
            )
        ver_lbl = QLabel(ver_text)
        ver_lbl.setStyleSheet("font-size: 12px;")
        layout.addWidget(ver_lbl)

        # 2. Changelog box
        layout.addWidget(QLabel("Chi tiết các thay đổi & cải tiến:"))
        self.txt_changelog = QTextBrowser()
        self.txt_changelog.setStyleSheet(
            "background-color: #0f172a; color: #e2e8f0; border: 1px solid #334155; "
            "border-radius: 6px; padding: 8px; font-size: 12px;"
        )
        md_lines = ["### Nhật ký phiên bản:"]
        for line in self.update_info.changelog:
            md_lines.append(f"• {line}")
        self.txt_changelog.setMarkdown("\n\n".join(md_lines))
        layout.addWidget(self.txt_changelog, 1)

        # 3. Progress Section (Hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #94a3b8;")
        self.lbl_status.hide()
        layout.addWidget(self.lbl_status)

        # 4. Action buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_later = QPushButton("Để sau")
        self.btn_later.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_later)

        if self.update_info.has_patch:
            self.btn_full_installer = QPushButton("Tải bộ cài đầy đủ")
            self.btn_full_installer.setToolTip("Tải file Setup exe đầy đủ (~300MB)")
            self.btn_full_installer.clicked.connect(lambda: self._start_download(use_patch=False))
            btn_row.addWidget(self.btn_full_installer)

        self.btn_update = QPushButton(
            "⚡ CẬP NHẬT NHANH (BẢN VÁ)" if self.update_info.has_patch else "CẬP NHẬT NGAY"
        )
        self.btn_update.setObjectName("primary")
        self.btn_update.setStyleSheet(
            "font-weight: bold; padding: 8px 18px; background-color: #0284c7; color: white;"
        )
        self.btn_update.clicked.connect(lambda: self._start_download(use_patch=self.update_info.has_patch))
        btn_row.addWidget(self.btn_update)

        layout.addLayout(btn_row)

        self.download_progress.connect(self._on_progress)
        self.download_finished.connect(self._on_finished)

    def _start_download(self, use_patch: bool = True) -> None:
        self._is_patch = use_patch and self.update_info.has_patch
        self.btn_update.setEnabled(False)
        if hasattr(self, "btn_full_installer"):
            self.btn_full_installer.setEnabled(False)
        self.btn_later.setText("Hủy tải")
        self.progress_bar.show()
        self.lbl_status.show()

        cache_dir = data_root() / "updates"
        cache_dir.mkdir(parents=True, exist_ok=True)

        if self._is_patch:
            self.lbl_status.setText("Đang kết nối tải bản vá siêu nhẹ (~vài MB)…")
            target_path = cache_dir / f"VK-Dub-Studio-Patch-v{self.update_info.version}.zip"
            download_url = self.update_info.patch_url
            expected_hash = self.update_info.patch_sha256
        else:
            self.lbl_status.setText("Đang kết nối tải bản cài đặt đầy đủ…")
            target_path = cache_dir / f"VK-Dub-Studio-Setup-v{self.update_info.version}.exe"
            download_url = self.update_info.installer_url
            expected_hash = self.update_info.sha256

        self._target_path = target_path

        def worker() -> None:
            def on_prog(d: int, t: int) -> None:
                self.download_progress.emit(d, t)

            success = download_installer(
                url=download_url,
                target_path=target_path,
                expected_sha256=expected_hash,
                progress_callback=on_prog,
                is_cancelled=lambda: self._cancelled,
            )
            if success:
                self.download_finished.emit(True, "Tải về và xác thực SHA-256 thành công!")
            else:
                msg = (
                    "Đã hủy tải bản cập nhật."
                    if self._cancelled
                    else "Lỗi tải hoặc mã băm SHA-256 không hợp lệ."
                )
                self.download_finished.emit(False, msg)

        self._download_thread = threading.Thread(target=worker, daemon=True)
        self._download_thread.start()

    def _on_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            pct = int(downloaded * 100 / total)
            self.progress_bar.setValue(pct)
            mb_down = downloaded / (1024 * 1024)
            mb_tot = total / (1024 * 1024)
            self.lbl_status.setText(f"Đang tải… {mb_down:.1f} MB / {mb_tot:.1f} MB ({pct}%)")
        else:
            mb_down = downloaded / (1024 * 1024)
            self.lbl_status.setText(f"Đang tải… {mb_down:.1f} MB")

    def _on_finished(self, success: bool, message: str) -> None:
        self.btn_update.setEnabled(True)
        if hasattr(self, "btn_full_installer"):
            self.btn_full_installer.setEnabled(True)
        self.lbl_status.setText(message)
        if success:
            self.progress_bar.setValue(100)
            is_patch = getattr(self, "_is_patch", False)
            title = "Bản vá đã sẵn sàng" if is_patch else "Sẵn sàng cài đặt"
            text = (
                f"Bản vá siêu nhẹ v{self.update_info.version} đã tải xong.\n"
                "Ứng dụng sẽ khởi động lại trong 2 giây để cập nhật ngay.\n"
                "Bạn có muốn tiếp tục?"
                if is_patch
                else f"Bản cập nhật v{self.update_info.version} đã sẵn sàng.\n"
                "Ứng dụng sẽ đóng lại để tiến hành cài đặt ngay bây giờ.\n"
                "Bạn có muốn tiếp tục?"
            )
            ret = QMessageBox.question(
                self,
                title,
                text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret == QMessageBox.StandardButton.Yes:
                try:
                    if is_patch:
                        from vkdub.services.update_service import apply_patch_and_restart

                        apply_patch_and_restart(self._target_path)
                    else:
                        apply_update_and_restart(self._target_path, silent=False)
                    app = QApplication.instance()
                    if app is not None:
                        app.quit()
                except Exception as exc:
                    err_msg = f"Không thể áp dụng bản cập nhật: {exc}"
                    QMessageBox.critical(self, "Lỗi cập nhật", err_msg)
            else:
                self.accept()
        else:
            if not self._cancelled:
                QMessageBox.warning(self, "Lỗi cập nhật", message)

    def reject(self) -> None:
        if self._download_thread and self._download_thread.is_alive():
            self._cancelled = True
        super().reject()
