"use client";

import React, { useEffect, useState } from "react";
import { UserButton, SignInButton, SignedIn, SignedOut } from "@clerk/nextjs";
import { checkBackendHealth } from "@/lib/api";

export default function Navbar() {
  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">("checking");

  useEffect(() => {
    checkBackendHealth()
      .then(() => setBackendStatus("online"))
      .catch(() => setBackendStatus("offline"));
  }, []);

  return (
    <header style={{
      borderBottom: "1px solid var(--border-color)",
      backgroundColor: "rgba(10, 13, 20, 0.8)",
      backdropFilter: "blur(12px)",
      position: "sticky",
      top: 0,
      zIndex: 50,
      padding: "16px 0",
    }}>
      <div className="container" style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{
            width: "36px",
            height: "36px",
            borderRadius: "10px",
            background: "var(--accent-gradient)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: "bold",
            fontSize: "1.1rem",
            color: "#fff",
            boxShadow: "0 0 16px rgba(99, 102, 241, 0.4)",
          }}>
            MW
          </div>
          <div>
            <span style={{ fontSize: "1.2rem", fontWeight: 700, letterSpacing: "-0.02em" }}>MergeWise</span>
            <span style={{
              marginLeft: "8px",
              fontSize: "0.7rem",
              background: "rgba(99, 102, 241, 0.2)",
              color: "#a5b4fc",
              padding: "2px 8px",
              borderRadius: "4px",
              fontWeight: 600,
            }}>
              AGENT
            </span>
          </div>
        </div>

        {/* Status & Auth Actions */}
        <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
          {/* Backend Status Pill */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.85rem", color: "var(--text-muted)" }}>
            <span style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              backgroundColor: backendStatus === "online" ? "var(--success)" : backendStatus === "offline" ? "var(--danger)" : "var(--warning)",
              boxShadow: backendStatus === "online" ? "0 0 8px var(--success)" : "none",
            }} />
            <span>FastAPI: {backendStatus}</span>
          </div>

          <SignedOut>
            <SignInButton mode="modal">
              <button className="btn-primary" style={{ padding: "8px 16px", fontSize: "0.85rem" }}>
                Sign In with GitHub
              </button>
            </SignInButton>
          </SignedOut>

          <SignedIn>
            <UserButton afterSignOutUrl="/" />
          </SignedIn>
        </div>
      </div>
    </header>
  );
}
