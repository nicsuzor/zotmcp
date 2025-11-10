#!/usr/bin/env python3
"""Diagnostic tool to identify corrupted text entries in ChromaDB collection.

This script scans the ChromaDB collection for documents with PDF encoding
artifacts (e.g., (cid:XX) patterns) that indicate failed OCR or corrupted text.

EXPERIMENTAL ENHANCEMENT: Language detection via langdetect to catch corruption
patterns without (cid:XX) markers (e.g., 'o o o o...', 't u o S...'). This feature
is subject to refinement based on false positive rates and detection accuracy.
"""

import asyncio
import json
import re
import sys
from pathlib import Path

import click
from langdetect import DetectorFactory

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from buttermilk import init_async
from buttermilk.tools import ChromaDBSearchTool
from buttermilk.utils.text_quality import detect_text_corruption, is_document_corrupt

# Pattern to detect PDF encoding artifacts like (cid:XX)
CID_PATTERN = re.compile(r"\(cid:\d+\)")

# Ensure consistent language detection results
DetectorFactory.seed = 0


def detect_corruption(text: str) -> dict:
    """Detect corruption patterns in text content.

    This is a wrapper around text_quality.detect_text_corruption() for backwards compatibility.

    Uses multiple detection methods:
    1. CID pattern matching: Detects (cid:XX) PDF encoding artifacts
    2. Newline ratio: Excessive newlines indicate corruption (>10% is suspect)
    3. Character separation: Single chars on lines indicate garbled text
    4. Language detection: Flags non-English text as potential corruption

    Args:
        text: Text content to analyze

    Returns:
        dict: Corruption analysis with keys:
            - is_corrupted: bool indicating if text has corruption (ANY signal)
            - corruption_percentage: float from 0-100 based on corruption signals
            - cid_count: int count of (cid:XX) patterns found
            - newline_ratio: float percentage of text that is newlines
            - avg_line_length: float average characters per line
            - detected_language: str language code from langdetect ('en', 'es', etc.)
    """
    return detect_text_corruption(text)


def classify_severity(corruption_result: dict) -> str:
    """Classify corruption severity based on corruption metrics.

    Args:
        corruption_result: Result from detect_corruption()

    Returns:
        str: Severity level - "clean", "low", "medium", "high", or "empty"
    """
    if corruption_result["corruption_percentage"] == 100.0:
        return "empty"
    elif not corruption_result["is_corrupted"]:
        return "clean"
    elif corruption_result["corruption_percentage"] < 5.0:
        return "low"
    elif corruption_result["corruption_percentage"] < 20.0:
        return "medium"
    else:
        return "high"


