#!/usr/bin/env python3
"""Remove corrupted documents from ChromaDB collection.

This script deletes all chunks associated with specific document IDs from
the ChromaDB collection. It reads document IDs from an input file and
provides both dry-run and execute modes for safety.

Usage:
    # Dry-run mode (default): Show what would be deleted
    python scripts/remove_corrupt_docs.py --input documents_to_remove_ids.txt

    # Execute mode: Actually delete documents
    python scripts/remove_corrupt_docs.py --input documents_to_remove_ids.txt --execute
"""

import asyncio
import sys
from pathlib import Path
from typing import List

import click

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from buttermilk import init_async, logger
from buttermilk.tools import ChromaDBSearchTool


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


async def get_chunk_count_for_document(collection, document_id: str) -> int:
    """Count how many chunks exist for a given document ID.

    Args:
        collection: ChromaDB collection instance
        document_id: Document ID to query

    Returns:
        int: Number of chunks found for this document
    """
    results = collection.get(
        where={"document_id": document_id},
        include=[]
    )

    return len(results["ids"])


async def delete_document_chunks(collection, document_id: str, dry_run: bool = True) -> int:
    """Delete all chunks for a given document ID.

    Args:
        collection: ChromaDB collection instance
        document_id: Document ID to delete
        dry_run: If True, only count chunks without deleting

    Returns:
        int: Number of chunks affected (counted or deleted)
    """
    # Count chunks first
    chunk_count = await get_chunk_count_for_document(collection, document_id)

    if chunk_count == 0:
        return 0

    # If not dry run, actually delete
    if not dry_run:
        collection.delete(where={"document_id": document_id})
        logger.info(
            f"Deleted {chunk_count} chunks for document {document_id}",
            document_id=document_id,
            chunks_deleted=chunk_count
        )

    return chunk_count


async def remove_documents(
    document_ids: List[str],
    dry_run: bool = True
) -> dict:
    """Remove documents from ChromaDB collection.

    Args:
        document_ids: List of document IDs to remove
        dry_run: If True, only show what would be deleted without deleting

    Returns:
        dict: Statistics about the removal operation
    """
    # Initialize buttermilk with zotero config
    conf_dir = str(Path(__file__).parent.parent / "conf")
    bm = await init_async(config_dir=conf_dir, config_name="zotero", overrides=["db=dev"])

    try:
        # Get ChromaDB collection
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

        # Process each document
        total_chunks = 0
        documents_found = 0
        documents_missing = 0

        for doc_id in document_ids:
            chunk_count = await delete_document_chunks(collection, doc_id, dry_run=dry_run)

            if chunk_count > 0:
                documents_found += 1
                total_chunks += chunk_count
            else:
                documents_missing += 1

        return {
            "total_documents": len(document_ids),
            "documents_found": documents_found,
            "documents_missing": documents_missing,
            "total_chunks": total_chunks,
            "dry_run": dry_run,
        }

    finally:
        await bm.graceful_shutdown()


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
    help="Actually delete documents (default is dry-run mode)",
)
def main(input: str, execute: bool):
    """Remove corrupted documents from ChromaDB collection.

    By default, runs in DRY-RUN mode and only shows what would be deleted.
    Use --execute flag to actually perform deletions.

    Example:
        # See what would be deleted
        python scripts/remove_corrupt_docs.py --input documents_to_remove_ids.txt

        # Actually delete documents
        python scripts/remove_corrupt_docs.py --input documents_to_remove_ids.txt --execute
    """
    dry_run = not execute

    click.echo("Document Removal Tool")
    click.echo("=" * 80)

    if dry_run:
        click.echo("🔍 DRY-RUN MODE: No documents will be deleted")
    else:
        click.echo("⚠️  EXECUTE MODE: Documents will be permanently deleted")

    click.echo(f"Input file: {input}")
    click.echo()

    # Read document IDs
    click.echo(f"Reading document IDs from {input}...")
    document_ids = read_document_ids(input)
    click.echo(f"Found {len(document_ids)} document IDs to process")

    # Run removal
    click.echo("\nProcessing documents...")
    stats = asyncio.run(remove_documents(document_ids, dry_run=dry_run))

    # Display results
    click.echo("\n" + "=" * 80)
    click.echo("REMOVAL SUMMARY")
    click.echo("=" * 80)
    click.echo(f"Total documents in input: {stats['total_documents']}")
    click.echo(f"Documents found in DB: {stats['documents_found']}")
    click.echo(f"Documents not found in DB: {stats['documents_missing']}")
    click.echo(f"Total chunks affected: {stats['total_chunks']}")

    if dry_run:
        click.echo("\n✅ DRY-RUN COMPLETE: No changes made to database")
        click.echo("Run with --execute flag to actually delete documents")
    else:
        click.echo("\n✅ DELETION COMPLETE: Documents permanently removed")

    click.echo("=" * 80)


if __name__ == "__main__":
    main()
