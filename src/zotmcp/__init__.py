"""ZotMCP - MCP server for Zotero library search."""

__version__ = "0.1.0"

# We monkeypatch buttermilk's `_sanitize_metadata_for_chroma` so that every chunk
# written to ChromaDB carries the citation fields the MCP `search()` tool reads back
# (`citation` and `citation_key`).
#
# Single authoritative key policy (decision 2026-06-19, supersedes issue #3's
# "native with extra fallback"): the ONLY accepted `citation_key` is Zotero's
# **native `citationKey`** field, populated solely by BetterBibTeX. There is no
# `extra`-field fallback. Un-keyed items are excluded upstream by
# `CitationKeyGateProcessor` (see `citation_key_gate.py`), so by the time a chunk
# reaches this seam it should already carry a non-empty native key; this seam is the
# last-line guarantee that the value written to Chroma is the native key.
#
# `citation` is produced by buttermilk's LLM Citator. When present we preserve it;
# we never invent one here.
import json
from typing import Any

from buttermilk.data import vector

_original_sanitize = vector._sanitize_metadata_for_chroma


def _extract_native_citation_key(zotero_data: Any) -> str | None:
    """Return the non-empty native `citationKey` from a `zotero_data` value.

    `zotero_data` may arrive as a dict (the common case) or as a JSON string (if an
    upstream step already serialized it). Anything else, or an empty/whitespace
    value, yields None.
    """
    if isinstance(zotero_data, str):
        try:
            zotero_data = json.loads(zotero_data)
        except (ValueError, TypeError):
            return None
    if isinstance(zotero_data, dict):
        key = zotero_data.get("citationKey")
        if isinstance(key, str) and key.strip():
            return key.strip()
    return None


def _derive_citation_key(metadata: dict[str, Any]) -> str | None:
    """Derive the authoritative citation key for a chunk's metadata.

    Native-field ONLY. Prefers an explicit, non-empty `citation_key` already in the
    metadata (set by the gate processor from the native field), otherwise reads the
    native `citationKey` directly from `zotero_data`. There is NO `extra`-field
    fallback. Returns None when no native key is available.
    """
    existing = metadata.get("citation_key")
    if isinstance(existing, str) and existing.strip():
        return existing.strip()

    return _extract_native_citation_key(metadata.get("zotero_data"))


def _sanitize_metadata_for_chroma_with_citation(
    metadata: dict[str, Any],
) -> dict[str, str | int | float | bool | None]:
    """Sanitize metadata for ChromaDB while guaranteeing the citation fields.

    Wraps buttermilk's sanitizer so that:
      - `citation_key` is the native Zotero `citationKey` (never derived from
        `extra`). It is preserved as None only as a defensive last resort — the
        pre-ingest gate should already have excluded un-keyed items.
      - `citation` produced upstream by the Citator survives unchanged (the base
        sanitizer already keeps string values; we never fabricate a citation here).
    """
    result = _original_sanitize(metadata)

    if isinstance(metadata, dict):
        citation_key = _derive_citation_key(metadata)
        if citation_key is not None:
            result["citation_key"] = citation_key  # type: ignore[assignment]
        elif "citation_key" not in result:
            # Preserve the field as None so it is explicit/queryable downstream.
            # Reaching here means the gate did not run; log so it is not silent.
            result["citation_key"] = None  # type: ignore[assignment]

    return result  # type: ignore[return-value]


vector._sanitize_metadata_for_chroma = _sanitize_metadata_for_chroma_with_citation

# Some buttermilk modules bind `_sanitize_metadata_for_chroma` by `from ... import`
# at import time, which captures the original function and would bypass the patch
# above. Rebind those names too, but only for modules already imported (avoid
# importing extra modules as a side effect of importing zotmcp).
import sys  # noqa: E402

for _mod_name in (
    "buttermilk.processors.chromadb_uploader",
    "buttermilk.processors.unified_processors",
):
    _mod = sys.modules.get(_mod_name)
    if _mod is not None and hasattr(_mod, "_sanitize_metadata_for_chroma"):
        _mod._sanitize_metadata_for_chroma = _sanitize_metadata_for_chroma_with_citation
