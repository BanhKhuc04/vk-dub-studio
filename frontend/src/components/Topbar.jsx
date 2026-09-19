import React from "react";
import { motion } from "framer-motion";
import { SearchIcon, BellIcon, SparkIcon, ChevronRightIcon } from "../icons.jsx";

export default function Topbar({
  onOpenAsk,
  onOpenSettings,
  searchQuery = "",
  setSearchQuery,
  aiStatus = "Sẵn sàng",
  bridgeStatus = null,
}) {
  // ChatGPT Status resolution
  const chatgptReady = Boolean(bridgeStatus?.chatgpt_logged_in || (bridgeStatus?.chatgpt && bridgeStatus?.chatgpt_ready));
  const chatgptAvailable = Boolean(bridgeStatus?.chatgpt_available || bridgeStatus?.chatgpt);
  const chatgptDot = chatgptReady ? "online" : chatgptAvailable ? "warning" : "offline";
  const chatgptText = chatgptReady
    ? "ChatGPT: Đã kết nối"
    : chatgptAvailable
    ? "ChatGPT: Chờ đăng nhập"
    : "ChatGPT: Chưa mở tab";
  const chatgptTooltip = chatgptReady
    ? "Extension trình duyệt đã kết nối ChatGPT và sẵn sàng dịch tự động"
    : chatgptAvailable
    ? "Tab ChatGPT đã mở nhưng chưa đăng nhập tài khoản"
    : "Chưa mở tab ChatGPT trên trình duyệt Edge/Chrome (Hệ thống sẽ giữ phụ đề gốc để bạn duyệt tại Bước 05)";

  // Vbee Status resolution
  const vbeeReady = Boolean(bridgeStatus?.vbee_logged_in || (bridgeStatus?.vbee && bridgeStatus?.vbee_ready));
  const vbeeAvailable = Boolean(bridgeStatus?.vbee_available || bridgeStatus?.vbee);
  const vbeeDot = vbeeReady ? "online" : vbeeAvailable ? "warning" : "info";
  const vbeeText = vbeeReady
    ? "Vbee: Sẵn sàng"
    : vbeeAvailable
    ? "Vbee: Chờ đăng nhập"
    : "Edge TTS: Sẵn sàng";
  const vbeeTooltip = vbeeReady
    ? "Vbee Studio đã sẵn sàng tạo giọng đọc AI chất lượng cao"
    : vbeeAvailable
    ? "Tab Vbee đã mở nhưng chưa đăng nhập tài khoản"
    : "Tự động kích hoạt Microsoft Edge TTS Neural (Hoài My / Nam Minh) khi chưa kết nối Vbee";

  return (
    <header className="kappak-topbar">
      {/* Left: Brand Logo */}
      <div className="topbar-left">
        <div className="topbar-logo-badge">
          <div className="logo-icon-square">
            <span className="logo-letter">K</span>
            <span className="logo-accent">4</span>
          </div>
          <div className="logo-text-group">
            <span className="logo-title">KAPPAK</span>
            <span className="logo-subtitle">STUDIO WEB V2</span>
          </div>
        </div>
      </div>

      {/* Center: Search Bar Pill (520 - 650px) */}
      <div className="topbar-center">
        <div className="search-pill-container">
          <SearchIcon size={18} className="search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Tìm kiếm công cụ, dự án, mẫu... (Ctrl + K)"
            value={searchQuery}
            onChange={(e) => setSearchQuery && setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Right: Actions & Profile */}
      <div className="topbar-right">
        {/* ChatGPT Status Pill */}
        <div className="bridge-status-pill" title={chatgptTooltip}>
          <span className={`status-dot ${chatgptDot}`} />
          <span className="status-text">{chatgptText}</span>
        </div>

        {/* Vbee Status Pill */}
        <div className="bridge-status-pill" title={vbeeTooltip}>
          <span className={`status-dot ${vbeeDot}`} />
          <span className="status-text">{vbeeText}</span>
        </div>

        {/* Ask KAPPAK Trigger Pill */}
        <motion.button
          whileHover={{ scale: 1.04 }}
          whileTap={{ scale: 0.96 }}
          className="ask-kappak-pill"
          onClick={onOpenAsk}
          title="Mở trợ lý AI Ask KAPPAK"
        >
          <SparkIcon size={15} />
          <span>✦ Ask KAPPAK</span>
        </motion.button>

        {/* Notification Bell with Badge */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="topbar-icon-btn notify"
          aria-label="Thông báo mới"
        >
          <BellIcon size={18} />
          <span className="notify-badge">1</span>
        </motion.button>

        {/* User Avatar + Name */}
        <div className="topbar-user-profile" title="Tài khoản Văn Khúc">
          <div className="user-avatar-circle">VK</div>
          <span className="user-name">Văn Khúc</span>
          <span className="dropdown-caret">ˇ</span>
        </div>
      </div>
    </header>
  );
}
