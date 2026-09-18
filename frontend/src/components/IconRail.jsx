import React from "react";
import { motion } from "framer-motion";
import {
  HomeIcon,
  FolderIcon,
  DownloadIcon,
  VideoIcon,
  SparkIcon,
  ScissorsIcon,
  ShareIcon,
  CalendarIcon,
  HelpIcon,
  GearIcon,
  SunIcon,
  MoonIcon,
  LogoGlyph
} from "../icons.jsx";

const TOP_ITEMS = [
  { id: "home", label: "Trang chủ", icon: HomeIcon },
  { id: "projects", label: "Dự án & Data", icon: FolderIcon },
  { id: "downloader", label: "Trình tải video", icon: DownloadIcon },
  { id: "auto-video", label: "Tạo Video Tự động", icon: SparkIcon },
  { id: "auto-dub", label: "Lồng tiếng Auto Dub", icon: ScissorsIcon },
  { id: "social", label: "Mạng xã hội", icon: ShareIcon },
  { id: "today", label: "Hôm nay", icon: CalendarIcon },
];

export default function IconRail({
  activeTab = "home",
  onSelectTab,
  dark,
  setDark,
  onOpenSettings
}) {
  return (
    <aside className="icon-rail" aria-label="Thanh điều hướng chính">
      {/* Top Window Control Simulation Dots */}
      <div className="rail-window-dots">
        <span className="dot dot-close" />
        <span className="dot dot-minimize" />
        <span className="dot dot-maximize" />
      </div>

      {/* Main Navigation Icons */}
      <nav className="rail-nav">
        {TOP_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <motion.button
              key={item.id}
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.94 }}
              className={`rail-item ${isActive ? "active" : ""}`}
              onClick={() => onSelectTab && onSelectTab(item.id)}
              aria-label={item.label}
              title={item.label}
            >
              <Icon size={21} />
              {isActive && (
                <motion.div
                  layoutId="activeRailIndicator"
                  className="rail-active-glow"
                  transition={{ type: "spring", stiffness: 450, damping: 32 }}
                />
              )}
            </motion.button>
          );
        })}
      </nav>

      {/* Spacer */}
      <div className="rail-spacer" />

      {/* Bottom Actions */}
      <div className="rail-bottom">
        <motion.button
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.94 }}
          className="rail-item"
          aria-label="Trợ giúp & Hướng dẫn"
          title="Trợ giúp"
          onClick={() => {}}
        >
          <HelpIcon size={20} />
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.94 }}
          className="rail-item"
          aria-label="Đổi giao diện Sáng / Tối"
          title={dark ? "Chuyển sang giao diện Sáng" : "Chuyển sang giao diện Tối"}
          onClick={() => setDark && setDark((v) => !v)}
        >
          {dark ? <SunIcon size={20} /> : <MoonIcon size={20} />}
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.94 }}
          className="rail-item"
          aria-label="Cài đặt hệ thống"
          title="Cài đặt"
          onClick={onOpenSettings}
        >
          <GearIcon size={20} />
        </motion.button>

        {/* Brand Logo Glyph at bottom */}
        <div className="rail-brand-bottom" title="KAPPAK Studio V2">
          <div className="rail-logo-box">
            <span className="rail-logo-text">K4</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
