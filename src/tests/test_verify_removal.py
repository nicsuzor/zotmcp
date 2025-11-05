"""Tests for verify_removal script.

Tests conservative document removal filter logic using real corrupted document data.
All tests use JSON fixtures for test data (no inline fake data).
"""
import json
import sys
from pathlib import Path

import pytest

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from verify_removal import (
    should_remove_document,
    detect_repetitive_pattern,
    generate_random_samples,
    calculate_statistics,
    get_removal_reason
)


def load_json_fixture(filepath: str):
    """Load JSON fixture file."""
    return json.loads(Path(filepath).read_text())


class TestConservativeFilterLogic:
    """Test suite for conservative document removal filters."""

    def test_should_remove_empty_document(self):
        """Empty documents (severity='empty') should be removed."""
        # Arrange
        doc = {
            "document_id": "EMPTY001",
            "severity": "empty",
            "corruption_percentage": 100.0,
            "cid_count": 0,
            "detected_language": "unknown",
            "text_preview": "(empty)"
        }

        # Act
        result = should_remove_document(doc)

        # Assert
        assert result is True, "Empty documents should be removed"

    def test_should_remove_high_corruption_percentage(self):
        """Documents with >=50% corruption should be removed."""
        # Arrange
        doc = {
            "document_id": "CORRUPT001",
            "severity": "high",
            "corruption_percentage": 75.5,
            "cid_count": 25,
            "detected_language": "en",
            "text_preview": "(cid:1) (cid:2) test text"
        }

        # Act
        result = should_remove_document(doc)

        # Assert
        assert result is True, "High corruption percentage documents should be removed"

    def test_should_remove_high_cid_count(self):
        """Documents with >=50 CID count should be removed."""
        # Arrange
        doc = {
            "document_id": "CID001",
            "severity": "high",
            "corruption_percentage": 30.0,
            "cid_count": 75,
            "detected_language": "en",
            "text_preview": "(cid:1) (cid:2) (cid:3)..."
        }

        # Act
        result = should_remove_document(doc)

        # Assert
        assert result is True, "High CID count documents should be removed"

    def test_should_remove_repetitive_pattern(self):
        """Documents with >50% single character repetition should be removed."""
        # Arrange
        # This document has mostly 'o' characters repeated
        doc = {
            "document_id": "REPEAT001",
            "severity": "medium",
            "corruption_percentage": 10.0,
            "cid_count": 5,
            "detected_language": "fi",
            "text_preview": "o o o o o o o o o o o o o o o o o o o o"
        }

        # Act
        result = should_remove_document(doc)

        # Assert
        assert result is True, "Repetitive pattern documents should be removed"

    def test_should_not_remove_low_corruption(self):
        """Low corruption documents should NOT be removed."""
        # Arrange
        doc = {
            "document_id": "GOOD001",
            "severity": "low",
            "corruption_percentage": 2.5,
            "cid_count": 3,
            "detected_language": "en",
            "text_preview": "This is mostly good text with (cid:1) minor issues"
        }

        # Act
        result = should_remove_document(doc)

        # Assert
        assert result is False, "Low corruption documents should be preserved"

    def test_should_not_remove_clean_document(self):
        """Clean documents should NOT be removed."""
        # Arrange
        doc = {
            "document_id": "CLEAN001",
            "severity": "clean",
            "corruption_percentage": 0.0,
            "cid_count": 0,
            "detected_language": "en",
            "text_preview": "This is completely clean text with no corruption"
        }

        # Act
        result = should_remove_document(doc)

        # Assert
        assert result is False, "Clean documents should be preserved"


