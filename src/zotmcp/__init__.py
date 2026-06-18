"""ZotMCP - MCP server for Zotero library search."""

__version__ = "0.1.0"

# We monkeypatch buttermilk's `_sanitize_metadata_for_chroma` so that every chunk
# written to ChromaDB carries the two citation fields the MCP `search()` tool reads
# back (`citation` and `citation_key`). Two failure modes motivated this (issue #3):
#
#   1. `citation_key` is derived from the Zotero BetterBibTeX `extra` field. When the
#      upstream source did not populate it (or set it to None), the base sanitizer
#      drops the key entirely (it skips None values), so `search()` returns None.
#   2. `citation` is produced by buttermilk's LLM Citator. When it is present we must
#      preserve it; we never invent one here.
#
# The patch is deliberately small and defensive: it derives `citation_key` from the
# already-present `zotero_data` (the full Zotero record dict) using buttermilk's own
# `extract_citation_key`, and otherwise defers entirely to the original sanitizer.
import json
from typing import Any

from buttermilk.data import vector
from buttermilk.libs.zotero import extract_citation_key

_original_sanitize = vector._sanitize_metadata_for_chroma


def _extract_extra_from_zotero_data(zotero_data: Any) -> str | None:
    """Return the Zotero `extra` field from a `zotero_data` metadata value.

    `zotero_data` may arrive as a dict (pre-sanitization, the common case) or as a
    JSON string (if an upstream step already serialized it). Anything else yields
    None so the caller falls back gracefully.
    """
    if isinstance(zotero_data, str):
        try:
            zotero_data = json.loads(zotero_data)
        except (ValueError, TypeError):
            return None
    if isinstance(zotero_data, dict):
        extra = zotero_data.get("extra")
        return extra if isinstance(extra, str) else None
    return None


def _derive_citation_key(metadata: dict[str, Any]) -> str | None:
    """Derive a BetterBibTeX citation key for a chunk's metadata.

    Prefers an explicit, non-empty `citation_key` already in the metadata. Otherwise
    derives one from `zotero_data`'s `extra` field via buttermilk's
    `extract_citation_key`. Returns None when no key can be determined.
    """
    existing = metadata.get("citation_key")
    if isinstance(existing, str) and existing.strip():
        return existing

    extra = _extract_extra_from_zotero_data(metadata.get("zotero_data"))
    return extract_citation_key(extra)


def _sanitize_metadata_for_chroma_with_citation(
    metadata: dict[str, Any],
) -> dict[str, str | int | float | bool | None]:
    """Sanitize metadata for ChromaDB while guaranteeing the citation fields.

    Wraps buttermilk's sanitizer so that:
      - `citation_key` is derived from `zotero_data.extra` when absent, and is
        preserved (as None) when genuinely unavailable so the field is queryable.
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
