#!/usr/bin/env python3
"""Fetch PDF file from Zotero storage for a document."""

import asyncio
import os
import sys
from pathlib import Path

from pyzotero import zotero

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from buttermilk import init_async


async def fetch_pdf(item_key: str, output_dir: str = "tests/data"):
    """Fetch PDF for an item and save to test data directory."""
    # Initialize buttermilk with zotero config
    conf_dir = str(Path(__file__).parent / "conf")
    bm = await init_async(
        config_dir=conf_dir, config_name="zotero", overrides=["db=dev"]
    )

    try:
        # Get library_id and API key from environment
        library_id = os.environ.get("ZOTERO_LIBRARY_ID")
        api_key = os.environ.get("ZOTERO_API_KEY")

        if not library_id or not api_key:
            print("❌ ZOTERO_LIBRARY_ID and ZOTERO_API_KEY must be set")
            return

        # Create Zotero client
        zot = zotero.Zotero(library_id, "group", api_key)

        # Get item
        item = zot.item(item_key)
        print(f"📄 Item: {item.get('data', {}).get('title', 'Unknown')[:80]}")

        # Get children (attachments)
        children = zot.children(item_key)

        # Find PDF attachment
        pdf_items = [
            c
            for c in children
            if c.get("data", {}).get("contentType") == "application/pdf"
        ]

        if not pdf_items:
            print(f"❌ No PDF attachments found for {item_key}")
            return

        pdf_item = pdf_items[0]
        attachment_key = pdf_item["key"]
        print(
            f"📎 PDF attachment: {pdf_item.get('data', {}).get('filename', 'unknown')}"
        )

        # Download PDF using pyzotero (returns bytes)
        pdf_bytes = zot.file(attachment_key)

        if not pdf_bytes:
            print("❌ PDF file download failed")
            return

        # Save to test data directory
        output_path = Path(output_dir) / f"{item_key}.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_bytes)

        print(f"✅ Copied PDF to: {output_path}")
        print(f"   Size: {output_path.stat().st_size / 1024:.1f} KB")

        return output_path

    finally:
        await bm.graceful_shutdown()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_pdf.py <item_key>")
        sys.exit(1)

    item_key = sys.argv[1]
    asyncio.run(fetch_pdf(item_key))
