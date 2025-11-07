#!/usr/bin/env python3
"""Fetch all chunks for a document and save as test data."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from buttermilk import init_async
from buttermilk.tools import ChromaDBSearchTool


async def fetch_document(document_id: str, is_corrupt: bool, output_path: str):
    """Fetch all chunks for a document and save as test data."""
    # Initialize buttermilk
    conf_dir = "conf"
    bm = await init_async(
        config_dir=conf_dir, config_name="zotero", overrides=["db=dev"]
    )

    try:
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

        # Get all chunks for this document
        results = collection.get(
            where={"document_id": {"$eq": document_id}},
            include=["documents", "metadatas"],
        )

        if not results["documents"]:
            print(f"No chunks found for document {document_id}")
            return

        # Create test record
        test_record = {
            "id": document_id,
            "corrupt": is_corrupt,
            "chunks": results["documents"],
            "chunk_ids": results["ids"],
            "metadata": results["metadatas"][0] if results["metadatas"] else {},
        }

        # Save to file
        with open(output_path, "w") as f:
            json.dump(test_record, f, indent=2)

        print(f"✅ Saved {len(results['documents'])} chunks to {output_path}")
        print(f"   Document ID: {document_id}")
        print(f"   Marked as corrupt: {is_corrupt}")

    finally:
        await bm.graceful_shutdown()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_document.py <document_id> [corrupt=true|false]")
        sys.exit(1)

    document_id = sys.argv[1]
    is_corrupt = sys.argv[2].lower() == "true" if len(sys.argv) > 2 else True
    output_path = f"tests/data/{document_id}.json"

    asyncio.run(fetch_document(document_id, is_corrupt, output_path))
