"""ZoteroItemSource - Fetch specific Zotero items by key.

This Source is used for reprocessing specific documents (e.g., corrupt ones)
without iterating through the entire Zotero library.

Usage in config:
    source:
      _target_: src.zotero_items.ZoteroItemSource
      library_id: ${oc.env:ZOTERO_LIBRARY_ID}
      item_keys_file: documents_to_remove_ids.txt
"""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr
from pyzotero import zotero

from buttermilk import bm, logger
from buttermilk._core.retry import RetryWrapper
from buttermilk._core.types import BaseRecord

from zotmcp.citation_key_gate import extract_native_citation_key


class ZoteroItemSource(BaseModel):
    """Source that yields BaseRecord objects for specific Zotero items by key.

    This source:
    - Reads item keys from a text file (one key per line)
    - Fetches each item individually from Zotero API
    - Yields minimal BaseRecord objects (ID + metadata only)

    Unlike ZoteroSource which iterates through all items, this fetches
    only specific items by key. Useful for reprocessing corrupt documents
    or processing a curated list of items.
    """

    model_config = {"arbitrary_types_allowed": True}

    library_id: str = Field(..., description="Zotero library ID")
    item_keys_file: str = Field(
        ..., description="Path to text file with item keys (one per line)"
    )
    item_keys: list[str] = Field(default_factory=list, description="Loaded item keys")

    _zot: RetryWrapper | None = PrivateAttr(default=None)

    def __init__(self, **data: Any):
        """Initialize and load item keys from file."""
        super().__init__(**data)

        # Load item keys from file
        keys_file = Path(self.item_keys_file)
        if not keys_file.exists():
            raise FileNotFoundError(f"Item keys file not found: {keys_file}")

        # Read keys, strip whitespace, skip empty lines
        keys_text = keys_file.read_text()
        self.item_keys = [
            line.strip() for line in keys_text.split("\n") if line.strip()
        ]

        logger.info(f"Loaded {len(self.item_keys)} item keys from {keys_file}")

    @property
    def zot(self) -> RetryWrapper:
        """Lazily initialize the Zotero client wrapped in RetryWrapper."""
        if self._zot is None:
            from buttermilk._core.constants import cache

            zot_client = zotero.Zotero(
                library_id=self.library_id,
                library_type="group",
                api_key=bm.credentials.get("ZOTERO_API_KEY"),
            )
            self._zot = RetryWrapper(
                client=zot_client,
                max_retries=3,
                min_wait_seconds=5.0,
                max_wait_seconds=60.0,
                jitter_seconds=5.0,
            )
            # Ensure cache directory exists
            bm.session_info.get_cache_subdir(cache.ZOTERO, create=True)
        return self._zot

    def __aiter__(self) -> AsyncGenerator[BaseRecord, None]:
        """Enable async iteration."""
        return self.fetch_items()

    async def fetch_items(self) -> AsyncGenerator[BaseRecord, None]:
        """Fetch specific Zotero items by key and yield BaseRecord objects.

        This method:
        - Fetches each item individually using pyzotero's item() method
        - Skips items that don't exist or are invalid types
        - Returns items in the order specified in the keys file

        Yields:
            BaseRecord: Minimal records with record_id and metadata
        """
        yielded_count = 0
        skipped_count = 0
        excluded: list[tuple[str, str]] = []  # (item_key, title) lacking native key

        for key in self.item_keys:
            try:
                # Fetch single item with retry logic
                async def _fetch_item() -> dict[str, Any]:
                    """Async wrapper for synchronous zot.item() call."""
                    return await asyncio.get_event_loop().run_in_executor(
                        None, lambda: self.zot.client.item(key)
                    )

                item = await self.zot._execute_with_retry(_fetch_item)

                # Skip invalid items
                if not item:
                    logger.warning(f"Item {key} not found, skipping")
                    skipped_count += 1
                    continue

                item_type = item.get("data", {}).get("itemType")
                if item_type in {"attachment", "note", "annotation"}:
                    logger.debug(f"Skipping {item_type} item: {key}")
                    skipped_count += 1
                    continue

                # Single authoritative key: Zotero's NATIVE citationKey field only
                # (populated by BetterBibTeX). No `extra`-field fallback.
                zotero_data = item.get("data", {})
                citation_key = extract_native_citation_key(zotero_data)

                # Hard pre-ingest gate: an item with no native citation key is
                # EXCLUDED (never enters ChromaDB). Report it so it can be keyed in
                # BetterBibTeX and re-ingested.
                if citation_key is None:
                    title = zotero_data.get("title", "(untitled)")
                    logger.warning(
                        "🚫 Excluding item from ingest: no native Zotero "
                        "citationKey (key it in BetterBibTeX and re-ingest)",
                        record_id=key,
                        title=str(title)[:120],
                    )
                    excluded.append((key, str(title)))
                    skipped_count += 1
                    continue

                # Track item version
                item_version = item.get("version", 0)

                # Create minimal BaseRecord with ID and metadata
                record = BaseRecord(
                    record_id=key,
                    metadata={
                        "zotero_item": zotero_data,
                        "zotero_version": item_version,
                        "zotero_links": item.get("links", {}),
                        "citation_key": citation_key,
                    },
                )

                yielded_count += 1
                logger.debug(
                    f"Yielded item {key}: {zotero_data.get('title', 'N/A')[:50]}"
                )
                yield record

            except Exception as e:
                logger.error(f"Error fetching item {key}: {e}")
                skipped_count += 1
                continue

        logger.info(
            f"✅ Fetch complete: {yielded_count} items yielded, {skipped_count} skipped"
        )

        if excluded:
            report = "\n".join(f"  {k}\t{t}" for k, t in excluded)
            logger.warning(
                f"⚠️ {len(excluded)} item(s) EXCLUDED from ingest for lacking a "
                f"native Zotero citationKey. Key these in BetterBibTeX and "
                f"re-ingest:\n{report}"
            )
