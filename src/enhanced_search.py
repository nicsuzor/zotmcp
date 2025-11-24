"""Enhanced search engine with fuzzy matching and hybrid search capabilities.

This module provides high-level search functions that combine semantic search
with fuzzy metadata matching for improved discovery.
"""

from typing import Optional

from buttermilk.tools import ChromaDBSearchTool

from search_utils import (
    SearchResult,
    combine_scores,
    deduplicate_results,
    filter_by_date_range,
    filter_corrupted_results,
    fuzzy_match_author,
    fuzzy_match_metadata,
    get_metadata_field,
    rank_results,
    search_by_citation_key,
    search_by_doi,
)


async def fuzzy_metadata_search(
    collection,
    query: str,
    n_results: int = 20,
    search_fields: list[str] = None,
    fuzzy_threshold: int = 60,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
    item_type: Optional[str] = None,
    max_items_to_scan: int = 5000,
) -> list[SearchResult]:
    """Search metadata fields using fuzzy string matching.

    This performs a pure metadata search without semantic embeddings.
    Useful for finding items by partial titles, author names with typos, etc.

    Args:
        collection: ChromaDB collection
        query: Search query
        n_results: Maximum number of results to return
        search_fields: List of metadata fields to search (default: common fields)
        fuzzy_threshold: Minimum fuzzy match score (0-100)
        date_from: Earliest year filter
        date_to: Latest year filter
        item_type: Filter by itemType (e.g., 'journalArticle')
        max_items_to_scan: Maximum items to scan (prevents excessive memory use)

    Returns:
        List of SearchResult objects ranked by fuzzy score
    """
    # Fetch items from ChromaDB
    # Note: This is a limitation of ChromaDB - no full-text search on metadata
    # so we have to fetch items and filter in Python
    results = collection.get(
        limit=max_items_to_scan, include=["metadatas", "documents"]
    )

    matched_results = []
    seen_items = set()

    for doc, meta in zip(results["documents"], results["metadatas"]):
        item_key = meta.get("item_key") or meta.get("document_id")
        if not item_key or item_key in seen_items:
            continue

        # Apply filters
        # Use helper to get itemType from flat or nested structure
        if item_type and get_metadata_field(meta, "itemType") != item_type:
            continue

        if not filter_by_date_range(meta, date_from, date_to):
            continue

        # Fuzzy match against metadata fields
        is_match, score, matched_field = fuzzy_match_metadata(
            query, meta, search_fields, fuzzy_threshold
        )

        if is_match:
            result = SearchResult(
                item_key=item_key,
                metadata=meta,
                document=doc,
                fuzzy_score=score,
                match_field=matched_field,
            )
            matched_results.append(result)
            seen_items.add(item_key)

            # Stop if we have enough results
            if len(matched_results) >= n_results * 2:  # Get extra for ranking
                break

    # Rank by fuzzy score and limit
    ranked = rank_results(matched_results, sort_by="fuzzy")
    return ranked[:n_results]


async def fuzzy_author_search(
    collection,
    author_name: str,
    n_results: int = 20,
    fuzzy_threshold: int = 70,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
    item_type: Optional[str] = None,
    max_items_to_scan: int = 5000,
) -> list[SearchResult]:
    """Search for items by author name with fuzzy matching.

    This replaces the inefficient search_zotero_by_author function with
    proper fuzzy matching and ranking.

    Args:
        collection: ChromaDB collection
        author_name: Author name to search for
        n_results: Maximum number of results
        fuzzy_threshold: Minimum match score (0-100)
        date_from: Earliest year filter
        date_to: Latest year filter
        item_type: Filter by itemType
        max_items_to_scan: Maximum items to scan

    Returns:
        List of SearchResult objects ranked by fuzzy score
    """
    results = collection.get(
        limit=max_items_to_scan, include=["metadatas", "documents"]
    )

    matched_results = []
    seen_items = set()

    for doc, meta in zip(results["documents"], results["metadatas"]):
        item_key = meta.get("item_key") or meta.get("document_id")
        if not item_key or item_key in seen_items:
            continue

        # Apply filters
        # Use helper to get itemType from flat or nested structure
        if item_type and get_metadata_field(meta, "itemType") != item_type:
            continue

        if not filter_by_date_range(meta, date_from, date_to):
            continue

        # Fuzzy match author name
        # Use helper to get creators from flat or nested structure
        creators = get_metadata_field(meta, "creators") or ""
        is_match, score, matched_name = fuzzy_match_author(
            author_name, creators, fuzzy_threshold
        )

        if is_match:
            result = SearchResult(
                item_key=item_key,
                metadata=meta,
                document=doc,
                fuzzy_score=score,
                match_field="creators",
            )
            matched_results.append(result)
            seen_items.add(item_key)

    # Rank by fuzzy score and limit
    ranked = rank_results(matched_results, sort_by="fuzzy")
    return ranked[:n_results]


