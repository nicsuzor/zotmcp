#!/usr/bin/env python3
"""PHASE 1 (read-only): Measure native citationKey coverage across the Zotero group library.

Classifies every top-level bibliographic item in the group library into three buckets:
  (a) has a non-empty NATIVE `citationKey` field (BBT migrated to native)
  (b) key only in `extra` ("Citation Key: ...") -- BBT not yet migrated to native field
  (c) neither -- no key at all

Read-only. Uses buttermilk credential management (GCP Secret Manager) for the API key
and library id; never prints the key.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from buttermilk import init_async  # noqa: E402
from buttermilk.libs.zotero import extract_citation_key  # noqa: E402
from pyzotero import zotero  # noqa: E402

SKIP_TYPES = {"attachment", "note", "annotation"}


async def main() -> None:
    conf_dir = str((Path(__file__).parent.parent / "src" / "zotmcp" / "conf").resolve())
    bm = await init_async(config_dir=conf_dir, config_name="zotero", overrides=["+db=dev"])

    api_key = bm.credentials.get("ZOTERO_API_KEY")
    library_id = bm.credentials.get("ZOTERO_LIBRARY_ID")
    if not api_key or not library_id:
        print("MISSING CREDENTIALS: ZOTERO_API_KEY or ZOTERO_LIBRARY_ID not resolvable")
        sys.exit(2)

    print(f"library_id (from credentials): {library_id}")
    print(f"library_type: group")
    print(f"api_key resolvable: {bool(api_key)} (not printed)")

    zot = zotero.Zotero(library_id=str(library_id), library_type="group", api_key=api_key)

    # everything() paginates through all top-level items.
    print("Fetching all top-level items (paginated)...")
    items = zot.everything(zot.top(limit=100))
    print(f"Fetched {len(items)} top-level items")

    bucket_native: list[tuple[str, str, str]] = []   # (key, citationKey, title)
    bucket_extra_only: list[tuple[str, str, str]] = []  # (key, extra_key, title)
    bucket_neither: list[tuple[str, str, str]] = []   # (key, itemType, title)
    skipped = 0

    for it in items:
        data = it.get("data", {})
        itype = data.get("itemType", "")
        if itype in SKIP_TYPES:
            skipped += 1
            continue
        key = data.get("key", it.get("key", "?"))
        title = (data.get("title") or "")[:80]
        native = data.get("citationKey")
        native_nonempty = isinstance(native, str) and native.strip() != ""
        extra_key = extract_citation_key(data.get("extra"))

        if native_nonempty:
            bucket_native.append((key, native, title))
        elif extra_key:
            bucket_extra_only.append((key, extra_key, title))
        else:
            bucket_neither.append((key, itype, title))

    total = len(bucket_native) + len(bucket_extra_only) + len(bucket_neither)
    print("\n" + "=" * 70)
    print("PHASE 1 RESULTS — group library citationKey coverage")
    print("=" * 70)
    print(f"Total bibliographic items classified (N): {total}")
    print(f"Skipped (attachment/note/annotation):     {skipped}")
    print("-" * 70)
    pct = lambda n: f"{100.0 * n / total:.1f}%" if total else "n/a"
    print(f"(a) native citationKey non-empty: {len(bucket_native):5d}  ({pct(len(bucket_native))})")
    print(f"(b) key only in extra:            {len(bucket_extra_only):5d}  ({pct(len(bucket_extra_only))})")
    print(f"(c) neither (no key):             {len(bucket_neither):5d}  ({pct(len(bucket_neither))})")
    print("=" * 70)

    def show(label: str, rows: list[tuple[str, str, str]], n: int = 8) -> None:
        print(f"\n--- sample: {label} (showing up to {n}) ---")
        for key, val, title in rows[:n]:
            print(f"  {key}  [{val!r}]  {title}")

    show("(a) native citationKey", bucket_native)
    show("(b) extra-only key", bucket_extra_only)
    show("(c) neither", bucket_neither)

    # Also write a machine-readable summary so results survive any stdout filtering.
    out = Path(__file__).parent.parent / "phase1_coverage_result.txt"
    with out.open("w") as f:
        f.write(f"library_id={library_id}\n")
        f.write(f"N={total}\nskipped={skipped}\n")
        f.write(f"native_nonempty={len(bucket_native)}\n")
        f.write(f"extra_only={len(bucket_extra_only)}\n")
        f.write(f"neither={len(bucket_neither)}\n\n")
        f.write("SAMPLE native (key | citationKey | title):\n")
        for k, v, t in bucket_native[:10]:
            f.write(f"  {k} | {v} | {t}\n")
        f.write("\nSAMPLE extra-only (key | extra_key | title):\n")
        for k, v, t in bucket_extra_only[:10]:
            f.write(f"  {k} | {v} | {t}\n")
        f.write("\nSAMPLE neither (key | itemType | title):\n")
        for k, v, t in bucket_neither[:10]:
            f.write(f"  {k} | {v} | {t}\n")
    print(f"\nWrote machine-readable summary to {out}")


if __name__ == "__main__":
    asyncio.run(main())
