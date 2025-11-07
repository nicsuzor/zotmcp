"""Tests for text corruption detection module.

Tests validate corruption detection logic for CID patterns, language detection,
and document-level quality analysis.
"""

import pytest


def test_detect_text_corruption_with_cid_patterns():
    """Test detect_text_corruption() identifies heavy CID pattern corruption.

    Updated to use 20+ CID patterns to reflect new threshold that ignores
    minor header CIDs (1-19 patterns).
    """
    # Arrange
    from src.text_quality import detect_text_corruption

    # Create text with 25 CID patterns (well above threshold of 20)
    cid_patterns = " ".join(f"(cid:{i})" for i in range(25))
    text_with_cid = (
        f"This is a heavily corrupted document with {cid_patterns} patterns."
    )

    # Act
    result = detect_text_corruption(text_with_cid)

    # Assert
    assert isinstance(result, dict), "Should return a dictionary"
    assert "is_corrupted" in result, "Should have is_corrupted key"
    assert "corruption_percentage" in result, "Should have corruption_percentage key"
    assert "cid_count" in result, "Should have cid_count key"
    assert "detected_language" in result, "Should have detected_language key"

    assert (
        result["is_corrupted"] is True
    ), "Text with 20+ CID patterns should be marked as corrupted"
    assert result["cid_count"] == 25, "Should detect 25 CID patterns"
    assert (
        result["cid_count"] >= 20
    ), "CID count should be >= 20 to trigger corruption flag"


def test_detect_text_corruption_with_clean_text():
    """Test detect_text_corruption() returns clean for normal text."""
    # Arrange
    from src.text_quality import detect_text_corruption

    clean_text = "This is a perfectly normal document with no corruption at all."

    # Act
    result = detect_text_corruption(clean_text)

    # Assert
    assert isinstance(result, dict)
    assert (
        result["is_corrupted"] is False
    ), "Clean text should not be marked as corrupted"
    assert result["cid_count"] == 0, "Clean text should have 0 CID patterns"
    assert (
        result["corruption_percentage"] == 0.0
    ), "Clean text should have 0% corruption"


def test_detect_text_corruption_with_empty_text():
    """Test detect_text_corruption() handles empty text as 100% corrupted."""
    # Arrange
    from src.text_quality import detect_text_corruption

    # Act
    result = detect_text_corruption("")

    # Assert
    assert result["is_corrupted"] is True, "Empty text should be marked as corrupted"
    assert (
        result["corruption_percentage"] == 100.0
    ), "Empty text should be 100% corrupted"


def test_analyze_document_quality_aggregates_chunks():
    """Test analyze_document_quality() aggregates corruption across chunks."""
    # Arrange
    from src.text_quality import analyze_document_quality

    # Create corrupt chunk with 25 CID patterns (above 20 threshold)
    corrupt_chunk = " ".join(f"(cid:{i})" for i in range(25)) + " corrupted chunk"

    chunks = [
        "Normal text chunk 1",
        "Normal text chunk 2",
        corrupt_chunk,
        "Another normal chunk",
    ]

    # Act
    result = analyze_document_quality(chunks)

    # Assert
    assert isinstance(result, dict)
    assert "total_chunks" in result
    assert "corrupted_chunks" in result
    assert "corruption_rate" in result

    assert result["total_chunks"] == 4
    assert result["corrupted_chunks"] == 1
    assert result["corruption_rate"] == 25.0  # 1 out of 4 = 25%


def test_analyze_document_quality_highly_corrupt_document():
    """Test analyze_document_quality() with 95%+ corrupt document."""
    # Arrange
    from src.text_quality import analyze_document_quality

    # Create corrupt chunk with 25 CID patterns (above 20 threshold)
    corrupt_chunk = " ".join(f"(cid:{i})" for i in range(25))

    # Create 100 chunks where 96 are corrupt
    chunks = [corrupt_chunk for _ in range(96)]
    chunks.extend(["Clean text" for _ in range(4)])

    # Act
    result = analyze_document_quality(chunks)

    # Assert
    assert result["corruption_rate"] == 96.0
    assert result["corrupted_chunks"] == 96
    assert result["total_chunks"] == 100


def test_detect_text_corruption_ignores_minor_header_cids():
    """Test that minor CID counts in headers/citations are not flagged as corrupted.

    Real-world case: HeinOnline citation headers contain a few CID characters
    (typically 1-14) but the document is otherwise clean. These should NOT be
    flagged as corrupted.

    This test will FAIL until we implement the CID threshold fix.
    """
    # Arrange
    from src.text_quality import detect_text_corruption

    # Real HeinOnline header with 4 CID characters in citation metadata
    heinonline_header = """Content downloaded/printed from
HeinOnline
Sun Jan 12 05:00:23 2020
Citations:
(cid:9)
Bluebook 20th ed.
John Smith, Privacy Law in the Digital Age, 45 Tech. L. Rev. 123 (2019).
"""

    # Act
    result = detect_text_corruption(heinonline_header)

    # Assert
    assert result["cid_count"] == 1, "Should detect the single CID pattern"
    assert (
        result["is_corrupted"] is False
    ), "Minor CID count in header should NOT flag document as corrupted"
    assert (
        result["corruption_percentage"] < 1.0
    ), "Minor CID should result in very low corruption percentage"


