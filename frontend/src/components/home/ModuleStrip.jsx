import React from "react";
import { motion } from "framer-motion";
import {
  DownloadIcon,
  FolderIcon,
  SparkIcon,
  ScissorsIcon,
  ShareIcon,
  CalendarIcon,
  ArrowRightIcon
} from "../../icons.jsx";

const MODULES = [
  {
    id: "downloader",
    title: "Downloader",
    desc: "Tải video đa nền tảng chất lượng gốc không watermark.",
    icon: DownloadIcon,
    tintClass: "tint-blue",
    iconColor: "#2777FF",
    badge: "v2.1"
  },
  {
    id: "data-studio",
    title: "Data Studio",
    desc: "Quản lý kho tài nguyên, phân tích và đồng bộ dự án.",
    icon: FolderIcon,
    tintClass: "tint-mint",
    iconColor: "#059669",
    badge: null
  },
  {
    id: "auto-video",
    title: "Auto Video",
    desc: "Tạo kịch bản, ghép cảnh và sinh clip tự động bằng AI.",
    icon: SparkIcon,
    tintClass: "tint-violet",
    iconColor: "#7C3AED",
    badge: "AI"
  },
  {
    id: "auto-dub",
    title: "Auto Dub",
    desc: "Bóc băng, dịch giữ ngữ cảnh và lồng tiếng đa ngôn ngữ.",
    icon: ScissorsIcon,
    tintClass: "tint-cyan",
    iconColor: "#0284C7",
    badge: "Hot"
  },
  {
    id: "social",
    title: "Social",
    desc: "Lên lịch đăng bài và phân phối đa kênh TikTok, YouTube.",
    icon: ShareIcon,
    tintClass: "tint-pink",
    iconColor: "#DB2777",
    badge: null
  },
  {
    id: "today",
    title: "Today",
    desc: "Lịch trình nội dung, xu hướng thịnh hành và nhắc việc.",
    icon: CalendarIcon,
    tintClass: "tint-amber",
    iconColor: "#D97706",
    badge: null
  }
];

export default function ModuleStrip({ onSelectModule }) {
  return (
    <section className="kappak-module-strip" aria-label="Danh mục công cụ">
      {MODULES.map((mod, idx) => {
        const Icon = mod.icon;
        return (
          <motion.article
            key={mod.id}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.05, duration: 0.4 }}
            whileHover={{ y: -4 }}
            className={`module-card ${mod.tintClass}`}
            onClick={() => onSelectModule && onSelectModule(mod.id)}
          >
            {/* Top Row: Pastel Icon Tile + Optional Badge */}
            <div className="card-top">
              <div className="icon-tile">
                <Icon size={22} style={{ color: mod.iconColor }} />
              </div>
              {mod.badge && <span className="module-badge">{mod.badge}</span>}
            </div>

            {/* Card Body */}
            <div className="card-body">
              <h2 className="card-title">{mod.title}</h2>
              <p className="card-desc">{mod.desc}</p>
            </div>

            {/* Card Footer: Round Arrow Action Button */}
            <div className="card-footer">
              <div className="card-arrow-circle" aria-label={`Mở ${mod.title}`}>
                <ArrowRightIcon size={16} />
              </div>
            </div>
          </motion.article>
        );
      })}
    </section>
  );
}
