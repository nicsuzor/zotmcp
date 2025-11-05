"""Tests for document-level verification script.

Tests validate document-level corruption analysis with ≥95% threshold logic.
"""
import pytest
import json
from pathlib import Path


def test_group_chunks_by_document():
    """Test grouping chunks by document_id."""
    from scripts.verify_removal import group_chunks_by_document

    corrupted_chunks = [
        {"document_id": "DOC1", "chunk_id": "chunk1", "corruption_percentage": 90.0},
        {"document_id": "DOC1", "chunk_id": "chunk2", "corruption_percentage": 95.0},
        {"document_id": "DOC2", "chunk_id": "chunk3", "corruption_percentage": 10.0},
        {"document_id": "DOC2", "chunk_id": "chunk4", "corruption_percentage": 5.0},
    ]

    result = group_chunks_by_document(corrupted_chunks)

    assert "DOC1" in result
    assert "DOC2" in result
    assert len(result["DOC1"]) == 2
    assert len(result["DOC2"]) == 2


def test_should_remove_document_with_95_percent_corrupt():
    """Test removal when ≥95% of chunks are high severity (≥20% corruption)."""
    from scripts.verify_removal import should_remove_document_v2

    # 96 out of 100 chunks have ≥20% corruption = 96% corrupt
    chunks = [{"corruption_percentage": 25.0, "severity": "high"} for _ in range(96)]
    chunks.extend([{"corruption_percentage": 5.0, "severity": "low"} for _ in range(4)])

    document_data = {"document_id": "TEST", "chunks": chunks}

    assert should_remove_document_v2(document_data) == True


def test_should_keep_document_with_94_percent_corrupt():
    """Test keeping when only 94% of chunks are high severity (below 95% threshold)."""
    from scripts.verify_removal import should_remove_document_v2

    # 94 out of 100 chunks have ≥20% corruption = 94% corrupt
    chunks = [{"corruption_percentage": 25.0, "severity": "high"} for _ in range(94)]
    chunks.extend([{"corruption_percentage": 5.0, "severity": "low"} for _ in range(6)])

    document_data = {"document_id": "TEST", "chunks": chunks}

    assert should_remove_document_v2(document_data) == False


def test_should_remove_document_with_80_percent_repetitive():
    """Test removal when ≥80% of chunks have repetitive patterns."""
    from scripts.verify_removal import should_remove_document_v2, detect_repetitive_pattern

    # 85 out of 100 chunks have repetitive patterns
    chunks = []
    for i in range(85):
        chunks.append({
            "corruption_percentage": 10.0,
            "severity": "low",
            "text_preview": "o o o o o o o o o o o o o o o o o o o o"  # Repetitive
        })
    for i in range(15):
        chunks.append({
            "corruption_percentage": 5.0,
            "severity": "low",
            "text_preview": "Normal text without repetition here"
        })

    document_data = {"document_id": "TEST", "chunks": chunks}

    assert should_remove_document_v2(document_data) == True


def test_calculate_document_level_statistics():
    """Test document-level statistics calculation."""
    from scripts.verify_removal import calculate_document_level_statistics

    documents = [
        {"document_id": "DOC1", "should_remove": True, "total_chunks": 100, "high_severity_chunks": 98},
        {"document_id": "DOC2", "should_remove": False, "total_chunks": 50, "high_severity_chunks": 10},
        {"document_id": "DOC3", "should_remove": True, "total_chunks": 200, "high_severity_chunks": 195},
    ]

    stats = calculate_document_level_statistics(documents)

    assert stats["total_documents"] == 3
    assert stats["documents_to_remove"] == 2
    assert stats["documents_to_keep"] == 1
    assert stats["removal_percentage"] == pytest.approx(66.67, rel=0.1)
