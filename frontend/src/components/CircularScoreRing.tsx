"use client";

import React from "react";

interface CircularScoreRingProps {
  score: number; // 0.0 to 1.0
  size?: number; // diameter in pixels (default 34)
  strokeWidth?: number; // stroke thickness in pixels (default 3)
}

export default function CircularScoreRing({
  score,
  size = 34,
  strokeWidth = 3,
}: CircularScoreRingProps) {
  const clampedScore = Math.max(0, Math.min(1, score));
  const percent = Math.round(clampedScore * 100);

  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - clampedScore * circumference;

  // Primer token coloring
  let progressColor = "var(--color-accent-fg)";
  if (percent >= 70) {
    progressColor = "var(--color-success-fg)";
  } else if (percent < 40) {
    progressColor = "var(--color-attention-fg)";
  }

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        width: `${size}px`,
        height: `${size}px`,
        flexShrink: 0,
      }}
      title={`Match score: ${percent}%`}
      aria-label={`${percent}% match`}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ transform: "rotate(-90deg)", display: "block" }}
      >
        {/* Background track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-border-default)"
          strokeWidth={strokeWidth}
        />
        {/* Progress ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={progressColor}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.4s ease" }}
        />
      </svg>
      {/* Percentage text */}
      <span
        style={{
          position: "absolute",
          fontSize: size <= 32 ? "10px" : "11px",
          fontWeight: 700,
          color: "var(--color-fg-default)",
          lineHeight: 1,
          letterSpacing: "-0.03em",
          userSelect: "none",
        }}
      >
        {percent}%
      </span>
    </div>
  );
}

