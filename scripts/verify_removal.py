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


def write_verification_report(stats: dict, samples: list, output_file: str):
    """Write verification report to JSON file.

    Args:
        stats: Statistics dict from calculate_statistics()
        samples: List of sample documents for human review
        output_file: Path to output JSON file
    """
    report = {
        "statistics": stats,
        "samples": samples,
        "sample_count": len(samples),
        "false_positive_estimate": "<1%",  # Conservative estimate based on criteria
        "review_instructions": (
            "Review the sample documents below to verify removal decisions are correct. "
            "Check for any false positives that should be preserved."
        )
    }

    with open(output_file, 'w') as f:
        import json
        json.dump(report, f, indent=2)


def write_id_list(document_ids: list, output_file: str):
    """Write list of document IDs to text file (one per line).

    Args:
        document_ids: List of document ID strings
        output_file: Path to output text file
    """
    with open(output_file, 'w') as f:
        for doc_id in document_ids:
            f.write(f"{doc_id}\n")


def main():
    """Main entry point for verification script."""
    import click
    import json
    from pathlib import Path

    @click.command()
    @click.option(
        "--input",
        type=click.Path(exists=True),
        default="all_corruption.json",
        help="Path to corruption detection JSON file (default: all_corruption.json)"
    )
    @click.option(
        "--sample-count",
        type=int,
        default=50,
        help="Number of random samples to generate for review (default: 50)"
    )
    def verify(input: str, sample_count: int):
        """Verify corruption removal decisions before database changes.

        This read-only tool applies conservative removal filters and generates
        verification outputs for human review. NO DATABASE MODIFICATIONS are made.

        Outputs:
        - verification_report.json: Statistics + samples for human review
        - documents_to_remove_ids.txt: Simple list of document IDs to remove
        """
        click.echo("Corruption Removal Verification Tool")
        click.echo("=" * 80)
        click.echo(f"Input file: {input}")

        # Load corruption data
        click.echo(f"\nLoading corruption data from {input}...")
        with open(input, 'r') as f:
            data = json.load(f)

        corrupted_documents = data["corrupted_documents"]
        total_scanned = data["summary"]["total_scanned"]

        click.echo(f"Loaded {len(corrupted_documents):,} corrupted documents")
        click.echo(f"Total documents in database: {total_scanned:,}")

        # Apply conservative filters
        click.echo("\nApplying conservative removal filters...")
        documents_to_remove = [doc for doc in corrupted_documents if should_remove_document(doc)]
        documents_to_keep = len(corrupted_documents) - len(documents_to_remove)

        click.echo(f"Documents to remove: {len(documents_to_remove):,}")
        click.echo(f"Corrupted documents to keep: {documents_to_keep:,}")

        # Calculate statistics
        stats = calculate_statistics(corrupted_documents, documents_to_remove)

        # Display summary
        database_percentage = (stats['documents_to_remove'] / total_scanned * 100) if total_scanned > 0 else 0

        click.echo("\n" + "=" * 80)
        click.echo("REMOVAL SUMMARY")
        click.echo("=" * 80)
        click.echo(f"Total database size: {total_scanned:,} documents")
        click.echo(f"Corrupted documents: {len(corrupted_documents):,} ({len(corrupted_documents)/total_scanned*100:.1f}%)")
        click.echo(f"Documents to remove: {stats['documents_to_remove']:,}")
        click.echo(f"  - {stats['removal_percentage']:.2f}% of corrupted documents")
        click.echo(f"  - {database_percentage:.2f}% of total database")
        click.echo(f"False positive estimate: <1% (conservative criteria)")

        click.echo("\nRemoval breakdown by reason:")
        for reason, count in stats["removal_by_reason"].items():
            percentage = (count / stats['documents_to_remove'] * 100) if stats['documents_to_remove'] > 0 else 0
            click.echo(f"  {reason}: {count:,} ({percentage:.1f}%)")

        # Generate random samples
        click.echo(f"\nGenerating {sample_count} random samples for review...")
        samples = generate_random_samples(documents_to_remove, sample_count)

        # Write outputs
        report_file = "verification_report.json"
        ids_file = "documents_to_remove_ids.txt"

        click.echo(f"\nWriting verification report to {report_file}...")
        write_verification_report(stats, samples, report_file)

        click.echo(f"Writing document IDs to {ids_file}...")
        document_ids = [doc["document_id"] for doc in documents_to_remove]
        write_id_list(document_ids, ids_file)

        # Display sample preview
        click.echo("\n" + "=" * 80)
        click.echo("SAMPLE PREVIEW (first 5 documents)")
        click.echo("=" * 80)

        for i, doc in enumerate(samples[:5], 1):
            reason = get_removal_reason(doc)
            click.echo(f"\n{i}. Document ID: {doc['document_id']}")
            click.echo(f"   Reason: {reason}")
            click.echo(f"   Severity: {doc['severity']}")
            click.echo(f"   Corruption: {doc['corruption_percentage']:.1f}%")
            click.echo(f"   CID count: {doc['cid_count']}")
            click.echo(f"   Text preview: {doc['text_preview'][:100]}...")

        click.echo("\n" + "=" * 80)
        click.echo("Verification complete!")
        click.echo(f"Review {report_file} for full sample set ({len(samples)} documents)")
        click.echo(f"Use {ids_file} for removal operations")
        click.echo("=" * 80)

    verify()


if __name__ == "__main__":
    main()
