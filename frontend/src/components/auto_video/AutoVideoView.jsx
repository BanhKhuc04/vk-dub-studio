import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ScissorsIcon,
  SparkIcon,
  PlayIcon,
  CheckIcon,
  RefreshIcon,
  CloseIcon,
  ChevronRightIcon,
  FolderIcon,
  DownloadIcon,
  VolumeIcon,
  FileIcon,
} from "../../icons.jsx";

const SAMPLE_SCRIPTS = [
  {
    title: "3 Mẹo Sáng Tạo Nội Dung Viral",
    text: `Bạn muốn video triệu view? Đừng bỏ qua 3 mẹo sau.
Mẹo thứ nhất: Luôn giữ 3 giây đầu tiên thật bất ngờ để kéo chân người xem.
Mẹo thứ hai: Dùng âm thanh nền bắt tai và tạo nhịp điệu nhanh.
Mẹo thứ ba: Đặt câu hỏi kích thích bình luận ở phần kết.
Thử ngay hôm nay và xem kết quả bất ngờ nhé!`,
  },
  {
    title: "Sự Thật Thú Vị Về Trí Tuệ Nhân Tạo",
    text: `Trí tuệ nhân tạo đang thay đổi thế giới như thế nào?
Hàng triệu video ngắn hiện nay được sản xuất hoàn toàn tự động chỉ trong vài phút.
Công nghệ AI giúp cắt ghép cảnh, dịch thuật đa ngôn ngữ và tạo giọng nói như người thật.
Bạn đã sẵn sàng bước vào kỷ nguyên sáng tạo số chưa?`,
  },
];

