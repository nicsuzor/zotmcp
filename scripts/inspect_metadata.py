#!/usr/bin/env python3
"""Inspect ChromaDB metadata to see actual field names."""

import asyncio
import json
import sys
from pathlib import Path

import click

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from buttermilk import init_async
from buttermilk.tools import ChromaDBSearchTool


async def inspect_metadata(query: str):
    """Search and inspect the actual metadata structure.

    Args:
        query: Search query
    """
    # Initialize buttermilk with vectorize config
    conf_dir = str(Path(__file__).parent.parent / "conf")
    bm = await init_async(config_dir=conf_dir, config_name="vectorize")

    # Get storage config
    storage_config = bm.cfg.get_storage_config("zotero_vectors")
    if storage_config is None:
        raise ValueError("zotero_vectors storage config not found")

    search_tool = ChromaDBSearchTool(
        type="chromadb",
        collection_name=storage_config.collection_name,
        persist_directory=storage_config.persist_directory,
        embedding_model=storage_config.embedding_model,
        dimensionality=storage_config.dimensionality,
    )

    await search_tool.initialize()

    # Perform search
    results = await search_tool.search(query=query, n_results=1)

    if results:
        click.echo(
            f"\n{click.style('First Result Metadata:', fg='green', bold=True)}\n"
        )
        metadata = results[0].metadata

        # Pretty print all metadata keys and values
        for key in sorted(metadata.keys()):
            value = metadata[key]
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            click.echo(f"{click.style(key, fg='cyan')}: {value}")

        click.echo(
            f"\n{click.style('Full metadata as JSON:', fg='yellow', bold=True)}\n"
        )
        click.echo(json.dumps(metadata, indent=2, default=str))
    else:
        click.echo("No results found")


@click.command()
@click.argument("query")
def main(query: str):
    """Inspect metadata structure for a search query.

    Example:
        inspect_metadata.py "klonick"
    """
    asyncio.run(inspect_metadata(query))


if __name__ == "__main__":
    main()
