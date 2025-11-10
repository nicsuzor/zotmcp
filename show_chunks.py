#!/usr/bin/env python3
"""Show 3 random chunks from a document."""

import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from buttermilk import init_async
from buttermilk.tools import ChromaDBSearchTool
from buttermilk.utils.text_quality import detect_text_corruption


async def show_random_chunks(document_id: str):
    """Show 3 random chunks from a document."""
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

        # Pick 3 random chunks
        indices = random.sample(
            range(len(results["documents"])), min(3, len(results["documents"]))
        )

        for i, idx in enumerate(indices, 1):
            chunk_text = results["documents"][idx]
            chunk_id = results["ids"][idx]

            # Analyze corruption
            corruption = detect_text_corruption(chunk_text)

            print(f"\n{'=' * 80}")
            print(f"CHUNK {i}/3 (ID: {chunk_id})")
            print(
                f"Corrupted: {corruption['is_corrupted']} | CID count: {corruption['cid_count']} | Corruption: {corruption['corruption_percentage']:.1f}%"
            )
            print(f"{'=' * 80}")
            print(chunk_text[:600])
            if len(chunk_text) > 600:
                print("\n[... truncated ...]")

    finally:
        await bm.graceful_shutdown()


if __name__ == "__main__":
    document_id = sys.argv[1] if len(sys.argv) > 1 else "ULXGASB5"
    asyncio.run(show_random_chunks(document_id))