async def hybrid_search(
    search_tool: ChromaDBSearchTool,
    collection,
    query: str,
    n_results: int = 20,
    semantic_weight: float = 0.6,
    fuzzy_weight: float = 0.4,
    fuzzy_threshold: int = 50,
    search_fields: list[str] = None,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
    item_type: Optional[str] = None,
    exclude_corrupted: bool = True,
) -> list[SearchResult]:
    """Hybrid search combining semantic similarity and fuzzy metadata matching.

    This provides the best of both worlds:
    - Semantic search for conceptual relevance
    - Fuzzy matching for exact title/author queries

    Args:
        search_tool: Buttermilk ChromaDBSearchTool for semantic search
        collection: ChromaDB collection for metadata access
        query: Search query
        n_results: Maximum number of results
        semantic_weight: Weight for semantic score (0-1)
        fuzzy_weight: Weight for fuzzy score (0-1)
        fuzzy_threshold: Minimum fuzzy match score
        search_fields: Metadata fields to search
        date_from: Earliest year filter
        date_to: Latest year filter
        item_type: Filter by itemType

    Returns:
        List of SearchResult objects ranked by combined score
    """
    # Run semantic search
    semantic_results = await search_tool.search(query=query, n_results=n_results * 3)

    # Build hybrid results
    hybrid_results = []

    for result in semantic_results:
        meta = result.metadata
        item_key = meta.get("item_key") or meta.get("document_id")

        # Apply filters
        # Use helper to get itemType from flat or nested structure
        if item_type and get_metadata_field(meta, "itemType") != item_type:
            continue

        if not filter_by_date_range(meta, date_from, date_to):
            continue

        # Calculate fuzzy score for this item
        is_match, fuzzy_score, matched_field = fuzzy_match_metadata(
            query, meta, search_fields, fuzzy_threshold
        )

        # Combine scores
        combined = combine_scores(
            result.score, fuzzy_score if is_match else 0, semantic_weight, fuzzy_weight
        )

        hybrid_result = SearchResult(
            item_key=item_key,
            metadata=meta,
            document=result.content,
            similarity_score=result.score,
            fuzzy_score=fuzzy_score if is_match else 0,
            combined_score=combined,
            match_field=matched_field if is_match else None,
        )
        hybrid_results.append(hybrid_result)

    # Deduplicate and rank by combined score
    deduplicated = deduplicate_results(hybrid_results)
    ranked = rank_results(deduplicated, sort_by="combined")

    if exclude_corrupted:
        filtered = filter_corrupted_results(ranked)
        return filtered[:n_results]
    else:
        return ranked[:n_results]


async def search_by_doi_async(collection, doi: str) -> Optional[dict]:
    """Search for an item by DOI (exact match).

    Args:
        collection: ChromaDB collection
        doi: DOI to search for

    Returns:
        Metadata dict if found, None otherwise
    """
    # Fetch all metadata (or use a reasonable limit)
    results = collection.get(limit=10000, include=["metadatas"])
    return search_by_doi(doi, results["metadatas"])


async def search_by_citation_key_async(collection, citation_key: str) -> Optional[dict]:
    """Search for an item by BetterBibTeX citation key.

    Args:
        collection: ChromaDB collection
        citation_key: Citation key to search for

    Returns:
        Metadata dict if found, None otherwise
    """
    results = collection.get(limit=10000, include=["metadatas"])
    return search_by_citation_key(citation_key, results["metadatas"])


async def advanced_search(
    search_tool: ChromaDBSearchTool,
    collection,
    query: str,
    n_results: int = 20,
    search_mode: str = "hybrid",
    author: Optional[str] = None,
    title: Optional[str] = None,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
    item_type: Optional[str] = None,
    fuzzy_threshold: int = 60,
    semantic_weight: float = 0.6,
    exclude_corrupted: bool = True,
) -> list[SearchResult]:
    """Advanced search with multiple modes and filters.

    This is the most flexible search function, supporting:
    - Multiple search modes (semantic, metadata, hybrid)
    - Field-specific searches (author, title)
    - Date range filtering
    - Item type filtering

    Args:
        search_tool: Buttermilk ChromaDBSearchTool
        collection: ChromaDB collection
        query: Main search query
        n_results: Maximum number of results
        search_mode: "semantic", "metadata", or "hybrid"
        author: Optional author name to filter by
        title: Optional title to search for
        date_from: Earliest year filter
        date_to: Latest year filter
        item_type: Filter by itemType
        fuzzy_threshold: Minimum fuzzy match score
        semantic_weight: Weight for semantic score in hybrid mode

    Returns:
        List of SearchResult objects
    """
    # If author or title specified, override query for metadata searches
    if author:
        search_query = author
        search_fields = ["creators"]
        search_func = fuzzy_author_search
    elif title:
        search_query = title
        search_fields = ["title"]
        search_func = fuzzy_metadata_search
    else:
        search_query = query
        search_fields = None
        search_func = None

    # Execute search based on mode
    if search_mode == "semantic":
        # Pure semantic search
        semantic_results = await search_tool.search(
            query=search_query, n_results=n_results * 2
        )

        results = []
        for result in semantic_results:
            meta = result.metadata
            item_key = meta.get("item_key") or meta.get("document_id")

            # Apply filters
            if item_type and meta.get("itemType") != item_type:
                continue
            if not filter_by_date_range(meta, date_from, date_to):
                continue

            results.append(
                SearchResult(
                    item_key=item_key,
                    metadata=meta,
                    document=result.content,
                    similarity_score=result.score,
                    combined_score=result.score * 100,  # Normalize to 0-100
                )
            )

        # Deduplicate and rank
        results = deduplicate_results(results)
        results = rank_results(results, sort_by="combined")

        if exclude_corrupted:
            results = filter_corrupted_results(results)

        return results[:n_results]

    elif search_mode == "metadata":
        # Pure metadata search
        if search_func == fuzzy_author_search:
            return await fuzzy_author_search(
                collection,
                search_query,
                n_results,
                fuzzy_threshold,
                date_from,
                date_to,
                item_type,
            )
        else:
            return await fuzzy_metadata_search(
                collection,
                search_query,
                n_results,
                search_fields,
                fuzzy_threshold,
                date_from,
                date_to,
                item_type,
            )

    else:  # hybrid
        return await hybrid_search(
            search_tool,
            collection,
            search_query,
            n_results,
            semantic_weight,
            1 - semantic_weight,  # fuzzy_weight
            fuzzy_threshold,
            search_fields,
            date_from,
            date_to,
            item_type,
            exclude_corrupted,
        )
