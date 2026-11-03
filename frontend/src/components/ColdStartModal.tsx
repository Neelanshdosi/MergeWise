"use client";

import React, { useState } from "react";
import { ColdStartQuestionnaire } from "@/lib/types";

interface ColdStartModalProps {
  onComplete: (answers: ColdStartQuestionnaire) => void;
  isLoading: boolean;
}

const AVAILABLE_LANGUAGES = ["TypeScript", "JavaScript", "Python", "Go", "Rust", "Java", "C++", "PHP"];
const AVAILABLE_FRAMEWORKS = ["React", "Next.js", "FastAPI", "Node.js", "Express", "TailwindCSS", "Django", "Vue", "Spring"];
const AVAILABLE_INTERESTS = ["Developer Tools", "Web Applications", "CLI & Automation", "AI / Machine Learning", "Backend APIs"];

export default function ColdStartModal({ onComplete, isLoading }: ColdStartModalProps) {
  const [selectedLangs, setSelectedLangs] = useState<string[]>(["TypeScript"]);
  const [selectedFrameworks, setSelectedFrameworks] = useState<string[]>(["React"]);
  const [selectedInterests, setSelectedInterests] = useState<string[]>(["Developer Tools"]);
  const [hours, setHours] = useState<number>(5);
  const [experienceLevel, setExperienceLevel] = useState<string>("intermediate");

  const toggleItem = (list: string[], setList: (val: string[]) => void, item: string) => {
    if (list.includes(item)) {
      if (list.length > 1) {
        setList(list.filter((x) => x !== item));
      }
    } else {
      setList([...list, item]);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onComplete({
      languages: selectedLangs,
      frameworks: selectedFrameworks,
      interests: selectedInterests,
      hours_per_week: hours,
      experience_level: experienceLevel,
    });
  };

  return (
    <div className="glass-panel" style={{ padding: "32px", maxWidth: "700px", margin: "0 auto", marginBottom: "40px" }}>
      <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", padding: "4px 12px", borderRadius: "9999px", background: "rgba(245, 158, 11, 0.15)", border: "1px solid rgba(245, 158, 11, 0.3)", color: "var(--warning)", fontSize: "0.8rem", marginBottom: "16px" }}>
        <span>⚡</span> Cold Start: Set Your Focus
      </div>

      <h2 style={{ fontSize: "1.6rem", fontWeight: 700, marginBottom: "8px" }}>
        Tell MergeWise What You Want to Work On
      </h2>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem", marginBottom: "24px" }}>
        Your GitHub account has limited public activity. Select your primary languages and target stacks so we can match you with the right open-source issues.
      </p>

      <form onSubmit={handleSubmit}>
        {/* Languages */}
        <div style={{ marginBottom: "20px" }}>
          <label style={{ display: "block", fontSize: "0.9rem", fontWeight: 600, marginBottom: "8px" }}>
            Primary Languages (select at least one):
          </label>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {AVAILABLE_LANGUAGES.map((lang) => {
              const active = selectedLangs.includes(lang);
              return (
                <button
                  type="button"
                  key={lang}
                  onClick={() => toggleItem(selectedLangs, setSelectedLangs, lang)}
                  style={{
                    padding: "6px 14px",
                    borderRadius: "9999px",
                    fontSize: "0.85rem",
                    cursor: "pointer",
                    border: active ? "1px solid var(--accent-primary)" : "1px solid var(--border-color)",
                    backgroundColor: active ? "rgba(99, 102, 241, 0.25)" : "rgba(255, 255, 255, 0.04)",
                    color: active ? "#c7d2fe" : "var(--text-secondary)",
                    fontWeight: active ? 600 : 400,
                  }}
                >
                  {active ? "✓ " : ""}{lang}
                </button>
              );
            })}
          </div>
        </div>

        {/* Frameworks */}
        <div style={{ marginBottom: "20px" }}>
          <label style={{ display: "block", fontSize: "0.9rem", fontWeight: 600, marginBottom: "8px" }}>
            Frameworks & Libraries:
          </label>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {AVAILABLE_FRAMEWORKS.map((fw) => {
              const active = selectedFrameworks.includes(fw);
              return (
                <button
                  type="button"
                  key={fw}
                  onClick={() => toggleItem(selectedFrameworks, setSelectedFrameworks, fw)}
                  style={{
                    padding: "6px 14px",
                    borderRadius: "9999px",
                    fontSize: "0.85rem",
                    cursor: "pointer",
                    border: active ? "1px solid var(--accent-primary)" : "1px solid var(--border-color)",
                    backgroundColor: active ? "rgba(99, 102, 241, 0.25)" : "rgba(255, 255, 255, 0.04)",
                    color: active ? "#c7d2fe" : "var(--text-secondary)",
                    fontWeight: active ? 600 : 400,
                  }}
                >
                  {active ? "✓ " : ""}{fw}
                </button>
              );
            })}
          </div>
        </div>

        {/* Areas of Interest */}
        <div style={{ marginBottom: "24px" }}>
          <label style={{ display: "block", fontSize: "0.9rem", fontWeight: 600, marginBottom: "8px" }}>
            Areas of Interest:
          </label>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {AVAILABLE_INTERESTS.map((interest) => {
              const active = selectedInterests.includes(interest);
              return (
                <button
                  type="button"
                  key={interest}
                  onClick={() => toggleItem(selectedInterests, setSelectedInterests, interest)}
                  style={{
                    padding: "6px 14px",
                    borderRadius: "9999px",
                    fontSize: "0.85rem",
                    cursor: "pointer",
                    border: active ? "1px solid var(--accent-primary)" : "1px solid var(--border-color)",
                    backgroundColor: active ? "rgba(99, 102, 241, 0.25)" : "rgba(255, 255, 255, 0.04)",
                    color: active ? "#c7d2fe" : "var(--text-secondary)",
                    fontWeight: active ? 600 : 400,
                  }}
                >
                  {active ? "✓ " : ""}{interest}
                </button>
              );
            })}
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button type="submit" className="btn-primary" disabled={isLoading}>
            {isLoading ? "Finding Viable Matches..." : "Save Preferences & Find Issues →"}
          </button>
        </div>
      </form>
    </div>
  );
}
