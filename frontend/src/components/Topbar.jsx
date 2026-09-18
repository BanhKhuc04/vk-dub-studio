import React from "react";
import { motion } from "framer-motion";
import { SearchIcon, BellIcon, SparkIcon, ChevronRightIcon } from "../icons.jsx";

export default function Topbar({
  onOpenAsk,
  onOpenSettings,
  searchQuery = "",
  setSearchQuery,
  aiStatus = "Sẵn sàng"
}) {
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
        {/* AI Status Badge */}
        <div className="ai-status-pill" title="Hệ thống AI đang hoạt động bình thường">
          <span className="status-dot online" />
          <span className="status-text">AI {aiStatus}</span>
          <span className="dropdown-caret">ˇ</span>
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
