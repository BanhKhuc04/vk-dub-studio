"""Centralized DOM selectors, URLs, and timing constants for Vbee Dubbing Studio.

If Vbee updates its web interface or layout, update the selectors in this file
without modifying the core automation engine or application workflow.
"""

# URLs
VBEE_HOME_URL = "https://vbee.vn"
VBEE_LOGIN_URL = "https://vbee.vn/login"
VBEE_DUBBING_URL = "https://studio.vbee.vn/studio/dubbing"
VBEE_STUDIO_URL = "https://studio.vbee.vn"

# Timeouts & Intervals (seconds / milliseconds)
DEFAULT_PAGE_TIMEOUT_MS = 35_000
DEFAULT_NAVIGATION_TIMEOUT_MS = 45_000
DEFAULT_POLL_INTERVAL_S = 2.0
DEFAULT_PROCESSING_TIMEOUT_S = 600.0  # 10 minutes max for long subtitle files
LOGIN_CHECK_INTERVAL_S = 1.5
LOGIN_WAIT_TIMEOUT_S = 300.0  # 5 minutes for user to complete manual login

# Login detection selectors
LOGGED_IN_INDICATORS = (
    # Profile avatar, user dropdown, logout button, account info
    "div[class*='user-info']",
    "div[class*='avatar']",
    "img[class*='avatar']",
    "button[class*='user']",
    "div[class*='account']",
    "div[class*='profile']",
    "a[href*='logout']",
    "button:has-text('Đăng xuất')",
    "span[class*='user-name']",
    ".ant-dropdown-trigger",
    ".user-avatar",
)

LOGIN_REQUIRED_INDICATORS = (
    # Login buttons, login inputs, auth page markers
    "input[type='password']",
    "button:has-text('Đăng nhập')",
    "a:has-text('Đăng nhập')",
    "form[class*='login']",
    "div[class*='login-form']",
    ".login-box",
    "a[href*='login']",
)

# Dubbing studio selectors
DUBBING_TAB_SELECTORS = (
    "div[role='tab']:has-text('Chuyển phụ đề')",
    "div[role='tab']:has-text('Thuyết minh')",
    "div[role='tab']:has-text('Dubbing')",
    "a:has-text('Chuyển phụ đề')",
    "button:has-text('Chuyển phụ đề')",
)

# File upload selectors
FILE_INPUT_SELECTORS = (
    "input[type='file'][accept*='.srt']",
    "input[type='file']",
    ".ant-upload input[type='file']",
)

UPLOAD_BUTTON_SELECTORS = (
    "button:has-text('Tải file lên')",
    "button:has-text('Tải lên')",
    "div[class*='upload-box']",
    ".ant-upload-drag",
    "span:has-text('Chọn file SRT')",
    "span:has-text('Tải lên file')",
)

# Voice configuration selectors
VOICE_SELECT_TRIGGER = (
    "div[class*='voice-select']",
    "div[class*='select-voice']",
    ".ant-select:has(.ant-select-selection-item)",
    "div:has-text('Chọn giọng đọc')",
    "span:has-text('Chọn giọng')",
    "div:has-text('Giọng đọc')",
    "button:has-text('Đổi giọng')",
)

VOICE_NGOC_HUYEN_OPTIONS = (
    "div.ant-select-item-option:has-text('Ngọc Huyền')",
    "div[role='option']:has-text('Ngọc Huyền')",
    "div:has-text('HN - Ngọc Huyền')",
    "span:has-text('HN - Ngọc Huyền')",
    "span:has-text('Ngọc Huyền')",
    "li:has-text('Ngọc Huyền')",
)

SPEED_TRIGGER = (
    ".speed [data-testid='ArrowDropDownIcon']",
    ".speed .MuiAutocomplete-popupIndicator",
    ".speed button",
    "div[class*='speed']",
    "span:has-text('Tốc độ')",
    "button:has-text('1x')",
    "span:has-text('1x')",
    "span:has-text('1.0x')",
)

SPEED_OPTIONS_1X = (
    "li.MuiMenuItem-root:has-text('1x')",
    "div.ant-select-item-option:has-text('1.0x')",
    "div.ant-select-item-option:has-text('1x')",
    "div[role='option']:has-text('1.0x')",
    "div[role='option']:has-text('1x')",
    "span:has-text('1.0x')",
    "span:has-text('1x (Chuẩn)')",
    "li:has-text('1.0x')",
    "li:has-text('1x')",
)

FORMAT_OPTIONS_MP3 = (
    "button:has-text('MP3')",
    "span:has-text('MP3')",
    "input[value='mp3']",
    "label:has-text('MP3')",
    "div.ant-radio-button-wrapper:has-text('MP3')",
)

# Conversion submission
SUBMIT_CONVERT_BUTTONS = (
    "button:has-text('Chuyển phụ đề')",
    "button:has-text('Bắt đầu chuyển')",
    "button:has-text('Tạo thuyết minh')",
    "button:has-text('Tạo voice')",
    "button:has-text('Chuyển đổi')",
    "button[class*='btn-convert']",
    "button[class*='btn-submit']",
)

CONFIRM_MODAL_BUTTONS = (
    "button.ant-btn-primary:has-text('Xác nhận')",
    "button.ant-btn-primary:has-text('Đồng ý')",
    "button:has-text('Tiếp tục')",
)

# Processing indicators
PROCESSING_INDICATORS = (
    "span:has-text('Đang xử lý')",
    "div:has-text('Đang chuyển')",
    "div[class*='loading']",
    ".ant-spin-spinning",
    "div[class*='progress']",
    "div[role='progressbar']",
    ".ant-progress",
)

# Completion indicators
COMPLETION_INDICATORS = (
    "button:has(svg[data-testid*='Download'])",
    "svg[data-testid*='Download']",
    "svg[data-testid='DownloadRoundedIcon']",
    "span:has-text('Hoàn thành')",
    "span:has-text('Thành công')",
    "button:has-text('Tải về')",
    "button:has-text('Tải xuống')",
    "button:has-text('Tải file')",
    "a[download]",
    "div[class*='download']",
)

# Download button selectors
DOWNLOAD_BUTTON_SELECTORS = (
    "button:has(svg[data-testid*='Download'])",
    "svg[data-testid*='Download']",
    "svg[data-testid='DownloadRoundedIcon']",
    "button:has-text('Tải xuống')",
    "button:has-text('Tải về')",
    "button:has-text('Tải audio')",
    "button:has-text('Tải file MP3')",
    "button:has-text('Tải MP3')",
    "a:has-text('Tải xuống')",
    "a:has-text('Tải về')",
    "div[class*='btn-download']",
    "button[class*='download']",
    "span[aria-label='download']",
    "i[class*='download']",
)

DOWNLOAD_FORMAT_MP3 = (
    "li:has-text('MP3')",
    "div:has-text('MP3')",
    "span:has-text('MP3')",
)

DOWNLOAD_FORMAT_WAV = (
    "li:has-text('WAV')",
    "div:has-text('WAV')",
    "span:has-text('WAV')",
)

# Error and quota selectors
QUOTA_ERROR_SELECTORS = (
    "div:has-text('hết ký tự')",
    "div:has-text('không đủ số dư')",
    "div:has-text('không đủ credit')",
    "div:has-text('vượt quá số ký tự')",
    "div:has-text('nâng cấp gói')",
    ".ant-message-error:has-text('ký tự')",
    ".ant-notification-notice-error",
)

GENERAL_ERROR_SELECTORS = (
    ".ant-message-error",
    ".ant-alert-error",
    "div[class*='error-message']",
    "div[role='alert']",
    ".toast-error",
)
