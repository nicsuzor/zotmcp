"""Tests for text corruption detection module.

Tests validate corruption detection logic for CID patterns, language detection,
and document-level quality analysis.
"""
import pytest
from pathlib import Path


def test_detect_text_corruption_with_cid_patterns():
    """Test detect_text_corruption() identifies heavy CID pattern corruption.

    Updated to use 20+ CID patterns to reflect new threshold that ignores
    minor header CIDs (1-19 patterns).
    """
    # Arrange
    from src.text_quality import detect_text_corruption

    # Create text with 25 CID patterns (well above threshold of 20)
    cid_patterns = " ".join(f"(cid:{i})" for i in range(25))
    text_with_cid = f"This is a heavily corrupted document with {cid_patterns} patterns."

    # Act
    result = detect_text_corruption(text_with_cid)

    # Assert
    assert isinstance(result, dict), "Should return a dictionary"
    assert "is_corrupted" in result, "Should have is_corrupted key"
    assert "corruption_percentage" in result, "Should have corruption_percentage key"
    assert "cid_count" in result, "Should have cid_count key"
    assert "detected_language" in result, "Should have detected_language key"

    assert result["is_corrupted"] == True, "Text with 20+ CID patterns should be marked as corrupted"
    assert result["cid_count"] == 25, "Should detect 25 CID patterns"
    assert result["cid_count"] >= 20, "CID count should be >= 20 to trigger corruption flag"


def test_detect_text_corruption_with_clean_text():
    """Test detect_text_corruption() returns clean for normal text."""
    # Arrange
    from src.text_quality import detect_text_corruption

    clean_text = "This is a perfectly normal document with no corruption at all."

    # Act
    result = detect_text_corruption(clean_text)

    # Assert
    assert isinstance(result, dict)
    assert result["is_corrupted"] == False, "Clean text should not be marked as corrupted"
    assert result["cid_count"] == 0, "Clean text should have 0 CID patterns"
    assert result["corruption_percentage"] == 0.0, "Clean text should have 0% corruption"


def test_detect_text_corruption_with_empty_text():
    """Test detect_text_corruption() handles empty text as 100% corrupted."""
    # Arrange
    from src.text_quality import detect_text_corruption

    # Act
    result = detect_text_corruption("")

    # Assert
    assert result["is_corrupted"] == True, "Empty text should be marked as corrupted"
    assert result["corruption_percentage"] == 100.0, "Empty text should be 100% corrupted"


def test_analyze_document_quality_aggregates_chunks():
    """Test analyze_document_quality() aggregates corruption across chunks."""
    # Arrange
    from src.text_quality import analyze_document_quality

    chunks = [
        "Normal text chunk 1",
        "Normal text chunk 2",
        "(cid:1)(cid:2)(cid:3)(cid:4)(cid:5) corrupted chunk",
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

    # Create 100 chunks where 96 are corrupt
    chunks = ["(cid:1)(cid:2)(cid:3)" for _ in range(96)]
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
    assert result["is_corrupted"] == False, \
        "Minor CID count in header should NOT flag document as corrupted"
    assert result["corruption_percentage"] < 1.0, \
        "Minor CID should result in very low corruption percentage"
