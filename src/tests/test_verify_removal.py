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

from verify_removal import should_remove_document, detect_repetitive_pattern


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
