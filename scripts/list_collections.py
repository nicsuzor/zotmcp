#!/usr/bin/env python3
"""List all ChromaDB collections and their stats."""

import chromadb
from pathlib import Path


def main():
    db_path = Path.home() / ".config" / "zotero-mcp" / "chroma_db"

    if not db_path.exists():
        print(f"❌ ChromaDB not found at {db_path}")
        return

    print(f"📂 Database: {db_path}\n")

    client = chromadb.PersistentClient(path=str(db_path))

    # List all collections
    collections = client.list_collections()

    print(f"Found {len(collections)} collection(s):\n")

    for coll in collections:
        print(f"  - Name: {coll.name}")
        print(f"    Count: {coll.count()}")
        print(f"    Metadata: {coll.metadata}")
        print()


if __name__ == "__main__":
    main()
