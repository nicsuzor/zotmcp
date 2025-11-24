"""Tests for search_utils module."""

from src.search_utils import extract_author_names


def test_extract_author_names_zotero_list_format():
    """Test that extract_author_names handles Zotero list-of-dicts format.

    This test demonstrates the bug: Zotero stores creators as list of dicts,
    but extract_author_names expects string input.
    """
    creators_list = [
        {"creatorType": "author", "firstName": "Tarleton", "lastName": "Gillespie"}
    ]
    result = extract_author_names(creators_list)
    # Should find the author name in normalized form
    assert any("gillespie" in name.lower() for name in result), (
        f"Expected 'gillespie' in results, got: {result}"
    )
