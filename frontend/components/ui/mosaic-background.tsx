"use client";

import { useEffect, useRef, useCallback } from "react";

export type LogoType = "arxiv" | "biorxiv" | "medrxiv" | "rxiv";

interface MosaicBackgroundProps {
  className?: string;
  /** When true, renders a logo as colored mosaic fragments */
  showLogo?: boolean;
  /** Vertical position of the logo as a fraction of viewport height (default 0.22) */
  logoYFraction?: number;
  /** Logo variant: arxiv (default), biorxiv, medrxiv, rxiv */
  logoType?: LogoType;
}

// ---------------------------------------------------------------------------
// Seeded PRNG — deterministic output for consistent renders
// ---------------------------------------------------------------------------
function createRng(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const CELL_SIZE = 12;
const JITTER = 3;
const SEED = 42;

// Neutral + domain accent colors
const ARXIV_GRAY = { r: 154, g: 140, b: 127 }; // #9a8c7f
// bioRxiv: #e74c3c, medRxiv: #3498db, rXivisual: #f97316
const LOGO_COLORS: Record<LogoType, { r: number; g: number; b: number }> = {
  arxiv: { r: 179, g: 27, b: 27 },
  biorxiv: { r: 231, g: 76, b: 60 },
  medrxiv: { r: 52, g: 152, b: 219 },
  rxiv: { r: 249, g: 115, b: 22 },
};


// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
const X_GLYPH = "Χ"; // Greek capital chi
const LOGO_PARTS: Record<
  LogoType,
  { left: string; accent: string; right: string; accentYOffset: number }
> = {
  arxiv: { left: "ar", accent: X_GLYPH, right: "iv", accentYOffset: 0.06 },
  biorxiv: { left: "bio", accent: "R", right: "xiv", accentYOffset: 0.0 },
  medrxiv: { left: "med", accent: "R", right: "xiv", accentYOffset: 0.0 },
  rxiv: { left: "r", accent: X_GLYPH, right: "iv", accentYOffset: 0.06 },
};

export function MosaicBackground({
  className = "",
  showLogo = false,
  logoYFraction = 0.22,
  logoType = "arxiv",
}: MosaicBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const parent = canvas.parentElement;
    if (!parent) return;

    const dpr = window.devicePixelRatio || 1;
    const w = parent.clientWidth;
    const h = parent.clientHeight;

    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    const rand = createRng(SEED);

    // ------------------------------------------------------------------
    // Step 1: Generate jittered point grid
    // ------------------------------------------------------------------
    const cols = Math.ceil(w / CELL_SIZE) + 1;
    const rows = Math.ceil(h / CELL_SIZE) + 1;

    // points[row][col] = [x, y]
    const points: [number, number][][] = [];
    for (let r = 0; r <= rows; r++) {
      points[r] = [];
      for (let c = 0; c <= cols; c++) {
        let px = c * CELL_SIZE;
        let py = r * CELL_SIZE;
        // Jitter interior points for organic feel
        if (r > 0 && r < rows && c > 0 && c < cols) {
          px += (rand() - 0.5) * 2 * JITTER;
          py += (rand() - 0.5) * 2 * JITTER;
        }
        points[r][c] = [px, py];
      }
    }

    // ------------------------------------------------------------------
    // Step 2: Render arXiv logo to offscreen canvas for pixel sampling
    // ------------------------------------------------------------------
    let logoData: ImageData | null = null;

    if (showLogo) {
      const offscreen = document.createElement("canvas");
      offscreen.width = w;
      offscreen.height = h;
      const offCtx = offscreen.getContext("2d");

      if (offCtx) {
        const parts = LOGO_PARTS[logoType];
        const logoText = `${parts.left}${parts.accent}${parts.right}`;
        const baseScale = 0.203;
        const fontSize = Math.max(60, Math.round(w * baseScale));
        offCtx.font = `900 ${fontSize}px "Arial Black", "Impact", "Helvetica Neue", Arial, sans-serif`;
        offCtx.textAlign = "center";
        offCtx.textBaseline = "middle";

        const logoX = w / 2;
        const logoY = h * logoYFraction;

        const fullWidth = offCtx.measureText(logoText).width;
        const leftWidth = offCtx.measureText(parts.left).width;
        const leftPlusAccentWidth = offCtx.measureText(`${parts.left}${parts.accent}`).width;
        const textLeft = logoX - fullWidth / 2;
        const xLeft = textLeft + leftWidth;
        const xRight = textLeft + leftPlusAccentWidth;
        const xCenter = (xLeft + xRight) / 2;

        // Draw left + right in neutral gray, then accent only the configured glyph.
        offCtx.fillStyle = `rgb(${ARXIV_GRAY.r}, ${ARXIV_GRAY.g}, ${ARXIV_GRAY.b})`;
        offCtx.textAlign = "right";
        offCtx.fillText(parts.left, xLeft, logoY);
        offCtx.textAlign = "left";
        offCtx.fillText(parts.right, xRight, logoY);

        const accent = LOGO_COLORS[logoType];
        const accentY = logoY + fontSize * parts.accentYOffset;
        offCtx.fillStyle = `rgb(${accent.r}, ${accent.g}, ${accent.b})`;
        offCtx.textAlign = "center";
        offCtx.fillText(parts.accent, xCenter, accentY);

        logoData = offCtx.getImageData(0, 0, w, h);
      }
    }

    // ------------------------------------------------------------------
    // Step 3: Draw triangulated mosaic
    // ------------------------------------------------------------------
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const p00 = points[r][c];
        const p10 = points[r][c + 1];
        const p01 = points[r + 1][c];
        const p11 = points[r + 1][c + 1];

        // Alternate diagonal direction per cell for variety
        const alt = (r + c) % 2 === 0;
        const tris: [number, number][][] = alt
          ? [
              [p00, p10, p01],
              [p10, p11, p01],
            ]
          : [
              [p00, p10, p11],
              [p00, p11, p01],
            ];

        for (const tri of tris) {
          // Centroid for logo sampling
          const cx = (tri[0][0] + tri[1][0] + tri[2][0]) / 3;
          const cy = (tri[0][1] + tri[1][1] + tri[2][1]) / 3;

          let fillColor: string;
          let strokeColor: string;

          // Sample the offscreen logo canvas at the centroid
          let isLogoFragment = false;
          if (logoData) {
            const px = Math.round(cx);
            const py = Math.round(cy);
            if (px >= 0 && px < w && py >= 0 && py < h) {
              const idx = (py * w + px) * 4;
              const pr = logoData.data[idx];
              const pg = logoData.data[idx + 1];
              const pb = logoData.data[idx + 2];
              const pa = logoData.data[idx + 3];

              if (pa > 10) {
                isLogoFragment = true;
                const brightnessShift = 0.85 + rand() * 0.30; // 0.85-1.15

                const accent = LOGO_COLORS[logoType];
                const distAccent =
                  (pr - accent.r) ** 2 + (pg - accent.g) ** 2 + (pb - accent.b) ** 2;
                const distGray =
                  (pr - ARXIV_GRAY.r) ** 2 + (pg - ARXIV_GRAY.g) ** 2 + (pb - ARXIV_GRAY.b) ** 2;
                const c = distAccent < distGray ? accent : ARXIV_GRAY;
                const cr = c.r;
                const cg = c.g;
                const cb = c.b;
                const opacity = (0.22 + rand() * 0.10) * brightnessShift;
                fillColor = `rgba(${cr}, ${cg}, ${cb}, ${opacity.toFixed(3)})`;
                strokeColor = `rgba(255, 255, 255, ${(0.12 + rand() * 0.06).toFixed(3)})`;
              }
            }
          }

          // Background fragment (not part of logo)
          if (!isLogoFragment) {
            const opacity = 0.008 + rand() * 0.010; // 0.008-0.018
            fillColor = `rgba(255, 255, 255, ${opacity.toFixed(4)})`;
            strokeColor = `rgba(255, 255, 255, ${(0.025 + rand() * 0.015).toFixed(3)})`;
          }

          // Draw triangle
          ctx.beginPath();
          ctx.moveTo(tri[0][0], tri[0][1]);
          ctx.lineTo(tri[1][0], tri[1][1]);
          ctx.lineTo(tri[2][0], tri[2][1]);
          ctx.closePath();

          ctx.fillStyle = fillColor!;
          ctx.fill();

          ctx.strokeStyle = strokeColor!;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }
  }, [showLogo, logoYFraction, logoType]);

  useEffect(() => {
    render();

    let timeout: ReturnType<typeof setTimeout>;
    const handleResize = () => {
      clearTimeout(timeout);
      timeout = setTimeout(render, 200);
    };

    window.addEventListener("resize", handleResize);
    return () => {
      clearTimeout(timeout);
      window.removeEventListener("resize", handleResize);
    };
  }, [render]);

  return (
    <div
      className={`absolute inset-0 overflow-hidden pointer-events-none ${className}`}
    >
      <canvas ref={canvasRef} className="absolute inset-0" />

      {/* Subtle radial gradient for depth */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 40%, rgba(255,255,255,0.015), transparent)",
        }}
      />
    </div>
  );
}
