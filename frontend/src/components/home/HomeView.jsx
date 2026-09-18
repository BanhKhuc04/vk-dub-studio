import React from "react";
import HeroSection from "./HeroSection.jsx";
import ModuleStrip from "./ModuleStrip.jsx";
import RecentProjectsSection from "./RecentProjectsSection.jsx";
import ContinueWorkSection from "./ContinueWorkSection.jsx";
import AISuggestionSection from "./AISuggestionSection.jsx";
import HomeFooter from "./HomeFooter.jsx";

export default function HomeView({
  onSelectModule,
  onOpenAsk,
  onOpenProject,
  onNewProject,
  activeSession
}) {
  return (
    <div className="kappak-home-container">
      {/* 1. Hero Banner with Asian Female Creator Visual */}
      <HeroSection onStartExploring={() => onSelectModule && onSelectModule("auto-dub")} />

      {/* 2. Module Cards Strip (6 Pastel Glass Cards) */}
      <ModuleStrip onSelectModule={onSelectModule} />

      {/* 3. Bottom 3-Column Content Row */}
      <section className="kappak-bottom-grid" aria-label="Khu vực tác vụ nhanh">
        {/* Recent Projects (~52% width) */}
        <RecentProjectsSection
          onOpenProject={onOpenProject}
          onShowAll={() => onSelectModule && onSelectModule("projects")}
        />

        {/* Continue Work (~24% width) */}
        <ContinueWorkSection
          onNewProject={onNewProject}
          activeSession={activeSession}
        />

        {/* AI Suggestion (~24% width) */}
        <AISuggestionSection onTryAI={onOpenAsk} />
      </section>

      {/* 4. Elegant Minimalist Footer */}
      <HomeFooter />
    </div>
  );
}
