"""ZotMCP - MCP server for searching academic Zotero library.

This server provides tools for semantic search, literature review, and
citation retrieval from a ChromaDB-indexed Zotero library.
"""

import json
import os
from pathlib import Path
from typing import Optional

import chromadb
from fastmcp import FastMCP
from chromadb.config import Settings as ChromaSettings

from models import ZoteroReference, ResearchResult

# Initialize MCP server
mcp = FastMCP("ZotMCP - Academic Literature Search")

# ChromaDB configuration
CACHE_DIR = Path(__file__).parent.parent / ".cache"
VECTORS_DIR = CACHE_DIR / "zotero-prosocial-fulltext" / "files"
COLLECTION_NAME = "prosocial_zot"

# Initialize ChromaDB client
chroma_client = None
collection = None


def get_collection():
    """Lazy-load ChromaDB collection."""
    global chroma_client, collection

    if collection is not None:
        return collection

    if not VECTORS_DIR.exists():
        raise FileNotFoundError(
            f"ChromaDB not found at {VECTORS_DIR}. "
            "Run: ./scripts/package_for_distribution.sh download"
        )

    chroma_client = chromadb.PersistentClient(
        path=str(VECTORS_DIR), settings=ChromaSettings(anonymized_telemetry=False)
    )

    collection = chroma_client.get_collection(name=COLLECTION_NAME)
    return collection


def extract_citation_metadata(
    metadata: dict,
) -> tuple[str, Optional[str], Optional[str]]:
    """Extract citation, DOI, and URI from ChromaDB metadata.

    Args:
        metadata: ChromaDB document metadata

    Returns:
        Tuple of (citation, doi, uri)
    """
    # Extract citation components
    authors = metadata.get("creators", "Unknown")
    title = metadata.get("document_title", metadata.get("title", "Untitled"))
    date = metadata.get("date", "")
    year = date[:4] if date else "n.d."

    # Build citation
    citation = f"{authors} ({year}). {title}"

    # Add publication venue if available
    publication = metadata.get("publicationTitle", metadata.get("publisher"))
    if publication:
        citation += f". {publication}"

    doi = metadata.get("DOI")
    uri = metadata.get("url", metadata.get("uri"))

    return citation, doi, uri


def clean_metadata(metadata: dict) -> dict:
    """Extract user-relevant metadata from ChromaDB record."""
    clean = {}

    # Core bibliographic fields
    user_fields = {
        "document_title": "title",
        "title": "title",
        "creators": "authors",
        "date": "date",
        "publicationTitle": "journal",
        "publisher": "publisher",
        "DOI": "doi",
        "url": "url",
        "itemType": "type",
        "abstractNote": "abstract",
        "item_key": "zotero_key",
    }

    for source_key, dest_key in user_fields.items():
        if source_key in metadata:
            clean[dest_key] = metadata[source_key]

    return clean


@mcp.tool()
def search(query: str, n_results: int = 10, filter_type: Optional[str] = None) -> str:
    """Search the Zotero library using semantic similarity.

    Args:
        query: Natural language search query
        n_results: Number of results to return (default: 10, max: 50)
        filter_type: Optional filter by item type (e.g., 'journalArticle', 'book', 'bookSection')

    Returns:
        JSON string with search results including titles, authors, and relevance
    """
    coll = get_collection()
    n_results = min(n_results, 50)

    # Build filter if specified
    where_filter = None
    if filter_type:
        where_filter = {"itemType": {"$eq": filter_type}}

    results = coll.query(
        query_texts=[query],
        n_results=n_results,
        include=["metadatas", "documents", "distances"],
        where=where_filter,
    )

    formatted_results = []
    for doc, meta, dist in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        citation, doi, uri = extract_citation_metadata(meta)
        clean_meta = clean_metadata(meta)

        formatted_results.append(
            {
                "citation": citation,
                "excerpt": doc[:500] + "..." if len(doc) > 500 else doc,
                "similarity": round(1 - dist, 3),
                "metadata": clean_meta,
                "doi": doi,
                "url": uri,
            }
        )

    return json.dumps(
        {
            "query": query,
            "total_results": len(formatted_results),
            "results": formatted_results,
        },
        indent=2,
    )


@mcp.tool()
def get_item(item_key: str) -> str:
    """Retrieve full text and metadata for a specific Zotero item.

    Args:
        item_key: Zotero item key

    Returns:
        JSON string with full item content and metadata
    """
    coll = get_collection()

    results = coll.get(
        where={"item_key": {"$eq": item_key}}, include=["metadatas", "documents"]
    )

    if not results["documents"]:
        return json.dumps({"error": f"Item {item_key} not found"})

    # TODO: just return the zotero link using the python zotero library
    raise NotImplementedError("Integration with Zotero cloud sync is not yet built.")


