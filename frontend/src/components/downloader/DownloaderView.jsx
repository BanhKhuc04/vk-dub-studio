import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  DownloadIcon,
  PlayIcon,
  SparkIcon,
  CheckIcon,
  FolderIcon,
  RefreshIcon,
  CloseIcon,
  ChevronRightIcon,
  GlobeIcon,
  FileIcon,
} from "../../icons.jsx";

const PLATFORMS = [
  { name: "TikTok", color: "#FE2C55" },
  { name: "YouTube", color: "#FF0000" },
  { name: "Douyin", color: "#000000" },
  { name: "Facebook", color: "#1877F2" },
  { name: "Instagram", color: "#E4405F" },
];

function formatFileSize(bytes) {
  const b = Number(bytes);
  if (!b || isNaN(b) || b <= 0) return "--";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1)} MB`;
  return `${(b / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export default function DownloaderView({ onOpenInDubStudio, onBackHome }) {
  const [url, setUrl] = useState("");
  const [quality, setQuality] = useState("best");
  const [inspecting, setInspecting] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [downloadMsg, setDownloadMsg] = useState("");
  const [meta, setMeta] = useState(null);
  const [downloadResult, setDownloadResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Fetch download history
  const fetchHistory = () => {
    setLoadingHistory(true);
    fetch("/api/downloader/history")
      .then((res) => (res.ok ? res.json() : Promise.reject(res)))
      .then((data) => {
        if (data && Array.isArray(data.assets)) {
          setHistory(data.assets);
        }
      })
      .catch((err) => console.warn("Failed to fetch download history:", err))
      .finally(() => setLoadingHistory(false));
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  // Inspect URL metadata
  const handleInspect = async () => {
    if (!url.trim()) {
      setErrorMsg("Vui lòng dán liên kết video.");
      return;
    }
    setErrorMsg("");
    setInspecting(true);
    setMeta(null);
    setDownloadResult(null);

    try {
      const res = await fetch("/api/downloader/inspect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Không thể phân tích liên kết.");
      }
      setMeta(data.metadata);
    } catch (err) {
      setErrorMsg(err.message || "Lỗi kiểm tra liên kết video.");
    } finally {
      setInspecting(false);
    }
  };

  // Start Download
  const handleDownload = async () => {
    if (!url.trim()) return;
    setErrorMsg("");
    setDownloading(true);
    setDownloadProgress(20);
    setDownloadMsg("Đang kết nối và chuẩn bị tải video...");
    setDownloadResult(null);

    const timer = setInterval(() => {
      setDownloadProgress((prev) => (prev < 90 ? prev + Math.floor(Math.random() * 15 + 5) : prev));
    }, 400);

    try {
      const res = await fetch("/api/downloader/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim(), quality }),
      });
      const data = await res.json();
      clearInterval(timer);
      if (!res.ok) {
        throw new Error(data.detail || "Tải video thất bại.");
      }
      setDownloadProgress(100);
      setDownloadMsg("Tải hoàn tất! Đã đăng ký tài nguyên vào thư viện.");
      setDownloadResult(data.asset);
      fetchHistory();
    } catch (err) {
      clearInterval(timer);
      setErrorMsg(err.message || "Lỗi trong quá trình tải video.");
    } finally {
      setDownloading(false);
    }
  };

  // Paste from clipboard
  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        setUrl(text.trim());
        setErrorMsg("");
      }
    } catch (e) {
      console.warn("Could not read clipboard:", e);
    }
  };

  return (
    <div className="kappak-scroll-area">
      <div className="kappak-home-container" style={{ padding: "32px 36px 60px" }}>
        {/* Top Breadcrumb & Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <button
                type="button"
                onClick={onBackHome}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--text-2)",
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                Trang chủ
              </button>
              <span style={{ color: "var(--text-2)", fontSize: 12 }}>/</span>
              <span style={{ color: "var(--primary)", fontSize: 12, fontWeight: 700 }}>Downloader</span>
            </div>
            <h1 style={{ fontSize: 26, fontWeight: 800, color: "var(--text)", margin: 0, letterSpacing: "-0.5px" }}>
              Universal Video Downloader
            </h1>
            <p style={{ color: "var(--text-2)", fontSize: 13, marginTop: 4, marginBottom: 0 }}>
              Tải video gốc đa nền tảng, tự động tính băm SHA-256 chống trùng lặp và chuyển 1-chạm sang Auto Dub Studio.
            </p>
          </div>

          {/* Supported Platform Badges */}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
            {PLATFORMS.map((p) => (
              <span
                key={p.name}
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: "4px 10px",
                  borderRadius: "999px",
                  background: "rgba(255,255,255,0.85)",
                  border: "1px solid rgba(76,104,153,0.12)",
                  color: "var(--text)",
                  boxShadow: "0 2px 6px rgba(52,78,130,0.04)",
                }}
              >
                {p.name}
              </span>
            ))}
          </div>
        </div>

        {/* URL Input & Controls Card */}
        <div
          className="bottom-card"
          style={{
            padding: 24,
            marginBottom: 20,
            background: "rgba(255, 255, 255, 0.88)",
            border: "1px solid rgba(76, 104, 153, 0.14)",
          }}
        >
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <div style={{ position: "relative", flex: 1 }}>
              <input
                type="text"
                placeholder="Dán liên kết TikTok, YouTube, Douyin, Facebook, Instagram..."
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value);
                  setErrorMsg("");
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleInspect();
                }}
                style={{
                  width: "100%",
                  height: 46,
                  padding: "0 40px 0 16px",
                  borderRadius: "12px",
                  border: "1px solid rgba(76,104,153,0.20)",
                  background: "#FFFFFF",
                  fontSize: 13,
                  fontWeight: 500,
                  color: "var(--text)",
                  outline: "none",
                  boxShadow: "inset 0 1px 3px rgba(0,0,0,0.02)",
                }}
              />
              {url ? (
                <button
                  type="button"
                  onClick={() => {
                    setUrl("");
                    setMeta(null);
                    setDownloadResult(null);
                  }}
                  style={{
                    position: "absolute",
                    right: 12,
                    top: "50%",
                    transform: "translateY(-50%)",
                    background: "none",
                    border: "none",
                    color: "var(--text-2)",
                    cursor: "pointer",
                    padding: 4,
                  }}
                >
                  <CloseIcon size={14} />
                </button>
              ) : null}
            </div>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="button"
              onClick={handlePaste}
              className="continue-primary-btn"
              style={{
                background: "#FFFFFF",
                color: "var(--text)",
                border: "1px solid rgba(76,104,153,0.2)",
                height: 46,
                padding: "0 16px",
                fontSize: 12,
              }}
            >
              Dán link
            </motion.button>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="button"
              onClick={handleInspect}
              disabled={inspecting || !url.trim()}
              className="continue-primary-btn"
              style={{
                height: 46,
                padding: "0 22px",
                fontSize: 13,
                opacity: inspecting || !url.trim() ? 0.6 : 1,
              }}
            >
              {inspecting ? (
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <div className="island-spinner" style={{ width: 14, height: 14 }} />
                  <span>Đang phân tích...</span>
                </div>
              ) : (
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <GlobeIcon size={16} />
                  <span>Kiểm tra link</span>
                </div>
              )}
            </motion.button>
          </div>

          {/* Quality Selector */}
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 14 }}>
            <span style={{ fontSize: 11.5, fontWeight: 700, color: "var(--text-2)" }}>Định dạng tải về:</span>
            <div style={{ display: "flex", gap: 6 }}>
              {[
                { id: "best", label: "⚡ Tốt nhất (Video+Audio)" },
                { id: "1080", label: "1080p Full HD" },
                { id: "720", label: "720p HD" },
                { id: "audio", label: "🎵 Chỉ lấy MP3" },
              ].map((q) => (
                <button
                  type="button"
                  key={q.id}
                  onClick={() => setQuality(q.id)}
                  style={{
                    fontSize: 11,
                    fontWeight: quality === q.id ? 700 : 500,
                    padding: "5px 12px",
                    borderRadius: "8px",
                    border: quality === q.id ? "1px solid var(--primary)" : "1px solid rgba(76,104,153,0.12)",
                    background: quality === q.id ? "var(--primary-soft)" : "transparent",
                    color: quality === q.id ? "var(--primary)" : "var(--text)",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  {q.label}
                </button>
              ))}
            </div>
          </div>

          {errorMsg && (
            <div
              style={{
                marginTop: 12,
                padding: "10px 14px",
                borderRadius: "8px",
                background: "rgba(255, 59, 48, 0.08)",
                border: "1px solid rgba(255, 59, 48, 0.2)",
                color: "var(--apple-red)",
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              ⚠ {errorMsg}
            </div>
          )}
        </div>

        {/* Video Preview Card (Post-Inspect) */}
        <AnimatePresence>
          {meta && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="bottom-card"
              style={{
                padding: 22,
                marginBottom: 20,
                background: "rgba(255, 255, 255, 0.92)",
                border: "1px solid rgba(39, 119, 255, 0.25)",
                boxShadow: "0 8px 24px rgba(39, 119, 255, 0.08)",
              }}
            >
              <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
                {/* Thumbnail */}
                <div
                  style={{
                    width: 140,
                    height: 95,
                    borderRadius: "10px",
                    overflow: "hidden",
                    background: "#09090C",
                    flexShrink: 0,
                    position: "relative",
                  }}
                >
                  {meta.thumbnail_url ? (
                    <img
                      src={meta.thumbnail_url}
                      alt={meta.title}
                      style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    />
                  ) : (
                    <div style={{ display: "grid", placeItems: "center", height: "100%", color: "#FFF" }}>
                      <PlayIcon size={24} />
                    </div>
                  )}
                  <span
                    style={{
                      position: "absolute",
                      bottom: 4,
                      right: 4,
                      background: "rgba(0,0,0,0.75)",
                      color: "#FFF",
                      fontSize: 10,
                      fontWeight: 700,
                      padding: "2px 5px",
                      borderRadius: "4px",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    {meta.duration_str}
                  </span>
                </div>

                {/* Metadata Details */}
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span
                      style={{
                        fontSize: 10.5,
                        fontWeight: 700,
                        padding: "2px 8px",
                        borderRadius: "999px",
                        background: "var(--primary-soft)",
                        color: "var(--primary)",
                      }}
                    >
                      {meta.platform}
                    </span>
                    <span style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 500 }}>
                      Kênh / Tác giả: <b>{meta.creator}</b>
                    </span>
                  </div>

                  <h3 style={{ fontSize: 15, fontWeight: 700, color: "var(--text)", margin: "0 0 6px 0", lineHeight: 1.35 }}>
                    {meta.title}
                  </h3>

                  {meta.description && (
                    <p style={{ fontSize: 11.5, color: "var(--text-2)", margin: "0 0 12px 0", lineHeight: 1.4 }}>
                      {meta.description.slice(0, 140)}...
                    </p>
                  )}

                  {/* Download Action */}
                  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      type="button"
                      onClick={handleDownload}
                      disabled={downloading}
                      className="continue-primary-btn"
                      style={{ height: 38, padding: "0 20px", fontSize: 12.5 }}
                    >
                      {downloading ? (
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <div className="island-spinner" style={{ width: 14, height: 14 }} />
                          <span>Đang tải xuống... ({downloadProgress}%)</span>
                        </div>
                      ) : (
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <DownloadIcon size={15} />
                          <span>Tải về máy</span>
                        </div>
                      )}
                    </motion.button>
                  </div>
                </div>
              </div>

              {/* Progress Bar while downloading */}
              {downloading && (
                <div style={{ marginTop: 14 }}>
                  <div style={{ height: 6, borderRadius: 999, background: "rgba(0,0,0,0.06)", overflow: "hidden" }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${downloadProgress}%`,
                        background: "linear-gradient(90deg, #2777FF, #34C759)",
                        transition: "width 0.3s ease",
                      }}
                    />
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-2)", marginTop: 5 }}>{downloadMsg}</div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Download Success Card */}
        <AnimatePresence>
          {downloadResult && (
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              className="bottom-card"
              style={{
                padding: 20,
                marginBottom: 20,
                background: "rgba(52, 199, 89, 0.08)",
                border: "1px solid rgba(52, 199, 89, 0.3)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 999,
                      background: "#34C759",
                      color: "#FFF",
                      display: "grid",
                      placeItems: "center",
                    }}
                  >
                    <CheckIcon size={18} />
                  </div>
                  <div>
                    <b style={{ fontSize: 14, color: "var(--text)", display: "block" }}>
                      Tải về thành công: {downloadResult.name}
                    </b>
                    <small style={{ color: "var(--text-2)", fontSize: 11 }}>
                      {downloadResult.duration_str} · {formatFileSize(downloadResult.file_size)} · SHA-256: <code>{downloadResult.sha256_hash?.slice(0, 12)}...</code>
                    </small>
                  </div>
                </div>

                <motion.button
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  type="button"
                  onClick={() => onOpenInDubStudio?.(downloadResult)}
                  className="continue-primary-btn"
                  style={{ height: 38, padding: "0 18px", fontSize: 12.5 }}
                >
                  <span>Mở ngay trong Auto Dub Studio ›</span>
                </motion.button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Download History Section */}
        <div className="bottom-card" style={{ padding: 22, background: "rgba(255,255,255,0.85)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <FolderIcon size={18} />
              <b style={{ fontSize: 14, color: "var(--text)" }}>Lịch sử tải & Kho tài nguyên ({history.length})</b>
            </div>
            <button
              type="button"
              onClick={fetchHistory}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--text-2)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 4,
                fontSize: 12,
              }}
            >
              <RefreshIcon size={13} /> Làm mới
            </button>
          </div>

          {loadingHistory ? (
            <div style={{ textAlign: "center", padding: "24px 0", color: "var(--text-2)", fontSize: 12 }}>
              Đang tải danh sách...
            </div>
          ) : history.length === 0 ? (
            <div style={{ textAlign: "center", padding: "28px 0", color: "var(--text-2)", fontSize: 12 }}>
              Chưa có video nào được tải về. Dán liên kết phía trên để bắt đầu!
            </div>
          ) : (
            <div style={{ display: "grid", gap: 8 }}>
              {history.map((item) => (
                <div
                  key={item.id}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "32px 1fr auto auto",
                    alignItems: "center",
                    gap: 12,
                    padding: "10px 14px",
                    borderRadius: "10px",
                    background: "rgba(255,255,255,0.7)",
                    border: "1px solid rgba(76,104,153,0.1)",
                    transition: "all 0.15s ease",
                  }}
                >
                  <span
                    style={{
                      width: 30,
                      height: 30,
                      borderRadius: "8px",
                      background: "var(--primary-soft)",
                      color: "var(--primary)",
                      display: "grid",
                      placeItems: "center",
                    }}
                  >
                    <FileIcon size={16} />
                  </span>

                  <div>
                    <b style={{ fontSize: 12.5, color: "var(--text)", display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {item.name}
                    </b>
                    <small style={{ color: "var(--text-2)", fontSize: 10.5 }}>
                      {item.platform} · {item.duration_str} · {formatFileSize(item.file_size)} · {item.updated_at}
                    </small>
                  </div>

                  <span
                    style={{
                      fontSize: 10,
                      fontFamily: "var(--font-mono)",
                      color: "var(--text-2)",
                      background: "rgba(0,0,0,0.04)",
                      padding: "2px 6px",
                      borderRadius: "4px",
                    }}
                    title={`SHA-256: ${item.sha256_hash}`}
                  >
                    #{item.sha256_hash?.slice(0, 8)}
                  </span>

                  <motion.button
                    whileHover={{ scale: 1.03 }}
                    whileTap={{ scale: 0.97 }}
                    type="button"
                    onClick={() => onOpenInDubStudio?.(item)}
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: "var(--primary)",
                      background: "var(--primary-soft)",
                      border: "1px solid rgba(39, 119, 255, 0.2)",
                      borderRadius: "6px",
                      padding: "5px 10px",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    <span>Lồng tiếng ›</span>
                  </motion.button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
