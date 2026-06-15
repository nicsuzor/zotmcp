#!/usr/bin/env python3
"""Batch paper ingestion CLI for Zotero.

Resolves DOIs and arXiv IDs to metadata + best available PDF, then
optionally creates Zotero items (requires ZOTERO_API_KEY + ZOTERO_LIBRARY_ID).

Usage:
    # Single paper by arXiv ID
    uv run python scripts/ingest_batch.py --identifier 2605.29800 --tag incoming/tja-2026-06

    # Single paper by DOI
    uv run python scripts/ingest_batch.py --identifier 10.1234/xyz --tag incoming/tja-2026-06

    # Batch from file (one identifier per line; # comments and blank lines ignored)
    uv run python scripts/ingest_batch.py --file papers.txt --tag incoming/tja-2026-06
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Ensure src/ is on the path when run as a script
_src = Path(__file__).parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


@dataclass
class IngestResult:
    identifier: str
    title: str
    item_key: Optional[str]
    created: Optional[bool]
    pdf_source: Optional[str]
    status: str  # "created", "existing", "no_creds", "resolve_only", "error"
    error: Optional[str] = None


async def ingest_one(
    identifier: str,
    tag: str,
    collection_key: Optional[str] = None,
) -> IngestResult:
    """Resolve and (optionally) ingest a single paper identifier.

    If Zotero credentials are absent, performs resolution only and returns
    status="no_creds" with the resolved metadata.
    """
    from zotmcp.source_resolver import resolve_paper

    # Resolve metadata + PDF
    try:
        paper = await resolve_paper(identifier)
    except Exception as e:
        return IngestResult(
            identifier=identifier,
            title="[resolution failed]",
            item_key=None,
            created=None,
            pdf_source=None,
            status="error",
            error=str(e),
        )

    # Check Zotero credentials
    api_key = os.environ.get("ZOTERO_API_KEY")
    library_id = os.environ.get("ZOTERO_LIBRARY_ID")
    if not api_key or not library_id:
        return IngestResult(
            identifier=identifier,
            title=paper.title,
            item_key=None,
            created=None,
            pdf_source=paper.pdf_source,
            status="no_creds",
            error="ZOTERO_API_KEY or ZOTERO_LIBRARY_ID not set — resolution only",
        )

    # Write to Zotero
    try:
        from zotmcp.zotero_write import ZoteroWriter

        writer = ZoteroWriter()

        creators: list[dict] = []
        for author_name in paper.authors:
            parts = author_name.rsplit(" ", 1)
            if len(parts) == 2:
                creators.append(
                    {
                        "firstName": parts[0],
                        "lastName": parts[1],
                        "creatorType": "author",
                    }
                )
            else:
                creators.append({"name": author_name, "creatorType": "author"})

        metadata: dict = {"title": paper.title, "creators": creators}
        if paper.year:
            metadata["date"] = str(paper.year)
        if paper.doi:
            metadata["doi"] = paper.doi
        if paper.abstract:
            metadata["abstractNote"] = paper.abstract
        if paper.extra:
            metadata["extra"] = paper.extra

        result = writer.create_item(
            item_type=paper.item_type,
            metadata=metadata,
            collection_key=collection_key,
            dedupe_by="doi" if paper.doi else "none",
            incoming_tag=tag,
        )

        item_key = result["item_key"]

        # Link PDF attachment if available
        if paper.pdf_url:
            try:
                writer.add_attachment_from_url(item_key, paper.pdf_url, "PDF")
            except Exception as att_e:
                print(
                    f"  Warning: failed to link PDF for {item_key}: {att_e}",
                    file=sys.stderr,
                )

        status = "created" if result["created"] else "existing"
        return IngestResult(
            identifier=identifier,
            title=paper.title,
            item_key=item_key,
            created=result["created"],
            pdf_source=paper.pdf_source,
            status=status,
        )

    except Exception as e:
        return IngestResult(
            identifier=identifier,
            title=paper.title,
            item_key=None,
            created=None,
            pdf_source=paper.pdf_source,
            status="error",
            error=str(e),
        )


def print_summary(results: list[IngestResult]) -> None:
    """Print a formatted summary table."""
    col_widths = [22, 42, 12, 8, 18, 10]
    headers = ["Identifier", "Title", "Item Key", "Created", "PDF Source", "Status"]

    header_row = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    separator = "-+-".join("-" * w for w in col_widths)
    print(header_row)
    print(separator)

    for r in results:
        title_s = r.title or ""
        max_title = col_widths[1]
        if len(title_s) > max_title:
            title_s = title_s[: max_title - 2] + ".."

        row_vals = [
            (r.identifier or "")[: col_widths[0]],
            title_s,
            (r.item_key or "")[: col_widths[2]],
            (str(r.created) if r.created is not None else "-"),
            (r.pdf_source or "-"),
            r.status,
        ]
        print(" | ".join(v.ljust(w) for v, w in zip(row_vals, col_widths)))

    print()
    counts = {s: sum(1 for r in results if r.status == s) for s in ["created", "existing", "no_creds", "error"]}
    resolved_pdf = sum(1 for r in results if r.pdf_source is not None)
    n = len(results)
    print(
        f"Summary: {n} papers | "
        f"{counts['created']} created | "
        f"{counts['existing']} existing | "
        f"{counts['no_creds']} no-creds | "
        f"{counts['error']} errors"
    )
    print(f"         {resolved_pdf}/{n} papers have a free PDF URL")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch ingest papers into Zotero via DOI or arXiv ID.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--identifier", metavar="DOI_OR_ARXIV", help="Single identifier")
    group.add_argument(
        "--file",
        metavar="PATH",
        help="File with one identifier per line (# comments and blank lines ignored)",
    )
    parser.add_argument("--tag", default="incoming/tja-2026-06", help="Incoming tag")
    parser.add_argument("--collection", metavar="KEY", default=None, help="Zotero collection key")

    args = parser.parse_args()

    if args.identifier:
        identifiers = [args.identifier]
    else:
        lines = Path(args.file).read_text(encoding="utf-8").splitlines()
        identifiers = [
            ln.strip()
            for ln in lines
            if ln.strip() and not ln.strip().startswith("#")
        ]

    has_creds = bool(os.environ.get("ZOTERO_API_KEY") and os.environ.get("ZOTERO_LIBRARY_ID"))
    print(f"Ingesting {len(identifiers)} paper(s) with tag '{args.tag}'")
    if not has_creds:
        print(
            "NOTE: ZOTERO_API_KEY or ZOTERO_LIBRARY_ID not set — "
            "resolution only (no Zotero write)"
        )
    print()

    results: list[IngestResult] = []
    for identifier in identifiers:
        print(f"  Resolving {identifier} ...")
        result = await ingest_one(identifier, args.tag, args.collection)
        results.append(result)
        pdf_str = f"pdf={result.pdf_source}" if result.pdf_source else "no-pdf"
        title_preview = (result.title or "")[:60]
        print(f"    → {title_preview!r} | {result.status} | {pdf_str}")

    print()
    print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
