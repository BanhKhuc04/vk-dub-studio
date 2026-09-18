import React, { useState, useEffect, useRef, useCallback } from "react";

/**
 * InteractiveCanvas Component for KAPPAK Studio Web v2
 * 
 * Features:
 * - Letterbox / Pillarbox aspect ratio compensation matching the rendered video box
 * - Mouse / Pointer draw new blur rectangle
 * - Drag to move existing rectangle with boundary clamping
 * - 8-handle resize (nw, ne, se, sw, n, s, e, w) with anti-inversion & min-size clamping
 * - Real-time CSS backdrop-filter: blur(...) preview directly over the video frame
 * - Normalization to [0.0, 1.0] coordinates matching backend domain
 * - Stops propagation to prevent video play/pause collisions
 */

const RESIZE_HANDLES = [
  { id: "nw", cursor: "nwse-resize", style: { top: -5, left: -5 } },
  { id: "n",  cursor: "ns-resize",   style: { top: -5, left: "50%", transform: "translateX(-50%)" } },
  { id: "ne", cursor: "nesw-resize", style: { top: -5, right: -5 } },
  { id: "e",  cursor: "ew-resize",   style: { top: "50%", right: -5, transform: "translateY(-50%)" } },
  { id: "se", cursor: "nwse-resize", style: { bottom: -5, right: -5 } },
  { id: "s",  cursor: "ns-resize",   style: { bottom: -5, left: "50%", transform: "translateX(-50%)" } },
  { id: "sw", cursor: "nesw-resize", style: { bottom: -5, left: -5 } },
  { id: "w",  cursor: "ew-resize",   style: { top: "50%", left: -5, transform: "translateY(-50%)" } },
];

