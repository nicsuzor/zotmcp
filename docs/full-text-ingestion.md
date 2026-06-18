# Full-text ingestion: add → sync → search

How to add an academic source to the Zotero library so it becomes **full-text
semantically searchable** in zotmcp, and how to undo a whole import in one step.

This is the repeatable procedure that closes the find → add → full-text loop.
It assumes the write tools (PR #13) are deployed and credentialed
(`ZOTERO_API_KEY` with **write** scope, `ZOTERO_LIBRARY_ID`,
`ZOTERO_LIBRARY_TYPE=group`).

## Why a *stored* attachment is mandatory

The full-text semantic index is built by the vectorization pipeline
(`scripts/run_vectorization.py`), which pulls **Zotero's extracted text** for
each item. Zotero only extracts text from **stored/imported** attachments
(`linkMode: imported_file` / `imported_url`) — it never extracts text from a
`linked_url` attachment (a bare URL link). So:

| Attachment type        | Tool                              | Zotero extracts text? | Enters full-text index? |
| ---------------------- | --------------------------------- | --------------------- | ----------------------- |
| `linked_url` (link)    | `link_attachment`                 | No                    | No (metadata only)      |
| `imported_file` (bytes)| `import_attachment` / `resolve_and_create(store_pdf=True)` | Yes | Yes (after next sync) |

An item with only metadata or a linked URL is searchable by title/author/abstract
but **not** by its body text. To be full-text searchable it needs uploaded PDF
bytes.

## Step 1 — Add the source with a stored PDF

Preferred one-shot path (resolves metadata + free PDF, dedupes by DOI, tags, and
uploads the PDF as a stored attachment):

```text
resolve_and_create(
    identifier="arXiv:2511.21140",      # DOI or arXiv id
    incoming_tag="incoming/<project>-<YYYY-MM>",   # e.g. incoming/tja-2026-06
    store_pdf=True,                     # default; uploads bytes (full-text capable)
)
```

The result reports `"pdf_attachment"` as one of:

- `"stored"` — PDF bytes uploaded; **will** become full-text searchable on next sync.
- `"linked"` — no real PDF available (download failed or content was not a PDF);
  fell back to a URL link; **metadata-only**, not full-text searchable.
- `"none"` — no PDF URL was resolved at all.

To attach a stored PDF to an item that already exists:

```text
import_attachment(item_key="<KEY>", url="<pdf-url>", title="Full Text PDF")
```

Both paths are idempotent: a stored attachment with the same title is not
re-uploaded, and `resolve_and_create` dedupes the parent item by DOI.

PDF resolution coverage (free, no paid API — Google grounding not needed):
arXiv (all CS/ML), Unpaywall (~50-70% OA), Semantic Scholar (fallback). Law /
humanities papers without a free PDF land as metadata-only — that is expected and
honest, not a failure.

### Reversible tagging

Every agent-added item carries a namespaced `incoming/<project>-<YYYY-MM>` tag
(e.g. `incoming/tja-2026-06`). To **undo a whole import** in one operation, in
the Zotero UI select the tag in the tag selector → select all items → delete; or
via the API, list items by that tag and batch-delete. The tag is the single
handle for "remove this entire batch."

## Step 2 — Sync the full-text index (incremental, idempotent)

The vectorization pipeline syncs incrementally from its `last_version`
checkpoint. It does **not** re-index the whole library.

```bash
cd ~/src/zotmcp
export ZOTERO_API_KEY=...        # read scope is enough for the sync
export ZOTERO_LIBRARY_ID=...
# Pick up everything new since the last checkpoint:
uv run python scripts/run_vectorization.py run.limit=null
```

Idempotency / safety guarantees (see `conf/vectorize.yaml`):

- `pipeline.source.force_full_sync: false` — only items newer than the stored
  `last_version` checkpoint are fetched.
- `VectorStoreExistenceFilter` + `deduplication_strategy: record_id` — items
  already in ChromaDB are skipped before download/embedding. Re-running is safe
  and cheap; it will not duplicate chunks or corrupt the store.
- The checkpoint only advances for items that are actually processed.

Cost: ~$0.002 per **new** item (Gemini Flash citation + gemini-embedding-001).
A no-op re-run costs only Zotero API calls.

> Note: a newly uploaded PDF must finish Zotero's server-side text extraction
> before the sync can pull its text. This is usually quick but is not instant;
> if a just-added item returns no full text, re-run the sync (it is idempotent).

## Step 3 — Verify it is full-text searchable

After the sync advances:

```text
get_item("<item_key>")          # returns full-text chunks from ChromaDB
search("<a distinctive phrase from the paper body>")   # semantic full-text query
```

A successful end-to-end run: `get_item` returns chunk text (not an error) and a
semantic `search` for a phrase that only appears in the body returns the new
item. If `get_item` errors with zero full-text bytes, the item never got a
stored, text-extracted PDF — go back to Step 1 and confirm `pdf_attachment` was
`"stored"`.

## Troubleshooting

- **`pdf_attachment: "linked"` unexpectedly** — the URL returned an HTML landing
  page rather than a PDF, or the download failed. The stored path verifies the
  `%PDF` magic bytes and refuses non-PDFs, falling back to a link. Find a direct
  PDF URL and call `import_attachment`.
- **Write returns 403** — see PKB `mem-bc700036`: needs (1) `ZOTERO_API_KEY` in
  the container env, (2) **write** scope on the key, (3) `ZOTERO_LIBRARY_TYPE`
  matching the library (group id 2281727 → `group`).
- **Item visible in metadata search but not full-text** — it has no stored PDF,
  or the sync has not been run since it was added.
