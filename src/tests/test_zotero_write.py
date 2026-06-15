"""Tests for ZoteroWriter and resolve_paper.

All pyzotero calls and HTTP calls are mocked — no live Zotero API or internet
access required.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _make_writer():
    """Create a ZoteroWriter with env vars set and pyzotero's Zotero mocked.

    Returns (writer, mock_zot) where mock_zot is the pyzotero.Zotero instance.
    """
    env = {
        "ZOTERO_API_KEY": "test-api-key",
        "ZOTERO_LIBRARY_ID": "99999",
        "ZOTERO_LIBRARY_TYPE": "group",
    }
    with patch.dict(os.environ, env):
        with patch("pyzotero.zotero.Zotero") as MockZotero:
            mock_zot = MagicMock()
            MockZotero.return_value = mock_zot
            from zotmcp.zotero_write import ZoteroWriter

            writer = ZoteroWriter()
            # Replace the real _zot with our mock (it was already set in __init__
            # but MockZotero captured the call, so writer._zot IS mock_zot already)
            writer._zot = mock_zot
            return writer, mock_zot


def _make_journal_template():
    return {
        "itemType": "journalArticle",
        "title": "",
        "creators": [],
        "date": "",
        "DOI": "",
        "url": "",
        "abstractNote": "",
        "publicationTitle": "",
        "extra": "",
        "tags": [],
        "collections": [],
    }


def _existing_item(key="EXISTKEY", doi="10.1234/test", version=5):
    return {
        "key": key,
        "version": version,
        "data": {
            "itemType": "journalArticle",
            "title": "Existing Paper",
            "DOI": doi,
            "tags": [],
        },
    }


# ────────────────────────────────────────────────────────────────────────────
# ZoteroWriter.create_item
# ────────────────────────────────────────────────────────────────────────────


class TestCreateItem:
    def test_create_item_success(self):
        """Happy path: no existing item, create succeeds, returns new key."""
        writer, mock_zot = _make_writer()
        mock_zot.item_template.return_value = _make_journal_template()
        mock_zot.items.return_value = []  # No dedup hit
        mock_zot.create_items.return_value = {
            "success": {"0": "NEWKEY123"},
            "failed": {},
        }

        result = writer.create_item(
            item_type="journalArticle",
            metadata={
                "title": "Test Paper",
                "creators": [],
                "doi": "10.1234/test",
            },
            dedupe_by="doi",
            incoming_tag="incoming/test",
        )

        assert result["created"] is True
        assert result["item_key"] == "NEWKEY123"
        assert result["existing_key"] is None
        mock_zot.create_items.assert_called_once()

    def test_create_item_dedup_existing(self):
        """If DOI matches an existing item, return it without creating."""
        writer, mock_zot = _make_writer()
        mock_zot.items.return_value = [_existing_item()]
        # item_template shouldn't be called — dedup bails out early
        mock_zot.item_template.return_value = _make_journal_template()

        result = writer.create_item(
            item_type="journalArticle",
            metadata={
                "title": "Test Paper",
                "creators": [],
                "doi": "10.1234/test",
            },
            dedupe_by="doi",
        )

        assert result["created"] is False
        assert result["item_key"] == "EXISTKEY"
        assert result["existing_key"] == "EXISTKEY"
        mock_zot.create_items.assert_not_called()

    def test_create_item_doi_normalisation_in_dedup(self):
        """DOI with URL prefix still matches bare DOI in library."""
        writer, mock_zot = _make_writer()
        # Library item has bare DOI
        mock_zot.items.return_value = [_existing_item(doi="10.1234/test")]

        result = writer.create_item(
            item_type="journalArticle",
            metadata={
                "title": "Test",
                "creators": [],
                "doi": "https://doi.org/10.1234/test",  # URL-prefixed
            },
            dedupe_by="doi",
        )

        assert result["created"] is False
        assert result["item_key"] == "EXISTKEY"


# ────────────────────────────────────────────────────────────────────────────
# ZoteroWriter.update_item
# ────────────────────────────────────────────────────────────────────────────


class TestUpdateItem:
    def test_update_item_version_conflict(self):
        """Wrong version → structured error, not exception."""
        writer, mock_zot = _make_writer()
        mock_zot.items.return_value = [
            {
                "key": "TESTKEY",
                "version": 10,
                "data": {"title": "Old Title", "tags": []},
            }
        ]

        result = writer.update_item("TESTKEY", {"title": "New Title"}, version=5)

        assert result["ok"] is False
        assert result["error"] == "version_conflict"
        assert result["new_version"] == 10
        mock_zot.update_item.assert_not_called()

    def test_update_item_success(self):
        """Correct version → update proceeds."""
        writer, mock_zot = _make_writer()
        mock_zot.items.side_effect = [
            # First call: fetch item
            [{"key": "TESTKEY", "version": 10, "data": {"title": "Old", "tags": []}}],
            # Second call: fetch new version after update
            [{"key": "TESTKEY", "version": 11, "data": {"title": "New", "tags": []}}],
        ]
        mock_zot.update_item.return_value = None

        result = writer.update_item("TESTKEY", {"title": "New"}, version=10)

        assert result["ok"] is True
        assert result["new_version"] == 11


# ────────────────────────────────────────────────────────────────────────────
# ZoteroWriter.add_tags
# ────────────────────────────────────────────────────────────────────────────


class TestAddTags:
    def test_add_tags_idempotent(self):
        """Tags already present are skipped; only new ones are added."""
        writer, mock_zot = _make_writer()
        mock_zot.items.return_value = [
            {
                "key": "TESTKEY",
                "version": 3,
                "data": {
                    "title": "Test",
                    "tags": [{"tag": "existing-tag"}],
                },
            }
        ]
        mock_zot.update_item.return_value = None

        result = writer.add_tags("TESTKEY", ["existing-tag", "new-tag"])

        assert result["ok"] is True
        assert result["tags_added"] == 1
        assert result["tags_skipped"] == 1

    def test_add_tags_all_new(self):
        """All tags new → all added, none skipped."""
        writer, mock_zot = _make_writer()
        mock_zot.items.return_value = [
            {
                "key": "TESTKEY",
                "version": 1,
                "data": {"title": "Test", "tags": []},
            }
        ]
        mock_zot.update_item.return_value = None

        result = writer.add_tags("TESTKEY", ["tag-a", "tag-b"])

        assert result["tags_added"] == 2
        assert result["tags_skipped"] == 0

    def test_add_tags_all_existing(self):
        """All tags already present → no update call."""
        writer, mock_zot = _make_writer()
        mock_zot.items.return_value = [
            {
                "key": "TESTKEY",
                "version": 1,
                "data": {"tags": [{"tag": "tag-a"}, {"tag": "tag-b"}]},
            }
        ]

        result = writer.add_tags("TESTKEY", ["tag-a", "tag-b"])

        assert result["tags_added"] == 0
        assert result["tags_skipped"] == 2
        mock_zot.update_item.assert_not_called()


# ────────────────────────────────────────────────────────────────────────────
# ZoteroWriter.add_note
# ────────────────────────────────────────────────────────────────────────────


class TestAddNote:
    def test_add_note_no_duplicate(self):
        """Exact duplicate note content → no second note created."""
        writer, mock_zot = _make_writer()
        existing_html = "<p>This is the note content</p>"
        mock_zot.children.return_value = [
            {
                "key": "NOTEKEY1",
                "data": {"itemType": "note", "note": existing_html},
            }
        ]

        result = writer.add_note("PARENTKEY", existing_html)

        assert result["note_key"] == "NOTEKEY1"
        assert result["created"] is False
        mock_zot.create_items.assert_not_called()

    def test_add_note_new(self):
        """No existing note with same content → new note created."""
        writer, mock_zot = _make_writer()
        mock_zot.children.return_value = []  # No existing notes
        mock_zot.item_template.return_value = {
            "itemType": "note",
            "note": "",
            "parentItem": "",
            "tags": [],
        }
        mock_zot.create_items.return_value = {
            "success": {"0": "NEWNOTEKEY"},
            "failed": {},
        }

        result = writer.add_note("PARENTKEY", "<p>Brand new note</p>")

        assert result["note_key"] == "NEWNOTEKEY"
        assert result["created"] is True


# ────────────────────────────────────────────────────────────────────────────
# DOI normalisation
# ────────────────────────────────────────────────────────────────────────────


class TestDoiNormalisation:
    def test_bare_doi(self):
        from zotmcp.zotero_write import _normalize_doi

        assert _normalize_doi("10.1234/test") == "10.1234/test"

    def test_https_prefix(self):
        from zotmcp.zotero_write import _normalize_doi

        assert _normalize_doi("https://doi.org/10.1234/TEST") == "10.1234/test"

    def test_http_prefix(self):
        from zotmcp.zotero_write import _normalize_doi

        assert _normalize_doi("http://doi.org/10.1234/test") == "10.1234/test"

    def test_doi_colon_prefix(self):
        from zotmcp.zotero_write import _normalize_doi

        assert _normalize_doi("doi:10.1234/test") == "10.1234/test"

    def test_whitespace_stripped(self):
        from zotmcp.zotero_write import _normalize_doi

        assert _normalize_doi("  10.1234/test  ") == "10.1234/test"

    def test_uppercased(self):
        from zotmcp.zotero_write import _normalize_doi

        assert _normalize_doi("10.1234/TEST.ABC") == "10.1234/test.abc"


# ────────────────────────────────────────────────────────────────────────────
# Source resolver tests (HTTP mocked with respx)
# ────────────────────────────────────────────────────────────────────────────

ARXIV_XML_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <title>Test arXiv Paper Title</title>
    <summary>This is the abstract of the paper.</summary>
    <published>2026-05-01T00:00:00Z</published>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <arxiv:doi>10.9999/arxiv.test</arxiv:doi>
  </entry>
</feed>"""


