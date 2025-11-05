"""Tests for text corruption detection module.

Tests validate corruption detection logic for CID patterns, language detection,
and document-level quality analysis.
"""
import pytest
from pathlib import Path


def test_detect_text_corruption_with_cid_patterns():
    """Test detect_text_corruption() identifies CID pattern corruption."""
    # Arrange
    from src.text_quality import detect_text_corruption

    text_with_cid = "This is a document with (cid:1) and (cid:2) and (cid:3) corruption patterns."

    # Act
    result = detect_text_corruption(text_with_cid)

    # Assert
    assert isinstance(result, dict), "Should return a dictionary"
    assert "is_corrupted" in result, "Should have is_corrupted key"
    assert "corruption_percentage" in result, "Should have corruption_percentage key"
    assert "cid_count" in result, "Should have cid_count key"
    assert "detected_language" in result, "Should have detected_language key"

    assert result["is_corrupted"] == True, "Text with CID patterns should be marked as corrupted"
    assert result["cid_count"] == 3, "Should detect 3 CID patterns"
    assert result["cid_count"] > 0, "CID count should be greater than 0"


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
