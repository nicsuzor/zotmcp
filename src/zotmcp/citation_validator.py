"""Citation validation processor for Buttermilk pipeline.

This processor validates LLM-generated citations before they are stored in
the vector database. It catches corrupt citations caused by:
1. PDF extraction artifacts (excessive whitespace, garbage text)
2. LLM hallucination/elaboration (commentary instead of citations)

Should be placed AFTER the Citator and BEFORE vectorization.
"""

import re
from typing import AsyncGenerator

from pydantic import BaseModel, Field

from buttermilk import logger
from buttermilk._core.processing_context import ProcessingContext
from buttermilk._core.types import Record


# Validation constants
MAX_CITATION_LENGTH = 500  # Reasonable max for a well-formed citation
WHITESPACE_PATTERN = re.compile(r"[\s\n\r\t]{10,}")  # 10+ consecutive whitespace


class CitationValidationResult(BaseModel):
    """Result of citation validation."""

    is_valid: bool
    citation: str
    issues: list[str] = Field(default_factory=list)


def validate_citation(citation: str | None) -> CitationValidationResult:
    """Validate a citation string for corruption patterns.

    Args:
        citation: The citation string to validate

    Returns:
        CitationValidationResult with validation status and any issues found
    """
    if citation is None:
        return CitationValidationResult(
            is_valid=False, citation="", issues=["citation is None"]
        )

    if not citation.strip():
        return CitationValidationResult(
            is_valid=False, citation="", issues=["citation is empty"]
        )

    issues = []

    # Check for excessive length
    if len(citation) > MAX_CITATION_LENGTH:
        issues.append(f"length={len(citation)} exceeds max={MAX_CITATION_LENGTH}")

    # Check for whitespace corruption
    if WHITESPACE_PATTERN.search(citation):
        issues.append("contains 10+ consecutive whitespace characters")

    # Check for placeholder text
    placeholder_patterns = [
        "Citation not available",
        "Unable to generate citation",
        "Error generating citation",
        "N/A",
    ]
    for pattern in placeholder_patterns:
        if pattern.lower() in citation.lower():
            issues.append(f"contains placeholder text: '{pattern}'")
            break

    is_valid = len(issues) == 0

    return CitationValidationResult(is_valid=is_valid, citation=citation, issues=issues)


def clean_citation(citation: str) -> str:
    """Attempt to clean a corrupted citation.

    For whitespace-only issues, we can normalize the whitespace.
    For length issues, we cannot reliably fix without re-generating.

    Args:
        citation: The citation to clean

    Returns:
        Cleaned citation string, or original if cleaning not possible
    """
    if not citation:
        return citation

    # Normalize whitespace: replace multiple whitespace with single space
    cleaned = " ".join(citation.split())

    # If still too long after whitespace normalization, we can't fix it
    if len(cleaned) > MAX_CITATION_LENGTH:
        return citation  # Return original, let validator reject it

    return cleaned


class CitationValidatorProcessor(BaseModel):
    """Validate and optionally clean LLM-generated citations.

    This processor validates citations in record metadata and either:
    1. Passes records with valid citations unchanged
    2. Cleans citations with minor issues (whitespace) and passes them
    3. Filters records with unfixable citation issues (or marks them for re-processing)

    Configuration:
        reject_invalid: If True, filter out records with invalid citations.
                       If False, mark them but pass through.
        attempt_cleanup: If True, try to clean citations with minor issues.
        log_rejections: If True, log details of rejected citations.

    Example:
        >>> processor = CitationValidatorProcessor(
        ...     reject_invalid=True,
        ...     attempt_cleanup=True
        ... )
    """

    reject_invalid: bool = Field(
        default=False,
        description="If True, filter out records with invalid citations. "
        "If False, pass through with 'citation_invalid' metadata flag.",
    )

    attempt_cleanup: bool = Field(
        default=True,
        description="If True, attempt to clean citations with minor issues "
        "(e.g., normalize whitespace). Cleaned citations are validated again.",
    )

    log_rejections: bool = Field(
        default=True,
        description="If True, log details when citations fail validation.",
    )

    async def process(self, context: ProcessingContext) -> AsyncGenerator[Record, None]:
        """Process a record by validating its citation metadata.

        Args:
            context: Unified processing context

        Yields:
            Record with validated/cleaned citation, or nothing if rejected
        """
        record = context.record
        processor_stage = context.session_id
        
        metadata = record.metadata.copy() if record.metadata else {}
        citation = metadata.get("citation")

        # No citation to validate - pass through
        if citation is None:
            yield record
            return

        # Attempt cleanup if enabled
        if self.attempt_cleanup:
            citation = clean_citation(citation)
            metadata["citation"] = citation

        # Validate citation
        result = validate_citation(citation)

        if result.is_valid:
            # Citation is clean - yield updated record
            yield record.model_copy(update={"metadata": metadata})
            return

        # Citation is invalid - log if enabled
        if self.log_rejections:
            title = getattr(record, "title", "Unknown")
            logger.warning(
                f"⚠️ Invalid citation for: {title}",
                record_id=record.record_id,
                issues=result.issues,
                citation_preview=citation[:100] if citation else None,
                processor_stage=processor_stage,
            )

        if self.reject_invalid:
            # Filter out the record
            logger.info(
                f"🚫 Rejecting record due to invalid citation: {title}",
                record_id=record.record_id,
                processor_stage=processor_stage,
            )
            return  # Do not yield

        # Pass through but mark as invalid for later re-processing
        metadata["citation_invalid"] = True
        metadata["citation_issues"] = result.issues
        yield record.model_copy(update={"metadata": metadata})
