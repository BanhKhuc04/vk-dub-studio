from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from vkdub.domain.translation import SUPPORTED_MODELS
from vkdub.providers.tts_provider import HealthResult
from vkdub.services.api_settings import ApiSettings, save_settings
from vkdub.services.app_settings import (
    detect_default_capcut_draft_root,
    load_app_settings,
    save_app_settings,
)
from vkdub.services.credential_service import (
    CredentialStore,
)
from vkdub.services.health_service import (
    check_capcut_root,
    check_gemini_generation,
    check_tts_backend,
)
from vkdub.services.update_service import (
    DEFAULT_UPDATE_FEED_BETA,
    DEFAULT_UPDATE_FEED_STABLE,
    fetch_update_info,
    is_newer_version,
)
from vkdub.services.voice_catalog import delete_voice, engine_root, read_catalog, rename_voice
from vkdub.ui.add_voice_dialog import AddVoiceDialog
from vkdub.ui.background_check import BackgroundCheck
from vkdub.ui.update_dialog import UpdateDialog
from vkdub.utils.paths import data_root
from vkdub.version import APP_BRANDING, __version__

if TYPE_CHECKING:
    from vkdub.ui.main_window import MainWindow


def section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #72d7c1; margin-top: 4px;")
    return lbl


def info_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: #929fb5; font-size: 12px;")
    return lbl


