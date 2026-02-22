"""
Paper Ingestion Pipeline for OpenrXivisual.

Main entry point: ingest_paper(paper_id) -> StructuredPaper

Supports arXiv, bioRxiv, and medRxiv preprints.

Pipeline:
1. Detect source (arXiv / bioRxiv / medRxiv) from paper ID format
2. Fetch metadata from the appropriate API
3. Parse HTML (arXiv/ar5iv preferred) or PDF (fallback / bioRxiv/medRxiv)
4. Extract sections with hierarchy
5. Cache and return StructuredPaper

Output goes to the AI visualization pipeline.
"""

import logging
import re
from typing import Optional

from models.paper import (
    ArxivPaperMeta,
    ParsedContent,
    Section,
    StructuredPaper,
)
from .arxiv_fetcher import (
    fetch_paper_meta,
    download_pdf,
    fetch_html_content,
    normalize_arxiv_id,
    validate_arxiv_id,
)
from .biorxiv_fetcher import fetch_biorxiv_meta, normalize_doi, is_rxiv_doi
from .pdf_parser import parse_pdf
from .html_parser import parse_html, fetch_and_parse_html
from .section_extractor import extract_sections
from .section_formatter import format_sections

# Configure logging
logger = logging.getLogger(__name__)

# Simple in-memory cache for development
# In production, use Redis or database
_paper_cache: dict[str, StructuredPaper] = {}


def detect_paper_source(paper_id: str) -> str:
    """
    Detect the preprint server from the paper ID format.

    Returns:
        "arxiv"  – standard arXiv ID (e.g. "1706.03762", "cs/0123456")
        "rxiv"   – bioRxiv/medRxiv DOI (e.g. "10.1101/…"); server resolved via API
        "biorxiv" / "medrxiv" – if explicit hint already known
    """
    paper_id = paper_id.strip()
    # arXiv new format: NNNN.NNNNN
    if re.match(r'^\d{4}\.\d{4,5}', paper_id):
        return "arxiv"
    # arXiv old format: category/NNNNNNN
    if re.match(r'^[a-z-]+(\.[a-z]{2})?/\d{7}', paper_id):
        return "arxiv"
    # DOI formats used by bioRxiv and medRxiv
    if is_rxiv_doi(paper_id):
        return "rxiv"
    # Default: assume arXiv (will fail if ID is invalid)
    return "arxiv"