async def test_resolve_arxiv_id():
    """arXiv API mock → PaperInfo with correct fields."""
    with respx.mock:
        respx.get(
            "https://export.arxiv.org/api/query?id_list=2605.29800"
        ).mock(return_value=httpx.Response(200, text=ARXIV_XML_RESPONSE))

        from zotmcp.source_resolver import resolve_paper

        result = await resolve_paper("2605.29800")

    assert result.title == "Test arXiv Paper Title"
    assert result.arxiv_id == "2605.29800"
    assert result.item_type == "preprint"
    assert result.pdf_url == "https://arxiv.org/pdf/2605.29800.pdf"
    assert result.pdf_source == "arxiv"
    assert "Alice Smith" in result.authors
    assert "Bob Jones" in result.authors
    assert result.year == 2026


async def test_resolve_arxiv_id_with_prefix():
    """arxiv: prefix is detected and stripped."""
    with respx.mock:
        respx.get(
            "https://export.arxiv.org/api/query?id_list=2605.29800"
        ).mock(return_value=httpx.Response(200, text=ARXIV_XML_RESPONSE))

        from zotmcp.source_resolver import resolve_paper

        result = await resolve_paper("arxiv:2605.29800")

    assert result.arxiv_id == "2605.29800"
    assert result.pdf_url == "https://arxiv.org/pdf/2605.29800.pdf"


