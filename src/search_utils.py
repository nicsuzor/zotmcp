"""Advanced search utilities with fuzzy matching and metadata filtering.

This module provides enhanced search capabilities including:
- Fuzzy string matching for metadata fields
- Author name normalization and matching
- Advanced filtering by date, type, and multi-field queries
- Hybrid semantic + metadata search
"""

import re
from dataclasses import dataclass
from typing import Any, Optional

from rapidfuzz import fuzz, process


@dataclass
class SearchResult:
    """Represents a search result with metadata and scoring."""

    item_key: str
    metadata: dict
    document: Optional[str] = None
    similarity_score: Optional[float] = None  # Semantic similarity (0-1)
    fuzzy_score: Optional[float] = None  # Fuzzy match score (0-100)
    combined_score: Optional[float] = None  # Hybrid score
    match_field: Optional[str] = None  # Which field matched (for debugging)


def normalize_author_name(name: str) -> str:
    """Normalize author name for comparison.

    Handles various name formats:
    - "Smith, John" -> "john smith"
    - "John Smith" -> "john smith"
    - "Smith, J." -> "j smith"

    Args:
        name: Author name in any format

    Returns:
        Normalized lowercase name without punctuation
    """
    # Remove common punctuation and extra whitespace
    normalized = re.sub(r"[.,;:]", " ", name.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def extract_author_names(creators_field: str) -> list[str]:
    """Extract individual author names from a creators field.

    Args:
        creators_field: Comma-separated list of authors or JSON string

    Returns:
        List of normalized author names
    """
    if not creators_field:
        return []

    # Handle various formats: "Smith, John; Doe, Jane" or "Smith, John, Doe, Jane"
    # Split by semicolon first (preferred format), then by comma pairs
    authors = []

    # Try semicolon separation first
    parts = creators_field.split(";")
    if len(parts) > 1:
        authors = [normalize_author_name(part) for part in parts]
    else:
        # Fall back to comma separation (be careful with "Last, First" format)
        # Simple heuristic: if we see pattern "Word, Word," it's likely "Last, First,"
        parts = creators_field.split(",")
        if len(parts) >= 2:
            # Try to group as pairs for "Last, First" format
            i = 0
            while i < len(parts) - 1:
                full_name = f"{parts[i]}, {parts[i+1]}"
                authors.append(normalize_author_name(full_name))
                i += 2
            # Add remaining part if odd number
            if i < len(parts):
                authors.append(normalize_author_name(parts[i]))
        else:
            authors = [normalize_author_name(creators_field)]

    return [a for a in authors if a]  # Filter empty strings


def fuzzy_match_author(
    query_name: str, creators_field: str, threshold: int = 70
) -> tuple[bool, float, str]:
    """Match author name against creators field using fuzzy matching.

    Args:
        query_name: Author name to search for
        creators_field: Creators metadata field
        threshold: Minimum score to consider a match (0-100)

    Returns:
        Tuple of (is_match, best_score, matched_name)
    """
    if not creators_field:
        return False, 0.0, ""

    query_normalized = normalize_author_name(query_name)
    author_names = extract_author_names(creators_field)

    if not author_names:
        # Fallback to direct comparison
        author_names = [normalize_author_name(creators_field)]

    # Try different matching strategies
    best_score = 0.0
    best_match = ""

    for author in author_names:
        # Strategy 1: Token sort ratio (handles word order differences)
        score1 = fuzz.token_sort_ratio(query_normalized, author)

        # Strategy 2: Partial ratio (handles partial name matches)
        score2 = fuzz.partial_ratio(query_normalized, author)

        # Strategy 3: Simple ratio for exact-ish matches
        score3 = fuzz.ratio(query_normalized, author)

        # Take the best score across strategies
        max_score = max(score1, score2, score3)

        if max_score > best_score:
            best_score = max_score
            best_match = author

    is_match = best_score >= threshold
    return is_match, best_score, best_match


def fuzzy_match_title(
    query: str, title: str, threshold: int = 60
) -> tuple[bool, float]:
    """Match query against title using fuzzy matching.

    Args:
        query: Search query
        title: Title to match against
        threshold: Minimum score to consider a match (0-100)

    Returns:
        Tuple of (is_match, score)
    """
    if not title:
        return False, 0.0

    # Use token set ratio to handle word order and partial matches
    score = fuzz.token_set_ratio(query.lower(), title.lower())
    return score >= threshold, score


def fuzzy_match_metadata(
    query: str,
    metadata: dict,
    fields: list[str] = None,
    threshold: int = 60,
) -> tuple[bool, float, str]:
    """Match query against multiple metadata fields.

    Args:
        query: Search query
        metadata: Metadata dictionary
        fields: List of field names to search (default: common fields)
        threshold: Minimum score to consider a match

    Returns:
        Tuple of (is_match, best_score, matched_field)
    """
    if fields is None:
        fields = [
            "title",
            "publicationTitle",
            "publisher",
            "abstractNote",
            "creators",
        ]

    best_score = 0.0
    best_field = ""

    for field in fields:
        value = metadata.get(field, "")
        if not value:
            continue

        # Special handling for creators field
        if field == "creators":
            is_match, score, _ = fuzzy_match_author(query, value, threshold)
        else:
            is_match, score = fuzzy_match_title(query, str(value), threshold)

        if score > best_score:
            best_score = score
            best_field = field

    return best_score >= threshold, best_score, best_field


def parse_year_from_date(date_str: str) -> Optional[int]:
    """Extract year from a date string.

    Args:
        date_str: Date string in various formats (e.g., "2024", "2024-01-15", "Jan 2024")

    Returns:
        Year as integer, or None if not found
    """
    if not date_str:
        return None

    # Try to extract 4-digit year
    match = re.search(r"\b(19|20)\d{2}\b", str(date_str))
    if match:
        return int(match.group())

    return None


def filter_by_date_range(
    metadata: dict,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
) -> bool:
    """Filter metadata by date range.

    Args:
        metadata: Metadata dictionary
        date_from: Earliest year (inclusive)
        date_to: Latest year (inclusive)

    Returns:
        True if item falls within date range
    """
    if date_from is None and date_to is None:
        return True

    date_str = metadata.get("date", "")
    year = parse_year_from_date(date_str)

    if year is None:
        return False

    if date_from is not None and year < date_from:
        return False

    if date_to is not None and year > date_to:
        return False

    return True


def search_by_doi(doi: str, all_metadata: list[dict]) -> Optional[dict]:
    """Search for an item by DOI (exact match).

    Args:
        doi: DOI to search for
        all_metadata: List of all metadata dictionaries

    Returns:
        Matching metadata dict, or None if not found
    """
    doi_normalized = doi.lower().strip()

    # Remove common prefixes
    doi_normalized = re.sub(r"^(doi:|https?://doi.org/|https?://dx.doi.org/)", "", doi_normalized)

    for metadata in all_metadata:
        item_doi = metadata.get("DOI", "")
        if item_doi:
            item_doi_normalized = re.sub(
                r"^(doi:|https?://doi.org/|https?://dx.doi.org/)",
                "",
                item_doi.lower().strip(),
            )
            if doi_normalized == item_doi_normalized:
                return metadata

    return None


def search_by_citation_key(citation_key: str, all_metadata: list[dict]) -> Optional[dict]:
    """Search for an item by BetterBibTeX citation key (exact match).

    Args:
        citation_key: Citation key to search for
        all_metadata: List of all metadata dictionaries

    Returns:
        Matching metadata dict, or None if not found
    """
    key_normalized = citation_key.lower().strip()

    for metadata in all_metadata:
        item_key = metadata.get("citation_key", "")
        if item_key and item_key.lower().strip() == key_normalized:
            return metadata

    return None


def combine_scores(
    semantic_score: Optional[float],
    fuzzy_score: Optional[float],
    semantic_weight: float = 0.6,
    fuzzy_weight: float = 0.4,
) -> float:
    """Combine semantic and fuzzy scores with weighting.

    Args:
        semantic_score: Semantic similarity score (0-1)
        fuzzy_score: Fuzzy match score (0-100)
        semantic_weight: Weight for semantic score (default: 0.6)
        fuzzy_weight: Weight for fuzzy score (default: 0.4)

    Returns:
        Combined score (0-100 scale)
    """
    # Normalize semantic score to 0-100 scale
    semantic_normalized = (semantic_score or 0) * 100
    fuzzy_normalized = fuzzy_score or 0

    combined = (semantic_normalized * semantic_weight) + (fuzzy_normalized * fuzzy_weight)
    return round(combined, 2)


def rank_results(results: list[SearchResult], sort_by: str = "combined") -> list[SearchResult]:
    """Rank search results by score.

    Args:
        results: List of SearchResult objects
        sort_by: Field to sort by ("combined", "semantic", "fuzzy")

    Returns:
        Sorted list of results (highest score first)
    """
    if sort_by == "semantic":
        key_func = lambda r: r.similarity_score or 0
    elif sort_by == "fuzzy":
        key_func = lambda r: r.fuzzy_score or 0
    else:  # combined
        key_func = lambda r: r.combined_score or 0

    return sorted(results, key=key_func, reverse=True)


def deduplicate_results(results: list[SearchResult]) -> list[SearchResult]:
    """Remove duplicate results by item_key.

    Args:
        results: List of SearchResult objects

    Returns:
        Deduplicated list (keeps first occurrence)
    """
    seen = set()
    deduplicated = []

    for result in results:
        if result.item_key not in seen:
            seen.add(result.item_key)
            deduplicated.append(result)

    return deduplicated
