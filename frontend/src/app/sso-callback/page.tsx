"use client";

import React from "react";
import { AuthenticateWithRedirectCallback } from "@clerk/nextjs";

export default function SSOCallbackPage() {
  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "#0E1116",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "#e6edf3",
      }}
    >
      <AuthenticateWithRedirectCallback />
    </div>
  );
}

