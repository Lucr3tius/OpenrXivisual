"""
Section formatting pipeline for ArXiviz.

Two-phase LLM pipeline:
  Phase 1: Holistic summarization -- LLM summarizes the entire paper to 30-40%
           of original length in beginner-friendly language.
  Phase 2: Section organization -- LLM organizes the summary into <=5 logical
           sections with descriptive headers.

Output populates both .content and .summary on each Section.
"""

import json
import logging
import os
import re

from agents.base import call_llm as call_llm_dedalus
from models.paper import ArxivPaperMeta, Equation, Figure, Section, Table

logger = logging.getLogger(__name__)

MAX_SECTIONS = 5


def _normalize_anthropic_model(model: str) -> str:
    """Map internal/default model strings to Anthropic-native names."""
    raw = model.split("/", 1)[-1]
    mapping = {
        "claude-sonnet-4-5-20250929": "claude-sonnet-4-5",
        "claude-haiku-4-5-20251001": "claude-haiku-4-5",
    }
    return mapping.get(raw, raw)


async def _call_formatter_llm(
    *,
    prompt: str,
    model: str,
    system_prompt: str,
    max_tokens: int,
) -> str:
    """
    Call LLM for section formatting.

    Uses Anthropic directly by default (for parser/summarizer telemetry),
    with Dedalus fallback if Anthropic key is not configured.
    """
    provider = os.getenv("SECTION_FORMATTER_PROVIDER", "anthropic").strip().lower()
    if provider in ("anthropic", "auto"):
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                from anthropic import AsyncAnthropic

                client = AsyncAnthropic(api_key=anthropic_key, timeout=300.0)
                response = await client.messages.create(
                    model=_normalize_anthropic_model(model),
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )
                text_parts = [
                    block.text
                    for block in response.content
                    if getattr(block, "type", None) == "text" and getattr(block, "text", None)
                ]
                return "\n".join(text_parts).strip()
            except Exception as e:
                logger.warning(f"Anthropic formatter call failed; falling back to Dedalus: {e}")
        elif provider == "anthropic":
            logger.warning("SECTION_FORMATTER_PROVIDER=anthropic but ANTHROPIC_API_KEY is missing; using Dedalus fallback")

    return await call_llm_dedalus(
        prompt=prompt,
        model=model,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
    )


# ---------------------------------------------------------------------------
# Pre-processing
# ---------------------------------------------------------------------------

def _prepare_paper_content(
    sections: list[Section],
    meta: ArxivPaperMeta,
) -> tuple[str, int]:
    """
    Concatenate all section content into a single document for summarization.

    Prepends the abstract from metadata if it's not already present as a section.
    Returns (full_text, word_count).
    """
    parts: list[str] = []

    # Add abstract from metadata if not in sections
    has_abstract = any(s.title.lower().strip() == "abstract" for s in sections)
    if meta.abstract and not has_abstract:
        parts.append(f"## Abstract\n\n{meta.abstract}")

    for section in sections:
        parts.append(f"## {section.title}\n\n{section.content}")

    full_text = "\n\n".join(parts)
    word_count = len(full_text.split())
    return full_text, word_count


# ---------------------------------------------------------------------------
# Phase 1: Holistic summarization
# ---------------------------------------------------------------------------

SUMMARIZE_SYSTEM_PROMPT = """\
You are an expert science communicator who makes academic papers accessible to newcomers.

Your task: Read the entire paper below and write a clear, approachable summary.

GOALS:
- Reduce to roughly {target_pct}% of the original length (~{target_words} words)
- Use language a smart person NEW to research can follow
- Explain the overall idea and core concepts, not every technical detail
- Make someone understand what this paper contributes and why it matters

KEEP (preserve fully):
- What the paper is about and why it matters (the "big picture")
- Core methodology -- how they did it, at a high level
- Key results and what they mean in plain language
- Important equations in LaTeX notation ($...$ inline, $$...$$ display) with a brief intuitive explanation of what each equation means
- Novel concepts and definitions, explained clearly
- Key figure/table references and their takeaways

CUT (remove aggressively):
- Detailed mathematical derivations and proofs (keep the statement, cut the steps)
- Hyperparameters, training schedules, and implementation specifics
- Extensive related work comparisons and literature reviews
- Boilerplate academic language ("In this section we...", "It is worth noting that...")
- Redundant explanations that restate what was already said
- Appendix material, author checklists, ethics statements

FORMATTING:
- Write in clean markdown with paragraph breaks for readability
- Use **bold** for key terms when first introduced
- Use bullet points sparingly for lists of results or contributions
- Preserve LaTeX notation for important equations
- Do NOT use TeX text styling commands like \textsc, \textbf, \mathrm for prose
- Write model names in plain text (e.g., "BERT Base", "BERT Large"), not split letters
- Do NOT invent information not in the source paper
- Do NOT start with "This paper..." or any preamble -- just begin explaining

Return ONLY the summarized text."""


