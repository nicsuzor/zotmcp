"""Tests for the citation validation processor.

These tests verify that:
1. Valid citations pass through unchanged
2. Citations with excessive length are detected
3. Citations with whitespace corruption are detected
4. Cleanup works for fixable issues
5. Placeholder text is detected
"""

import pytest
from buttermilk._core.processing_context import ProcessingContext
from zotmcp.citation_validator import (
    CitationValidationResult,
    CitationValidatorProcessor,
    MAX_CITATION_LENGTH,
    clean_citation,
    validate_citation,
)


class TestValidateCitation:
    """Tests for the validate_citation function."""

    def test_valid_citation_passes(self):
        """A normal citation should pass validation."""
        citation = (
            "Smith, J. (2023). Understanding AI Ethics. "
            "Journal of AI Research, 15(2), 100-120. "
            "https://doi.org/10.1234/jair.2023.001"
        )
        result = validate_citation(citation)

        assert result.is_valid is True
        assert result.citation == citation
        assert result.issues == []

    def test_none_citation_fails(self):
        """None citation should fail validation."""
        result = validate_citation(None)

        assert result.is_valid is False
        assert "citation is None" in result.issues

    def test_empty_citation_fails(self):
        """Empty citation should fail validation."""
        result = validate_citation("")
        assert result.is_valid is False
        assert "citation is empty" in result.issues

        result = validate_citation("   ")
        assert result.is_valid is False
        assert "citation is empty" in result.issues

    def test_excessive_length_detected(self):
        """Citations over 500 characters should be flagged."""
        long_citation = "A" * (MAX_CITATION_LENGTH + 1)
        result = validate_citation(long_citation)

        assert result.is_valid is False
        assert any("exceeds max" in issue for issue in result.issues)

    def test_whitespace_corruption_detected(self):
        """Citations with 10+ consecutive whitespace should be flagged."""
        # 10 newlines
        corrupt = "Smith (2023). Title." + "\n" * 10 + "More text"
        result = validate_citation(corrupt)

        assert result.is_valid is False
        assert any("consecutive whitespace" in issue for issue in result.issues)

        # 15 spaces
        corrupt2 = "Smith (2023)." + " " * 15 + "Journal."
        result2 = validate_citation(corrupt2)

        assert result2.is_valid is False

    def test_nine_whitespace_ok(self):
        """9 consecutive whitespace should be ok (threshold is 10)."""
        ok_citation = "Smith (2023)." + " " * 9 + "Journal of X."
        result = validate_citation(ok_citation)

        # Should not flag whitespace issue (might flag length if too long)
        assert not any("consecutive whitespace" in issue for issue in result.issues)

    def test_placeholder_text_detected(self):
        """Placeholder citations should be flagged."""
        placeholders = [
            "Citation not available",
            "Unable to generate citation",
            "Error generating citation: timeout",
            "N/A",
        ]

        for placeholder in placeholders:
            result = validate_citation(placeholder)
            assert result.is_valid is False
            assert any("placeholder" in issue for issue in result.issues)


class TestCleanCitation:
    """Tests for the clean_citation function."""

    def test_normalizes_whitespace(self):
        """Multiple whitespace should be normalized to single space."""
        dirty = "Smith (2023).\n\n\n\n\nTitle of Article.   Journal, 1(2)."
        cleaned = clean_citation(dirty)

        assert cleaned == "Smith (2023). Title of Article. Journal, 1(2)."
        assert "\n" not in cleaned
        assert "  " not in cleaned

    def test_preserves_valid_citation(self):
        """Valid citation should be unchanged."""
        valid = "Smith, J. (2023). Title. Journal, 1(2), 10-20."
        cleaned = clean_citation(valid)

        assert cleaned == valid

    def test_returns_original_if_still_too_long(self):
        """If cleaning doesn't fix length, return original."""
        # Create a citation that's too long even after whitespace removal
        too_long = "A" * (MAX_CITATION_LENGTH + 100)
        cleaned = clean_citation(too_long)

        # Should return original since we can't fix length
        assert cleaned == too_long


