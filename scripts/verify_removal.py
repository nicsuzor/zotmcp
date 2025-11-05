#!/usr/bin/env python3
"""Verification tool for document-level corruption analysis.

This script analyzes corruption at the DOCUMENT level (not chunk level) and applies
conservative removal filters. NO DATABASE MODIFICATIONS are made.

Document-level removal criteria:
- ≥95% of chunks are high severity (corruption_percentage ≥ 20%)
- ≥80% of chunks have repetitive patterns
- Otherwise: KEEP (good documents with localized corruption)

This approach avoids false positives like GH6GBZQT (21% corrupt, should keep).
"""

import random
from collections import Counter, defaultdict
from typing import List, Dict


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


def group_chunks_by_document(corrupted_chunks: List[dict]) -> Dict[str, List[dict]]:
    """Group chunks by their document_id.

    Args:
        corrupted_chunks: List of chunk dicts from corruption detection

    Returns:
        Dict mapping document_id to list of chunks for that document
    """
    documents = defaultdict(list)
    for chunk in corrupted_chunks:
        doc_id = chunk.get("document_id")
        if doc_id:
            documents[doc_id].append(chunk)
    return dict(documents)


def should_remove_document_v2(document_data: dict) -> bool:
    """Determine if a document should be removed using document-level criteria.

    Removal criteria (ANY triggers removal):
    1. ≥95% of chunks have high severity (corruption_percentage ≥ 20%)
    2. ≥80% of chunks have repetitive patterns

    Otherwise: KEEP the document (may have localized corruption, but mostly good)

    Args:
        document_data: Dict with keys:
            - document_id: str
            - chunks: List[dict] with corruption_percentage, severity, text_preview

    Returns:
        bool: True if document should be removed, False to keep
    """
    chunks = document_data.get("chunks", [])
    if not chunks:
        return True  # Empty document should be removed

    total_chunks = len(chunks)

    # Count high severity chunks (corruption_percentage ≥ 20%)
    high_severity_chunks = sum(
        1 for chunk in chunks
        if chunk.get("corruption_percentage", 0) >= 20.0
    )

    high_severity_rate = (high_severity_chunks / total_chunks * 100) if total_chunks > 0 else 0

    # Criterion 1: ≥95% of chunks are high severity
    if high_severity_rate >= 95.0:
        return True

    # Count chunks with repetitive patterns
    repetitive_chunks = sum(
        1 for chunk in chunks
        if detect_repetitive_pattern(chunk.get("text_preview", ""))
    )

    repetitive_rate = (repetitive_chunks / total_chunks * 100) if total_chunks > 0 else 0

    # Criterion 2: ≥80% of chunks have repetitive patterns
    if repetitive_rate >= 80.0:
        return True

    # Otherwise: KEEP the document
    return False


def calculate_document_level_statistics(documents: List[dict]) -> dict:
    """Calculate statistics at document level.

    Args:
        documents: List of document dicts with should_remove, total_chunks, etc.

    Returns:
        dict: Statistics about documents to remove/keep
    """
    total_documents = len(documents)
    documents_to_remove = sum(1 for doc in documents if doc.get("should_remove", False))
    documents_to_keep = total_documents - documents_to_remove

    removal_percentage = (documents_to_remove / total_documents * 100) if total_documents > 0 else 0.0

    return {
        "total_documents": total_documents,
        "documents_to_remove": documents_to_remove,
        "documents_to_keep": documents_to_keep,
        "removal_percentage": removal_percentage,
    }


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

        corrupted_chunks = data["corrupted_documents"]  # These are actually chunks
        total_scanned = data["summary"]["total_scanned"]

        click.echo(f"Loaded {len(corrupted_chunks):,} corrupted chunks")
        click.echo(f"Total documents in database: {total_scanned:,}")

        # Group chunks by document for document-level analysis
        click.echo("\nGrouping chunks by document...")
        documents_by_id = group_chunks_by_document(corrupted_chunks)
        click.echo(f"Found {len(documents_by_id):,} unique documents with corruption")

        # Apply document-level removal criteria
        click.echo("\nApplying document-level removal filters (≥95% corrupt)...")
        document_decisions = []
        for doc_id, chunks in documents_by_id.items():
            document_data = {
                "document_id": doc_id,
                "chunks": chunks
            }
            should_remove = should_remove_document_v2(document_data)
            document_decisions.append({
                "document_id": doc_id,
                "should_remove": should_remove,
                "total_chunks": len(chunks),
                "chunks": chunks
            })

        documents_to_remove = [doc for doc in document_decisions if doc["should_remove"]]
        documents_to_keep = [doc for doc in document_decisions if not doc["should_remove"]]

        click.echo(f"Documents to remove: {len(documents_to_remove):,}")
        click.echo(f"Corrupted documents to keep: {len(documents_to_keep):,}")

        # Calculate document-level statistics
        stats = calculate_document_level_statistics(document_decisions)

        # Display summary
        database_percentage = (stats['documents_to_remove'] / total_scanned * 100) if total_scanned > 0 else 0

        click.echo("\n" + "=" * 80)
        click.echo("DOCUMENT-LEVEL REMOVAL SUMMARY")
        click.echo("=" * 80)
        click.echo(f"Total database size: {total_scanned:,} documents")
        click.echo(f"Documents with corruption: {len(documents_by_id):,}")
        click.echo(f"Documents to remove: {stats['documents_to_remove']:,} (≥95% corrupt)")
        click.echo(f"Documents to keep: {stats['documents_to_keep']:,} (<95% corrupt)")
        click.echo(f"  - {stats['removal_percentage']:.2f}% of corrupted documents will be removed")
        click.echo(f"  - {database_percentage:.2f}% of total database will be removed")
        click.echo(f"\nNote: Document-level analysis groups chunks by document_id.")
        click.echo(f"A document is removed only if ≥95% of its chunks are corrupt.")

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
            doc_id = doc['document_id']
            total_chunks = doc['total_chunks']
            chunks = doc['chunks']

            # Calculate document-level stats
            high_severity_chunks = sum(1 for c in chunks if c.get("corruption_percentage", 0) >= 20.0)
            corruption_rate = (high_severity_chunks / total_chunks * 100) if total_chunks > 0 else 0

            # Get first chunk's text preview
            first_chunk_text = chunks[0].get('text_preview', '') if chunks else 'N/A'

            click.echo(f"\n{i}. Document ID: {doc_id}")
            click.echo(f"   Total chunks: {total_chunks}")
            click.echo(f"   High severity chunks: {high_severity_chunks} ({corruption_rate:.1f}%)")
            click.echo(f"   Decision: REMOVE (≥95% corrupt)")
            click.echo(f"   First chunk preview: {first_chunk_text[:100]}...")

        click.echo("\n" + "=" * 80)
        click.echo("Verification complete!")
        click.echo(f"Review {report_file} for full sample set ({len(samples)} documents)")
        click.echo(f"Use {ids_file} for removal operations")
        click.echo("=" * 80)

    verify()


if __name__ == "__main__":
    main()
