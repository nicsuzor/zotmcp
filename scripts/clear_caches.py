#!/usr/bin/env python3
"""Clear cached files for specific document IDs.

This script clears cached files associated with specific document IDs across
three cache locations:
- PDFs: ~/.cache/buttermilk/zotero/<ID>.pdf
- Embeddings: ~/.cache/buttermilk/embeddings/<ID>_embeddings.json
- Records: ~/.cache/buttermilk/records/zotero_vectorization/*/<ID>.json

Usage:
    # Dry-run mode (default): Show what would be deleted
    python scripts/clear_caches.py --input documents_to_remove_ids.txt

    # Execute mode: Actually delete cache files
    python scripts/clear_caches.py --input documents_to_remove_ids.txt --execute
"""

import sys
from pathlib import Path
from typing import List, Dict
import os

import click


def read_document_ids(input_file: str) -> List[str]:
    """Read document IDs from input file (one ID per line).

    Args:
        input_file: Path to text file containing document IDs

    Returns:
        List of document ID strings (whitespace stripped, empty lines removed)

    Raises:
        FileNotFoundError: If input file does not exist
    """
    with open(input_file, 'r') as f:
        lines = f.readlines()

    # Strip whitespace and filter out empty lines
    document_ids = [line.strip() for line in lines if line.strip()]

    return document_ids


def get_cache_paths_for_document(document_id: str) -> Dict[str, List[Path]]:
    """Get all cache file paths for a given document ID.

    Args:
        document_id: Document ID to find cache files for

    Returns:
        Dict with cache type as key and list of Path objects as values:
        - "pdf": List of PDF cache paths
        - "embeddings": List of embedding cache paths
        - "records": List of record cache paths
    """
    home = Path.home()
    cache_base = home / ".cache" / "buttermilk"

    paths = {
        "pdf": [],
        "embeddings": [],
        "records": [],
    }

    # 1. PDF cache: ~/.cache/buttermilk/zotero/<ID>.pdf
    pdf_path = cache_base / "zotero" / "items" / f"{document_id}.pdf"
    if pdf_path.exists():
        paths["pdf"].append(pdf_path)

    # 2. Embeddings cache: ~/.cache/buttermilk/embeddings/<ID>_embeddings.json
    embeddings_path = cache_base / "embeddings" / f"{document_id}_embeddings.json"
    if embeddings_path.exists():
        paths["embeddings"].append(embeddings_path)

    # 3. Records cache: ~/.cache/buttermilk/records/zotero_vectorization/*/<ID>.json
    records_base = cache_base / "records" / "zotero_vectorization"
    if records_base.exists():
        # Search all subdirectories for <ID>.json
        for record_file in records_base.rglob(f"{document_id}.json"):
            paths["records"].append(record_file)

    return paths


def clear_cache_file(file_path: Path, dry_run: bool = True) -> bool:
    """Delete a cache file.

    Args:
        file_path: Path to file to delete
        dry_run: If True, only report without deleting

    Returns:
        bool: True if file was/would be deleted, False if file doesn't exist
    """
    if not file_path.exists():
        return False

    if not dry_run:
        file_path.unlink()

    return True


def clear_caches(
    document_ids: List[str],
    dry_run: bool = True
) -> Dict[str, int]:
    """Clear cache files for specified document IDs.

    Args:
        document_ids: List of document IDs to clear caches for
        dry_run: If True, only show what would be deleted without deleting

    Returns:
        Dict with statistics:
        - total_documents: Number of document IDs processed
        - pdfs_cleared: Number of PDF files cleared
        - embeddings_cleared: Number of embedding files cleared
        - records_cleared: Number of record files cleared
        - total_files_cleared: Total number of files cleared
    """
    stats = {
        "total_documents": len(document_ids),
        "pdfs_cleared": 0,
        "embeddings_cleared": 0,
        "records_cleared": 0,
        "total_files_cleared": 0,
    }

    for doc_id in document_ids:
        cache_paths = get_cache_paths_for_document(doc_id)

        # Clear PDFs
        for pdf_path in cache_paths["pdf"]:
            if clear_cache_file(pdf_path, dry_run=dry_run):
                stats["pdfs_cleared"] += 1
                stats["total_files_cleared"] += 1

        # Clear embeddings
        for emb_path in cache_paths["embeddings"]:
            if clear_cache_file(emb_path, dry_run=dry_run):
                stats["embeddings_cleared"] += 1
                stats["total_files_cleared"] += 1

        # Clear records
        for rec_path in cache_paths["records"]:
            if clear_cache_file(rec_path, dry_run=dry_run):
                stats["records_cleared"] += 1
                stats["total_files_cleared"] += 1

    return stats


@click.command()
@click.option(
    "--input",
    type=click.Path(exists=True),
    default="documents_to_remove_ids.txt",
    help="Path to input file with document IDs (one per line)",
)
@click.option(
    "--execute",
    is_flag=True,
    default=False,
    help="Actually delete cache files (default is dry-run mode)",
)
def main(input: str, execute: bool):
    """Clear cached files for corrupted documents.

    By default, runs in DRY-RUN mode and only shows what would be deleted.
    Use --execute flag to actually perform deletions.

    This script clears:
    - PDF files from ~/.cache/buttermilk/zotero/items/
    - Embedding files from ~/.cache/buttermilk/embeddings/
    - Record files from ~/.cache/buttermilk/records/zotero_vectorization/

    Example:
        # See what would be deleted
        python scripts/clear_caches.py --input documents_to_remove_ids.txt

        # Actually delete cache files
        python scripts/clear_caches.py --input documents_to_remove_ids.txt --execute
    """
    dry_run = not execute

    click.echo("Cache Clearing Tool")
    click.echo("=" * 80)

    if dry_run:
        click.echo("🔍 DRY-RUN MODE: No files will be deleted")
    else:
        click.echo("⚠️  EXECUTE MODE: Cache files will be permanently deleted")

    click.echo(f"Input file: {input}")
    click.echo()

    # Read document IDs
    click.echo(f"Reading document IDs from {input}...")
    document_ids = read_document_ids(input)
    click.echo(f"Found {len(document_ids)} document IDs to process")

    # Clear caches
    click.echo("\nScanning cache directories...")
    stats = clear_caches(document_ids, dry_run=dry_run)

    # Display results
    click.echo("\n" + "=" * 80)
    click.echo("CACHE CLEARING SUMMARY")
    click.echo("=" * 80)
    click.echo(f"Total documents processed: {stats['total_documents']}")
    click.echo(f"\nCache files affected:")
    click.echo(f"  PDFs:       {stats['pdfs_cleared']}")
    click.echo(f"  Embeddings: {stats['embeddings_cleared']}")
    click.echo(f"  Records:    {stats['records_cleared']}")
    click.echo(f"  Total:      {stats['total_files_cleared']}")

    if dry_run:
        click.echo("\n✅ DRY-RUN COMPLETE: No files deleted")
        click.echo("Run with --execute flag to actually delete cache files")
    else:
        click.echo("\n✅ DELETION COMPLETE: Cache files permanently removed")

    click.echo("=" * 80)


if __name__ == "__main__":
    main()
