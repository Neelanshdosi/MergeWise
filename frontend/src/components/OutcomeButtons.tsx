"use client";

import React, { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { OutcomeType } from "@/lib/types";
import { recordIssueOutcome } from "@/lib/api";

interface OutcomeButtonsProps {
  repoFullName: string;
  issueNumber: number;
  issueTitle?: string;
  initialOutcome?: OutcomeType | null;
  onOutcomeChanged?: (newOutcome: OutcomeType) => void;
}

const OUTCOME_CONFIG: {
  key: OutcomeType;
  label: string;
  icon: string;
  activeColor: string;
  activeBg: string;
}[] = [
  {
    key: "attempted",
    label: "Working on it",
    icon: "🔨",
    activeColor: "#60a5fa",
    activeBg: "rgba(96, 165, 250, 0.15)",
  },
  {
    key: "pr_opened",
    label: "PR Opened",
    icon: "🚀",
    activeColor: "#a78bfa",
    activeBg: "rgba(167, 139, 250, 0.15)",
  },
  {
    key: "merged",
    label: "Merged! 🎉",
    icon: "🟣",
    activeColor: "#34d399",
    activeBg: "rgba(52, 211, 153, 0.15)",
  },
  {
    key: "too_hard",
    label: "Too Hard",
    icon: "😅",
    activeColor: "#fbbf24",
    activeBg: "rgba(251, 191, 36, 0.15)",
  },
  {
    key: "skipped",
    label: "Skip",
    icon: "⏭️",
    activeColor: "#9ca3af",
    activeBg: "rgba(156, 163, 175, 0.15)",
  },
];

export const OutcomeButtons: React.FC<OutcomeButtonsProps> = ({
  repoFullName,
  issueNumber,
  issueTitle,
  initialOutcome = null,
  onOutcomeChanged,
}) => {
  const { getToken } = useAuth();
  const [currentOutcome, setCurrentOutcome] = useState<OutcomeType | null>(initialOutcome);
  const [isSaving, setIsSaving] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  const handleSelectOutcome = async (outcome: OutcomeType) => {
    if (isSaving || outcome === currentOutcome) return;

    setIsSaving(true);
    setFeedbackMsg(null);

    try {
      const token = await getToken();
      if (!token) {
        setFeedbackMsg("Sign in to save outcome");
        setIsSaving(false);
        return;
      }

      await recordIssueOutcome(
        {
          repo_full_name: repoFullName,
          issue_number: issueNumber,
          issue_title: issueTitle || "",
          outcome,
        },
        token
      );

      setCurrentOutcome(outcome);
      onOutcomeChanged?.(outcome);
      setFeedbackMsg("Saved!");
      setTimeout(() => setFeedbackMsg(null), 2500);
    } catch (err: any) {
      setFeedbackMsg("Could not save outcome");
      setTimeout(() => setFeedbackMsg(null), 3000);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "6px",
          alignItems: "center",
        }}
      >
        <span
          style={{
            fontSize: "0.72rem",
            color: "var(--text-muted)",
            marginRight: "4px",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          Outcome:
        </span>
        {OUTCOME_CONFIG.map((cfg) => {
          const isActive = currentOutcome === cfg.key;
          return (
            <button
              key={cfg.key}
              onClick={() => handleSelectOutcome(cfg.key)}
              disabled={isSaving}
              style={{
                fontSize: "0.75rem",
                padding: "3px 8px",
                borderRadius: "14px",
                border: isActive
                  ? `1px solid ${cfg.activeColor}`
                  : "1px solid rgba(255, 255, 255, 0.1)",
                backgroundColor: isActive ? cfg.activeBg : "rgba(255, 255, 255, 0.03)",
                color: isActive ? cfg.activeColor : "var(--text-secondary)",
                fontWeight: isActive ? 600 : 400,
                cursor: isSaving ? "not-allowed" : "pointer",
                transition: "all 0.15s ease",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
              }}
              title={`Mark as ${cfg.label}`}
            >
              <span>{cfg.icon}</span>
              <span>{cfg.label}</span>
            </button>
          );
        })}
      </div>
      {feedbackMsg && (
        <span
          style={{
            fontSize: "0.7rem",
            color: feedbackMsg.includes("Saved") ? "var(--success)" : "#fca5a5",
            fontStyle: "italic",
          }}
        >
          {feedbackMsg}
        </span>
      )}
    </div>
  );
};