CROSSREF_RESPONSE = {
    "message": {
        "title": ["Test Journal Article"],
        "author": [
            {"given": "Jane", "family": "Doe"},
            {"given": "John", "family": "Smith"},
        ],
        "published-print": {"date-parts": [[2024]]},
        "type": "journal-article",
        "abstract": "This is the abstract.",
    }
}

UNPAYWALL_HIT = {
    "is_oa": True,
    "best_oa_location": {"url_for_pdf": "https://example.com/paper.pdf"},
}

UNPAYWALL_MISS = {
    "is_oa": False,
    "best_oa_location": None,
}


async def test_resolve_doi_with_unpaywall_hit():
    """CrossRef + Unpaywall return metadata + OA PDF URL."""
    doi = "10.1234/testdoi"
    email = "nic.suzor@gmail.com"

    with respx.mock:
        respx.get(f"https://api.crossref.org/works/{doi}").mock(
            return_value=httpx.Response(200, json=CROSSREF_RESPONSE)
        )
        respx.get(
            f"https://api.unpaywall.org/v2/{doi}?email={email}"
        ).mock(return_value=httpx.Response(200, json=UNPAYWALL_HIT))

        from zotmcp.source_resolver import resolve_paper

        result = await resolve_paper(doi)

    assert result.title == "Test Journal Article"
    assert result.doi == doi
    assert result.item_type == "journalArticle"
    assert result.pdf_url == "https://example.com/paper.pdf"
    assert result.pdf_source == "unpaywall"
    assert result.year == 2024
    assert "Jane Doe" in result.authors


async def test_resolve_doi_no_free_pdf():
    """Unpaywall miss + Semantic Scholar miss → pdf_url is None."""
    doi = "10.9999/closed"
    email = "nic.suzor@gmail.com"

    with respx.mock:
        respx.get(f"https://api.crossref.org/works/{doi}").mock(
            return_value=httpx.Response(200, json=CROSSREF_RESPONSE)
        )
        respx.get(
            f"https://api.unpaywall.org/v2/{doi}?email={email}"
        ).mock(return_value=httpx.Response(200, json=UNPAYWALL_MISS))
        respx.get(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
            "?fields=openAccessPdf,title,authors,year,abstract"
        ).mock(return_value=httpx.Response(200, json={"openAccessPdf": None}))

        from zotmcp.source_resolver import resolve_paper

        result = await resolve_paper(doi)

    assert result.pdf_url is None
    assert result.pdf_source is None


async def test_resolve_doi_semantic_scholar_fallback():
    """Unpaywall miss → Semantic Scholar provides the PDF URL."""
    doi = "10.5555/s2fallback"
    email = "nic.suzor@gmail.com"

    s2_response = {
        "openAccessPdf": {"url": "https://s2.example.com/paper.pdf"},
        "title": "S2 Title",
        "authors": [{"name": "S2 Author"}],
        "year": 2023,
        "abstract": "S2 abstract",
    }

    with respx.mock:
        respx.get(f"https://api.crossref.org/works/{doi}").mock(
            return_value=httpx.Response(200, json=CROSSREF_RESPONSE)
        )
        respx.get(
            f"https://api.unpaywall.org/v2/{doi}?email={email}"
        ).mock(return_value=httpx.Response(200, json=UNPAYWALL_MISS))
        respx.get(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
            "?fields=openAccessPdf,title,authors,year,abstract"
        ).mock(return_value=httpx.Response(200, json=s2_response))

        from zotmcp.source_resolver import resolve_paper

        result = await resolve_paper(doi)

    assert result.pdf_url == "https://s2.example.com/paper.pdf"
    assert result.pdf_source == "semantic_scholar"
