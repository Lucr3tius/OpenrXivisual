"""
Domain-based branding and URL routing utilities.

Handles multi-domain deployment (biorxivisual.org, medrxivisual.org, rxivisual.com)
"""

import re
from typing import Optional


# Domain configuration
DOMAIN_CONFIG = {
    "biorxivisual.org": {
        "name": "bioRxivisual",
        "theme_color": "#e74c3c",
        "allowed_servers": ["biorxiv.org"],
        "server_display": "bioRxiv",
        "server_url": "https://www.biorxiv.org",
        "hero_subtitle": "Transform bioRxiv preprints into animated visual explanations",
        "examples": [
            {"id": "10.1101/2024.02.20.707059", "label": "COVID-19 Research"},
            {"id": "10.1101/2023.05.15.550578", "label": "Neuroscience"},
            {"id": "10.1101/2024.01.12.575480", "label": "Genomics"},
        ],
    },
    "medrxivisual.org": {
        "name": "medRxivisual", 
        "theme_color": "#3498db",
        "allowed_servers": ["medrxiv.org"],
        "server_display": "medRxiv",
        "server_url": "https://www.medrxiv.org",
        "hero_subtitle": "Transform medRxiv preprints into animated visual explanations",
        "examples": [
            {"id": "10.64898/2026.02.16.26346428", "label": "Clinical Trial"},
            {"id": "10.1101/2024.03.15.24304018", "label": "Public Health"},
            {"id": "10.1101/2024.01.08.21245332", "label": "Epidemiology"},
        ],
    },
    "rxivisual.com": {
        "name": "rXivisual",
        "theme_color": "#f97316",
        "allowed_servers": ["arxiv.org", "biorxiv.org", "medrxiv.org"],
        "server_display": "arXiv + bioRxiv + medRxiv",
        "server_url": None,
        "hero_subtitle": "Transform any preprint into animated visual explanations",
        "examples": [
            {"id": "1706.03762", "label": "Transformers (arXiv)"},
            {"id": "10.1101/2024.02.20.707059", "label": "bioRxiv"},
            {"id": "10.64898/2026.02.16.26346428", "label": "medRxiv"},
        ],
    },
}


def get_branding(host: str) -> dict:
    """Get branding configuration for a given host."""
    # Strip port if present
    host = host.split(":")[0].lower()
    
    # Try exact match first
    if host in DOMAIN_CONFIG:
        return DOMAIN_CONFIG[host]
    
    # Check for subdomain match (e.g., www.biorxivisual.org)
    for domain, config in DOMAIN_CONFIG.items():
        if host.endswith(domain) or domain.endswith(host):
            return config
    
    # Default to unified site
    return DOMAIN_CONFIG["rxivisual.com"]


