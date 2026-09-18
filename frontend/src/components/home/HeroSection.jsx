import React from "react";
import { motion } from "framer-motion";
import { SparkIcon, ChevronRightIcon } from "../../icons.jsx";

export default function HeroSection({ onStartExploring }) {
  return (
    <section className="kappak-hero-card">
      {/* Decorative Handwritten Ambient Background on Left */}
      <div className="hero-handwritten-left" aria-hidden="true">
        <span>Good</span>
        <span>Ideas</span>
        <span className="script-sub">Better Videos</span>
      </div>

      {/* Left Content Column (~52%) */}
      <div className="hero-content-left">
        <div className="hero-eyebrow">K A P P A K &nbsp; S T U D I O &nbsp; W E B &nbsp; V 2</div>
        <h1 className="hero-headline">
          Biến ý tưởng thành<br />
          những video <span className="hero-text-accent">tuyệt vời</span>
        </h1>
        <p className="hero-subheading">
          Sức mạnh AI cho sáng tạo nội dung đa phương tiện.<br />
          Nhanh hơn. Đơn giản hơn. Hiệu quả hơn mỗi ngày.
        </p>

        <div className="hero-actions">
          <motion.button
            whileHover={{ scale: 1.02, x: 2 }}
            whileTap={{ scale: 0.98 }}
            className="hero-cta-pill"
            onClick={onStartExploring}
          >
            <SparkIcon size={16} className="cta-spark" />
            <span>Sáng tạo không giới hạn, với AI đồng hành.</span>
            <span className="cta-arrow">›</span>
          </motion.button>
        </div>
      </div>

      {/* Right Visual Column (~48%) with Asian Female Creator */}
      <div className="hero-visual-right">
        <div className="hero-model-container">
          <img
            src="/kappak/hero_female_creator.png"
            alt="KAPPAK Female Creator Hero"
            className="hero-model-img"
          />
        </div>
      </div>
    </section>
  );
}
