"""Tests for metadata utility functions.

Tests the get_metadata_field() helper that extracts fields from both
flat and nested (zotero_data JSON) metadata structures.
"""

import json


from search_utils import get_metadata_field


class TestGetMetadataField:
    """Test metadata field extraction from flat and nested structures."""

    def test_flat_structure_title(self) -> None:
        """Extract title from flat metadata structure."""
        metadata = {"title": "Platform Governance"}
        result = get_metadata_field(metadata, "title")
        assert result == "Platform Governance"

    def test_flat_structure_doi(self) -> None:
        """Extract DOI from flat metadata structure."""
        metadata = {"doi_or_url": "10.1234/example"}
        result = get_metadata_field(metadata, "doi_or_url")
        assert result == "10.1234/example"

    def test_nested_structure_creators(self) -> None:
        """Extract creators from nested zotero_data JSON."""
        zotero_data = {
            "creators": [
                {"creatorType": "author", "firstName": "Nicolas", "lastName": "Suzor"}
            ]
        }
        metadata = {"zotero_data": json.dumps(zotero_data)}
        result = get_metadata_field(metadata, "creators")
        assert result == zotero_data["creators"]

    def test_nested_structure_item_type(self) -> None:
        """Extract itemType from nested zotero_data JSON."""
        zotero_data = {"itemType": "journalArticle"}
        metadata = {"zotero_data": json.dumps(zotero_data)}
        result = get_metadata_field(metadata, "itemType")
        assert result == "journalArticle"

    def test_nested_structure_date(self) -> None:
        """Extract date from nested zotero_data JSON."""
        zotero_data = {"date": "2020-01-15"}
        metadata = {"zotero_data": json.dumps(zotero_data)}
        result = get_metadata_field(metadata, "date")
        assert result == "2020-01-15"

    def test_flat_takes_precedence_over_nested(self) -> None:
        """Flat structure field takes precedence over nested."""
        zotero_data = {"title": "Nested Title"}
        metadata = {
            "title": "Flat Title",
            "zotero_data": json.dumps(zotero_data),
        }
        result = get_metadata_field(metadata, "title")
        assert result == "Flat Title"

    def test_missing_field_returns_none(self) -> None:
        """Return None when field doesn't exist in either structure."""
        metadata = {"title": "Some Title"}
        result = get_metadata_field(metadata, "nonexistent_field")
        assert result is None

    def test_malformed_json_returns_none(self) -> None:
        """Return None gracefully when zotero_data JSON is malformed."""
        metadata = {"zotero_data": "not valid json {{{"}
        result = get_metadata_field(metadata, "creators")
        assert result is None

    def test_missing_zotero_data_field_returns_none(self) -> None:
        """Return None when zotero_data exists but doesn't contain field."""
        zotero_data = {"itemType": "book"}
        metadata = {"zotero_data": json.dumps(zotero_data)}
        result = get_metadata_field(metadata, "creators")
        assert result is None

    def test_empty_metadata_returns_none(self) -> None:
        """Return None when metadata dict is empty."""
        metadata = {}
        result = get_metadata_field(metadata, "title")
        assert result is None
