import React from "react";
import { motion } from "framer-motion";
import { LightbulbIcon, SparkIcon, ArrowRightIcon } from "../../icons.jsx";

export default function AISuggestionSection({ onTryAI }) {
  return (
    <div className="bottom-card ai-suggestion-card">
      {/* Header Row */}
      <div className="bottom-card-header">
        <div className="header-title-group">
          <LightbulbIcon size={18} className="header-icon" />
          <h2 className="header-title">Gợi ý bởi AI</h2>
        </div>
        <span className="header-caret" aria-hidden="true">›</span>
      </div>

      {/* Inner Pastel Gradient Card */}
      <div className="ai-suggestion-inner">
        <div className="ai-suggestion-sparkle">
          <SparkIcon size={22} />
        </div>
        <h3 className="ai-suggestion-title">
          Biến ý tưởng thành video chỉ trong vài phút
        </h3>
        <p className="ai-suggestion-desc">
          Thử tạo video từ một đoạn mô tả ngắn với trợ lý AI của KAPPAK.
        </p>
        <motion.button
          whileHover={{ scale: 1.03, x: 2 }}
          whileTap={{ scale: 0.97 }}
          className="ai-suggestion-btn"
          onClick={onTryAI}
        >
          <span>Dùng thử ngay</span>
          <ArrowRightIcon size={14} />
        </motion.button>
      </div>
    </div>
  );
}
