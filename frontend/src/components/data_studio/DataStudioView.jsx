import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FolderIcon,
  PlayIcon,
  VolumeIcon,
  SearchIcon,
  TrashIcon,
  CheckIcon,
  ChevronRightIcon,
  SparkIcon,
  FileIcon,
  MoreIcon
} from "../../icons.jsx";

function formatFileSize(bytes) {
  const b = Number(bytes);
  if (!b || isNaN(b) || b <= 0) return "--";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1)} MB`;
  return `${(b / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export default function DataStudioView({ onNavigateHome, onSendToAutoDub }) {
  const [activeTab, setActiveTab] = useState("all"); // 'all', 'video', 'audio', 'unused', 'duplicates', 'tree'
  const [search, setSearch] = useState("");
  const [overview, setOverview] = useState({
    total_assets: 0,
    total_size_mb: 0,
    formatted_duration: "00:00",
    duplicate_groups_count: 0,
  });
  const [assets, setAssets] = useState([]);
  const [duplicates, setDuplicates] = useState([]);
  const [folderTree, setFolderTree] = useState(null);
  const [loading, setLoading] = useState(true);
  const [feedback, setFeedback] = useState(null);

  // Fetch overview stats
  const loadOverview = () => {
    fetch("/api/data-studio/overview")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) setOverview(data);
      })
      .catch((err) => console.warn("Could not load overview:", err));
  };

  // Fetch assets list
  const loadAssets = () => {
    setLoading(true);
    let url = `/api/data-studio/assets?collection=${activeTab}`;
    if (search.trim()) {
      url += `&search=${encodeURIComponent(search.trim())}`;
    }
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.assets)) {
          setAssets(data.assets);
        }
      })
      .catch((err) => console.error("Error loading assets:", err))
      .finally(() => setLoading(false));
  };

  // Fetch duplicates
  const loadDuplicates = () => {
    setLoading(true);
    fetch("/api/data-studio/duplicates")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.duplicates)) {
          setDuplicates(data.duplicates);
        }
      })
      .catch((err) => console.error("Error loading duplicates:", err))
      .finally(() => setLoading(false));
  };

  // Fetch folder tree
  const loadFolderTree = () => {
    setLoading(true);
    fetch("/api/data-studio/folder-tree")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) setFolderTree(data);
      })
      .catch((err) => console.error("Error loading folder tree:", err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadOverview();
  }, []);

  useEffect(() => {
    if (activeTab === "duplicates") {
      loadDuplicates();
    } else if (activeTab === "tree") {
      loadFolderTree();
    } else {
      loadAssets();
    }
  }, [activeTab, search]);

  const handleDeleteAsset = (assetId, deleteFile = false) => {
    if (!window.confirm("Bạn có chắc chắn muốn xóa tài nguyên này khỏi kho dữ liệu?")) return;
    fetch("/api/data-studio/assets/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ asset_id: assetId, delete_file: deleteFile }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r)))
      .then(() => {
        setFeedback({ type: "success", text: "Đã xóa tài nguyên thành công." });
        loadOverview();
        if (activeTab === "duplicates") loadDuplicates();
        else loadAssets();
        setTimeout(() => setFeedback(null), 3000);
      })
      .catch((err) => {
        setFeedback({ type: "error", text: "Không thể xóa tài nguyên." });
        setTimeout(() => setFeedback(null), 4000);
      });
  };

  const handleCleanDuplicateCopies = (dupGroup) => {
    if (!dupGroup.items || dupGroup.items.length <= 1) return;
    if (!window.confirm(`Dọn dẹp ${dupGroup.items.length - 1} bản ghi trùng lặp và giải phóng ${dupGroup.wasted_mb} MB?`)) return;

    // Keep the first item, delete the rest
    const copiesToDelete = dupGroup.items.slice(1);
    Promise.all(
      copiesToDelete.map((it) =>
        fetch("/api/data-studio/assets/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ asset_id: it.id, delete_file: false }),
        })
      )
    )
      .then(() => {
        setFeedback({ type: "success", text: `Đã dọn dẹp các bản sao trùng lặp hash #${dupGroup.sha_short}!` });
        loadOverview();
        loadDuplicates();
        setTimeout(() => setFeedback(null), 3000);
      })
      .catch(() => {
        setFeedback({ type: "error", text: "Lỗi trong quá trình dọn dẹp bản sao trùng lặp." });
        setTimeout(() => setFeedback(null), 4000);
      });
  };

  return (
    <div className="kappak-scroll-area">
      <div className="kappak-home-container" style={{ maxWidth: 1380 }}>
        {/* Breadcrumb Header */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--text-3)", marginBottom: 16 }}>
          <button
            onClick={onNavigateHome}
            style={{
              background: "none",
              border: "none",
              color: "var(--text-2)",
              cursor: "pointer",
              padding: 0,
              fontSize: 13,
            }}
          >
            Trang chủ
          </button>
          <span>/</span>
          <span style={{ color: "var(--accent-mint)", fontWeight: 600 }}>Data Studio</span>
        </div>

        {/* Title Bar */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 }}>
          <div>
            <h1 style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.02em", color: "var(--text-1)", margin: "0 0 6px 0" }}>
              Data Studio — Quản lý Kho Tài Nguyên & Bộ Sưu Tập
            </h1>
            <p style={{ margin: 0, fontSize: 14, color: "var(--text-2)" }}>
              Theo dõi dung lượng, phát hiện trùng lặp SHA-256 và duyệt cấu trúc 8 tầng chuẩn của dự án.
            </p>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                padding: "6px 14px",
                borderRadius: 20,
                background: "rgba(52, 199, 89, 0.12)",
                color: "var(--accent-mint)",
                border: "1px solid rgba(52, 199, 89, 0.25)",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent-mint)" }}></span>
              SQLite WAL Active
            </span>
          </div>
        </div>

        {/* Feedback Alert */}
        <AnimatePresence>
          {feedback && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              style={{
                padding: "12px 18px",
                borderRadius: "var(--radius-md)",
                marginBottom: 20,
                fontSize: 13,
                fontWeight: 500,
                background: feedback.type === "success" ? "rgba(52, 199, 89, 0.12)" : "rgba(255, 69, 58, 0.12)",
                color: feedback.type === "success" ? "var(--accent-mint)" : "var(--danger)",
                border: `1px solid ${feedback.type === "success" ? "rgba(52, 199, 89, 0.3)" : "rgba(255, 69, 58, 0.3)"}`,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              {feedback.text}
            </motion.div>
          )}
        </AnimatePresence>

        {/* 4 Storage Stats Cards */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 16,
            marginBottom: 28,
          }}
        >
          {/* Card 1: Storage Size */}
          <div className="bottom-card" style={{ padding: "20px 22px" }}>
            <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 8, fontWeight: 500 }}>
              Dung lượng đã dùng
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, color: "var(--text-1)", letterSpacing: "-0.02em" }}>
              {overview?.total_size_formatted || (
                (overview?.total_size_mb ?? 0) > 1024
                  ? `${((overview?.total_size_mb ?? 0) / 1024).toFixed(2)} GB`
                  : (overview?.total_size_mb ?? 0) > 0
                  ? `${overview?.total_size_mb} MB`
                  : (overview?.total_bytes ?? 0) > 0
                  ? `${((overview?.total_bytes ?? 0) / 1024).toFixed(1)} KB`
                  : "0 MB"
              )}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 6 }}>
              {(overview?.total_bytes ?? 0).toLocaleString()} bytes
            </div>
          </div>

          {/* Card 2: Assets Count */}
          <div className="bottom-card" style={{ padding: "20px 22px" }}>
            <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 8, fontWeight: 500 }}>
              Tổng số tài nguyên
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, color: "var(--accent-blue)", letterSpacing: "-0.02em" }}>
              {overview?.total_assets ?? 0}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 6 }}>
              Video, Audio & Subtitles
            </div>
          </div>

          {/* Card 3: Video Duration */}
          <div className="bottom-card" style={{ padding: "20px 22px" }}>
            <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 8, fontWeight: 500 }}>
              Thời lượng đa phương tiện
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, color: "var(--accent-mint)", letterSpacing: "-0.02em" }}>
              {overview?.formatted_duration ?? "00:00"}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 6 }}>
              {Math.round(overview?.total_duration_sec ?? 0)} giây nội dung
            </div>
          </div>

          {/* Card 4: Duplicate Groups */}
          <div className="bottom-card" style={{ padding: "20px 22px" }}>
            <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 8, fontWeight: 500 }}>
              Nhóm trùng lặp SHA-256
            </div>
            <div
              style={{
                fontSize: 24,
                fontWeight: 700,
                color: (overview?.duplicate_groups_count ?? 0) > 0 ? "var(--warning)" : "var(--accent-mint)",
                letterSpacing: "-0.02em",
              }}
            >
              {overview?.duplicate_groups_count ?? 0}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 6 }}>
              {(overview?.duplicate_groups_count ?? 0) > 0 ? "Cần dọn dẹp để tiết kiệm dung lượng" : "Không có trùng lặp"}
            </div>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="bottom-card" style={{ padding: 24 }}>
          {/* Controls Header: Tabs + Search */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 16,
              marginBottom: 20,
              borderBottom: "1px solid var(--border-soft)",
              paddingBottom: 16,
            }}
          >
            {/* Smart Collection Tabs */}
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {[
                { id: "all", label: "Tất cả" },
                { id: "video", label: "Video" },
                { id: "audio", label: "Âm thanh" },
                { id: "unused", label: "Chưa dùng" },
                { id: "duplicates", label: `Trùng SHA-256 (${overview.duplicate_groups_count})` },
                { id: "tree", label: "Cây thư mục 8 tầng" },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    padding: "7px 16px",
                    borderRadius: 20,
                    fontSize: 13,
                    fontWeight: activeTab === tab.id ? 600 : 500,
                    cursor: "pointer",
                    border: activeTab === tab.id ? "1px solid #10B981" : "1px solid var(--border-soft)",
                    background: activeTab === tab.id ? "#10B981" : "var(--surface)",
                    color: activeTab === tab.id ? "#FFFFFF" : "var(--text-1)",
                    boxShadow: activeTab === tab.id ? "0 2px 8px rgba(16, 185, 129, 0.25)" : "none",
                    transition: "all 0.15s ease",
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Search Input (When in regular list tabs) */}
            {activeTab !== "tree" && activeTab !== "duplicates" && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  background: "var(--surface)",
                  borderRadius: "var(--radius-sm)",
                  padding: "0 12px",
                  border: "1px solid var(--border-soft)",
                  width: 260,
                }}
              >
                <SearchIcon size={14} style={{ color: "var(--text-3)", marginRight: 8 }} />
                <input
                  type="text"
                  placeholder="Tìm theo tên, creator, tag..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  style={{
                    border: "none",
                    background: "transparent",
                    color: "var(--text-1)",
                    fontSize: 13,
                    padding: "8px 0",
                    outline: "none",
                    width: "100%",
                  }}
                />
              </div>
            )}
          </div>

          {/* Tab 1-4: Regular Assets List */}
          {activeTab !== "duplicates" && activeTab !== "tree" && (
            <div>
              {loading ? (
                <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-3)", fontSize: 14 }}>
                  Đang tải danh sách tài nguyên...
                </div>
              ) : assets.length === 0 ? (
                <div style={{ textAlign: "center", padding: "48px 0", color: "var(--text-3)" }}>
                  <FolderIcon size={36} style={{ opacity: 0.3, marginBottom: 12 }} />
                  <div style={{ fontSize: 15, fontWeight: 500, color: "var(--text-2)", marginBottom: 4 }}>
                    Chưa có tài nguyên nào trong bộ sưu tập này
                  </div>
                  <div style={{ fontSize: 13 }}>Tải video qua Universal Downloader hoặc import tệp vào dự án.</div>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {assets.map((asset) => (
                    <div
                      key={asset.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "12px 16px",
                        background: "var(--surface)",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-soft)",
                      }}
                    >
                      {/* Left: Icon & Info */}
                      <div style={{ display: "flex", alignItems: "center", gap: 14, minWidth: 0, flex: 1 }}>
                        <div
                          style={{
                            width: 38,
                            height: 38,
                            borderRadius: 8,
                            background: "rgba(52, 199, 89, 0.12)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: "var(--accent-mint)",
                            flexShrink: 0,
                          }}
                        >
                          {asset.local_path?.endsWith(".mp3") || asset.local_path?.endsWith(".wav") ? (
                            <VolumeIcon size={18} />
                          ) : (
                            <PlayIcon size={18} />
                          )}
                        </div>

                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div
                            style={{
                              fontSize: 14,
                              fontWeight: 600,
                              color: "var(--text-1)",
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              marginBottom: 4,
                            }}
                            title={asset.name}
                          >
                            {asset.name}
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12, color: "var(--text-3)" }}>
                            <span style={{ fontWeight: 500, color: "var(--text-2)" }}>{asset.platform || "Local"}</span>
                            <span>•</span>
                            <span>{asset.duration_formatted}</span>
                            <span>•</span>
                            <span>{formatFileSize(asset.file_size)}</span>
                            <span>•</span>
                            <span
                              style={{
                                fontFamily: "JetBrains Mono, monospace",
                                background: "rgba(255, 255, 255, 0.05)",
                                padding: "1px 5px",
                                borderRadius: 4,
                                fontSize: 11,
                              }}
                            >
                              #{asset.sha_short || "nohash"}
                            </span>
                            <span>•</span>
                            <span style={{ color: "var(--accent-mint)", fontWeight: 500 }}>{asset.category}</span>
                          </div>
                        </div>
                      </div>

                      {/* Right: Actions */}
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0, marginLeft: 16 }}>
                        <button
                          onClick={() => onSendToAutoDub && onSendToAutoDub(asset)}
                          style={{
                            padding: "6px 14px",
                            borderRadius: 16,
                            background: "var(--accent-mint)",
                            color: "#ffffff",
                            border: "none",
                            fontSize: 12,
                            fontWeight: 600,
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: 4,
                          }}
                        >
                          <span>Lồng tiếng</span>
                          <ChevronRightIcon size={13} />
                        </button>
                        <button
                          onClick={() => handleDeleteAsset(asset.id, false)}
                          title="Xóa tài nguyên"
                          style={{
                            padding: "7px 10px",
                            borderRadius: 16,
                            background: "transparent",
                            color: "var(--text-3)",
                            border: "1px solid var(--border-soft)",
                            cursor: "pointer",
                          }}
                        >
                          <TrashIcon size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Tab 5: Duplicates View */}
          {activeTab === "duplicates" && (
            <div>
              {loading ? (
                <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-3)", fontSize: 14 }}>
                  Đang quét và phân tích các nhóm trùng lặp...
                </div>
              ) : duplicates.length === 0 ? (
                <div style={{ textAlign: "center", padding: "48px 0", color: "var(--accent-mint)" }}>
                  <CheckIcon size={36} style={{ marginBottom: 12 }} />
                  <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
                    Kho dữ liệu sạch sẽ, không có tệp trùng lặp!
                  </div>
                  <div style={{ fontSize: 13, color: "var(--text-2)" }}>
                    Universal Downloader đã tự động chặn trùng lặp qua kiểm tra SHA-256.
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  {duplicates.map((dup) => (
                    <div
                      key={dup.sha256_hash}
                      style={{
                        padding: 16,
                        borderRadius: "var(--radius-md)",
                        background: "var(--surface)",
                        border: "1px solid rgba(255, 149, 0, 0.3)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                        <div>
                          <span
                            style={{
                              fontFamily: "JetBrains Mono, monospace",
                              fontSize: 12,
                              fontWeight: 600,
                              background: "rgba(255, 149, 0, 0.15)",
                              color: "var(--warning)",
                              padding: "3px 8px",
                              borderRadius: 4,
                            }}
                          >
                            SHA-256: #{dup.sha_short}
                          </span>
                          <span style={{ fontSize: 13, color: "var(--text-2)", marginLeft: 10 }}>
                            {dup.count} bản sao • Lãng phí: {formatFileSize(dup.wasted_bytes || (dup.wasted_mb * 1024 * 1024))}
                          </span>
                        </div>
                        <button
                          onClick={() => handleCleanDuplicateCopies(dup)}
                          style={{
                            padding: "6px 14px",
                            borderRadius: 16,
                            background: "var(--warning)",
                            color: "#000000",
                            border: "none",
                            fontSize: 12,
                            fontWeight: 600,
                            cursor: "pointer",
                          }}
                        >
                          Dọn dẹp bản sao thừa ({dup.count - 1})
                        </button>
                      </div>

                      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        {dup.items.map((it, idx) => (
                          <div
                            key={it.id}
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              fontSize: 12,
                              color: "var(--text-2)",
                              background: "rgba(0,0,0,0.15)",
                              padding: "6px 12px",
                              borderRadius: 6,
                            }}
                          >
                            <span>
                              {idx === 0 ? "★ [Bản gốc] " : "• [Bản sao] "}
                              {it.name} ({it.platform})
                            </span>
                            <span>{it.created_at?.slice(0, 19)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Tab 6: 8-Tier Folder Tree View */}
          {activeTab === "tree" && (
            <div>
              {loading ? (
                <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-3)", fontSize: 14 }}>
                  Đang đọc cấu trúc cây thư mục 8 tầng...
                </div>
              ) : !folderTree || !folderTree.tiers ? (
                <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-3)" }}>
                  Không tìm thấy cấu trúc dự án.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div style={{ fontSize: 13, color: "var(--text-2)", marginBottom: 8 }}>
                    Cấu trúc 8 tầng chuẩn của KAPPAK tại:{" "}
                    <code style={{ fontFamily: "JetBrains Mono, monospace", color: "var(--accent-mint)" }}>
                      {folderTree.path}
                    </code>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
                    {folderTree.tiers.map((tier) => (
                      <div
                        key={tier.tier}
                        style={{
                          padding: 14,
                          background: "var(--surface)",
                          borderRadius: "var(--radius-sm)",
                          border: `1px solid ${tier.exists ? "var(--border-soft)" : "rgba(255,255,255,0.05)"}`,
                          opacity: tier.exists ? 1 : 0.6,
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                          <div style={{ fontWeight: 600, fontSize: 14, color: "var(--text-1)", display: "flex", alignItems: "center", gap: 8 }}>
                            <FolderIcon size={16} style={{ color: tier.exists ? "var(--accent-mint)" : "var(--text-3)" }} />
                            <span>{tier.tier}</span>
                          </div>
                          <span
                            style={{
                              fontSize: 11,
                              padding: "2px 8px",
                              borderRadius: 10,
                              background: tier.file_count > 0 ? "rgba(52, 199, 89, 0.15)" : "rgba(255,255,255,0.05)",
                              color: tier.file_count > 0 ? "var(--accent-mint)" : "var(--text-3)",
                              fontWeight: 600,
                            }}
                          >
                            {tier.file_count} tệp
                          </span>
                        </div>

                        {tier.files && tier.files.length > 0 ? (
                          <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8 }}>
                            {tier.files.slice(0, 5).map((f) => (
                              <div
                                key={f.name}
                                style={{
                                  fontSize: 12,
                                  color: "var(--text-3)",
                                  display: "flex",
                                  justifyContent: "space-between",
                                  padding: "2px 0",
                                }}
                              >
                                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 220 }}>
                                  {f.name}
                                </span>
                                <span>{f.size_mb} MB</span>
                              </div>
                            ))}
                            {tier.files.length > 5 && (
                              <div style={{ fontSize: 11, color: "var(--text-3)", fontStyle: "italic", marginTop: 2 }}>
                                + {tier.files.length - 5} tệp khác...
                              </div>
                            )}
                          </div>
                        ) : (
                          <div style={{ fontSize: 12, color: "var(--text-3)", fontStyle: "italic", marginTop: 6 }}>
                            Thư mục trống
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