async def _summarize_paper(
    full_content: str,
    paper_title: str,
    total_words: int,
    model: str,
) -> str:
    """
    Phase 1: Summarize the entire paper holistically.

    Returns plain markdown text at 30-40% of original length.
    """
    target_pct = 35  # aim for middle of 30-40% range
    target_words = max(300, int(total_words * target_pct / 100))

    system_prompt = (
        SUMMARIZE_SYSTEM_PROMPT
        .replace("{target_pct}", str(target_pct))
        .replace("{target_words}", str(target_words))
    )

    user_prompt = f"""Paper: "{paper_title}"
Original length: ~{total_words} words
Target summary length: ~{target_words} words

Full paper content:

{full_content}"""

    print(f"[FORMATTER] Phase 1: Summarizing paper ({total_words} words -> ~{target_words} words)...")

    result = await _call_formatter_llm(
        prompt=user_prompt,
        model=model,
        system_prompt=system_prompt,
        max_tokens=16000,
    )
    result = result.strip()
    result_words = len(result.split())
    compression = round(result_words / total_words * 100) if total_words > 0 else 0
    print(f"[FORMATTER] Phase 1 complete: {total_words} -> {result_words} words ({compression}% of original)")

    return result


# ---------------------------------------------------------------------------
# Phase 2: Section organization
# ---------------------------------------------------------------------------

ORGANIZE_SYSTEM_PROMPT = """\
You are organizing a summarized academic paper into clear, logical sections.

Given the summarized text of a research paper, split it into {max_sections} or fewer \
well-structured sections.

RULES:
1. Create at most {max_sections} sections (fewer is fine for shorter content).
2. Each section needs a clear, descriptive title -- NOT generic labels like \
"Section 1" or "Part A".
3. Good title examples: "The Core Idea", "How It Works", "Key Results and Findings", \
"Why This Matters".
4. Sections should flow logically, typically:
   - What is this about and why does it matter
   - How does it work (methodology)
   - What did they find (results)
   - What does it mean (discussion / implications)
5. Every piece of the input text must appear in exactly one section -- do NOT drop content.
6. Do NOT rewrite or modify the text -- just organize it into sections.
7. Do NOT add new content or commentary.

Return ONLY valid JSON (no markdown fences, no explanation):
{
  "sections": [
    {"title": "Descriptive Section Title", "content": "Section content here..."},
    ...
  ]
}"""


async def _organize_into_sections(
    summary_text: str,
    paper_title: str,
    model: str,
) -> list[dict]:
    """
    Phase 2: Organize summarized text into <=5 logical sections.

    Returns list of dicts with 'title' and 'content' keys.
    """
    system_prompt = ORGANIZE_SYSTEM_PROMPT.replace(
        "{max_sections}", str(MAX_SECTIONS)
    )

    user_prompt = f"""Paper: "{paper_title}"

Summarized text to organize into sections:

{summary_text}"""

    summary_words = len(summary_text.split())
    print(f"[FORMATTER] Phase 2: Organizing {summary_words} words into <={MAX_SECTIONS} sections...")

    raw_response = await _call_formatter_llm(
        prompt=user_prompt,
        model=model,
        system_prompt=system_prompt,
        max_tokens=16000,
    )
    raw_response = raw_response.strip()

    # Strip markdown code fences if present
    if raw_response.startswith("```"):
        lines = raw_response.split("\n")
        raw_response = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        )

    parsed = json.loads(raw_response)
    organized_sections = parsed["sections"]

    # Validate
    if not organized_sections:
        raise ValueError("LLM returned empty sections list")
    if len(organized_sections) > MAX_SECTIONS:
        # Truncate to max if LLM returned too many
        organized_sections = organized_sections[:MAX_SECTIONS]

    print(f"[FORMATTER] Phase 2 complete: {len(organized_sections)} sections")
    for s in organized_sections:
        wc = len(s["content"].split())
        print(f'  - "{s["title"]}": {wc} words')

    return organized_sections


# ---------------------------------------------------------------------------
# Fallback: deterministic split
# ---------------------------------------------------------------------------

