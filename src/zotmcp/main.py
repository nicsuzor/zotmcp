"""ZotMCP - MCP server for searching academic Zotero library.

This server provides tools for semantic search, literature review, and
citation retrieval from a ChromaDB-indexed Zotero library.

Usage:
    uv run python src/main.py          # Uses mcp.yaml config (minimal, no GCP)
    uv run python src/main.py +db=dev  # Override database location
"""

import asyncio
import logging
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

# Size threshold for large documents (500KB)
SIZE_THRESHOLD = 500 * 1024

# CRITICAL: Set up temporary stderr logging BEFORE any other imports
# This prevents stdout pollution during module import phase
# Buttermilk will replace this handler during init_async()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
    force=True,
)

# CRITICAL: Configure structlog to use stderr instead of stdout
# MCP uses stdio transport, so stdout must contain ONLY JSON-RPC messages
import structlog  # noqa: E402

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    cache_logger_on_first_use=False,
)

from buttermilk import init_async, logger  # noqa: E402
from buttermilk.tools import ChromaDBSearchTool  # noqa: E402
from fastmcp import FastMCP  # noqa: E402

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))


import hydra  # For configuration management  # noqa: E402
from omegaconf import DictConfig  # Hydra's configuration objects  # noqa: E402

# Global buttermilk instance
bm = None
search_tool = None
conf = None
_gcp_ready = False
_gcp_init_task = None
_gcp_init_error = None
_chromadb_ready = False
_chromadb_init_task = None
_chromadb_init_error = None


async def _initialize_gcp_background():
    """Initialize GCP (Vertex AI) in the background without blocking server startup.

    This function runs asynchronously and sets _gcp_ready when complete.
    If initialization fails, the error is stored in _gcp_init_error.
    """
    global _gcp_ready, _gcp_init_error, bm

    # Force immediate yield to event loop so server becomes responsive
    await asyncio.sleep(0)

    try:
        logger.info("🔄 Starting GCP initialization in background")
        # Load MCP config - minimal config with only Vertex AI
        # This allows fast startup without BigQuery/PubSub/Logging
        # Use absolute path from project root
        conf_dir = str(Path(__file__).parent / "conf")
        bm = await init_async(config_dir=conf_dir, config_name="mcp", overrides=[])
        _gcp_ready = True
        logger.info("✅ GCP initialization complete - Vertex AI is ready")
    except Exception as e:
        _gcp_init_error = str(e)
        logger.error(f"❌ GCP initialization failed: {e}")


async def _initialize_chromadb_background():
    """Initialize ChromaDB in the background without blocking server startup.

    This function runs asynchronously and sets _chromadb_ready when complete.
    If initialization fails, the error is stored in _chromadb_init_error.
    """
    global _chromadb_ready, _chromadb_init_error, search_tool, _gcp_ready

    # Force immediate yield to event loop so server becomes responsive
    await asyncio.sleep(0)

    # Wait for GCP to be ready (ChromaDB needs Vertex AI for embeddings)
    while not _gcp_ready:
        if _gcp_init_error:
            logger.error(
                f"❌ Cannot initialize ChromaDB: GCP init failed with {_gcp_init_error}"
            )
            _chromadb_init_error = f"GCP initialization failed: {_gcp_init_error}"
            return
        await asyncio.sleep(0.1)

    try:
        logger.info("🔄 Starting ChromaDB initialization in background")
        search_tool = get_search_tool()
        await search_tool.initialize()
        _chromadb_ready = True
        logger.info("✅ ChromaDB initialization complete - tools are now ready")
    except Exception as e:
        _chromadb_init_error = str(e)
        logger.error(f"❌ ChromaDB initialization failed: {e}")


