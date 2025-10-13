#!/usr/bin/env python3
"""CLI tool to lookup Zotero items by ID and display metadata with child items."""

import asyncio
import json
import sys
from pathlib import Path

import click

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from buttermilk import init_async, logger
from buttermilk.libs.zotero import ZoteroSource


def pretty_print_json(data: dict, indent: int = 0) -> None:
    """Pretty print a dictionary with proper indentation."""
    indent_str = "  " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            click.echo(f"{indent_str}{click.style(key, fg='cyan')}:")
            pretty_print_json(value, indent + 1)
        elif isinstance(value, list):
            click.echo(f"{indent_str}{click.style(key, fg='cyan')}: [{len(value)} items]")
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    click.echo(f"{indent_str}  [{i}]:")
                    pretty_print_json(item, indent + 2)
                else:
                    click.echo(f"{indent_str}  [{i}] {item}")
        else:
            # Truncate long strings
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:100] + "..."
            click.echo(f"{indent_str}{click.style(key, fg='cyan')}: {value_str}")


async def lookup_item(item_key: str, show_content: bool = False):
    """Look up a Zotero item by key and display all metadata.

    Args:
        item_key: Zotero item key to look up
        show_content: Whether to show content preview from ChromaDB
    """
    # Initialize buttermilk with vectorize config (which has the pipeline source config)
    conf_dir = str(Path(__file__).parent.parent / "conf")
    bm = await init_async(config_dir=conf_dir, config_name="vectorize")

    # Get library_id from the pipeline source config
    # The config uses ${oc.env:ZOTERO_LIBRARY_ID} which gets resolved by OmegaConf
    library_id = bm.cfg.pipeline.source.library_id

    if not library_id:
        click.echo(
            f"\n{click.style('❌ Error:', fg='red', bold=True)} library_id not found in config\n",
            err=True,
        )
        sys.exit(1)

    # Use buttermilk's ZoteroSource to get a properly configured Zotero client
    # This ensures we're using buttermilk's credential management
    zotero_source = ZoteroSource(
        library_id=library_id,
        save_dir=str(Path.home() / ".cache" / "buttermilk" / "zotero" / "state"),
    )
    zot = zotero_source.zot

    try:
        # Fetch the item from Zotero API
        click.echo(f"\n{click.style('📚 Fetching item from Zotero API...', fg='blue', bold=True)}\n")
        item = zot.item(item_key)

        # Display item metadata
        click.echo(f"{click.style('Main Item:', fg='green', bold=True)}")
        click.echo(f"{'='*80}\n")

        # Display data section
        if item.get("data"):
            click.echo(f"{click.style('Data:', fg='yellow', bold=True)}")
            pretty_print_json(item["data"], indent=1)
            click.echo()

        # Display links section
        if item.get("links"):
            click.echo(f"{click.style('Links:', fg='yellow', bold=True)}")
            pretty_print_json(item["links"], indent=1)
            click.echo()

        # Display library info
        if item.get("library"):
            click.echo(f"{click.style('Library:', fg='yellow', bold=True)}")
            pretty_print_json(item["library"], indent=1)
            click.echo()

        # Display version
        if "version" in item:
            click.echo(f"{click.style('Version:', fg='yellow')} {item['version']}\n")

        # Fetch child items (attachments, notes)
        click.echo(f"\n{click.style('📎 Fetching child items...', fg='blue', bold=True)}\n")
        children = zot.children(item_key)

        if children:
            click.echo(f"{click.style(f'Found {len(children)} child items:', fg='green', bold=True)}")
            click.echo(f"{'='*80}\n")

            for idx, child in enumerate(children, 1):
                child_type = child.get("data", {}).get("itemType", "unknown")
                child_title = child.get("data", {}).get("title", "Untitled")

                click.echo(f"{click.style(f'{idx}. {child_title}', fg='magenta', bold=True)} ({child_type})")
                click.echo(f"{'-'*80}\n")

                # Display child data
                if child.get("data"):
                    click.echo(f"{click.style('Data:', fg='yellow', bold=True)}")
                    pretty_print_json(child["data"], indent=1)
                    click.echo()

                # Display child links
                if child.get("links"):
                    click.echo(f"{click.style('Links:', fg='yellow', bold=True)}")
                    pretty_print_json(child["links"], indent=1)
                    click.echo()

                click.echo()
        else:
            click.echo(f"{click.style('No child items found', fg='yellow')}\n")

        # Optionally show content from ChromaDB
        if show_content:
            click.echo(f"\n{click.style('📄 Checking ChromaDB for content...', fg='blue', bold=True)}\n")

            from buttermilk.tools import ChromaDBSearchTool

            storage_config = bm.cfg.storage.zotero_vectors
            search_tool = ChromaDBSearchTool(
                type="chromadb",
                collection_name=storage_config.collection_name,
                persist_directory=storage_config.persist_directory,
                embedding_model=storage_config.embedding_model,
                dimensionality=storage_config.dimensionality,
            )

            await search_tool.ensure_cache_initialized()
            collection = search_tool.collection

            # Query for the item
            results = collection.get(
                where={"item_key": {"$eq": item_key}}, include=["metadatas", "documents"]
            )

            if results["documents"]:
                click.echo(f"{click.style('Found in ChromaDB:', fg='green', bold=True)}")
                click.echo(f"Total chunks: {len(results['documents'])}\n")

                # Show first chunk metadata
                if results["metadatas"]:
                    click.echo(f"{click.style('ChromaDB Metadata (first chunk):', fg='yellow', bold=True)}")
                    pretty_print_json(results["metadatas"][0], indent=1)
                    click.echo()

                # Show first chunk content preview
                if results["documents"]:
                    content = results["documents"][0]
                    preview = content[:500] + "..." if len(content) > 500 else content
                    click.echo(f"{click.style('Content Preview:', fg='yellow', bold=True)}")
                    click.echo(f"  {preview}\n")
            else:
                click.echo(f"{click.style('Item not found in ChromaDB', fg='yellow')}\n")

    except Exception as e:
        click.echo(f"\n{click.style('❌ Error:', fg='red', bold=True)} {str(e)}\n", err=True)
        sys.exit(1)


@click.command()
@click.argument("item_key")
@click.option(
    "--content",
    is_flag=True,
    help="Show content preview from ChromaDB",
)
def main(item_key: str, content: bool):
    """Look up Zotero items by ID and display all metadata.

    Examples:

      \b
      # Look up an item with basic metadata
      lookup_item.py ABC123XYZ

      \b
      # Include content preview from ChromaDB
      lookup_item.py ABC123XYZ --content
    """
    asyncio.run(lookup_item(item_key, show_content=content))


if __name__ == "__main__":
    main()
