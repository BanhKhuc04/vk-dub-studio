import React, { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { SparkIcon, CloseIcon, ArrowUpIcon, EraserIcon } from "../icons.jsx";

const QUICK_PROMPTS = [
  { label: "Lồng tiếng video 1-chạm", prompt: "Hướng dẫn tôi lồng tiếng video tự động trên KAPPAK Studio" },
  { label: "Tạo kịch bản video ngắn", prompt: "Giúp tôi tạo kịch bản video ngắn viral cho TikTok/YouTube Shorts" },
  { label: "Gợi ý hook viral", prompt: "Gợi ý 5 hook viral cho video review sản phẩm thuộc lĩnh vực [niche] của tôi" },
  { label: "Tối ưu nội dung 9:16", prompt: "Cách tối ưu nội dung video 9:16 cho Reels/TikTok để tăng retention" },
];

const API_BASE = "";

async function streamChat(message, onChunk, onDone, onError) {
  try {
    const res = await fetch(`${API_BASE}/api/ask-kappak/chat-stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `Lỗi server: ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line || !line.startsWith("event:")) continue;

        const eventType = line.slice(6).trim();
        const dataIdx = rawLine.indexOf("data:");
        if (dataIdx === -1) continue;

        const dataLine = rawLine.slice(dataIdx + 5).trim();
        try {
          const data = JSON.parse(dataLine);

          if (eventType === "chunk") {
            onChunk(data.text || "");
          } else if (eventType === "error") {
            onError(data.error || "Đã xảy ra lỗi không xác định.");
            return;
          } else if (eventType === "done") {
            onDone(data.full_text || "");
          }
        } catch (e) {
          // Skip malformed JSON lines
        }
      }
    }
  } catch (err) {
    onError(err.message || "Không thể kết nối server. Hãy chắc chắn KAPPAK Studio đang chạy.");
  }
}

export default function AskKappakDrawer({
  isOpen,
  onClose,
  onExecuteAction,
}) {
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState([
    {
      id: "m_welcome",
      sender: "ai",
      text: "Xin chào! Tôi là trợ lý AI của KAPPAK Studio. Hôm nay bạn muốn tạo hay xử lý nội dung video nào?",
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasApiKey, setHasApiKey] = useState(true);
  const [errorMsg, setErrorMsg] = useState(null);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  // Load history on mount / open
  useEffect(() => {
    if (!isOpen) return;
    fetch(`${API_BASE}/api/ask-kappak/status`)
      .then((r) => r.json())
      .then((d) => {
        setHasApiKey(d.has_api_key);
        if (d.history_count > 0) {
          fetch(`${API_BASE}/api/ask-kappak/history`)
            .then((r) => r.json())
            .then((d) => {
              if (d.history && d.history.length > 0) {
                setMessages((prev) => {
                  const filtered = d.history.filter((m) => m.role !== "system");
                  return filtered.map((m, i) => ({
                    id: `h_${i}`,
                    sender: m.role === "model" ? "ai" : "user",
                    text: m.content,
                  }));
                });
              }
            })
            .catch(() => {});
        }
      })
      .catch(() => setHasApiKey(false));
  }, [isOpen]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(
    async (e) => {
      e?.preventDefault();
      if (!prompt.trim() || isLoading) return;

      const userText = prompt.trim();
      setPrompt("");
      setErrorMsg(null);

      const userMsgId = `u_${Date.now()}`;
      const aiMsgId = `ai_${Date.now() + 1}`;

      // Append user message immediately
      setMessages((prev) => [
        ...prev,
        { id: userMsgId, sender: "user", text: userText },
      ]);

      // Append empty AI message placeholder
      setMessages((prev) => [
        ...prev,
        { id: aiMsgId, sender: "ai", text: "", isStreaming: true },
      ]);

      setIsLoading(true);

      let accumulatedText = "";

      streamChat(
        userText,
        (chunk) => {
          accumulatedText += chunk;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId
                ? { ...m, text: accumulatedText, isStreaming: true }
                : m
            )
          );
        },
        (fullText) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId
                ? { ...m, text: fullText, isStreaming: false }
                : m
            )
          );
          setIsLoading(false);
        },
        (error) => {
          setErrorMsg(error);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId
                ? {
                    ...m,
                    text: `⚠️ ${error}`,
                    isStreaming: false,
                    isError: true,
                  }
                : m
            )
          );
          setIsLoading(false);
        }
      );
    },
    [prompt, isLoading]
  );

  const handleClear = useCallback(() => {
    fetch(`${API_BASE}/api/ask-kappak/clear`, { method: "POST" }).catch(() => {});
    setMessages([
      {
        id: "m_welcome",
        sender: "ai",
        text: "Đã xóa lịch sử. Bạn muốn làm gì tiếp theo?",
      },
    ]);
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleQuickPrompt = (p) => {
    setPrompt(p.prompt);
    inputRef.current?.focus();
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
                  <p className="ask-subtitle">
                    {hasApiKey
                      ? "Đã kết nối Gemini"
                      : "⚠️ Chưa có API key"}
                  </p>
                </div>
              </div>
              <div className="ask-header-actions">
                <button
                  className="ask-icon-btn"
                  onClick={handleClear}
                  title="Xóa lịch sử"
                  aria-label="Xóa lịch sử trò chuyện"
                >
                  <EraserIcon size={16} />
                </button>
                <button
                  className="ask-close-btn"
                  onClick={onClose}
                  aria-label="Đóng bảng trợ lý"
                >
                  <CloseIcon size={18} />
                </button>
              </div>
            </div>

            {/* API Key Warning Banner */}
            {!hasApiKey && (
              <div className="ask-warning-banner">
                <span>
                  Chưa có Gemini API key.{" "}
                  <strong>Vui lòng mở Cài đặt → API &amp; Chi phí</strong> để nhập key.
                </span>
              </div>
            )}

            {/* Quick action chips */}
            <div className="ask-quick-chips">
              {QUICK_PROMPTS.map((p, idx) => (
                <button
                  key={idx}
                  className="ask-chip"
                  onClick={() => handleQuickPrompt(p)}
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
                  <div className={`ask-message-bubble ${m.isError ? "ask-error-bubble" : ""}`}>
                    {m.text}
                    {m.isStreaming && (
                      <span className="ask-cursor" aria-hidden="true">▊</span>
                    )}
                  </div>
                </div>
              ))}

              {/* Error message toast */}
              <AnimatePresence>
                {errorMsg && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="ask-error-toast"
                  >
                    ⚠️ {errorMsg}
                  </motion.div>
                )}
              </AnimatePresence>

              <div ref={chatEndRef} />
            </div>

            {/* Input Prompt Box */}
            <form className="ask-input-form" onSubmit={handleSend}>
              <div className="ask-input-wrapper">
                <textarea
                  className="ask-prompt-input"
                  placeholder="Nhập yêu cầu sáng tạo của bạn..."
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={1}
                  ref={inputRef}
                  disabled={isLoading}
                />
                <button
                  type="submit"
                  className={`ask-send-btn ${prompt.trim() && !isLoading ? "active" : ""}`}
                  disabled={!prompt.trim() || isLoading}
                  aria-label="Gửi yêu cầu"
                >
                  {isLoading ? (
                    <span className="ask-spinner" aria-label="Đang xử lý" />
                  ) : (
                    <ArrowUpIcon size={17} />
                  )}
                </button>
              </div>
              <span className="ask-input-hint">Nhấn Enter để gửi • Shift+Enter xuống dòng</span>
            </form>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