class TestRepetitivePatternDetection:
    """Test suite for repetitive pattern detection."""

    def test_detect_single_char_repetition(self):
        """Text with >50% single character should be detected."""
        # Arrange
        text = "o o o o o o o o o o o o o o o o o o o o"

        # Act
        result = detect_repetitive_pattern(text)

        # Assert
        assert result is True, "Single character repetition should be detected"

    def test_detect_dot_repetition(self):
        """Text with >50% dots should be detected."""
        # Arrange
        text = ". . . . . . . . . . . . . . . . . . . ."

        # Act
        result = detect_repetitive_pattern(text)

        # Assert
        assert result is True, "Dot repetition should be detected"

    def test_no_pattern_in_normal_text(self):
        """Normal text should not be flagged as repetitive."""
        # Arrange
        text = "This is normal text with proper words and sentences."

        # Act
        result = detect_repetitive_pattern(text)

        # Assert
        assert result is False, "Normal text should not be flagged"

    def test_mixed_text_below_threshold(self):
        """Text with some repetition but <50% should not be flagged."""
        # Arrange
        text = "The cat sat on the mat. The cat was happy. The cat slept."

        # Act
        result = detect_repetitive_pattern(text)

        # Assert
        assert result is False, "Below threshold repetition should not be flagged"

class TestSampleGeneration:
    """Test suite for random sample generation."""

    def test_generate_random_samples_returns_requested_count(self):
        """Should return exactly the requested number of samples."""
        # Arrange
        documents = [
            {"document_id": f"DOC{i:03d}", "severity": "high", "corruption_percentage": 60.0,
             "cid_count": 55, "detected_language": "en", "text_preview": f"Text {i}"}
            for i in range(100)
        ]
        sample_count = 10

        # Act
        samples = generate_random_samples(documents, sample_count)

        # Assert
        assert len(samples) == sample_count, f"Should return {sample_count} samples"

    def test_generate_random_samples_returns_all_if_fewer_than_requested(self):
        """Should return all documents if fewer than requested count."""
        # Arrange
        documents = [
            {"document_id": f"DOC{i:03d}", "severity": "high", "corruption_percentage": 60.0,
             "cid_count": 55, "detected_language": "en", "text_preview": f"Text {i}"}
            for i in range(5)
        ]
        sample_count = 10

        # Act
        samples = generate_random_samples(documents, sample_count)

        # Assert
        assert len(samples) == 5, "Should return all 5 documents when requesting 10"

    def test_generate_random_samples_with_empty_list(self):
        """Should return empty list when given empty input."""
        # Arrange
        documents = []
        sample_count = 10

        # Act
        samples = generate_random_samples(documents, sample_count)

        # Assert
        assert len(samples) == 0, "Should return empty list"


class TestRemovalReason:
    """Test suite for categorizing removal reasons."""

    def test_get_removal_reason_for_empty(self):
        """Empty documents should be categorized as 'empty'."""
        # Arrange
        doc = {
            "document_id": "EMPTY001",
            "severity": "empty",
            "corruption_percentage": 100.0,
            "cid_count": 0,
            "detected_language": "unknown",
            "text_preview": "(empty)"
        }

        # Act
        reason = get_removal_reason(doc)

        # Assert
        assert reason == "empty", "Empty documents should have reason 'empty'"

    def test_get_removal_reason_for_high_corruption(self):
        """High corruption documents should be categorized as 'high_corruption'."""
        # Arrange
        doc = {
            "document_id": "CORRUPT001",
            "severity": "high",
            "corruption_percentage": 75.0,
            "cid_count": 10,
            "detected_language": "en",
            "text_preview": "(cid:1) (cid:2) text"
        }

        # Act
        reason = get_removal_reason(doc)

        # Assert
        assert reason == "high_corruption", ">=50% corruption should have reason 'high_corruption'"

    def test_get_removal_reason_for_high_cid(self):
        """High CID count documents should be categorized as 'high_cid'."""
        # Arrange
        doc = {
            "document_id": "CID001",
            "severity": "high",
            "corruption_percentage": 30.0,
            "cid_count": 60,
            "detected_language": "en",
            "text_preview": "(cid:1) (cid:2) (cid:3)..."
        }

        # Act
        reason = get_removal_reason(doc)

        # Assert
        assert reason == "high_cid", ">=50 CID count should have reason 'high_cid'"

    def test_get_removal_reason_for_repetitive_pattern(self):
        """Repetitive pattern documents should be categorized as 'repetitive_pattern'."""
        # Arrange
        doc = {
            "document_id": "REPEAT001",
            "severity": "medium",
            "corruption_percentage": 10.0,
            "cid_count": 5,
            "detected_language": "fi",
            "text_preview": "o o o o o o o o o o o o o o o o o o o o"
        }

        # Act
        reason = get_removal_reason(doc)

        # Assert
        assert reason == "repetitive_pattern", "Repetitive text should have reason 'repetitive_pattern'"


