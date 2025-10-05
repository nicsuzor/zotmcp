"""ZotMCP - MCP server for searching academic Zotero library.

This server provides tools for semantic search, literature review, and
citation retrieval from a ChromaDB-indexed Zotero library.
"""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import chromadb
from fastmcp import FastMCP
from chromadb.config import Settings as ChromaSettings
from chromadb import Documents, EmbeddingFunction, Embeddings
from google import genai

from buttermilk import logger, init, init_async
from buttermilk.tools import ChromaDBSearchTool

from models import ZoteroReference, ResearchResult

# Global buttermilk instance
bm = None
search_tool = None

# Try to initialize buttermilk at module load time (more efficient)
# This works in tests/normal execution but fails in Docker stdio mode
# where an event loop is already running
import asyncio
conf_dir = str(Path(__file__).parent.parent / "conf")
try:
    # Check if an event loop is already running
    asyncio.get_running_loop()
    # Loop exists - must initialize in lifespan manager
    _deferred_init = True
except RuntimeError:
    # No loop - safe to initialize now
    bm = init(config_dir=conf_dir, config_name="zotero")
    logger.info("Buttermilk initialized at module load")
    _deferred_init = False


@asynccontextmanager
async def lifespan_manager(server: FastMCP):
    """Initialize buttermilk with zotero config on startup."""
    global bm, search_tool
    logger.info("Starting ZotMCP...")

    # Only initialize if we couldn't do it at module load time
    if _deferred_init:
        bm = await init_async(config_dir=conf_dir, config_name="zotero")
        logger.info("Buttermilk initialized in lifespan")

    yield

    logger.info("Shutting down ZotMCP")

# Initialize MCP server with lifespan manager
mcp = FastMCP("ZotMCP - Academic Literature Search", lifespan=lifespan_manager)

# ChromaDB configuration
CACHE_DIR = Path(__file__).parent.parent / ".cache"
VECTORS_DIR = CACHE_DIR / "zotero-prosocial-fulltext" / "files"
COLLECTION_NAME = "prosocial_zot"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONALITY = 3072

# Initialize ChromaDB client
chroma_client = None
collection = None


class GeminiEmbeddingFunction(EmbeddingFunction):
    """Embedding function for Gemini API compatible with ChromaDB."""

    def __init__(
        self,
        embedding_model: str = EMBEDDING_MODEL,
        dimensionality: int = EMBEDDING_DIMENSIONALITY,
    ):
        self.dimensionality = dimensionality
        self._embedding_model = embedding_model

        # Initialize with Vertex AI configuration
        project_id = os.getenv("GCP_PROJECT_ID", "prosocial-443205")
        location = os.getenv("GCP_LOCATION", "us-central1")

        self.client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
        )

    def __call__(self, input: Documents) -> Embeddings:
        response = self.client.models.embed_content(
            model=self._embedding_model,
            contents=input,
            config={
                "output_dimensionality": self.dimensionality,
                "auto_truncate": False,
            },
        )

        # Extract embeddings from response
        embeddings = []
        for embedding in response.embeddings:
            # Convert to list if it's a numpy array
            if hasattr(embedding.values, 'tolist'):
                embeddings.append(embedding.values.tolist())
            else:
                embeddings.append(list(embedding.values))

        return embeddings


def get_collection():
    """Lazy-load ChromaDB collection with Gemini embedding function.

    Note: This is used for direct ChromaDB operations that need custom filters
    or aggregations. For basic semantic search, use get_search_tool() instead.
    """
    global chroma_client, collection

    if collection is not None:
        return collection

    if not VECTORS_DIR.exists():
        raise FileNotFoundError(
            f"ChromaDB not found at {VECTORS_DIR}. "
            "Run: ./scripts/package_for_distribution.sh download"
        )

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Loading ChromaDB from: {VECTORS_DIR}")
    logger.info(f"Collection name: {COLLECTION_NAME}")

    chroma_client = chromadb.PersistentClient(
        path=str(VECTORS_DIR), settings=ChromaSettings(anonymized_telemetry=False)
    )

    # Use Gemini embedding function to match collection's embeddings
    embedding_function = GeminiEmbeddingFunction(
        embedding_model=EMBEDDING_MODEL,
        dimensionality=EMBEDDING_DIMENSIONALITY
    )

    collection = chroma_client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function
    )
    logger.info(f"Loaded ChromaDB collection: {collection.name}")
    return collection


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

            citation, doi, uri = extract_citation_metadata(result.metadata)
            clean_meta = clean_metadata(result.metadata)

            formatted_results.append(
                {
                    "citation": citation,
                    "excerpt": result.content[:500] + "..." if len(result.content) > 500 else result.content,
                    "similarity": round(result.score, 3) if result.score else None,
                    "metadata": clean_meta,
                    "doi": doi,
                    "url": uri,
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

    return {
        "collection_name": COLLECTION_NAME,
        "total_chunks": total_chunks,
        "estimated_unique_items": len(unique_items) * (total_chunks // 100),
        "sample_item_types": item_types,
        "embedding_model": "gemini-embedding-001",
        "dimensions": 3072,
    }


@mcp.tool()
async def assisted_search(research_question: str, max_sources: int = 10) -> dict:
    """Perform an assisted literature search with LLM synthesis.

    This tool searches the library, retrieves relevant sources, and provides
    a synthesized response with proper academic citations.

    Args:
        research_question: The research question or topic to investigate
        max_sources: Maximum number of sources to include (default: 10)

    Returns:
        Dictionary with synthesized response and literature references
    """
    # Perform semantic search
    search_data = await search(query=research_question, n_results=max_sources * 2)

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

    return result.model_dump()


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

    return {
        "author": author_name,
        "total_results": len(matching_items),
        "items": list(matching_items.values()),
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