export default function AutoVideoView({ onOpenInDubStudio, onBackHome }) {
  // State
  const [activeStep, setActiveStep] = useState(1); // 1: Script & Template, 2: Scenes & Assets, 3: Render
  const [projectName, setProjectName] = useState("Video Ngắn Viral 01");
  const [scriptText, setScriptText] = useState(SAMPLE_SCRIPTS[0].text);
  const [selectedTemplate, setSelectedTemplate] = useState("blur_bg");
  const [selectedVoice, setSelectedVoice] = useState("vi-VN-HoaiMyNeural");
  const [voiceSpeed, setVoiceSpeed] = useState(1.0);

  const [templates, setTemplates] = useState([]);
  const [availableAssets, setAvailableAssets] = useState([]);
  const [scenes, setScenes] = useState([]);
  const [selectedSceneIndex, setSelectedSceneIndex] = useState(0);

  const [currentProject, setCurrentProject] = useState(null);
  const [rendering, setRendering] = useState(false);
  const [renderProgress, setRenderProgress] = useState(0);
  const [renderMessage, setRenderMessage] = useState("");
  const [outputVideoUrl, setOutputVideoUrl] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");

  const wsRef = useRef(null);

  // Fetch templates and assets on mount
  useEffect(() => {
    fetch("/api/auto-video/templates")
      .then((res) => (res.ok ? res.json() : Promise.reject(res)))
      .then((data) => {
        if (data && Array.isArray(data.templates)) {
          setTemplates(data.templates);
        }
      })
      .catch((err) => console.warn("Lỗi tải templates:", err));

    fetch("/api/auto-video/assets")
      .then((res) => (res.ok ? res.json() : Promise.reject(res)))
      .then((data) => {
        if (data && Array.isArray(data.assets)) {
          setAvailableAssets(data.assets);
        }
      })
      .catch((err) => console.warn("Lỗi tải assets:", err));

    // Connect WebSocket for real-time progress
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/pipeline`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "auto_video_progress") {
          setRenderProgress(msg.progress_pct || 0);
          setRenderMessage(msg.message || "Đang xử lý...");
          if (msg.progress_pct >= 100) {
            setRendering(false);
          }
        } else if (msg.type === "auto_video_failed") {
          setRendering(false);
          setErrorMsg(msg.error || "Quá trình dựng video gặp lỗi.");
        }
      } catch (e) {
        // ignore parse errors
      }
    };

    wsRef.current = ws;
    return () => {
      ws.close();
    };
  }, []);

  // Parse script whenever user proceeds to Step 2
  const handleParseScript = async () => {
    if (!scriptText.trim()) {
      setErrorMsg("Vui lòng nhập kịch bản văn bản trước.");
      return;
    }
    setErrorMsg("");

    try {
      const res = await fetch("/api/auto-video/script/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ script_text: scriptText }),
      });
      const data = await res.json();
      if (data && Array.isArray(data.scenes)) {
        // Auto assign available assets to scenes in round-robin fashion
        const mappedScenes = data.scenes.map((s, idx) => {
          const matchedAsset = availableAssets[idx % availableAssets.length];
          return {
            ...s,
            asset_id: matchedAsset ? matchedAsset.id : null,
            asset_path: matchedAsset ? matchedAsset.path : null,
          };
        });
        setScenes(mappedScenes);
        setActiveStep(2);
      }
    } catch (err) {
      setErrorMsg("Không thể phân tích kịch bản: " + err.message);
    }
  };

  // Trigger render
  const handleStartRender = async () => {
    setErrorMsg("");
    setRendering(true);
    setRenderProgress(5);
    setRenderMessage("Khởi tạo dự án dựng video...");
    setActiveStep(3);

    try {
      // 1. Create project
      const createRes = await fetch("/api/auto-video/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: projectName,
          template_id: selectedTemplate,
          voice_id: selectedVoice,
          voice_speed: voiceSpeed,
          script_text: scriptText,
          scenes: scenes,
        }),
      });

      const createData = await createRes.json();
      if (!createRes.ok || !createData.project) {
        throw new Error(createData.detail || "Tạo dự án thất bại.");
      }

      const proj = createData.project;
      setCurrentProject(proj);

      // 2. Trigger render
      const renderRes = await fetch(`/api/auto-video/projects/${proj.id}/render`, {
        method: "POST",
      });
      const renderData = await renderRes.json();
      if (!renderRes.ok) {
        throw new Error(renderData.detail || "Khởi động render thất bại.");
      }

      // Poll status as watchdog
      const pollInterval = setInterval(async () => {
        try {
          const stRes = await fetch(`/api/auto-video/projects/${proj.id}`);
          if (stRes.ok) {
            const stData = await stRes.json();
            const p = stData.project;
            if (p) {
              setRenderProgress(p.progress_pct);
              if (p.status === "COMPLETED") {
                clearInterval(pollInterval);
                setRendering(false);
                setOutputVideoUrl(`/api/auto-video/download/${p.id}`);
              } else if (p.status === "FAILED") {
                clearInterval(pollInterval);
                setRendering(false);
                setErrorMsg(p.error_message || "Dựng video thất bại.");
              }
            }
          }
        } catch (e) {
          // ignore
        }
      }, 2000);
    } catch (err) {
      setRendering(false);
      setErrorMsg(err.message);
    }
  };

  // Stats calculation
  const totalWords = scriptText.trim() ? scriptText.trim().split(/\s+/).length : 0;
  const estimatedSeconds = Math.max(3, Math.round(totalWords / 2.8 / voiceSpeed));

  return (
    <div className="kappak-scroll-area">
      <div className="kappak-home-container" style={{ maxWidth: 1180, margin: "0 auto", padding: "28px 24px 60px 24px" }}>
        
        {/* Top Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div
              style={{
                width: 46,
                height: 46,
                borderRadius: 14,
                background: "linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#FFFFFF",
                boxShadow: "0 8px 18px rgba(139, 92, 246, 0.28)",
              }}
            >
              <ScissorsIcon size={24} />
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0, color: "var(--text)" }}>
                  Auto Video Generator
                </h1>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    padding: "3px 8px",
                    borderRadius: 20,
                    background: "rgba(139, 92, 246, 0.12)",
                    color: "#8B5CF6",
                    border: "1px solid rgba(139, 92, 246, 0.25)",
                  }}
                >
                  9:16 Shorts / Reels / TikTok
                </span>
              </div>
              <p style={{ fontSize: 13, color: "var(--text-2)", margin: "4px 0 0 0" }}>
                Tự động hóa kịch bản, cắt ghép khung hình dọc, lồng tiếng AI & phụ đề động
              </p>
            </div>
          </div>

          <div style={{ display: "flex", gap: 10 }}>
            {onBackHome && (
              <button
                className="continue-primary-btn"
                style={{ background: "#FFFFFF", color: "var(--text)", border: "1px solid rgba(76,104,153,0.18)" }}
                onClick={onBackHome}
              >
                ← Về Trang chủ
              </button>
            )}
          </div>
        </div>

        {/* Step Stepper Header */}
        <div
          style={{
            display: "flex",
            gap: 12,
            background: "rgba(255, 255, 255, 0.65)",
            backdropFilter: "blur(20px)",
            padding: "8px 12px",
            borderRadius: 16,
            border: "1px solid rgba(76, 104, 153, 0.14)",
            marginBottom: 24,
          }}
        >
          {[
            { step: 1, title: "1. Kịch bản & Bố cục 9:16" },
            { step: 2, title: "2. Ghép cảnh & Tư liệu" },
            { step: 3, title: "3. Dựng & Xuất Video" },
          ].map((s) => (
            <button
              key={s.step}
              onClick={() => !rendering && setActiveStep(s.step)}
              style={{
                flex: 1,
                padding: "8px 16px",
                borderRadius: 10,
                border: "none",
                background: activeStep === s.step ? "linear-gradient(135deg, #8B5CF6, #6D28D9)" : "transparent",
                color: activeStep === s.step ? "#FFFFFF" : "var(--text-2)",
                fontWeight: activeStep === s.step ? 700 : 500,
                fontSize: 13,
                cursor: rendering ? "not-allowed" : "pointer",
                transition: "all 0.2s ease",
              }}
            >
              {s.title}
            </button>
          ))}
        </div>

        {/* Error banner */}
        {errorMsg && (
          <div
            style={{
              padding: "12px 16px",
              borderRadius: 12,
              background: "#FEE2E2",
              border: "1px solid #FCA5A5",
              color: "#B91C1C",
              fontSize: 13,
              marginBottom: 20,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span>⚠️ {errorMsg}</span>
            <button
              onClick={() => setErrorMsg("")}
              style={{ background: "none", border: "none", cursor: "pointer", color: "#B91C1C" }}
            >
              <CloseIcon size={16} />
            </button>
          </div>
        )}

        {/* STEP 1: Script & Template Settings */}
        {activeStep === 1 && (
          <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 24 }}>
            {/* Left: Script Editor */}
            <div
              className="bottom-card"
              style={{ padding: 24, borderRadius: 20, background: "rgba(255, 255, 255, 0.75)" }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <label style={{ fontSize: 14, fontWeight: 700, color: "var(--text)" }}>Tên Dự Án</label>
              </div>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="Nhập tên video ngắn..."
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: 10,
                  border: "1px solid rgba(76, 104, 153, 0.2)",
                  fontSize: 14,
                  marginBottom: 18,
                  outline: "none",
                }}
              />

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <label style={{ fontSize: 14, fontWeight: 700, color: "var(--text)" }}>Kịch Bản Thoại</label>
                <div style={{ display: "flex", gap: 6 }}>
                  {SAMPLE_SCRIPTS.map((s, idx) => (
                    <button
                      key={idx}
                      onClick={() => setScriptText(s.text)}
                      style={{
                        padding: "3px 8px",
                        fontSize: 11,
                        borderRadius: 6,
                        border: "1px solid rgba(139, 92, 246, 0.25)",
                        background: "rgba(139, 92, 246, 0.08)",
                        color: "#8B5CF6",
                        cursor: "pointer",
                      }}
                    >
                      Mẫu {idx + 1}
                    </button>
                  ))}
                </div>
              </div>

              <textarea
                value={scriptText}
                onChange={(e) => setScriptText(e.target.value)}
                rows={8}
                placeholder="Nhập nội dung kịch bản tại đây. Mỗi câu/đoạn sẽ tự động chia thành 1 cảnh video..."
                style={{
                  width: "100%",
                  padding: "12px 14px",
                  borderRadius: 12,
                  border: "1px solid rgba(76, 104, 153, 0.2)",
                  fontSize: 13,
                  lineHeight: 1.6,
                  resize: "vertical",
                  outline: "none",
                  fontFamily: "inherit",
                }}
              />

              {/* Stats pill */}
              <div
                style={{
                  display: "flex",
                  gap: 16,
                  padding: "10px 14px",
                  borderRadius: 10,
                  background: "rgba(240, 243, 248, 0.7)",
                  marginTop: 12,
                  fontSize: 12,
                  color: "var(--text-2)",
                }}
              >
                <span>📝 Số từ: <strong>{totalWords}</strong></span>
                <span>⏱️ Thời lượng ước tính: <strong>~{estimatedSeconds}s</strong></span>
                <span>🎯 Tỷ lệ: <strong>9:16 Dọc</strong></span>
              </div>

              <div style={{ marginTop: 24, display: "flex", justifyContent: "flex-end" }}>
                <button
                  className="continue-primary-btn"
                  onClick={handleParseScript}
                  style={{
                    background: "linear-gradient(135deg, #8B5CF6, #6D28D9)",
                    boxShadow: "0 4px 12px rgba(139, 92, 246, 0.3)",
                  }}
                >
                  Phân tích kịch bản & Tiếp tục ›
                </button>
              </div>
            </div>

            {/* Right: Template & Voice Options */}
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              {/* Template selection */}
              <div className="bottom-card" style={{ padding: 20, borderRadius: 20 }}>
                <h3 style={{ fontSize: 14, fontWeight: 700, margin: "0 0 12px 0" }}>Bố Cục Video 9:16</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {[
                    {
                      id: "blur_bg",
                      name: "Cinematic Nền Mờ",
                      desc: "Khung giữa sắc nét, nền làm mờ tự nhiên",
                      badge: "Khuyên dùng",
                    },
                    {
                      id: "split_screen",
                      name: "Màn Hình Kép (Split)",
                      desc: "Tư liệu nửa trên, hiệu ứng nửa dưới",
                      badge: "Viral Trend",
                    },
                    {
                      id: "caption_header",
                      name: "Hook & Headline",
                      desc: "Tiêu đề lớn ở đỉnh, phụ đề nổi bật đáy",
                      badge: "Retention Cao",
                    },
                  ].map((t) => (
                    <div
                      key={t.id}
                      onClick={() => setSelectedTemplate(t.id)}
                      style={{
                        padding: "12px 14px",
                        borderRadius: 12,
                        border: selectedTemplate === t.id ? "2px solid #8B5CF6" : "1px solid rgba(76, 104, 153, 0.16)",
                        background: selectedTemplate === t.id ? "rgba(139, 92, 246, 0.06)" : "#FFFFFF",
                        cursor: "pointer",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text)" }}>{t.name}</div>
                        <div style={{ fontSize: 11, color: "var(--text-2)", marginTop: 2 }}>{t.desc}</div>
                      </div>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          padding: "2px 6px",
                          borderRadius: 6,
                          background: selectedTemplate === t.id ? "#8B5CF6" : "rgba(76,104,153,0.1)",
                          color: selectedTemplate === t.id ? "#FFFFFF" : "var(--text-2)",
                        }}
                      >
                        {t.badge}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Voice selection */}
              <div className="bottom-card" style={{ padding: 20, borderRadius: 20 }}>
                <h3 style={{ fontSize: 14, fontWeight: 700, margin: "0 0 12px 0" }}>Giọng Đọc AI (Edge TTS)</h3>
                <div style={{ display: "flex", gap: 10, marginBottom: 14 }}>
                  {[
                    { id: "vi-VN-HoaiMyNeural", label: "Hoài My (Nữ AI)" },
                    { id: "vi-VN-NamMinhNeural", label: "Nam Minh (Nam AI)" },
                  ].map((v) => (
                    <button
                      key={v.id}
                      onClick={() => setSelectedVoice(v.id)}
                      style={{
                        flex: 1,
                        padding: "8px 10px",
                        borderRadius: 8,
                        border: selectedVoice === v.id ? "2px solid #8B5CF6" : "1px solid rgba(76,104,153,0.18)",
                        background: selectedVoice === v.id ? "rgba(139, 92, 246, 0.08)" : "#FFFFFF",
                        color: selectedVoice === v.id ? "#8B5CF6" : "var(--text)",
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      {v.label}
                    </button>
                  ))}
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 6 }}>
                  <span style={{ color: "var(--text-2)" }}>Tốc độ đọc:</span>
                  <span style={{ fontWeight: 700 }}>{voiceSpeed}x</span>
                </div>
                <input
                  type="range"
                  min="0.8"
                  max="1.4"
                  step="0.05"
                  value={voiceSpeed}
                  onChange={(e) => setVoiceSpeed(parseFloat(e.target.value))}
                  style={{ width: "100%", accentColor: "#8B5CF6" }}
                />
              </div>
            </div>
          </div>
        )}

        {/* STEP 2: Scenes & Asset Matching Timeline */}
        {activeStep === 2 && (
          <div style={{ display: "grid", gridTemplateColumns: "1.3fr 0.9fr", gap: 24 }}>
            {/* Left: Scenes List */}
            <div className="bottom-card" style={{ padding: 22, borderRadius: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <div>
                  <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>Dòng Thời Gian Phân Cảnh ({scenes.length} cảnh)</h3>
                  <p style={{ fontSize: 12, color: "var(--text-2)", margin: "2px 0 0 0" }}>
                    Kiểm tra và gán tư liệu video từ Data Studio cho từng đoạn kịch bản
                  </p>
                </div>
                <button
                  onClick={() => setActiveStep(1)}
                  style={{ padding: "4px 10px", fontSize: 11, borderRadius: 6, border: "1px solid rgba(76,104,153,0.2)", background: "#FFF", cursor: "pointer" }}
                >
                  ← Sửa kịch bản
                </button>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 12, maxHeight: 440, overflowY: "auto", paddingRight: 6 }}>
                {scenes.map((scene, idx) => (
                  <div
                    key={scene.id || idx}
                    onClick={() => setSelectedSceneIndex(idx)}
                    style={{
                      padding: 14,
                      borderRadius: 12,
                      border: selectedSceneIndex === idx ? "2px solid #8B5CF6" : "1px solid rgba(76, 104, 153, 0.16)",
                      background: selectedSceneIndex === idx ? "rgba(139, 92, 246, 0.04)" : "#FFFFFF",
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: "#8B5CF6" }}>Cảnh #{idx + 1}</span>
                      <span style={{ fontSize: 11, padding: "2px 6px", borderRadius: 4, background: "rgba(0,0,0,0.05)", color: "var(--text-2)" }}>
                        ~{scene.duration_sec}s
                      </span>
                    </div>

                    <p style={{ fontSize: 13, margin: "0 0 10px 0", lineHeight: 1.5, color: "var(--text)" }}>
                      "{scene.text}"
                    </p>

                    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                      <span style={{ color: "var(--text-2)" }}>Tư liệu:</span>
                      <select
                        value={scene.asset_id || ""}
                        onChange={(e) => {
                          const val = e.target.value;
                          const found = availableAssets.find((a) => a.id === val);
                          const updated = [...scenes];
                          updated[idx] = {
                            ...updated[idx],
                            asset_id: val || null,
                            asset_path: found ? found.path : null,
                          };
                          setScenes(updated);
                        }}
                        style={{
                          flex: 1,
                          padding: "4px 8px",
                          borderRadius: 6,
                          border: "1px solid rgba(76, 104, 153, 0.2)",
                          fontSize: 12,
                          outline: "none",
                        }}
                      >
                        <option value="">(Nền thẩm mỹ tự động)</option>
                        {availableAssets.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.name} ({a.resolution || "Video"})
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                ))}
              </div>

              <div style={{ marginTop: 20, display: "flex", justifyContent: "flex-end", gap: 10 }}>
                <button
                  className="continue-primary-btn"
                  onClick={handleStartRender}
                  style={{
                    background: "linear-gradient(135deg, #8B5CF6, #6D28D9)",
                    boxShadow: "0 4px 14px rgba(139, 92, 246, 0.35)",
                  }}
                >
                  🚀 Bắt đầu Tạo Video 9:16 ›
                </button>
              </div>
            </div>

            {/* Right: Phone Frame Preview 9:16 */}
            <div
              className="bottom-card"
              style={{
                padding: 20,
                borderRadius: 20,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12, color: "var(--text)" }}>
                Xem Trước Khung Hình 9:16 (Cảnh #{selectedSceneIndex + 1})
              </div>

              {/* iPhone style mockup frame */}
              <div
                style={{
                  width: 220,
                  height: 390,
                  borderRadius: 36,
                  border: "6px solid #1F2937",
                  background: "#0F172A",
                  boxShadow: "0 18px 36px rgba(0,0,0,0.25)",
                  position: "relative",
                  overflow: "hidden",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  padding: "16px 12px",
                }}
              >
                {/* Dynamic island notch */}
                <div
                  style={{
                    width: 70,
                    height: 14,
                    background: "#000",
                    borderRadius: 10,
                    margin: "0 auto",
                  }}
                />

                {/* Simulated visual based on template */}
                <div
                  style={{
                    flex: 1,
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "center",
                    alignItems: "center",
                    textAlign: "center",
                    padding: 8,
                  }}
                >
                  {selectedTemplate === "caption_header" && (
                    <div
                      style={{
                        background: "rgba(0,0,0,0.7)",
                        color: "#FFD700",
                        fontWeight: 800,
                        fontSize: 10,
                        padding: "4px 8px",
                        borderRadius: 4,
                        marginBottom: 10,
                        textTransform: "uppercase",
                      }}
                    >
                      🔥 BÍ MẬT VIRAL 🔥
                    </div>
                  )}

                  <div
                    style={{
                      width: "100%",
                      height: selectedTemplate === "split_screen" ? "65%" : "50%",
                      background: "linear-gradient(135deg, #3B82F6, #8B5CF6)",
                      borderRadius: 8,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#FFF",
                      fontSize: 10,
                    }}
                  >
                    🎬 Visual Cảnh #{selectedSceneIndex + 1}
                  </div>

                  {/* Subtitle simulation */}
                  <div
                    style={{
                      marginTop: 12,
                      background: "rgba(0, 0, 0, 0.65)",
                      color: "#FFFFFF",
                      padding: "4px 8px",
                      borderRadius: 6,
                      fontSize: 10,
                      fontWeight: 700,
                      lineHeight: 1.3,
                    }}
                  >
                    {scenes[selectedSceneIndex]?.text || "Phụ đề động TikTok..."}
                  </div>
                </div>

                {/* Bottom home indicator */}
                <div
                  style={{
                    width: 60,
                    height: 3,
                    background: "rgba(255,255,255,0.4)",
                    borderRadius: 2,
                    margin: "0 auto",
                  }}
                />
              </div>

              <div style={{ fontSize: 11, color: "var(--text-2)", marginTop: 12, textAlign: "center" }}>
                Template: <strong>{selectedTemplate}</strong> | Tốc độ: <strong>{voiceSpeed}x</strong>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: Rendering & Output Download */}
        {activeStep === 3 && (
          <div
            className="bottom-card"
            style={{
              padding: "40px 24px",
              borderRadius: 24,
              textAlign: "center",
              maxWidth: 700,
              margin: "0 auto",
            }}
          >
            {rendering ? (
              <div>
                <div
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: 20,
                    background: "rgba(139, 92, 246, 0.12)",
                    color: "#8B5CF6",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    margin: "0 auto 16px auto",
                  }}
                >
                  <RefreshIcon size={32} className="spinning" />
                </div>
                <h2 style={{ fontSize: 20, fontWeight: 700, margin: "0 0 8px 0" }}>
                  Đang Dựng Video Ngắn 9:16...
                </h2>
                <p style={{ color: "var(--text-2)", fontSize: 13, marginBottom: 24 }}>
                  {renderMessage || "Đang tổng hợp giọng đọc AI và ghép khung hình..."}
                </p>

                {/* Progress bar */}
                <div
                  style={{
                    width: "100%",
                    height: 10,
                    borderRadius: 8,
                    background: "rgba(76,104,153,0.12)",
                    overflow: "hidden",
                    marginBottom: 12,
                  }}
                >
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${renderProgress}%` }}
                    transition={{ ease: "easeOut", duration: 0.3 }}
                    style={{
                      height: "100%",
                      background: "linear-gradient(90deg, #8B5CF6, #EC4899)",
                    }}
                  />
                </div>
                <span style={{ fontSize: 13, fontWeight: 700, color: "#8B5CF6" }}>{renderProgress}%</span>
              </div>
            ) : outputVideoUrl ? (
              <div>
                <div
                  style={{
                    width: 60,
                    height: 60,
                    borderRadius: 18,
                    background: "#DCFCE7",
                    color: "#16A34A",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    margin: "0 auto 16px auto",
                  }}
                >
                  <CheckIcon size={32} />
                </div>
                <h2 style={{ fontSize: 22, fontWeight: 700, margin: "0 0 8px 0" }}>
                  🎉 Video Ngắn 9:16 Đã Hoàn Thành!
                </h2>
                <p style={{ color: "var(--text-2)", fontSize: 13, marginBottom: 24 }}>
                  Video đã được render hoàn chỉnh với phụ đề động và giọng đọc AI.
                </p>

                {/* Video player */}
                <div style={{ maxWidth: 300, margin: "0 auto 24px auto", borderRadius: 16, overflow: "hidden", boxShadow: "0 10px 25px rgba(0,0,0,0.18)" }}>
                  <video
                    src={outputVideoUrl}
                    controls
                    playsInline
                    style={{ width: "100%", display: "block", background: "#000" }}
                  />
                </div>

                <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
                  <a
                    href={outputVideoUrl}
                    download={`${projectName}.mp4`}
                    className="continue-primary-btn"
                    style={{
                      background: "linear-gradient(135deg, #10B981, #059669)",
                      textDecoration: "none",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <DownloadIcon size={18} /> Tải Video MP4
                  </a>

                  {onOpenInDubStudio && (
                    <button
                      className="continue-primary-btn"
                      style={{ background: "#FFFFFF", color: "var(--text)", border: "1px solid rgba(76,104,153,0.2)" }}
                      onClick={onOpenInDubStudio}
                    >
                      Mở Auto Dub Studio ›
                    </button>
                  )}

                  <button
                    className="continue-primary-btn"
                    style={{ background: "#FFFFFF", color: "var(--text)", border: "1px solid rgba(76,104,153,0.2)" }}
                    onClick={() => {
                      setActiveStep(1);
                      setOutputVideoUrl(null);
                    }}
                  >
                    Tạo video khác
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <p style={{ color: "var(--text-2)" }}>Chưa có tác vụ render nào đang chạy.</p>
                <button
                  className="continue-primary-btn"
                  onClick={() => setActiveStep(1)}
                  style={{ marginTop: 12 }}
                >
                  ← Bắt đầu lại
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
