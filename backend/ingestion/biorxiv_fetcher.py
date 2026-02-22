"""
bioRxiv and medRxiv paper fetcher for the ingestion pipeline.

Uses the bioRxiv REST API (api.biorxiv.org) which serves both bioRxiv and medRxiv.
Falls back to PDF parsing since bioRxiv HTML structure differs from ar5iv.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Optional

import httpx

from models.paper import ArxivPaperMeta

logger = logging.getLogger(__name__)

BIORXIV_API_BASE = "https://api.biorxiv.org/details"


def normalize_doi(doi: str) -> str:
    """
    Normalize a DOI by removing URL prefixes and version suffixes.

    Examples:
        "https://doi.org/10.1101/2024.02.20.707059" -> "10.1101/2024.02.20.707059"
        "10.1101/2024.02.20.707059v2"                -> "10.1101/2024.02.20.707059"
    """
    doi = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:", "DOI:"):
        if doi.lower().startswith(prefix.lower()):
            doi = doi[len(prefix):]
    # Strip trailing version suffix like v1, v2
    doi = re.sub(r'v\d+$', '', doi)
    return doi.strip("/")


def is_rxiv_doi(doi: str) -> bool:
    """Return True if this looks like a bioRxiv/medRxiv DOI."""
    doi = normalize_doi(doi)
    return doi.startswith("10.1101/") or doi.startswith("10.64898/")


async def detect_server(doi: str) -> str:
    """
    Detect whether a DOI belongs to bioRxiv or medRxiv by querying both APIs.

    Returns "biorxiv" or "medrxiv".
    Raises ValueError if the DOI is not found on either server.
    """
    doi = normalize_doi(doi)
    for server in ("biorxiv", "medrxiv"):
        url = f"{BIORXIV_API_BASE}/{server}/{doi}/na/1"
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url)
                data = response.json()
                if data.get("collection"):
                    logger.info(f"Auto-detected server: {server} for DOI {doi}")
                    return server
        except Exception as exc:
            logger.debug(f"Error probing {server} for {doi}: {exc}")

    raise ValueError(
        f"DOI '{doi}' was not found on bioRxiv or medRxiv. "
        "Please verify the DOI is correct and the preprint has been posted."
    )


async def fetch_biorxiv_meta(doi: str, server: Optional[str] = None) -> ArxivPaperMeta:
    """
    Fetch paper metadata from the bioRxiv/medRxiv API.

    Args:
        doi:    DOI string, e.g. "10.1101/2024.02.20.707059" (version suffix optional)
        server: "biorxiv" or "medrxiv".  Auto-detected when None.

    Returns:
        ArxivPaperMeta populated from the API response.

    Raises:
        ValueError: Paper not found or invalid DOI.
        httpx.HTTPError: Network / HTTP failure.
    """
    doi = normalize_doi(doi)

    if server is None:
        server = await detect_server(doi)

    url = f"{BIORXIV_API_BASE}/{server}/{doi}/na/1"
    logger.info(f"Fetching {server} metadata from {url}")

    max_retries = 3
    last_error: Exception = RuntimeError("Unknown error")

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
            break
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_error = exc
            wait = 2 ** attempt
            logger.warning(f"Network error fetching {server} metadata (attempt {attempt + 1}): {exc}. Retrying in {wait}s")
            await asyncio.sleep(wait)
    else:
        raise ConnectionError(f"Could not fetch {server} metadata for '{doi}' after {max_retries} retries: {last_error}")

    collection = data.get("collection", [])
    if not collection:
        status_msg = ""
        messages = data.get("messages", [])
        if messages:
            status_msg = f" (API: {messages[0].get('status', '')})"
        raise ValueError(f"Paper '{doi}' not found on {server}{status_msg}")

    # The API returns one entry per version; use the latest (last in list)
    paper = collection[-1]

    version = str(paper.get("version", "1"))
    base_url = "https://www.biorxiv.org" if server == "biorxiv" else "https://www.medrxiv.org"
    pdf_url = f"{base_url}/content/{doi}v{version}.full.pdf"
    # HTML is available but structure differs from ar5iv; set to None so PDF path is used
    html_url: Optional[str] = None

    # Authors: the API returns a semicolon-separated string
    authors_raw = paper.get("authors", "")
    if isinstance(authors_raw, str):
        authors = [a.strip() for a in authors_raw.split(";") if a.strip()]
    elif isinstance(authors_raw, list):
        authors = [str(a) for a in authors_raw if a]
    else:
        authors = []

    # Publication date
    published: Optional[datetime] = None
    date_str = paper.get("date") or paper.get("prepub_date")
    if date_str:
        try:
            published = datetime.strptime(str(date_str), "%Y-%m-%d")
        except ValueError:
            pass

    category = paper.get("category", "")
    categories = [category] if category else []

    return ArxivPaperMeta(
        arxiv_id=doi,
        source=server,  # type: ignore[arg-type]
        title=(paper.get("title") or "").strip(),
        authors=authors,
        abstract=(paper.get("abstract") or "").strip(),
        published=published,
        updated=published,
        categories=categories,
        pdf_url=pdf_url,
        html_url=html_url,
    )
