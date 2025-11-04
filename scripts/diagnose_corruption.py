#!/usr/bin/env python3
"""Diagnostic tool to identify corrupted text entries in ChromaDB collection.

This script scans the ChromaDB collection for documents with PDF encoding
artifacts (e.g., (cid:XX) patterns) that indicate failed OCR or corrupted text.
"""

import asyncio
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


@click.command()
@click.option(
    "--verbose",
    is_flag=True,
    help="Show verbose output including sample corrupted entries",
)
def main(verbose: bool):
    """Scan ChromaDB collection for corrupted text entries.

    This tool identifies documents with PDF encoding artifacts like (cid:XX)
    patterns that indicate poor OCR quality or corrupted text extraction.

    The diagnostic report includes:
    - Total number of documents scanned
    - Percentage of documents with corruption
    - Severity breakdown (missing text, partial corruption, heavy corruption)
    - Sample corrupted entries (with --verbose flag)
    """
    asyncio.run(diagnose_collection(verbose=verbose))


async def diagnose_collection(verbose: bool = False):
    """Run diagnostic scan on ChromaDB collection."""
    click.echo("ChromaDB corruption diagnostic tool")
    click.echo("=" * 80)

    # TODO: Implement collection scanning
    click.echo("\nDiagnostic scan not yet implemented")
    return 0


if __name__ == "__main__":
    main()
