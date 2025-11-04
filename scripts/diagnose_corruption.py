#!/usr/bin/env python3
"""Diagnostic tool to identify corrupted text entries in ChromaDB collection.

This script scans the ChromaDB collection for documents with PDF encoding
artifacts (e.g., (cid:XX) patterns) that indicate failed OCR or corrupted text.
"""

import asyncio
import json
import re
import sys
from pathlib import Path

import click

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from buttermilk import init_async, logger
from buttermilk.tools import ChromaDBSearchTool

# Pattern to detect PDF encoding artifacts like (cid:XX)
CID_PATTERN = re.compile(r'\(cid:\d+\)')


def detect_corruption(text: str) -> dict:
    """Detect corruption patterns in text content.

    Args:
        text: Text content to analyze

    Returns:
        dict: Corruption analysis with keys:
            - is_corrupted: bool indicating if text has corruption
            - corruption_percentage: float from 0-100
            - cid_count: int count of (cid:XX) patterns found
    """
    if not text or len(text.strip()) == 0:
        # Empty text is considered completely corrupted
        return {
            "is_corrupted": True,
            "corruption_percentage": 100.0,
            "cid_count": 0,
        }

    # Find all (cid:XX) patterns
    cid_matches = CID_PATTERN.findall(text)
    cid_count = len(cid_matches)

    # Calculate corruption percentage based on:
    # - Ratio of cid patterns to text length
    # - Presence of any cid patterns indicates corruption
    total_chars = len(text)
    cid_chars = sum(len(match) for match in cid_matches)
    corruption_percentage = (cid_chars / total_chars * 100) if total_chars > 0 else 0.0

    is_corrupted = cid_count > 0

    return {
        "is_corrupted": is_corrupted,
        "corruption_percentage": corruption_percentage,
        "cid_count": cid_count,
    }


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


async def scan_collection_for_corruption(bm, max_documents: int = None, collect_all_corrupted: bool = False) -> dict:
    """Scan ChromaDB collection for corruption and generate diagnostic report.

    Args:
        bm: Initialized buttermilk instance
        max_documents: Maximum number of documents to scan (None = all)
        collect_all_corrupted: If True, collect ALL corrupted documents (not just 10 samples)

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
    scan_limit = min(max_documents, total_in_collection) if max_documents else total_in_collection

    # Initialize counters
    severity_counts = {"clean": 0, "low": 0, "medium": 0, "high": 0, "empty": 0}
    corrupted_count = 0
    sample_corrupted = []

    # Scan collection in batches to avoid memory issues
    batch_size = 100
    for offset in range(0, scan_limit, batch_size):
        batch_limit = min(batch_size, scan_limit - offset)

        # Get batch of documents
        results = collection.get(
            limit=batch_limit,
            offset=offset,
            include=["documents", "metadatas"]
        )

        # Analyze each document
        for doc, metadata in zip(results["documents"], results["metadatas"]):
            corruption = detect_corruption(doc)
            severity = classify_severity(corruption)

            severity_counts[severity] += 1

            if corruption["is_corrupted"]:
                corrupted_count += 1

                # Collect corrupted entries
                # If collect_all_corrupted is True, collect ALL; otherwise limit to 10
                if collect_all_corrupted or len(sample_corrupted) < 10:
                    item_key = metadata.get("item_key", "unknown")
                    sample_corrupted.append({
                        "item_key": item_key,
                        "severity": severity,
                        "corruption_percentage": corruption["corruption_percentage"],
                        "cid_count": corruption["cid_count"],
                        "text_preview": doc[:200] if doc else "(empty)"
                    })

    # Calculate statistics
    corruption_rate = (corrupted_count / scan_limit * 100) if scan_limit > 0 else 0.0

    return {
        "total_scanned": scan_limit,
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

    with open(output_file, 'w') as f:
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
def main(verbose: bool, output: str):
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
    asyncio.run(diagnose_collection(verbose=verbose, output_file=output))


async def diagnose_collection(verbose: bool = False, output_file: str = None):
    """Run diagnostic scan on ChromaDB collection.

    Args:
        verbose: Show verbose output including sample corrupted entries
        output_file: Path to output JSON file with detailed corruption report
    """
    click.echo("ChromaDB Corruption Diagnostic Tool")
    click.echo("=" * 80)

    # Initialize buttermilk with zotero config
    conf_dir = str(Path(__file__).parent.parent / "conf")
    bm = await init_async(config_dir=conf_dir, config_name="zotero", overrides=["db=dev"])

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
            bm,
            max_documents=1000,
            collect_all_corrupted=collect_all
        )

        # Display results
        click.echo(f"\n✅ Scan complete")
        click.echo(f"   Documents scanned: {report['total_scanned']:,}")
        click.echo(f"   Corrupted documents: {report['total_corrupted']:,}")
        click.echo(f"   Corruption rate: {report['corruption_rate']:.2f}%")

        # Display severity breakdown
        click.echo("\n📈 Severity Breakdown:")
        severity = report['severity_breakdown']
        click.echo(f"   Clean:  {severity['clean']:,} ({severity['clean']/report['total_scanned']*100:.1f}%)")
        click.echo(f"   Low:    {severity['low']:,} ({severity['low']/report['total_scanned']*100:.1f}%)")
        click.echo(f"   Medium: {severity['medium']:,} ({severity['medium']/report['total_scanned']*100:.1f}%)")
        click.echo(f"   High:   {severity['high']:,} ({severity['high']/report['total_scanned']*100:.1f}%)")
        click.echo(f"   Empty:  {severity['empty']:,} ({severity['empty']/report['total_scanned']*100:.1f}%)")

        # Write JSON output if requested
        if output_file:
            write_json_output(output_file, report)
            click.echo(f"\n💾 Report saved to: {output_file}")

        # Display sample corrupted entries if verbose
        if verbose and report['sample_corrupted']:
            click.echo("\n🔎 Sample Corrupted Entries:")
            for i, sample in enumerate(report['sample_corrupted'][:5], 1):
                click.echo(f"\n   {i}. Item: {sample['item_key']}")
                click.echo(f"      Severity: {sample['severity']}")
                click.echo(f"      Corruption: {sample['corruption_percentage']:.1f}%")
                click.echo(f"      CID count: {sample['cid_count']}")
                click.echo(f"      Preview: {sample['text_preview'][:100]}...")

        click.echo("\n" + "=" * 80)
        return 0

    finally:
        await bm.graceful_shutdown()


if __name__ == "__main__":
    main()
