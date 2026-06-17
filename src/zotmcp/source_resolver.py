"""Resolve paper identifiers (DOI, arXiv ID) to metadata + best available PDF URL.

Resolution order:
  1. arXiv ID → arXiv API (free PDF always available)
  2. DOI → CrossRef for metadata + Unpaywall for OA PDF URL
  3. If Unpaywall misses → Semantic Scholar S2 open access PDF
  4. If still no PDF → returns metadata-only (pdf_url=None)

Uses httpx for all HTTP calls (already a project dependency).
"""
from __future__ import annotations

import logging
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# arXiv ID patterns:
#   2605.29800        (new-style, 4-digit + 5-digit)
#   2203.11171v3      (with version suffix)
#   arxiv:2605.29800  (prefixed)
ARXIV_PATTERN = re.compile(
    r"^(?:arxiv:)?(\d{4}\.\d{4,5}(?:v\d+)?)$", re.IGNORECASE
)

# Contact email for the CrossRef/Unpaywall polite pools. Override via the
# ZOTMCP_CONTACT_EMAIL env var; defaults to a non-personal project placeholder.
DEFAULT_EMAIL = os.environ.get("ZOTMCP_CONTACT_EMAIL", "zotmcp@example.com")


@dataclass
class PaperInfo:
    """Resolved paper metadata and PDF location."""

    title: str
    authors: list[str]
    year: Optional[int]
    doi: Optional[str]
    arxiv_id: Optional[str]
    abstract: Optional[str]
    item_type: str  # "preprint" for arXiv, "journalArticle" for DOI papers, etc.
    pdf_url: Optional[str]
    pdf_source: Optional[str]  # "arxiv", "unpaywall", "semantic_scholar", or None
    extra: str = ""  # e.g. "arXiv:2605.29800"


async def resolve_paper(
    identifier: str,
    email: str = DEFAULT_EMAIL,
    client: Optional[httpx.AsyncClient] = None,
) -> PaperInfo:
    """Resolve a paper identifier to metadata + best available PDF URL.

    Args:
        identifier: DOI (bare or with URL prefix), arXiv ID (e.g. "2605.29800"),
                    or "arxiv:2605.29800".
        email: Contact email for Unpaywall and CrossRef polite pool.
        client: Optional shared httpx.AsyncClient. When provided it is reused
                (and left open) for connection pooling; when omitted a client is
                created and closed locally.

    Returns:
        PaperInfo with metadata and best available pdf_url.
    """
    identifier = identifier.strip()

    # Detect arXiv ID
    m = ARXIV_PATTERN.match(identifier)
    if m:
        arxiv_id = m.group(1)
        return await _resolve_arxiv(arxiv_id, client=client)

    # Treat as DOI — strip URL prefix if present
    doi = identifier
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break

    return await _resolve_doi(doi, email=email, client=client)


async def _resolve_arxiv(
    arxiv_id: str, client: Optional[httpx.AsyncClient] = None
) -> PaperInfo:
    """Resolve an arXiv ID to metadata. PDF is always available at arxiv.org."""
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    try:
        resp = await client.get(url)
        resp.raise_for_status()
    finally:
        if owns_client:
            await client.aclose()

    # Parse Atom XML response
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    root = ET.fromstring(resp.content)
    entry = root.find("atom:entry", ns)

    if entry is None:
        raise ValueError(f"arXiv ID {arxiv_id} not found in arXiv API response")

    title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
    # Normalise whitespace in title (arXiv sometimes has newlines)
    title = " ".join(title.split())

    abstract = (
        entry.findtext("atom:summary", default="", namespaces=ns) or ""
    ).strip()

    # Authors
    authors: list[str] = []
    for author_el in entry.findall("atom:author", ns):
        name = author_el.findtext("atom:name", default="", namespaces=ns)
        if name:
            authors.append(name.strip())

    # Publication year from the published date (ISO 8601)
    published = entry.findtext("atom:published", default="", namespaces=ns) or ""
    year: Optional[int] = int(published[:4]) if published and published[:4].isdigit() else None

    # DOI cross-reference if present
    doi = entry.findtext("arxiv:doi", default=None, namespaces=ns)
    if doi:
        doi = doi.strip()

    # Construct PDF URL (strip version suffix for canonical URL)
    base_id = re.sub(r"v\d+$", "", arxiv_id)
    pdf_url = f"https://arxiv.org/pdf/{base_id}.pdf"

    extra = f"arXiv:{arxiv_id}"

    return PaperInfo(
        title=title,
        authors=authors,
        year=year,
        doi=doi,
        arxiv_id=arxiv_id,
        abstract=abstract,
        item_type="preprint",
        pdf_url=pdf_url,
        pdf_source="arxiv",
        extra=extra,
    )


