"""Citation search functionality using OpenAlex API.

This module provides tools for discovering academic literature through the OpenAlex API,
independent of the Zotero library. It's designed to work alongside zotero_tools to enable
comprehensive literature discovery and review workflows.
"""

from typing import Optional
import httpx


async def search_papers(
    query: str,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    limit: int = 20,
    sort: str = "relevance",
) -> str:
    """Search for academic papers using OpenAlex API.

    OpenAlex is a free, legal API with 240M+ works and good humanities coverage.
    No authentication needed, rate limit: 10 req/sec, 100k/day.

    Args:
        query: Search keywords
        year_from: Earliest publication year (optional)
        year_to: Latest publication year (optional)
        limit: Max results (1-100, default 20)
        sort: Sort order - "relevance", "cited_by_count", or "publication_date"

    Returns:
        Formatted string with paper metadata for LLM consumption
    """
    # Build OpenAlex API URL
    base_url = "https://api.openalex.org/works"

    # Build filter string for year ranges
    filters = []
    if year_from:
        filters.append(f"from_publication_date:{year_from}-01-01")
    if year_to:
        filters.append(f"to_publication_date:{year_to}-12-31")

    params = {
        "search": query,
        "sort": sort,
        "per_page": min(limit, 100),
        "mailto": "nic@suzor.com",  # For polite pool
    }

    if filters:
        params["filter"] = ",".join(filters)

    # Make API request
    async with httpx.AsyncClient() as client:
        response = await client.get(base_url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()

    # Process results
    results = []
    for work in data.get("results", []):
        paper = {
            "title": work.get("title", "Unknown"),
            "authors": [
                author.get("author", {}).get("display_name", "Unknown")
                for author in work.get("authorships", [])[:5]  # Limit to 5 authors
            ],
            "year": work.get("publication_year"),
            "doi": work.get("doi"),
            "citations": work.get("cited_by_count", 0),
            "abstract": None,
            "open_access": work.get("open_access", {}).get("is_oa", False),
            "pdf_url": work.get("open_access", {}).get("oa_url"),
            "openalex_id": work.get("id"),
        }

        # Convert inverted index abstract to text if present
        if inv_index := work.get("abstract_inverted_index"):
            word_positions = []
            for word, positions in inv_index.items():
                for pos in positions:
                    word_positions.append((pos, word))
            word_positions.sort()
            paper["abstract"] = " ".join([word for _, word in word_positions])

        results.append(paper)

    # Format for LLM
    output = f"# Search Results: {query}\n\n"
    output += f"Found {len(results)} papers\n\n"

    for i, paper in enumerate(results, 1):
        output += f"## {i}. {paper['title']}\n"
        output += f"**Authors:** {', '.join(paper['authors'])}\n"
        output += f"**Year:** {paper['year']}  |  **Citations:** {paper['citations']}\n"

        if paper['doi']:
            output += f"**DOI:** {paper['doi']}\n"

        if paper['abstract']:
            # Truncate long abstracts
            abstract = paper['abstract'][:500]
            if len(paper['abstract']) > 500:
                abstract += "... [truncated]"
            output += f"**Abstract:** {abstract}\n"

        if paper['open_access'] and paper['pdf_url']:
            output += f"**📄 Open Access PDF:** {paper['pdf_url']}\n"

        output += f"**OpenAlex ID:** {paper['openalex_id']}\n"
        output += "\n---\n\n"

    return output
