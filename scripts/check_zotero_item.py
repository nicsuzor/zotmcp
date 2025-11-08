#!/usr/bin/env python3
"""Check if Zotero items exist and display their metadata.

This script checks whether given item IDs (keys) exist in the Zotero library
and displays their type, title, and attachment information.

Uses buttermilk infrastructure:
- Loads library_id from ZOTERO_LIBRARY_ID environment variable (via buttermilk config)
- Gets ZOTERO_API_KEY from buttermilk credentials system
- Initializes buttermilk with zotero config for proper credential management

Usage:
    # Check single item
    uv run python scripts/check_zotero_item.py ITEM_KEY

    # Check multiple items
    uv run python scripts/check_zotero_item.py ITEM1 ITEM2 ITEM3

    # Check items from file (one per line)
    uv run python scripts/check_zotero_item.py --input documents_to_remove_ids.txt
"""

import asyncio
import os
import sys
from pathlib import Path

import click
from pyzotero import zotero
from pyzotero.zotero_errors import ResourceNotFoundError

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from buttermilk import init_async


async def get_zotero_client_from_buttermilk() -> tuple[zotero.Zotero, str]:
    """Initialize Zotero client using buttermilk infrastructure.

    This function:
    1. Initializes buttermilk with zotero config
    2. Loads library_id from ZOTERO_LIBRARY_ID environment variable
    3. Gets ZOTERO_API_KEY from buttermilk credentials system
    4. Creates Zotero client with these credentials

    Returns:
        tuple: (Zotero client, library_id)

    Raises:
        ValueError: If ZOTERO_LIBRARY_ID not set or ZOTERO_API_KEY not available
    """
    # Initialize buttermilk with zotero config
    conf_dir = str(Path(__file__).parent.parent / "conf")
    bm = await init_async(
        config_dir=conf_dir, config_name="zotero", overrides=["db=dev"]
    )

    # Get library_id from environment (same pattern as vectorize.yaml)
    library_id = os.environ.get("ZOTERO_LIBRARY_ID")
    if not library_id:
        raise ValueError("ZOTERO_LIBRARY_ID environment variable not set")

    # Get API key from buttermilk credentials
    api_key = bm.credentials.get("ZOTERO_API_KEY")
    if not api_key:
        raise ValueError("ZOTERO_API_KEY not available in buttermilk credentials")

    # Create Zotero client
    zot = zotero.Zotero(library_id=library_id, library_type="group", api_key=api_key)

    return zot, library_id


def check_item(zot: zotero.Zotero, item_id: str) -> dict:
    """Check if item exists in Zotero and get its metadata.

    Args:
        zot: Zotero client instance
        item_id: Zotero item key to check

    Returns:
        dict with keys:
            - exists: bool
            - item_type: str (if exists)
            - title: str (if exists)
            - has_pdf: bool (if exists)
            - attachment_key: str or None (if has PDF)
            - error: str (if not exists)
    """
    try:
        item = zot.item(item_id)
        data = item.get("data", {})
        links = item.get("links", {})

        # Check for PDF attachment
        attachment = links.get("attachment", {})
        has_pdf = attachment.get("attachmentType") == "application/pdf"
        attachment_key = None
        if has_pdf and (href := attachment.get("href")):
            attachment_key = href.split("/")[-1]

        return {
            "exists": True,
            "item_type": data.get("itemType", "unknown"),
            "title": data.get("title", "NO TITLE"),
            "has_pdf": has_pdf,
            "attachment_key": attachment_key,
        }
    except ResourceNotFoundError:
        return {
            "exists": False,
            "error": "Item does not exist in Zotero (404)",
        }
    except Exception as e:
        return {
            "exists": False,
            "error": f"Error: {type(e).__name__}: {str(e)[:100]}",
        }


def read_item_ids_from_file(input_file: str) -> list[str]:
    """Read item IDs from input file (one per line).

    Args:
        input_file: Path to text file containing item IDs

    Returns:
        List of item ID strings (whitespace stripped, empty lines removed)
    """
    with open(input_file, "r") as f:
        lines = f.readlines()

    # Strip whitespace and filter out empty lines
    item_ids = [line.strip() for line in lines if line.strip()]

    return item_ids


@click.command()
@click.argument("item_ids", nargs=-1)
@click.option(
    "--input",
    type=click.Path(exists=True),
    help="Path to input file with item IDs (one per line)",
)
def main(item_ids: tuple[str], input: str):
    """Check if Zotero items exist and display their metadata.

    Uses buttermilk infrastructure to load credentials and library configuration.

    Provide item IDs as arguments or use --input to read from a file.

    Examples:
        # Check single item
        uv run python scripts/check_zotero_item.py UFEQ4F94

        # Check multiple items
        uv run python scripts/check_zotero_item.py ITEM1 ITEM2 ITEM3

        # Check items from file
        uv run python scripts/check_zotero_item.py --input documents_to_remove_ids.txt
    """
    asyncio.run(check_items_async(item_ids, input))


async def check_items_async(item_ids: tuple[str], input_file: str):
    """Async implementation of item checking workflow.

    Args:
        item_ids: Tuple of item IDs from command line arguments
        input_file: Path to input file with item IDs (optional)
    """
    # Collect item IDs from arguments and/or file
    all_item_ids = list(item_ids)

    if input_file:
        file_item_ids = read_item_ids_from_file(input_file)
        all_item_ids.extend(file_item_ids)

    if not all_item_ids:
        click.echo("Error: No item IDs provided. Use arguments or --input flag.")
        click.echo("Run with --help for usage information.")
        sys.exit(1)

    click.echo("Zotero Item Checker")
    click.echo("=" * 80)
    click.echo("Using buttermilk infrastructure for credentials and config")
    click.echo()

    # Initialize Zotero client using buttermilk
    try:
        zot, library_id = await get_zotero_client_from_buttermilk()
        click.echo(f"Library ID: {library_id} (from ZOTERO_LIBRARY_ID env var)")
        click.echo(f"Items to check: {len(all_item_ids)}")
        click.echo()
    except ValueError as e:
        click.echo(f"Error: {e}")
        sys.exit(1)

    # Check each item
    results = {}
    for item_id in all_item_ids:
        click.echo(f"Checking {item_id}...", nl=False)
        result = check_item(zot, item_id)
        results[item_id] = result

        if result["exists"]:
            click.echo(" ✅ EXISTS")
        else:
            click.echo(" ❌ NOT FOUND")

    # Display detailed results
    click.echo()
    click.echo("=" * 80)
    click.echo("DETAILED RESULTS")
    click.echo("=" * 80)

    exists_count = 0
    not_found_count = 0

    for item_id, result in results.items():
        if result["exists"]:
            exists_count += 1
            click.echo(f"\n✅ {item_id}")
            click.echo(f"   Type: {result['item_type']}")
            click.echo(f"   Title: {result['title'][:70]}")
            click.echo(f"   Has PDF: {'Yes' if result['has_pdf'] else 'No'}")
            if result.get("attachment_key"):
                click.echo(f"   Attachment Key: {result['attachment_key']}")
        else:
            not_found_count += 1
            click.echo(f"\n❌ {item_id}")
            click.echo(f"   {result['error']}")

    # Summary
    click.echo()
    click.echo("=" * 80)
    click.echo("SUMMARY")
    click.echo("=" * 80)
    click.echo(f"Total items checked: {len(all_item_ids)}")
    click.echo(f"Items found: {exists_count}")
    click.echo(f"Items not found: {not_found_count}")
    click.echo("=" * 80)


if __name__ == "__main__":
    main()
