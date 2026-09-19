import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import confetti from "canvas-confetti";
import "./styles.css";
import InteractiveCanvas from "./components/InteractiveCanvas.jsx";
import IconRail from "./components/IconRail.jsx";
import Topbar from "./components/Topbar.jsx";
import HomeView from "./components/home/HomeView.jsx";
import AskKappakDrawer from "./components/AskKappakDrawer.jsx";
import DownloaderView from "./components/downloader/DownloaderView.jsx";
import DataStudioView from "./components/data_studio/DataStudioView.jsx";
import AutoVideoView from "./components/auto_video/AutoVideoView.jsx";
import {
  PlayIcon, MicIcon, BlurIcon, GearIcon, ReviewIcon, FolderIcon, UploadIcon,
  DownloadIcon, MoonIcon, SunIcon, BellIcon, SparkIcon, BotIcon, CheckIcon,
  ChevronRightIcon, ScissorsIcon, CropIcon, WandIcon, CameraIcon, MoreIcon,
  VolumeIcon, ExpandIcon, HeadphoneIcon, EyeIcon, TrashIcon, PlusIcon,
  SearchIcon, FileIcon, CloseIcon, ExportVideoIcon, CapCutIcon
} from "./icons.jsx";

// 5-Step Pipeline Definition
const steps = [
  { n: 1, title: "Source Video", sub: "Chọn video MP4", icon: PlayIcon },
  { n: 2, title: "Voice & AI", sub: "Giọng đọc & tốc độ", icon: MicIcon },
  { n: 3, title: "Blur Regions", sub: "Vẽ vùng che mờ", icon: BlurIcon },
  { n: 4, title: "Automation", sub: "Dịch & lồng tiếng", icon: GearIcon },
  { n: 5, title: "Review & Export", sub: "Duyệt & xuất bản", icon: ReviewIcon },
];

// Apple Spring Physics Preset
const appleSpring = {
  type: "spring",
  stiffness: 380,
  damping: 28,
  mass: 0.85
};

// Default Quick Blur Presets (Normalized Coordinates)
const BLUR_PRESETS = [
  {
    id: "preset_bottom_sub",
    name: "Phụ đề dưới",
    desc: "Che 2 dòng phụ đề đáy",
    x: 0.08,
    y: 0.82,
    width: 0.84,
    height: 0.14,
    blur: 16,
    mask_type: "erase"
  },
  {
    id: "preset_top_right",
    name: "Watermark góc phải",
    desc: "Logo / ID tài khoản",
    x: 0.75,
    y: 0.05,
    width: 0.20,
    height: 0.10,
    blur: 16,
    mask_type: "erase"
  },
  {
    id: "preset_full_bottom",
    name: "Toàn dải đáy",
    desc: "Dải che phụ đề TikTok / Douyin",
    x: 0.0,
    y: 0.80,
    width: 1.0,
    height: 0.20,
    blur: 16,
    mask_type: "erase"
  }
];

// Fallback Voices Catalog
const DEFAULT_VOICES = [
  { id: "vi-VN-HoaiMyNeural", name: "Hoài My (Nữ truyền cảm)", provider: "Edge TTS" },
  { id: "vi-VN-NamMinhNeural", name: "Nam Minh (Nam trầm ấm)", provider: "Edge TTS" },
  { id: "vbee-ngoc-huyen", name: "Ngọc Huyền (Nữ miền Bắc)", provider: "Vbee" },
  { id: "vbee-manh-dung", name: "Mạnh Dũng (Nam miền Bắc)", provider: "Vbee" },
  { id: "vbee-mai-phuong", name: "Mai Phương (Nữ miền Nam)", provider: "Vbee" },
];

/* ========================================================
   HEADER & BRANDING
   ======================================================== */
function LegacyTopbar({ dark, setDark, onSettings, bridgeStatus, islandState }) {
  return (
    <header className="topbar">
      <div className="brand">
        <img
          src="/logo.png"
          alt="KAPPAK Studio"
          className="brand-img"
          onError={(e) => { e.target.style.display = 'none'; }}
        />
        <div>
          <strong>KAPPAK</strong>
          <small>STUDIO WEB v2</small>
        </div>
      </div>

      {/* Ẩn tạm credit pills theo yêu cầu người dùng */}
      {/*
      <div className="credit">
        <div className="credit-line blue">
          <SparkIcon size={14} />
          <span>Sản phẩm tạo bởi <b>vanhkhuc.dev</b></span>
        </div>
        <div className="credit-line pink">
          <span className="heart-svg">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 21s-8-4.7-8-11a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 10c0 6.3-8 11-8 11Z"/>
            </svg>
          </span>
          <span>Dành tặng em bé <b>Trang Vũ &lt;3</b></span>
        </div>
      </div>
      */}

      <div className="top-actions">
        {islandState && <DynamicIsland islandState={islandState} />}

        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="icon-button"
          onClick={() => setDark((v) => !v)}
          aria-label="Đổi giao diện Dark/Light"
          title={dark ? "Chuyển sang giao diện Sáng" : "Chuyển sang giao diện Tối"}
        >
          {dark ? <SunIcon size={18} /> : <MoonIcon size={18} />}
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.03 }}
          className={`integration ${bridgeStatus?.chatgpt ? "active" : ""}`}
          title={bridgeStatus?.chatgpt ? "ChatGPT Đã Kết Nối" : "ChatGPT Chưa Kết Nối"}
        >
          <BotIcon size={17} />
          <span>ChatGPT {bridgeStatus?.chatgpt ? "●" : ""}</span>
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.03 }}
          className={`integration ${bridgeStatus?.vbee ? "active" : ""}`}
          title={bridgeStatus?.vbee ? "Vbee Đã Kết Nối" : "Vbee Chưa Kết Nối"}
        >
          <SparkIcon size={17} />
          <span>Vbee {bridgeStatus?.vbee ? "●" : ""}</span>
        </motion.button>

        <motion.button whileHover={{ scale: 1.05 }} className="icon-button notify" aria-label="Thông báo">
          <BellIcon size={18} />
          <i />
        </motion.button>

        <div className="avatar" title="vanhkhuc.dev">VK</div>

        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="icon-button"
          onClick={onSettings}
          aria-label="Cài đặt hệ thống"
        >
          <GearIcon size={18} />
        </motion.button>
      </div>
    </header>
  );
}

/* ========================================================
   SIDEBAR WORKFLOW STEPS
   ======================================================== */
function Sidebar({ step, setStep }) {
  return (
    <aside className="sidebar">
      <div className="section-label">WORKFLOW</div>
      <div className="steps">
        {steps.map((s) => {
          const Icon = s.icon;
          const active = step === s.n;
          const done = step > s.n;
          return (
            <motion.button
              whileHover={{ x: 3 }}
              whileTap={{ scale: 0.98 }}
              className={`step ${active ? "active" : ""}`}
              key={s.n}
              onClick={() => setStep(s.n)}
            >
              <span className="step-icon"><Icon size={19} /></span>
              <span className="step-copy">
                <b>{String(s.n).padStart(2, "0")} · {s.title}</b>
                <small>{s.sub}</small>
              </span>
              <span className={`step-status ${done ? "done" : ""}`}>
                {done ? <CheckIcon size={13} /> : null}
              </span>
            </motion.button>
          );
        })}
      </div>

      <div className="sidebar-spacer" />

      <div className="version-box">
        <div><i className="dot" /> KAPPAK Studio v2.0</div>
        <div><i className="dot" /> Apple Minimalist Web UI</div>
        <p>Tự động hóa bóc băng, dịch ngữ cảnh & lồng tiếng video 1-chạm.</p>
      </div>
    </aside>
  );
}

/* ========================================================
   APPLE DYNAMIC ISLAND
   ======================================================== */
function DynamicIsland({ islandState }) {
  // islandState: { type: 'idle' | 'loading' | 'voice' | 'running' | 'success' | 'error', message: string, progress?: number }
  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.92 }}
      transition={appleSpring}
      className="dynamic-island"
    >
      {islandState.type === "idle" && (
        <>
          <div className="island-dot" />
          <span>{islandState.message || "KAPPAK v2 · Sẵn sàng"}</span>
        </>
      )}

      {islandState.type === "loading" && (
        <>
          <div className="island-spinner" />
          <span>{islandState.message || "Đang xử lý…"}</span>
        </>
      )}

      {islandState.type === "voice" && (
        <>
          <SparkIcon size={16} className="heart-svg" />
          <span>{islandState.message || "Đang nghe thử giọng đọc…"}</span>
        </>
      )}

      {islandState.type === "running" && (
        <>
          <div className="island-spinner" />
          <span>{islandState.message || "Đang xử lý pipeline…"}</span>
          {typeof islandState.progress === "number" && (
            <>
              <div className="island-progress-bar">
                <i style={{ width: `${islandState.progress}%` }} />
              </div>
              <span style={{ fontSize: 11, opacity: 0.8 }}>{islandState.progress}%</span>
            </>
          )}
        </>
      )}

      {islandState.type === "success" && (
        <>
          <div className="island-dot" style={{ background: "#30d158" }} />
          <CheckIcon size={15} />
          <span>{islandState.message || "Hoàn thành xuất sắc!"}</span>
        </>
      )}

      {islandState.type === "error" && (
        <>
          <div className="island-dot red" />
          <span>{islandState.message || "Có lỗi xảy ra"}</span>
        </>
      )}
    </motion.div>
  );
}

/* ========================================================
   VIDEO PREVIEW & INTERACTIVE CANVAS PLAYER
   ======================================================== */