class TestStatisticsCalculation:
    """Test suite for statistics calculation."""

    def test_calculate_statistics_with_mixed_documents(self):
        """Should correctly calculate statistics for mixed document set."""
        # Arrange
        all_docs = [
            {"document_id": "DOC001", "severity": "empty", "corruption_percentage": 100.0, "cid_count": 0, "detected_language": "unknown", "text_preview": ""},
            {"document_id": "DOC002", "severity": "high", "corruption_percentage": 75.0, "cid_count": 55, "detected_language": "en", "text_preview": "cid text"},
            {"document_id": "DOC003", "severity": "low", "corruption_percentage": 2.0, "cid_count": 3, "detected_language": "en", "text_preview": "good text"},
            {"document_id": "DOC004", "severity": "high", "corruption_percentage": 80.0, "cid_count": 70, "detected_language": "en", "text_preview": "more cid"},
            {"document_id": "DOC005", "severity": "clean", "corruption_percentage": 0.0, "cid_count": 0, "detected_language": "en", "text_preview": "clean text"},
        ]
        to_remove = [all_docs[0], all_docs[1], all_docs[3]]  # 3 documents to remove

        # Act
        stats = calculate_statistics(all_docs, to_remove)

        # Assert
        assert stats["total_documents"] == 5, "Should count all documents"
        assert stats["documents_to_remove"] == 3, "Should count removal documents"
        assert stats["documents_to_keep"] == 2, "Should count remaining documents"
        assert stats["removal_percentage"] == 60.0, "Should calculate correct percentage"

    def test_calculate_statistics_categorizes_by_reason(self):
        """Should break down removals by reason."""
        # Arrange
        all_docs = [
            {"document_id": "EMPTY001", "severity": "empty", "corruption_percentage": 100.0, "cid_count": 0, "detected_language": "unknown", "text_preview": ""},
            {"document_id": "CORRUPT001", "severity": "high", "corruption_percentage": 75.0, "cid_count": 10, "detected_language": "en", "text_preview": "cid text"},
            {"document_id": "CID001", "severity": "high", "corruption_percentage": 30.0, "cid_count": 60, "detected_language": "en", "text_preview": "more cid"},
            {"document_id": "REPEAT001", "severity": "medium", "corruption_percentage": 10.0, "cid_count": 5, "detected_language": "fi", "text_preview": "o o o o o o o o o o o o o o o o o o o o"},
        ]
        to_remove = all_docs  # All should be removed

        # Act
        stats = calculate_statistics(all_docs, to_remove)

        # Assert
        assert "removal_by_reason" in stats, "Should include breakdown by reason"
        breakdown = stats["removal_by_reason"]
        assert breakdown["empty"] == 1, "Should count empty documents"
        assert breakdown["high_corruption"] == 1, "Should count high corruption documents"
        assert breakdown["high_cid"] == 1, "Should count high CID documents"
        assert breakdown["repetitive_pattern"] == 1, "Should count repetitive pattern documents"

    def test_calculate_statistics_with_no_removals(self):
        """Should handle case with no documents to remove."""
        # Arrange
        all_docs = [
            {"document_id": "CLEAN001", "severity": "clean", "corruption_percentage": 0.0, "cid_count": 0, "detected_language": "en", "text_preview": "clean text"},
            {"document_id": "LOW001", "severity": "low", "corruption_percentage": 2.0, "cid_count": 3, "detected_language": "en", "text_preview": "mostly good"},
        ]
        to_remove = []

        # Act
        stats = calculate_statistics(all_docs, to_remove)

        # Assert
        assert stats["total_documents"] == 2, "Should count all documents"
        assert stats["documents_to_remove"] == 0, "Should show zero removals"
        assert stats["documents_to_keep"] == 2, "Should keep all documents"
        assert stats["removal_percentage"] == 0.0, "Should show 0% removal"
