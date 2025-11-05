#!/usr/bin/env python3
"""Verification tool to validate corruption detection outputs before database changes.

This script applies conservative removal filters to corrupted documents and generates
verification outputs for human review. NO DATABASE MODIFICATIONS are made.

Conservative removal criteria:
- severity == 'empty'
- corruption_percentage >= 50
- cid_count >= 50
- Repetitive patterns (>50% single char or dots)
"""

import random
from collections import Counter


def detect_repetitive_pattern(text: str) -> bool:
    """Detect if text has repetitive patterns (>50% single char or dots).

    Args:
        text: Text content to analyze

    Returns:
        bool: True if text has >50% single character repetition or dots
    """
    if not text or len(text.strip()) == 0:
        return False

    # Remove whitespace for character counting
    clean_text = text.replace(" ", "").replace("\n", "").replace("\t", "")

    if len(clean_text) == 0:
        return False

    # Count character frequencies
    char_counts = Counter(clean_text)

    # Check if any single character makes up >50% of text
    total_chars = len(clean_text)
    for char, count in char_counts.items():
        percentage = (count / total_chars) * 100
        if percentage > 50:
            return True

    # Check specifically for dots (common corruption pattern)
    dot_count = clean_text.count(".")
    dot_percentage = (dot_count / total_chars) * 100
    if dot_percentage > 50:
        return True

    return False


def should_remove_document(doc: dict) -> bool:
    """Apply conservative removal criteria to determine if document should be removed.

    Conservative criteria (ANY triggers removal):
    - severity == 'empty'
    - corruption_percentage >= 50
    - cid_count >= 50
    - Repetitive pattern detected (>50% single char)

    Args:
        doc: Document dict with keys: document_id, severity, corruption_percentage,
             cid_count, detected_language, text_preview

    Returns:
        bool: True if document should be removed, False otherwise

    Raises:
        KeyError: If required keys are missing from document dict
    """
    # Validate required keys exist (fail-fast - no defaults)
    required_keys = ["severity", "corruption_percentage", "cid_count", "text_preview"]
    missing_keys = [key for key in required_keys if key not in doc]
    if missing_keys:
        raise KeyError(f"Document missing required keys: {missing_keys}")

    # Criterion 1: Empty documents
    if doc["severity"] == "empty":
        return True

    # Criterion 2: High corruption percentage (>= 50%)
    if doc["corruption_percentage"] >= 50:
        return True

    # Criterion 3: High CID count (>= 50)
    if doc["cid_count"] >= 50:
        return True

    # Criterion 4: Repetitive pattern in text
    if detect_repetitive_pattern(doc["text_preview"]):
        return True

    return False


def get_removal_reason(doc: dict) -> str:
    """Categorize why a document should be removed.

    Args:
        doc: Document dict with corruption metrics

    Returns:
        str: Removal reason category - 'empty', 'high_corruption', 'high_cid', 'repetitive_pattern'

    Raises:
        KeyError: If required keys are missing from document dict
    """
    # Validate required keys exist (fail-fast - no defaults)
    required_keys = ["severity", "corruption_percentage", "cid_count", "text_preview"]
    missing_keys = [key for key in required_keys if key not in doc]
    if missing_keys:
        raise KeyError(f"Document missing required keys: {missing_keys}")

    # Check criteria in priority order
    if doc["severity"] == "empty":
        return "empty"

    if doc["corruption_percentage"] >= 50:
        return "high_corruption"

    if doc["cid_count"] >= 50:
        return "high_cid"

    if detect_repetitive_pattern(doc["text_preview"]):
        return "repetitive_pattern"

    # Should not reach here if document passes should_remove_document()
    raise ValueError(f"Document {doc.get('document_id', 'unknown')} does not match any removal criteria")


def generate_random_samples(documents: list, count: int) -> list:
    """Generate random sample of documents for verification.

    Args:
        documents: List of document dicts to sample from
        count: Number of samples to generate

    Returns:
        list: Random sample of documents (up to count, or all if fewer available)
    """
    if not documents:
        return []

    # Return all documents if fewer than requested count
    if len(documents) <= count:
        return documents.copy()

    # Return random sample of requested count
    return random.sample(documents, count)


def calculate_statistics(all_documents: list, documents_to_remove: list) -> dict:
    """Calculate statistics about removal operation.

    Args:
        all_documents: Complete list of all corrupted documents scanned
        documents_to_remove: List of documents that will be removed

    Returns:
        dict: Statistics including counts, percentages, and breakdown by removal reason
    """
    total = len(all_documents)
    to_remove = len(documents_to_remove)
    to_keep = total - to_remove

    removal_percentage = (to_remove / total * 100) if total > 0 else 0.0

    # Categorize removals by reason
    removal_by_reason = {
        "empty": 0,
        "high_corruption": 0,
        "high_cid": 0,
        "repetitive_pattern": 0
    }

    for doc in documents_to_remove:
        reason = get_removal_reason(doc)
        removal_by_reason[reason] += 1

    return {
        "total_documents": total,
        "documents_to_remove": to_remove,
        "documents_to_keep": to_keep,
        "removal_percentage": removal_percentage,
        "removal_by_reason": removal_by_reason
    }
