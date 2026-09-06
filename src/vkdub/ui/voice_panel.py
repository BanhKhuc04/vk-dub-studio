from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QPushButton,
    QVBoxLayout,
)

from vkdub.domain.voice import DEFAULT_LABEL, DEFAULT_VOICE
from vkdub.ui.left_config_panel import label


class VoicePanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label("GIỌNG ĐỌC • CLOUD", "eyebrow"))
        self.provider = QComboBox()
        self.provider.addItem("Vbee • API chính thức", "vbee")
        self.provider.addItem("ElevenLabs • Đa cảm xúc (Free 10k/tháng)", "elevenlabs")
        self.provider.setToolTip("Chọn nhà cung cấp TTS: Vbee hoặc ElevenLabs.")
        self.voice = QComboBox()
        self.voice.addItem(DEFAULT_LABEL, DEFAULT_VOICE)
        self.voice.setAccessibleName("Giọng đọc")
        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.8, 1.3)
        self.speed.setSingleStep(0.05)
        self.speed.setDecimals(2)
        self.speed.setValue(1.0)
        self.speed.setSuffix("x")
        self.volume = QDoubleSpinBox()
        self.volume.setRange(0, 100)
        self.volume.setValue(100)
        self.volume.setSuffix(" %")
        form = QFormLayout()
        form.addRow("Provider", self.provider)
        form.addRow("Giọng", self.voice)
        form.addRow("Tốc độ", self.speed)
        form.addRow("Âm lượng nghe", self.volume)
        layout.addLayout(form)
        self.settings = QPushButton("Cấu hình / Kiểm tra Vbee")
        self.retry = QPushButton("Tạo tiếp / Thử lại câu lỗi")
        self.listen = QPushButton("Nghe voice câu đang chọn")
        self.status = label("Thiếu App ID / token Vbee.")
        for widget in (self.settings, self.status, self.retry, self.listen):
            layout.addWidget(widget)
        layout.addWidget(label("Chỉ gửi kịch bản đã duyệt. Có thể tính phí theo gói Vbee."))
