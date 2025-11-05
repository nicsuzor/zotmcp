"""Test enhanced corruption detection on real-world patterns.

This test suite validates that the improved corruption detection in text_quality.py
catches the specific corruption patterns we observed in ChromaDB chunks.
"""

import pytest
from text_quality import detect_text_corruption


def test_character_separation_corruption():
    """Test that character-by-character separation is detected as corruption.

    This pattern was found in MBGHP5HR Chunk 2 and EFWDZDU2 Chunk 2,
    where text appears as single characters on separate lines with excessive whitespace.
    """
    # Example from MBGHP5HR Chunk 2: "h T . y l d a o r b d e t a n i"
    corrupted_text = """h
T
.
y
l
d
a
o
r
b
d
e
t
a
n
i
m
u
l
l
i
s
s
i
d
"""

    result = detect_text_corruption(corrupted_text)

    assert result["is_corrupted"], "Character separation should be detected as corruption"
    assert result["avg_line_length"] < 10, f"Average line length should be < 10, got {result['avg_line_length']}"
    assert result["corruption_percentage"] > 0, "Should have non-zero corruption percentage"


def test_excessive_newline_corruption():
    """Test that excessive newline ratios are detected as corruption.

    Text with >10% newlines indicates poor OCR quality or formatting issues.
    """
    # Create text with high newline ratio
    corrupted_text = "word\n\n\nword\n\n\nword\n\n\nword\n\n\n" * 10

    result = detect_text_corruption(corrupted_text)

    assert result["is_corrupted"], "Excessive newlines should be detected as corruption"
    assert result["newline_ratio"] > 10.0, f"Newline ratio should be > 10%, got {result['newline_ratio']}"


def test_cid_pattern_corruption():
    """Test that CID encoding artifacts are detected as corruption."""
    corrupted_text = "This text has (cid:123) encoding (cid:456) artifacts (cid:789) throughout."

    result = detect_text_corruption(corrupted_text)

    assert result["is_corrupted"], "CID patterns should be detected as corruption"
    assert result["cid_count"] == 3, f"Should find 3 CID patterns, got {result['cid_count']}"


def test_clean_text_not_flagged():
    """Test that clean, well-formatted text is not flagged as corrupted."""
    clean_text = """This is a well-formatted paragraph with normal sentences.

It has appropriate line breaks and reasonable paragraph structure.
The text flows naturally and contains complete words and sentences.

This represents what we expect from good quality OCR or native digital text.
"""

    result = detect_text_corruption(clean_text)

    assert not result["is_corrupted"], f"Clean text should not be flagged as corrupted: {result}"


def test_short_text_not_corrupted():
    """Test that short but valid text is not flagged as corrupted."""
    short_text = "Title\n\nAbstract: This is a short abstract."

    result = detect_text_corruption(short_text)

    # Short text with reasonable structure should not be flagged
    assert not result["is_corrupted"], f"Short valid text should not be corrupted: {result}"


def test_empty_text_is_corrupted():
    """Test that empty text is flagged as 100% corrupted."""
    result = detect_text_corruption("")

    assert result["is_corrupted"], "Empty text should be corrupted"
    assert result["corruption_percentage"] == 100.0, "Empty text should have 100% corruption"


def test_whitespace_only_is_corrupted():
    """Test that whitespace-only text is flagged as corrupted."""
    result = detect_text_corruption("   \n\n   \n   ")

    assert result["is_corrupted"], "Whitespace-only text should be corrupted"
    assert result["corruption_percentage"] == 100.0, "Whitespace-only should have 100% corruption"


@pytest.mark.parametrize("text,should_be_corrupted,reason", [
    # Character separation patterns
    ("a\nb\nc\nd\ne\nf\ng\nh\ni\nj\nk", True, "Single characters on lines"),
    ("ab\ncd\nef\ngh\nij\nkl\nmn", True, "Very short lines"),

    # Excessive newlines
    ("word\n\n\n\n\nword\n\n\n\n\nword", True, "Multiple consecutive newlines"),

    # CID patterns
    ("Normal text (cid:1) with (cid:2) artifacts", True, "CID encoding artifacts"),

    # Clean text
    ("This is a normal paragraph with complete sentences.", False, "Normal paragraph"),
    ("Title\n\nBody text that is well formatted.", False, "Title and body"),
])
def test_corruption_detection_patterns(text, should_be_corrupted, reason):
    """Parameterized test for various corruption patterns."""
    result = detect_text_corruption(text)

    assert result["is_corrupted"] == should_be_corrupted, (
        f"Text should {'be' if should_be_corrupted else 'not be'} corrupted ({reason}). "
        f"Got: is_corrupted={result['is_corrupted']}, "
        f"corruption_percentage={result['corruption_percentage']}, "
        f"newline_ratio={result['newline_ratio']}, "
        f"avg_line_length={result['avg_line_length']}"
    )
