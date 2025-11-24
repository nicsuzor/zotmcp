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


def test_fuzzy_match_metadata_with_list_creators():
    """Test that fuzzy_match_metadata properly handles list-of-dicts creators field.

    Bug: In search_utils.py line 256, `str(value)` converts the creators list to
    a garbage string like "[{'firstName': 'John', 'lastName': 'Smith'}]", which
    defeats the list handling in fuzzy_match_author. The fuzzy score for exact
    matches is ~72-76 instead of >=90.
    """
    from src.search_utils import fuzzy_match_metadata

    # Zotero native format: creators as list of dicts
    metadata = {
        "creators": [
            {"creatorType": "author", "firstName": "Tarleton", "lastName": "Gillespie"}
        ],
        "title": "Some Paper Title",
    }

    is_match, score, field = fuzzy_match_metadata(
        "Tarleton Gillespie", metadata, fields=["creators"], threshold=70
    )

    # With current bug, score is ~72-76 because str() mangles the list
    # Correct behavior should yield score >= 90 for exact author match
    assert score >= 90, (
        f"Expected high score (>=90) for exact author match, got {score}. "
        "This indicates the creators list is being str() converted instead of "
        "properly processed as a list-of-dicts."
    )
    assert is_match is True, f"Expected is_match=True, got is_match={is_match}"
    assert field == "creators", f"Expected field='creators', got field='{field}'"
