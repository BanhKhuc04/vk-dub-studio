from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from vkdub.domain.translation import GEMINI_MODEL
from vkdub.services.api_settings import ApiSettings, load_settings, save_settings
from vkdub.services.cost_service import DISCLAIMER, estimate_tokens, estimate_usd, load_pricing
from vkdub.services.credential_service import CredentialStore
from vkdub.services.translation_service import batches
from vkdub.services.tts_usage import TTSUsage
from vkdub.services.usage_service import UsageLedger
from vkdub.ui.left_config_panel import label

if TYPE_CHECKING:
    from vkdub.ui.translation_controller import TranslationController


class ApiCostDialog(QDialog):
    def __init__(self, controller: "TranslationController") -> None:
        super().__init__(controller.window)
        self.controller = controller
        self.store = CredentialStore()
        self.setWindowTitle("VK Dub Studio — API & Chi phí")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(1080, 780)
        self.close_after_job = False
        self.credential_status = "Chưa kiểm tra"
        layout = QVBoxLayout(self)
        layout.addWidget(label("API & CHI PHÍ", "heading"))
        layout.addWidget(label(DISCLAIMER, "badge"))
        self.table = QTableWidget(4, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Công đoạn",
                "Provider",
                "Chế độ",
                "Credential",
                "Dùng ước tính",
                "Chi phí",
                "Trạng thái",
            ]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().hide()
        self.table.setMinimumHeight(170)
        layout.addWidget(self.table)
        layout.addWidget(label(f"Gemini CLOUD • {GEMINI_MODEL}", "eyebrow"))
        layout.addWidget(
            label(
                "Dịch gửi bản chép lời tới Google; không gửi video/audio. "
                "Điều khoản dữ liệu và quota "
                "phụ thuộc gói Google của bạn. Nút kiểm tra chỉ đọc model, không tạo bản dịch."
                " Gói miễn phí có thể dùng nội dung để cải thiện sản phẩm Google."
            )
        )
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText(
            "Nhập Gemini API key mới • lưu trong Windows Credential Manager"
        )
        self.key_input.setAccessibleName("Gemini API key")
        layout.addWidget(self.key_input)
        actions = QHBoxLayout()
        self.save_key = QPushButton("Lưu khóa")
        self.delete_key = QPushButton("Xóa khóa")
        self.test_key = QPushButton("Kiểm tra kết nối")
        for button in (self.save_key, self.delete_key, self.test_key):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.status = label("Chưa kiểm tra kết nối.")
        layout.addWidget(self.status)
        self.vbee_button = QPushButton("Vbee • Cấu hình / Kiểm tra / Thống kê")
        self.vbee_button.clicked.connect(controller.window.tts.open_manager)
        layout.addWidget(self.vbee_button)
        self.mode = QComboBox()
        self.mode.addItems(["FREE_TIER", "PAID"])
        self.rate = QDoubleSpinBox()
        self.rate.setRange(1, 1_000_000)
        self.rate.setDecimals(2)
        self.budget = QDoubleSpinBox()
        self.budget.setRange(0, 1_000_000_000)
        self.budget.setDecimals(0)
        self.budget.setSpecialValueText("Không đặt ngân sách")
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(1, 100)
        self.threshold.setSuffix(" %")
        self.threshold.setDecimals(0)
        form = QFormLayout()
        form.addRow("Gói tài khoản (tự khai báo)", self.mode)
        form.addRow("USD → VND (tự nhập)", self.rate)
        form.addRow("Ngân sách tháng (VND, tùy chọn)", self.budget)
        form.addRow("Ngưỡng cảnh báo ngân sách", self.threshold)
        layout.addLayout(form)
        try:
            settings = load_settings()
        except (OSError, ValueError) as exc:
            settings = ApiSettings()
            self.status.setText(str(exc))
        self.mode.setCurrentText(settings.mode)
        self.rate.setValue(settings.usd_vnd)
        self.budget.setValue(settings.budget_vnd)
        self.threshold.setValue(settings.warning_percent)
        self.usage = label("")
        self.estimate = label("")
        layout.addWidget(self.estimate)
        layout.addWidget(self.usage)
        self.price_note = label(
            "Token dự án dùng công thức gần đúng, chưa trừ cache. "
            "FREE_TIER không chứng minh yêu cầu miễn phí. "
            '<a href="https://ai.google.dev/gemini-api/docs/pricing">Bảng giá Google</a>'
        )
        self.price_note.setOpenExternalLinks(True)
        layout.addWidget(self.price_note)
        footer = QHBoxLayout()
        self.reset_button = QPushButton("Đặt lại thống kê cục bộ")
        self.save_button = QPushButton("Lưu cài đặt")
        self.close_button = QPushButton("Đóng")
        for button in (self.reset_button, self.save_button, self.close_button):
            footer.addWidget(button)
        layout.addLayout(footer)
        self.save_key.clicked.connect(self._save_key)
        self.delete_key.clicked.connect(self._delete_key)
        self.test_key.clicked.connect(controller.test_connection)
        self.reset_button.clicked.connect(self._reset)
        self.save_button.clicked.connect(self._save_settings)
        self.close_button.clicked.connect(self.reject)
        self.mode.currentTextChanged.connect(self.refresh)
        for spin in (self.rate, self.budget, self.threshold):
            spin.valueChanged.connect(self.refresh)
        self._read_credential_status()
        self.refresh()

    def _read_credential_status(self) -> None:
        try:
            self.credential_status = "Đã lưu • chưa kiểm tra" if self.store.get() else "Thiếu khóa"
        except RuntimeError as exc:
            self.credential_status = "Kho khóa không khả dụng"
            self.status.setText(str(exc))

    def _save_key(self) -> None:
        try:
            self.store.save(self.key_input.text())
            self.key_input.clear()
            self.status.setText("Đã lưu trong Windows Credential Manager; chưa kiểm tra kết nối.")
            self._read_credential_status()
        except (ValueError, RuntimeError) as exc:
            self.status.setText(str(exc))
        self.refresh()

    def _delete_key(self) -> None:
        try:
            self.store.delete()
            self.key_input.clear()
            self.status.setText("Đã xóa Gemini API key.")
            self._read_credential_status()
        except RuntimeError as exc:
            self.status.setText(str(exc))
        self.refresh()

    def _save_settings(self) -> None:
        try:
            save_settings(
                ApiSettings(
                    self.mode.currentText(),
                    self.rate.value(),
                    self.budget.value(),
                    self.threshold.value(),
                )
            )
            self.status.setText("Đã lưu cài đặt chi phí. Tỷ giá do bạn nhập; không tự cập nhật.")
        except (OSError, ValueError):
            self.status.setText("Không lưu được cài đặt chi phí. Kiểm tra quyền ghi.")

    def _reset(self) -> None:
        if (
            QMessageBox.question(
                self,
                "Đặt lại thống kê?",
                "Xóa thống kê trên máy này? Thao tác này không đặt lại quota/hóa đơn Google.",
            )
            == QMessageBox.StandardButton.Yes
        ):
            try:
                UsageLedger().reset()
                TTSUsage().reset()
                self.refresh()
            except Exception:
                self.status.setText("Không đặt lại được thống kê cục bộ.")

    def refresh(self) -> None:
        window = self.controller.window
        busy = window.busy
        for widget in (
            self.save_key,
            self.delete_key,
            self.test_key,
            self.key_input,
            self.reset_button,
            self.save_button,
            self.mode,
            self.rate,
            self.budget,
            self.threshold,
            self.vbee_button,
        ):
            widget.setEnabled(not busy)
        project = window.project
        transcript = project.transcript
        chars = sum(len(s.text) for s in transcript.segments) if transcript else 0
        try:
            groups = len(batches(transcript)) if transcript else 0
            incoming, outgoing = estimate_tokens(chars, groups)
            prices = load_pricing()
            usd = estimate_usd(incoming, outgoing, prices)
            self.price_note.setText(
                "Giá chuẩn: "
                + " • ".join(
                    f"{p.metric}: {p.price_per_unit_usd:g} USD / {p.unit_size:g} "
                    f"(xác minh {p.last_verified_at})"
                    for p in prices
                )
                + "<br>Token dự án dùng công thức gần đúng, chưa trừ cache. "
                "FREE_TIER không chứng minh yêu cầu miễn phí. "
                '<a href="https://ai.google.dev/gemini-api/docs/pricing">Bảng giá Google</a>'
            )
            monthly = UsageLedger().monthly()
            vnd = usd * self.rate.value()
            self.estimate.setText(
                f"Dự án: {chars:,} ký tự • ~{incoming:,} token vào / "
                f"{outgoing:,} token ra • ~{usd:.6f} USD / {vnd:,.0f}đ (giá trả phí)."
            )
            total = monthly["usd"] * self.rate.value()
            self.usage.setText(
                f"Tháng này (UTC, chỉ máy này): {monthly['requests']} lượt gửi • "
                f"{monthly['input_tokens']:,} token vào / {monthly['output_tokens']:,} token ra • "
                f"~{total:,.0f}đ theo token nhận được.\n"
                f"{monthly['unknown']} lượt chưa biết token/chi phí (timeout, hủy hoặc lỗi). "
                "Đối chiếu hóa đơn Google; ngân sách chỉ cảnh báo."
            )
            if (
                self.budget.value()
                and total + vnd >= self.budget.value() * self.threshold.value() / 100
            ):
                self.usage.setText(
                    self.usage.text() + "\nCẢNH BÁO: tháng + dự án đạt ngưỡng ngân sách."
                )
            cost = f"~{vnd:,.0f}đ"
        except Exception:
            self.estimate.setText(
                "Không tính được chi phí; kiểm tra dữ liệu giá/thống kê và độ dài câu."
            )
            self.usage.setText("Thống kê chưa khả dụng.")
            cost = "Chưa biết"
        translated_chars = (
            sum(len(line.text) for line in project.script.lines)
            if project.script
            else sum(map(len, project.translation.texts))
            if project.translation
            else 0
        )
        values = [
            [
                "STT",
                "Faster-Whisper",
                "LOCAL",
                "—",
                f"{transcript.duration:.1f}s" if transcript else "—",
                "0đ",
                window.left.model_status.text(),
            ],
            [
                "Dịch",
                "Gemini",
                self.mode.currentText(),
                self.credential_status,
                f"~{chars:,} ký tự",
                cost,
                "CLOUD • cần bản gốc" if not chars else "CLOUD • sẵn sàng cấu hình",
            ],
            [
                "TTS",
                "Vbee",
                "CLOUD",
                "Đã lưu" if window.tts.configured else "Thiếu App ID/token",
                f"{translated_chars:,} ký tự",
                "Chưa biết",
                window.tts.credential_reason,
            ],
            [
                "Render",
                "FFmpeg",
                "LOCAL",
                "—",
                "—",
                "0đ",
                "Công cụ có • render chưa triển khai"
                if window.tools.paths["ffmpeg"]
                else "Thiếu công cụ",
            ],
        ]
        for row, items in enumerate(values):
            for column, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                self.table.setItem(row, column, item)

    def reject(self) -> None:
        self.key_input.clear()
        if self.controller.job is not None:
            self.close_after_job = True
            self.controller.stop()
            self.status.setText("Đang dừng kiểm tra kết nối…")
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.controller.job is not None:
            self.reject()
            event.ignore()
        else:
            self.key_input.clear()
            event.accept()
