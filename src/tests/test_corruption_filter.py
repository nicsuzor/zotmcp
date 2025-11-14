"""Tests for corruption filtering in search results.

Tests verify that search results with CID corruption patterns are properly
filtered out to prevent corrupted documents from being returned to users.

CID corruption patterns like (cid:123) appear in poorly OCR'd PDFs and indicate
that the text is not usable for research purposes.
"""

from search_utils import SearchResult, filter_corrupted_results


def test_filter_removes_cid_corruption():
    """Test filter_corrupted_results() removes results with heavy CID corruption.

    Heavy corruption is defined as 20+ CID patterns like (cid:123) in the
    document text, following the threshold used in buttermilk text quality
    analysis.

    Arrange:
        Create SearchResult objects with real corruption patterns:
        - 1 clean result with no CID patterns
        - 1 result with minor CID corruption (< 20 patterns, should keep)
        - 1 result with heavy CID corruption (>= 20 patterns, should filter)

    Act:
        Call filter_corrupted_results() with the list

    Assert:
        - Clean result is retained
        - Minor corruption result is retained (below threshold)
        - Heavy corruption result is filtered out
        - Return value is list of SearchResult objects
    """
    # Arrange: Create real SearchResult fixtures
    clean_result = SearchResult(
        item_key="CLEAN_ITEM",
        metadata={"title": "Clean Document"},
        document="This is clean text with no corruption patterns at all.",
        similarity_score=0.95,
    )

    # Minor corruption: 5 CID patterns (below 20 threshold)
    minor_cid_patterns = " ".join(f"(cid:{i})" for i in range(5))
    minor_corruption_result = SearchResult(
        item_key="MINOR_CID_ITEM",
        metadata={"title": "Document with Header CIDs"},
        document=f"HeinOnline header with {minor_cid_patterns} but otherwise clean content.",
        similarity_score=0.88,
    )

    # Heavy corruption: 25 CID patterns (above 20 threshold)
    heavy_cid_patterns = " ".join(f"(cid:{i})" for i in range(25))
    heavy_corruption_result = SearchResult(
        item_key="CORRUPT_ITEM",
        metadata={"title": "Corrupted OCR Document"},
        document=f"This document is heavily corrupted with {heavy_cid_patterns} patterns.",
        similarity_score=0.92,
    )

    # Input list with all three types
    search_results = [
        clean_result,
        minor_corruption_result,
        heavy_corruption_result,
    ]

    # Act
    filtered_results = filter_corrupted_results(search_results)

    # Assert: Verify filtering behavior
    assert isinstance(filtered_results, list), "Should return a list"
    assert len(filtered_results) == 2, (
        "Should filter out 1 heavily corrupted result, keeping 2 results"
    )

    # Verify clean result is retained
    assert any(r.item_key == "CLEAN_ITEM" for r in filtered_results), (
        "Clean result should be retained"
    )

    # Verify minor corruption result is retained
    assert any(r.item_key == "MINOR_CID_ITEM" for r in filtered_results), (
        "Minor corruption result (< 20 CID patterns) should be retained"
    )

    # Verify heavy corruption result is filtered out
    assert not any(r.item_key == "CORRUPT_ITEM" for r in filtered_results), (
        "Heavy corruption result (>= 20 CID patterns) should be filtered out"
    )

    # Verify all returned items are SearchResult objects
    for result in filtered_results:
        assert isinstance(result, SearchResult), (
            "All filtered results should be SearchResult objects"
        )


def test_filter_handles_empty_list():
    """Test filter_corrupted_results() handles empty input list.

    Following fail-fast philosophy, empty list should either:
    - Return empty list (if valid state), OR
    - Raise ValueError (if empty list is invalid input)

    This test will FAIL until implementation clarifies expected behavior.
    """
    # Act & Assert
    result = filter_corrupted_results([])

    # Verify result (implementation should define this behavior)
    assert isinstance(result, list), "Should return a list"
    assert len(result) == 0, "Empty input should return empty output"


def test_filter_handles_results_without_document_field():
    """Test filter_corrupted_results() handles SearchResults with None document.

    SearchResult.document is Optional[str], so results may have None document.
    Function should handle this gracefully - likely by keeping the result since
    we can't detect corruption without text.

    Following fail-fast philosophy, function should either:
    - Keep results with None document (can't prove corruption), OR
    - Raise ValueError (if document is required for filtering)

    This test will FAIL until implementation clarifies expected behavior.
    """
    # Arrange: SearchResult with no document text
    result_no_document = SearchResult(
        item_key="NO_DOC_ITEM",
        metadata={"title": "Metadata Only Result"},
        document=None,  # No document text available
        similarity_score=0.85,
    )

    # Act
    filtered_results = filter_corrupted_results([result_no_document])

    # Assert: Verify behavior with None document
    assert isinstance(filtered_results, list), "Should return a list"
    # Implementation should define: keep or filter results with None document?
    # For now, expect it to be kept (can't detect corruption without text)
    assert len(filtered_results) == 1, (
        "Result with None document should be kept (can't detect corruption)"
    )
