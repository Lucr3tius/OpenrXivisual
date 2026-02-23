import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";
import { headers } from "next/headers";
import { getBranding } from "@/lib/domain-config";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export async function generateMetadata(): Promise<Metadata> {
  const reqHeaders = await headers();
  const hostHeader =
    reqHeaders.get("x-forwarded-host") ??
    reqHeaders.get("host") ??
    "rxivisual.com";
  const host = hostHeader.split(",")[0].trim().split(":")[0].toLowerCase();
  const branding = getBranding(host);

  const faviconPath =
    branding.source === "medrxiv"
      ? "/favicon-medrxiv.svg"
      : branding.source === "biorxiv"
        ? "/favicon-biorxiv.svg"
        : "/favicon-rxivisual.svg";

  return {
    title: {
      default: "OpenrXivisual",
      template: "%s · OpenrXivisual",
    },
    description:
      "Turn arXiv, bioRxiv, and medRxiv preprints into scrollytelling explanations with AI-generated visuals.",
    applicationName: "OpenrXivisual",
    keywords: [
      "arXiv",
      "bioRxiv",
      "medRxiv",
      "preprints",
      "research",
      "visualization",
      "scrollytelling",
      "Manim",
      "machine learning",
      "computer science",
    ],
    icons: {
      icon: [
        { url: faviconPath, type: "image/svg+xml", sizes: "any" },
      ],
      apple: [{ url: faviconPath, type: "image/svg+xml" }],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased min-h-dvh bg-black text-[#e8e8e8]`}
      >
        <div className="min-h-dvh">{children}</div>
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