export default function InteractiveCanvas({
  videoRef,
  containerRef,
  masks = [],
  activeMaskId,
  setActiveMaskId,
  onMasksChange,
  enabled = true,
  videoAspectRatio = null, // e.g. { width: 16, height: 9 }
}) {
  const canvasRef = useRef(null);
  const [renderBox, setRenderBox] = useState({ width: 0, height: 0, left: 0, top: 0 });
  const [interaction, setInteraction] = useState(null); 
  // interaction: { mode: 'drawing' | 'dragging' | 'resizing', ...params }

  // 1. Calculate Rendered Video Box (Letterbox / Pillarbox Compensation)
  const computeRenderBox = useCallback(() => {
    if (!containerRef?.current) return;
    const containerRect = containerRef.current.getBoundingClientRect();
    const contW = containerRect.width;
    const contH = containerRect.height;
    if (contW <= 0 || contH <= 0) return;

    let vidW = videoRef?.current?.videoWidth || 0;
    let vidH = videoRef?.current?.videoHeight || 0;

    if (!vidW || !vidH) {
      if (videoAspectRatio?.width && videoAspectRatio?.height) {
        vidW = videoAspectRatio.width;
        vidH = videoAspectRatio.height;
      } else {
        // Fallback standard 16:9
        vidW = 16;
        vidH = 9;
      }
    }

    const contAR = contW / contH;
    const vidAR = vidW / vidH;

    let rendW = contW;
    let rendH = contH;
    let offX = 0;
    let offY = 0;

    if (contAR >= vidAR) {
      // Container is wider than video -> Pillarbox (bars left & right)
      rendH = contH;
      rendW = contH * vidAR;
      offX = (contW - rendW) / 2;
      offY = 0;
    } else {
      // Container is taller than video -> Letterbox (bars top & bottom)
      rendW = contW;
      rendH = contW / vidAR;
      offX = 0;
      offY = (contH - rendH) / 2;
    }

    setRenderBox({
      width: Math.round(rendW),
      height: Math.round(rendH),
      left: Math.round(offX),
      top: Math.round(offY),
    });
  }, [containerRef, videoRef, videoAspectRatio]);

  // Recalculate on mount, window resize, container resize, and video metadata loaded
  useEffect(() => {
    computeRenderBox();

    const videoEl = videoRef?.current;
    if (videoEl) {
      videoEl.addEventListener("loadedmetadata", computeRenderBox);
      videoEl.addEventListener("resize", computeRenderBox);
    }

    const containerEl = containerRef?.current;
    let resizeObserver = null;
    if (containerEl && typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(() => computeRenderBox());
      resizeObserver.observe(containerEl);
    }

    window.addEventListener("resize", computeRenderBox);
    return () => {
      if (videoEl) {
        videoEl.removeEventListener("loadedmetadata", computeRenderBox);
        videoEl.removeEventListener("resize", computeRenderBox);
      }
      if (resizeObserver) resizeObserver.disconnect();
      window.removeEventListener("resize", computeRenderBox);
    };
  }, [computeRenderBox, containerRef, videoRef]);

  // Keyboard shortcut: Delete active mask on Delete / Backspace
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!enabled || !activeMaskId) return;
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") {
        return;
      }
      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        const updated = masks.filter((m) => m.id !== activeMaskId);
        onMasksChange(updated);
        setActiveMaskId(updated.length > 0 ? updated[0].id : null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [enabled, activeMaskId, masks, onMasksChange, setActiveMaskId]);

  // Helper to convert client coordinates to normalized coordinates inside renderBox
  const getNormalizedPoint = useCallback((clientX, clientY) => {
    if (!canvasRef.current || renderBox.width <= 0 || renderBox.height <= 0) {
      return { x: 0, y: 0 };
    }
    const canvasRect = canvasRef.current.getBoundingClientRect();
    const localX = clientX - canvasRect.left;
    const localY = clientY - canvasRect.top;
    return {
      x: Math.max(0, Math.min(1, localX / renderBox.width)),
      y: Math.max(0, Math.min(1, localY / renderBox.height)),
    };
  }, [renderBox]);

  // --- 2. DRAWING NEW MASK ---
  const handleCanvasPointerDown = (e) => {
    if (!enabled) return;
    // Only primary mouse click
    if (e.button !== 0) return;
    e.stopPropagation();

    const pt = getNormalizedPoint(e.clientX, e.clientY);
    setInteraction({
      mode: "drawing",
      startX: pt.x,
      startY: pt.y,
      currX: pt.x,
      currY: pt.y,
      pointerId: e.pointerId,
    });
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch (_) {}
  };

  // --- 3. DRAGGING EXISTING MASK ---
  const handleMaskPointerDown = (e, mask) => {
    if (!enabled) return;
    if (e.button !== 0) return;
    e.stopPropagation();

    setActiveMaskId(mask.id);
    const pt = getNormalizedPoint(e.clientX, e.clientY);

    setInteraction({
      mode: "dragging",
      maskId: mask.id,
      startClickX: pt.x,
      startClickY: pt.y,
      initialMaskX: mask.x,
      initialMaskY: mask.y,
      maskW: mask.width,
      maskH: mask.height,
      pointerId: e.pointerId,
    });
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch (_) {}
  };

  // --- 4. 8-HANDLE RESIZING ---
  const handleResizePointerDown = (e, mask, handleId) => {
    if (!enabled) return;
    if (e.button !== 0) return;
    e.stopPropagation();

    setActiveMaskId(mask.id);
    const pt = getNormalizedPoint(e.clientX, e.clientY);

    setInteraction({
      mode: "resizing",
      handle: handleId,
      maskId: mask.id,
      startPt: pt,
      initialMask: { ...mask },
      pointerId: e.pointerId,
    });
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch (_) {}
  };

  // --- POINTER MOVE DISPATCHER ---
  const handlePointerMove = (e) => {
    if (!interaction) return;
    e.stopPropagation();

    const pt = getNormalizedPoint(e.clientX, e.clientY);

    if (interaction.mode === "drawing") {
      setInteraction((prev) => (prev ? { ...prev, currX: pt.x, currY: pt.y } : null));
    } else if (interaction.mode === "dragging") {
      const deltaX = pt.x - interaction.startClickX;
      const deltaY = pt.y - interaction.startClickY;

      const newX = Math.max(0, Math.min(1 - interaction.maskW, interaction.initialMaskX + deltaX));
      const newY = Math.max(0, Math.min(1 - interaction.maskH, interaction.initialMaskY + deltaY));

      const updated = masks.map((m) =>
        m.id === interaction.maskId
          ? { ...m, x: Math.round(newX * 1000) / 1000, y: Math.round(newY * 1000) / 1000 }
          : m
      );
      onMasksChange(updated);
    } else if (interaction.mode === "resizing") {
      const { handle, initialMask, startPt } = interaction;
      const deltaX = pt.x - startPt.x;
      const deltaY = pt.y - startPt.y;

      const minW = 0.02;
      const minH = 0.02;

      let newX = initialMask.x;
      let newY = initialMask.y;
      let newW = initialMask.width;
      let newH = initialMask.height;

      // Handle calculations with strict anti-inversion and boundary clamping
      if (handle.includes("w")) {
        newX = Math.min(initialMask.x + initialMask.width - minW, Math.max(0, initialMask.x + deltaX));
        newW = initialMask.width + (initialMask.x - newX);
      }
      if (handle.includes("e")) {
        newW = Math.max(minW, Math.min(1 - initialMask.x, initialMask.width + deltaX));
      }
      if (handle.includes("n")) {
        newY = Math.min(initialMask.y + initialMask.height - minH, Math.max(0, initialMask.y + deltaY));
        newH = initialMask.height + (initialMask.y - newY);
      }
      if (handle.includes("s")) {
        newH = Math.max(minH, Math.min(1 - initialMask.y, initialMask.height + deltaY));
      }

      const updated = masks.map((m) =>
        m.id === interaction.maskId
          ? {
              ...m,
              x: Math.round(newX * 1000) / 1000,
              y: Math.round(newY * 1000) / 1000,
              width: Math.round(newW * 1000) / 1000,
              height: Math.round(newH * 1000) / 1000,
            }
          : m
      );
      onMasksChange(updated);
    }
  };

  // --- POINTER UP DISPATCHER ---
  const handlePointerUp = (e) => {
    if (!interaction) return;
    e.stopPropagation();

    if (interaction.mode === "drawing") {
      const { startX, startY, currX, currY } = interaction;
      const normLeft = Math.min(startX, currX);
      const normTop = Math.min(startY, currY);
      const normW = Math.abs(currX - startX);
      const normH = Math.abs(currY - startY);

      // Only create if rectangle exceeds minimum threshold
      if (normW >= 0.02 && normH >= 0.02) {
        const newMask = {
          id: `mask_${Date.now()}`,
          label: `Vùng ${masks.length + 1}`,
          x: Math.round(normLeft * 1000) / 1000,
          y: Math.round(normTop * 1000) / 1000,
          width: Math.round(normW * 1000) / 1000,
          height: Math.round(normH * 1000) / 1000,
          blur: 16,
          mask_type: "erase",
        };
        const updated = [...masks, newMask];
        onMasksChange(updated);
        setActiveMaskId(newMask.id);
      }
    }

    try {
      if (interaction.pointerId !== undefined) {
        e.currentTarget.releasePointerCapture?.(interaction.pointerId);
      }
    } catch (_) {}

    setInteraction(null);
  };

  // Drawing preview rect
  const drawingRect =
    interaction?.mode === "drawing"
      ? {
          left: `${Math.min(interaction.startX, interaction.currX) * 100}%`,
          top: `${Math.min(interaction.startY, interaction.currY) * 100}%`,
          width: `${Math.abs(interaction.currX - interaction.startX) * 100}%`,
          height: `${Math.abs(interaction.currY - interaction.startY) * 100}%`,
        }
      : null;

  if (renderBox.width <= 0 || renderBox.height <= 0) {
    return null;
  }

  return (
    <div
      ref={canvasRef}
      className="interactive-canvas-overlay"
      style={{
        position: "absolute",
        left: `${renderBox.left}px`,
        top: `${renderBox.top}px`,
        width: `${renderBox.width}px`,
        height: `${renderBox.height}px`,
        pointerEvents: enabled ? "auto" : "none",
        cursor: enabled ? (interaction ? "crosshair" : "crosshair") : "default",
        userSelect: "none",
        zIndex: 20,
      }}
      onPointerDown={handleCanvasPointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
    >
      {/* Existing Masks */}
      {masks.map((mask) => {
        const isActive = mask.id === activeMaskId;
        const blurSigma = mask.blur ?? 16;

        return (
          <div
            key={mask.id}
            className={`interactive-mask-box ${isActive ? "active" : ""}`}
            style={{
              position: "absolute",
              left: `${mask.x * 100}%`,
              top: `${mask.y * 100}%`,
              width: `${mask.width * 100}%`,
              height: `${mask.height * 100}%`,
              backdropFilter: `blur(${blurSigma}px)`,
              WebkitBackdropFilter: `blur(${blurSigma}px)`,
              cursor: enabled ? "move" : "default",
              pointerEvents: enabled ? "auto" : "none",
            }}
            onPointerDown={(e) => handleMaskPointerDown(e, mask)}
          >
            {/* Mask Label & Info Pill */}
            <div className="mask-badge" onPointerDown={(e) => e.stopPropagation()}>
              <span className="mask-badge-title">{mask.label || "Vùng làm mờ"}</span>
              <span className="mask-badge-meta">
                {Math.round(mask.width * 100)}% × {Math.round(mask.height * 100)}%
              </span>
              {isActive && enabled && (
                <button
                  type="button"
                  className="mask-badge-delete"
                  title="Xóa vùng làm mờ (Phím Delete)"
                  onClick={(e) => {
                    e.stopPropagation();
                    const updated = masks.filter((m) => m.id !== mask.id);
                    onMasksChange(updated);
                    setActiveMaskId(updated.length > 0 ? updated[0].id : null);
                  }}
                >
                  ×
                </button>
              )}
            </div>

            {/* 8 Resize Handles on Active Mask */}
            {isActive && enabled && (
              <>
                {RESIZE_HANDLES.map((h) => (
                  <div
                    key={h.id}
                    className={`mask-handle handle-${h.id}`}
                    style={{
                      position: "absolute",
                      cursor: h.cursor,
                      ...h.style,
                    }}
                    onPointerDown={(e) => handleResizePointerDown(e, mask, h.id)}
                  />
                ))}
              </>
            )}
          </div>
        );
      })}

      {/* Real-time Drawing Box Preview */}
      {drawingRect && (
        <div
          className="interactive-mask-box drawing"
          style={{
            position: "absolute",
            ...drawingRect,
            backdropFilter: "blur(14px)",
            WebkitBackdropFilter: "blur(14px)",
            pointerEvents: "none",
          }}
        >
          <div className="mask-badge drawing">
            <span>Đang vẽ vùng che…</span>
          </div>
        </div>
      )}
    </div>
  );
}
