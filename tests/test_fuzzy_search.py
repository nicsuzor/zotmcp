"""Quick test script to verify fuzzy matching functionality."""

import sys

sys.path.insert(0, "src")

from search_utils import (
    fuzzy_match_author,
    fuzzy_match_title,
    normalize_author_name,
    parse_year_from_date,
    filter_by_date_range,
)


def test_author_normalization():
    """Test author name normalization."""
    print("Testing author name normalization...")

    test_cases = [
        ("Smith, John", "john smith"),
        ("John Smith", "john smith"),
        ("Smith, J.", "j smith"),
        ("SMITH, JOHN", "john smith"),
    ]

    for input_name, expected in test_cases:
        result = normalize_author_name(input_name)
        status = "✓" if result == expected else "✗"
        print(
            f"  {status} normalize_author_name('{input_name}') = '{result}' (expected: '{expected}')"
        )


def test_fuzzy_author_matching():
    """Test fuzzy author matching with typos and variations."""
    print("\nTesting fuzzy author matching...")

    # Test cases: (query, creators_field, threshold, should_match)
    test_cases = [
        ("Suzor", "Nicolas Suzor; Brian Fitzgerald", 70, True),
        ("Nick Suzor", "Nicolas Suzor; Brian Fitzgerald", 70, True),
        ("Suzor, N", "Nicolas Suzor; Brian Fitzgerald", 60, True),
        ("John Smith", "Smith, John; Doe, Jane", 70, True),
        ("Jon Smith", "Smith, John; Doe, Jane", 70, True),  # Typo in first name
        ("Smyth", "Smith, John", 60, True),  # Fuzzy last name match
        ("Completely Different", "Smith, John", 70, False),
    ]

    for query, creators, threshold, should_match in test_cases:
        is_match, score, matched_name = fuzzy_match_author(query, creators, threshold)
        status = "✓" if is_match == should_match else "✗"
        print(f"  {status} fuzzy_match_author('{query}', '{creators}', {threshold})")
        print(f"     Match: {is_match}, Score: {score:.1f}, Matched: '{matched_name}'")


def test_fuzzy_title_matching():
    """Test fuzzy title matching."""
    print("\nTesting fuzzy title matching...")

    test_cases = [
        ("machine learning", "Machine Learning for Everyone", 60, True),
        ("AI ethics", "The Ethics of Artificial Intelligence", 50, True),
        ("privacy law", "Privacy and Data Protection Law", 60, True),
        ("completely unrelated", "Machine Learning for Everyone", 60, False),
    ]

    for query, title, threshold, should_match in test_cases:
        is_match, score = fuzzy_match_title(query, title, threshold)
        status = "✓" if is_match == should_match else "✗"
        print(f"  {status} fuzzy_match_title('{query}', '{title}', {threshold})")
        print(f"     Match: {is_match}, Score: {score:.1f}")


def test_date_parsing():
    """Test date parsing from various formats."""
    print("\nTesting date parsing...")

    test_cases = [
        ("2024", 2024),
        ("2024-01-15", 2024),
        ("Jan 2024", 2024),
        ("2024/01/15", 2024),
        ("invalid", None),
    ]

    for date_str, expected in test_cases:
        result = parse_year_from_date(date_str)
        status = "✓" if result == expected else "✗"
        print(
            f"  {status} parse_year_from_date('{date_str}') = {result} (expected: {expected})"
        )


def test_date_filtering():
    """Test date range filtering."""
    print("\nTesting date range filtering...")

    metadata_2023 = {"date": "2023-05-15"}
    metadata_2020 = {"date": "2020"}
    metadata_no_date = {}

    test_cases = [
        (metadata_2023, 2020, 2024, True),
        (metadata_2023, 2024, 2025, False),
        (metadata_2020, 2020, 2024, True),
        (metadata_2020, 2021, 2024, False),
        (metadata_no_date, 2020, 2024, False),
        (metadata_2023, None, None, True),  # No filter
    ]

    for meta, date_from, date_to, expected in test_cases:
        result = filter_by_date_range(meta, date_from, date_to)
        status = "✓" if result == expected else "✗"
        date_val = meta.get("date", "no date")
        print(
            f"  {status} filter_by_date_range(date='{date_val}', {date_from}-{date_to}) = {result} (expected: {expected})"
        )


if __name__ == "__main__":
    print("=" * 60)
    print("FUZZY SEARCH UTILITIES TEST SUITE")
    print("=" * 60)

    test_author_normalization()
    test_fuzzy_author_matching()
    test_fuzzy_title_matching()
    test_date_parsing()
    test_date_filtering()

    print("\n" + "=" * 60)
    print("Testing complete!")
    print("=" * 60)
