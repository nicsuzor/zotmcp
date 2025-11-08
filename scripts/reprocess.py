#!/usr/bin/env python3
"""Thin wrapper to reprocess specific Zotero items through the vectorization pipeline.

This script uses the reprocess.yaml config to force fresh processing of items
listed in a file, bypassing all caches and re-extracting from PDFs.

Usage:
    uv run python scripts/reprocess.py [items_file] [--db=dev]

Examples:
    # Reprocess corrupt documents (default file)
    uv run python scripts/reprocess.py

    # Reprocess custom list
    uv run python scripts/reprocess.py my_items.txt

    # Use dev database instead of upstream
    uv run python scripts/reprocess.py corrupt_docs.txt --db=dev

Note:
    - Always forces fresh processing (ignores caches)
    - Requires buttermilk bug fix for ZoteroDownloadProcessor to force PDF download
    - Until fix: items with Zotero fulltext will bypass PDF extraction
"""

import sys
from pathlib import Path

import click


@click.command()
@click.argument(
    "items_file",
    type=click.Path(exists=True),
    default="corrupt_documents_66pct.txt",
)
@click.option(
    "--db",
    type=click.Choice(["dev", "upstream", "deploy"]),
    default="upstream",
    help="Database configuration to use (default: upstream)",
)
def main(items_file: str, db: str):
    """Reprocess Zotero items through the full vectorization pipeline.

    ITEMS_FILE: Path to file containing document IDs (one per line)
    """
    from pathlib import Path
    import subprocess

    items_path = Path(items_file).resolve()
    project_root = Path(__file__).parent.parent

    click.echo(f"🔄 Reprocessing items from: {items_path}")
    click.echo(f"📊 Database: {db}")
    click.echo(f"⚠️  Cache disabled: Fresh processing enforced")
    click.echo()

    # Run buttermilk CLI with reprocess config
    cmd = [
        "uv",
        "run",
        "python",
        "-m",
        "buttermilk.runner.cli",
        "--config-dir",
        str(project_root / "conf"),
        "--config-name",
        "reprocess",
        f"db={db}",
        f"reprocess.items_file={items_path}",
    ]

    click.echo(f"Running: {' '.join(cmd)}")
    click.echo()

    try:
        result = subprocess.run(cmd, check=True, cwd=project_root)
        click.echo()
        click.echo("✅ Reprocessing completed successfully")
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        click.echo()
        click.echo(f"❌ Reprocessing failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        click.echo()
        click.echo("⚠️  Interrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