def _fallback_split(text: str, max_sections: int = MAX_SECTIONS) -> list[dict]:
    """
    Deterministic fallback if the LLM organization call fails.

    Splits text on double-newline paragraph boundaries into roughly equal chunks,
    then assigns generic titles based on position.
    """
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    if not paragraphs:
        return [{"title": "Summary", "content": text.strip()}]

    target = min(max_sections, len(paragraphs))
    sections: list[dict] = []
    base_size = len(paragraphs) // target
    remainder = len(paragraphs) % target
    idx = 0

    fallback_titles = [
        "Introduction & Motivation",
        "Approach & Methodology",
        "Key Concepts",
        "Results & Findings",
        "Discussion & Implications",
    ]

    for i in range(target):
        size = base_size + (1 if i < remainder else 0)
        chunk = "\n\n".join(paragraphs[idx : idx + size])
        title = fallback_titles[i] if i < len(fallback_titles) else f"Part {i + 1}"
        sections.append({"title": title, "content": chunk})
        idx += size

    return sections


def _clean_display_text(text: str) -> str:
    """
    Clean common LLM/PDF formatting artifacts that break markdown rendering.

    Specifically normalizes split small-caps sequences such as:
      \\textsc
      L
      A
      R
      G
      E
    into:
      LARGE
    """
    if not text:
        return text

    cleaned = text

    # Remove zero-width characters.
    cleaned = re.sub(r"[\u200B-\u200D\uFEFF]", "", cleaned)

    # Remove \textsc marker while preserving inline word, e.g. \textscBASE -> BASE
    cleaned = re.sub(r"\\textsc\s*([A-Za-z]+)", r"\1", cleaned)
    cleaned = re.sub(r"\\textsc\b", "", cleaned)

    # Collapse letter-per-line runs: L\nA\nR\nG\nE -> LARGE
    cleaned = re.sub(
        r"(?m)^(?:[A-Z]\s*\n){2,}[A-Z]\s*$",
        lambda m: "".join(ch for ch in m.group(0) if ch.isalpha()),
        cleaned,
    )

    # Remove immediate duplicate line after collapse, e.g. LARGE\nLARGE
    cleaned = re.sub(r"(?m)^([A-Z]{2,})\n\1$", r"\1", cleaned)

    # Normalize excessive blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def _collect_unique_assets(
    sections: list[Section],
) -> tuple[list[Equation], list[Figure], list[Table]]:
    """Collect and dedupe equations/figures/tables from raw parsed sections."""
    equations: list[Equation] = []
    figures: list[Figure] = []
    tables: list[Table] = []

    seen_eq: set[str] = set()
    seen_fig: set[str] = set()
    seen_tbl: set[str] = set()

    for section in sections:
        for eq in section.equations:
            key = (eq.latex or "").strip()
            if not key or key in seen_eq:
                continue
            seen_eq.add(key)
            equations.append(eq)
        for fig in section.figures:
            key = (fig.id or "").strip()
            if not key or key in seen_fig:
                continue
            seen_fig.add(key)
            figures.append(fig)
        for tbl in section.tables:
            key = (tbl.id or "").strip()
            if not key or key in seen_tbl:
                continue
            seen_tbl.add(key)
            tables.append(tbl)

    return equations, figures, tables


def _match_equations(content: str, equations: list[Equation]) -> list[Equation]:
    normalized_content = re.sub(r"\s+", "", content)
    matched: list[Equation] = []
    for eq in equations:
        latex = (eq.latex or "").strip()
        if not latex:
            continue
        normalized_eq = re.sub(r"\s+", "", latex)
        if normalized_eq and normalized_eq in normalized_content:
            matched.append(eq)
    return matched


def _match_figures(content: str, figures: list[Figure]) -> list[Figure]:
    content_lower = content.lower()
    matched: list[Figure] = []
    for fig in figures:
        fig_id = (fig.id or "").lower()
        fig_num = fig_id.replace("figure-", "")
        caption = (fig.caption or "").lower()
        if (
            (fig_id and fig_id in content_lower)
            or (fig_num and f"figure {fig_num}" in content_lower)
            or (fig_num and f"fig. {fig_num}" in content_lower)
            or (fig_num and f"fig {fig_num}" in content_lower)
            or (caption and caption[:40] in content_lower)
        ):
            matched.append(fig)
    return matched


