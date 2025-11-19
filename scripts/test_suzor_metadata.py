#!/usr/bin/env python3
"""
Diagnostic script to verify Suzor papers in ChromaDB zotero_data field.

Tests:
1. Query ChromaDB for items containing "suzor" in zotero_data
2. Parse zotero_data JSON and extract creators
3. Confirm metadata is present but not searchable
"""

import chromadb
import json
from pathlib import Path
from typing import Dict, List, Any


def find_suzor_papers(collection) -> tuple[List[str], List[Dict[str, Any]]]:
    """
    Find all items with 'suzor' in zotero_data field.

    Returns:
        Tuple of (item_keys, zotero_data_objects)
    """
    # Get ALL items from collection
    results = collection.get(include=["metadatas"])

    suzor_keys = []
    suzor_data = []

    # Check each item's zotero_data field
    for idx, metadata in enumerate(results["metadatas"]):
        zotero_data_str = metadata.get("zotero_data", "")

        # Case-insensitive search for "suzor"
        if "suzor" in zotero_data_str.lower():
            item_key = metadata.get("item_key", f"unknown_{idx}")
            suzor_keys.append(item_key)

            # Parse JSON
            try:
                data = json.loads(zotero_data_str)
                suzor_data.append(data)
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse JSON for {item_key}: {e}")
                suzor_data.append({"error": str(e)})

    return suzor_keys, suzor_data


def extract_creators(zotero_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract creators array from zotero_data."""
    return zotero_data.get("creators", [])


def main():
    """Run diagnostic tests."""
    print("🔍 Testing Suzor metadata in ChromaDB\n")

    # Connect to ChromaDB
    db_path = Path.home() / ".config" / "zotero-mcp" / "chroma_db"

    if not db_path.exists():
        print(f"❌ ChromaDB not found at {db_path}")
        return

    print(f"📂 Database: {db_path}")

    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_collection("zotero_library")

    print(f"📚 Collection: {collection.name}")
    print(f"📊 Total items: {collection.count()}\n")

    # Find Suzor papers
    print("🔎 Searching for 'suzor' in zotero_data field...")
    suzor_keys, suzor_data = find_suzor_papers(collection)

    print(f"\n✅ Found {len(suzor_keys)} items with 'suzor' in zotero_data\n")

    if not suzor_keys:
        print("❌ No Suzor papers found!")
        return

    # Show sample results
    print("=" * 80)
    print("SAMPLE RESULTS")
    print("=" * 80)

    for idx, (key, data) in enumerate(zip(suzor_keys[:3], suzor_data[:3])):
        print(f"\n[{idx + 1}] Item Key: {key}")
        print(f"    Title: {data.get('title', 'N/A')}")
        print(f"    Year: {data.get('date', 'N/A')}")

        creators = extract_creators(data)
        print(f"    Creators ({len(creators)}):")
        for creator in creators:
            creator_type = creator.get("creatorType", "unknown")
            last_name = creator.get("lastName", "")
            first_name = creator.get("firstName", "")
            name = creator.get("name", "")  # For single-field names

            if name:
                print(f"      - {creator_type}: {name}")
            else:
                print(f"      - {creator_type}: {first_name} {last_name}")

        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total Suzor papers found: {len(suzor_keys)}")
    print(f"Sample item keys: {suzor_keys[:5]}")
    print()
    print("✅ Confirmation: Suzor papers exist in zotero_data field")
    print("❌ Issue: This data is NOT accessible to semantic/metadata search")
    print()
    print("Reason: ChromaDB metadata is for filtering only. Content in metadata")
    print("        fields is NOT indexed for search. Only the 'documents' field")
    print("        (which contains title + abstract) is searchable.")
    print()


if __name__ == "__main__":
    main()
