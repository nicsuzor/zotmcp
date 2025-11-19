#!/usr/bin/env python3
"""Check ChromaDB metadata population and structure."""

import json
import sys
from pathlib import Path

import chromadb
import click

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def check_metadata():
    """Check metadata population in ChromaDB."""

    # Connect to ChromaDB
    persist_dir = (
        Path.home()
        / ".cache/buttermilk/chromadb/gs_prosocial-dev_data_zotero-prosocial-fulltext_files"
    )

    if not persist_dir.exists():
        click.echo(f"❌ ChromaDB directory not found: {persist_dir}", err=True)
        return

    client = chromadb.PersistentClient(path=str(persist_dir))
    collection = client.get_collection("prosocial_zot")

    # Get 10 random items
    results = collection.get(limit=10, include=["metadatas", "documents"])

    click.echo(
        f"\n{click.style('ChromaDB Metadata Diagnostics', fg='green', bold=True)}\n"
    )
    click.echo(f"Total items retrieved: {len(results['ids'])}")
    click.echo(f"Collection total count: {collection.count()}\n")

    # Analyze metadata keys across all items
    all_keys = set()
    for metadata in results["metadatas"]:
        all_keys.update(metadata.keys())

    click.echo(f"{click.style('Available Metadata Fields:', fg='cyan', bold=True)}")
    for key in sorted(all_keys):
        click.echo(f"  • {key}")

    # Check for specific fields we're interested in
    click.echo(
        f"\n{click.style('Field Population Analysis:', fg='yellow', bold=True)}\n"
    )

    # Check zotero_data field
    zotero_data_populated = 0
    sample_zotero = None

    for metadata in results["metadatas"]:
        if "zotero_data" in metadata and metadata["zotero_data"]:
            zotero_data_populated += 1
            if sample_zotero is None:
                sample_zotero = metadata["zotero_data"]

    click.echo("zotero_data field:")
    click.echo(
        f"  Populated: {zotero_data_populated}/{len(results['metadatas'])} items"
    )

    if sample_zotero:
        # Parse the JSON to show structure
        try:
            zot_json = json.loads(sample_zotero)
            click.echo("\n  Sample zotero_data structure:")
            click.echo(f"    • itemType: {zot_json.get('itemType', 'N/A')}")
            click.echo(f"    • title: {zot_json.get('title', 'N/A')[:80]}...")
            click.echo(f"    • creators: {len(zot_json.get('creators', []))} authors")
            if zot_json.get("creators"):
                first_author = zot_json["creators"][0]
                click.echo(
                    f"      - First: {first_author.get('firstName', '')} {first_author.get('lastName', '')}"
                )
            click.echo(f"    • date: {zot_json.get('date', 'N/A')}")
            click.echo(f"    • DOI: {zot_json.get('DOI', 'N/A')}")
            click.echo(f"    • tags: {len(zot_json.get('tags', []))} tags")
        except json.JSONDecodeError:
            click.echo("    ⚠️  Could not parse zotero_data JSON")

    # Check other key fields
    click.echo(f"\n{click.style('Other Key Fields:', fg='magenta', bold=True)}\n")

    for field in ["title", "citation", "doi_or_url", "document_id", "itemType"]:
        populated = sum(1 for m in results["metadatas"] if field in m and m[field])
        click.echo(f"{field}:")
        click.echo(f"  Populated: {populated}/{len(results['metadatas'])} items")

        # Show sample value
        for metadata in results["metadatas"]:
            if field in metadata and metadata[field]:
                sample = str(metadata[field])[:100]
                if len(str(metadata[field])) > 100:
                    sample += "..."
                click.echo(f"  Sample: {sample}")
                break

    # Full sample record
    click.echo(f"\n{click.style('Full Sample Record:', fg='blue', bold=True)}\n")
    if results["metadatas"]:
        click.echo(json.dumps(results["metadatas"][0], indent=2, default=str))


@click.command()
def main():
    """Check ChromaDB metadata population."""
    check_metadata()


if __name__ == "__main__":
    main()
