"use client";

import React, { useEffect, useState, useRef, useSyncExternalStore } from "react";
import dynamic from "next/dynamic";
import { useSignIn } from "@clerk/nextjs";

// Dynamically import client-only WebGL components with ssr: false
const Lightfall = dynamic<any>(() => import("@/components/reactbits/Lightfall"), { ssr: false });
const TechText = dynamic<any>(() => import("@/components/reactbits/TechText"), { ssr: false });
const FlyingButton = dynamic<any>(() => import("@/components/reactbits/FlyingButton"), { ssr: false });

// Sequence constants (in seconds / milliseconds)
export const LANDING_TIMINGS = {
  HEADING_DELAY_MS: 400,        // t=0.4s: heading mounts and plays intro
  HEADING_INTRO_DUR_S: 2.2,     // heading intro duration (s)
  GAP_AFTER_HEADING_MS: 300,    // pause after heading intro finishes
  SUBHEADING_INTRO_DUR_S: 1.4,  // subheading intro duration (s)
};

function checkWebGL2(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    return !!(window.WebGL2RenderingContext && canvas.getContext("webgl2"));
  } catch (e) {
    return false;
  }
}

export default function LandingHero() {
  const { signIn, isLoaded: isSignInLoaded } = useSignIn();

  // State
  const [hasWebGL2, setHasWebGL2] = useState<boolean>(true);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState<boolean>(false);
  const [isNarrow, setIsNarrow] = useState<boolean>(false);
  const [isLowPower, setIsLowPower] = useState<boolean>(false);

  // Staging sequence flags
  const [headingMounted, setHeadingMounted] = useState<boolean>(false);
  const [subheadingMounted, setSubheadingMounted] = useState<boolean>(false);
  const [buttonMounted, setButtonMounted] = useState<boolean>(false);

  // Auth interaction state
  const [isRedirecting, setIsRedirecting] = useState<boolean>(false);
  const [oauthError, setOauthError] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const [buttonContainerHeight, setButtonContainerHeight] = useState<number>(300);

  useEffect(() => {
    // Ensure landing page background matches #0E1116
    const prevBodyBg = document.body.style.backgroundColor;
    const prevHtmlBg = document.documentElement.style.backgroundColor;
    document.body.style.backgroundColor = "#0E1116";
    document.documentElement.style.backgroundColor = "#0E1116";
    document.documentElement.setAttribute("data-theme", "dark");

    return () => {
      document.body.style.backgroundColor = prevBodyBg;
      document.documentElement.style.backgroundColor = prevHtmlBg;
    };
  }, []);

  useEffect(() => {
    // Check WebGL2
    const webglSupported = checkWebGL2();
    setHasWebGL2(webglSupported);

    // Check reduced motion
    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(motionQuery.matches);

    // Check viewport width (<640px stacks subheading)
    const checkViewport = () => {
      setIsNarrow(window.innerWidth < 640);
    };
    checkViewport();
    window.addEventListener("resize", checkViewport);

    // Check hardware concurrency / mobile
    const lowPower =
      (typeof navigator !== "undefined" &&
        ((navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4) ||
          /iPhone|Android|Mobile/i.test(navigator.userAgent))) ||
      false;
    setIsLowPower(lowPower);

    // If reduced motion is preferred or WebGL2 is missing, mount everything immediately
    if (motionQuery.matches || !webglSupported) {
      setHeadingMounted(true);
      setSubheadingMounted(true);
      setButtonMounted(true);
      return () => window.removeEventListener("resize", checkViewport);
    }

    // Sequence execution
    // 1. Heading mounts at t=0.4s
    const timer1 = setTimeout(() => {
      setHeadingMounted(true);
    }, LANDING_TIMINGS.HEADING_DELAY_MS);

    // 2. Subheading mounts after heading intro (0.4s + 2.2s + 0.3s = 2.9s)
    const subheadingDelay =
      LANDING_TIMINGS.HEADING_DELAY_MS +
      LANDING_TIMINGS.HEADING_INTRO_DUR_S * 1000 +
      LANDING_TIMINGS.GAP_AFTER_HEADING_MS;
    const timer2 = setTimeout(() => {
      setSubheadingMounted(true);
    }, subheadingDelay);

    // 3. Button mounts after subheading intro (2.9s + 1.4s = 4.3s)
    const buttonDelay = subheadingDelay + LANDING_TIMINGS.SUBHEADING_INTRO_DUR_S * 1000;
    const timer3 = setTimeout(() => {
      setButtonMounted(true);
    }, buttonDelay);

    return () => {
      window.removeEventListener("resize", checkViewport);
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
    };
  }, []);

  // Update button container height on resize for accurate altitude clamping
  useEffect(() => {
    const updateContainerSize = () => {
      if (containerRef.current) {
        setButtonContainerHeight(containerRef.current.clientHeight);
      }
    };
    updateContainerSize();
    window.addEventListener("resize", updateContainerSize);
    return () => window.removeEventListener("resize", updateContainerSize);
  }, [buttonMounted]);

  const handleSignIn = async () => {
    // Double invocation guard
    if (isRedirecting) return;
    setIsRedirecting(true);
    setOauthError(null);

    try {
      if (signIn) {
        await signIn.authenticateWithRedirect({
          strategy: "oauth_github",
          redirectUrl: "/sso-callback",
          redirectUrlComplete: "/",
        });
      } else {
        window.location.href = "/sign-in";
      }
    } catch (err: any) {
      console.error("Clerk OAuth redirect failed:", err);
      setIsRedirecting(false);
      const msg =
        err?.errors?.[0]?.message ||
        err?.message ||
        "GitHub authentication failed. Please try again.";
      setOauthError(msg);
    }
  };

  const calculatedAltitude = Math.max(120, Math.min(200, buttonContainerHeight - 90));
  const repoUrl = process.env.NEXT_PUBLIC_REPO_URL;

  return (
    <div
      style={{
        position: "relative",
        height: "100vh",
        maxHeight: "100vh",
        width: "100vw",
        backgroundColor: "#0E1116",
        color: "#e6edf3",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif',
      }}
    >
      {/* Visually Hidden Content for SEO and Screen Readers (no double announce) */}
      <div
        className="sr-only"
        style={{
          position: "absolute",
          width: "1px",
          height: "1px",
          padding: 0,
          margin: "-1px",
          overflow: "hidden",
          clip: "rect(0, 0, 0, 0)",
          whiteSpace: "nowrap",
          border: 0,
        }}
      >
        <h1>MergeWise</h1>
        <p>Open-source issues matched to your GitHub work.</p>
      </div>

      {/* Background Layer: Lightfall (WebGL2) or Static CSS Gradient Fallback */}
      {hasWebGL2 ? (
        <div
          aria-hidden="true"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 0,
            pointerEvents: "none",
            width: "100%",
            height: "100%",
          }}
        >
          <Lightfall
            colors={["#cbd5e1"]}
            backgroundColor="#0E1116"
            speed={0.3}
            streakCount={isLowPower ? 1 : 2}
            streakWidth={0.65}
            glow={0.45}
            headGlow={0.25}
            bloom={isLowPower ? 0 : 0.15}
            opacity={0.65}
            backgroundGlow={0.08}
            mouseInteraction={true}
            holdToWarp={true}
            intro={!prefersReducedMotion}
            dpr={Math.min(typeof window !== "undefined" ? window.devicePixelRatio : 1, 1.5)}
            style={{ width: "100%", height: "100%" }}
          />
        </div>
      ) : (
        <div
          aria-hidden="true"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 0,
            pointerEvents: "none",
            background:
              "radial-gradient(ellipse at 50% 25%, #1c2128 0%, #151921 55%, #0E1116 100%)",
          }}
        />
      )}

      {/* Main Content Column */}
      <main
        style={{
          position: "relative",
          zIndex: 1,
          width: "100%",
          maxWidth: "1012px",
          margin: "0 auto",
          padding: "48px 20px 24px 20px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          flexGrow: 1,
        }}
      >
        {/* 1. Heading: TechText "MergeWise" or Static Fallback */}
        <div
          aria-hidden="true"
          style={{
            width: "100%",
            maxWidth: "760px",
            height: isNarrow ? "clamp(120px, 24vh, 180px)" : "clamp(180px, 36vh, 280px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            opacity: headingMounted ? 1 : 0,
            transition: "opacity 0.3s ease-out",
          }}
        >
          {headingMounted && hasWebGL2 && (
            <TechText
              text="MergeWise"
              fontWeight={700}
              fontSize={isNarrow ? 100 : 160}
              reveal="letter"
              intro={prefersReducedMotion ? "none" : "assemble"}
              introDuration={LANDING_TIMINGS.HEADING_INTRO_DUR_S}
              specks={15}
              clickKick={true}
              guides={false}
              color="#e6edf3"
              accentColor="#58a6ff"
              style={{ width: "100%", height: "100%" }}
            />
          )}

          {headingMounted && !hasWebGL2 && (
            <h1
              style={{
                fontSize: isNarrow ? "42px" : "68px",
                fontWeight: 800,
                letterSpacing: "-0.03em",
                color: "#e6edf3",
                textAlign: "center",
                margin: 0,
              }}
            >
              MergeWise
            </h1>
          )}
        </div>

        {/* 2. Subheading: TechText or Static Fallback (split <640px) */}
        <div
          aria-hidden="true"
          style={{
            width: "100%",
            maxWidth: "720px",
            marginTop: "8px",
            opacity: subheadingMounted ? 1 : 0,
            transition: "opacity 0.3s ease-out",
          }}
        >
          {subheadingMounted && hasWebGL2 && (
            <>
              {!isNarrow ? (
                <div style={{ width: "100%", height: "44px" }}>
                  <TechText
                    text="Open-source issues matched to your GitHub work."
                    fontWeight={400}
                    fontSize={26}
                    reveal="off"
                    selection={false}
                    labels={false}
                    specks={0}
                    draggable={false}
                    clickKick={false}
                    sweep={false}
                    intro={prefersReducedMotion ? "none" : "type"}
                    introDuration={LANDING_TIMINGS.SUBHEADING_INTRO_DUR_S}
                    color="#cbd5e1"
                    accentColor="#a78bfa"
                    style={{ width: "100%", height: "100%" }}
                  />
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "2px", alignItems: "center" }}>
                  <div style={{ width: "100%", height: "32px" }}>
                    <TechText
                      text="Open-source issues"
                      fontWeight={400}
                      fontSize={24}
                      reveal="off"
                      selection={false}
                      labels={false}
                      specks={0}
                      draggable={false}
                      clickKick={false}
                      sweep={false}
                      intro={prefersReducedMotion ? "none" : "type"}
                      introDuration={0.7}
                      color="#cbd5e1"
                      accentColor="#a78bfa"
                      style={{ width: "100%", height: "100%" }}
                    />
                  </div>
                  <div style={{ width: "100%", height: "32px" }}>
                    <TechText
                      text="matched to your GitHub work."
                      fontWeight={400}
                      fontSize={24}
                      reveal="off"
                      selection={false}
                      labels={false}
                      specks={0}
                      draggable={false}
                      clickKick={false}
                      sweep={false}
                      intro={prefersReducedMotion ? "none" : "type"}
                      introDuration={0.7}
                      color="#cbd5e1"
                      accentColor="#a78bfa"
                      style={{ width: "100%", height: "100%" }}
                    />
                  </div>
                </div>
              )}
            </>
          )}

          {subheadingMounted && !hasWebGL2 && (
            <p
              style={{
                fontSize: isNarrow ? "16px" : "20px",
                color: "#cbd5e1",
                textAlign: "center",
                margin: 0,
                lineHeight: 1.4,
              }}
            >
              Open-source issues matched to your GitHub work.
            </p>
          )}
        </div>

        {/* 3. Button: FlyingButton Container or WebGL2 Fallback */}
        <div
          ref={containerRef}
          style={{
            position: "relative",
            width: "100%",
            maxWidth: "520px",
            height: "clamp(260px, 36vh, 360px)",
            marginTop: "16px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "flex-end",
            opacity: buttonMounted ? 1 : 0,
            transform: buttonMounted ? "translateY(0)" : "translateY(16px)",
            transition: prefersReducedMotion
              ? "none"
              : "opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1), transform 0.6s cubic-bezier(0.16, 1, 0.3, 1)",
            WebkitMaskImage:
              "linear-gradient(to top, rgba(0,0,0,1) 0%, rgba(0,0,0,1) 70%, rgba(0,0,0,0) 100%)",
            maskImage:
              "linear-gradient(to top, rgba(0,0,0,1) 0%, rgba(0,0,0,1) 70%, rgba(0,0,0,0) 100%)",
          }}
        >
          {buttonMounted && hasWebGL2 && (
            <FlyingButton
              theme="dark"
              size="large"
              trigger="hover"
              carryCursor={true}
              altitude={calculatedAltitude}
              hoverTime={2.4}
              jets={2}
              thrusters={true}
              thrustColor="#58a6ff"
              onClick={handleSignIn}
            >
              Continue with GitHub
            </FlyingButton>
          )}

          {buttonMounted && !hasWebGL2 && (
            <button
              type="button"
              onClick={handleSignIn}
              disabled={isRedirecting}
              className="btn btn-primary"
              style={{
                height: "44px",
                padding: "0 28px",
                fontSize: "16px",
                fontWeight: 600,
                marginBottom: "20px",
                borderRadius: "6px",
                backgroundColor: "#238636",
                color: "#ffffff",
                border: "1px solid rgba(240, 246, 252, 0.1)",
                cursor: "pointer",
              }}
            >
              Continue with GitHub
            </button>
          )}
        </div>

        {/* Status / Error feedback below button */}
        <div style={{ minHeight: "24px", marginTop: "12px", textAlign: "center" }}>
          {isRedirecting && (
            <span style={{ fontSize: "13px", color: "#58a6ff" }}>
              Connecting to GitHub OAuth...
            </span>
          )}
          {oauthError && (
            <span style={{ fontSize: "13px", color: "#f85149" }}>
              {oauthError}
            </span>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer
        style={{
          position: "relative",
          zIndex: 1,
          width: "100%",
          padding: "16px 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "16px",
          fontSize: "12px",
          color: "#8b8198",
        }}
      >
        <span>Not affiliated with GitHub.</span>
        {repoUrl && (
          <>
            <span>•</span>
            <a
              href={repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: "#a78bfa", textDecoration: "none", fontWeight: 500 }}
            >
              Source repository
            </a>
          </>
        )}
      </footer>
    </div>
  );
}
