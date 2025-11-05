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
