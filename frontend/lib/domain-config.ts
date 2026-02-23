/**
 * Domain branding config — mirrors backend utils/domain_utils.py
 * Used for domain-specific frontend: biorxivisual, medrxivisual, rxivisual
 */

export interface BrandingExample {
  id: string;
  label: string;
}

export interface BrandingConfig {
  name: string;
  theme_color: string;
  hero_subtitle: string;
  server_display: string;
  server_url: string | null;
  examples: BrandingExample[];
  /** Source filter for landing page: "arxiv" | "biorxiv" | "medrxiv" | "all" */
  source: "arxiv" | "biorxiv" | "medrxiv" | "all";
}

export const DOMAIN_CONFIG: Record<string, BrandingConfig> = {
  "biorxivisual.org": {
    name: "bioRxivisual",
    theme_color: "#e74c3c",
    hero_subtitle: "Transform bioRxiv preprints into animated visual explanations",
    server_display: "bioRxiv",
    server_url: "https://www.biorxiv.org",
    source: "biorxiv",
    examples: [
      { id: "10.1101/2021.10.04.463034", label: "Protein Design" },
      { id: "10.1101/2023.05.15.540764", label: "Neuroscience" },
      { id: "10.1101/2024.04.18.590025", label: "Genomics" },
    ],
  },
  "medrxivisual.org": {
    name: "medRxivisual",
    theme_color: "#3498db",
    hero_subtitle: "Transform medRxiv preprints into animated visual explanations",
    server_display: "medRxiv",
    server_url: "https://www.medrxiv.org",
    source: "medrxiv",
    examples: [
      { id: "10.1101/2024.05.31.24308283", label: "Sports Science" },
      { id: "10.1101/2024.05.31.24308297", label: "Clinical Research" },
      { id: "10.1101/2024.05.31.24308140", label: "Audiology" },
    ],
  },
  "rxivisual.com": {
    name: "rXivisual",
    theme_color: "#f97316",
    hero_subtitle: "Transform any preprint into animated visual explanations",
    server_display: "bioRxiv + medRxiv",
    server_url: null,
    source: "all",
    examples: [
      { id: "10.1101/2021.10.04.463034", label: "bioRxiv" },
      { id: "10.1101/2024.05.31.24308297", label: "medRxiv" },
    ],
  },
};

export function getBranding(host: string): BrandingConfig {
  const hostClean = host.split(":")[0].toLowerCase();
  if (DOMAIN_CONFIG[hostClean]) {
    return DOMAIN_CONFIG[hostClean];
  }
  for (const domain of Object.keys(DOMAIN_CONFIG)) {
    if (hostClean.endsWith(domain) || domain.endsWith(hostClean)) {
      return DOMAIN_CONFIG[domain];
    }
  }
  return DOMAIN_CONFIG["rxivisual.com"];
}