def validate_server(
    host: str,
    paper_input: str,
    source: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """
    Validate that the submitted paper's server is allowed for this domain.

    Accepts a paper ID (arXiv ID, DOI) or full URL.
    An explicit ``source`` hint overrides auto-detection.

    Returns: (is_valid, error_message)
    """
    branding = get_branding(host)
    allowed = branding["allowed_servers"]

    # All-allow domains need no check
    if set(allowed) == {"arxiv.org", "biorxiv.org", "medrxiv.org"}:
        return True, None

    # Detect server from the input
    if source:
        detected = source
    else:
        lower = paper_input.lower()
        if "arxiv.org" in lower or re.match(r'^\d{4}\.\d', paper_input) or re.match(r'^[a-z-]+/\d', paper_input):
            detected = "arxiv"
        elif "biorxiv.org" in lower:
            detected = "biorxiv"
        elif "medrxiv.org" in lower:
            detected = "medrxiv"
        elif paper_input.startswith("10.1101/") or paper_input.startswith("10.64898/"):
            # Ambiguous DOI: accept on any single-rxiv domain, resolve later
            if "biorxiv.org" in allowed or "medrxiv.org" in allowed:
                return True, None
            detected = "biorxiv"  # will fail if wrong
        else:
            detected = "arxiv"

    server_domain = {
        "arxiv": "arxiv.org",
        "biorxiv": "biorxiv.org",
        "medrxiv": "medrxiv.org",
    }.get(detected, "arxiv.org")

    if server_domain in allowed:
        return True, None

    # Build a helpful error message
    server_display = {"arxiv.org": "arXiv", "biorxiv.org": "bioRxiv", "medrxiv.org": "medRxiv"}.get(server_domain, detected)
    if branding["server_url"]:
        return False, (
            f"This site only accepts {branding['server_display']} papers. "
            f"Visit {branding['server_url']} for {server_display} papers instead."
        )
    return False, f"Papers from {server_display} are not supported on this site."


def normalize_paper_input(paper_input: str) -> tuple[str, Optional[str]]:
    """
    Normalize user input to a canonical paper identifier.

    Returns:
        (paper_id, source_hint)
        - paper_id: arXiv ID or DOI without version suffix
        - source_hint: "arxiv", "biorxiv", "medrxiv", or None
    """
    raw = paper_input.strip()
    lower = raw.lower()

    # arXiv URLs: /abs/<id> or /pdf/<id>.pdf
    arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf)/([^?\s#]+?)(?:\.pdf)?(?:[?#].*)?$', raw, re.IGNORECASE)
    if arxiv_match:
        arxiv_id = re.sub(r'v\d+$', '', arxiv_match.group(1))
        return arxiv_id, "arxiv"

    # Direct arXiv IDs
    if re.match(r'^\d{4}\.\d{4,5}(v\d+)?$', raw) or re.match(r'^[a-z-]+(\.[a-z]{2})?/\d{7}(v\d+)?$', raw):
        return re.sub(r'v\d+$', '', raw), "arxiv"

    # bioRxiv URL: /content/<doi>vN(.full.pdf)
    biorxiv_match = re.search(
        r'biorxiv\.org/content/(?P<doi>10\.\d{4,9}/[^/?#]+?)(?:v\d+)?(?:\.full\.pdf)?(?:[/?#].*)?$',
        raw,
        re.IGNORECASE,
    )
    if biorxiv_match:
        doi = re.sub(r'v\d+$', '', biorxiv_match.group("doi"))
        return doi, "biorxiv"

    # medRxiv URL: /content/<doi>vN(.full.pdf)
    medrxiv_match = re.search(
        r'medrxiv\.org/content/(?P<doi>10\.\d{4,9}/[^/?#]+?)(?:v\d+)?(?:\.full\.pdf)?(?:[/?#].*)?$',
        raw,
        re.IGNORECASE,
    )
    if medrxiv_match:
        doi = re.sub(r'v\d+$', '', medrxiv_match.group("doi"))
        return doi, "medrxiv"

    # Bare DOI
    doi_match = re.match(r'^(10\.\d{4,9}/\S+?)(?:v\d+)?$', raw)
    if doi_match:
        doi = re.sub(r'v\d+$', '', doi_match.group(1))
        source_hint = "medrxiv" if doi.startswith("10.64898/") else None
        return doi, source_hint

    # Leave unknown values untouched (validation/ingestion will handle errors)
    return raw, None


def get_paper_pdf_url(input_url: str) -> tuple[str, str]:
    """
    Convert any preprint URL to its direct PDF URL.
    
    Returns: (pdf_url, paper_id)
    
    Examples:
    - arxiv.org/abs/1706.03762 -> arxiv.org/pdf/1706.03762.pdf
    - biorxiv.org/content/10.1101/2024.02.20.707059v1 -> biorxiv.org/content/10.1101/2024.02.20.707059v1.full.pdf
    - medrxiv.org/content/10.64898/2026.02.16.26346428v1 -> medrxiv.org/content/10.64898/2026.02.16.26346428v1.full.pdf
    """
    input_url = input_url.strip()
    
    # arXiv: extract ID and construct PDF URL
    arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf)/([^\s/?#]+)', input_url, re.IGNORECASE)
    if arxiv_match:
        arxiv_id = arxiv_match.group(1)
        # Remove version suffix for PDF URL if present
        arxiv_id_clean = re.sub(r'v\d+$', '', arxiv_id)
        return f"https://arxiv.org/pdf/{arxiv_id_clean}.pdf", arxiv_id_clean
    
    # bioRxiv: /content/10.xxxx/...
    biorxiv_match = re.search(
        r'biorxiv\.org/content/(10\.\d{4,9}/[^/?#]+?)(?:v(\d+))?(?:\.full\.pdf)?(?:[/?#].*)?$',
        input_url,
        re.IGNORECASE,
    )
    if biorxiv_match:
        doi = re.sub(r'v\d+$', '', biorxiv_match.group(1))
        version = biorxiv_match.group(2) or "1"
        paper_id = doi
        pdf_url = f"https://www.biorxiv.org/content/{doi}v{version}.full.pdf"
        return pdf_url, paper_id

    # medRxiv: /content/10.xxxx/...
    medrxiv_match = re.search(
        r'medrxiv\.org/content/(10\.\d{4,9}/[^/?#]+?)(?:v(\d+))?(?:\.full\.pdf)?(?:[/?#].*)?$',
        input_url,
        re.IGNORECASE,
    )
    if medrxiv_match:
        doi = re.sub(r'v\d+$', '', medrxiv_match.group(1))
        version = medrxiv_match.group(2) or "1"
        paper_id = doi
        pdf_url = f"https://www.medrxiv.org/content/{doi}v{version}.full.pdf"
        return pdf_url, paper_id

    # Also handle bare DOI formats
    bare_doi = re.search(r'(10\.\d{4,9}/\S+?)(?:v\d+)?$', input_url)
    if bare_doi:
        doi = re.sub(r'v\d+$', '', bare_doi.group(1))
        if doi.startswith("10.64898/"):
            return f"https://www.medrxiv.org/content/{doi}v1.full.pdf", doi
        # 10.1101 can exist on bioRxiv or medRxiv; default to bioRxiv here
        if doi.startswith("10.1101/"):
            return f"https://www.biorxiv.org/content/{doi}v1.full.pdf", doi
    
    raise ValueError(f"Could not parse preprint URL: {input_url}")


# For backwards compatibility - extract just arxiv ID
def extract_arxiv_id(input_str: str) -> Optional[str]:
    """Extract arXiv ID from various input formats."""
    # Direct new format: 1706.03762
    match = re.match(r'^(\d{4}\.\d{4,5})(v\d+)?$', input_str.strip())
    if match:
        return match.group(1)
    
    # Direct old format: hep-th/9901001
    match = re.match(r'^[a-z-]+/\d{7}(v\d+)?$', input_str.strip())
    if match:
        return input_str.strip()
    
    # URL: arxiv.org/abs/...
    match = re.search(r'arxiv\.org/(?:abs|pdf)/([^\s/?#]+)', input_str)
    if match:
        return match.group(1)
    
    return None