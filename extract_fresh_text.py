#!/usr/bin/env python3
"""Extract fresh text from PDF and save in test data format."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from buttermilk import init_async
from buttermilk.chunking import BaseRecord, SemanticSplitter


async def extract_fresh_text(pdf_path: str, document_id: str, output_path: str):
    """Extract fresh text from PDF and save as test data."""
    # Initialize buttermilk
    conf_dir = "conf"
    bm = await init_async(
        config_dir=conf_dir, config_name="zotero", overrides=["db=dev"]
    )

    try:
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            print(f"❌ PDF file not found: {pdf_path}")
            return

        print(f"📄 Extracting text from: {pdf_file.name}")

        # Extract text using pdftotext (same as pipeline)
        result = subprocess.run(
            ["pdftotext", str(pdf_file), "-"],
            capture_output=True,
            text=True,
            check=True,
        )
        full_text = result.stdout

        print(f"✅ Extracted {len(full_text)} characters")

        # Create a BaseRecord for chunking
        record = BaseRecord(record_id=document_id, content=full_text)

        # Chunk the text using SemanticSplitter (same config as pipeline)
        splitter = SemanticSplitter(chunk_size=500, chunk_overlap=200)
        chunks = []
        chunk_ids = []

        async for chunk_record in splitter.process(record):
            # SemanticSplitter attaches chunks to the record
            if hasattr(chunk_record, "chunks") and chunk_record.chunks:
                # Extract text from each ChunkedDocument
                for chunk in chunk_record.chunks:
                    if hasattr(chunk, "chunk_text"):
                        chunks.append(chunk.chunk_text)
                        chunk_ids.append(f"{document_id}_fresh_{len(chunks) - 1}")

        print(f"✅ Created {len(chunks)} chunks")

        # Create test record (same format as ChromaDB version)
        test_record = {
            "id": f"{document_id}_fresh",
            "corrupt": False,  # Fresh extraction should be clean
            "chunks": chunks,
            "chunk_ids": chunk_ids,
            "metadata": {
                "source": "fresh_extraction",
                "pdf_file": pdf_file.name,
                "total_chars": len(full_text),
            },
        }

        # Save to file
        output_file = Path(output_path)
        with open(output_file, "w") as f:
            json.dump(test_record, f, indent=2)

        print(f"✅ Saved fresh extraction to: {output_file}")
        print(f"   Document ID: {test_record['id']}")
        print(f"   Chunks: {len(chunks)}")
        print("   Marked as corrupt: False")

        # Run corruption detection to prove it's clean
        from buttermilk.utils.text_quality import is_document_corrupt

        result = is_document_corrupt(chunks, threshold=66.0)
        print("\n📊 Corruption Analysis:")
        print(f"   Is corrupt: {result['is_corrupt']}")
        print(f"   Corruption rate: {result['corruption_rate']:.1f}%")
        print(
            f"   Corrupted chunks: {result['corrupted_chunks']}/{result['total_chunks']}"
        )

    finally:
        await bm.graceful_shutdown()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: python extract_fresh_text.py <pdf_path> <document_id> [output_path]"
        )
        sys.exit(1)

    pdf_path = sys.argv[1]
    document_id = sys.argv[2]
    output_path = (
        sys.argv[3] if len(sys.argv) > 3 else f"tests/data/{document_id}_fresh.json"
    )

    asyncio.run(extract_fresh_text(pdf_path, document_id, output_path))