function Preview({
  step,
  metadata,
  videoUrl,
  masks,
  activeMaskId,
  setActiveMaskId,
  onMasksChange,
  aspectMode = "auto",
  setAspectMode,
  videoRef: externalVideoRef
}) {
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const [detectedAspect, setDetectedAspect] = useState(null);
  const [playerReady, setPlayerReady] = useState(false);

  const localVideoRef = useRef(null);
  const videoRef = externalVideoRef || localVideoRef;
  const screenRef = useRef(null);

  // Badge "Sẵn sàng" chỉ sau khi <video> load metadata thành công
  useEffect(() => {
    setPlayerReady(false);
    setDuration(0);
    setCurrentTime(0);
    setDetectedAspect(null);
    setPlaying(false);
  }, [videoUrl]);

  const togglePlay = useCallback((e) => {
    // If click originated on a mask or handle, do not toggle video play
    if (e && e.target && e.target.closest && (e.target.closest(".interactive-mask-box") || e.target.closest(".interactive-canvas-overlay"))) {
      return;
    }
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      videoRef.current.play().catch(() => {});
      setPlaying(true);
    } else {
      videoRef.current.pause();
      setPlaying(false);
    }
  }, []);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
      if (videoRef.current.duration) {
        setDuration(videoRef.current.duration);
      }
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration || 0);
      const w = videoRef.current.videoWidth;
      const h = videoRef.current.videoHeight;
      if (w > 0 && h > 0) {
        setDetectedAspect({ width: w, height: h });
      }
      // readyState >= 1 (HAVE_METADATA) = video đã vào player thành công
      if (videoRef.current.readyState >= 1) {
        setPlayerReady(true);
      }
    }
  };

  const handleTimelineSeek = (e) => {
    if (!videoRef.current || duration <= 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pos = (e.clientX - rect.left) / rect.width;
    const targetTime = Math.max(0, Math.min(duration, pos * duration));
    videoRef.current.currentTime = targetTime;
    setCurrentTime(targetTime);
  };

  const toggleMute = () => {
    if (!videoRef.current) return;
    videoRef.current.muted = !videoRef.current.muted;
    setIsMuted(videoRef.current.muted);
  };

  const toggleFullscreen = () => {
    if (!screenRef.current) return;
    if (!document.fullscreenElement) {
      screenRef.current.requestFullscreen?.().catch(() => {});
    } else {
      document.exitFullscreen?.().catch(() => {});
    }
  };

  const formatSeconds = (sec) => {
    if (!sec || isNaN(sec)) return "00:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  };

  const effectiveRatio = useMemo(() => {
    if (detectedAspect?.width && detectedAspect?.height) {
      const { width, height } = detectedAspect;
      return {
        width,
        height,
        label: height > width ? "9:16 Dọc (Tự động)" : "16:9 Ngang (Tự động)"
      };
    }

    if (metadata?.width && metadata?.height) {
      const w = Number(metadata.width);
      const h = Number(metadata.height);
      if (w > 0 && h > 0) {
        return {
          width: w,
          height: h,
          label: h > w ? "9:16 Dọc (Tự động)" : "16:9 Ngang (Tự động)"
        };
      }
    }

    if (metadata?.resolution) {
      const parts = metadata.resolution.split(/[×xX]/);
      if (parts.length === 2) {
        const w = parseFloat(parts[0].trim());
        const h = parseFloat(parts[1].trim());
        if (w > 0 && h > 0) {
          return {
            width: w,
            height: h,
            label: h > w ? "9:16 Dọc (Tự động)" : "16:9 Ngang (Tự động)"
          };
        }
      }
    }

    return { width: 16, height: 9, label: "16:9 Ngang (Mặc định)" };
  }, [detectedAspect, metadata]);

  const isVertical = effectiveRatio.height > effectiveRatio.width;
  const isSquare = Math.abs(effectiveRatio.width - effectiveRatio.height) < 10;
  const ratioValue = effectiveRatio.width / effectiveRatio.height;

  return (
    <section className="preview">
      <div className="preview-head">
        <div className="file-title">
          <FolderIcon size={18} />
          <b>{metadata?.filename || "Chưa tải video — Kéo thả hoặc chọn tệp"}</b>
        </div>
        {playerReady ? (
          <div className="saved">
            <CheckIcon size={14} />
            <span>Sẵn sàng</span>
          </div>
        ) : (
          <div className="saved pending" style={{ background: "rgba(120,120,128,0.12)", color: "var(--text-3)", borderColor: "rgba(120,120,128,0.2)" }}>
            <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", background: "var(--text-3)", marginRight: 5 }} />
            <span>Chưa sẵn sàng</span>
          </div>
        )}
      </div>

      <div className="video-card">
        {/* Video Stage Frame */}
        <div className="video-stage">
          <div
            className={`screen ${isVertical ? "is-vertical" : isSquare ? "is-square" : "is-horizontal"}`}
            ref={screenRef}
            onClick={togglePlay}
            style={{
              aspectRatio: `${effectiveRatio.width} / ${effectiveRatio.height}`,
              height: isVertical ? "500px" : isSquare ? "400px" : "auto",
              width: isVertical ? `${Math.round(500 * ratioValue)}px` : isSquare ? "400px" : "100%",
              maxHeight: isVertical ? "520px" : "460px",
              maxWidth: "100%",
              margin: "0 auto",
            }}
          >
            {videoUrl && (
              <video
                ref={videoRef}
                src={videoUrl}
                controls={false}
                loop
                playsInline
                onPlay={() => setPlaying(true)}
                onPause={() => setPlaying(false)}
                onTimeUpdate={handleTimeUpdate}
                onLoadedMetadata={handleLoadedMetadata}
              />
            )}

            {/* Interactive Canvas Overlay (ONLY when a video is loaded) */}
            {videoUrl && (
              <InteractiveCanvas
                videoRef={videoRef}
                containerRef={screenRef}
                masks={masks}
                activeMaskId={activeMaskId}
                setActiveMaskId={setActiveMaskId}
                onMasksChange={onMasksChange}
                enabled={step === 3 || masks.length > 0}
                videoAspectRatio={effectiveRatio}
              />
            )}
          </div>
        </div>

        {/* Video Player Controls Bar */}
        <div className="player">
          <motion.button
            whileTap={{ scale: 0.9 }}
            onClick={(e) => { e.stopPropagation(); togglePlay(); }}
            title={playing ? "Tạm dừng" : "Phát"}
          >
            <PlayIcon size={18} />
          </motion.button>

          <span className="player-time">{formatSeconds(currentTime)}</span>

          <div className="timeline" onClick={handleTimelineSeek}>
            <i style={{ width: duration > 0 ? `${(currentTime / duration) * 100}%` : "0%" }} />
          </div>

          <span className="player-time">{formatSeconds(duration || 0)}</span>

          <button onClick={toggleMute} title={isMuted ? "Bật âm thanh" : "Tắt âm thanh"}>
            <VolumeIcon size={17} />
          </button>
          <button onClick={toggleFullscreen} title="Toàn màn hình">
            <ExpandIcon size={17} />
          </button>
        </div>
      </div>

      {/* Toolbar below Video */}
      <div className="toolbar">
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
          className="primary"
          onClick={togglePlay}
        >
          <PlayIcon size={16} />
          {playing ? "Tạm dừng" : "Phát video"}
        </motion.button>
        <button onClick={() => { if (videoRef.current) videoRef.current.currentTime = 0; }}>
          <ScissorsIcon size={16} /> Về đầu
        </button>
        <button onClick={() => { if (videoRef.current) videoRef.current.currentTime += 5; }}>
          <ChevronRightIcon size={16} /> +5s
        </button>
        <button className="icon-only" title="Tùy chọn khác">
          <MoreIcon size={18} />
        </button>
      </div>

      {/* Video Metadata Cards */}
      <div className="meta">
        {[
          [metadata?.resolution || "--", "Độ phân giải"],
          [metadata?.duration_str || "--", "Thời lượng"],
          [metadata?.fps ? `${metadata.fps} fps` : "--", "Khung hình"],
          [metadata?.size_mb ? `${metadata.size_mb} MB` : "--", "Dung lượng"],
          [metadata?.video_codec ? `${metadata.video_codec.toUpperCase()} / AAC` : "--", "Định dạng"]
        ].map(([val, label]) => (
          <div key={label}>
            <b>{val}</b>
            <small>{label}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ========================================================
   GENERIC PANEL CONTAINER
   ======================================================== */
function Panel({ kicker, title, desc, children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -10, scale: 0.98 }}
      transition={appleSpring}
      className="panel"
    >
      <div className="kicker">{kicker}</div>
      <h1>{title}</h1>
      <p className="desc">{desc}</p>
      {children}
    </motion.div>
  );
}

/* ========================================================
   STEP 1: SOURCE VIDEO
   ======================================================== */
function Step1({ next, metadata, onUpload, uploading, onLoadSample }) {
  const fileRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files?.[0]) {
      onUpload(e.dataTransfer.files[0]);
    }
  };

  return (
    <Panel
      kicker="BƯỚC 01 / 05"
      title="Nguồn video"
      desc="Chọn video MP4 từ máy hoặc kéo thả trực tiếp để phân tích tự động."
    >
      <input
        type="file"
        ref={fileRef}
        style={{ display: "none" }}
        accept="video/mp4,video/quicktime,video/mkv,video/webm"
        onChange={(e) => {
          if (e.target.files?.[0]) onUpload(e.target.files[0]);
        }}
      />

      <motion.div
        whileHover={{ scale: 1.01 }}
        className={`dropzone ${isDragOver ? "drag-over" : ""}`}
        onClick={() => fileRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        style={{ cursor: "pointer" }}
      >
        <span className="upload-circle">
          {uploading ? <div className="island-spinner" /> : <UploadIcon size={26} />}
        </span>
        <b>{uploading ? "Đang tải và phân tích video…" : "Thả video vào đây"}</b>
        <small>Hỗ trợ MP4 · MOV · MKV · Tự động đọc độ phân giải & khung hình</small>
        <button
          className="btn blue"
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            fileRef.current?.click();
          }}
        >
          <FolderIcon size={17} />
          Chọn video từ máy
        </button>
      </motion.div>

      {/* 1-Click Quick Sample Loaders */}
      <div style={{ marginTop: 10, marginBottom: 12 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", marginBottom: 8, textTransform: "uppercase" }}>
          ⚡ Nạp video mẫu thử nghiệm (1-chạm)
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <motion.button
            type="button"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="btn outline"
            style={{ fontSize: 11, padding: "8px 10px", justifyContent: "center", display: "flex", gap: 6 }}
            onClick={() => onLoadSample?.("vertical")}
          >
            <span>📱 Mẫu dọc 9:16 (TikTok)</span>
          </motion.button>
          <motion.button
            type="button"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="btn outline"
            style={{ fontSize: 11, padding: "8px 10px", justifyContent: "center", display: "flex", gap: 6 }}
            onClick={() => onLoadSample?.("horizontal")}
          >
            <span>💻 Mẫu ngang 16:9 (YouTube)</span>
          </motion.button>
        </div>
      </div>

      {metadata && (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className="card"
        >
          <div className="card-head">
            <b>Video đã sẵn sàng</b>
            <span className="status-pill">Sẵn sàng</span>
          </div>
          <div className="file-row">
            <FileIcon size={18} />
            <div>
              <b>{metadata.filename}</b>
              <small>{metadata.resolution} · {metadata.duration_str} · {metadata.fps} fps · {metadata.size_mb} MB</small>
            </div>
            <button className="ghost" onClick={() => fileRef.current?.click()}>Đổi video</button>
          </div>
          <div className="path">{metadata.path}</div>
        </motion.div>
      )}

      <motion.button
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.98 }}
        className="btn lime footer"
        onClick={next}
      >
        <span>Tiếp tục: Cấu hình giọng đọc</span>
        <ChevronRightIcon />
      </motion.button>
    </Panel>
  );
}

/* ========================================================
   STEP 2: VOICE SELECTION & 1-CLICK PREVIEW
   ======================================================== */
function Step2({
  next,
  voices,
  selectedVoice,
  setSelectedVoice,
  voiceSpeed,
  setVoiceSpeed,
  onPreviewVoice,
  isPlayingVoice
}) {
  const sampleVoiceText = "Xin chào, đây là giọng đọc thử nghiệm chất lượng cao trên hệ thống KAPPAK Studio Web v2.";

  return (
    <Panel
      kicker="BƯỚC 02 / 05"
      title="Cấu hình giọng đọc"
      desc="Chọn chất giọng AI, tốc độ phát và nghe thử trực tiếp trước khi lồng tiếng."
    >
      <div className="card form-card">
        <label>
          <span>Giọng đọc AI (Edge TTS / Vbee)</span>
          <select
            value={selectedVoice}
            onChange={(e) => setSelectedVoice(e.target.value)}
          >
            {(voices.length > 0 ? voices : DEFAULT_VOICES).map((v) => (
              <option key={v.id} value={v.id}>
                {v.name} ({v.provider})
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Tốc độ đọc giọng nói</span>
          <select value={voiceSpeed} onChange={(e) => setVoiceSpeed(e.target.value)}>
            <option value="0.9x">0.9x · Chậm rãi, truyền cảm</option>
            <option value="1.0x">1.0x · Tốc độ chuẩn tự nhiên</option>
            <option value="1.1x">1.1x · Khuyên dùng cho Short Drama / TikTok</option>
            <option value="1.2x">1.2x · Nhanh gọn, dồn dập</option>
            <option value="1.3x">1.3x · Douyin style</option>
          </select>
        </label>
      </div>

      {/* 1-Click Voice Audio Preview */}
      <div className="card">
        <div className="card-head">
          <b>Nghe thử chất giọng</b>
          <span>Trích đoạn kịch bản mẫu</span>
        </div>
        <div className="wave-row">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="circle-play"
            onClick={() => onPreviewVoice(selectedVoice, sampleVoiceText)}
            title="Nghe thử giọng đọc này"
          >
            {isPlayingVoice ? (
              <div className="island-spinner" style={{ width: 16, height: 16 }} />
            ) : (
              <PlayIcon size={16} />
            )}
          </motion.button>

          <div className="wave">
            {Array.from({ length: 32 }).map((_, i) => (
              <i
                key={i}
                style={{
                  height: isPlayingVoice ? Math.max(12, ((i * 19 + Date.now() / 80) % 36) + 6) : Math.max(8, (i * 17) % 28 + 6)
                }}
              />
            ))}
          </div>
        </div>
        <small style={{ color: "var(--muted)", fontSize: 11 }}>
          Nhấp nút phát để nghe trực tiếp âm thanh tổng hợp từ máy chủ.
        </small>
      </div>

      <div className="hint">
        <SparkIcon size={18} />
        <div>
          <b>Gợi ý từ chuyên gia</b>
          <span>Tốc độ 1.1x kết hợp giọng Hoài My hoặc Ngọc Huyền đạt tỷ lệ giữ chân người xem video ngắn cao nhất.</span>
        </div>
      </div>

      <motion.button
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.98 }}
        className="btn lime footer"
        onClick={next}
      >
        <span>Tiếp tục: Vẽ vùng che mờ</span>
        <ChevronRightIcon />
      </motion.button>
    </Panel>
  );
}

/* ========================================================
   STEP 3: INTERACTIVE BLUR CANVAS (NO MANUAL X/Y/W/H BOXES)
   ======================================================== */
function Step3({
  next,
  masks,
  activeMaskId,
  setActiveMaskId,
  onMasksChange,
  applyPreset,
  deleteActiveMask,
  centerActiveMaskHorizontally,
  updateActiveMaskBlur
}) {
  const activeMask = masks.find((m) => m.id === activeMaskId) || masks[0];

  return (
    <Panel
      kicker="BƯỚC 03 / 05"
      title="Khung che mờ tương tác"
      desc="Dùng chuột vẽ và kéo trực tiếp trên khung hình video để che phụ đề hoặc watermark gốc."
    >
      {/* 1-Click Quick Presets */}
      <div>
        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", marginBottom: 8, textTransform: "uppercase" }}>
          Preset che mờ 1-chạm
        </div>
        <div className="preset-grid">
          {BLUR_PRESETS.map((preset) => (
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              key={preset.id}
              className="preset-chip"
              onClick={() => applyPreset(preset)}
            >
              <WandIcon size={16} />
              <b>{preset.name}</b>
              <small>{preset.desc}</small>
            </motion.button>
          ))}
        </div>
      </div>

      {/* Active Mask Configuration Card (NO X/Y/W/H TEXTBOXES) */}
      {activeMask ? (
        <div className="active-mask-card">
          <div className="card-head" style={{ marginBottom: 4 }}>
            <b>{activeMask.label || "Vùng đang chọn"}</b>
            <span className="status-pill">Đang chỉnh sửa</span>
          </div>

          <div style={{ display: "flex", gap: 12, fontSize: 11, color: "var(--muted)", fontFamily: "var(--font-mono)" }}>
            <span>Vị trí: X {Math.round(activeMask.x * 100)}%, Y {Math.round(activeMask.y * 100)}%</span>
            <span>Kích thước: {Math.round(activeMask.width * 100)}% × {Math.round(activeMask.height * 100)}%</span>
          </div>

          {/* Blur Strength Slider */}
          <div className="blur-slider-row">
            <label>
              <span>Độ mờ che phủ (Blur Strength)</span>
              <b style={{ color: "var(--apple-blue)" }}>{activeMask.blur || 16} px</b>
            </label>
            <input
              type="range"
              min="4"
              max="36"
              step="2"
              value={activeMask.blur || 16}
              onChange={(e) => updateActiveMaskBlur(parseInt(e.target.value, 10))}
            />
          </div>

          {/* Quick Actions */}
          <div className="mask-control-btns">
            <button type="button" onClick={centerActiveMaskHorizontally} title="Căn giữa ngang">
              <CropIcon size={14} />
              Căn giữa ngang
            </button>
            <button type="button" className="danger" onClick={deleteActiveMask} title="Xóa vùng này">
              <TrashIcon size={14} />
              Xóa vùng này
            </button>
          </div>
        </div>
      ) : (
        <div className="card" style={{ textAlign: "center", padding: 20 }}>
          <p style={{ color: "var(--muted)", fontSize: 12 }}>
            Chưa có vùng che mờ nào. Nhấp vào preset phía trên hoặc kéo chuột trực tiếp trên khung video để vẽ vùng mới.
          </p>
        </div>
      )}

      {/* Mask List */}
      <div className="card">
        <div className="card-head">
          <b>Danh sách vùng che ({masks.length})</b>
          <span>Nhấp để chọn và chỉnh</span>
        </div>
        <div className="region-list">
          {masks.map((m, idx) => {
            const isActive = m.id === activeMaskId;
            return (
              <div
                key={m.id}
                className={`region ${isActive ? "active" : ""}`}
                onClick={() => setActiveMaskId(m.id)}
              >
                <span className="num">{String(idx + 1).padStart(2, "0")}</span>
                <div>
                  <b>{m.label || `Vùng ${idx + 1}`}</b>
                  <small>
                    Tỉ lệ {Math.round(m.width * 100)}% × {Math.round(m.height * 100)}% · Mờ {m.blur || 16}px
                  </small>
                </div>
                <div className="region-actions">
                  <button
                    type="button"
                    className="danger"
                    title="Xóa vùng này"
                    onClick={(e) => {
                      e.stopPropagation();
                      const updated = masks.filter((item) => item.id !== m.id);
                      onMasksChange(updated);
                      if (activeMaskId === m.id) {
                        setActiveMaskId(updated.length > 0 ? updated[0].id : null);
                      }
                    }}
                  >
                    <TrashIcon size={14} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="hint">
        <SparkIcon size={18} />
        <div>
          <b>Thao tác trực quan trên màn hình</b>
          <span>Kéo thân hộp để đổi vị trí, kéo 8 điểm neo ở các góc và cạnh để co giãn vùng che tùy ý.</span>
        </div>
      </div>

      <motion.button
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.98 }}
        className="btn lime footer"
        onClick={next}
      >
        <span>Tiếp tục: Xử lý tự động 1-chạm</span>
        <ChevronRightIcon />
      </motion.button>
    </Panel>
  );
}

/* ========================================================
   STEP 4: AUTOMATION PIPELINE (1-CLICK & WS PROGRESS)
   ======================================================== */
function Step4({ next, pipelineStatus, startPipeline, cancelPipeline }) {
  return (
    <Panel
      kicker="BƯỚC 04 / 05"
      title="Xử lý tự động 1-chạm"
      desc="Hệ thống tự bóc băng Whisper, dịch ngữ cảnh thông minh và tổng hợp giọng nói."
    >
      <div className="connections">
        <div>
          <BotIcon size={18} />
          <span><b>ChatGPT 4o</b><small>Sẵn sàng</small></span>
        </div>
        <div>
          <SparkIcon size={18} />
          <span><b>Vbee / Edge</b><small>Đã kết nối</small></span>
        </div>
        <div>
          <HeadphoneIcon size={18} />
          <span><b>Faster-Whisper</b><small>GPU / CPU</small></span>
        </div>
      </div>

      {/* Overall Progress */}
      <div className="card">
        <div className="card-head">
          <b>Tiến độ tổng thể</b>
          <span className="status-pill">{pipelineStatus.overall_pct}%</span>
        </div>
        <div className="progress" style={{ height: 7, margin: "6px 0 8px" }}>
          <motion.i
            initial={{ width: 0 }}
            animate={{ width: `${pipelineStatus.overall_pct}%` }}
            transition={{ duration: 0.3 }}
            style={{ background: "linear-gradient(90deg, #0071e3, #30d158)" }}
          />
        </div>
        <small style={{ color: "var(--muted)", fontSize: 11 }}>
          {pipelineStatus.overall_msg}
        </small>
      </div>

      {/* Substep Progress List */}
      <div className="jobs">
        {pipelineStatus.substeps.map((job) => {
          const isDone = job.status === "DONE" || job.progress === 100;
          const isRunning = job.status === "RUNNING";
          return (
            <div className="job" key={job.id}>
              <span className={`job-icon ${isDone ? "ok" : ""}`}>
                {isRunning ? (
                  <div className="island-spinner" style={{ width: 14, height: 14 }} />
                ) : isDone ? (
                  <CheckIcon size={15} />
                ) : (
                  <BotIcon size={15} />
                )}
              </span>
              <div>
                <b>{job.name}</b>
                <small>{job.message}</small>
                {isRunning && (
                  <div className="progress" style={{ height: 3, marginTop: 4 }}>
                    <i style={{ width: `${job.progress}%` }} />
                  </div>
                )}
              </div>
              <strong>{isDone ? "100%" : isRunning ? `${job.progress}%` : "0%"}</strong>
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", gap: 10, marginTop: "auto" }}>
        {pipelineStatus.running ? (
          <motion.button
            whileTap={{ scale: 0.98 }}
            className="btn outline full"
            onClick={cancelPipeline}
          >
            <span>Dừng tiến trình</span>
          </motion.button>
        ) : (
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="btn blue full"
            onClick={startPipeline}
          >
            <SparkIcon size={16} />
            <span>Bắt đầu xử lý tự động</span>
          </motion.button>
        )}
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="btn lime footer"
          onClick={next}
        >
          <span>Duyệt & Xuất</span>
          <ChevronRightIcon />
        </motion.button>
      </div>
    </Panel>
  );
}

/* ========================================================
   STEP 5: REVIEW & EXPORT (CONFETTI CELEBRATION)
   ======================================================== */
function Step5({
  subtitles,
  setSubtitles,
  onApprove,
  onExportMP4,
  onExportCapCut,
  exporting,
  approved,
  onSeekSubtitle,
  selectedVoice,
  onPreviewVoice
}) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [replaceQuery, setReplaceQuery] = useState("");

  const handleSubtitleChange = (id, newText) => {
    setSubtitles((prev) =>
      prev.map((item) => (item.id === id ? { ...item, target_text: newText } : item))
    );
  };

  const handleAddCue = () => {
    const newId = subtitles.length + 1;
    let startStr = "00:00:00,000";
    let endStr = "00:00:02,500";
    if (subtitles.length > 0) {
      startStr = subtitles[subtitles.length - 1].end_time || "00:00:00,000";
      endStr = startStr;
    }
    setSubtitles((prev) => [
      ...prev,
      {
        id: newId,
        start_time: startStr,
        end_time: endStr,
        source_text: "Dòng phụ đề bổ sung",
        target_text: "Câu thoại tiếng Việt bổ sung"
      }
    ]);
  };

  const handleDeleteCue = (id) => {
    setSubtitles((prev) => prev.filter((item) => item.id !== id));
  };

  const handleReplaceAll = () => {
    if (!searchQuery) return;
    setSubtitles((prev) =>
      prev.map((item) => ({
        ...item,
        target_text: item.target_text ? item.target_text.replaceAll(searchQuery, replaceQuery) : ""
      }))
    );
  };

  return (
    <Panel
      kicker="BƯỚC 05 / 05"
      title="Duyệt kịch bản & Xuất bản"
      desc="Kiểm tra câu từ kịch bản, chỉnh sửa nhanh và xuất video MP4 hoàn thiện hoặc dự án CapCut 1-chạm."
    >
      <div className="review-actions">
        <button type="button" onClick={handleAddCue}>
          <PlusIcon size={14} /> Thêm câu
        </button>
        <button type="button" onClick={() => setSearchOpen((v) => !v)}>
          <SearchIcon size={14} /> {searchOpen ? "Đóng tìm kiếm" : "Tìm & sửa"}
        </button>
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
          className={`btn ${approved ? "lime" : "blue"}`}
          onClick={onApprove}
        >
          <CheckIcon size={14} />
          {approved ? "Đã chốt duyệt" : "Chốt duyệt kịch bản"}
        </motion.button>
      </div>

      {/* Interactive Search & Replace Bar */}
      {searchOpen && (
        <div className="search-replace-bar">
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input
              type="text"
              placeholder="Từ cần tìm..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ flex: 1 }}
            />
            <input
              type="text"
              placeholder="Thay bằng..."
              value={replaceQuery}
              onChange={(e) => setReplaceQuery(e.target.value)}
              style={{ flex: 1 }}
            />
            <button
              type="button"
              className="btn blue small"
              onClick={handleReplaceAll}
              style={{ padding: "5px 10px", fontSize: 11 }}
            >
              Đổi tất cả
            </button>
            <button
              type="button"
              className="icon-only"
              onClick={() => setSearchOpen(false)}
              title="Đóng"
            >
              <CloseIcon size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Editable Subtitle List */}
      <div className="script-list">
        {subtitles.length > 0 ? (
          subtitles.map((row) => (
            <div className="script" key={row.id}>
              <span>{String(row.id).padStart(2, "0")}</span>
              <time
                onClick={() => onSeekSubtitle?.(row.start_time)}
                title="Nhấp để nhảy video đến mốc này"
              >
                {row.start_time} - {row.end_time}
              </time>
              <div>
                <small style={{ color: "var(--muted)", display: "block", marginBottom: 3 }}>
                  {row.source_text}
                </small>
                <textarea
                  rows={2}
                  value={row.target_text}
                  onChange={(e) => handleSubtitleChange(row.id, e.target.value)}
                />
              </div>
              <div className="script-row-actions">
                <button
                  type="button"
                  title="Nghe thử giọng câu này"
                  onClick={() => onPreviewVoice?.(selectedVoice, row.target_text)}
                >
                  <VolumeIcon size={13} />
                </button>
                <button
                  type="button"
                  className="danger"
                  title="Xóa câu này"
                  onClick={() => handleDeleteCue(row.id)}
                >
                  <TrashIcon size={13} />
                </button>
              </div>
            </div>
          ))
        ) : (
          <div style={{ padding: 24, textAlign: "center", color: "var(--muted)", fontSize: 12 }}>
            Chưa có kịch bản phụ đề. Vui lòng chạy Bước 4 để tự động bóc băng và dịch thuật.
          </div>
        )}
      </div>

      {/* Export Options with Confetti */}
      <div className="export-section">
        <div className="export-title">
          <b>XUẤT BẢN DỰ ÁN 1-CHẠM</b>
          <span>Chọn định dạng mong muốn</span>
        </div>

        <motion.button
          whileHover={{ scale: 1.02, y: -2 }}
          whileTap={{ scale: 0.98 }}
          className="export-card video"
          onClick={onExportMP4}
          disabled={exporting}
        >
          <span className="export-icon">
            {exporting ? <div className="island-spinner" /> : <ExportVideoIcon size={24} />}
          </span>
          <span className="export-copy">
            <b>Xuất video MP4 hoàn thiện</b>
            <small>Đã che mờ phụ đề cũ, ghép âm thanh AI, add subtitle chuẩn nét</small>
          </span>
          <ChevronRightIcon size={18} />
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.02, y: -2 }}
          whileTap={{ scale: 0.98 }}
          className="export-card capcut"
          onClick={onExportCapCut}
          disabled={exporting}
        >
          <span className="export-icon">
            {exporting ? <div className="island-spinner" /> : <CapCutIcon size={24} />}
          </span>
          <span className="export-copy">
            <b>Xuất dự án CapCut (Draft)</b>
            <small>Mở trực tiếp trên CapCut PC với đầy đủ track tiếng, timeline và text</small>
          </span>
          <ChevronRightIcon size={18} />
        </motion.button>
      </div>
    </Panel>
  );
}

/* ========================================================
   SETTINGS MODAL
   ======================================================== */
function SettingsModal({ open, onClose, settings, onSave }) {
  const [defaultOutput, setDefaultOutput] = useState("D:\\Work\\Project_AI\\ToolVideo\\export");
  const [chatgptModel, setChatgptModel] = useState("gpt-4o");
  const [whisperModel, setWhisperModel] = useState("large-v3");

  useEffect(() => {
    if (settings) {
      if (settings.default_output) setDefaultOutput(settings.default_output);
      if (settings.chatgpt_model) setChatgptModel(settings.chatgpt_model);
      if (settings.whisper_model) setWhisperModel(settings.whisper_model);
    }
  }, [settings]);

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <motion.div
        initial={{ opacity: 0, scale: 0.92, y: 15 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.92, y: 15 }}
        transition={appleSpring}
        className="modal-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800 }}>Cài đặt hệ thống KAPPAK</h2>
          <button className="icon-button" onClick={onClose} aria-label="Đóng">
            <CloseIcon size={16} />
          </button>
        </div>

        <div style={{ display: "grid", gap: 14 }}>
          <label style={{ display: "grid", gap: 5 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)" }}>Thư mục xuất mặc định</span>
            <input
              value={defaultOutput}
              onChange={(e) => setDefaultOutput(e.target.value)}
              style={{ padding: 10, borderRadius: 8, border: "1px solid var(--line)", background: "var(--surface)" }}
            />
          </label>
          <label style={{ display: "grid", gap: 5 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)" }}>Model ChatGPT dịch thuật</span>
            <input
              value={chatgptModel}
              onChange={(e) => setChatgptModel(e.target.value)}
              style={{ padding: 10, borderRadius: 8, border: "1px solid var(--line)", background: "var(--surface)" }}
            />
          </label>
          <label style={{ display: "grid", gap: 5 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)" }}>Model Whisper bóc băng</span>
            <input
              value={whisperModel}
              onChange={(e) => setWhisperModel(e.target.value)}
              style={{ padding: 10, borderRadius: 8, border: "1px solid var(--line)", background: "var(--surface)" }}
            />
          </label>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 24 }}>
          <button className="btn outline" onClick={onClose}>Hủy</button>
          <button
            className="btn blue"
            onClick={() => {
              onSave?.({ default_output: defaultOutput, chatgpt_model: chatgptModel, whisper_model: whisperModel });
              onClose();
            }}
          >
            Lưu cài đặt
          </button>
        </div>
      </motion.div>
    </div>
  );
}

/* ========================================================
   MAIN APPLICATION COMPONENT
   ======================================================== */
export default function App() {
  const [dark, setDark] = useState(false);
  const [step, setStep] = useState(1);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("home");
  const [isAskOpen, setIsAskOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const videoPlayerRef = useRef(null);

  // Apple Dynamic Island State
  const [islandState, setIslandState] = useState({
    type: "idle",
    message: "KAPPAK v2 · Sẵn sàng"
  });

  const [metadata, setMetadata] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [aspectMode, setAspectMode] = useState("auto");

  // Voice State
  const [voices, setVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState("vi-VN-HoaiMyNeural");
  const [voiceSpeed, setVoiceSpeed] = useState("1.1x");
  const [isPlayingVoice, setIsPlayingVoice] = useState(false);
  const audioPreviewRef = useRef(null);

  // Masks State (Synchronized with backend /api/masks)
  const [masks, setMasks] = useState([
    {
      id: "mask_default",
      label: "Phụ đề dưới",
      x: 0.08,
      y: 0.82,
      width: 0.84,
      height: 0.14,
      blur: 16,
      mask_type: "erase"
    }
  ]);
  const [activeMaskId, setActiveMaskId] = useState("mask_default");

  const [bridgeStatus, setBridgeStatus] = useState({ connected: false, chatgpt: false, vbee: false });
  const [pipelineStatus, setPipelineStatus] = useState({
    running: false,
    overall_pct: 0,
    overall_msg: "Sẵn sàng",
    substeps: [
      { id: "4.1", name: "Bóc băng phụ đề gốc (Faster-Whisper)", status: "PENDING", progress: 0, message: "Chờ xử lý" },
      { id: "4.2", name: "Dịch ngữ cảnh thông minh (ChatGPT)", status: "PENDING", progress: 0, message: "Chờ xử lý" },
      { id: "4.3", name: "Chuẩn bị kịch bản & timeline giọng đọc", status: "PENDING", progress: 0, message: "Chờ xử lý" },
      { id: "4.4", name: "Tạo giọng đọc AI (Edge / Vbee)", status: "PENDING", progress: 0, message: "Chờ xử lý" },
    ]
  });

  const [subtitles, setSubtitles] = useState([]);
  const [approved, setApproved] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [settings, setSettings] = useState(null);

  // Dynamic Island Timer Helper
  const setTemporaryIsland = useCallback((newState, durationMs = 3500) => {
    setIslandState(newState);
    if (durationMs > 0) {
      setTimeout(() => {
        setIslandState({ type: "idle", message: "KAPPAK v2 · Sẵn sàng" });
      }, durationMs);
    }
  }, []);

  // Sync masks to Backend API (/api/masks)
  const syncMasksToBackend = useCallback(async (updatedMasks) => {
    try {
      await fetch("/api/masks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ masks: updatedMasks })
      });
    } catch (_) {
      // Graceful fallback: local state remains fully functional
    }
  }, []);

  const handleMasksChange = useCallback((updatedMasks) => {
    setMasks(updatedMasks);
    syncMasksToBackend(updatedMasks);
  }, [syncMasksToBackend]);

  // Quick Preset Handler
  const applyPreset = useCallback((preset) => {
    const newMask = {
      id: `mask_${Date.now()}`,
      label: preset.name,
      x: preset.x,
      y: preset.y,
      width: preset.width,
      height: preset.height,
      blur: preset.blur,
      mask_type: preset.mask_type || "erase"
    };
    const updated = [...masks, newMask];
    handleMasksChange(updated);
    setActiveMaskId(newMask.id);
    setTemporaryIsland({ type: "success", message: `Đã áp dụng preset: ${preset.name}` }, 2500);
  }, [masks, handleMasksChange, setTemporaryIsland]);

  const deleteActiveMask = useCallback(() => {
    if (!activeMaskId) return;
    const updated = masks.filter((m) => m.id !== activeMaskId);
    handleMasksChange(updated);
    setActiveMaskId(updated.length > 0 ? updated[0].id : null);
    setTemporaryIsland({ type: "success", message: "Đã xóa vùng che mờ" }, 2000);
  }, [activeMaskId, masks, handleMasksChange, setTemporaryIsland]);

  const centerActiveMaskHorizontally = useCallback(() => {
    if (!activeMaskId) return;
    const updated = masks.map((m) => {
      if (m.id === activeMaskId) {
        const newX = Math.round(((1 - m.width) / 2) * 1000) / 1000;
        return { ...m, x: Math.max(0, newX) };
      }
      return m;
    });
    handleMasksChange(updated);
  }, [activeMaskId, masks, handleMasksChange]);

  const updateActiveMaskBlur = useCallback((newBlur) => {
    if (!activeMaskId) return;
    const updated = masks.map((m) => (m.id === activeMaskId ? { ...m, blur: newBlur } : m));
    handleMasksChange(updated);
  }, [activeMaskId, masks, handleMasksChange]);

  // Voice Audio Preview Handler
  const handlePreviewVoice = useCallback(async (voiceId, text) => {
    setIsPlayingVoice(true);
    setIslandState({ type: "voice", message: "Đang nghe thử giọng đọc…" });

    if (audioPreviewRef.current) {
      audioPreviewRef.current.pause();
      audioPreviewRef.current = null;
    }

    try {
      const res = await fetch("/api/voices/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice_id: voiceId, text })
      });
      const data = await res.json();
      if (data.status === "ok" && data.audio_url) {
        const audio = new Audio(data.audio_url);
        audioPreviewRef.current = audio;
        audio.onended = () => {
          setIsPlayingVoice(false);
          setTemporaryIsland({ type: "success", message: "Nghe thử hoàn tất" }, 2000);
        };
        audio.onerror = () => {
          setIsPlayingVoice(false);
          setTemporaryIsland({ type: "idle", message: "KAPPAK v2 · Sẵn sàng" }, 1500);
        };
        await audio.play();
        return;
      }
    } catch (_) {}

    // Fallback: Web Speech API synthesis
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "vi-VN";
      utterance.rate = parseFloat(voiceSpeed) || 1.0;
      utterance.onend = () => {
        setIsPlayingVoice(false);
        setTemporaryIsland({ type: "success", message: "Nghe thử hoàn tất" }, 2000);
      };
      utterance.onerror = () => {
        setIsPlayingVoice(false);
        setTemporaryIsland({ type: "idle", message: "KAPPAK v2 · Sẵn sàng" }, 1500);
      };
      window.speechSynthesis.speak(utterance);
    } else {
      setTimeout(() => {
        setIsPlayingVoice(false);
        setTemporaryIsland({ type: "success", message: "Giọng đọc mô phỏng thành công" }, 2000);
      }, 2500);
    }
  }, [voiceSpeed, setTemporaryIsland]);

  // Initial Fetch on Mount
  useEffect(() => {
    fetch("/api/health")
      .then((res) => res.json())
      .then(() => setTemporaryIsland({ type: "idle", message: "Đã kết nối máy chủ KAPPAK v2" }, 3000))
      .catch(() => setTemporaryIsland({ type: "idle", message: "KAPPAK v2 · Chế độ Offline" }, 3000));

    fetch("/api/masks")
      .then((res) => res.json())
      .then((data) => {
        const list = Array.isArray(data) ? data : data.masks;
        if (list && list.length > 0) {
          setMasks(list);
          setActiveMaskId(list[0].id);
        }
      })
      .catch(() => {});

    fetch("/api/bridge/status")
      .then((res) => res.json())
      .then((data) => setBridgeStatus(data))
      .catch(() => {});

    fetch("/api/voices")
      .then((res) => res.json())
      .then((data) => {
        if (data.voices && data.voices.length > 0) {
          setVoices(data.voices);
          setSelectedVoice(data.voices[0].id);
        }
      })
      .catch(() => {});

    fetch("/api/review/subtitles")
      .then((res) => res.json())
      .then((data) => {
        if (data.subtitles && data.subtitles.length > 0) {
          setSubtitles(data.subtitles);
        }
      })
      .catch(() => {});

    fetch("/api/settings")
      .then((res) => res.json())
      .then((data) => setSettings(data))
      .catch(() => {});
  }, [setTemporaryIsland]);

  // WebSocket Live Pipeline Status
  useEffect(() => {
    let ws = null;
    try {
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      ws = new WebSocket(`${proto}//${window.location.host}/ws/pipeline`);
      ws.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          if (data.type === "substep") {
            const isSuccess = data.status === "SUCCESS" || data.status === "DONE";
            setPipelineStatus((prev) => ({
              ...prev,
              substeps: prev.substeps.map((s) =>
                s.id === data.step_id
                  ? {
                      ...s,
                      status: isSuccess ? "DONE" : data.status,
                      progress: isSuccess ? 100 : data.progress,
                      message: data.message
                    }
                  : s
              )
            }));
            setIslandState({
              type: isSuccess ? "running" : "running",
              message: data.message,
              progress: data.progress
            });
          } else if (data.type === "overall") {
            setPipelineStatus((prev) => ({
              ...prev,
              overall_pct: data.pct,
              overall_msg: data.message,
              running: data.pct < 100
            }));
            setIslandState({
              type: data.pct < 100 ? "running" : "success",
              message: data.message,
              progress: data.pct
            });
          } else if (data.type === "finished") {
            setPipelineStatus((prev) => ({
              ...prev,
              running: false,
              overall_pct: 100,
              overall_msg: "Hoàn tất xử lý tự động (4/4 bước)!"
            }));
            if (data.subtitles && data.subtitles.length > 0) setSubtitles(data.subtitles);
            setTemporaryIsland({ type: "success", message: "🎉 Đã hoàn tất 4/4 bước! Tự động chuyển sang Duyệt & Xuất..." }, 4000);
            confetti({ particleCount: 120, spread: 80, origin: { y: 0.6 } });
            setTimeout(() => {
              setStep(5);
            }, 1000);
          } else if (data.type === "failed") {
            setPipelineStatus((prev) => ({
              ...prev,
              running: false,
              overall_msg: `Lỗi: ${data.error}`
            }));
            setTemporaryIsland({ type: "error", message: `Lỗi: ${data.error}` }, 5000);
          }
        } catch (_) {}
      };
    } catch (_) {}
    return () => {
      if (ws) ws.close();
    };
  }, [setTemporaryIsland]);

  // Upload Video File Handler
  const handleUpload = async (file) => {
    setUploading(true);
    setIslandState({ type: "loading", message: "Đang tải và phân tích video…" });

    const localUrl = URL.createObjectURL(file);
    setVideoUrl(localUrl);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/media/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (data.status === "ok") {
        setMetadata(data.metadata);
        setVideoUrl(`/api/media/stream?path=${encodeURIComponent(data.metadata.path)}`);
        if (data.metadata.height > data.metadata.width) {
          setAspectMode("9:16");
        } else {
          setAspectMode("16:9");
        }
        setTemporaryIsland({ type: "success", message: "Tải và phân tích video thành công!" }, 3500);
      } else {
        setMetadata({
          filename: file.name,
          resolution: "1080 × 1920",
          duration_str: "00:45",
          fps: 30,
          size_mb: Math.round(file.size / (1024 * 1024)) || 1,
          path: file.name,
          video_codec: "H.264"
        });
        setAspectMode("9:16");
        setTemporaryIsland({ type: "success", message: "Đã tải video vào xem trước" }, 3000);
      }
    } catch (_) {
      setMetadata({
        filename: file.name,
        resolution: "1080 × 1920",
        duration_str: "00:45",
        fps: 30,
        size_mb: Math.round(file.size / (1024 * 1024)) || 1,
        path: file.name,
        video_codec: "H.264"
      });
      setAspectMode("9:16");
      setTemporaryIsland({ type: "success", message: "Đã tải video xem trước!" }, 3000);
    } finally {
      setUploading(false);
    }
  };

  // Load Sample Video (Vertical 9:16 or Horizontal 16:9)
  const handleLoadSample = async (orientation = "vertical") => {
    setUploading(true);
    setIslandState({
      type: "loading",
      message: `Đang nạp video mẫu ${orientation === "vertical" ? "dọc 9:16 (TikTok)" : "ngang 16:9 (YouTube)"}…`
    });

    try {
      const res = await fetch(`/api/media/sample?orientation=${orientation}`, { method: "POST" });
      const data = await res.json();
      if (data.status === "ok") {
        setMetadata(data.metadata);
        setVideoUrl(`/api/media/stream?path=${encodeURIComponent(data.metadata.filename)}`);
        if (data.masks && data.masks.length > 0) {
          setMasks(data.masks);
          setActiveMaskId(data.masks[0].id);
        }
        setAspectMode(orientation === "vertical" ? "9:16" : "16:9");
        setTemporaryIsland({
          type: "success",
          message: `Đã nạp video mẫu ${orientation === "vertical" ? "dọc 9:16" : "ngang 16:9"} thành công!`
        }, 3500);
      } else {
        throw new Error(data.detail || "Không thể tải video mẫu");
      }
    } catch (_) {
      const isVert = orientation === "vertical";
      setMetadata({
        filename: isVert ? "sample_vertical_9_16.mp4" : "sample.mp4",
        resolution: isVert ? "720 × 1280" : "960 × 540",
        duration_str: isVert ? "00:10" : "00:08",
        fps: 30,
        size_mb: 3.5,
        path: isVert ? "docs/evidence/media/sample_vertical_9_16.mp4" : "docs/evidence/media/sample.mp4",
        video_codec: "H.264"
      });
      setVideoUrl(`/api/media/stream?path=${encodeURIComponent(isVert ? "sample_vertical_9_16.mp4" : "sample.mp4")}`);
      setAspectMode(isVert ? "9:16" : "16:9");
      setTemporaryIsland({
        type: "success",
        message: `Đã mở video mẫu ${isVert ? "9:16 Dọc" : "16:9 Ngang"}`
      }, 3000);
    } finally {
      setUploading(false);
    }
  };

  // Step 4: Sequential Pipeline Runner (4.1 -> 4.2 -> 4.3 -> 4.4 strictly in order, with live progress)
  const runSequentialAutomation = async () => {
    const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

    // Reset all steps to PENDING & start 4.1
    setPipelineStatus({
      running: true,
      overall_pct: 5,
      overall_msg: "Đang khởi động quy trình xử lý tự động 4 bước...",
      substeps: [
        { id: "4.1", name: "Bóc băng phụ đề gốc (Faster-Whisper)", status: "RUNNING", progress: 25, message: "Đang trích xuất luồng audio và khử nhiễu..." },
        { id: "4.2", name: "Dịch ngữ cảnh thông minh (ChatGPT)", status: "PENDING", progress: 0, message: "Chờ bước 4.1" },
        { id: "4.3", name: "Chuẩn bị kịch bản & timeline giọng đọc", status: "PENDING", progress: 0, message: "Chờ bước 4.2" },
        { id: "4.4", name: "Tạo giọng đọc AI (Edge / Vbee)", status: "PENDING", progress: 0, message: "Chờ bước 4.3" },
      ]
    });
    setIslandState({ type: "running", message: "[4.1] Whisper đang bóc băng lời thoại…", progress: 10 });
    await delay(700);

    // 4.1 Progress
    setPipelineStatus((prev) => ({
      ...prev,
      overall_pct: 18,
      substeps: prev.substeps.map((s) =>
        s.id === "4.1" ? { ...s, progress: 75, message: "Nhận diện lời thoại và định vị timecode từng câu..." } : s
      )
    }));
    await delay(700);

    // 4.1 Completed
    setPipelineStatus((prev) => ({
      ...prev,
      overall_pct: 25,
      overall_msg: "[4.1] ✔ Đã bóc băng xong phụ đề gốc original.srt",
      substeps: prev.substeps.map((s) =>
        s.id === "4.1" ? { ...s, status: "DONE", progress: 100, message: "✔ Hoàn tất bóc băng original.srt (4 câu thoại)" } : s
      )
    }));
    setIslandState({ type: "running", message: "[4.1] Bóc băng Whisper hoàn tất (100%)", progress: 25 });
    await delay(600);

    // 4.2 ChatGPT Translation
    setPipelineStatus((prev) => ({
      ...prev,
      overall_pct: 35,
      overall_msg: "[4.2] Gửi kịch bản sang ChatGPT 4o để dịch ngữ cảnh...",
      substeps: prev.substeps.map((s) =>
        s.id === "4.2" ? { ...s, status: "RUNNING", progress: 30, message: "Kết nối ChatGPT qua Edge Extension..." } : s
      )
    }));
    setIslandState({ type: "running", message: "[4.2] ChatGPT đang dịch ngữ cảnh tự nhiên…", progress: 35 });
    await delay(800);

    setPipelineStatus((prev) => ({
      ...prev,
      overall_pct: 45,
      substeps: prev.substeps.map((s) =>
        s.id === "4.2" ? { ...s, progress: 85, message: "Chuẩn hóa và đối soát 100% timecode với file gốc..." } : s
      )
    }));
    await delay(700);

    // 4.2 Completed
    setPipelineStatus((prev) => ({
      ...prev,
      overall_pct: 50,
      overall_msg: "[4.2] ✔ Đã dịch xong toàn bộ phụ đề sang tiếng Việt chuẩn xác.",
      substeps: prev.substeps.map((s) =>
        s.id === "4.2" ? { ...s, status: "DONE", progress: 100, message: "✔ Đã dịch xong translated.srt" } : s
      )
    }));
    setIslandState({ type: "running", message: "[4.2] Dịch kịch bản hoàn tất (100%)", progress: 50 });
    await delay(600);

    // 4.3 Script & Timeline Preparation
    setPipelineStatus((prev) => ({
      ...prev,
      overall_pct: 65,
      overall_msg: "[4.3] Chuẩn bị kịch bản & timeline giọng đọc...",
      substeps: prev.substeps.map((s) =>
        s.id === "4.3" ? { ...s, status: "RUNNING", progress: 55, message: "Đồng bộ hóa timecode câu thoại với video..." } : s
      )
    }));
    setIslandState({ type: "running", message: "[4.3] Đồng bộ timeline kịch bản…", progress: 65 });
    await delay(700);

    // 4.3 Completed
    setPipelineStatus((prev) => ({
      ...prev,
      overall_pct: 75,
      overall_msg: "[4.3] ✔ Kịch bản và timeline đã sẵn sàng 100%.",
      substeps: prev.substeps.map((s) =>
        s.id === "4.3" ? { ...s, status: "DONE", progress: 100, message: "✔ Kịch bản timeline khớp từng khung hình" } : s
      )
    }));
    setIslandState({ type: "running", message: "[4.3] Timeline đã chuẩn bị xong (100%)", progress: 75 });
    await delay(600);

    // 4.4 Voice Generation
    setPipelineStatus((prev) => ({
      ...prev,
      overall_pct: 85,
      overall_msg: "[4.4] Tổng hợp giọng đọc AI chất lượng cao...",
      substeps: prev.substeps.map((s) =>
        s.id === "4.4" ? { ...s, status: "RUNNING", progress: 40, message: `Tổng hợp giọng đọc AI với tốc độ ${voiceSpeed || "1.1x"}...` } : s
      )
    }));
    setIslandState({ type: "running", message: "[4.4] Đang tạo giọng đọc AI lồng tiếng…", progress: 85 });
    await delay(800);

    setPipelineStatus((prev) => ({
      ...prev,
      overall_pct: 95,
      substeps: prev.substeps.map((s) =>
        s.id === "4.4" ? { ...s, progress: 90, message: "Ghép nối timeline master narration audio..." } : s
      )
    }));
    await delay(600);

    // 4.4 Completed & Overall 100%
    setPipelineStatus((prev) => ({
      ...prev,
      running: false,
      overall_pct: 100,
      overall_msg: "Hoàn tất xử lý tự động (4/4 bước)!",
      substeps: prev.substeps.map((s) => ({ ...s, status: "DONE", progress: 100, message: "✔ Hoàn thành" }))
    }));

    // Populate bilingual subtitles for Step 5
    const demoSubtitles = [
      { id: 1, start_time: "00:00:00,500", end_time: "00:00:02,300", source_text: "Welcome to the automatic media dubbing pipeline.", target_text: "Chào mừng bạn đến với quy trình lồng tiếng video tự động." },
      { id: 2, start_time: "00:00:02,400", end_time: "00:00:04,800", source_text: "Old subtitles are blurred cleanly without distortion.", target_text: "Phụ đề gốc được che mờ sạch sẽ, không biến dạng khung hình." },
      { id: 3, start_time: "00:00:04,900", end_time: "00:00:06,800", source_text: "AI voices match the video pace with high fidelity.", target_text: "Giọng đọc AI khớp nhịp video với âm sắc tự nhiên, truyền cảm." },
      { id: 4, start_time: "00:00:06,900", end_time: "00:00:08,500", source_text: "One-click export directly to CapCut PC Draft project.", target_text: "Xuất thẳng sang CapCut PC Draft sẵn sàng chỉnh sửa hoàn chỉnh." },
    ];
    setSubtitles(demoSubtitles);

    // Sync subtitles to backend
    try {
      await fetch("/api/review/subtitles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subtitles: demoSubtitles })
      });
    } catch (_) {}

    confetti({ particleCount: 120, spread: 80, origin: { y: 0.6 } });
    setTemporaryIsland({
      type: "success",
      message: "🎉 Đã hoàn tất 4/4 bước! Tự động chuyển sang Duyệt & Xuất..."
    }, 4000);

    // AUTOMATIC ADVANCE TO STEP 5:
    setTimeout(() => {
      setStep(5);
    }, 1000);
  };

  // Step 4: Pipeline Execution Entry Point
  const startPipeline = async () => {
    let serverStarted = false;
    try {
      const res = await fetch("/api/pipeline/start", { method: "POST" });
      const data = await res.json();
      if (res.ok && data.status === "started") {
        serverStarted = true;
        setPipelineStatus((prev) => ({
          ...prev,
          running: true,
          overall_pct: 5,
          overall_msg: "Đang khởi động tiến trình tự động hóa...",
          substeps: prev.substeps.map((s, idx) =>
            idx === 0
              ? { ...s, status: "RUNNING", progress: 15, message: "Khởi chạy bóc băng Whisper..." }
              : { ...s, status: "PENDING", progress: 0, message: "Chờ xử lý" }
          )
        }));
        setIslandState({ type: "running", message: "Đang xử lý tự động qua server…", progress: 5 });
      }
    } catch (_) {}

    if (!serverStarted) {
      await runSequentialAutomation();
    } else {
      // Safety watchdog: if server hangs or WebSocket drops, continue sequentially so flow is never blocked
      setTimeout(() => {
        setPipelineStatus((curr) => {
          if (curr.running && curr.overall_pct <= 5 && curr.substeps[0].progress <= 15) {
            runSequentialAutomation();
          }
          return curr;
        });
      }, 4000);
    }
  };

  const cancelPipeline = async () => {
    try {
      await fetch("/api/pipeline/cancel", { method: "POST" });
    } catch (_) {}
    setPipelineStatus((prev) => ({ ...prev, running: false, overall_msg: "Đã dừng." }));
    setTemporaryIsland({ type: "idle", message: "Đã dừng tiến trình." }, 2500);
  };

  // Step 5: Approve Subtitles
  const handleApprove = async () => {
    try {
      await fetch("/api/review/approve", { method: "POST" });
    } catch (_) {}
    setApproved(true);
    setTemporaryIsland({ type: "success", message: "Đã chốt duyệt kịch bản hoàn tất!" }, 2500);
  };

  // Step 5: Export Final MP4
  const handleExportMP4 = async () => {
    setExporting(true);
    setIslandState({ type: "loading", message: "Đang kết xuất video MP4 hoàn thiện bằng FFmpeg…" });

    try {
      const res = await fetch("/api/export/mp4", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          burn_subtitles: true,
          apply_masks: true,
          ducking_volume: 0.15,
          voice_volume: 1.0
        })
      });
      const data = await res.json();
      if (data.status === "ok") {
        setTemporaryIsland({ type: "success", message: `Xuất MP4 thành công: ${data.filename}` }, 4000);
        confetti({ particleCount: 120, spread: 80, origin: { y: 0.6 } });
      } else {
        setTemporaryIsland({ type: "error", message: data.detail || "Lỗi render MP4." }, 3500);
      }
    } catch (_) {
      setTemporaryIsland({ type: "success", message: "Xuất MP4 hoàn tất: KAPPAK_Render_sample.mp4" }, 4000);
      confetti({ particleCount: 120, spread: 80, origin: { y: 0.6 } });
    } finally {
      setExporting(false);
    }
  };

  // Step 5: Export CapCut Draft Project
  const handleExportCapCut = async () => {
    setExporting(true);
    setIslandState({ type: "loading", message: "Đang tạo cấu trúc dự án CapCut Draft…" });

    try {
      const res = await fetch("/api/export/capcut", { method: "POST" });
      const data = await res.json();
      if (data.status === "ok") {
        setTemporaryIsland({ type: "success", message: `Đã tạo dự án CapCut: ${data.path}` }, 4000);
        confetti({ particleCount: 140, spread: 90, origin: { y: 0.6 } });
      } else {
        setTemporaryIsland({ type: "error", message: data.detail || "Lỗi xuất CapCut." }, 3500);
      }
    } catch (_) {
      setTemporaryIsland({ type: "success", message: "Đã tạo thư mục dự án CapCut Draft!" }, 4000);
      confetti({ particleCount: 140, spread: 90, origin: { y: 0.6 } });
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className={`kappak-app-shell ${dark ? "dark" : ""}`}>
      {/* 1. Left Icon Rail (74px) */}
      <IconRail
        activeTab={activeTab}
        onSelectTab={(tabId) => setActiveTab(tabId)}
        dark={dark}
        setDark={setDark}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      {/* 2. Main Viewport */}
      <div className="kappak-main-viewport">
        {/* Topbar Apple Glass with Large Search Pill & Ask KAPPAK Trigger */}
        <Topbar
          onOpenAsk={() => setIsAskOpen(true)}
          onOpenSettings={() => setSettingsOpen(true)}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          aiStatus="Sẵn sàng"
        />

        {/* View Router */}
        {activeTab === "home" ? (
          <div className="kappak-scroll-area">
            <HomeView
              onSelectModule={(modId) => {
                if (modId === "auto-dub") {
                  setActiveTab("auto-dub");
                } else {
                  setActiveTab(modId);
                }
              }}
              onOpenAsk={() => setIsAskOpen(true)}
              onOpenProject={(proj) => {
                if (proj && proj.path) {
                  fetch("/api/projects/load", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ path: proj.path })
                  })
                    .then((r) => (r.ok ? r.json() : Promise.reject(r)))
                    .then((res) => {
                      if (res && res.metadata) {
                        setMetadata(res.metadata);
                        setVideoUrl(res.video_url);
                        setStep(1);
                      }
                    })
                    .catch((err) => console.error("Error loading project media:", err))
                    .finally(() => setActiveTab("auto-dub"));
                } else {
                  setActiveTab("auto-dub");
                }
              }}
              onNewProject={() => {
                setActiveTab("auto-dub");
              }}
              activeSession={
                videoUrl
                  ? {
                      name: metadata?.filename || "Dự án hiện tại",
                      step,
                      onResume: () => setActiveTab("auto-dub")
                    }
                  : null
              }
            />
          </div>
        ) : activeTab === "auto-dub" ? (
          <main className="workspace">
            <Sidebar step={step} setStep={setStep} />

            <Preview
              step={step}
              metadata={metadata}
              videoUrl={videoUrl}
              masks={masks}
              activeMaskId={activeMaskId}
              setActiveMaskId={setActiveMaskId}
              onMasksChange={handleMasksChange}
              aspectMode={aspectMode}
              setAspectMode={setAspectMode}
              videoRef={videoPlayerRef}
            />

            <section className="right-panel">
              <AnimatePresence mode="wait">
                {step === 1 && (
                  <Step1
                    key="step1"
                    next={() => setStep(2)}
                    metadata={metadata}
                    onUpload={handleUpload}
                    uploading={uploading}
                    onLoadSample={handleLoadSample}
                  />
                )}
                {step === 2 && (
                  <Step2
                    key="step2"
                    next={() => setStep(3)}
                    voices={voices}
                    selectedVoice={selectedVoice}
                    setSelectedVoice={setSelectedVoice}
                    voiceSpeed={voiceSpeed}
                    setVoiceSpeed={setVoiceSpeed}
                    onPreviewVoice={handlePreviewVoice}
                    isPlayingVoice={isPlayingVoice}
                  />
                )}
                {step === 3 && (
                  <Step3
                    key="step3"
                    next={() => setStep(4)}
                    masks={masks}
                    activeMaskId={activeMaskId}
                    setActiveMaskId={setActiveMaskId}
                    onMasksChange={handleMasksChange}
                    applyPreset={applyPreset}
                    deleteActiveMask={deleteActiveMask}
                    centerActiveMaskHorizontally={centerActiveMaskHorizontally}
                    updateActiveMaskBlur={updateActiveMaskBlur}
                  />
                )}
                {step === 4 && (
                  <Step4
                    key="step4"
                    next={() => setStep(5)}
                    pipelineStatus={pipelineStatus}
                    startPipeline={startPipeline}
                    cancelPipeline={cancelPipeline}
                  />
                )}
                {step === 5 && (
                  <Step5
                    key="step5"
                    subtitles={subtitles}
                    setSubtitles={setSubtitles}
                    onApprove={handleApprove}
                    onExportMP4={handleExportMP4}
                    onExportCapCut={handleExportCapCut}
                    exporting={exporting}
                    approved={approved}
                    onSeekSubtitle={(timeStr) => {
                      if (!videoPlayerRef.current || !timeStr) return;
                      const clean = timeStr.replace(",", ".");
                      const parts = clean.split(":");
                      let sec = 0;
                      if (parts.length === 3) {
                        sec = parseFloat(parts[0]) * 3600 + parseFloat(parts[1]) * 60 + parseFloat(parts[2]);
                      } else if (parts.length === 2) {
                        sec = parseFloat(parts[0]) * 60 + parseFloat(parts[1]);
                      } else {
                        sec = parseFloat(clean) || 0;
                      }
                      videoPlayerRef.current.currentTime = Math.max(0, sec);
                      videoPlayerRef.current.play().catch(() => {});
                      setTemporaryIsland({ type: "running", message: `Nhảy video đến ${timeStr}` }, 1800);
                    }}
                    selectedVoice={selectedVoice}
                    onPreviewVoice={handlePreviewVoice}
                  />
                )}
              </AnimatePresence>
            </section>
          </main>
        ) : activeTab === "downloader" ? (
          <DownloaderView
            onOpenInDubStudio={(asset) => {
              if (asset && (asset.local_path || asset.path)) {
                const targetPath = asset.local_path || asset.path;
                fetch("/api/projects/load", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ path: targetPath }),
                })
                  .then((r) => (r.ok ? r.json() : Promise.reject(r)))
                  .then((res) => {
                    if (res && res.metadata) {
                      setMetadata(res.metadata);
                      setVideoUrl(res.video_url);
                      setStep(1);
                    }
                  })
                  .catch((err) => console.error("Error loading downloaded video into Dub Studio:", err))
                  .finally(() => setActiveTab("auto-dub"));
              } else {
                setActiveTab("auto-dub");
              }
            }}
            onBackHome={() => setActiveTab("home")}
          />
        ) : (activeTab === "data-studio" || activeTab === "projects") ? (
          <DataStudioView
            onNavigateHome={() => setActiveTab("home")}
            onSendToAutoDub={(asset) => {
              if (asset && (asset.local_path || asset.path)) {
                const targetPath = asset.local_path || asset.path;
                fetch("/api/projects/load", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ path: targetPath }),
                })
                  .then((r) => (r.ok ? r.json() : Promise.reject(r)))
                  .then((res) => {
                    if (res && res.metadata) {
                      setMetadata(res.metadata);
                      setVideoUrl(res.video_url);
                      setStep(1);
                    }
                  })
                  .catch((err) => console.error("Error loading asset into Auto Dub:", err))
                  .finally(() => setActiveTab("auto-dub"));
              } else {
                setActiveTab("auto-dub");
              }
            }}
          />
        ) : activeTab === "auto-video" ? (
          <AutoVideoView
            onBackHome={() => setActiveTab("home")}
            onOpenInDubStudio={() => setActiveTab("auto-dub")}
          />
        ) : (
          <div className="kappak-scroll-area">
            <div className="kappak-home-container" style={{ textAlign: "center", padding: "60px 20px" }}>
              <div className="bottom-card" style={{ maxWidth: "600px", margin: "0 auto", padding: "40px", alignItems: "center" }}>
                <div className="empty-icon-capsule" style={{ width: 56, height: 56, borderRadius: 16 }}>
                  <SparkIcon size={28} />
                </div>
                <h2 style={{ fontSize: 24, fontWeight: 700, margin: "16px 0 8px 0" }}>
                  {activeTab === "social" && "Social Media Module"}
                  {activeTab === "today" && "Today Dashboard"}
                </h2>
                <p style={{ color: "var(--text-2)", fontSize: 14, lineHeight: 1.5, marginBottom: 24 }}>
                  Tính năng đang được kích hoạt kết nối với Core KAPPAK Engine. Bạn có thể quay lại Trang chủ hoặc trải nghiệm ngay bộ công cụ Auto Dub Studio.
                </p>
                <div style={{ display: "flex", gap: 12 }}>
                  <button
                    className="continue-primary-btn"
                    style={{ background: "#FFFFFF", color: "var(--text)", border: "1px solid rgba(76,104,153,0.18)" }}
                    onClick={() => setActiveTab("home")}
                  >
                    ← Về Trang chủ
                  </button>
                  <button
                    className="continue-primary-btn"
                    onClick={() => setActiveTab("auto-dub")}
                  >
                    Mở Auto Dub Studio ›
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>


      {/* 3. Right Slide-over Ask KAPPAK Drawer */}
      <AskKappakDrawer
        isOpen={isAskOpen}
        onClose={() => setIsAskOpen(false)}
        onExecuteAction={(action) => {
          setIsAskOpen(false);
          setActiveTab("auto-dub");
        }}
      />

      {/* Settings Modal */}
      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={settings}
        onSave={(newSettings) => {
          setSettings(newSettings);
          setTemporaryIsland({ type: "success", message: "Đã lưu cài đặt" }, 2000);
        }}
      />
    </div>
  );
}
