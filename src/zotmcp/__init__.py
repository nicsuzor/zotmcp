"""ZotMCP - MCP server for Zotero library search."""

__version__ = "0.1.0"

# Monkeypatch buttermilk's _sanitize_metadata_for_chroma to preserve citation_key field
# The original function skips None values, but citation_key can be None when no BetterBibTeX
# key is present. We need to preserve the field in ChromaDB so it can be queried.
# ChromaDB actually DOES support None values despite the type hint - trying it.
from typing import Any
from buttermilk.data import vector

_original_sanitize = vector._sanitize_metadata_for_chroma


def _sanitize_metadata_for_chroma_with_citation_key(
    metadata: dict[str, Any],
) -> dict[str, str | int | float | bool | None]:  # Add None to return type
    """Sanitize metadata for ChromaDB, preserving citation_key even when None."""
    result = _original_sanitize(metadata)

    # If citation_key was None and thus skipped, add it back with None value
    if (
        "citation_key" in metadata
        and metadata["citation_key"] is None
        and "citation_key" not in result
    ):
        result["citation_key"] = None  # type: ignore  # ChromaDB may accept None despite type hint

    return result  # type: ignore


vector._sanitize_metadata_for_chroma = _sanitize_metadata_for_chroma_with_citation_key
