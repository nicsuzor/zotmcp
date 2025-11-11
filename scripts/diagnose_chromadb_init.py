#!/usr/bin/env python3
"""Diagnostic script to check ChromaDB initialization error states."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import main module to access globals
import main


async def diagnose():
    """Check the initialization state and errors."""
    print("=" * 60)
    print("ChromaDB Initialization Diagnostic")
    print("=" * 60)

    # Wait a bit for background tasks to start
    print("\nWaiting 2 seconds for initialization tasks to start...")
    await asyncio.sleep(2)

    # Check GCP state
    print("\n--- GCP Initialization State ---")
    print(f"GCP ready: {main._gcp_ready}")
    print(f"GCP error: {main._gcp_init_error}")
    print(f"GCP task: {main._gcp_init_task}")
    if main._gcp_init_task:
        print(f"GCP task done: {main._gcp_init_task.done()}")
        if main._gcp_init_task.done() and main._gcp_init_task.exception():
            print(f"GCP task exception: {main._gcp_init_task.exception()}")

    # Check ChromaDB state
    print("\n--- ChromaDB Initialization State ---")
    print(f"ChromaDB ready: {main._chromadb_ready}")
    print(f"ChromaDB error: {main._chromadb_init_error}")
    print(f"ChromaDB task: {main._chromadb_init_task}")
    if main._chromadb_init_task:
        print(f"ChromaDB task done: {main._chromadb_init_task.done()}")
        if main._chromadb_init_task.done() and main._chromadb_init_task.exception():
            print(f"ChromaDB task exception: {main._chromadb_init_task.exception()}")

    # Wait longer to see if they complete
    print("\n--- Waiting 10 more seconds for completion ---")
    for i in range(10):
        await asyncio.sleep(1)
        if main._gcp_ready and main._chromadb_ready:
            print(f"\n✅ Both initialized successfully after {i + 1} seconds!")
            break
        if main._gcp_init_error or main._chromadb_init_error:
            print(f"\n❌ Error detected after {i + 1} seconds")
            break
        print(f"  {i + 1}s - GCP: {main._gcp_ready}, ChromaDB: {main._chromadb_ready}")

    # Final state
    print("\n--- Final State ---")
    print(f"GCP ready: {main._gcp_ready}")
    print(f"GCP error: {main._gcp_init_error}")
    print(f"ChromaDB ready: {main._chromadb_ready}")
    print(f"ChromaDB error: {main._chromadb_init_error}")

    # Analysis
    print("\n--- Analysis ---")
    if main._gcp_init_error:
        print("❌ BLOCKER: GCP initialization failed")
        print(f"   Error: {main._gcp_init_error}")
        print("   ChromaDB cannot initialize without GCP (needs Vertex AI)")
    elif not main._gcp_ready:
        print("⏳ GCP initialization still in progress or stuck")
        print("   ChromaDB is waiting for GCP to complete (line 89-94 of main.py)")
    elif main._chromadb_init_error:
        print("❌ ChromaDB initialization failed after GCP succeeded")
        print(f"   Error: {main._chromadb_init_error}")
    elif not main._chromadb_ready:
        print("⏳ ChromaDB initialization still in progress")
    else:
        print("✅ Both GCP and ChromaDB initialized successfully")


if __name__ == "__main__":
    asyncio.run(diagnose())