async def ingest_paper(
    paper_id: str,
    source: Optional[str] = None,
    force_refresh: bool = False,
    prefer_pdf: bool = False,
) -> StructuredPaper:
    """
    Main entry point for paper ingestion.

    Accepts arXiv IDs or bioRxiv/medRxiv DOIs and returns a fully
    structured paper ready for the AI visualization pipeline.

    Args:
        paper_id:      arXiv ID (e.g. "1706.03762") or DOI (e.g. "10.1101/2024.02.20.707059")
        source:        Explicit source hint: "arxiv", "biorxiv", or "medrxiv".
                       Auto-detected when None.
        force_refresh: Bypass cache and re-fetch.
        prefer_pdf:    Use PDF even when HTML is available (arXiv only).

    Returns:
        StructuredPaper with metadata and extracted sections.

    Raises:
        ValueError: Paper not found or parsing fails.
    """
    # --- Source detection & ID normalization ---
    if source is None:
        source = detect_paper_source(paper_id)

    if source == "arxiv":
        paper_id = normalize_arxiv_id(paper_id)
    else:
        # "rxiv" means DOI with server TBD; "biorxiv"/"medrxiv" are explicit
        paper_id = normalize_doi(paper_id)

    logger.info(f"Starting ingestion for paper: {paper_id} (source={source})")

    # Check cache
    if not force_refresh:
        cached = await get_cached_paper(paper_id)
        if cached:
            logger.info(f"Returning cached paper: {paper_id}")
            return cached

    # --- Step 1: Fetch metadata ---
    meta: ArxivPaperMeta
    if source == "arxiv":
        logger.info(f"Fetching arXiv metadata for: {paper_id}")
        meta = await fetch_paper_meta(paper_id)
    elif source in ("biorxiv", "medrxiv"):
        logger.info(f"Fetching {source} metadata for: {paper_id}")
        meta = await fetch_biorxiv_meta(paper_id, server=source)
    else:
        # "rxiv" – auto-detect between bioRxiv and medRxiv
        logger.info(f"Auto-detecting bioRxiv/medRxiv server for: {paper_id}")
        meta = await fetch_biorxiv_meta(paper_id, server=None)

    logger.info(f"Got paper: {meta.title!r} (source={meta.source})")

    # --- Step 2: Parse content ---
    content: ParsedContent

    if meta.source == "arxiv" and meta.html_url and not prefer_pdf:
        # arXiv: try ar5iv HTML first (cleaner structure)
        logger.info(f"Parsing ar5iv HTML: {meta.html_url}")
        try:
            content = await fetch_and_parse_html(meta.html_url)
            logger.info("Successfully parsed HTML content")
        except Exception as e:
            logger.warning(f"HTML parsing failed, falling back to PDF: {e}")
            content = await _parse_pdf_content(meta.pdf_url)
    else:
        # bioRxiv/medRxiv or arXiv without HTML: use PDF
        content = await _parse_pdf_content(meta.pdf_url)

    # Step 3: Extract sections
    logger.info("Extracting sections from parsed content")
    sections = extract_sections(content, meta)
    raw_count = len(sections)
    total_chars = sum(len(s.content) for s in sections)
    logger.info(f"Extracted {raw_count} raw sections ({total_chars:,} chars total)")

    # Step 4: Summarize + organize into <=5 sections (two-phase LLM pipeline)
    try:
        sections = await format_sections(sections, meta)
        logger.info(
            f"Section formatting succeeded: {raw_count} raw → {len(sections)} summarized sections"
        )
    except Exception as e:
        logger.error(
            f"Section formatting FAILED ({type(e).__name__}: {e}). "
            f"Falling back to {raw_count} raw sections. "
            f"This usually means the LLM call timed out or the API key is invalid."
        )

    # Step 5: Build final structure
    paper = StructuredPaper(
        meta=meta,
        sections=sections
    )

    # Step 6: Cache result
    await cache_paper(paper)

    logger.info(f"Ingestion complete for: {paper_id}")
    return paper


async def _parse_pdf_content(pdf_url: str) -> ParsedContent:
    """Helper to download and parse PDF."""
    logger.info(f"Downloading PDF: {pdf_url}")
    pdf_bytes = await download_pdf(pdf_url)
    logger.info(f"Downloaded {len(pdf_bytes)} bytes, parsing...")

    content = parse_pdf(pdf_bytes)
    logger.info(
        f"Parsed PDF: {len(content.raw_text)} chars, "
        f"{len(content.equations)} equations, "
        f"{len(content.figures)} figures, "
        f"{len(content.tables)} tables"
    )
    return content


async def get_cached_paper(arxiv_id: str) -> Optional[StructuredPaper]:
    """
    Check cache for previously processed paper.

    In production, this would check Redis/database.
    """
    return _paper_cache.get(arxiv_id)


async def cache_paper(paper: StructuredPaper) -> None:
    """
    Cache processed paper for future requests.

    In production, this would store in Redis/database.
    """
    _paper_cache[paper.meta.arxiv_id] = paper
    logger.debug(f"Cached paper: {paper.meta.arxiv_id}")


def clear_cache() -> None:
    """Clear the paper cache (useful for testing)."""
    _paper_cache.clear()
    logger.info("Paper cache cleared")


# Export public API
__all__ = [
    # Main functions
    "ingest_paper",
    "detect_paper_source",

    # Cache functions
    "get_cached_paper",
    "cache_paper",
    "clear_cache",

    # Lower-level functions for flexibility
    "fetch_paper_meta",
    "fetch_biorxiv_meta",
    "download_pdf",
    "fetch_html_content",
    "parse_pdf",
    "parse_html",
    "fetch_and_parse_html",
    "extract_sections",
    "format_sections",
    "normalize_arxiv_id",
    "normalize_doi",
    "validate_arxiv_id",
    "is_rxiv_doi",

    # Models (re-exported for convenience)
    "ArxivPaperMeta",
    "ParsedContent",
    "Section",
    "StructuredPaper",
]