async def scan_collection_for_corruption(
    bm,
    max_documents: int = None,
    collect_all_corrupted: bool = False,
    document_corruption_threshold: float = 66.0,
) -> dict:
    """Scan ChromaDB collection for corruption and generate diagnostic report.

    Args:
        bm: Initialized buttermilk instance
        max_documents: Maximum number of documents to scan (None = all)
        collect_all_corrupted: If True, collect ALL corrupted documents (not just 10 samples)
        document_corruption_threshold: Corruption percentage threshold for document-level detection (default: 66.0)

    Returns:
        dict: Diagnostic report with corruption statistics and samples/all corrupted docs
    """
    # Get collection
    storage_config = bm.cfg.get_storage_config("zotero_vectors")
    search_tool = ChromaDBSearchTool(
        type="chromadb",
        collection_name=storage_config.collection_name,
        persist_directory=storage_config.persist_directory,
        embedding_model=storage_config.embedding_model,
        dimensionality=storage_config.dimensionality,
    )
    await search_tool.ensure_cache_initialized()
    collection = search_tool.collection

    # Determine scan range
    total_in_collection = collection.count()
    scan_limit = (
        min(max_documents, total_in_collection)
        if max_documents
        else total_in_collection
    )

    # Dictionary to group chunks by document_id
    documents = {}

    # Scan collection in batches to avoid memory issues
    batch_size = 100
    for offset in range(0, scan_limit, batch_size):
        batch_limit = min(batch_size, scan_limit - offset)

        # Get batch of documents
        results = collection.get(
            limit=batch_limit, offset=offset, include=["documents", "metadatas"]
        )

        # Group chunks by document_id
        for chunk_id, doc, metadata in zip(
            results["ids"], results["documents"], results["metadatas"]
        ):
            document_id = metadata.get("document_id", "unknown")
            if document_id not in documents:
                documents[document_id] = {"chunks": [], "chunk_ids": []}
            documents[document_id]["chunks"].append(doc)
            documents[document_id]["chunk_ids"].append(chunk_id)

    # Analyze each document
    corrupted_count = 0
    sample_corrupted = []
    severity_counts = {"clean": 0, "low": 0, "medium": 0, "high": 0, "empty": 0}

    for document_id, doc_data in documents.items():
        chunks = doc_data["chunks"]
        doc_data["chunk_ids"]

        # Analyze document-level corruption
        result = is_document_corrupt(chunks, threshold=document_corruption_threshold)

        # Classify severity based on document-level corruption rate
        corruption_pct = result["corruption_rate"]
        if corruption_pct == 100.0:
            severity = "empty"
        elif not result["is_corrupt"]:
            severity = "clean"
        elif corruption_pct < 75.0:
            severity = "low"
        elif corruption_pct < 90.0:
            severity = "medium"
        else:
            severity = "high"

        severity_counts[severity] += 1

        if result["is_corrupt"]:
            corrupted_count += 1

            # Collect corrupted documents
            # If collect_all_corrupted is True, collect ALL; otherwise limit to 10
            if collect_all_corrupted or len(sample_corrupted) < 10:
                sample_corrupted.append(
                    {
                        "document_id": document_id,
                        "corruption_rate": result["corruption_rate"],
                        "corrupted_chunks": result["corrupted_chunks"],
                        "total_chunks": result["total_chunks"],
                        "severity": severity,
                    }
                )

    # Calculate statistics
    total_documents = len(documents)
    corruption_rate = (
        (corrupted_count / total_documents * 100) if total_documents > 0 else 0.0
    )

    return {
        "total_scanned": total_documents,
        "total_corrupted": corrupted_count,
        "corruption_rate": corruption_rate,
        "severity_breakdown": severity_counts,
        "sample_corrupted": sample_corrupted,
    }


async def get_collection_stats(bm):
    """Get basic statistics about the ChromaDB collection.

    Args:
        bm: Initialized buttermilk instance with zotero config

    Returns:
        dict: Collection statistics including total_documents and collection_name
    """
    # Get ChromaDB storage config
    storage_config = bm.cfg.get_storage_config("zotero_vectors")
    if storage_config is None:
        raise ValueError("zotero_vectors storage config not found in configuration")

    # Create search tool to access collection
    search_tool = ChromaDBSearchTool(
        type="chromadb",
        collection_name=storage_config.collection_name,
        persist_directory=storage_config.persist_directory,
        embedding_model=storage_config.embedding_model,
        dimensionality=storage_config.dimensionality,
    )

    await search_tool.ensure_cache_initialized()
    collection = search_tool.collection

    # Get collection count
    total_documents = collection.count()

    return {
        "total_documents": total_documents,
        "collection_name": storage_config.collection_name,
    }


def write_json_output(output_file: str, report: dict):
    """Write corruption report to JSON file.

    Args:
        output_file: Path to output JSON file
        report: Diagnostic report from scan_collection_for_corruption()
    """
    output_data = {
        "summary": {
            "total_scanned": report["total_scanned"],
            "total_corrupted": report["total_corrupted"],
            "corruption_rate": report["corruption_rate"],
            "severity_breakdown": report["severity_breakdown"],
        },
        "corrupted_documents": report["sample_corrupted"],
    }

    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)


