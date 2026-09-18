import React from "react";
import { motion } from "framer-motion";
import { PlayIcon, ChevronRightIcon, PlusIcon, FileIcon } from "../../icons.jsx";

export default function ContinueWorkSection({ onNewProject, activeSession }) {
  return (
    <div className="bottom-card continue-work-card">
      {/* Header Row */}
      <div className="bottom-card-header">
        <div className="header-title-group">
          <PlayIcon size={18} className="header-icon" />
          <h2 className="header-title">Tiếp tục công việc</h2>
        </div>
        <span className="header-caret" aria-hidden="true">›</span>
      </div>

      {/* Content Body */}
      <div className="continue-body">
        {activeSession ? (
          <div className="active-session-box">
            <div className="session-icon-tile">
              <FileIcon size={24} />
            </div>
            <div className="session-details">
              <span className="session-name">{activeSession.name}</span>
              <span className="session-progress">Đang ở bước {activeSession.step}/5</span>
            </div>
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              className="continue-primary-btn"
              onClick={activeSession.onResume}
            >
              Tiếp tục dự án
            </motion.button>
          </div>
        ) : (
          <div className="empty-session-box">
            <div className="empty-icon-capsule">
              <PlayIcon size={20} />
            </div>
            <h3 className="empty-title">Chưa có phiên làm việc gần đây</h3>
            <p className="empty-desc">
              Hãy bắt đầu một dự án hoặc khám phá các công cụ AI để tạo nội dung tuyệt vời.
            </p>
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              className="continue-primary-btn"
              onClick={onNewProject}
            >
              <PlusIcon size={16} />
              <span>Tạo dự án mới</span>
            </motion.button>
          </div>
        )}
      </div>
    </div>
  );
}
