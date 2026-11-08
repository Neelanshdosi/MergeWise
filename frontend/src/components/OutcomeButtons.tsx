"use client";

import React, { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { OutcomeType } from "@/lib/types";
import { recordIssueOutcome } from "@/lib/api";
import { GitPullRequestIcon, GitMergeIcon, CheckIcon } from "./Octicons";

interface OutcomeButtonsProps {
  repoFullName: string;
  issueNumber: number;
  issueTitle?: string;
  initialOutcome?: OutcomeType | null;
  onOutcomeChanged?: (newOutcome: OutcomeType) => void;
  primaryLanguage?: string | null;
  labels?: string[] | null;
}

const OUTCOMES: { key: OutcomeType; label: string; icon?: React.ReactNode }[] = [
  { key: "attempted", label: "Working on it" },
  { key: "pr_opened", label: "PR opened", icon: <GitPullRequestIcon size={14} /> },
  { key: "merged", label: "Merged", icon: <GitMergeIcon size={14} /> },
  { key: "too_hard", label: "Too hard" },
  { key: "skipped", label: "Skip" },
];

export const OutcomeButtons: React.FC<OutcomeButtonsProps> = ({
  repoFullName,
  issueNumber,
  issueTitle,
  initialOutcome = null,
  onOutcomeChanged,
  primaryLanguage,
  labels,
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
        setFeedbackMsg("Sign in required");
        setIsSaving(false);
        return;
      }

      await recordIssueOutcome(
        {
          repo_full_name: repoFullName,
          issue_number: issueNumber,
          issue_title: issueTitle || "",
          outcome,
          primary_language: primaryLanguage || undefined,
          labels: labels || undefined,
        },
        token
      );

      setCurrentOutcome(outcome);
      onOutcomeChanged?.(outcome);
      setFeedbackMsg("Saved!");
      setTimeout(() => setFeedbackMsg(null), 2500);
    } catch {
      setFeedbackMsg("Could not save");
      setTimeout(() => setFeedbackMsg(null), 3000);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
      <span style={{ fontSize: "12px", color: "var(--color-fg-muted)", fontWeight: 500 }}>
        Status:
      </span>
      <div className="BtnGroup" role="group" aria-label="Issue outcome status">
        {OUTCOMES.map(({ key, label, icon }) => {
          const isSelected = currentOutcome === key;
          const isDone = key === "merged" && isSelected;
          return (
            <button
              key={key}
              type="button"
              className={`BtnGroup-item btn btn-sm ${isSelected ? "selected" : ""} ${isDone ? "done" : ""}`}
              onClick={() => handleSelectOutcome(key)}
              disabled={isSaving}
              aria-pressed={isSelected}
              title={`Mark as ${label}`}
            >
              {icon}
              <span>{label}</span>
            </button>
          );
        })}
      </div>
      {feedbackMsg && (
        <span
          style={{
            fontSize: "12px",
            color: feedbackMsg.includes("Saved") ? "var(--color-success-fg)" : "var(--color-danger-fg)",
            display: "inline-flex",
            alignItems: "center",
            gap: "3px",
            fontWeight: 500,
          }}
        >
          {feedbackMsg.includes("Saved") && <CheckIcon size={12} />}
          {feedbackMsg}
        </span>
      )}
    </div>
  );
};
