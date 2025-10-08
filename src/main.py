"""ZotMCP - MCP server for searching academic Zotero library.

This server provides tools for semantic search, literature review, and
citation retrieval from a ChromaDB-indexed Zotero library.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

from buttermilk import logger, init_async
from buttermilk.tools import ChromaDBSearchTool

# Global buttermilk instance
bm = None
search_tool = None



@asynccontextmanager
async def lifespan_manager(server: FastMCP):
    """Initialize buttermilk with zotero config on startup."""
    global bm, search_tool

    # Load zotero config - use absolute path from project root
    conf_dir = str(Path(__file__).parent.parent / "conf")
    bm = await init_async(config_dir=conf_dir, config_name="zotero")

    search_tool = get_search_tool()
    await search_tool.ensure_cache_initialized()

    logger.info("Buttermilk initialized")

    yield

    logger.info("Shutting down ZotMCP")

# Initialize MCP server with lifespan manager
mcp = FastMCP("ZotMCP - Academic Literature Search", lifespan=lifespan_manager)


def get_collection():
    """Get ChromaDB collection from buttermilk search tool.

    Note: This is used for direct ChromaDB operations that need custom filters
    or aggregations. For basic semantic search, use get_search_tool() instead.
    """
    return search_tool.collection


def get_search_tool():
    """Get or create buttermilk ChromaDBSearchTool instance."""
    global bm, search_tool

    if search_tool is not None:
        return search_tool

    storage_config = bm.cfg.storage.zotero_vectors
    search_tool = ChromaDBSearchTool(
        type="chromadb",
        collection_name=storage_config.collection_name,
        persist_directory=storage_config.persist_directory,
        embedding_model=storage_config.embedding_model,
        dimensionality=storage_config.dimensionality,
    )

    return search_tool


def extract_citation_metadata(
    metadata: dict,
) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
    """Extract citation, DOI/URL, URI, and Zotero key from ChromaDB metadata.

    Args:
        metadata: ChromaDB document metadata

    Returns:
        Tuple of (citation, doi_or_url, uri, zotero_key)
    """
    # These fields are already stored at top-level in ChromaDB metadata
    citation = metadata.get("citation", "Citation not available")
    doi_or_url = metadata.get("doi_or_url")
    uri = metadata.get("uri")
    zotero_key = metadata.get("document_id")  # document_id is the Zotero key

    return citation, doi_or_url, uri, zotero_key


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
async def search(
    query: str, n_results: int = 10, filter_type: Optional[str] = None
) -> dict:
    """Search the Zotero library using semantic similarity.

    Args:
        query: Natural language search query
        n_results: Number of results to return (default: 10, max: 50)
        filter_type: Optional filter by item type (e.g., 'journalArticle', 'book', 'bookSection')

    Returns:
        Dictionary with search results including titles, authors, and relevance
    """
    try:
        n_results = min(n_results, 50)

        # Use buttermilk's search tool
        tool = get_search_tool()
        results = await tool.search(query=query, n_results=n_results)

        formatted_results = []
        for result in results:
            # Filter by item type if specified
            if filter_type and result.metadata.get("itemType") != filter_type:
                continue

            citation, doi_or_url, uri, zotero_key = extract_citation_metadata(result.metadata)
            clean_meta = clean_metadata(result.metadata)

            # Create Zotero app link
            zotero_link = f"zotero://select/library/items/{zotero_key}" if zotero_key else None

            formatted_results.append(
                {
                    "citation": citation,
                    "excerpt": result.content,
                    "similarity": round(result.score, 3) if result.score else None,
                    "metadata": clean_meta,
                    "doi_or_url": doi_or_url,
                    "uri": uri,
                    "zotero_key": zotero_key,
                    "zotero_link": zotero_link,
                }
            )

        return {
            "query": query,
            "total_results": len(formatted_results),
            "results": formatted_results,
        }
    except Exception as e:
        return {
            "error": str(e),
            "results": [],
            "total_results": 0,
        }


@mcp.tool()
def get_item(item_key: str) -> dict:
    """Retrieve full text and metadata for a specific Zotero item.

    Args:
        item_key: Zotero item key

    Returns:
        Dictionary with full item content and metadata
    """
    coll = get_collection()

    results = coll.get(
        where={"item_key": {"$eq": item_key}}, include=["metadatas", "documents"]
    )

    if not results["documents"]:
        return {"error": f"Item {item_key} not found"}

    # TODO: just return the zotero link using the python zotero library
    raise NotImplementedError("Integration with Zotero cloud sync is not yet built.")


@mcp.tool()
def get_similar_items(item_key: str, n_results: int = 5) -> dict:
    """Find items similar to a given Zotero item.

    Args:
        item_key: Zotero item key to find similar items for
        n_results: Number of similar items to return (default: 5)

    Returns:
        Dictionary with similar items and their citations
    """
    coll = get_collection()

    # First get the item
    item_results = coll.get(
        where={"item_key": {"$eq": item_key}}, include=["documents"], limit=1
    )

    if not item_results["documents"]:
        return {"error": f"Item {item_key} not found"}

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
            citation, doi_or_url, uri, zotero_key = extract_citation_metadata(meta)
            zotero_link = f"zotero://select/library/items/{zotero_key}" if zotero_key else None

            similar_items.append(
                {
                    "item_key": key,
                    "citation": citation,
                    "similarity": round(1 - dist, 3),
                    "doi_or_url": doi_or_url,
                    "uri": uri,
                    "zotero_key": zotero_key,
                    "zotero_link": zotero_link,
                    "metadata": clean_metadata(meta),
                }
            )
            seen_keys.add(key)

            if len(similar_items) >= n_results:
                break

    return {"source_item": item_key, "similar_items": similar_items}


@mcp.tool()
def get_version_info() -> dict:
    """Get version information for zotmcp and key dependencies.

    Returns:
        Dictionary with version information
    """
    import importlib.metadata

    versions = {}
    for pkg in ["zotmcp", "buttermilk", "fastmcp", "chromadb"]:
        try:
            version = importlib.metadata.version(pkg)
            # For git installs, version might include commit hash
            versions[pkg] = version
        except importlib.metadata.PackageNotFoundError:
            versions[pkg] = "not installed"

    return versions


@mcp.tool()
def get_collection_info() -> dict:
    """Get information about the Zotero library collection.

    Returns:
        Dictionary with collection statistics and metadata
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

    search_tool = get_search_tool()
    return {
        "collection_name": search_tool.collection_name,
        "total_chunks": total_chunks,
        "estimated_unique_items": len(unique_items) * (total_chunks // 100),
        "sample_item_types": item_types,
        "embedding_model": search_tool.embedding_model,
        "dimensions": search_tool.dimensionality,
    }


@mcp.tool()
def search_by_author(author_name: str, n_results: int = 20) -> dict:
    """Search for items by a specific author.

    Args:
        author_name: Author name to search for (can be partial)
        n_results: Number of results to return

    Returns:
        Dictionary with items by the specified author
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
                citation, doi_or_url, uri, zotero_key = extract_citation_metadata(meta)
                zotero_link = f"zotero://select/library/items/{zotero_key}" if zotero_key else None

                matching_items[item_key] = {
                    "item_key": item_key,
                    "citation": citation,
                    "doi_or_url": doi_or_url,
                    "uri": uri,
                    "zotero_key": zotero_key,
                    "zotero_link": zotero_link,
                    "metadata": clean_metadata(meta),
                }

            if len(matching_items) >= n_results:
                break

    return {
        "author": author_name,
        "total_results": len(matching_items),
        "items": list(matching_items.values()),
    }


if __name__ == "__main__":
    # Default to stdio for MCP; allow opting into HTTP via env for local debugging
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport == "stdio":
        mcp.run()
    else:
        mcp.run(
            transport="streamable-http",
            host=os.getenv("MCP_HTTP_HOST", "0.0.0.0"),
            port=int(os.getenv("MCP_HTTP_PORT", "8024")),
            # stateless_http=True,
        )