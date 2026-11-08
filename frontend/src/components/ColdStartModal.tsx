"use client";

import React, { useState } from "react";
import { ColdStartQuestionnaire } from "@/lib/types";
import { CheckIcon } from "./Octicons";

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
    <div className="Box" style={{ marginBottom: "24px" }}>
      <div className="Box-header">
        <h3 style={{ fontSize: "14px", fontWeight: 600, color: "var(--color-fg-default)" }}>
          Preferences &amp; Focus Areas
        </h3>
        <span
          className="IssueLabel"
          style={{
            backgroundColor: "var(--color-attention-subtle)",
            color: "var(--color-attention-fg)",
            borderColor: "var(--color-attention-border)",
            fontWeight: 600,
          }}
        >
          Cold Start Customization
        </span>
      </div>

      <div className="Box-body">
        <p style={{ fontSize: "13px", color: "var(--color-fg-muted)", marginBottom: "16px" }}>
          Configure your primary languages and target stacks so MergeWise can match you with the right open-source issues.
        </p>

        <form onSubmit={handleSubmit}>
          {/* Languages */}
          <div style={{ marginBottom: "16px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--color-fg-default)", marginBottom: "8px" }}>
              Primary Languages (select at least one):
            </label>
            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
              {AVAILABLE_LANGUAGES.map((lang) => {
                const active = selectedLangs.includes(lang);
                return (
                  <button
                    type="button"
                    key={lang}
                    onClick={() => toggleItem(selectedLangs, setSelectedLangs, lang)}
                    className={`btn btn-sm ${active ? "btn-primary" : ""}`}
                    style={{ fontSize: "12px", height: "26px", padding: "0 10px" }}
                  >
                    {active && <CheckIcon size={12} />}
                    {lang}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Frameworks */}
          <div style={{ marginBottom: "16px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--color-fg-default)", marginBottom: "8px" }}>
              Frameworks &amp; Libraries:
            </label>
            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
              {AVAILABLE_FRAMEWORKS.map((fw) => {
                const active = selectedFrameworks.includes(fw);
                return (
                  <button
                    type="button"
                    key={fw}
                    onClick={() => toggleItem(selectedFrameworks, setSelectedFrameworks, fw)}
                    className={`btn btn-sm ${active ? "btn-primary" : ""}`}
                    style={{ fontSize: "12px", height: "26px", padding: "0 10px" }}
                  >
                    {active && <CheckIcon size={12} />}
                    {fw}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Areas of Interest */}
          <div style={{ marginBottom: "20px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--color-fg-default)", marginBottom: "8px" }}>
              Areas of Interest:
            </label>
            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
              {AVAILABLE_INTERESTS.map((interest) => {
                const active = selectedInterests.includes(interest);
                return (
                  <button
                    type="button"
                    key={interest}
                    onClick={() => toggleItem(selectedInterests, setSelectedInterests, interest)}
                    className={`btn btn-sm ${active ? "btn-primary" : ""}`}
                    style={{ fontSize: "12px", height: "26px", padding: "0 10px" }}
                  >
                    {active && <CheckIcon size={12} />}
                    {interest}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Action Row */}
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button type="submit" className="btn btn-primary" disabled={isLoading}>
              {isLoading ? "Finding Viable Matches..." : "Save Preferences & Find Issues →"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