@mcp.tool()
def get_similar_items(item_key: str, n_results: int = 5) -> str:
    """Find items similar to a given Zotero item.

    Args:
        item_key: Zotero item key to find similar items for
        n_results: Number of similar items to return (default: 5)

    Returns:
        JSON string with similar items and their citations
    """
    coll = get_collection()

    # First get the item
    item_results = coll.get(
        where={"item_key": {"$eq": item_key}}, include=["documents"], limit=1
    )

    if not item_results["documents"]:
        return json.dumps({"error": f"Item {item_key} not found"})

    # Use the first chunk as query
    query_text = item_results["documents"][0]

    # Search for similar items (excluding the query item itself)
    results = coll.query(
        query_texts=[query_text],
        n_results=n_results + 5,  # Get extra to filter out the original
        include=["metadatas", "distances"],
    )

    similar_items = []
    seen_keys = set()

    # TODO: formalise the results in a pydantic object
    for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
        key = meta.get("item_key")
        if key and key != item_key and key not in seen_keys:
            citation, doi, uri = extract_citation_metadata(meta)
            similar_items.append(
                {
                    "item_key": key,
                    "citation": citation,
                    "similarity": round(1 - dist, 3),
                    "doi": doi,
                    "url": uri,
                    "metadata": clean_metadata(meta),
                }
            )
            seen_keys.add(key)

            if len(similar_items) >= n_results:
                break

    return json.dumps(
        {"source_item": item_key, "similar_items": similar_items}, indent=2
    )


@mcp.tool()
def get_collection_info() -> str:
    """Get information about the Zotero library collection.

    Returns:
        JSON string with collection statistics and metadata
    """
    coll = get_collection()

    total_chunks = coll.count()

    # Get sample to understand item types
    sample = coll.get(limit=100, include=["metadatas"])

    # Count unique items
    unique_items = set()
    item_types = {}

    for meta in sample["metadatas"]:
        item_key = meta.get("item_key")
        if item_key:
            unique_items.add(item_key)

        item_type = meta.get("itemType", "unknown")
        item_types[item_type] = item_types.get(item_type, 0) + 1

    return json.dumps(
        {
            "collection_name": COLLECTION_NAME,
            "total_chunks": total_chunks,
            "estimated_unique_items": len(unique_items) * (total_chunks // 100),
            "sample_item_types": item_types,
            "embedding_model": "gemini-embedding-001",
            "dimensions": 3072,
        },
        indent=2,
    )


@mcp.tool()
def assisted_search(research_question: str, max_sources: int = 10) -> str:
    """Perform an assisted literature search with LLM synthesis.

    This tool searches the library, retrieves relevant sources, and provides
    a synthesized response with proper academic citations.

    Args:
        research_question: The research question or topic to investigate
        max_sources: Maximum number of sources to include (default: 10)

    Returns:
        JSON string with synthesized response and literature references
    """
    # Perform semantic search
    search_results = search(query=research_question, n_results=max_sources * 2)
    search_data = json.loads(search_results)

    # Extract top results
    references = []
    for result in search_data["results"][:max_sources]:
        ref = ZoteroReference(
            citation=result["citation"],
            summary=f"Relevant excerpt: {result['excerpt'][:200]}...",
            doi=result.get("doi"),
            uri=result.get("url"),
            item_key=result["metadata"].get("zotero_key"),
        )
        references.append(ref)

    # Create research result
    # Note: In a full implementation, this would use an LLM to synthesize
    # For now, we provide the structured data for the client to work with
    result = ResearchResult(
        response=f"Found {len(references)} relevant sources on: {research_question}",
        summary=f"Search returned {len(references)} academic sources related to the research question.",
        literature=references,
        search_queries=[research_question],
    )

    return result.model_dump_json(indent=2)


@mcp.tool()
def search_by_author(author_name: str, n_results: int = 20) -> str:
    """Search for items by a specific author.

    Args:
        author_name: Author name to search for (can be partial)
        n_results: Number of results to return

    Returns:
        JSON string with items by the specified author
    """
    coll = get_collection()

    # ChromaDB doesn't support full-text metadata search well,
    # so we do a broader search and filter
    results = coll.get(limit=1000, include=["metadatas", "documents"])

    matching_items = {}

    for doc, meta in zip(results["documents"], results["metadatas"]):
        creators = meta.get("creators", "")
        if author_name.lower() in creators.lower():
            item_key = meta.get("item_key")
            if item_key and item_key not in matching_items:
                citation, doi, uri = extract_citation_metadata(meta)
                matching_items[item_key] = {
                    "item_key": item_key,
                    "citation": citation,
                    "doi": doi,
                    "url": uri,
                    "metadata": clean_metadata(meta),
                }

            if len(matching_items) >= n_results:
                break

    return json.dumps(
        {
            "author": author_name,
            "total_results": len(matching_items),
            "items": list(matching_items.values()),
        },
        indent=2,
    )


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