class TestCitationValidatorProcessor:
    """Tests for the CitationValidatorProcessor class."""

    @pytest.fixture
    def mock_record(self):
        """Create a mock Record-like object."""
        from unittest.mock import MagicMock

        def create_record(citation=None, title="Test Title"):
            record = MagicMock()
            record.record_id = "TEST123"
            record.metadata = {"title": title}
            if citation is not None:
                record.metadata["citation"] = citation

            def model_copy(update=None):
                new_record = MagicMock()
                new_record.record_id = record.record_id
                new_record.metadata = record.metadata.copy()
                if update and "metadata" in update:
                    new_record.metadata.update(update["metadata"])
                return new_record

            record.model_copy = model_copy
            return record

        return create_record

    @pytest.mark.anyio
    async def test_valid_citation_passes_through(self, mock_record):
        """Records with valid citations should pass through unchanged."""
        processor = CitationValidatorProcessor()
        record = mock_record(citation="Smith (2023). Title. Journal, 1(2).")

        results = [r async for r in processor.process(ProcessingContext(session_id="test", record=record))]

        assert len(results) == 1
        assert results[0].metadata["citation"] == "Smith (2023). Title. Journal, 1(2)."
        assert "citation_invalid" not in results[0].metadata

    @pytest.mark.anyio
    async def test_no_citation_passes_through(self, mock_record):
        """Records without citation should pass through."""
        processor = CitationValidatorProcessor()
        record = mock_record(citation=None)

        results = [r async for r in processor.process(ProcessingContext(session_id="test", record=record))]

        assert len(results) == 1

    @pytest.mark.anyio
    async def test_whitespace_cleaned_automatically(self, mock_record):
        """Citations with whitespace should be cleaned if attempt_cleanup=True."""
        processor = CitationValidatorProcessor(attempt_cleanup=True)
        dirty_citation = "Smith (2023).\n\n\n\n\n\n\n\n\n\n\nTitle."
        record = mock_record(citation=dirty_citation)

        results = [r async for r in processor.process(ProcessingContext(session_id="test", record=record))]

        assert len(results) == 1
        assert results[0].metadata["citation"] == "Smith (2023). Title."
        assert results[0].metadata.get("citation_cleaned") is True

    @pytest.mark.anyio
    async def test_invalid_marked_when_not_rejected(self, mock_record):
        """Invalid citations should be marked but passed through if reject_invalid=False."""
        processor = CitationValidatorProcessor(reject_invalid=False, attempt_cleanup=False)
        # Too long to clean
        bad_citation = "A" * 1000
        record = mock_record(citation=bad_citation)

        results = [r async for r in processor.process(ProcessingContext(session_id="test", record=record))]

        assert len(results) == 1
        assert results[0].metadata.get("citation_invalid") is True
        assert len(results[0].metadata.get("citation_issues", [])) > 0

    @pytest.mark.anyio
    async def test_invalid_rejected_when_enabled(self, mock_record):
        """Invalid citations should filter record if reject_invalid=True."""
        processor = CitationValidatorProcessor(reject_invalid=True, attempt_cleanup=False)
        bad_citation = "A" * 1000
        record = mock_record(citation=bad_citation)

        results = [r async for r in processor.process(ProcessingContext(session_id="test", record=record))]

        assert len(results) == 0  # Record was filtered


class TestRealWorldCorruption:
    """Tests using patterns from actual corrupted citations found in the corpus."""

    def test_excessive_newlines_pattern(self):
        """Test pattern from YNMAD9RF - citation followed by thousands of newlines."""
        # Simulated corruption pattern
        citation = (
            "Kolla, M., Salunkhe, S., Chandrasekharan, E., & Saha, K. (2024). "
            "LLM-Mod: Can Large Language Models Assist Content Moderation?. "
            "In Extended Abstracts of the CHI Conference." + "\n" * 500
        )

        result = validate_citation(citation)
        assert result.is_valid is False
        assert any("exceeds max" in issue for issue in result.issues)
        assert any("consecutive whitespace" in issue for issue in result.issues)

    def test_cleanup_fixes_newline_pattern(self):
        """Cleanup should fix citations with trailing newlines."""
        citation = (
            "Smith, J. (2023). Title of the Article. "
            "Journal of Testing, 10(2), 100-120." + "\n" * 50
        )

        cleaned = clean_citation(citation)
        result = validate_citation(cleaned)

        assert result.is_valid is True
        assert "\n" not in cleaned

    def test_embedded_whitespace_corruption(self):
        """Test pattern where whitespace is embedded in middle of citation."""
        citation = (
            "Author (2023). Title" + " " * 20 + "with embedded" + "\t" * 15 + "whitespace."
        )

        result = validate_citation(citation)
        assert result.is_valid is False

        cleaned = clean_citation(citation)
        clean_result = validate_citation(cleaned)
        assert clean_result.is_valid is True