@asynccontextmanager
async def lifespan_manager(server: FastMCP):
    """Initialize GCP and ChromaDB in background on startup.

    This starts both GCP and ChromaDB initialization as background tasks,
    allowing the MCP server to become responsive immediately without waiting.
    GCP initializes first (for Vertex AI), then ChromaDB waits for GCP to be ready.
    """
    global bm, search_tool, conf, _gcp_init_task, _chromadb_init_task

    # Start GCP initialization in background - don't await it!
    # This allows the server to become responsive immediately while GCP initializes
    if bm is None and (_gcp_init_task is None or _gcp_init_task.done()):
        logger.info("🚀 Starting background GCP initialization")
        _gcp_init_task = asyncio.create_task(_initialize_gcp_background())

    # Start ChromaDB initialization in background - don't await it!
    # ChromaDB will wait for GCP to be ready before initializing
    if _chromadb_init_task is None or _chromadb_init_task.done():
        logger.info("🚀 Starting background ChromaDB initialization")
        _chromadb_init_task = asyncio.create_task(_initialize_chromadb_background())

    logger.info("✅ Lifespan startup complete - yielding control to FastMCP")
    yield
    logger.info("🛑 Lifespan shutdown initiated")

    # Clean up background tasks if they were started
    if _gcp_init_task and not _gcp_init_task.done():
        _gcp_init_task.cancel()
        try:
            await _gcp_init_task
        except asyncio.CancelledError:
            pass  # Expected when we cancel the task

    if _chromadb_init_task and not _chromadb_init_task.done():
        _chromadb_init_task.cancel()
        try:
            await _chromadb_init_task
        except asyncio.CancelledError:
            pass  # Expected when we cancel the task

    logger.info("Shutting down ZotMCP")


# Initialize MCP server with lifespan manager
mcp = FastMCP("ZotMCP - Academic Literature Search", lifespan=lifespan_manager)


def _check_chromadb_ready() -> Optional[dict]:
    """Check if ChromaDB is ready for use.

    The background task should already be running from lifespan startup.
    This function just checks the status and returns an error if not ready.

    Returns:
        None if ready, or a dict with error information if not ready.
    """
    global _chromadb_init_task

    # Safety fallback: start initialization if somehow it wasn't started in lifespan
    # This should never happen in normal operation
    if _chromadb_init_task is None and not _chromadb_ready:
        logger.warning(
            "⚠️  ChromaDB task not found - starting late initialization (this shouldn't happen)"
        )
        _chromadb_init_task = asyncio.create_task(_initialize_chromadb_background())

    if _chromadb_init_error:
        return {
            "error": f"ChromaDB initialization failed: {_chromadb_init_error}",
            "results": [],
            "total_results": 0,
        }

    if not _chromadb_ready:
        return {
            "error": "ChromaDB is still initializing. Please try again in 30 seconds.",
            "results": [],
            "total_results": 0,
        }

    return None  # Ready!


def get_collection():
    """Get ChromaDB collection from buttermilk search tool.

    Note: This is used for direct ChromaDB operations that need custom filters
    or aggregations. For basic semantic search, use get_search_tool() instead.
    """
    tool = get_search_tool()
    return tool.collection


def get_search_tool():
    """Get or create buttermilk ChromaDBSearchTool instance."""
    global bm, search_tool

    if search_tool is not None:
        return search_tool

    storage_config = bm.cfg.get_storage_config("zotero_vectors")
    if storage_config is None:
        raise ValueError("zotero_vectors storage config not found in configuration")

    search_tool = ChromaDBSearchTool(
        type="chromadb",
        collection_name=storage_config.collection_name,
        persist_directory=storage_config.persist_directory,
        embedding_model=storage_config.embedding_model,
        dimensionality=storage_config.dimensionality,
        read_only=getattr(storage_config, "read_only", True),
    )

    return search_tool


def extract_citation_metadata(
    metadata: dict,
) -> tuple[
    str, Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]
]:
    """Extract citation, DOI/URL, URI, Zotero key, citation key, and online library link from ChromaDB metadata.

    Args:
        metadata: ChromaDB document metadata

    Returns:
        Tuple of (citation, doi_or_url, uri, zotero_key, citation_key, zotero_web_link)
    """
    # These fields are already stored at top-level in ChromaDB metadata
    citation = metadata.get("citation", "Citation not available")
    doi_or_url = metadata.get("doi_or_url")
    uri = metadata.get("uri")
    zotero_key = metadata.get("document_id")  # document_id is the Zotero key
    citation_key = metadata.get("citation_key")  # BetterBibTeX citation key

    # Extract online library link from zotero_links
    # Note: zotero_links can be either a dict or a string in ChromaDB metadata
    zotero_links = metadata.get("zotero_links", {})
    zotero_web_link = None
    if isinstance(zotero_links, dict):
        if alternate_link := zotero_links.get("alternate"):
            if isinstance(alternate_link, dict):
                zotero_web_link = alternate_link.get("href")

    return citation, doi_or_url, uri, zotero_key, citation_key, zotero_web_link


