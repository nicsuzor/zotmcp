"""Thin pyzotero wrapper for Zotero write operations.

All operations are synchronous — the MCP server wraps them in
asyncio.run_in_executor where needed.

Requires env vars:
    ZOTERO_API_KEY    — Zotero API key with write access
    ZOTERO_LIBRARY_ID — Numeric group/user library ID
    ZOTERO_LIBRARY_TYPE — "group" (default) or "user"
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

from pyzotero import zotero

logger = logging.getLogger(__name__)

RATE_LIMIT_RETRIES = 3
RATE_LIMIT_BACKOFF_BASE = 2  # seconds


def _normalize_doi(doi: str) -> str:
    """Strip URL prefix and lowercase DOI for comparison.

    Examples:
        "https://doi.org/10.1234/TEST" → "10.1234/test"
        "doi:10.1234/test"             → "10.1234/test"
        "10.1234/test"                 → "10.1234/test"
    """
    doi = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi.lower()


class ZoteroWriteError(Exception):
    """Structured Zotero write error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ZoteroWriter:
    """Thin pyzotero wrapper for write operations. Initialised from env vars."""

    def __init__(self):
        api_key = os.environ.get("ZOTERO_API_KEY")
        library_id = os.environ.get("ZOTERO_LIBRARY_ID")
        if not api_key:
            raise ValueError("ZOTERO_API_KEY environment variable is required")
        if not library_id:
            raise ValueError("ZOTERO_LIBRARY_ID environment variable is required")
        library_type = os.environ.get("ZOTERO_LIBRARY_TYPE", "group")
        self._zot = zotero.Zotero(library_id, library_type, api_key)

    def _retry_on_rate_limit(self, fn, *args, **kwargs):
        """Call fn with exponential backoff on HTTP 429 responses."""
        last_exc = None
        for attempt in range(RATE_LIMIT_RETRIES):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                # pyzotero raises httpx.HTTPStatusError or custom errors;
                # detect 429 by checking the string representation
                if "429" in str(e):
                    # attempt starts at 0; +1 makes the first backoff equal
                    # RATE_LIMIT_BACKOFF_BASE seconds (the documented base).
                    wait = RATE_LIMIT_BACKOFF_BASE ** (attempt + 1)
                    logger.warning(
                        f"Rate limited (429), retry {attempt + 1}/{RATE_LIMIT_RETRIES} in {wait}s"
                    )
                    time.sleep(wait)
                    last_exc = e
                else:
                    raise
        raise last_exc  # type: ignore[misc]

    def get_current_version(self, item_key: str) -> int:
        """Get the current version of an item for optimistic locking."""
        items = self._retry_on_rate_limit(self._zot.items, itemKey=item_key)
        if not items:
            raise ZoteroWriteError(f"Item {item_key} not found")
        return items[0]["version"]

    def find_by_doi(self, doi: str) -> Optional[dict]:
        """Search for an existing item by DOI. Returns Zotero item dict or None.

        Uses a broad pyzotero search on the normalised DOI, then exact-matches
        the DOI field to filter out false positives from the text search.
        """
        normalized = _normalize_doi(doi)
        results = self._retry_on_rate_limit(
            self._zot.items, q=normalized, itemType="-attachment"
        )
        for item in results:
            data = item.get("data", {})
            item_doi = data.get("DOI", "")
            if item_doi and _normalize_doi(item_doi) == normalized:
                return item
        return None

    def create_item(
        self,
        item_type: str,
        metadata: dict,
        collection_key: Optional[str] = None,
        dedupe_by: str = "doi",
        incoming_tag: Optional[str] = None,
    ) -> dict:
        """Create a new Zotero item.

        Args:
            item_type: Zotero item type, e.g. "journalArticle", "preprint".
            metadata: Dict with keys: title, creators, date, doi, url,
                      abstractNote, publicationTitle, extra.
            collection_key: Zotero collection key to add the item to.
            dedupe_by: "doi" to check for existing item by DOI before creating;
                       "none" to always create.
            incoming_tag: Tag added to mark agent-ingested items.

        Returns:
            {"item_key": str, "created": bool, "existing_key": str | None}
        """
        # Dedup check
        if dedupe_by == "doi" and metadata.get("doi"):
            existing = self.find_by_doi(metadata["doi"])
            if existing:
                existing_key = existing["key"]
                logger.info(
                    f"Item already exists with key {existing_key}, skipping create"
                )
                if incoming_tag:
                    self.add_tags(existing_key, [incoming_tag])
                return {
                    "item_key": existing_key,
                    "created": False,
                    "existing_key": existing_key,
                }

        # Build from pyzotero template
        template = self._retry_on_rate_limit(self._zot.item_template, item_type)

        # Fill in standard fields (only set if the template has the field)
        if "title" in template and "title" in metadata:
            template["title"] = metadata["title"]
        if "creators" in template and "creators" in metadata:
            template["creators"] = metadata["creators"]
        if "date" in template and "date" in metadata:
            template["date"] = metadata["date"]
        if "DOI" in template and "doi" in metadata:
            template["DOI"] = metadata["doi"]
        if "url" in template and "url" in metadata:
            template["url"] = metadata["url"]
        if "abstractNote" in template and "abstractNote" in metadata:
            template["abstractNote"] = metadata["abstractNote"]
        if "publicationTitle" in template and "publicationTitle" in metadata:
            template["publicationTitle"] = metadata["publicationTitle"]
        if "extra" in template and "extra" in metadata:
            template["extra"] = metadata["extra"]

        # Tags
        tags = list(template.get("tags", []))
        if incoming_tag:
            tags.append({"tag": incoming_tag})
        template["tags"] = tags

        # Collection
        if collection_key:
            template["collections"] = [collection_key]

        result = self._retry_on_rate_limit(self._zot.create_items, [template])
        success = result.get("success", {})
        if not success:
            failed = result.get("failed", {})
            raise ZoteroWriteError(f"Failed to create item: {failed}")
        item_key = list(success.values())[0]
        logger.info(f"Created Zotero item {item_key} (type={item_type})")
        return {"item_key": item_key, "created": True, "existing_key": None}

    def update_item(
        self, item_key: str, patch: dict, version: Optional[int] = None
    ) -> dict:
        """Patch an item.

        Args:
            item_key: Zotero item key.
            patch: Fields to update (merged into existing item data).
            version: Optional optimistic lock — if provided and doesn't match
                     current server version, returns a version_conflict error.

        Returns:
            {"ok": True, "new_version": int} on success.
            {"ok": False, "error": "version_conflict", "new_version": int} on conflict.
        """
        items = self._retry_on_rate_limit(self._zot.items, itemKey=item_key)
        if not items:
            raise ZoteroWriteError(f"Item {item_key} not found")
        item = items[0]

        current_version = item["version"]
        if version is not None and current_version != version:
            return {
                "ok": False,
                "error": "version_conflict",
                "new_version": current_version,
            }

        # Apply patch to item data
        updated_data = dict(item["data"])
        updated_data.update(patch)

        # Build the payload pyzotero's update_item expects:
        # a dict with top-level "key" and "version" plus the data fields
        payload = {"key": item_key, "version": current_version, **updated_data}

        try:
            self._retry_on_rate_limit(self._zot.update_item, payload)
            # Fetch the new version
            new_items = self._retry_on_rate_limit(self._zot.items, itemKey=item_key)
            new_version = new_items[0]["version"] if new_items else current_version + 1
            return {"ok": True, "new_version": new_version}
        except Exception as e:
            if "412" in str(e) or "Precondition Failed" in str(e):
                # Match the other conflict path's contract: return an int version.
                # Fetch the latest server version, falling back to current_version.
                latest_version = current_version
                try:
                    refreshed = self._retry_on_rate_limit(
                        self._zot.items, itemKey=item_key
                    )
                    if refreshed:
                        latest_version = refreshed[0]["version"]
                except Exception:
                    pass
                return {
                    "ok": False,
                    "error": "version_conflict",
                    "new_version": latest_version,
                }
            raise

    def add_tags(self, item_key: str, tags: list[str]) -> dict:
        """Add tags to an item. Idempotent — skips tags already present.

        Returns:
            {"ok": bool, "tags_added": int, "tags_skipped": int}
        """
        items = self._retry_on_rate_limit(self._zot.items, itemKey=item_key)
        if not items:
            raise ZoteroWriteError(f"Item {item_key} not found")
        item = items[0]

        existing_tags = {t["tag"] for t in item["data"].get("tags", [])}
        new_tags = [t for t in tags if t not in existing_tags]
        skipped = len([t for t in tags if t in existing_tags])

        if not new_tags:
            return {"ok": True, "tags_added": 0, "tags_skipped": skipped}

        all_tags = list(item["data"].get("tags", [])) + [{"tag": t} for t in new_tags]
        # Update item with merged tags
        payload = {
            "key": item_key,
            "version": item["version"],
            **item["data"],
            "tags": all_tags,
        }
        self._retry_on_rate_limit(self._zot.update_item, payload)
        return {"ok": True, "tags_added": len(new_tags), "tags_skipped": skipped}

    def add_note(self, item_key: str, note_html: str) -> dict:
        """Add a note child item. Checks for exact duplicate before creating.

        Args:
            item_key: Parent item key.
            note_html: HTML content for the note.

        Returns:
            {"note_key": str, "created": bool}
        """
        children = self._retry_on_rate_limit(self._zot.children, item_key)
        for child in children:
            if child["data"].get("itemType") == "note":
                existing_note = child["data"].get("note", "").strip()
                if existing_note == note_html.strip():
                    logger.debug(
                        f"Duplicate note found for {item_key}, skipping creation"
                    )
                    return {"note_key": child["key"], "created": False}

        template = self._retry_on_rate_limit(self._zot.item_template, "note")
        template["note"] = note_html
        template["parentItem"] = item_key

        result = self._retry_on_rate_limit(self._zot.create_items, [template])
        success = result.get("success", {})
        if not success:
            raise ZoteroWriteError(
                f"Failed to create note: {result.get('failed', {})}"
            )
        note_key = list(success.values())[0]
        return {"note_key": note_key, "created": True}

    def add_attachment_from_url(
        self, item_key: str, url: str, title: str = "PDF"
    ) -> dict:
        """Link a URL attachment to an item (linked_url type — no file upload).

        Args:
            item_key: Parent item key.
            url: URL of the PDF or resource.
            title: Display title for the attachment.

        Returns:
            {"attachment_key": str}
        """
        # Build a linked_url attachment template
        template = self._retry_on_rate_limit(
            self._zot.item_template, "attachment", linkmode="linked_url"
        )
        template["url"] = url
        template["title"] = title
        template["parentItem"] = item_key

        result = self._retry_on_rate_limit(self._zot.create_items, [template])
        success = result.get("success", {})
        if not success:
            raise ZoteroWriteError(
                f"Failed to add attachment: {result.get('failed', {})}"
            )
        attachment_key = list(success.values())[0]
        logger.info(f"Linked URL attachment {attachment_key} to {item_key}")
        return {"attachment_key": attachment_key}
