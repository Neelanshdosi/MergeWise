"use client";

import React, { useEffect, useState, useRef } from "react";
import { UserButton, SignInButton, SignedIn, SignedOut, useAuth, useUser, useClerk } from "@clerk/nextjs";
import { usePathname } from "next/navigation";
import { checkBackendHealth } from "@/lib/api";
import { useSearch } from "@/lib/searchContext";
import {
  SunIcon,
  MoonIcon,
  MenuIcon,
  SearchIcon,
  TriangleDownIcon,
  TrashIcon,
  XIcon,
} from "./Octicons";

export default function Navbar() {
  const { isSignedIn, isLoaded } = useAuth();
  const { user } = useUser();
  const { signOut } = useClerk();
  const pathname = usePathname();
  const { searchQuery, setSearchQuery } = useSearch();

  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">("checking");
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  const [breadcrumbMenuOpen, setBreadcrumbMenuOpen] = useState(false);
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const breadcrumbRef = useRef<HTMLDivElement>(null);

  // Sync theme
  useEffect(() => {
    const currentTheme = document.documentElement.getAttribute("data-theme") as "light" | "dark";
    if (currentTheme) {
      setTheme(currentTheme);
    } else if (typeof window !== "undefined" && window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {
      setTheme("light");
    } else {
      setTheme("dark");
    }

    checkBackendHealth()
      .then(() => setBackendStatus("online"))
      .catch(() => setBackendStatus("offline"));
  }, []);

  // Global Keyboard listener for '/' and 'Esc'
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // If '/' pressed and not inside an input/textarea
      if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes((document.activeElement?.tagName || ""))) {
        e.preventDefault();
        searchInputRef.current?.focus();
      }

      // If 'Escape' pressed
      if (e.key === "Escape") {
        if (document.activeElement === searchInputRef.current) {
          setSearchQuery("");
          searchInputRef.current?.blur();
        }
        setBreadcrumbMenuOpen(false);
        setMobileDrawerOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [setSearchQuery]);

  // Click outside to close breadcrumb dropdown
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (breadcrumbRef.current && !breadcrumbRef.current.contains(e.target as Node)) {
        setBreadcrumbMenuOpen(false);
      }
    };
    if (breadcrumbMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [breadcrumbMenuOpen]);

  // Hide global navbar on landing page for signed-out users
  if (pathname === "/" && (!isLoaded || !isSignedIn)) {
    return null;
  }

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    document.documentElement.setAttribute("data-theme", nextTheme);
    try {
      localStorage.setItem("mergewise-theme", nextTheme);
    } catch (e) {}
  };

  const scrollToDangerZone = () => {
    setBreadcrumbMenuOpen(false);
    setMobileDrawerOpen(false);
    const dangerZone = document.getElementById("danger-zone");
    if (dangerZone) {
      dangerZone.scrollIntoView({ behavior: "smooth" });
    }
  };

  const githubLogin =
    user?.username ||
    (user?.emailAddresses?.[0]?.emailAddress ? user.emailAddresses[0].emailAddress.split("@")[0] : null) ||
    "Neelanshdosi";

  return (
    <header className="GlobalHeader" role="banner">
      <div className="GlobalHeader-container">
        {/* Left Side: Mobile Menu, MW Logo, Breadcrumb */}
        <div className="GlobalHeader-left">
          {/* Mobile hamburger menu toggle */}
          <button
            className="btn-octicon GlobalHeader-mobile-toggle"
            onClick={() => setMobileDrawerOpen(!mobileDrawerOpen)}
            aria-label="Toggle navigation drawer"
            aria-expanded={mobileDrawerOpen}
          >
            {mobileDrawerOpen ? <XIcon size={18} /> : <MenuIcon size={18} />}
          </button>

          {/* MergeWise Logo */}
          <a href="/" className="GlobalHeader-logo" aria-label="MergeWise Home">
            <img
              src="/mergewise-logo.png"
              alt="MergeWise Logo"
              width={32}
              height={32}
              style={{ width: "32px", height: "32px", borderRadius: "50%", objectFit: "cover", display: "block" }}
              className="GlobalHeader-logo-img"
            />
          </a>

          {/* Breadcrumb: <github login> / MergeWise with dropdown caret */}
          <div className="GlobalHeader-breadcrumb" ref={breadcrumbRef}>
            <span className="GlobalHeader-breadcrumb-login">{githubLogin}</span>
            <span className="GlobalHeader-breadcrumb-divider">/</span>
            <a href="/" className="GlobalHeader-breadcrumb-repo">
              MergeWise
            </a>

            <button
              className="GlobalHeader-breadcrumb-caret"
              onClick={() => setBreadcrumbMenuOpen(!breadcrumbMenuOpen)}
              aria-label="Repository and account options"
              aria-expanded={breadcrumbMenuOpen}
              aria-haspopup="true"
            >
              <TriangleDownIcon size={12} />
            </button>

            {/* Breadcrumb Dropdown Menu */}
            {breadcrumbMenuOpen && (
              <div className="GlobalHeader-dropdown" role="menu">
                <button
                  className="GlobalHeader-dropdown-item"
                  onClick={toggleTheme}
                  role="menuitem"
                >
                  {theme === "dark" ? <SunIcon size={14} /> : <MoonIcon size={14} />}
                  <span>Switch to {theme === "dark" ? "light" : "dark"} theme</span>
                </button>

                <button
                  className="GlobalHeader-dropdown-item GlobalHeader-dropdown-item--danger"
                  onClick={scrollToDangerZone}
                  role="menuitem"
                >
                  <TrashIcon size={14} />
                  <span>Delete my data</span>
                </button>

                <div className="GlobalHeader-dropdown-divider" />

                <button
                  className="GlobalHeader-dropdown-item"
                  onClick={() => signOut({ redirectUrl: "/" })}
                  role="menuitem"
                >
                  <span>Sign out</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Search Box, API Status Dot, Theme Toggle, Clerk Avatar */}
        <div className="GlobalHeader-right">
          {/* Search Box with "/" hint */}
          <div className="GlobalHeader-search">
            <SearchIcon size={14} className="GlobalHeader-search-icon" />
            <input
              ref={searchInputRef}
              type="text"
              className="GlobalHeader-search-input"
              placeholder="Type / to search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Search and filter issues"
            />
            {!searchQuery && <kbd className="GlobalHeader-search-kbd">/</kbd>}
            {searchQuery && (
              <button
                className="GlobalHeader-search-clear"
                onClick={() => setSearchQuery("")}
                aria-label="Clear search"
              >
                <XIcon size={12} />
              </button>
            )}
          </div>

          {/* API Status Dot */}
          <div
            className="GlobalHeader-status"
            title={`API ${backendStatus}`}
            aria-label={`API status: ${backendStatus}`}
          >
            <span
              className={`GlobalHeader-status-dot GlobalHeader-status-dot--${backendStatus}`}
            />
          </div>

          {/* Theme Toggle Button */}
          <button
            onClick={toggleTheme}
            className="btn-octicon"
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          >
            {theme === "dark" ? <SunIcon size={16} /> : <MoonIcon size={16} />}
          </button>

          {/* Clerk User Avatar Menu */}
          <SignedOut>
            <SignInButton mode="modal">
              <button className="btn btn-sm btn-primary">Sign in with GitHub</button>
            </SignInButton>
          </SignedOut>

          <SignedIn>
            <UserButton afterSignOutUrl="/" />
          </SignedIn>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileDrawerOpen && (
        <div className="GlobalHeader-drawer" role="dialog" aria-label="Mobile navigation">
          <div className="GlobalHeader-drawer-search">
            <SearchIcon size={14} className="GlobalHeader-search-icon" />
            <input
              type="text"
              className="GlobalHeader-search-input"
              placeholder="Filter visible issues..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                className="GlobalHeader-search-clear"
                onClick={() => setSearchQuery("")}
                aria-label="Clear search"
              >
                <XIcon size={12} />
              </button>
            )}
          </div>

          <div className="GlobalHeader-drawer-menu">
            <button className="GlobalHeader-drawer-item" onClick={toggleTheme}>
              {theme === "dark" ? <SunIcon size={16} /> : <MoonIcon size={16} />}
              <span>Toggle theme ({theme === "dark" ? "Dark" : "Light"})</span>
            </button>
            <button className="GlobalHeader-drawer-item GlobalHeader-drawer-item--danger" onClick={scrollToDangerZone}>
              <TrashIcon size={16} />
              <span>Delete my data</span>
            </button>
            <button className="GlobalHeader-drawer-item" onClick={() => signOut({ redirectUrl: "/" })}>
              <span>Sign out</span>
            </button>
          </div>
        </div>
      )}
    </header>
  );
}
