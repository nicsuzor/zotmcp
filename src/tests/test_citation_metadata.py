"""Tests for the native-only citation-key policy and the hard pre-ingest gate.

Single authoritative key (decision 2026-06-19): the ONLY accepted citation key is
Zotero's native `citationKey` field (BBT-populated). There is no `extra`-field
fallback, and un-keyed items are EXCLUDED from ingest — never silent None into
ChromaDB.

Three layers:

1. Unit tests for the zotmcp monkeypatch of buttermilk's
   `_sanitize_metadata_for_chroma` — asserts native-only derivation and that the
   `extra`-field fallback is gone.
2. Unit tests for `CitationKeyGateProcessor` — the hard pre-ingest gate that
   excludes un-keyed items and reports them.
3. A live integration test that queries a real ChromaDB collection. It is skipped
   automatically when the collection/credentials are unavailable.
"""

import json

import pytest
from buttermilk import logger

# Importing zotmcp installs the monkeypatch on buttermilk's sanitizer.
import zotmcp
from zotmcp import (
    _derive_citation_key,
    _extract_native_citation_key,
)
from zotmcp.citation_key_gate import (
    CitationKeyGateProcessor,
    extract_native_citation_key,
)
from buttermilk._core.types import Record
from buttermilk.data import vector


pytestmark = pytest.mark.anyio


# --------------------------------------------------------------------------- #
# Unit tests: the native-only citation-metadata seam (no live infra)          #
# --------------------------------------------------------------------------- #


def test_monkeypatch_installed():
    """zotmcp import rebinds buttermilk's sanitizer to the citation-aware wrapper."""
    assert (
        vector._sanitize_metadata_for_chroma
        is zotmcp._sanitize_metadata_for_chroma_with_citation
    )


def test_extract_native_from_dict():
    assert (
        _extract_native_citation_key({"citationKey": "foo2020"}) == "foo2020"
    )


def test_extract_native_from_json_string():
    payload = json.dumps({"citationKey": "bar2021"})
    assert _extract_native_citation_key(payload) == "bar2021"


def test_extract_native_strips_whitespace():
    assert _extract_native_citation_key({"citationKey": "  k2017  "}) == "k2017"


def test_extract_native_handles_missing_and_garbage():
    assert _extract_native_citation_key(None) is None
    assert _extract_native_citation_key("not json") is None
    assert _extract_native_citation_key({"title": "no key"}) is None
    assert _extract_native_citation_key({"citationKey": ""}) is None
    assert _extract_native_citation_key({"citationKey": "   "}) is None
    assert _extract_native_citation_key(12345) is None


def test_no_extra_fallback():
    """A key present ONLY in `extra` must NOT be derived (fallback removed)."""
    meta = {"zotero_data": {"extra": "Citation Key: legacy2019"}}
    assert _derive_citation_key(meta) is None


def test_derive_prefers_explicit_citation_key():
    """An explicit, non-empty citation_key wins over the native field."""
    meta = {
        "citation_key": "explicit2019",
        "zotero_data": {"citationKey": "native2019"},
    }
    assert _derive_citation_key(meta) == "explicit2019"


def test_derive_from_native_citationkey():
    meta = {"zotero_data": {"citationKey": "klonick2017", "extra": "Publisher: HLR"}}
    assert _derive_citation_key(meta) == "klonick2017"


def test_derive_returns_none_when_no_native_key():
    assert _derive_citation_key({"zotero_data": {"title": "x"}}) is None
    assert _derive_citation_key({"zotero_data": {"extra": "Citation Key: x2020"}}) is None
    assert _derive_citation_key({}) is None


def test_sanitize_preserves_citation():
    """The Citator-produced `citation` string must survive sanitization."""
    citation = "Klonick, K. (2017). The New Governors. Harvard Law Review, 131."
    meta = {"citation": citation, "zotero_data": {"citationKey": "k2017"}}
    result = vector._sanitize_metadata_for_chroma(meta)
    assert result["citation"] == citation


