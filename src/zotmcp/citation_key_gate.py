"""Hard pre-ingest gate on the native Zotero citation key.

Single authoritative key policy (decision 2026-06-19): the ONLY accepted citation
key is Zotero's **native `citationKey`** field, populated solely by BetterBibTeX.
There is no `extra`-field fallback and no silent `None`.

This processor sits early in the vectorization pipeline (after the source/download
stage that populates `zotero_data`, before any expensive extraction/embedding work).
It:

  1. Reads the native key from ``record.metadata["zotero_data"]["citationKey"]``.
  2. Normalises ``record.metadata["citation_key"]`` to that native value so every
     downstream chunk carries the authoritative key.
  3. EXCLUDES (does not yield) any record whose native key is missing/empty, and
     records it in an actionable report (item key + title) so it can be keyed in
     BetterBibTeX and re-ingested.

Excluding here — rather than letting a ``None`` key flow into ChromaDB — is the
whole point of the gate: no un-keyed item is ever indexed.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from buttermilk import logger
from buttermilk._core.processing_context import ProcessingContext
from buttermilk._core.types import Record


def extract_native_citation_key(zotero_data: Any) -> str | None:
    """Return the non-empty native ``citationKey`` from a Zotero data payload.

    ``zotero_data`` is the full Zotero item ``data`` dict (the common case), or a
    JSON string if an upstream step already serialised it. Anything else, or an
    empty/whitespace value, yields ``None``.
    """
    if isinstance(zotero_data, str):
        try:
            zotero_data = json.loads(zotero_data)
        except (ValueError, TypeError):
            return None
    if isinstance(zotero_data, dict):
        key = zotero_data.get("citationKey")
        if isinstance(key, str) and key.strip():
            return key.strip()
    return None


def _record_title(record: Record) -> str:
    md = record.metadata or {}
    title = md.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    zd = md.get("zotero_data")
    if isinstance(zd, dict):
        zt = zd.get("title")
        if isinstance(zt, str) and zt.strip():
            return zt.strip()
    return "(untitled)"


class CitationKeyGateProcessor(BaseModel):
    """Exclude any record lacking a non-empty native Zotero ``citationKey``.

    Configuration:
        report_path: File to which excluded items are appended (item key + title).
                     Defaults to ``ZOTMCP_CITATIONKEY_REPORT`` env var or
                     ``citationkey_gate_excluded.txt`` in the cwd.
        log_exclusions: Emit a warning log line per excluded item when True.

    Place this AFTER the source/download stage (so ``zotero_data`` is populated)
    and BEFORE extraction/embedding (so excluded items cost nothing downstream).
    """

    report_path: str | None = Field(
        default=None,
        description="Where to append excluded items (item key + title). "
        "Defaults to $ZOTMCP_CITATIONKEY_REPORT or ./citationkey_gate_excluded.txt.",
    )
    log_exclusions: bool = Field(
        default=True,
        description="Log a warning for each excluded (un-keyed) item.",
    )

    def _resolve_report_path(self) -> Path:
        target = (
            self.report_path
            or os.environ.get("ZOTMCP_CITATIONKEY_REPORT")
            or "citationkey_gate_excluded.txt"
        )
        return Path(target)

    def _report_excluded(self, record_id: str, title: str) -> None:
        path = self._resolve_report_path()
        ts = datetime.now(timezone.utc).isoformat()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(f"{ts}\t{record_id}\t{title}\n")
        except OSError as exc:  # reporting must never crash the pipeline
            logger.error(
                f"Failed to write citationKey-gate report to {path}: {exc}",
                record_id=record_id,
            )

    async def process(
        self, context: ProcessingContext
    ) -> AsyncGenerator[Record, None]:
        """Gate one record on its native citation key.

        Yields the record (with ``citation_key`` normalised to the native value)
        when a non-empty native key is present; yields nothing otherwise.
        """
        record = context.record
        metadata = record.metadata.copy() if record.metadata else {}

        native_key = extract_native_citation_key(metadata.get("zotero_data"))

        if native_key is None:
            title = _record_title(record)
            if self.log_exclusions:
                logger.warning(
                    "🚫 Excluding item from ingest: no native Zotero citationKey "
                    "(key it in BetterBibTeX and re-ingest)",
                    record_id=record.record_id,
                    title=title[:120],
                )
            self._report_excluded(record.record_id, title)
            return  # hard gate: do not yield -> never enters ChromaDB

        # Authoritative key wins over anything an upstream stage may have set.
        metadata["citation_key"] = native_key
        yield record.model_copy(update={"metadata": metadata})
