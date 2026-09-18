import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { SparkIcon, CloseIcon, ArrowUpIcon, ScissorsIcon, DownloadIcon, WandIcon } from "../icons.jsx";

const QUICK_PROMPTS = [
  { label: "Lồng tiếng video 1-chạm", action: "dub" },
  { label: "Tải video Douyin không logo", action: "download" },
  { label: "Tạo kịch bản review sản phẩm", action: "script" },
  { label: "Che mờ phụ đề cũ trên video", action: "blur" }
];

export default function AskKappakDrawer({
  isOpen,
  onClose,
  onExecuteAction
}) {
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState([
    {
      id: "m_welcome",
      sender: "ai",
      text: "Xin chào Văn Khúc! Tôi là trợ lý AI của KAPPAK Studio. Hôm nay bạn muốn tạo hay xử lý nội dung video nào?"
    }
  ]);

  const handleSend = (e) => {
    e?.preventDefault();
    if (!prompt.trim()) return;

    const userText = prompt.trim();
    setMessages((prev) => [
      ...prev,
      { id: `u_${Date.now()}`, sender: "user", text: userText },
      {
        id: `ai_${Date.now()}`,
        sender: "ai",
        text: `Đã tiếp nhận yêu cầu: "${userText}". Tôi có thể hỗ trợ bạn mở công cụ Auto Dub hoặc tải nội dung liên quan ngay lập tức.`
      }
    ]);
    setPrompt("");
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="ask-drawer-backdrop"
            onClick={onClose}
          />

          {/* Right Glass Drawer Panel */}
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 32 }}
            className="ask-drawer-panel"
            aria-label="Khung trợ lý Ask KAPPAK"
          >
            {/* Header */}
            <div className="ask-drawer-header">
              <div className="ask-title-group">
                <div className="ask-sparkle-badge">
                  <SparkIcon size={18} />
                </div>
                <div>
                  <h2 className="ask-title">✦ KAPPAK AI</h2>
                  <p className="ask-subtitle">Bạn muốn làm gì hôm nay?</p>
                </div>
              </div>
              <button
                className="ask-close-btn"
                onClick={onClose}
                aria-label="Đóng bảng trợ lý"
              >
                <CloseIcon size={18} />
              </button>
            </div>

            {/* Quick action chips */}
            <div className="ask-quick-chips">
              {QUICK_PROMPTS.map((p, idx) => (
                <button
                  key={idx}
                  className="ask-chip"
                  onClick={() => {
                    setPrompt(p.label);
                  }}
                >
                  <span>{p.label}</span>
                </button>
              ))}
            </div>

            {/* Chat Conversation Area */}
            <div className="ask-chat-history">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={`ask-message-row ${m.sender === "user" ? "user-row" : "ai-row"}`}
                >
                  <div className="ask-message-bubble">
                    {m.text}
                  </div>
                </div>
              ))}
            </div>

            {/* Input Prompt Box */}
            <form className="ask-input-form" onSubmit={handleSend}>
              <div className="ask-input-wrapper">
                <input
                  type="text"
                  className="ask-prompt-input"
                  placeholder="Nhập yêu cầu sáng tạo của bạn..."
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  autoFocus
                />
                <button
                  type="submit"
                  className={`ask-send-btn ${prompt.trim() ? "active" : ""}`}
                  disabled={!prompt.trim()}
                  aria-label="Gửi yêu cầu"
                >
                  <ArrowUpIcon size={17} />
                </button>
              </div>
              <span className="ask-input-hint">Nhấn Enter để gửi yêu cầu</span>
            </form>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