@click.command()
@click.option(
    "--verbose",
    is_flag=True,
    help="Show verbose output including sample corrupted entries",
)
@click.option(
    "--output",
    type=click.Path(),
    help="Path to output JSON file with detailed corruption report",
)
@click.option(
    "--limit",
    type=int,
    default=1000,
    help="Number of documents to scan (0 = scan all documents, default: 1000)",
)
def main(verbose: bool, output: str, limit: int):
    """Scan ChromaDB collection for corrupted text entries.

    This tool identifies documents with PDF encoding artifacts like (cid:XX)
    patterns that indicate poor OCR quality or corrupted text extraction.

    The diagnostic report includes:
    - Total number of documents scanned
    - Percentage of documents with corruption
    - Severity breakdown (missing text, partial corruption, heavy corruption)
    - Sample corrupted entries (with --verbose flag)
    - JSON output with all corrupted documents (with --output flag)
    """
    # Convert limit=0 to None (scan all documents)
    max_documents = None if limit == 0 else limit
    asyncio.run(
        diagnose_collection(
            verbose=verbose, output_file=output, max_documents=max_documents
        )
    )


async def diagnose_collection(
    verbose: bool = False, output_file: str = None, max_documents: int = 1000
):
    """Run diagnostic scan on ChromaDB collection.

    Args:
        verbose: Show verbose output including sample corrupted entries
        output_file: Path to output JSON file with detailed corruption report
        max_documents: Maximum number of documents to scan (0 or None = scan all)
    """
    # Convert max_documents=0 to None (scan all documents)
    scan_limit = None if max_documents == 0 else max_documents

    click.echo("ChromaDB Corruption Diagnostic Tool")
    click.echo("=" * 80)

    # Initialize buttermilk with zotero config
    conf_dir = str(Path(__file__).parent.parent / "conf")
    bm = await init_async(
        config_dir=conf_dir, config_name="zotero", overrides=["db=dev"]
    )

    try:
        # Get collection statistics
        stats = await get_collection_stats(bm)
        click.echo(f"\n📊 Collection: {stats['collection_name']}")
        click.echo(f"   Total documents: {stats['total_documents']:,}")

        # Scan collection for corruption
        # If output file specified, collect ALL corrupted documents
        click.echo("\n🔍 Scanning for corruption patterns...")
        collect_all = output_file is not None
        report = await scan_collection_for_corruption(
            bm, max_documents=scan_limit, collect_all_corrupted=collect_all
        )

        # Display results
        click.echo("\n✅ Scan complete")
        click.echo(f"   Documents scanned: {report['total_scanned']:,}")
        click.echo(f"   Corrupted documents: {report['total_corrupted']:,}")
        click.echo(f"   Corruption rate: {report['corruption_rate']:.2f}%")

        # Display severity breakdown
        click.echo("\n📈 Severity Breakdown:")
        severity = report["severity_breakdown"]
        click.echo(
            f"   Clean:  {severity['clean']:,} ({severity['clean'] / report['total_scanned'] * 100:.1f}%)"
        )
        click.echo(
            f"   Low:    {severity['low']:,} ({severity['low'] / report['total_scanned'] * 100:.1f}%)"
        )
        click.echo(
            f"   Medium: {severity['medium']:,} ({severity['medium'] / report['total_scanned'] * 100:.1f}%)"
        )
        click.echo(
            f"   High:   {severity['high']:,} ({severity['high'] / report['total_scanned'] * 100:.1f}%)"
        )
        click.echo(
            f"   Empty:  {severity['empty']:,} ({severity['empty'] / report['total_scanned'] * 100:.1f}%)"
        )

        # Write JSON output if requested
        if output_file:
            write_json_output(output_file, report)
            click.echo(f"\n💾 Report saved to: {output_file}")

        # Display sample corrupted entries if verbose
        if verbose and report["sample_corrupted"]:
            click.echo("\n🔎 Sample Corrupted Entries:")
            for i, sample in enumerate(report["sample_corrupted"][:5], 1):
                click.echo(f"\n   {i}. Document ID: {sample['document_id']}")
                click.echo(f"      Severity: {sample['severity']}")
                click.echo(f"      Corruption: {sample['corruption_percentage']:.1f}%")
                click.echo(f"      CID count: {sample['cid_count']}")
                click.echo(f"      Preview: {sample['text_preview'][:100]}...")

        click.echo("\n" + "=" * 80)
        return report

    finally:
        await bm.graceful_shutdown()


if __name__ == "__main__":
    main()