@mcp.tool()
async def search(
    query: str,
    n_results: int = 10,
    search_mode: str = "hybrid",
    filter_type: Optional[str] = None,
    author: Optional[str] = None,
    title: Optional[str] = None,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
    fuzzy_threshold: int = 60,
    semantic_weight: float = 0.6,
    exclude_corrupted: bool = True,
) -> dict:
    """Search the Zotero library with semantic, fuzzy, or hybrid search.

    This is the main search tool with multiple modes and advanced filtering:
    - **hybrid** (default): Combines semantic embeddings + fuzzy metadata matching
    - **semantic**: Pure vector similarity search
    - **metadata**: Fuzzy text matching on metadata fields

    Args:
        query: Search query
        n_results: Number of results to return (default: 10, max: 100)
        search_mode: Search strategy - "hybrid" (recommended), "semantic", or "metadata"
        filter_type: Filter by item type (e.g., 'journalArticle', 'book', 'bookSection')
        author: Filter by author name (fuzzy matching, handles typos)
        title: Search by title (fuzzy matching)
        date_from: Earliest publication year (e.g., 2020)
        date_to: Latest publication year (e.g., 2024)
        fuzzy_threshold: Minimum fuzzy match score 0-100 (default: 60)
        semantic_weight: Weight for semantic vs fuzzy in hybrid mode (default: 0.6)
        exclude_corrupted: Filter out results with heavy CID corruption (>=20 patterns) (default: True)

    Returns:
        Dictionary with search results including citations, excerpts, and relevance scores

    Examples:
        search("machine learning ethics")  # Hybrid search
        search("privacy", author="Smith", date_from=2020)  # With filters
        search("AI", search_mode="semantic")  # Pure semantic search
    """
    # Check if ChromaDB is ready
    if error_response := _check_chromadb_ready():
        return error_response

    try:
        n_results = min(n_results, 100)

        if search_mode not in ["hybrid", "semantic", "metadata"]:
            return {
                "error": f"Invalid search_mode: {search_mode}. Must be 'hybrid', 'semantic', or 'metadata'",
                "results": [],
            }

        tool = get_search_tool()
        coll = get_collection()

        # Use enhanced search engine
        results = await _advanced_search(
            search_tool=tool,
            collection=coll,
            query=query,
            n_results=n_results,
            search_mode=search_mode,
            author=author,
            title=title,
            date_from=date_from,
            date_to=date_to,
            item_type=filter_type,
            fuzzy_threshold=fuzzy_threshold,
            semantic_weight=semantic_weight,
            exclude_corrupted=exclude_corrupted,
        )

        formatted_results = [_format_search_result(r) for r in results]

        return {
            "query": query,
            "search_mode": search_mode,
            "total_results": len(formatted_results),
            "results": formatted_results,
        }

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
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
    from zotmcp.search_utils import get_metadata_field

    coll = get_collection()

    results = coll.get(
        where={"document_id": {"$eq": item_key}}, include=["metadatas", "documents"]
    )

    if not results["documents"]:
        return {"error": f"Item {item_key} not found"}

    # Get all chunks and sort by chunk_index
    chunk_count = len(results["documents"])
    chunks_with_index = []
    for i, (doc, meta) in enumerate(zip(results["documents"], results["metadatas"])):
        chunk_index = meta["chunk_index"]  # Fail-fast: required field
        chunks_with_index.append((chunk_index, doc))

    # Sort by chunk_index and concatenate
    chunks_with_index.sort(key=lambda x: x[0])
    full_text = "\n\n".join(chunk[1] for chunk in chunks_with_index)

    # Use first chunk's metadata for item-level fields
    metadata = results["metadatas"][0]

    # Extract citation metadata using existing helper
    citation, doi_or_url, uri, zotero_key, citation_key, zotero_web_link = (
        extract_citation_metadata(metadata)
    )

    # Extract additional metadata fields
    title = get_metadata_field(metadata, "title")
    item_type = get_metadata_field(metadata, "itemType")
    abstract = get_metadata_field(metadata, "abstractNote")

    # Build Zotero desktop link
    zotero_link = f"zotero://select/library/items/{zotero_key}" if zotero_key else None

    # Check document size for large document handling
    full_text_bytes = len(full_text.encode("utf-8"))

    # Base metadata common to both large and small documents
    base_metadata = {
        "citation": citation,
        "title": title,
        "item_type": item_type,
        "doi": doi_or_url,
        "url": uri,
        "abstract": abstract,
        "zotero_link": zotero_link,
        "zotero_key": zotero_key,
        "citation_key": citation_key,
        "zotero_web_link": zotero_web_link,
    }

    # Always write full text to temp file for consistent behavior
    temp_dir = Path(tempfile.gettempdir()) / "zotmcp"
    temp_dir.mkdir(exist_ok=True)
    temp_file = temp_dir / f"{item_key}_full_text.txt"
    temp_file.write_text(full_text, encoding="utf-8")

    return {
        **base_metadata,
        "full_text_preview": full_text[:2000],
        "full_text_file": str(temp_file),
        "full_text_size_bytes": full_text_bytes,
        "chunk_count": chunk_count,
    }


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
        where={"document_id": {"$eq": item_key}}, include=["documents"], limit=1
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
        key = meta.get("document_id")
        if key and key != item_key and key not in seen_keys:
            citation, doi_or_url, uri, zotero_key, citation_key, zotero_web_link = (
                extract_citation_metadata(meta)
            )
            zotero_link = (
                f"zotero://select/library/items/{zotero_key}" if zotero_key else None
            )

            similar_items.append(
                {
                    "item_key": key,
                    "citation": citation,
                    "similarity": round(1 - dist, 3),
                    "doi_or_url": doi_or_url,
                    "uri": uri,
                    "zotero_key": zotero_key,
                    "citation_key": citation_key,
                    "zotero_link": zotero_link,
                    "zotero_web_link": zotero_web_link,
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


# ===== Citation Search Tools (OpenAlex API) =====
# These tools enable discovery of new academic literature beyond the Zotero library

from zotmcp.citation_search import (  # noqa: E402
    search_papers as _search_papers,
    get_paper_citations as _get_paper_citations,
    get_referenced_works as _get_referenced_works,
    search_openalex_author as _search_openalex_author,
    get_paper_details as _get_paper_details,
)

# ===== Enhanced Search Tools =====
# Fuzzy matching and hybrid search capabilities

from zotmcp.enhanced_search import (  # noqa: E402
    advanced_search as _advanced_search,
    fuzzy_author_search,
    search_by_citation_key_async,
    search_by_doi_async,
)
from zotmcp.search_utils import SearchResult  # noqa: E402


@mcp.tool()
async def search_papers(
    query: str,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    open_access_only: bool = False,
    limit: int = 25,
) -> list:
    """Search for academic papers using OpenAlex API.

    Discover new literature beyond your Zotero library. OpenAlex provides free
    access to 240M+ academic works with good humanities coverage.

    Args:
        query: Search query (searches title, abstract, full text)
        year_from: Earliest publication year (optional)
        year_to: Latest publication year (optional)
        open_access_only: Only return open access papers (default: False)
        limit: Max results (1-200, default 25)

    Returns:
        List of paper dictionaries with metadata
    """
    return await _search_papers(query, year_from, year_to, open_access_only, limit)


@mcp.tool()
async def get_paper_citations(
    paper_id: str,
    limit: int = 50,
    year_from: Optional[int] = None,
) -> list:
    """Get papers that CITE a specific paper (forward citations).

    Explore citation networks to discover recent work building on foundational papers.

    Args:
        paper_id: OpenAlex ID (e.g., 'W2741809807') or DOI
        limit: Maximum number of results (default: 50)
        year_from: Only include citations from this year onwards (optional)

    Returns:
        List of citing paper dictionaries
    """
    return await _get_paper_citations(paper_id, limit, year_from)


@mcp.tool()
async def get_referenced_works(paper_id: str, limit: int = 50) -> list:
    """Get papers referenced by a given paper (backward citations).

    Useful for understanding foundational work and context.

    Args:
        paper_id: OpenAlex ID or DOI
        limit: Maximum number of results (default: 50)

    Returns:
        List of referenced paper dictionaries
    """
    return await _get_referenced_works(paper_id, limit)


@mcp.tool()
async def search_openalex_author(
    author_name: str,
    limit: int = 50,
    year_from: Optional[int] = None,
) -> list:
    """Search for papers by author using OpenAlex API - discovers NEW papers beyond your Zotero library.

    This tool searches the OpenAlex database (240M+ papers) for works by a specific author.
    It does NOT search your personal Zotero library. To search YOUR library, use the
    main 'search' tool with the author parameter instead.

    Uses two-step lookup: finds author in OpenAlex, then retrieves their papers.

    Args:
        author_name: Author name to search for (e.g., "Geoffrey Hinton")
        limit: Maximum number of papers to return (default: 50)
        year_from: Filter papers from this year onwards (optional)

    Returns:
        List of paper dictionaries from OpenAlex with metadata and citations

    Examples:
        search_openalex_author("Yann LeCun", limit=25, year_from=2020)
    """
    return await _search_openalex_author(author_name, limit, year_from)


@mcp.tool()
async def search_library_by_author(
    author_name: str,
    n_results: int = 20,
    fuzzy_threshold: int = 70,
) -> dict:
    """Search for papers by author in YOUR Zotero library using fuzzy name matching.

    This tool searches your personal Zotero library collection for papers by a specific
    author. It uses fuzzy matching to handle name variations, typos, and different
    name formats (e.g., "Smith, J." vs "John Smith").

    This is NOT an OpenAlex search - it only searches papers you already have in your
    library. To discover new papers by an author, use search_openalex_author instead.

    Args:
        author_name: Author name to search for (e.g., "Suzor", "Gillespie")
        n_results: Maximum number of results to return (default: 20)
        fuzzy_threshold: Minimum match score 0-100 (default: 70, higher = stricter)

    Returns:
        Dictionary with search results including papers by the specified author

    Examples:
        search_library_by_author("Suzor")
        search_library_by_author("Gillespie", n_results=10, fuzzy_threshold=80)
    """
    # Check if ChromaDB is ready
    if error_response := _check_chromadb_ready():
        return error_response

    try:
        from zotmcp.search_utils import get_metadata_field

        coll = get_collection()

        # Use fuzzy author search from enhanced_search
        results = await fuzzy_author_search(
            collection=coll,
            author_name=author_name,
            n_results=n_results,
            fuzzy_threshold=fuzzy_threshold,
        )

        # Format results with authors field included
        formatted_results = []
        for result in results:
            formatted = _format_search_result(result)
            # Add authors field from metadata
            authors = get_metadata_field(result.metadata, "creators")
            if authors:
                formatted["authors"] = authors
            formatted_results.append(formatted)

        return {
            "author_query": author_name,
            "total_results": len(formatted_results),
            "results": formatted_results,
        }

    except Exception as e:
        logger.error(f"Library author search error: {e}", exc_info=True)
        return {
            "error": str(e),
            "results": [],
            "total_results": 0,
        }


@mcp.tool()
async def get_paper_details(paper_id: str) -> dict:
    """Get detailed information about a specific paper.

    Args:
        paper_id: OpenAlex ID or DOI

    Returns:
        Paper dictionary with full details, or None if not found
    """
    result = await _get_paper_details(paper_id)
    return result if result else {"error": "Paper not found"}


def _format_search_result(result: SearchResult) -> dict:
    """Format a SearchResult object for MCP tool output.

    Args:
        result: SearchResult object

    Returns:
        Dictionary with formatted result
    """
    citation, doi_or_url, uri, zotero_key, citation_key, zotero_web_link = (
        extract_citation_metadata(result.metadata)
    )

    zotero_link = f"zotero://select/library/items/{zotero_key}" if zotero_key else None

    output = {
        "citation": citation,
        "excerpt": result.document if result.document else None,
        "doi_or_url": doi_or_url,
        "uri": uri,
        "zotero_key": zotero_key,
        "citation_key": citation_key,
        "zotero_link": zotero_link,
        "zotero_web_link": zotero_web_link,
    }

    # Add scores if available
    if result.similarity_score is not None:
        output["semantic_score"] = round(result.similarity_score, 3)
    if result.fuzzy_score is not None:
        output["fuzzy_score"] = round(result.fuzzy_score, 1)
    if result.combined_score is not None:
        output["combined_score"] = round(result.combined_score, 1)
    if result.match_field:
        output["matched_field"] = result.match_field

    return output


# ===== Enhanced Search MCP Tools =====
# Note: Enhanced search capabilities are now integrated into the main 'search' tool above


@mcp.tool()
async def search_by_doi(doi: str) -> dict:
    """Search for an item by DOI (exact match).

    Args:
        doi: DOI to search for (with or without doi: prefix or URL)

    Returns:
        Dictionary with item metadata if found

    Examples:
        - search_by_doi("10.1038/nature12373")
        - search_by_doi("https://doi.org/10.1038/nature12373")
    """
    # Check if ChromaDB is ready
    if error_response := _check_chromadb_ready():
        return error_response

    try:
        coll = get_collection()
        metadata = await search_by_doi_async(coll, doi)

        if not metadata:
            return {"error": f"No item found with DOI: {doi}"}

        # Extract citation info
        citation, doi_or_url, uri, zotero_key, citation_key, zotero_web_link = (
            extract_citation_metadata(metadata)
        )

        zotero_link = (
            f"zotero://select/library/items/{zotero_key}" if zotero_key else None
        )

        return {
            "citation": citation,
            "doi": doi_or_url,
            "uri": uri,
            "zotero_key": zotero_key,
            "citation_key": citation_key,
            "zotero_link": zotero_link,
            "zotero_web_link": zotero_web_link,
        }

    except Exception as e:
        logger.error(f"DOI search error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def search_by_citation_key(citation_key: str) -> dict:
    """Search for an item by BetterBibTeX citation key (exact match).

    Args:
        citation_key: BetterBibTeX citation key (e.g., "smith2020machine")

    Returns:
        Dictionary with item metadata if found
    """
    # Check if ChromaDB is ready
    if error_response := _check_chromadb_ready():
        return error_response

    try:
        coll = get_collection()
        metadata = await search_by_citation_key_async(coll, citation_key)

        if not metadata:
            return {"error": f"No item found with citation key: {citation_key}"}

        citation, doi_or_url, uri, zotero_key, cit_key, zotero_web_link = (
            extract_citation_metadata(metadata)
        )

        zotero_link = (
            f"zotero://select/library/items/{zotero_key}" if zotero_key else None
        )

        return {
            "citation": citation,
            "citation_key": cit_key,
            "doi_or_url": doi_or_url,
            "uri": uri,
            "zotero_key": zotero_key,
            "zotero_link": zotero_link,
            "zotero_web_link": zotero_web_link,
        }

    except Exception as e:
        logger.error(f"Citation key search error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.prompt()
def literature_review(question: str, context: str = ""):
    """Academic literature review with systematic search and citation synthesis.

    Use this prompt for research questions that require:
    - Comprehensive literature search across academic sources
    - Evaluation of source quality, recency, and authority
    - Synthesis of findings with proper academic citations

    Args:
        question: The research question or topic to investigate
        context: Optional additional context, constraints, or guidance
    """
    context_section = f"\n**Additional Context**: {context}\n" if context else ""

    return f"""# Academic Literature Review: {question}
{context_section}
## Phase 1: Multi-Angle Search Strategy

Academic literature requires systematic discovery. Run 3-5 searches with different approaches:

1. **Primary concept search**: Use the main keywords from your question
2. **Methodological angle**: Add terms like "systematic review", "meta-analysis", "empirical study"
3. **Theoretical angle**: Add framework or theory terms if relevant
4. **Author-based search**: If you find a key author, search their other works
5. **Citation chaining**: Use `get_similar_items` on highly relevant papers

**Search Parameters**:
- Start with `n_results=10` to get broad coverage
- Note similarity scores: > 0.7 = highly relevant, 0.5-0.7 = possibly relevant, < 0.5 = likely tangential

## Phase 2: Source Evaluation

For each result, evaluate:

### Recency
- Check publication year in the citation
- Prioritize recent work (last 5 years) unless doing historical analysis
- Note if field moves quickly (tech/social media) vs. slowly (legal theory)

### Authority
- **Peer-reviewed journals** > conference papers > books > reports
- Check if published in top-tier outlets for the field
- Look for citation counts if available
- Note author affiliations and expertise

### Relevance
- Read the excerpt carefully - does it directly address your question?
- Check if it's empirical research, theoretical, or commentary
- Note the geographic/cultural context if relevant

**Create a shortlist**: Select 5-10 most promising items based on recency, authority, and relevance.

## Phase 3: Iterative Refinement

Based on Phase 2 findings:

1. **Identify gaps**: What aspects of your question aren't covered?
2. **Extract new keywords**: What terminology do the best papers use?
3. **Run targeted searches**: Use the new keywords to find additional sources
4. **Use similar items**: For your top 2-3 papers, run `get_similar_items` to find related work

**Stopping criteria**: Stop when you've found 5-10 high-quality sources that collectively address your question, or when new searches stop yielding relevant results.

## Phase 4: Synthesis and Citation

Now synthesize your findings:

### Structure Your Response

**Summary** (2-3 sentences):
- What are the main findings across the literature?
- Is there consensus or debate?
- What are the key takeaways?

**Response** (detailed synthesis):
- Organize by themes or sub-questions
- Synthesize across sources - don't just list papers
- Note where sources agree or disagree
- Identify trends or evolution in thinking
- **CRITICAL**: Only include information found in search results - NEVER use general knowledge

**Literature List**:
For each source you cite, create a ZoteroReference with:
- **citation**: Full academic citation (Author, Year. Title. Journal/Publisher)
- **summary**: What specific finding from this source supports your synthesis
- **doi**: Include if available in the metadata
- **uri**: Include if DOI not available
- **item_key**: The Zotero key for reference

### Academic Citation Standards

- Citations must be **precise and complete**: Author(s), Year, Full Title, Journal/Publisher
- Each claim in your response should be backed by a source in the literature list
- If multiple sources support a claim, cite all of them
- If sources conflict, explicitly note the disagreement
- Direct quotes should be marked as such with page numbers if available

## Quality Checklist

Before finalizing, verify:
- [ ] Ran at least 3 different search queries?
- [ ] Evaluated at least 10 individual sources?
- [ ] Selected 5-10 high-quality sources for synthesis?
- [ ] Checked publication dates for recency?
- [ ] Prioritized peer-reviewed sources?
- [ ] Synthesized across sources (not just listing)?
- [ ] Every claim backed by a citation?
- [ ] All citations complete with author/year/title/outlet?
- [ ] Used ONLY information from search results?
- [ ] Included DOI/URI for each reference?

## Important Constraints

**NEVER use general knowledge**: Your synthesis must ONLY contain information present in the search results. If information is not available in the results, state that clearly.

**Filter garbled results**: Search results may sometimes be poorly formatted. Exclude illegible content and ensure all citations are clean and readable.

**Note limitations**: If you cannot find sufficient sources on a topic, explicitly state this. Better to acknowledge gaps than to speculate.

## Output Format

Your response should be structured as a ResearchResult with:
- `summary`: 2-3 sentence overview of main findings
- `response`: Detailed synthesis organized by themes
- `literature`: List of ZoteroReference objects for all cited sources
- `search_queries`: List of queries you used (optional but helpful)
"""


@hydra.main(version_base="1.3", config_path="conf", config_name="mcp")
def main(cfg: DictConfig) -> None:
    """Entry point - loads config and runs async pipeline."""
    global conf
    conf = cfg

    # Default to stdio for MCP; allow opting into HTTP via env for local debugging
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    logger.info(f"🔌 Starting FastMCP with transport: {transport}")
    if transport == "stdio":
        mcp.run()
    else:
        mcp.run(
            transport="streamable-http",
            host=os.getenv("MCP_HTTP_HOST", "0.0.0.0"),
            port=int(os.getenv("MCP_HTTP_PORT", "8024")),
        )
    logger.info("🏁 FastMCP run() completed")


if __name__ == "__main__":
    # This block executes if the script is run directly
    # Hydra's `@hydra.main` decorator handles parsing command-line arguments
    # and loading the configuration specified by `config_path` and `config_name`.

    main()
