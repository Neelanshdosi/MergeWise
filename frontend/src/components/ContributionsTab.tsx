"use client";

import React from "react";
import { ContributionsResponse, ContributionItem } from "@/lib/types";
import {
  GitMergeIcon,
  GitPullRequestIcon,
  GitPullRequestClosedIcon,
  StarIcon,
  SyncIcon,
  AlertIcon,
  IssueOpenedIcon,
  RepoIcon,
} from "./Octicons";

interface ContributionsTabProps {
  data: ContributionsResponse | null;
  loading: boolean;
  onRefresh: () => void;
  onSwitchToRecommended: () => void;
}

function formatDate(isoStr?: string | null): string {
  if (!isoStr) return "";
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return isoStr;
  }
}

export default function ContributionsTab({
  data,
  loading,
  onRefresh,
  onSwitchToRecommended,
}: ContributionsTabProps) {
  const summary = data?.summary || {
    merged_count: 0,
    open_count: 0,
    closed_count: 0,
    repo_count: 0,
  };

  const items = data?.items || [];
  const rateLimitNotice = data?.rate_limit_notice;

  return (
    <div>
      {/* Rate limit warning banner if active */}
      {rateLimitNotice && (
        <div className="Flash Flash--warning" style={{ marginBottom: "16px" }}>
          <AlertIcon size={16} />
          <div>
            <strong>GitHub Rate Limit Notice:</strong> {rateLimitNotice}
          </div>
        </div>
      )}

      {/* Stats Summary Row (Primer Style) */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          gap: "12px",
          marginBottom: "16px",
        }}
      >
        <div className="Box" style={{ padding: "14px 16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--color-done-fg)", marginBottom: "4px" }}>
            <GitMergeIcon size={16} />
            <span style={{ fontSize: "12px", fontWeight: 600 }}>Merged PRs</span>
          </div>
          <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--color-fg-default)" }}>
            {summary.merged_count}
          </div>
        </div>

        <div className="Box" style={{ padding: "14px 16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--color-success-fg)", marginBottom: "4px" }}>
            <GitPullRequestIcon size={16} />
            <span style={{ fontSize: "12px", fontWeight: 600 }}>Open PRs</span>
          </div>
          <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--color-fg-default)" }}>
            {summary.open_count}
          </div>
        </div>

        <div className="Box" style={{ padding: "14px 16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--color-accent-fg)", marginBottom: "4px" }}>
            <RepoIcon size={16} />
            <span style={{ fontSize: "12px", fontWeight: 600 }}>Repositories</span>
          </div>
          <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--color-fg-default)" }}>
            {summary.repo_count}
          </div>
        </div>

        {summary.closed_count > 0 && (
          <div className="Box" style={{ padding: "14px 16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--color-fg-muted)", marginBottom: "4px" }}>
              <GitPullRequestClosedIcon size={16} />
              <span style={{ fontSize: "12px", fontWeight: 600 }}>Closed</span>
            </div>
            <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--color-fg-muted)" }}>
              {summary.closed_count}
            </div>
          </div>
        )}
      </div>

      {/* Contributions Box in Primer Issue-List Style */}
      <div className="Box">
        {/* Header */}
        <div className="Box-header">
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <GitPullRequestIcon size={16} color="var(--color-done-fg)" />
            <span style={{ fontWeight: 600, fontSize: "14px", color: "var(--color-fg-default)" }}>
              {items.length > 0 ? `${items.length} public contributions` : "Open-source contributions"}
            </span>
          </div>

          <button
            onClick={onRefresh}
            disabled={loading}
            className="btn btn-sm"
            title="Refresh open-source contributions from GitHub"
          >
            <SyncIcon size={13} />
            <span>{loading ? "Checking..." : "Refresh"}</span>
          </button>
        </div>

        {/* Skeleton Loading State */}
        {loading && !data && (
          <div>
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="Box-row" style={{ display: "flex", gap: "12px", alignItems: "center" }}>
                <div className="SkeletonBar" style={{ width: "16px", height: "16px", borderRadius: "50%", flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <div className="SkeletonBar" style={{ width: "65%", height: "16px", marginBottom: "8px" }} />
                  <div className="SkeletonBar" style={{ width: "40%", height: "12px" }} />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Populated List of Contributions */}
        {!loading && items.length > 0 && (
          <div>
            {items.map((item, idx) => {
              const repoOwner = item.repo.includes("/") ? item.repo.split("/")[0] : "github";
              const avatarUrl = item.repo_owner_avatar_url || `https://github.com/${repoOwner}.png?size=40`;

              return (
                <div
                  key={`${item.repo}-${item.number}-${idx}`}
                  className="Box-row"
                  style={{
                    display: "flex",
                    gap: "12px",
                    alignItems: "flex-start",
                    padding: "14px 16px",
                  }}
                >
                  {/* PR State Icon */}
                  <div style={{ marginTop: "2px", flexShrink: 0 }}>
                    {item.state === "merged" ? (
                      <div title="Merged pull request">
                        <GitMergeIcon size={18} color="var(--color-done-fg)" />
                      </div>
                    ) : item.state === "open" ? (
                      <div title="Open pull request">
                        <GitPullRequestIcon size={18} color="var(--color-success-fg)" />
                      </div>
                    ) : (
                      <div title="Closed pull request">
                        <GitPullRequestClosedIcon size={18} color="var(--color-danger-fg)" />
                      </div>
                    )}
                  </div>

                  {/* PR Details */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "6px 8px", marginBottom: "4px" }}>
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          fontSize: "14px",
                          fontWeight: 600,
                          color: "var(--color-fg-default)",
                          lineHeight: 1.35,
                          wordBreak: "break-word",
                        }}
                      >
                        {item.title}
                      </a>

                      {/* via MergeWise Pill */}
                      {item.via_mergewise && (
                        <span
                          className="IssueLabel IssueLabel--good-first"
                          style={{
                            fontSize: "11px",
                            fontWeight: 600,
                            padding: "1px 8px",
                            borderRadius: "12px",
                          }}
                          title="Matched an issue or plan you worked on via MergeWise"
                        >
                          ✦ via MergeWise
                        </span>
                      )}
                    </div>

                    {/* Metadata line: owner/repo #number, owner avatar, stars, date */}
                    <div
                      style={{
                        fontSize: "12px",
                        color: "var(--color-fg-muted)",
                        display: "flex",
                        flexWrap: "wrap",
                        alignItems: "center",
                        gap: "8px 12px",
                      }}
                    >
                      <div style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                        <img
                          src={avatarUrl}
                          alt={repoOwner}
                          width={16}
                          height={16}
                          style={{
                            borderRadius: "50%",
                            flexShrink: 0,
                            border: "1px solid var(--color-border-default)",
                          }}
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = "none";
                          }}
                        />
                        <span style={{ fontWeight: 500, color: "var(--color-fg-default)" }}>
                          {item.repo} #{item.number}
                        </span>
                      </div>

                      {item.stars > 0 && (
                        <span style={{ display: "inline-flex", alignItems: "center", gap: "3px" }}>
                          <StarIcon size={13} color="var(--color-fg-muted)" />
                          {item.stars.toLocaleString()}
                        </span>
                      )}

                      <span>
                        {item.state === "merged" && item.merged_at
                          ? `merged on ${formatDate(item.merged_at)}`
                          : item.created_at
                          ? `opened on ${formatDate(item.created_at)}`
                          : "contributed"}
                      </span>
                    </div>
                  </div>

                  {/* Right Action */}
                  <div style={{ flexShrink: 0 }}>
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-sm"
                    >
                      View PR
                    </a>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Empty State */}
        {!loading && items.length === 0 && (
          <div className="Box-body" style={{ textAlign: "center", padding: "48px 16px" }}>
            <div style={{ color: "var(--color-fg-muted)", marginBottom: "12px" }}>
              <GitPullRequestIcon size={36} color="var(--color-fg-muted)" />
            </div>
            <div style={{ fontSize: "16px", fontWeight: 600, color: "var(--color-fg-default)", marginBottom: "6px" }}>
              No contributions yet
            </div>
            <p style={{ fontSize: "13px", color: "var(--color-fg-muted)", maxWidth: "460px", margin: "0 auto 20px auto" }}>
              Pick an issue and open your first pull request. Once submitted, your public pull requests across open-source repositories will appear here automatically.
            </p>
            <button onClick={onSwitchToRecommended} className="btn btn-primary">
              Browse Recommended Issues
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

