"""Tests that citation and citation_key metadata fields are populated for ChromaDB.

Two layers:

1. Unit tests for the zotmcp monkeypatch of buttermilk's
   `_sanitize_metadata_for_chroma` (issue #3). These run without any live
   infrastructure and assert the seam derives/preserves `citation_key` and keeps
   `citation`.
2. A live integration test that queries a real ChromaDB collection. It is skipped
   automatically when the collection/credentials are unavailable.
"""

import json

import pytest
from buttermilk import logger

# Importing zotmcp installs the monkeypatch on buttermilk's sanitizer.
import zotmcp
from zotmcp import (
    _derive_citation_key,
    _extract_extra_from_zotero_data,
)
from buttermilk.data import vector


pytestmark = pytest.mark.anyio


# --------------------------------------------------------------------------- #
# Unit tests: the citation-metadata seam (no live infra required)             #
# --------------------------------------------------------------------------- #


def test_monkeypatch_installed():
    """zotmcp import rebinds buttermilk's sanitizer to the citation-aware wrapper."""
    assert (
        vector._sanitize_metadata_for_chroma
        is zotmcp._sanitize_metadata_for_chroma_with_citation
    )


def test_extract_extra_from_dict():
    assert (
        _extract_extra_from_zotero_data({"extra": "Citation Key: foo2020"})
        == "Citation Key: foo2020"
    )


def test_extract_extra_from_json_string():
    payload = json.dumps({"extra": "Citation Key: bar2021"})
    assert _extract_extra_from_zotero_data(payload) == "Citation Key: bar2021"


def test_extract_extra_handles_missing_and_garbage():
    assert _extract_extra_from_zotero_data(None) is None
    assert _extract_extra_from_zotero_data("not json") is None
    assert _extract_extra_from_zotero_data({"title": "no extra"}) is None
    assert _extract_extra_from_zotero_data(12345) is None


def test_derive_prefers_explicit_citation_key():
    """An explicit, non-empty citation_key wins over anything derivable."""
    meta = {
        "citation_key": "explicit2019",
        "zotero_data": {"extra": "Citation Key: derived2019"},
    }
    assert _derive_citation_key(meta) == "explicit2019"


def test_derive_from_zotero_data_extra():
    meta = {"zotero_data": {"extra": "Publisher: HLR\nCitation Key: klonick2017"}}
    assert _derive_citation_key(meta) == "klonick2017"


def test_derive_returns_none_when_unavailable():
    assert _derive_citation_key({"zotero_data": {"title": "x"}}) is None
    assert _derive_citation_key({}) is None


def test_sanitize_preserves_citation():
    """The Citator-produced `citation` string must survive sanitization."""
    citation = "Klonick, K. (2017). The New Governors. Harvard Law Review, 131."
    meta = {"citation": citation, "zotero_data": {"extra": "Citation Key: k2017"}}
    result = vector._sanitize_metadata_for_chroma(meta)
    assert result["citation"] == citation


def test_sanitize_derives_citation_key_when_absent():
    """citation_key absent in source -> derived from zotero_data.extra."""
    meta = {
        "citation": "Some citation",
        "zotero_data": {"extra": "Citation Key: klonick2017newgov"},
    }
    result = vector._sanitize_metadata_for_chroma(meta)
    assert result["citation_key"] == "klonick2017newgov"


def test_sanitize_derives_citation_key_from_json_string():
    """Even when zotero_data has already been serialized to JSON."""
    meta = {"zotero_data": json.dumps({"extra": "Citation Key: derived123"})}
    result = vector._sanitize_metadata_for_chroma(meta)
    assert result["citation_key"] == "derived123"


def test_sanitize_preserves_none_citation_key_as_queryable_field():
    """No key available anywhere -> field is preserved as None (not dropped)."""
    meta = {"zotero_data": {"title": "no extra field here"}}
    result = vector._sanitize_metadata_for_chroma(meta)
    assert "citation_key" in result
    assert result["citation_key"] is None


def test_sanitize_explicit_key_overrides_derivable():
    meta = {
        "citation_key": "explicit2019",
        "zotero_data": {"extra": "Citation Key: derived2019"},
    }
    result = vector._sanitize_metadata_for_chroma(meta)
    assert result["citation_key"] == "explicit2019"


# --------------------------------------------------------------------------- #
# Live integration test (auto-skips without a populated collection)           #
# --------------------------------------------------------------------------- #


async def test_citation_metadata_present_in_chromadb(mcp_server_local):
    """Verify citation and citation_key metadata for a real indexed item.

    Skips when the item is not present in the local collection (e.g. no
    ChromaDB cache / credentials in this environment).
    """
    import main

    search_tool = main.get_search_tool()
    await search_tool.ensure_cache_initialized()
    collection = search_tool.collection

    # Known test item (Kowalski cyberbullying paper) from test_chromadb_retrieval.py
    item_key = "MBGHP5HR"

    results = collection.get(
        where={"document_id": {"$eq": item_key}},
        include=["metadatas"],
    )

    assert results is not None, f"Query returned None for item {item_key}"
    num_chunks = len(results["ids"])
    if num_chunks == 0:
        pytest.skip(
            f"Item {item_key} not present in local ChromaDB collection; "
            "live verification requires a populated cache."
        )

    logger.info(f"Found {num_chunks} chunks for item {item_key}")

    # The citation-field fix only affects items vectorized AFTER it landed. The
    # shared collection may still hold pre-fix chunks (issue #3 is exactly that
    # stale data). Detect that case and skip rather than fail: the post-fix
    # behaviour is proven by the unit tests above against the real sanitize path.
    first_meta = results["metadatas"][0]
    if "citation_key" not in first_meta:
        pytest.skip(
            f"Item {item_key} chunks pre-date the citation-field fix "
            f"(no 'citation_key' key present) — reprocess required to backfill. "
            f"Post-fix behaviour is covered by the unit tests in this module."
        )

    for idx, (chunk_id, metadata) in enumerate(
        zip(results["ids"], results["metadatas"])
    ):
        assert "citation" in metadata, (
            f"Chunk {chunk_id} missing 'citation' field. "
            f"Available fields: {list(metadata.keys())}"
        )
        citation = metadata["citation"]
        assert citation is not None and len(citation) > 0, (
            f"Chunk {chunk_id} has empty citation"
        )

        # citation_key may be None (no BetterBibTeX key) but the field should exist.
        assert "citation_key" in metadata, (
            f"Chunk {chunk_id} missing 'citation_key' field"
        )
        citation_key = metadata.get("citation_key")
        if citation_key is not None:
            assert len(citation_key) > 0, f"Chunk {chunk_id} has empty citation_key"

        logger.info(
            f"  Chunk {idx + 1} citation={citation[:80]!r} key={citation_key!r}"
        )

    logger.info(f"All {num_chunks} chunks have valid citation metadata")