@pytest.mark.parametrize(
    "corrupted_chunk_count,total_chunks,threshold,expected_corrupt",
    [
        (0, 3, 66.0, False),  # 0% corrupt - all clean
        (2, 3, 66.0, True),  # 66.67% corrupt - should flag at 66% threshold
        (1, 3, 66.0, False),  # 33.33% corrupt - should NOT flag at 66% threshold
        (3, 3, 66.0, True),  # 100% corrupt - should flag
        (2, 3, 50.0, True),  # 66.67% corrupt - should flag at lower 50% threshold
        (1, 3, 50.0, False),  # 33.33% corrupt - should NOT flag at 50% threshold
    ],
)
def test_is_document_corrupt_threshold(
    corrupted_chunk_count, total_chunks, threshold, expected_corrupt
):
    """Test is_document_corrupt() with various corruption percentages and thresholds.

    Function should analyze chunks, count how many are corrupt, and return
    document-level decision based on whether corruption rate exceeds threshold.

    Args:
        corrupted_chunk_count: Number of chunks with 25+ CID patterns
        total_chunks: Total number of chunks in document
        threshold: Percentage threshold (e.g., 66.0 means 66%)
        expected_corrupt: Whether document should be flagged as corrupt
    """
    # Arrange
    from src.text_quality import is_document_corrupt

    # Create chunks with known corruption patterns
    # Corrupt chunks have 25 CID patterns (above the 20 pattern threshold)
    corrupt_chunk = " ".join(f"(cid:{i})" for i in range(25))
    clean_chunk = "This is perfectly clean academic text with no corruption."

    # Build document with specified corruption ratio
    chunks = []
    for i in range(total_chunks):
        if i < corrupted_chunk_count:
            chunks.append(corrupt_chunk)
        else:
            chunks.append(clean_chunk)

    # Act
    result = is_document_corrupt(chunks, threshold=threshold)

    # Assert - verify result structure
    assert isinstance(result, dict), "Should return a dictionary"
    assert "is_corrupt" in result, "Should have is_corrupt boolean flag"
    assert "corruption_rate" in result, "Should have corruption_rate percentage"
    assert "total_chunks" in result, "Should have total_chunks count"
    assert "corrupted_chunks" in result, "Should have corrupted_chunks count"
    assert "threshold" in result, "Should have threshold value used"

    # Assert - verify corruption detection logic
    expected_rate = (corrupted_chunk_count / total_chunks) * 100
    assert result["corruption_rate"] == pytest.approx(
        expected_rate, rel=0.01
    ), f"Corruption rate should be {expected_rate}%"
    assert result["is_corrupt"] is expected_corrupt, (
        f"With {expected_rate}% corruption and {threshold}% threshold, "
        f"is_corrupt should be {expected_corrupt}"
    )
    assert result["corrupted_chunks"] == corrupted_chunk_count
    assert result["total_chunks"] == total_chunks
    assert result["threshold"] == threshold


def test_is_document_corrupt_empty_document():
    """Test is_document_corrupt() handles empty document edge case.

    Empty documents should be treated as 100% corrupt.
    """
    # Arrange
    from src.text_quality import is_document_corrupt

    # Act
    result = is_document_corrupt([], threshold=66.0)

    # Assert
    assert result["is_corrupt"] is True, "Empty document should be flagged as corrupt"
    assert result["corruption_rate"] == 100.0, "Empty document is 100% corrupt"
    assert result["total_chunks"] == 0
    assert result["corrupted_chunks"] == 0


def test_is_document_corrupt_default_threshold():
    """Test is_document_corrupt() uses 66.0 as default threshold.

    When threshold is not specified, function should default to 66%.
    """
    # Arrange
    from src.text_quality import is_document_corrupt

    # Create document with 67% corruption (2 out of 3 chunks)
    corrupt_chunk = " ".join(f"(cid:{i})" for i in range(25))
    chunks = [corrupt_chunk, corrupt_chunk, "Clean text"]

    # Act - call without threshold parameter
    result = is_document_corrupt(chunks)

    # Assert
    assert result["threshold"] == 66.0, "Default threshold should be 66.0"
    assert result["is_corrupt"] is True, "67% corruption exceeds 66% default threshold"