def _match_tables(content: str, tables: list[Table]) -> list[Table]:
    content_lower = content.lower()
    matched: list[Table] = []
    for tbl in tables:
        tbl_id = (tbl.id or "").lower()
        tbl_num = tbl_id.replace("table-", "")
        caption = (tbl.caption or "").lower()
        if (
            (tbl_id and tbl_id in content_lower)
            or (tbl_num and f"table {tbl_num}" in content_lower)
            or (caption and caption[:40] in content_lower)
        ):
            matched.append(tbl)
    return matched


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def format_sections(
    sections: list[Section],
    meta: ArxivPaperMeta,
    model: str = "claude-sonnet-4-5-20250929",
    max_concurrent: int = 5,
) -> list[Section]:
    """
    Summarize and organize paper sections for presentation.

    Phase 1: Holistic LLM summarization of the entire paper (30-40% of original).
    Phase 2: LLM organizes the summary into <= 5 logical sections.
    Output populates both .content and .summary on each Section.

    Args:
        sections: Sections from extract_sections()
        meta: Paper metadata for context
        model: Claude model identifier (e.g. "claude-sonnet-4-5-20250929")
        max_concurrent: Max concurrent API calls

    Returns:
        List of <= 5 sections with summarized .content and .summary
    """
    if not sections:
        return sections

    print(f"\n[FORMATTER] === Summarize & Organize pipeline: {len(sections)} input sections ===")
    logger.info(f"Starting summarize & organize pipeline for {len(sections)} sections")

    # --- Pre-processing: combine all sections into one document ---
    full_content, total_words = _prepare_paper_content(sections, meta)
    print(f"[FORMATTER] Total paper content: {total_words} words")

    # --- Phase 1: Holistic summarization ---
    try:
        summary_text = await _summarize_paper(full_content, meta.title, total_words, model)
    except Exception as e:
        logger.error(f"Phase 1 (summarization) failed: {e}")
        print(f"[FORMATTER] Phase 1 FAILED ({type(e).__name__}: {e}), aborting pipeline")
        raise RuntimeError(
            "Section summarization failed. No paper content was stored to avoid raw-text fallback."
        ) from e

    # --- Phase 2: Section organization ---
    try:
        organized = await _organize_into_sections(summary_text, meta.title, model)
    except Exception as e:
        logger.error(f"Phase 2 (organization) failed: {e}")
        print(f"[FORMATTER] Phase 2 FAILED ({type(e).__name__}: {e}), using fallback split")
        organized = _fallback_split(summary_text)

    # --- Build final Section objects ---
    all_equations, all_figures, all_tables = _collect_unique_assets(sections)
    used_eq_ids: set[str] = set()
    used_fig_ids: set[str] = set()
    used_tbl_ids: set[str] = set()

    result_sections: list[Section] = []
    for i, org_section in enumerate(organized):
        cleaned_content = _clean_display_text(org_section["content"])
        matched_eq = _match_equations(cleaned_content, all_equations)
        matched_figures = _match_figures(cleaned_content, all_figures)
        matched_tables = _match_tables(cleaned_content, all_tables)

        for eq in matched_eq:
            used_eq_ids.add((eq.latex or "").strip())
        for fig in matched_figures:
            used_fig_ids.add((fig.id or "").strip())
        for tbl in matched_tables:
            used_tbl_ids.add((tbl.id or "").strip())

        section = Section(
            id=f"{meta.arxiv_id}-section-{i + 1}",
            title=org_section["title"],
            level=1,
            content=cleaned_content,
            summary=cleaned_content,
            equations=matched_eq,
            figures=matched_figures,
            tables=matched_tables,
            parent_id=None,
        )
        result_sections.append(section)

    # Keep any unmatched assets so parsed visuals are never silently dropped.
    if result_sections:
        leftover_eq = [eq for eq in all_equations if (eq.latex or "").strip() not in used_eq_ids]
        leftover_fig = [fig for fig in all_figures if (fig.id or "").strip() not in used_fig_ids]
        leftover_tbl = [tbl for tbl in all_tables if (tbl.id or "").strip() not in used_tbl_ids]
        result_sections[0].equations.extend(leftover_eq)
        result_sections[0].figures.extend(leftover_fig)
        result_sections[0].tables.extend(leftover_tbl)

    print(f"[FORMATTER] === Pipeline complete: {len(result_sections)} final sections ===")
    total_output_words = 0
    for s in result_sections:
        wc = len(s.content.split())
        total_output_words += wc
        print(f'  - "{s.title}": {wc} words')
    compression = round(total_output_words / total_words * 100) if total_words > 0 else 0
    print(f"[FORMATTER] Total output: {total_output_words} words ({compression}% of original {total_words})")

    logger.info(f"Summarize & organize pipeline complete: {len(result_sections)} sections")
    return result_sections
