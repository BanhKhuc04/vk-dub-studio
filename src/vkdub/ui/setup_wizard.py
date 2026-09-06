from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from vkdub.domain.translation import SUPPORTED_MODELS
from vkdub.providers.tts_provider import HealthResult
from vkdub.services.app_settings import (
    AppSettings,
    detect_default_capcut_draft_root,
    load_app_settings,
    save_app_settings,
)
from vkdub.services.credential_service import CredentialStore
from vkdub.services.health_service import check_gemini, check_tts_backend, run_startup_health_checks
from vkdub.ui.background_check import BackgroundCheck
from vkdub.version import APP_NAME


class SetupWizardDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Chào mừng đến {APP_NAME} 2.0 — Thiết lập ban đầu")
        self.resize(680, 520)
        self.setMinimumSize(620, 480)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self.settings = load_app_settings()
        self.check_job: BackgroundCheck | None = None
        self.gemini_job: BackgroundCheck | None = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # Header with step breadcrumbs
        self.header_title = QLabel("CHÀO MỪNG ĐẾN VK DUB STUDIO 2.0")
        self.header_title.setObjectName("heading")
        self.header_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #72d7c1;")
        main_layout.addWidget(self.header_title)

        self.step_label = QLabel("Bước 1 / 5: Cấu hình Gemini AI")
        self.step_label.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: 600;")
        main_layout.addWidget(self.step_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #293245;")
        main_layout.addWidget(sep)

        # Pages stacked widget
        self.stack = QStackedWidget()
        self.page_gemini = self._build_gemini_page()
        self.page_voice = self._build_voice_page()
        self.page_capcut = self._build_capcut_page()
        self.page_workspace = self._build_workspace_page()
        self.page_check = self._build_system_check_page()

        self.stack.addWidget(self.page_gemini)
        self.stack.addWidget(self.page_voice)
        self.stack.addWidget(self.page_capcut)
        self.stack.addWidget(self.page_workspace)
        self.stack.addWidget(self.page_check)

        main_layout.addWidget(self.stack, 1)

        # Bottom nav buttons
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #293245;")
        main_layout.addWidget(sep2)

        nav_row = QHBoxLayout()
        self.btn_prev = QPushButton("← Quay lại")
        self.btn_prev.clicked.connect(self._prev_step)
        self.btn_prev.setEnabled(False)
        nav_row.addWidget(self.btn_prev)

        nav_row.addStretch()

        self.btn_skip = QPushButton("Thiết lập sau")
        self.btn_skip.setStyleSheet("color: #94a3b8;")
        self.btn_skip.clicked.connect(self._skip_wizard)
        nav_row.addWidget(self.btn_skip)

        self.btn_next = QPushButton("Tiếp tục →")
        self.btn_next.setObjectName("primary")
        self.btn_next.setStyleSheet("font-weight: bold; padding: 6px 18px;")
        self.btn_next.clicked.connect(self._next_step)
        nav_row.addWidget(self.btn_next)

        main_layout.addLayout(nav_row)

    # -------------------------------------------------------------
    # Page 1: Gemini
    # -------------------------------------------------------------
    def _build_gemini_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        info = QLabel(
            "Gemini AI được sử dụng để dịch thuật kịch bản, làm mượt tiếng Việt tự nhiên "
            "theo đúng nhịp đọc của từng câu thoại. API Key được lưu bảo mật bằng "
            "Windows Credential Manager."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #cbd5e1; font-size: 13px; line-height: 1.4;")
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(10)

        self.gemini_key_input = QLineEdit()
        self.gemini_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_input.setPlaceholderText("Dán API Key (AIzaSy...)")
        try:
            existing_key = CredentialStore().get()
        except RuntimeError:
            existing_key = None
        if existing_key:
            self.gemini_key_input.setText(existing_key)
        form.addRow("Gemini API Key:", self.gemini_key_input)

        self.gemini_model_combo = QComboBox()
        self.gemini_model_combo.addItems(SUPPORTED_MODELS)
        self.gemini_model_combo.setCurrentText(self.settings.gemini_model)
        form.addRow("Mô hình AI:", self.gemini_model_combo)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.btn_test_gemini = QPushButton("Kiểm tra kết nối")
        self.btn_test_gemini.clicked.connect(self._test_gemini_key)
        btn_row.addWidget(self.btn_test_gemini)

        self.btn_get_key = QPushButton("🌐 Hướng dẫn lấy API Key")
        self.btn_get_key.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://aistudio.google.com/app/apikey"))
        )
        btn_row.addWidget(self.btn_get_key)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.gemini_status_lbl = QLabel()
        self.gemini_status_lbl.setWordWrap(True)
        layout.addWidget(self.gemini_status_lbl)

        layout.addStretch()
        return w

    def _test_gemini_key(self) -> None:
        if self.gemini_job is not None:
            return
        key = self.gemini_key_input.text().strip()
        if not key:
            self.gemini_status_lbl.setText("Vui lòng nhập API Key.")
            return
        model = self.gemini_model_combo.currentText()
        self.gemini_status_lbl.setText("Đang kiểm tra Gemini…")
        self.btn_test_gemini.setEnabled(False)
        self.gemini_job = BackgroundCheck(lambda: check_gemini(model, key))
        self.gemini_job.succeeded.connect(self._gemini_result)
        self.gemini_job.failed.connect(self.gemini_status_lbl.setText)
        self.gemini_job.finished.connect(self._gemini_finished)
        self.gemini_job.start()

    def _gemini_result(self, result: HealthResult) -> None:
        self.gemini_status_lbl.setText(result.message)

    def _gemini_finished(self) -> None:
        self.gemini_job = None
        self.btn_test_gemini.setEnabled(True)

    # -------------------------------------------------------------
    # Page 2: Voice Engine
    # -------------------------------------------------------------
    def _build_voice_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(14)

        info = QLabel(
            "VK Dub Studio 2.0 hỗ trợ 2 backend tạo giọng đọc tiếng Việt:\n"
            "• VieNeu Local: Chạy offline hoàn toàn trên máy tính, v3 Turbo tối ưu CPU.\n"
            "• CapCut TTS (Tùy chọn): Tận dụng kho giọng CapCut qua API trực tuyến."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #cbd5e1; font-size: 13px; line-height: 1.4;")
        layout.addWidget(info)

        self.radio_vieneu = QRadioButton("VieNeu Local (Mặc định — Khuyên dùng)")
        self.radio_vieneu.setChecked(self.settings.tts_backend == "vieneu_local")
        self.radio_vieneu.setStyleSheet("font-weight: bold; font-size: 13px; color: #72d7c1;")

        self.radio_capcut_tts = QRadioButton("CapCut TTS API (Thử nghiệm / Online)")
        self.radio_capcut_tts.setChecked(self.settings.tts_backend == "capcut_tts")
        self.radio_capcut_tts.setStyleSheet("font-size: 13px; color: #cbd5e1;")

        self.voice_group = QButtonGroup(self)
        self.voice_group.addButton(self.radio_vieneu)
        self.voice_group.addButton(self.radio_capcut_tts)

        layout.addWidget(self.radio_vieneu)
        vieneu_desc = QLabel(
            "  ✓ Hoàn toàn cục bộ, không gửi audio ra ngoài, không giới hạn ký tự."
        )
        vieneu_desc.setStyleSheet("color: #94a3b8; font-size: 12px; margin-bottom: 6px;")
        layout.addWidget(vieneu_desc)

        layout.addWidget(self.radio_capcut_tts)
        capcut_desc = QLabel("  ⚠️ Yêu cầu kết nối mạng, phụ thuộc máy chủ CapCut TTS.")
        capcut_desc.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(capcut_desc)
        self.voice_status = QLabel()
        self.voice_status.setWordWrap(True)
        btn_check_voice = QPushButton("Kiểm tra Voice Engine")
        btn_check_voice.clicked.connect(self._check_voice)
        layout.addWidget(btn_check_voice)
        layout.addWidget(self.voice_status)
        self._check_voice()

        layout.addStretch()
        return w

    # -------------------------------------------------------------
    # Page 3: CapCut Folder
    # -------------------------------------------------------------
    def _check_voice(self) -> None:
        backend = "capcut_tts" if self.radio_capcut_tts.isChecked() else "vieneu_local"
        self.voice_status.setText(check_tts_backend(backend).message)

    def _build_capcut_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        info = QLabel(
            "CapCut Draft Root là nơi lưu các project CapCut trên máy. "
            "App ghi nhớ thư mục này và chỉ tạo project mới với mã riêng."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #cbd5e1; font-size: 13px; line-height: 1.4;")
        layout.addWidget(info)

        detected = detect_default_capcut_draft_root()
        self.capcut_detect_status = QLabel()
        if detected:
            self.capcut_detect_status.setText(
                "✓ Đã tự động tìm thấy thư mục CapCut Draft trên Windows!"
            )
            self.capcut_detect_status.setStyleSheet(
                "color: #34d399; font-weight: bold; font-size: 13px;"
            )
        else:
            self.capcut_detect_status.setText(
                "ℹ Chưa phát hiện thư mục mặc định CapCut. Bạn có thể chọn thư mục bên dưới."
            )
            self.capcut_detect_status.setStyleSheet("color: #fbbf24; font-size: 12px;")
        layout.addWidget(self.capcut_detect_status)

        form = QFormLayout()
        self.capcut_path_input = QLineEdit()
        self.capcut_path_input.setText(self.settings.capcut_draft_root)
        form.addRow("Đường dẫn CapCut Draft:", self.capcut_path_input)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_browse = QPushButton("📁 Chọn thư mục khác…")
        btn_browse.clicked.connect(self._browse_capcut_folder)
        btn_row.addWidget(btn_browse)

        if detected:
            btn_use_detected = QPushButton("Dùng thư mục tự động phát hiện")
            btn_use_detected.clicked.connect(lambda: self.capcut_path_input.setText(str(detected)))
            btn_row.addWidget(btn_use_detected)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()
        return w

    def _browse_capcut_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục CapCut Draft")
        if path:
            self.capcut_path_input.setText(path)

    # -------------------------------------------------------------
    # Page 4: Workspace
    # -------------------------------------------------------------
    def _build_workspace_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        info = QLabel(
            "Cấu hình thư mục làm việc mặc định và ngôn ngữ dịch thuật. "
            "Các thiết lập này sẽ được ghi nhớ cho mọi lần mở sau."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #cbd5e1; font-size: 13px;")
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(10)

        self.workspace_input = QLineEdit()
        self.workspace_input.setText(self.settings.workspace_root)
        ws_row = QHBoxLayout()
        ws_row.addWidget(self.workspace_input, 1)
        btn_ws = QPushButton("Chọn…")
        btn_ws.clicked.connect(self._browse_workspace)
        ws_row.addWidget(btn_ws)
        form.addRow("Thư mục Workspace:", ws_row)

        self.src_lang_combo = QComboBox()
        for title, code in (
            ("Tự động nhận diện", "auto"),
            ("Tiếng Trung (zh)", "zh"),
            ("Tiếng Anh (en)", "en"),
            ("Tiếng Nhật (ja)", "ja"),
            ("Tiếng Hàn (ko)", "ko"),
        ):
            self.src_lang_combo.addItem(title, code)
        self.src_lang_combo.setCurrentIndex(
            self.src_lang_combo.findData(self.settings.source_language)
        )
        form.addRow("Ngôn ngữ nguồn mặc định:", self.src_lang_combo)

        self.tgt_lang_lbl = QLabel("Tiếng Việt (vi)")
        self.tgt_lang_lbl.setStyleSheet("color: #72d7c1; font-weight: bold;")
        form.addRow("Dịch sang:", self.tgt_lang_lbl)

        layout.addLayout(form)
        layout.addStretch()
        return w

    def _browse_workspace(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục Workspace")
        if path:
            self.workspace_input.setText(path)

    # -------------------------------------------------------------
    # Page 5: System Check
    # -------------------------------------------------------------
    def _build_system_check_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        info = QLabel("Tổng kết kiểm tra hệ thống trước khi sẵn sàng sử dụng:")
        info.setStyleSheet("color: #cbd5e1; font-size: 13px; font-weight: bold;")
        layout.addWidget(info)

        self.check_list_box = QFrame()
        self.check_list_box.setObjectName("systemChecks")
        self.check_list_box.setStyleSheet(
            "QFrame#systemChecks { background: #0f141e; border: 1px solid #232d3f; "
            "border-radius: 6px; }"
        )
        self.check_layout = QVBoxLayout(self.check_list_box)
        self.check_layout.setSpacing(8)
        check_scroll = QScrollArea()
        check_scroll.setWidgetResizable(True)
        check_scroll.setWidget(self.check_list_box)
        layout.addWidget(check_scroll, 1)

        btn_recheck = QPushButton("🔄 Kiểm tra lại")
        btn_recheck.clicked.connect(self._refresh_checks)
        layout.addWidget(btn_recheck)

        layout.addStretch()
        return w

    def _refresh_checks(self) -> None:
        # Clear existing items
        while self.check_layout.count():
            item = self.check_layout.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        # Gather temporary settings
        temp_settings = AppSettings(
            gemini_model=self.gemini_model_combo.currentText(),
            tts_backend="capcut_tts" if self.radio_capcut_tts.isChecked() else "vieneu_local",
            capcut_draft_root=self.capcut_path_input.text().strip(),
            workspace_root=self.workspace_input.text().strip(),
        )

        if self.check_job is not None:
            return
        self.check_job = BackgroundCheck(lambda: run_startup_health_checks(temp_settings))
        self.check_job.succeeded.connect(self._show_checks)
        self.check_job.finished.connect(self._checks_finished)
        self.check_job.start()

    def _checks_finished(self) -> None:
        self.check_job = None

    def _show_checks(self, results: list[HealthResult]) -> None:
        for res in results:
            icon = "✓" if res.ok else "⚠️"
            color = "#34d399" if res.ok else "#fbbf24"
            lbl = QLabel(f"{icon}  <b>{res.title}</b>: {res.message}")
            lbl.setStyleSheet(f"color: {color}; font-size: 12px; padding: 4px; border: none;")
            lbl.setWordWrap(True)
            self.check_layout.addWidget(lbl)

    # -------------------------------------------------------------
    # Navigation Logic
    # -------------------------------------------------------------
    def _next_step(self) -> None:
        idx = self.stack.currentIndex()
        if idx == 0:
            # Save gemini key if filled
            key = self.gemini_key_input.text().strip()
            if key:
                try:
                    CredentialStore().save(key)
                except Exception:
                    self.gemini_status_lbl.setText("Không lưu được khóa vào Windows. Hãy thử lại.")
                    return
        elif idx == 3:
            # Entering step 5, refresh system checks
            self._refresh_checks()

        if idx < self.stack.count() - 1:
            self.stack.setCurrentIndex(idx + 1)
            self._update_step_ui()
        else:
            # Finish wizard
            self._finish_wizard()

    def _prev_step(self) -> None:
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._update_step_ui()

    def _update_step_ui(self) -> None:
        idx = self.stack.currentIndex()
        titles = [
            "Bước 1 / 5: Cấu hình Gemini AI",
            "Bước 2 / 5: Chọn Voice Engine",
            "Bước 3 / 5: Kết nối thư mục CapCut Draft",
            "Bước 4 / 5: Thiết lập Workspace",
            "Bước 5 / 5: Kiểm tra hệ thống",
        ]
        self.step_label.setText(titles[idx])
        self.btn_prev.setEnabled(idx > 0)
        self.btn_next.setText("Hoàn tất ✓" if idx == self.stack.count() - 1 else "Tiếp tục →")

    def _finish_wizard(self) -> None:
        self.settings.gemini_model = self.gemini_model_combo.currentText()
        self.settings.tts_backend = (
            "capcut_tts" if self.radio_capcut_tts.isChecked() else "vieneu_local"
        )
        self.settings.capcut_draft_root = self.capcut_path_input.text().strip()
        self.settings.workspace_root = self.workspace_input.text().strip()
        self.settings.source_language = self.src_lang_combo.currentData()
        self.settings.wizard_completed = True
        try:
            save_app_settings(self.settings)
        except (OSError, ValueError):
            self.step_label.setText(
                "Không lưu được cấu hình. Kiểm tra đường dẫn và model rồi thử lại."
            )
            return
        self.accept()

    def _skip_wizard(self) -> None:
        self._finish_wizard()
