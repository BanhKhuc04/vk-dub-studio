import React from "react";
import { motion } from "framer-motion";
import { ClockIcon, ArrowRightIcon, MoreIcon } from "../../icons.jsx";

const SAMPLE_PROJECTS = [
  {
    id: "proj_1",
    title: "Hành trình Đà Lạt",
    duration: "02:14",
    updated: "16/09/2025",
    thumb: "/kappak/thumb_sample_1.png"
  },
  {
    id: "proj_2",
    title: "Giới thiệu sản phẩm",
    duration: "00:38",
    updated: "15/09/2025",
    thumb: "/kappak/thumb_sample_2.png"
  },
  {
    id: "proj_3",
    title: "Apple Minimalist Video",
    duration: "01:27",
    updated: "14/09/2025",
    thumb: "/kappak/thumb_sample_3.png"
  }
];

export default function RecentProjectsSection({ onOpenProject, onShowAll }) {
  return (
    <div className="bottom-card recent-projects-card">
      {/* Header Row */}
      <div className="bottom-card-header">
        <div className="header-title-group">
          <ClockIcon size={18} className="header-icon" />
          <h2 className="header-title">Dự án gần đây</h2>
        </div>
        <button className="header-link-btn" onClick={onShowAll}>
          <span>Xem tất cả</span>
          <ArrowRightIcon size={14} />
        </button>
      </div>

      {/* 3 Projects Grid */}
      <div className="projects-grid">
        {SAMPLE_PROJECTS.map((proj) => (
          <motion.div
            key={proj.id}
            whileHover={{ y: -3 }}
            className="project-item"
            onClick={() => onOpenProject && onOpenProject(proj)}
          >
            {/* Thumbnail Box */}
            <div className="project-thumb-box">
              <img
                src={proj.thumb}
                alt={proj.title}
                className="project-thumb-img"
                onError={(e) => {
                  e.target.style.background = "linear-gradient(135deg, #2777FF 0%, #0A1738 100%)";
                }}
              />
              <span className="project-duration">{proj.duration}</span>
            </div>

            {/* Info Row */}
            <div className="project-info-row">
              <div className="project-text">
                <span className="project-name" title={proj.title}>
                  {proj.title}
                </span>
                <span className="project-date">Cập nhật {proj.updated}</span>
              </div>
              <button
                className="project-menu-btn"
                aria-label="Tùy chọn dự án"
                onClick={(e) => {
                  e.stopPropagation();
                }}
              >
                <MoreIcon size={16} />
              </button>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
