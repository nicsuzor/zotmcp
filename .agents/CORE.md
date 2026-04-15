# zotmcp — Developer Reference

## Overview

Python MCP server for semantic search of a Zotero academic library. Uses FastMCP, Buttermilk for embeddings, and OpenAlex for citation data.

## MCP Tools

- `search` — semantic search across Zotero library
- `search_by_citation_key` — find by citation key
- `search_by_doi` — find by DOI
- `search_library_by_author` — find by author name
- `get_item` — get full Zotero item details
- `get_similar_items` — find related items by embedding similarity
- `get_version_info` — server version info
- `get_collection_info` — collection statistics
- `search_papers` — search OpenAlex papers
- `get_paper_details` — OpenAlex paper details
- `get_paper_citations` — citation list from OpenAlex
- `get_referenced_works` — references from OpenAlex
- `search_openalex_author` — author search via OpenAlex

## Structure

```
src/zotmcp/      — main package
src/tests/       — tests
scripts/build.sh — Docker build
```

## Development

- `uv run ...` for all Python commands
- `uv run pytest` for tests
- Docker: `bash scripts/build.sh` (don't push by default)
- OpenAlex API docs: `docs/lib/openalex-api.md`
- Testing: TDD, no mocks — live data and live APIs only
