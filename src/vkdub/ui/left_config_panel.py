from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from vkdub.domain.transcript import MODELS
from vkdub.services.app_settings import load_app_settings
from vkdub.ui.browser_bridge_widget import BrowserBridgeWidget
from vkdub.ui.pipeline_step4_widget import Step4PipelineWidget
from vkdub.version import APP_CREDIT, __version__


def label(text: str, name: str = "muted") -> QLabel:
    widget = QLabel(text)
    widget.setObjectName(name)
    widget.setWordWrap(True)
    return widget


class LeftConfigPanel(QFrame):
    settings_requested = Signal()
    test_listen_requested = Signal()
    voice_settings_changed = Signal()
    manage_voices_requested = Signal()
    capcut_folder_requested = Signal()
    open_capcut_requested = Signal()
    open_capcut_folder_requested = Signal()
    export_video_requested = Signal()
    export_capcut_requested = Signal()
    vbee_voice_requested = Signal()
    vbee_export_srt_requested = Signal()
    vbee_manual_audio_requested = Signal()
    chatgpt_translate_requested = Signal()
    import_chatgpt_srt_requested = Signal()
    approve_script_requested = Signal()
    toggle_mask_requested = Signal()
    open_browser_requested = Signal()
    refresh_bridge_requested = Signal()
    pipeline_start_requested = Signal()
    pipeline_cancel_requested = Signal()
    pipeline_retry_step_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("panel")
        self.setMinimumWidth(280)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(10)

        # ---------------------------------------------------------
        # Header: Branding & Settings button
        # ---------------------------------------------------------
        header_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.addWidget(label("VK Dub Studio", "heading"))
        title_col.addWidget(label(f"by vanhkhuc.dev   •   v{__version__}"))
        header_row.addLayout(title_col, 1)

        self.settings_button = QPushButton("⚙ Cài đặt")
        self.settings_button.setToolTip(
            "Mở bảng Cài đặt chi tiết 2.0 (Chung, AI, Voice, CapCut, Cập nhật, Nâng cao)"
        )
        self.settings_button.clicked.connect(self.settings_requested.emit)
        header_row.addWidget(self.settings_button)
        root_layout.addLayout(header_row)

        self.credit_label = label(APP_CREDIT)
        self.credit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.credit_label.setStyleSheet(
            "color: #72d7c1; font-size: 10px; font-style: italic; padding: 2px 0 4px 0;"
        )
        root_layout.addWidget(self.credit_label)

        sep0 = QFrame()
        sep0.setFrameShape(QFrame.Shape.HLine)
        sep0.setStyleSheet("color: #293245;")
        root_layout.addWidget(sep0)

        # ---------------------------------------------------------
        # Scrollable Configuration Area
        # ---------------------------------------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(10)

        # ---------------------------------------------------------
        # CẦU NỐI TRÌNH DUYỆT (H6 BRIDGE STATUS)
        # ---------------------------------------------------------
        self.browser_bridge = BrowserBridgeWidget()
        self.browser_bridge.open_browser_requested.connect(self.open_browser_requested.emit)
        self.browser_bridge.refresh_requested.connect(self.refresh_bridge_requested.emit)
        layout.addWidget(self.browser_bridge)

        sep_bridge = QFrame()
        sep_bridge.setFrameShape(QFrame.Shape.HLine)
        sep_bridge.setStyleSheet("color: #21262d;")
        layout.addWidget(sep_bridge)

        # =========================================================
        # 01 SOURCE: NGUỒN VIDEO
        # =========================================================
        layout.addWidget(label("01 NGUỒN VIDEO (SOURCE)", "eyebrow"))
        self.import_button = QPushButton("📂 BƯỚC 1: CHỌN VIDEO")
        self.import_button.setObjectName("primary")
        self.import_button.setEnabled(False)
        self.import_button.setStyleSheet("font-size: 13px; padding: 9px; font-weight: bold;")
        layout.addWidget(self.import_button)

        self.video_info = QLabel("Chưa chọn video MP4")
        self.video_info.setWordWrap(True)
        self.video_info.setStyleSheet("color: #72d7c1; font-weight: 600; font-size: 12px;")
        layout.addWidget(self.video_info)
        self.video_path = self.video_info

        step1_tools = QHBoxLayout()
        self.save_button = QPushButton("💾 Lưu")
        self.save_button.setToolTip("Lưu project (.vkdub)")
        self.load_button = QPushButton("📂 Mở")
        self.load_button.setToolTip("Mở project (.vkdub)")
        self.output_button = QPushButton("📁")
        self.output_button.hide()
        for btn in (self.save_button, self.load_button):
            btn.setStyleSheet("padding: 4px 6px; font-size: 11px;")
            step1_tools.addWidget(btn)
        layout.addLayout(step1_tools)
        self.output_path = QLabel("Chưa chọn thư mục")
        self.output_path.hide()

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #21262d;")
        layout.addWidget(sep1)

        # =========================================================
        # 02 VOICE: CẤU HÌNH GIỌNG ĐỌC
        # =========================================================
        layout.addWidget(label("02 CẤU HÌNH GIỌNG ĐỌC (VOICE)", "eyebrow"))
        self.voice_combo = QComboBox()
        self.voice_combo.addItem("HN - Ngọc Huyền", "vbee-ngoc-huyen")
        self.voice_combo.currentIndexChanged.connect(lambda *_: self.voice_settings_changed.emit())
        layout.addWidget(self.voice_combo)

        voice_ctrl_row = QHBoxLayout()
        self.speed_combo = QComboBox()
        for s in ("0.8x", "0.9x", "1.0x (Chuẩn)", "1.1x", "1.2x", "1.3x"):
            self.speed_combo.addItem(s, float(s.split("x")[0]))
        curr_spd = load_app_settings().voice_speed
        idx = self.speed_combo.findData(curr_spd)
        self.speed_combo.setCurrentIndex(idx if idx >= 0 else self.speed_combo.findData(1.1))
        self.speed_combo.currentIndexChanged.connect(lambda *_: self.voice_settings_changed.emit())
        voice_ctrl_row.addWidget(self.speed_combo, 1)

        self.listen_test_button = QPushButton("▶ Nghe thử")
        self.listen_test_button.setStyleSheet("padding: 4px 8px; font-size: 11px;")
        self.listen_test_button.clicked.connect(self.test_listen_requested.emit)
        voice_ctrl_row.addWidget(self.listen_test_button)
        layout.addLayout(voice_ctrl_row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #21262d;")
        layout.addWidget(sep2)

        # =========================================================
        # 03 BLUR REGIONS: KHUNG CHE MỜ PHỤ ĐỀ
        # =========================================================
        layout.addWidget(label("03 KHUNG CHE MỜ (BLUR REGIONS)", "eyebrow"))
        self.btn_toggle_mask = QPushButton("▣ Bật / Chỉnh Khung Che Mờ")
        self.btn_toggle_mask.setToolTip(
            "Bật hoặc căn chỉnh khung che mờ phụ đề cũ trên video xem trước"
        )
        self.btn_toggle_mask.setStyleSheet("padding: 6px; font-size: 11px; font-weight: 500;")
        self.btn_toggle_mask.clicked.connect(self.toggle_mask_requested.emit)
        layout.addWidget(self.btn_toggle_mask)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("color: #21262d;")
        layout.addWidget(sep3)

        # =========================================================
        # 04 AUTOMATIC PROCESSING: XỬ LÝ TỰ ĐỘNG
        # =========================================================
        self.step4_pipeline = Step4PipelineWidget()
        self.step4_pipeline.start_requested.connect(self.pipeline_start_requested.emit)
        self.step4_pipeline.cancel_requested.connect(self.pipeline_cancel_requested.emit)
        self.step4_pipeline.retry_step_requested.connect(self.pipeline_retry_step_requested.emit)
        layout.addWidget(self.step4_pipeline)

        sep4 = QFrame()
        sep4.setFrameShape(QFrame.Shape.HLine)
        sep4.setStyleSheet("color: #21262d;")
        layout.addWidget(sep4)

        # =========================================================
        # 05 REVIEW & EXPORT: DUYỆT & XUẤT
        # =========================================================
        layout.addWidget(label("05 DUYỆT & XUẤT (REVIEW & EXPORT)", "eyebrow"))
        self.lbl_review_status = QLabel("Chờ xử lý xong bước 4")
        self.lbl_review_status.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(self.lbl_review_status)

        self.btn_approve_script = QPushButton("✔ BƯỚC 5: CHỐT KỊCH BẢN (DUYỆT)")
        self.btn_approve_script.setStyleSheet(
            "background: #059669; color: white; font-weight: bold; font-size: 12px; padding: 8px; border-radius: 4px;"
        )
        self.btn_approve_script.clicked.connect(self.approve_script_requested.emit)
        layout.addWidget(self.btn_approve_script)

        capcut_box = QHBoxLayout()
        self.capcut_dest_lbl = QLabel("CapCut Draft Root")
        self.capcut_dest_lbl.setStyleSheet("color: #94a3b8; font-size: 10px;")
        self.btn_capcut_folder = QPushButton("Đổi…")
        self.btn_capcut_folder.setStyleSheet("padding: 2px 4px; font-size: 10px;")
        self.btn_capcut_folder.clicked.connect(self.capcut_folder_requested.emit)
        capcut_box.addWidget(self.capcut_dest_lbl, 1)
        capcut_box.addWidget(self.btn_capcut_folder)
        layout.addLayout(capcut_box)

        # Compatibility aliases for legacy tests and controllers
        self.btn_open_chatgpt = QPushButton()
        self.btn_open_chatgpt.hide()
        self.btn_import_chatgpt_srt = QPushButton()
        self.btn_import_chatgpt_srt.hide()
        self.btn_vbee_voice = QPushButton()
        self.btn_vbee_voice.hide()
        self.btn_vbee_export_srt = QPushButton()
        self.btn_vbee_export_srt.hide()
        self.btn_vbee_manual_audio = QPushButton()
        self.btn_vbee_manual_audio.hide()
        self.manage_voices_button = QPushButton()
        self.manage_voices_button.hide()
        self.source_language = QComboBox()
        self.source_language.addItem("Tự động nhận diện", "auto")
        self.target_language = QComboBox()
        self.target_language.addItem("Tiếng Việt", "vi")

        # 5. TIẾN TRÌNH & CTA CHÍNH SECTION
        layout.addWidget(label("QUY TRÌNH & HÀNH ĐỘNG", "eyebrow"))
        self.process_button = QPushButton("🚀 BẮT ĐẦU XỬ LÝ")
        self.process_button.setObjectName("primary")
        self.process_button.setEnabled(False)
        self.process_button.setStyleSheet("font-size: 13px; font-weight: bold; padding: 11px;")
        layout.addWidget(self.process_button)

        self.stop_button = QPushButton("⏹ DỪNG")
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

        self.job_progress = QProgressBar()
        self.job_progress.setRange(0, 100)
        self.job_progress.setValue(0)
        layout.addWidget(self.job_progress)

        # Clean 6-stage status indicators (Spec Section 7)
        self.status_box = QFrame()
        self.status_box.setObjectName("pipelineStatus")
        self.status_box.setStyleSheet(
            "QFrame#pipelineStatus { background: #0f141e; border: 1px solid #232d3f; "
            "border-radius: 6px; }"
        )
        status_layout = QVBoxLayout(self.status_box)
        status_layout.setContentsMargins(8, 8, 8, 8)
        status_layout.setSpacing(5)

        self.status_video = QLabel("○ Video")
        self.status_stt = QLabel("○ Bóc băng")
        self.status_trans = QLabel("○ Dịch")
        self.status_review = QLabel("○ Chờ duyệt")
        self.status_voice = QLabel("○ Voice")
        self.status_export = QLabel("○ CapCut")

        for s_lbl in (
            self.status_video,
            self.status_stt,
            self.status_trans,
            self.status_review,
            self.status_voice,
            self.status_export,
        ):
            s_lbl.setStyleSheet("color: #69768b; font-weight: 600; font-size: 12px;")
            status_layout.addWidget(s_lbl)
        layout.addWidget(self.status_box)

        layout.addStretch()

        # Hidden technical widgets kept for 100% test & controller backward compatibility
        self.hidden_tech_widget = QWidget()
        self.hidden_tech_widget.hide()
        tech_layout = QVBoxLayout(self.hidden_tech_widget)
        self.ffmpeg_status = label("FFmpeg  •  Đang kiểm tra…")
        self.ffprobe_status = label("ffprobe  •  Đang kiểm tra…")
        self.detect_button = QPushButton("Kiểm tra lại công cụ")
        self.language_voice = label("")
        self.model_selector = QComboBox()
        self.model_selector.addItems(MODELS)
        self.model_selector.setCurrentText("base")
        self.device_selector = QComboBox()
        for title, device in (("Auto", "auto"), ("CPU", "cpu"), ("CUDA", "cuda")):
            self.device_selector.addItem(title, device)
        self.model_status = label("Chưa kiểm tra model")
        self.download_button = QPushButton("TẢI MODEL")
        self.reuse_cache = QCheckBox("Dùng bản chép lời đã lưu nếu có")
        self.reuse_cache.setChecked(True)
        self.translation_cache = QCheckBox("Dùng bản dịch đã lưu nếu có")
        self.translation_cache.setChecked(True)
        self.api_button = QPushButton("API && Chi phí")
        self.translate_button = QPushButton("DỊCH SANG TIẾNG VIỆT")

        for w in (
            self.ffmpeg_status,
            self.ffprobe_status,
            self.detect_button,
            self.language_voice,
            self.model_selector,
            self.device_selector,
            self.model_status,
            self.download_button,
            self.reuse_cache,
            self.translation_cache,
            self.api_button,
            self.translate_button,
        ):
            tech_layout.addWidget(w)
        layout.addWidget(self.hidden_tech_widget)

        self.configuration_layout = layout
        self.configuration_scroll = scroll
        scroll.setWidget(scroll_content)
        root_layout.addWidget(scroll, 1)
        # Keep the primary action reachable even when configuration needs scrolling.
        for widget in (self.status_box, self.process_button, self.stop_button, self.job_progress):
            layout.removeWidget(widget)
            root_layout.addWidget(widget)

        self.export_actions = QFrame()
        export_layout = QHBoxLayout(self.export_actions)
        export_layout.setContentsMargins(0, 0, 0, 0)
        export_layout.setSpacing(8)
        self.export_video_button = QPushButton("🎞 XUẤT VIDEO")
        self.export_capcut_button = QPushButton("🎬 XUẤT CAPCUT")
        self.export_video_button.setToolTip("Tạo MP4 hoàn chỉnh với xóa chữ, voice và phụ đề")
        self.export_capcut_button.setToolTip("Tạo project CapCut có video đã xóa chữ và voice")
        self.export_video_button.clicked.connect(self.export_video_requested.emit)
        self.export_capcut_button.clicked.connect(self.export_capcut_requested.emit)
        export_layout.addWidget(self.export_video_button)
        export_layout.addWidget(self.export_capcut_button)
        root_layout.addWidget(self.export_actions)
        self.export_actions.hide()

        result_actions = QHBoxLayout()
        self.open_capcut_button = QPushButton("MỞ CAPCUT")
        self.open_capcut_folder_button = QPushButton("MỞ PROJECT")
        self.open_capcut_button.clicked.connect(self.open_capcut_requested.emit)
        self.open_capcut_folder_button.clicked.connect(self.open_capcut_folder_requested.emit)
        result_actions.addWidget(self.open_capcut_button)
        result_actions.addWidget(self.open_capcut_folder_button)
        root_layout.addLayout(result_actions)
        self.show_capcut_result(False)

        # ---------------------------------------------------------
        # Activity Log (Compact)
        # ---------------------------------------------------------
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumBlockCount(120)
        self.logs.setMinimumHeight(105)
        self.logs.setMaximumHeight(125)
        self.logs.setStyleSheet(
            "font-size: 11px; background: #0c111a; border: 1px solid #232d3f; border-radius: 4px;"
        )
        self.logs.setAccessibleName("Nhật ký hoạt động")
        self.activity_header = QLabel("● NHẬT KÝ ĐANG CHẠY")
        self.activity_header.setStyleSheet("color:#72d7c1;font-weight:700;font-size:11px;")
        root_layout.addWidget(self.activity_header)
        root_layout.addWidget(self.logs)

        # Initialize CapCut destination label
        self.refresh_capcut_destination()

    def show_capcut_result(self, visible: bool) -> None:
        self.open_capcut_button.setVisible(visible)
        self.open_capcut_folder_button.setVisible(visible)

    def refresh_capcut_destination(self) -> None:
        settings = load_app_settings()
        dest = settings.capcut_draft_root
        if dest:
            from pathlib import Path

            p = Path(dest)
            self.capcut_dest_lbl.setText(f"📁 {p.name if p.name else dest}")
            self.capcut_dest_lbl.setToolTip(dest)
        else:
            self.capcut_dest_lbl.setText("📁 Chưa kết nối")

    def update_cta_for_state(self, state: str, has_video: bool = False) -> None:
        """Update CTA button text and primary state according to pipeline state."""
        show_exports = has_video and state == "VOICE_READY"
        self.process_button.setVisible(not show_exports)
        self.export_actions.setVisible(show_exports)
        if not has_video:
            self.process_button.setText("📂 HÃY CHỌN VIDEO")
            self.process_button.setEnabled(False)
            return

        if state in ("IDLE", "VIDEO_IMPORTED"):
            self.process_button.setText("🚀 BẮT ĐẦU XỬ LÝ")
            self.process_button.setEnabled(True)
        elif state == "TRANSCRIBED":
            self.process_button.setText("🚀 BẮT ĐẦU XỬ LÝ")
        elif state in ("REVIEW_REQUIRED", "APPROVED"):
            self.process_button.setText("✓ DUYỆT && TẠO VOICE")
            self.process_button.setEnabled(True)
        elif state == "VOICE_READY":
            self.process_button.setText("🎬 XUẤT PROJECT CAPCUT")
            self.process_button.setEnabled(True)
        else:
            self.process_button.setText("🚀 BẮT ĐẦU XỬ LÝ")
            self.process_button.setEnabled(True)

    def set_pipeline_status(self, step: int, active: bool = False, done: bool = False) -> None:
        """Update 6-stage status list indicators:
        step 1: Video
        step 2: Bóc băng
        step 3: Dịch
        step 4: Chờ duyệt
        step 5: Voice
        step 6: CapCut
        """
        labels = [
            (self.status_video, "Video"),
            (self.status_stt, "Bóc băng"),
            (self.status_trans, "Dịch"),
            (self.status_review, "Chờ duyệt"),
            (self.status_voice, "Voice"),
            (self.status_export, "CapCut"),
        ]
        for idx, (lbl, text) in enumerate(labels, 1):
            if idx < step:
                lbl.setText(f"✓ {text}")
                lbl.setStyleSheet("color: #34d399; font-weight: 600; font-size: 12px;")
            elif idx == step:
                if done:
                    lbl.setText(f"✓ {text}")
                    lbl.setStyleSheet("color: #34d399; font-weight: 600; font-size: 12px;")
                elif active:
                    lbl.setText(f"● {text} (Đang chạy…)")
                    lbl.setStyleSheet("color: #fbbf24; font-weight: 600; font-size: 12px;")
                else:
                    lbl.setText(f"● {text}")
                    lbl.setStyleSheet("color: #72d7c1; font-weight: 600; font-size: 12px;")
            else:
                lbl.setText(f"○ {text}")
                lbl.setStyleSheet("color: #69768b; font-weight: 600; font-size: 12px;")
