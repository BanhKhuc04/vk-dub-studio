import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { ClockIcon, ArrowRightIcon, MoreIcon } from "../../icons.jsx";

export default function RecentProjectsSection({ onOpenProject, onShowAll }) {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/projects/recent")
      .then((res) => (res.ok ? res.json() : Promise.reject(res)))
      .then((data) => {
        if (data && Array.isArray(data.projects)) {
          setProjects(data.projects);
        }
      })
      .catch((err) => {
        console.warn("Could not fetch real projects, fallback to empty:", err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

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

      {/* Projects Grid */}
      <div className="projects-grid">
        {loading ? (
          <div style={{ color: "var(--text-2)", fontSize: 13, padding: "16px 0" }}>Đang tải danh sách dự án...</div>
        ) : projects.length === 0 ? (
          <div style={{ color: "var(--text-2)", fontSize: 13, padding: "16px 0" }}>Chưa có dự án nào gần đây.</div>
        ) : (
          projects.slice(0, 3).map((proj) => (
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
          ))
        )}
      </div>
    </div>
  );
}
