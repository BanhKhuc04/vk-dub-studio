"""State machine definitions for Vbee Voice automation workflow."""

from enum import StrEnum


class WorkflowState(StrEnum):
    IDLE = "IDLE"
    VALIDATING = "VALIDATING"
    EXPORTING_SRT = "EXPORTING_SRT"
    OPENING_VBEE = "OPENING_VBEE"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    UPLOADING_SRT = "UPLOADING_SRT"
    CONFIGURING_VOICE = "CONFIGURING_VOICE"
    SUBMITTING = "SUBMITTING"
    PROCESSING = "PROCESSING"
    DOWNLOADING = "DOWNLOADING"
    PROCESSING_AUDIO = "PROCESSING_AUDIO"
    IMPORTING_AUDIO = "IMPORTING_AUDIO"
    READY = "READY"
    ERROR = "ERROR"

    @property
    def label(self) -> str:
        labels = {
            self.IDLE: "Sẵn sàng",
            self.VALIDATING: "Đang kiểm tra điều kiện kịch bản và công cụ",
            self.EXPORTING_SRT: "Đang xuất file SRT tiếng Việt",
            self.OPENING_VBEE: "Đang mở Vbee Dubbing Studio",
            self.LOGIN_REQUIRED: "Cần đăng nhập Vbee trên trình duyệt",
            self.UPLOADING_SRT: "Đang tải file SRT lên Vbee",
            self.CONFIGURING_VOICE: "Đang cấu hình giọng đọc HN - Ngọc Huyền & thông số",
            self.SUBMITTING: "Đang yêu cầu chuyển phụ đề",
            self.PROCESSING: "Vbee đang xử lý phụ đề thành voice…",
            self.DOWNLOADING: "Đang tải file âm thanh kết quả",
            self.PROCESSING_AUDIO: "Đang chuẩn hóa âm thanh qua FFmpeg",
            self.IMPORTING_AUDIO: "Đang nhập âm thanh vào project VK Dub Studio",
            self.READY: "Hoàn tất! Voice Vbee đã sẵn sàng",
            self.ERROR: "Có lỗi xảy ra trong quá trình tạo voice",
        }
        return labels.get(self, self.value)

    @property
    def is_active(self) -> bool:
        """True if workflow is currently in an ongoing/in-flight process."""
        return self not in (self.IDLE, self.LOGIN_REQUIRED, self.READY, self.ERROR)

    @property
    def is_terminal(self) -> bool:
        """True if workflow has completed or failed."""
        return self in (self.READY, self.ERROR)

    @property
    def step_index(self) -> int:
        """Sequential 0-indexed step number for checklist progression."""
        order = [
            self.IDLE,
            self.VALIDATING,
            self.EXPORTING_SRT,
            self.OPENING_VBEE,
            self.UPLOADING_SRT,
            self.CONFIGURING_VOICE,
            self.SUBMITTING,
            self.PROCESSING,
            self.DOWNLOADING,
            self.PROCESSING_AUDIO,
            self.IMPORTING_AUDIO,
            self.READY,
        ]
        return order.index(self) if self in order else -1


# Checklist items shown in UI:
CHECKLIST_STEPS = (
    ("export", "Xuất file SRT tiếng Việt"),
    ("open", "Mở Vbee Dubbing Studio"),
    ("upload", "Tải file SRT lên hệ thống Vbee"),
    ("process", "Vbee chuyển đổi phụ đề thành voice"),
    ("download", "Tải file âm thanh kết quả"),
    ("import", "Đồng bộ voice vào project VK Dub Studio"),
)