class SettingsDialog(QDialog):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.main_window = window
        self.setWindowTitle(f"⚙ Cài đặt 2.0 — {APP_BRANDING}")
        self.resize(860, 620)
        self.setMinimumSize(760, 540)
        self.setWindowModality(Qt.WindowModality.WindowModal)

        self.app_settings = load_app_settings()
        self.gemini_job: BackgroundCheck | None = None
        self.update_job: BackgroundCheck | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("⚙ CÀI ĐẶT HỆ THỐNG")
        title.setObjectName("heading")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #293245; border-radius: 6px; "
            "background: #141a26; padding: 12px; }"
            "QTabBar::tab { background: #10141d; color: #929fb5; padding: 8px 18px; "
            "font-weight: 600; border-top-left-radius: 4px; border-top-right-radius: 4px; "
            "margin-right: 2px; }"
            "QTabBar::tab:selected { background: #237761; color: white; }"
        )

        # 6 tabs as per VK_DUB_STUDIO_V2_SPEC.md Section 21
        self.tab_general = self._build_general_tab()
        self.tab_ai = self._build_ai_tab()
        self.tab_voice = self._build_voice_tab()
        self.tab_capcut = self._build_capcut_tab()
        self.tab_update = self._build_update_tab()
        self.tab_advanced = self._build_advanced_tab()

        self.tabs.addTab(self.tab_general, "Chung")
        self.tabs.addTab(self.tab_ai, "AI")
        self.tabs.addTab(self.tab_voice, "Voice")
        self.tabs.addTab(self.tab_capcut, "CapCut")
        self.tabs.addTab(self.tab_update, "Cập nhật")
        self.tabs.addTab(self.tab_advanced, "Nâng cao")

        # Backward compatibility aliases for existing controllers/tests
        self.tab_video = self.tab_advanced
        self.tab_api = self.tab_ai

        layout.addWidget(self.tabs, 1)

        bottom = QHBoxLayout()
        bottom.addStretch()
        btn_close = QPushButton("Đóng")
        btn_close.setObjectName("primary")
        btn_close.clicked.connect(self.accept)
        bottom.addWidget(btn_close)
        layout.addLayout(bottom)

        self.refresh()

    # -------------------------------------------------------------
    # 1. TAB CHUNG (General)
    # -------------------------------------------------------------
    def _build_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(14)

        layout.addWidget(section_label("THƯ MỤC LÀM VIỆC & DỰ ÁN"))
        form = QFormLayout()
        form.setSpacing(10)

        # Workspace Root
        ws_row = QHBoxLayout()
        self.workspace_input = QLineEdit()
        self.workspace_input.setText(self.app_settings.workspace_root)
        btn_ws_browse = QPushButton("Chọn…")
        btn_ws_browse.clicked.connect(self._browse_workspace)
        ws_row.addWidget(self.workspace_input, 1)
        ws_row.addWidget(btn_ws_browse)
        form.addRow("Thư mục Workspace:", ws_row)

        # Default Output Folder
        out_row = QHBoxLayout()
        self.default_output_input = QLineEdit()
        self.default_output_input.setPlaceholderText("Chưa chọn thư mục mặc định")
        self.default_output_input.setText(self.app_settings.default_output)
        btn_browse = QPushButton("Chọn…")
        btn_browse.clicked.connect(self._browse_default_output)
        out_row.addWidget(self.default_output_input, 1)
        out_row.addWidget(btn_browse)
        form.addRow("Thư mục xuất video:", out_row)

        self.chk_autosave = QCheckBox("Tự động lưu dự án định kỳ và khi có thay đổi")
        self.chk_autosave.setChecked(self.app_settings.autosave)
        form.addRow("Tự động lưu:", self.chk_autosave)

        layout.addLayout(form)

        layout.addWidget(section_label("NGÔN NGỮ & GIAO DIỆN"))
        form_lang = QFormLayout()
        form_lang.setSpacing(10)

        self.pref_source_lang = QComboBox()
        for title, code in (
            ("Tự động nhận diện", "auto"),
            ("Tiếng Trung (zh)", "zh"),
            ("Tiếng Anh (en)", "en"),
            ("Tiếng Nhật (ja)", "ja"),
            ("Tiếng Hàn (ko)", "ko"),
        ):
            self.pref_source_lang.addItem(title, code)
        form_lang.addRow("Ngôn ngữ nguồn mặc định:", self.pref_source_lang)

        theme_lbl = QLabel("Chế độ: Dark Studio (Tối ưu biên tập video)")
        theme_lbl.setStyleSheet("color: #72d7c1; font-weight: 600;")
        form_lang.addRow("Giao diện:", theme_lbl)

        layout.addLayout(form_lang)

        btn_save_gen = QPushButton("Lưu cài đặt chung")
        btn_save_gen.clicked.connect(self._save_general_settings)
        layout.addWidget(btn_save_gen)

        layout.addStretch()
        return widget

    def _browse_workspace(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục Workspace")
        if path:
            self.workspace_input.setText(path)

    def _browse_default_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất video mặc định")
        if path:
            self.default_output_input.setText(path)

    def _save_general_settings(self) -> None:
        self.app_settings = load_app_settings()
        self.app_settings.default_output = self.default_output_input.text().strip()
        self.app_settings.autosave = self.chk_autosave.isChecked()
        self.app_settings.workspace_root = self.workspace_input.text().strip()
        self.app_settings.source_language = self.pref_source_lang.currentData()
        if not self._persist_settings():
            return
        QMessageBox.information(self, "Thành công", "Đã lưu thiết lập Chung.")

    # -------------------------------------------------------------
    # 2. TAB AI (Gemini Translation & Cost)
    # -------------------------------------------------------------
    def _build_ai_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        layout.addWidget(section_label("GOOGLE GEMINI API (DỊCH VÀ BIÊN TẬP KỊCH BẢN)"))
        layout.addWidget(
            info_label(
                "Gemini dịch transcript sang tiếng Việt mượt mà, "
                "đúng ngữ cảnh và ngắt câu theo timeline. "
                "API Key được lưu an toàn trong Windows Credential Manager."
            )
        )

        form = QFormLayout()
        form.setSpacing(8)

        self.gemini_key_input = QLineEdit()
        self.gemini_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_input.setPlaceholderText("Nhập Gemini API Key mới")
        form.addRow("Gemini API Key:", self.gemini_key_input)

        self.gemini_model_combo = QComboBox()
        self.gemini_model_combo.addItems(SUPPORTED_MODELS)
        self.gemini_model_combo.setCurrentText(self.app_settings.gemini_model)
        form.addRow("Mô hình Gemini:", self.gemini_model_combo)

        layout.addLayout(form)

        key_act = QHBoxLayout()
        btn_save_key = QPushButton("Lưu khóa")
        btn_save_key.clicked.connect(self._save_gemini_key)
        btn_del_key = QPushButton("Xóa khóa")
        btn_del_key.clicked.connect(self._delete_gemini_key)
        btn_test_gemini = QPushButton("Kiểm tra dịch thử")
        btn_test_gemini.clicked.connect(self._test_gemini)
        btn_get_key = QPushButton("🌐 Lấy API Key")
        btn_get_key.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://aistudio.google.com/app/apikey"))
        )
        key_act.addWidget(btn_save_key)
        key_act.addWidget(btn_del_key)
        key_act.addWidget(btn_test_gemini)
        key_act.addWidget(btn_get_key)
        btn_save_model = QPushButton("Lưu model")
        btn_save_model.clicked.connect(self._save_model)
        key_act.addWidget(btn_save_model)
        key_act.addStretch()
        layout.addLayout(key_act)

        self.gemini_status_lbl = QLabel("Chưa kiểm tra.")
        self.gemini_status_lbl.setStyleSheet("color: #f6c676;")
        layout.addWidget(self.gemini_status_lbl)

        layout.addWidget(section_label("HẠN MỨC & QUẢN LÝ CHI PHÍ"))
        form_cost = QFormLayout()
        form_cost.setSpacing(6)

        self.combo_mode = QComboBox()
        self.combo_mode.addItem("Gói Miễn phí (hạn mức theo tài khoản)", "FREE_TIER")
        self.combo_mode.addItem("Gói Trả phí (Pay-as-you-go)", "PAID")
        form_cost.addRow("Chế độ tài khoản:", self.combo_mode)

        self.spin_usd_vnd = QDoubleSpinBox()
        self.spin_usd_vnd.setRange(1000, 100000)
        self.spin_usd_vnd.setValue(25000)
        self.spin_usd_vnd.setSuffix(" đ/USD")
        form_cost.addRow("Tỷ giá USD/VND:", self.spin_usd_vnd)

        self.spin_budget_vnd = QDoubleSpinBox()
        self.spin_budget_vnd.setRange(0, 100000000)
        self.spin_budget_vnd.setValue(0)
        self.spin_budget_vnd.setSuffix(" VNĐ")
        form_cost.addRow("Ngân sách tháng:", self.spin_budget_vnd)

        self.spin_warning_pct = QDoubleSpinBox()
        self.spin_warning_pct.setRange(1, 100)
        self.spin_warning_pct.setValue(80)
        self.spin_warning_pct.setSuffix(" %")
        form_cost.addRow("Cảnh báo khi đạt:", self.spin_warning_pct)

        layout.addLayout(form_cost)

        cost_act = QHBoxLayout()
        btn_save_cost = QPushButton("Lưu cài đặt chi phí")
        btn_save_cost.clicked.connect(self._save_cost_settings)
        btn_reset_stats = QPushButton("Đặt lại thống kê")
        btn_reset_stats.clicked.connect(self._reset_cost_stats)
        cost_act.addWidget(btn_save_cost)
        cost_act.addWidget(btn_reset_stats)
        cost_act.addStretch()
        layout.addLayout(cost_act)

        layout.addStretch()
        return widget

    def _save_gemini_key(self) -> None:
        key = self.gemini_key_input.text().strip()
        if not key or any(c.isspace() for c in key):
            QMessageBox.warning(
                self, "Lỗi", "Vui lòng nhập API Key hợp lệ (không chứa khoảng trắng)."
            )
            return
        try:
            CredentialStore().save(key)
            self.gemini_key_input.clear()
            self.gemini_status_lbl.setText("✓ Đã lưu an toàn trong Windows Credential Manager.")
            self.app_settings.gemini_model = self.gemini_model_combo.currentText()
            save_app_settings(self.app_settings)
        except Exception as exc:
            self.gemini_status_lbl.setText(f"Lỗi: {exc}")

    def _delete_gemini_key(self) -> None:
        try:
            CredentialStore().delete()
            self.gemini_key_input.clear()
            self.gemini_status_lbl.setText("Đã xóa Gemini API Key khỏi máy tính.")
        except Exception as exc:
            self.gemini_status_lbl.setText(f"Lỗi: {exc}")

    def _save_model(self) -> None:
        self.app_settings = load_app_settings()
        self.app_settings.gemini_model = self.gemini_model_combo.currentText()
        self._persist_settings()

    def _test_gemini(self) -> None:
        if self.gemini_job is not None:
            return
        model = self.gemini_model_combo.currentText()
        key = self.gemini_key_input.text().strip() or None
        self.gemini_status_lbl.setText("Đang dịch thử một câu mẫu…")
        self.gemini_job = BackgroundCheck(lambda: check_gemini_generation(model, key))
        self.gemini_job.succeeded.connect(self._gemini_result)
        self.gemini_job.failed.connect(self.gemini_status_lbl.setText)
        self.gemini_job.finished.connect(self._gemini_finished)
        self.gemini_job.start()

    def _gemini_result(self, result: HealthResult) -> None:
        self.gemini_status_lbl.setText(result.message)

    def _gemini_finished(self) -> None:
        self.gemini_job = None

    def _persist_settings(self) -> bool:
        try:
            save_app_settings(self.app_settings)
        except (OSError, ValueError):
            QMessageBox.warning(self, "Chưa lưu", "Kiểm tra cấu hình và quyền ghi rồi thử lại.")
            return False
        self.main_window._settings_applied()
        return True

    def _save_cost_settings(self) -> None:
        try:
            settings = ApiSettings(
                mode=self.combo_mode.currentData(),
                usd_vnd=self.spin_usd_vnd.value(),
                budget_vnd=self.spin_budget_vnd.value(),
                warning_percent=self.spin_warning_pct.value(),
            )
            save_settings(settings)
            QMessageBox.information(self, "Thành công", "Đã lưu cài đặt chi phí.")
        except Exception as exc:
            QMessageBox.warning(self, "Lỗi", str(exc))

    def _reset_cost_stats(self) -> None:
        from vkdub.services.usage_service import UsageLedger

        UsageLedger().reset()
        QMessageBox.information(self, "Thành công", "Đã đặt lại thống kê chi phí.")

    # -------------------------------------------------------------
    # 3. TAB VOICE (VieNeu Local & CapCut TTS)
    # -------------------------------------------------------------
    def _build_voice_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setSpacing(14)

        layout.addWidget(section_label("ĐỘNG CƠ GIỌNG ĐỌC (VOICE ENGINE 2.0)"))
        layout.addWidget(
            info_label(
                "1. Chọn VieNeu hoặc CapCut → 2. Chọn giọng → 3. Bấm Nghe thử. "
                "Giọng được lưu ngay khi chọn. Duyệt kịch bản ở màn hình chính để tạo voice."
                " CapCut gửi câu đọc lên dịch vụ; VieNeu xử lý trên máy."
            )
        )

        form = QFormLayout()
        form.setSpacing(10)

        self.voice_backend_combo = QComboBox()
        self.voice_backend_combo.addItem(
            "VieNeu — dùng offline, thêm được giọng riêng", "vieneu_local"
        )
        self.voice_backend_combo.addItem("CapCut — giọng có sẵn, cần Internet", "capcut_tts")
        self.voice_backend_combo.addItem("Vbee — Lồng tiếng tự động (Trình duyệt / API)", "vbee")
        current_provider = self.main_window.project.voice.provider or self.app_settings.tts_backend
        backend_idx = self.voice_backend_combo.findData(current_provider)
        self.voice_backend_combo.setCurrentIndex(max(0, backend_idx))
        self.voice_backend_combo.currentIndexChanged.connect(self._on_voice_backend_changed)
        form.addRow("Dùng giọng từ:", self.voice_backend_combo)

        self.vbee_mode_combo = QComboBox()
        self.vbee_mode_combo.addItem(
            "🌐 Trình duyệt tự động (Vbee Dubbing Studio — Edge/Chrome)", "browser"
        )
        self.vbee_mode_combo.addItem(
            "⚡ API chính thức (Vbee Realtime API — Dùng App ID & Token)", "api"
        )
        current_vbee_mode = getattr(self.app_settings, "vbee_mode", "browser")
        vbee_mode_idx = self.vbee_mode_combo.findData(current_vbee_mode)
        self.vbee_mode_combo.setCurrentIndex(max(0, vbee_mode_idx))
        self.vbee_mode_combo.currentIndexChanged.connect(self._on_vbee_mode_changed)

        self.lbl_vbee_mode = QLabel("Chế độ Vbee:")
        form.addRow(self.lbl_vbee_mode, self.vbee_mode_combo)

        self.lbl_voice_status = QLabel(check_tts_backend(self.app_settings.tts_backend).message)
        self.lbl_voice_status.setWordWrap(True)
        self.lbl_voice_status.setStyleSheet("color: #72d7c1; font-weight: 600;")
        form.addRow("Trạng thái Engine:", self.lbl_voice_status)

        layout.addLayout(form)

        # Vbee API Credentials Box
        self.vbee_api_box = QWidget()
        vbee_api_layout = QVBoxLayout(self.vbee_api_box)
        vbee_api_layout.setContentsMargins(0, 4, 0, 8)
        vbee_api_layout.setSpacing(8)

        vbee_api_layout.addWidget(section_label("THÔNG TIN VBEE API (REALTIME)"))
        vbee_api_layout.addWidget(
            info_label(
                "Lấy App ID và Access Token từ tài khoản Vbee API (api-docs.vbee.vn). "
                "Thông tin được mã hóa an toàn trong Windows Credential Manager."
            )
        )
        api_form = QFormLayout()
        api_form.setSpacing(8)
        self.vbee_app_id_input = QLineEdit()
        self.vbee_app_id_input.setPlaceholderText("Nhập App ID mới…")
        self.vbee_token_input = QLineEdit()
        self.vbee_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.vbee_token_input.setPlaceholderText("Nhập Access Token mới…")
        api_form.addRow("App ID:", self.vbee_app_id_input)
        api_form.addRow("Access Token:", self.vbee_token_input)
        vbee_api_layout.addLayout(api_form)

        vbee_actions = QHBoxLayout()
        self.btn_save_vbee_api = QPushButton("Lưu thông tin Vbee API")
        self.btn_save_vbee_api.clicked.connect(self._save_vbee_api_credentials)
        self.btn_test_vbee_api = QPushButton("Kiểm tra kết nối API")
        self.btn_test_vbee_api.clicked.connect(self._test_vbee_api)
        self.btn_delete_vbee_api = QPushButton("Xóa thông tin API")
        self.btn_delete_vbee_api.clicked.connect(self._delete_vbee_api_credentials)
        for btn in (self.btn_save_vbee_api, self.btn_test_vbee_api, self.btn_delete_vbee_api):
            vbee_actions.addWidget(btn)
        vbee_actions.addStretch()
        vbee_api_layout.addLayout(vbee_actions)

        self.lbl_vbee_api_status = QLabel("")
        self.lbl_vbee_api_status.setWordWrap(True)
        self.lbl_vbee_api_status.setStyleSheet("color: #72d7c1; font-weight: 600; font-size: 12px;")
        vbee_api_layout.addWidget(self.lbl_vbee_api_status)

        layout.addWidget(self.vbee_api_box)

        layout.addWidget(section_label("QUẢN LÝ GIỌNG ĐỌC"))
        voice_manage_box = QHBoxLayout()
        self.voice_list_combo = QComboBox()
        self.voice_list_combo.addItem("Chưa có danh sách giọng đã xác minh", "")
        self.voice_list_combo.setEnabled(False)
        voice_manage_box.addWidget(self.voice_list_combo, 1)

        self.btn_voice_preview = QPushButton("▶ Nghe thử")
        self.btn_voice_preview.clicked.connect(self._preview_selected_voice)
        voice_manage_box.addWidget(self.btn_voice_preview)
        layout.addLayout(voice_manage_box)
        voice_actions = QHBoxLayout()
        self.btn_add_voice = QPushButton("+ Thêm giọng")
        self.btn_add_voice.clicked.connect(self._show_add_voice_info)
        self.btn_rename_voice = QPushButton("Đổi tên")
        self.btn_rename_voice.clicked.connect(self._rename_voice)
        self.btn_delete_voice = QPushButton("Xóa giọng")
        self.btn_delete_voice.clicked.connect(self._delete_voice)
        for button in (self.btn_add_voice, self.btn_rename_voice, self.btn_delete_voice):
            voice_actions.addWidget(button)
        layout.addLayout(voice_actions)
        self.btn_setup_voice = QPushButton("Cài / Kiểm tra VieNeu")
        self.btn_setup_voice.clicked.connect(self._setup_voice)
        layout.addWidget(self.btn_setup_voice)
        self.btn_use_local = QPushButton("Dùng VieNeu offline")
        self.btn_use_local.clicked.connect(lambda: self.voice_backend_combo.setCurrentIndex(0))
        layout.addWidget(self.btn_use_local)
        voice_log = QPushButton("Mở log Voice")
        voice_log.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(engine_root())))
        )
        layout.addWidget(voice_log)
        self.voice_list_combo.currentIndexChanged.connect(self._voice_selection_changed)
        self.refresh_voice_catalog()

        layout.addWidget(section_label("ÂM LƯỢNG & ĐỘ LỚN"))
        vol_form = QFormLayout()
        self.spin_voice_vol = QDoubleSpinBox()
        self.spin_voice_vol.setMinimumHeight(32)
        self.spin_voice_vol.setRange(0, 100)
        self.spin_voice_vol.setValue(self.app_settings.voice_volume)
        self.spin_voice_vol.setSuffix(" %")
        vol_form.addRow("Âm lượng giọng lồng tiếng:", self.spin_voice_vol)

        self.spin_orig_vol = QDoubleSpinBox()
        self.spin_orig_vol.setMinimumHeight(32)
        self.spin_orig_vol.setRange(0, 100)
        self.spin_orig_vol.setValue(self.app_settings.original_volume)
        self.spin_orig_vol.setSuffix(" %")
        vol_form.addRow("Âm lượng video gốc (Ducking):", self.spin_orig_vol)
        layout.addLayout(vol_form)

        btn_save_voice = QPushButton("Lưu thiết lập Voice")
        btn_save_voice.clicked.connect(self._save_voice_settings)
        layout.addWidget(btn_save_voice)

        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        return scroll

    def refresh_voice_catalog(self) -> None:
        if not hasattr(self, "btn_setup_voice"):
            return
        self.voice_list_combo.blockSignals(True)
        previous = self.voice_list_combo.currentData() or load_app_settings().selected_voice
        if self.main_window.project.voice.provider == self.voice_backend_combo.currentData():
            previous = self.main_window.project.voice.voice_id
        self.voice_list_combo.clear()
        try:
            rows = read_catalog(self.voice_backend_combo.currentData())
            for row in rows:
                self.voice_list_combo.addItem(row["name"], row["id"])
            if not rows:
                self.voice_list_combo.addItem("Chưa có giọng — bấm nút kết nối / cài bên dưới", "")
        except ValueError as exc:
            self.lbl_voice_status.setText(str(exc))
        index = self.voice_list_combo.findData(previous)
        if index >= 0:
            self.voice_list_combo.setCurrentIndex(index)
        self.voice_list_combo.blockSignals(False)
        self._update_voice_controls()

    def _on_voice_backend_changed(self) -> None:
        if not hasattr(self, "btn_setup_voice"):
            return
        self.refresh_voice_catalog()
        self._voice_selection_changed()

    def _on_vbee_mode_changed(self) -> None:
        if not hasattr(self, "vbee_mode_combo"):
            return
        mode = self.vbee_mode_combo.currentData() or "browser"
        self.app_settings.vbee_mode = mode
        save_app_settings(self.app_settings)
        self.main_window.tts.read_credentials()
        self.main_window._refresh()
        self._update_voice_controls()

    def _refresh_vbee_api_status(self) -> None:
        try:
            from vkdub.services.credential_service import VbeeAppStore, VbeeTokenStore

            has_app = bool(VbeeAppStore().get())
            has_token = bool(VbeeTokenStore().get())
            if has_app and has_token:
                self.lbl_vbee_api_status.setText(
                    "✓ Đã lưu App ID & Token trong Windows Credential Manager."
                )
            elif has_app:
                self.lbl_vbee_api_status.setText("⚠ Đã có App ID nhưng chưa có Access Token.")
            else:
                self.lbl_vbee_api_status.setText("Chưa lưu thông tin Vbee API.")
        except Exception:
            self.lbl_vbee_api_status.setText("Không đọc được Windows Credential Manager.")

    def _save_vbee_api_credentials(self) -> None:
        app_id = self.vbee_app_id_input.text().strip()
        token = self.vbee_token_input.text().strip()
        if not app_id or not token or any(c.isspace() for c in app_id + token):
            QMessageBox.warning(
                self,
                "Lỗi",
                "Vui lòng nhập App ID và Access Token hợp lệ (không chứa khoảng trắng).",
            )
            return
        try:
            from vkdub.services.credential_service import VbeeAppStore, VbeeTokenStore

            VbeeAppStore().save(app_id)
            VbeeTokenStore().save(token)
            self.vbee_app_id_input.clear()
            self.vbee_token_input.clear()
            self.lbl_vbee_api_status.setText("✓ Đã lưu an toàn trong Windows Credential Manager.")
            self.main_window.tts.read_credentials()
            self.main_window._refresh()
            self._update_voice_controls()
        except Exception as exc:
            self.lbl_vbee_api_status.setText(f"Lỗi: {exc}")

    def _delete_vbee_api_credentials(self) -> None:
        try:
            from vkdub.services.credential_service import VbeeAppStore, VbeeTokenStore

            VbeeAppStore().delete()
            VbeeTokenStore().delete()
            self.vbee_app_id_input.clear()
            self.vbee_token_input.clear()
            self.lbl_vbee_api_status.setText("Đã xóa thông tin Vbee API khỏi máy tính.")
            self.main_window.tts.read_credentials()
            self.main_window._refresh()
            self._update_voice_controls()
        except Exception as exc:
            self.lbl_vbee_api_status.setText(f"Lỗi: {exc}")

    def _test_vbee_api(self) -> None:
        try:
            import asyncio

            from vkdub.providers.vbee_tts import VbeeTTSProvider
            from vkdub.services.credential_service import VbeeAppStore, VbeeTokenStore
            from vkdub.services.tts_usage import TTSUsage

            app_id = self.vbee_app_id_input.text().strip() or VbeeAppStore().get()
            token = self.vbee_token_input.text().strip() or VbeeTokenStore().get()
            if not app_id or not token:
                QMessageBox.warning(
                    self,
                    "Chưa đủ thông tin",
                    "Vui lòng nhập hoặc lưu App ID và Token trước khi kiểm tra.",
                )
                return

            self.lbl_vbee_api_status.setText("Đang kiểm tra kết nối tới Vbee API…")
            tts = VbeeTTSProvider(app_id, token, TTSUsage())
            voices = asyncio.run(tts.list_voices())
            can_realtime, detail = asyncio.run(tts.check_realtime_support())

            if can_realtime:
                self.lbl_vbee_api_status.setStyleSheet("color: #72d7c1; font-weight: 600; font-size: 12px;")
                self.lbl_vbee_api_status.setText(
                    f"✓ Kết nối Vbee API thành công! Đọc được {len(voices)} giọng. Tài khoản hỗ trợ Realtime API."
                )
            else:
                self.lbl_vbee_api_status.setStyleSheet("color: #fca5a5; font-weight: 600; font-size: 12px;")
                self.lbl_vbee_api_status.setText(
                    f"✓ Token & App ID chính xác ({len(voices)} giọng khả dụng).\n"
                    f"⚠ Tuy nhiên: {detail}.\n"
                    f"👉 Để lồng tiếng với gói này, vui lòng chuyển chế độ phía trên sang 'Trình duyệt tự động'!"
                )
        except Exception as exc:
            self.lbl_vbee_api_status.setStyleSheet("color: #fca5a5; font-weight: 600; font-size: 12px;")
            self.lbl_vbee_api_status.setText(f"Lỗi kiểm tra API: {exc}")

    def _update_voice_controls(self) -> None:
        backend = self.voice_backend_combo.currentData()
        health = check_tts_backend(backend)
        self.lbl_voice_status.setText(
            "Đang xử lý giọng… Bấm Dừng ở cửa sổ chính nếu muốn hủy."
            if self.main_window.busy
            else health.message
        )
        if hasattr(self, "btn_setup_voice"):
            local = backend == "vieneu_local"
            is_vbee = backend == "vbee"
            vbee_mode = (
                self.vbee_mode_combo.currentData()
                if hasattr(self, "vbee_mode_combo")
                else "browser"
            )
            is_vbee_api = is_vbee and vbee_mode == "api"

            if hasattr(self, "lbl_vbee_mode") and hasattr(self, "vbee_mode_combo"):
                self.lbl_vbee_mode.setVisible(is_vbee)
                self.vbee_mode_combo.setVisible(is_vbee)

            if hasattr(self, "vbee_api_box"):
                self.vbee_api_box.setVisible(is_vbee_api)
                if is_vbee_api:
                    self._refresh_vbee_api_status()

            idle = not self.main_window.busy
            self.voice_backend_combo.setEnabled(idle)
            if is_vbee:
                if is_vbee_api:
                    self.btn_setup_voice.setVisible(False)
                else:
                    self.btn_setup_voice.setVisible(True)
                    self.btn_setup_voice.setText("🌐 Mở / Kiểm tra Vbee Dubbing")
            elif local:
                self.btn_setup_voice.setVisible(True)
                self.btn_setup_voice.setText("Cài / Kiểm tra VieNeu")
            else:
                self.btn_setup_voice.setVisible(True)
                self.btn_setup_voice.setText("Kết nối / Kiểm tra CapCut")
            self.btn_setup_voice.setEnabled(idle)
            self.btn_use_local.setVisible(not local and not is_vbee)
            self.btn_use_local.setEnabled(idle)
            ready = health.ok and idle and bool(self.voice_list_combo.currentData())
            self.voice_list_combo.setEnabled(ready)
            self.btn_voice_preview.setEnabled(ready and (not is_vbee or is_vbee_api))
            self.btn_add_voice.setVisible(local)
            self.btn_rename_voice.setVisible(local)
            self.btn_delete_voice.setVisible(local)
            self.btn_add_voice.setEnabled(ready and local)
            custom = str(self.voice_list_combo.currentData() or "").startswith("custom-")
            self.btn_rename_voice.setEnabled(ready and custom and local)
            self.btn_delete_voice.setEnabled(ready and custom and local)

    def _voice_selection_changed(self) -> None:
        self.main_window.tts.select_voice(
            self.voice_backend_combo.currentData(), self.voice_list_combo.currentData() or ""
        )
        self._update_voice_controls()

    def _setup_voice(self) -> None:
        if self.main_window.tts.setup_engine(self.voice_backend_combo.currentData()):
            self.lbl_voice_status.setText(
                "Đang chuẩn bị và tạo audio thử… Có thể mất vài phút ở lần đầu."
            )
            self.btn_setup_voice.setEnabled(False)

    def _preview_selected_voice(self) -> None:
        self.main_window.tts.preview_voice(
            self.voice_list_combo.currentData(), self.voice_backend_combo.currentData()
        )

    def _show_add_voice_info(self) -> None:
        if self.main_window.busy:
            return
        self.voice_dialog = AddVoiceDialog(self)
        self.voice_dialog.accepted.connect(
            lambda: self.main_window.tts.add_voice(
                self.voice_dialog.name_input.text(), Path(self.voice_dialog.reference_input.text())
            )
        )
        self.voice_dialog.open()

    def _rename_voice(self) -> None:
        name, ok = QInputDialog.getText(
            self, "Đổi tên giọng", "Tên mới", text=self.voice_list_combo.currentText()
        )
        if ok:
            try:
                rename_voice(self.voice_list_combo.currentData(), name)
                self.main_window.tts.read_credentials()
                self.main_window._refresh()
                self.refresh_voice_catalog()
            except ValueError as exc:
                self.lbl_voice_status.setText(str(exc))

    def _delete_voice(self) -> None:
        try:
            identifier = self.voice_list_combo.currentData()
            delete_voice(identifier)
            remaining = read_catalog()
            if remaining:
                settings = load_app_settings()
                if settings.selected_voice == identifier:
                    settings.selected_voice = remaining[0]["id"]
                    save_app_settings(settings)
                if self.main_window.project.voice.voice_id == identifier:
                    self.main_window.project.voice = replace(
                        self.main_window.project.voice,
                        voice_id=remaining[0]["id"],
                        display_name=remaining[0]["name"],
                    )
                    self.main_window.dirty = True
            self.main_window.tts.read_credentials()
            self.main_window._refresh()
            self.refresh_voice_catalog()
        except ValueError as exc:
            self.lbl_voice_status.setText(str(exc))

    def _save_voice_settings(self) -> None:
        if self.main_window.busy:
            return
        if not self.main_window.tts.select_voice(
            self.voice_backend_combo.currentData(), self.voice_list_combo.currentData() or ""
        ):
            self.lbl_voice_status.setText("Hãy kiểm tra engine và chọn giọng trước khi lưu.")
            return
        self.app_settings = load_app_settings()
        self.app_settings.tts_backend = self.voice_backend_combo.currentData()
        self.app_settings.selected_voice = self.voice_list_combo.currentData() or ""
        self.app_settings.voice_volume = self.spin_voice_vol.value()
        self.app_settings.original_volume = self.spin_orig_vol.value()
        if hasattr(self, "vbee_mode_combo"):
            self.app_settings.vbee_mode = self.vbee_mode_combo.currentData() or "browser"
        if self.app_settings.tts_backend == "vbee":
            self.app_settings.voice_speed = 1.1
            if (
                hasattr(self, "vbee_app_id_input")
                and hasattr(self, "vbee_token_input")
                and self.vbee_app_id_input.text().strip()
                and self.vbee_token_input.text().strip()
            ):
                self._save_vbee_api_credentials()
        identifier = self.voice_list_combo.currentData()
        if identifier:
            self.main_window.project.voice = replace(
                self.main_window.project.voice,
                provider=self.app_settings.tts_backend,
                voice_id=identifier,
                display_name=self.voice_list_combo.currentText(),
                volume=self.app_settings.voice_volume / 100,
                speed=1.1 if self.app_settings.tts_backend == "vbee" else self.main_window.project.voice.speed,
            )
            self.main_window.dirty = True
        if not self._persist_settings():
            return
        backend_title = self.voice_backend_combo.currentText()
        QMessageBox.information(
            self, "Thành công", f"Đã lưu thiết lập Voice Engine:\n{backend_title}"
        )

    # -------------------------------------------------------------
    # 4. TAB CAPCUT (CapCut Draft Root & Compatibility)
    # -------------------------------------------------------------
    def _build_capcut_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(14)

        layout.addWidget(section_label("KẾT NỐI CAPCUT PC (WINDOWS DRAFT)"))
        layout.addWidget(
            info_label(
                "Chọn nơi lưu dự án CapCut cho các lần dùng sau. "
                "Khi đủ voice, nút chính sẽ tạo draft mới có video, voice và caption chỉnh được."
            )
        )

        form = QFormLayout()
        form.setSpacing(10)

        cap_row = QHBoxLayout()
        self.capcut_root_input = QLineEdit()
        self.capcut_root_input.setText(self.app_settings.capcut_draft_root)
        btn_browse = QPushButton("Chọn thư mục…")
        btn_browse.clicked.connect(self._browse_capcut_root)
        cap_row.addWidget(self.capcut_root_input, 1)
        cap_row.addWidget(btn_browse)
        form.addRow("Thư mục CapCut Draft Root:", cap_row)

        self.capcut_status_lbl = QLabel()
        form.addRow("Trạng thái kết nối:", self.capcut_status_lbl)

        layout.addLayout(form)

        btn_act_row = QHBoxLayout()
        btn_auto_detect = QPushButton("🔍 Tự động phát hiện")
        btn_auto_detect.clicked.connect(self._auto_detect_capcut)
        btn_open_folder = QPushButton("📂 Mở thư mục CapCut")
        btn_open_folder.clicked.connect(self._open_capcut_folder)
        btn_check_compat = QPushButton("Kiểm tra thư mục")
        btn_check_compat.clicked.connect(self._check_capcut_compat)

        btn_act_row.addWidget(btn_auto_detect)
        btn_act_row.addWidget(btn_open_folder)
        btn_act_row.addWidget(btn_check_compat)
        btn_act_row.addStretch()
        layout.addLayout(btn_act_row)

        btn_save_capcut = QPushButton("Lưu cấu hình CapCut")
        btn_save_capcut.clicked.connect(self._save_capcut_settings)
        layout.addWidget(btn_save_capcut)

        layout.addStretch()
        return widget

    def _browse_capcut_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục CapCut Draft Root")
        if path:
            self.capcut_root_input.setText(path)
            self._update_capcut_status()

    def _auto_detect_capcut(self) -> None:
        detected = detect_default_capcut_draft_root()
        if detected:
            self.capcut_root_input.setText(str(detected))
            QMessageBox.information(
                self, "Tự động phát hiện", f"Đã tìm thấy thư mục CapCut:\n{detected}"
            )
        else:
            QMessageBox.warning(
                self,
                "Không tìm thấy",
                "Chưa tìm thấy thư mục CapCut mặc định trong AppData. Hãy chọn thủ công.",
            )
        self._update_capcut_status()

    def _open_capcut_folder(self) -> None:
        path_str = self.capcut_root_input.text().strip()
        if path_str and Path(path_str).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(path_str))
        else:
            QMessageBox.warning(self, "Lỗi", "Thư mục không tồn tại.")

    def _check_capcut_compat(self) -> None:
        res = check_capcut_root(self.capcut_root_input.text().strip())
        if res.ok:
            QMessageBox.information(
                self,
                "Tương thích CapCut",
                "Thư mục ghi được. Chưa xác minh schema hoặc khả năng mở draft trong CapCut.",
            )
        else:
            QMessageBox.warning(self, "Chưa sẵn sàng", res.message)

    def _update_capcut_status(self) -> None:
        res = check_capcut_root(self.capcut_root_input.text().strip())
        if res.ok:
            self.capcut_status_lbl.setText("✓ Đã kết nối thư mục hợp lệ.")
            self.capcut_status_lbl.setStyleSheet("color: #34d399; font-weight: bold;")
        else:
            self.capcut_status_lbl.setText("Chưa kết nối.")
            self.capcut_status_lbl.setStyleSheet("color: #fbbf24;")

    def _save_capcut_settings(self) -> None:
        self.app_settings = load_app_settings()
        self.app_settings.capcut_draft_root = self.capcut_root_input.text().strip()
        if not self._persist_settings():
            return
        if hasattr(self.main_window, "left"):
            self.main_window.left.refresh_capcut_destination()
        QMessageBox.information(self, "Thành công", "Đã lưu đường dẫn CapCut Draft.")

    # -------------------------------------------------------------
    # 5. TAB CẬP NHẬT (Update)
    # -------------------------------------------------------------
    def _build_update_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(14)

        layout.addWidget(section_label("THÔNG TIN PHIÊN BẢN & CẬP NHẬT"))

        form = QFormLayout()
        form.setSpacing(8)

        lbl_ver = QLabel(f"v{__version__}")
        lbl_ver.setStyleSheet("font-size: 13px; font-weight: 700; color: #72d7c1;")
        form.addRow("Phiên bản hiện tại:", lbl_ver)

        self.update_channel = QComboBox()
        self.update_channel.addItem("Ổn định (Stable)", DEFAULT_UPDATE_FEED_STABLE)
        self.update_channel.addItem("Thử nghiệm (Beta)", DEFAULT_UPDATE_FEED_BETA)
        form.addRow("Kênh phát hành:", self.update_channel)

        self.chk_auto_update = QCheckBox("Tự động kiểm tra bản cập nhật khi khởi động")
        self.chk_auto_update.setChecked(self.app_settings.auto_update)
        self.chk_auto_update.toggled.connect(self._save_update_preference)
        form.addRow("Tự động kiểm tra:", self.chk_auto_update)

        layout.addLayout(form)

        row_btn = QHBoxLayout()
        self.btn_check_update = QPushButton("🔍 Kiểm tra cập nhật ngay")
        self.btn_check_update.clicked.connect(self._check_for_updates)
        row_btn.addWidget(self.btn_check_update)
        row_btn.addStretch()
        layout.addLayout(row_btn)

        self.update_status_lbl = QLabel()
        self.update_status_lbl.setWordWrap(True)
        layout.addWidget(self.update_status_lbl)

        layout.addStretch()
        return widget

    def _save_update_preference(self, enabled: bool) -> None:
        self.app_settings = load_app_settings()
        self.app_settings.auto_update = enabled
        self._persist_settings()

    def _check_for_updates(self) -> None:
        if self.update_job is not None:
            return
        self.update_status_lbl.setText("Đang kiểm tra máy chủ phát hành…")
        feed = self.update_channel.currentData()
        self.btn_check_update.setEnabled(False)
        self.update_job = BackgroundCheck(lambda: fetch_update_info(feed))
        self.update_job.succeeded.connect(self._update_result)
        self.update_job.failed.connect(self.update_status_lbl.setText)
        self.update_job.finished.connect(self._update_finished)
        self.update_job.start()

    def _update_finished(self) -> None:
        self.update_job = None
        self.btn_check_update.setEnabled(True)

    def _update_result(self, info: object) -> None:
        from vkdub.services.update_service import UpdateInfo

        if not isinstance(info, UpdateInfo):
            self.update_status_lbl.setText(
                "Không kiểm tra được máy chủ cập nhật. Ứng dụng vẫn dùng được."
            )
        elif is_newer_version(info.version, __version__):
            self.update_status_lbl.setText(f"Có bản mới: {info.version}")
            self.update_dialog = UpdateDialog(info, self)
            self.update_dialog.open()
        else:
            self.update_status_lbl.setText(f"Đang dùng phiên bản mới nhất (v{__version__}).")

    # -------------------------------------------------------------
    # 6. TAB NÂNG CAO (Advanced: Media Tools, STT Model, Logs, Cache)
    # -------------------------------------------------------------
    def _build_advanced_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        layout.addWidget(section_label("CÔNG CỤ XỬ LÝ MEDIA (FFMPEG & FFPROBE)"))
        form_tools = QFormLayout()
        form_tools.setSpacing(6)

        self.ffmpeg_stat_lbl = QLabel("Đang kiểm tra…")
        self.ffprobe_stat_lbl = QLabel("Đang kiểm tra…")
        form_tools.addRow("FFmpeg:", self.ffmpeg_stat_lbl)
        form_tools.addRow("ffprobe:", self.ffprobe_stat_lbl)
        layout.addLayout(form_tools)

        btn_detect = QPushButton("Kiểm tra lại FFmpeg / ffprobe")
        btn_detect.clicked.connect(self.main_window.detect_tools)
        layout.addWidget(btn_detect)

        layout.addWidget(section_label("BÓC BĂNG CỤC BỘ (FASTER-WHISPER)"))
        form_stt = QFormLayout()
        form_stt.setSpacing(6)
        self.ai_model_combo = self.main_window.left.model_selector
        form_stt.addRow("Model Whisper:", self.ai_model_combo)
        self.ai_device_combo = self.main_window.left.device_selector
        form_stt.addRow("Thiết bị tính toán:", self.ai_device_combo)
        self.ai_model_status = self.main_window.left.model_status
        form_stt.addRow("Trạng thái model:", self.ai_model_status)
        layout.addLayout(form_stt)

        stt_act = QHBoxLayout()
        btn_check_model = QPushButton("Kiểm tra model")
        btn_check_model.clicked.connect(self._check_model)
        self.btn_download_model = self.main_window.left.download_button
        stt_act.addWidget(btn_check_model)
        stt_act.addWidget(self.btn_download_model)
        stt_act.addStretch()
        layout.addLayout(stt_act)

        layout.addWidget(section_label("NHẬT KÝ & BỘ NHỚ ĐỆM"))
        diag_row = QHBoxLayout()
        btn_logs = QPushButton("Xem log hệ thống (F12)")
        btn_logs.clicked.connect(self.main_window.open_log_viewer)
        btn_open_data = QPushButton("Mở thư mục ứng dụng")
        btn_open_data.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_root())))
        )
        diag_row.addWidget(btn_logs)
        diag_row.addWidget(btn_open_data)
        diag_row.addStretch()
        layout.addLayout(diag_row)

        layout.addStretch()
        return widget

    def _check_model(self) -> None:
        self.main_window.transcription.refresh()
        QMessageBox.information(
            self,
            "Kiểm tra mô hình",
            f"Trạng thái mô hình: {self.ai_model_status.text()}",
        )

    # -------------------------------------------------------------
    # Refresh & backward compatibility
    # -------------------------------------------------------------
    def refresh(self) -> None:
        self.app_settings = load_app_settings()
        self._update_capcut_status()
        self.capcut_root_input.setText(self.app_settings.capcut_draft_root)
        self.workspace_input.setText(self.app_settings.workspace_root)

        # Update FFmpeg status labels
        if hasattr(self.main_window, "tools"):
            paths = getattr(self.main_window.tools, "paths", {})
            ff = paths.get("ffmpeg")
            fp = paths.get("ffprobe")
            self.ffmpeg_stat_lbl.setText(f"✓ {ff}" if ff else "Chưa sẵn sàng")
            self.ffprobe_stat_lbl.setText(f"✓ {fp}" if fp else "Chưa sẵn sàng")

        self.gemini_model_combo.setCurrentText(self.app_settings.gemini_model)
        self.pref_source_lang.setCurrentIndex(
            self.pref_source_lang.findData(self.app_settings.source_language)
        )
        self.voice_backend_combo.setCurrentIndex(
            self.voice_backend_combo.findData(self.app_settings.tts_backend)
        )
        self.chk_auto_update.blockSignals(True)
        self.chk_auto_update.setChecked(self.app_settings.auto_update)
        self.chk_auto_update.blockSignals(False)
        self.gemini_status_lbl.setText("Nhấn Kiểm tra kết nối để xác minh khóa và model.")
