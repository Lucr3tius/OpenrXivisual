"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { PlaceholdersAndVanishInput } from "@/components/ui/placeholders-and-vanish-input";
import { ShardField } from "@/components/ui/glass-shard";
import { GlassCard } from "@/components/ui/glass-card";
import { getBranding } from "@/lib/domain-config";

/**
 * Extract a normalized paper ID from any supported input:
 * - arXiv IDs:  "1706.03762", "cs/0123456", full arxiv.org URLs
 * - bioRxiv DOIs: "10.1101/2024.02.20.707059", biorxiv.org URLs
 * - medRxiv DOIs: "10.1101/2024.03.15.24304018", medrxiv.org URLs
 *
 * Returns { id, source } or null if the input is unrecognized.
 */
function extractPaperId(inputRaw: string): { id: string; source: string } | null {
  const input = inputRaw.trim();
  if (!input) return null;

  // --- arXiv ---
  // Direct new format: NNNN.NNNNN[vN]
  const arXivNew = input.match(/^(\d{4}\.\d{4,5})(v\d+)?$/i);
  if (arXivNew) return { id: arXivNew[1], source: "arxiv" };

  // Direct old format: category[.XX]/NNNNNNN[vN]
  const arXivOld = input.match(/^([a-z-]+(?:\.[a-z]{2})?\/\d{7})(v\d+)?$/i);
  if (arXivOld) return { id: arXivOld[1], source: "arxiv" };

  // arxiv.org URL (abs or pdf)
  const arXivAbs = input.match(/arxiv\.org\/(?:abs|pdf)\/([^?\s#]+?)(?:\.pdf)?(?:[?#].*)?$/i);
  if (arXivAbs?.[1]) return { id: decodeURIComponent(arXivAbs[1]).replace(/\/$/, ""), source: "arxiv" };

  // --- bioRxiv ---
  // Full biorxiv.org URL: /content/10.1101/...
  const bioRxivUrl = input.match(/biorxiv\.org\/content\/(10\.\d{4,}\/[^?\s#v]+)(v\d+)?/i);
  if (bioRxivUrl?.[1]) return { id: bioRxivUrl[1], source: "biorxiv" };

  // --- medRxiv ---
  // Full medrxiv.org URL: /content/10.1101/...
  const medRxivUrl = input.match(/medrxiv\.org\/content\/(10\.\d{4,}\/[^?\s#v]+)(v\d+)?/i);
  if (medRxivUrl?.[1]) return { id: medRxivUrl[1], source: "medrxiv" };

  // --- Bare DOI (10.1101/...) — could be bioRxiv or medRxiv; backend auto-detects ---
  const bareDoiNew = input.match(/^(10\.\d{4,}\/\d{4}\.\d{2}\.\d{2}\.\d+)(v\d+)?$/i);
  if (bareDoiNew?.[1]) return { id: bareDoiNew[1], source: "rxiv" };

  // Generic DOI starting with 10.
  const bareDoi = input.match(/^(10\.\d{4,}\/.+?)(?:v\d+)?$/i);
  if (bareDoi?.[1] && !bareDoi[1].includes(" ")) return { id: bareDoi[1], source: "rxiv" };

  return null;
}

function getPlaceholders(source: "arxiv" | "biorxiv" | "medrxiv" | "all"): string[] {
  if (source === "biorxiv") {
    return [
      "Paste a bioRxiv URL or ID...",
      "https://www.biorxiv.org/content/10.1101/2024.02.20.707059",
      "10.1101/2021.10.04.463034",
      "10.1101/2024.04.18.590025",
    ];
  }
  if (source === "medrxiv") {
    return [
      "Paste a medRxiv URL or ID...",
      "https://www.medrxiv.org/content/10.1101/2024.05.31.24308297",
      "10.64898/2026.02.16.26346428",
      "10.1101/2024.05.31.24308283",
    ];
  }
  if (source === "arxiv") {
    return [
      "Paste an arXiv URL or ID...",
      "1706.03762 (Attention Is All You Need)",
      "https://arxiv.org/abs/2005.14165",
    ];
  }
  return [
    "Paste an arXiv, bioRxiv, or medRxiv URL or ID...",
    "1706.03762 (Attention Is All You Need)",
    "https://arxiv.org/abs/2005.14165",
    "https://www.biorxiv.org/content/10.1101/2024.02.20.707059",
    "10.1101/2024.03.15.24304018 (medRxiv DOI)",
  ];
}

function getWordmark(source: "arxiv" | "biorxiv" | "medrxiv" | "all") {
  if (source === "medrxiv") return { prefix: "med", accent: "R", suffix: "χivisual" };
  if (source === "biorxiv") return { prefix: "bio", accent: "R", suffix: "χivisual" };
  return { prefix: "open", accent: "R", suffix: "χivisual" };
}

/** Get domain-specific branding (client-side) */
function useBranding() {
  const previewBrandHost = process.env.NEXT_PUBLIC_BRANDING_HOST?.trim().toLowerCase();
  return useMemo(() => {
    if (typeof window === "undefined") return getBranding("rxivisual.com");
    return getBranding(previewBrandHost || window.location.hostname);
  }, []);
}

export default function Home() {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [touched, setTouched] = useState(false);
  const branding = useBranding();
  const placeholders = useMemo(
    () => getPlaceholders(branding.source),
    [branding.source],
  );
  const wordmark = useMemo(
    () => getWordmark(branding.source),
    [branding.source],
  );

  useEffect(() => {
    let meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
    if (!meta) {
      meta = document.createElement("meta");
      meta.name = "theme-color";
      document.head.appendChild(meta);
    }
    meta.content = branding.theme_color;
  }, [branding.theme_color]);

  const parsed = useMemo(() => extractPaperId(value), [value]);
  const parsedId = parsed?.id ?? null;
  const canSubmit = Boolean(parsedId);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!parsedId) return;
    router.push(`/abs/${encodeURIComponent(parsedId)}`);
  }

  return (
    <main className="min-h-dvh relative overflow-hidden bg-black">
      {/* Floating glass shards */}
      <ShardField />

      <div className="relative z-10 mx-auto w-full max-w-6xl px-6">
        {/* ── First viewport: Logo + search bar below ── */}
        <section className="min-h-dvh flex flex-col">
          {/* Logo — clean text, centered in upper portion */}
          <div className="flex-1 flex items-center justify-center">
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-black tracking-tight text-white/90 select-none"
            >
              {wordmark.prefix}
              <span style={{ color: branding.theme_color }}>{wordmark.accent}</span>
              {wordmark.suffix}
            </motion.h1>
          </div>

          {/* Search area — pinned to lower portion of viewport */}
          <div className="max-w-4xl mx-auto w-full text-center pb-16 sm:pb-24">
            {/* Subtitle */}
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.5 }}
              className="text-lg sm:text-xl text-white/40 max-w-2xl mx-auto leading-relaxed font-light"
            >
              {branding.hero_subtitle}.
            </motion.p>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.65 }}
              className="mt-2 text-base sm:text-lg text-white/30 max-w-2xl mx-auto leading-relaxed font-light"
            >
              Paste {branding.server_display} URL or ID.
            </motion.p>

            {/* Input Section */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.8 }}
              className="mt-10 max-w-xl mx-auto"
            >
              <div className="relative">
                {/* Decorative brackets */}
                <div className="absolute -left-4 top-1/2 -translate-y-1/2 text-3xl text-white/10 font-light select-none hidden sm:block">
                  [
                </div>
                <div className="absolute -right-4 top-1/2 -translate-y-1/2 text-3xl text-white/10 font-light select-none hidden sm:block">
                  ]
                </div>

                <PlaceholdersAndVanishInput
                  placeholders={placeholders}
                  value={value}
                  onChange={(e) => {
                    setValue(e.target.value);
                    setTouched(true);
                  }}
                  onSubmit={onSubmit}
                  disabled={!canSubmit && touched && value.length > 0}
                />
              </div>

              {/* Status feedback */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1.0 }}
                className="mt-4 h-6 text-sm"
              >
                {parsedId ? (
                  <span className="text-[#7dd19b] flex items-center justify-center gap-2">
                    <span className="text-lg">✓</span>
                    <span>Detected{parsed?.source && parsed.source !== "rxiv" ? ` (${parsed.source})` : ""}:{" "}</span>
                    <span className="font-mono bg-[#7dd19b]/10 px-2 py-0.5 rounded">{parsedId}</span>
                  </span>
                ) : touched && value ? (
                  <span className="text-[#f27066]">
                    Enter a valid preprint URL, DOI, or arXiv ID
                  </span>
                ) : null}
              </motion.div>
            </motion.div>

            {/* Quick Examples */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.6, delay: 1.2 }}
              className="mt-8 flex flex-wrap items-center justify-center gap-3"
            >
              <span className="text-sm text-white/30">Try these:</span>
              {branding.examples.map((example) => (
                <motion.button
                  key={example.id}
                  whileHover={{ scale: 1.05, y: -2 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => setValue(example.id)}
                  className="group rounded-xl bg-white/[0.04] px-4 py-2.5 text-sm border border-white/[0.08] transition-all hover:bg-white/[0.07] hover:border-white/[0.14]"
                >
                  <span className="text-white/60 font-mono">{example.id}</span>
                  <span className="text-white/30 ml-2">({example.label})</span>
                </motion.button>
              ))}
            </motion.div>
          </div>
        </section>

        {/* Pro Tip Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 2.2 }}
          className="mt-20 max-w-2xl mx-auto"
        >
          <GlassCard spotlight className="p-8">
            <div className="flex items-center gap-4 mb-4">
              <div className="h-12 w-12 rounded-xl bg-white/[0.06] flex items-center justify-center border border-white/[0.10]">
                <div
                  className="h-4 w-4 bg-gradient-to-br from-white/50 to-white/20"
                  style={{ clipPath: "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)" }}
                />
              </div>
              <div>
                <h3 className="font-semibold text-white/90">Pro Tip</h3>
                <p className="text-sm text-white/40">One edit turns any preprint into a visual</p>
              </div>
            </div>
            <div className="space-y-3 text-sm text-white/45 leading-relaxed">
              <p>
                {branding.source === "biorxiv" ? (
                  <>
                    Add{" "}
                    <code className="text-white/60 bg-white/[0.06] px-1.5 py-0.5 rounded text-xs font-mono">
                      isual
                    </code>
                    {" "}after{" "}
                    <code className="text-white/60 bg-white/[0.06] px-1.5 py-0.5 rounded text-xs font-mono">
                      bioRxiv
                    </code>
                    {" "}in any preprint URL.
                  </>
                ) : branding.source === "medrxiv" ? (
                  <>
                    Add{" "}
                    <code className="text-white/60 bg-white/[0.06] px-1.5 py-0.5 rounded text-xs font-mono">
                      isual
                    </code>
                    {" "}after{" "}
                    <code className="text-white/60 bg-white/[0.06] px-1.5 py-0.5 rounded text-xs font-mono">
                      medRxiv
                    </code>
                    {" "}in any preprint URL.
                  </>
                ) : (
                  <>
                    Add{" "}
                    <code className="text-white/60 bg-white/[0.06] px-1.5 py-0.5 rounded text-xs font-mono">
                      isual
                    </code>
                    {" "}after{" "}
                    <code className="text-white/60 bg-white/[0.06] px-1.5 py-0.5 rounded text-xs font-mono">
                      bioRxiv
                    </code>
                    {" "}or{" "}
                    <code className="text-white/60 bg-white/[0.06] px-1.5 py-0.5 rounded text-xs font-mono">
                      medRxiv
                    </code>
                    {" "}in any preprint URL.
                  </>
                )}
              </p>
              <div className="rounded-lg border border-white/[0.08] bg-white/[0.03] p-3 space-y-1">
                {branding.source === "biorxiv" ? (
                  <p className="font-mono text-xs text-white/50">biorxiv.org → <span className="text-white/70">biorxivisual.org</span></p>
                ) : branding.source === "medrxiv" ? (
                  <p className="font-mono text-xs text-white/50">medrxiv.org → <span className="text-white/70">medrxivisual.org</span></p>
                ) : (
                  <>
                    <p className="font-mono text-xs text-white/50">biorxiv.org → <span className="text-white/70">biorxivisual.org</span></p>
                    <p className="font-mono text-xs text-white/50">medrxiv.org → <span className="text-white/70">medrxivisual.org</span></p>
                  </>
                )}
              </div>
            </div>
          </GlassCard>
        </motion.div>

        {/* Footer */}
        <motion.footer
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 2.4 }}
          className="mt-20 flex flex-col items-center justify-between gap-4 border-t border-white/[0.06] pt-8 text-sm sm:flex-row"
        >
          <div className="flex items-center gap-3 text-white/30">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
              className="h-3 w-3 bg-gradient-to-br from-white/30 to-white/10"
              style={{ clipPath: "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)" }}
            />
            <span>
              {branding.source === "biorxiv"
                ? "Visualizing biology preprints"
                : branding.source === "medrxiv"
                  ? "Visualizing medical preprints"
                  : "Visualizing preprints, one paper at a time"}
            </span>
          </div>
          <div className="flex items-center gap-4">
            {(branding.source === "biorxiv" || branding.source === "all") && (
              <a
                className="rounded-lg px-3 py-1.5 text-white/40 border border-white/[0.06] transition hover:bg-white/[0.04] hover:text-white/60 hover:border-white/[0.12]"
                href="https://www.biorxiv.org"
                target="_blank"
                rel="noreferrer"
              >
                bioRxiv
              </a>
            )}
            {(branding.source === "medrxiv" || branding.source === "all") && (
              <a
                className="rounded-lg px-3 py-1.5 text-white/40 border border-white/[0.06] transition hover:bg-white/[0.04] hover:text-white/60 hover:border-white/[0.12]"
                href="https://www.medrxiv.org"
                target="_blank"
                rel="noreferrer"
              >
                medRxiv
              </a>
            )}
            <a
              className="rounded-lg px-3 py-1.5 text-white/40 border border-white/[0.06] transition hover:bg-white/[0.04] hover:text-white/60 hover:border-white/[0.12]"
              href="https://www.manim.community/"
              target="_blank"
              rel="noreferrer"
            >
              Manim
            </a>
          </div>
        </motion.footer>
      </div>
    </main>
  );
}