def test_sanitize_uses_native_citation_key_when_absent():
    """citation_key absent in source -> read from native zotero_data.citationKey."""
    meta = {
        "citation": "Some citation",
        "zotero_data": {"citationKey": "klonick2017newgov"},
    }
    result = vector._sanitize_metadata_for_chroma(meta)
    assert result["citation_key"] == "klonick2017newgov"


def test_sanitize_reads_native_key_from_json_string():
    """Even when zotero_data has already been serialized to JSON."""
    meta = {"zotero_data": json.dumps({"citationKey": "native123"})}
    result = vector._sanitize_metadata_for_chroma(meta)
    assert result["citation_key"] == "native123"


def test_sanitize_ignores_extra_field():
    """A key only in `extra` must NOT leak into ChromaDB (no fallback)."""
    meta = {"zotero_data": {"extra": "Citation Key: legacy2019"}}
    result = vector._sanitize_metadata_for_chroma(meta)
    assert result["citation_key"] is None


def test_sanitize_preserves_none_citation_key_as_queryable_field():
    """No native key anywhere -> field preserved as None (defensive last resort)."""
    meta = {"zotero_data": {"title": "no citationKey field here"}}
    result = vector._sanitize_metadata_for_chroma(meta)
    assert "citation_key" in result
    assert result["citation_key"] is None


def test_sanitize_explicit_key_overrides_native():
    meta = {
        "citation_key": "explicit2019",
        "zotero_data": {"citationKey": "native2019"},
    }
    result = vector._sanitize_metadata_for_chroma(meta)
    assert result["citation_key"] == "explicit2019"


# --------------------------------------------------------------------------- #
# Unit tests: the hard pre-ingest gate (CitationKeyGateProcessor)             #
# --------------------------------------------------------------------------- #


class _Ctx:
    """Minimal ProcessingContext stand-in carrying a record."""

    def __init__(self, record: Record):
        self.record = record


async def _run_gate(gate: CitationKeyGateProcessor, record: Record) -> list[Record]:
    return [r async for r in gate.process(_Ctx(record))]


def test_gate_extract_native_helper():
    assert extract_native_citation_key({"citationKey": "smith2020"}) == "smith2020"
    assert extract_native_citation_key({"extra": "Citation Key: x"}) is None
    assert extract_native_citation_key(None) is None


async def test_gate_passes_item_with_native_key(tmp_path):
    gate = CitationKeyGateProcessor(report_path=str(tmp_path / "excluded.txt"))
    rec = Record(
        record_id="ABC123",
        metadata={"title": "A Paper", "zotero_data": {"citationKey": "paper2020"}},
    )
    out = await _run_gate(gate, rec)
    assert len(out) == 1
    # Authoritative native key is normalised onto citation_key.
    assert out[0].metadata["citation_key"] == "paper2020"


async def test_gate_normalises_citation_key_to_native(tmp_path):
    """Even if an upstream stage set a (legacy/extra) citation_key, native wins."""
    gate = CitationKeyGateProcessor(report_path=str(tmp_path / "excluded.txt"))
    rec = Record(
        record_id="ABC123",
        metadata={
            "title": "A Paper",
            "citation_key": "legacyExtraKey",
            "zotero_data": {"citationKey": "native2020"},
        },
    )
    out = await _run_gate(gate, rec)
    assert out[0].metadata["citation_key"] == "native2020"


async def test_gate_excludes_item_without_native_key(tmp_path):
    report = tmp_path / "excluded.txt"
    gate = CitationKeyGateProcessor(report_path=str(report))
    rec = Record(
        record_id="NOKEY1",
        metadata={"title": "Unkeyed Paper", "zotero_data": {"extra": "Citation Key: x"}},
    )
    out = await _run_gate(gate, rec)
    assert out == []  # excluded -> never enters ChromaDB
    # Reported with item key + title.
    contents = report.read_text()
    assert "NOKEY1" in contents
    assert "Unkeyed Paper" in contents


async def test_gate_excludes_when_no_zotero_data(tmp_path):
    report = tmp_path / "excluded.txt"
    gate = CitationKeyGateProcessor(report_path=str(report))
    rec = Record(record_id="EMPTY1", metadata={"title": "No Zotero Data"})
    out = await _run_gate(gate, rec)
    assert out == []
    assert "EMPTY1" in report.read_text()


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