async def _resolve_doi(
    doi: str,
    email: str = DEFAULT_EMAIL,
    client: Optional[httpx.AsyncClient] = None,
) -> PaperInfo:
    """Resolve a DOI via CrossRef + Unpaywall + Semantic Scholar fallback.

    CrossRef provides bibliographic metadata.
    Unpaywall provides the best OA PDF URL.
    Semantic Scholar fills in gaps if both previous sources miss.

    A shared ``client`` may be passed for connection pooling; it is left open
    for the caller to close. When omitted a client is created and closed here.
    """
    title: str = doi  # fallback if CrossRef fails
    authors: list[str] = []
    year: Optional[int] = None
    abstract: Optional[str] = None
    item_type: str = "journalArticle"

    pdf_url: Optional[str] = None
    pdf_source: Optional[str] = None

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    try:
        # ── CrossRef metadata ──────────────────────────────────────────────
        crossref_url = f"https://api.crossref.org/works/{doi}"
        try:
            resp = await client.get(
                crossref_url,
                headers={"User-Agent": f"zotmcp/1.0 (mailto:{email})"},
            )
            if resp.status_code == 200:
                resp_json = resp.json()
                work = (resp_json.get("message") or {}) if isinstance(resp_json, dict) else {}
                title_list = work.get("title") or []
                if title_list:
                    title = title_list[0]

                for a in (work.get("author") or []):
                    if not isinstance(a, dict):
                        continue
                    given = a.get("given", "")
                    family = a.get("family", "")
                    if given or family:
                        name = f"{given} {family}".strip()
                    else:
                        name = a.get("name", "")
                    if name:
                        authors.append(name)

                # Extract year from published dates
                for date_field in ("published-print", "published-online", "published"):
                    dp = work.get(date_field, {})
                    if dp:
                        parts = dp.get("date-parts", [[]])
                        if parts and parts[0]:
                            year = parts[0][0]
                            break

                abstract = work.get("abstract")
                item_type = _crossref_type_to_zotero(work.get("type", ""))
        except Exception as e:
            logger.warning(f"CrossRef lookup failed for DOI {doi}: {e}")

        # ── Unpaywall OA PDF ───────────────────────────────────────────────
        unpaywall_url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
        try:
            resp = await client.get(unpaywall_url)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and data.get("is_oa"):
                    best = data.get("best_oa_location") or {}
                    candidate = best.get("url_for_pdf")
                    if candidate:
                        pdf_url = candidate
                        pdf_source = "unpaywall"
        except Exception as e:
            logger.warning(f"Unpaywall lookup failed for DOI {doi}: {e}")

        # ── Semantic Scholar fallback ──────────────────────────────────────
        if not pdf_url:
            s2_url = (
                f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
                f"?fields=openAccessPdf,title,authors,year,abstract"
            )
            try:
                resp = await client.get(s2_url)
                if resp.status_code == 200:
                    s2data = resp.json()
                    if isinstance(s2data, dict):
                        oa_pdf = s2data.get("openAccessPdf") or {}
                        candidate = oa_pdf.get("url")
                        if candidate:
                            pdf_url = candidate
                            pdf_source = "semantic_scholar"
                        # Fill in metadata gaps from S2
                        if not title or title == doi:
                            title = s2data.get("title") or title
                        if not authors:
                            authors = [
                                a.get("name", "")
                                for a in (s2data.get("authors") or [])
                                if isinstance(a, dict)
                            ]
                        if year is None:
                            year = s2data.get("year")
                        if not abstract:
                            abstract = s2data.get("abstract")
            except Exception as e:
                logger.warning(f"Semantic Scholar lookup failed for DOI {doi}: {e}")
    finally:
        if owns_client:
            await client.aclose()

    return PaperInfo(
        title=title,
        authors=authors,
        year=year,
        doi=doi,
        arxiv_id=None,
        abstract=abstract,
        item_type=item_type,
        pdf_url=pdf_url,
        pdf_source=pdf_source,
        extra="",
    )


def _crossref_type_to_zotero(crossref_type: str) -> str:
    """Map a CrossRef work type string to the nearest Zotero item type."""
    mapping = {
        "journal-article": "journalArticle",
        "book": "book",
        "book-chapter": "bookSection",
        "proceedings-article": "conferencePaper",
        "dissertation": "thesis",
        "report": "report",
        "preprint": "preprint",
        "posted-content": "preprint",
        "dataset": "dataset",
        "monograph": "book",
        "edited-book": "book",
        "reference-entry": "encyclopediaArticle",
    }
    return mapping.get(crossref_type, "journalArticle")
