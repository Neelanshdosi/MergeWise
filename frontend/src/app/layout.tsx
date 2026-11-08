import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import "@/styles/globals.css";
import Navbar from "@/components/Navbar";
import { SearchProvider } from "@/lib/searchContext";

export const metadata: Metadata = {
  title: "MergeWise: find open-source issues you can merge",
  description:
    "Open-source issues matched to your GitHub work. Personalized recommendations, live viability verification, starter plans, and contribution tracking.",
  icons: {
    icon: "/mergewise-logo.png",
  },
  openGraph: {
    title: "MergeWise: find open-source issues you can merge",
    description: "Open-source issues matched to your GitHub work.",
    type: "website",
    siteName: "MergeWise",
  },
  twitter: {
    card: "summary_large_image",
    title: "MergeWise: find open-source issues you can merge",
    description: "Open-source issues matched to your GitHub work.",
  },
};

const themeInitScript = `
(function() {
  try {
    var params = new URLSearchParams(window.location.search);
    var queryTheme = params.get("theme");
    if (queryTheme === "dark" || queryTheme === "light") {
      document.documentElement.setAttribute("data-theme", queryTheme);
      return;
    }
    var stored = localStorage.getItem("mergewise-theme");
    if (stored === "dark" || stored === "light") {
      document.documentElement.setAttribute("data-theme", stored);
    } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      document.documentElement.setAttribute("data-theme", "dark");
    } else {
      document.documentElement.setAttribute("data-theme", "light");
    }
  } catch (e) {}
})();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const publishableKey =
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ||
    "pk_test_bWVyZ2V3aXNlLWJ1aWxkLXBsYWNlaG9sZGVyLmNsZXJrLmFjY291bnRzLmRldiQ";

  return (
    <ClerkProvider publishableKey={publishableKey}>
      <html lang="en" suppressHydrationWarning>
        <head>
          <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        </head>
        <body>
          <SearchProvider>
            <Navbar />
            <main>{children}</main>
          </SearchProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
