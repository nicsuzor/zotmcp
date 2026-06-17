# ZotMCP — Developer & Agent Reference

## Path Discovery

To discover project locations, read `.agents/INDEX.md` in the relevant repo. A missing or stale index is NOT a hard HALT — if you are already inside a mounted worktree, fall back to the repo's README/CLAUDE.md and top-level layout, and refresh the index where you can.

## Fail-Fast / Halt Rule (ENFORCED)

If you cannot do what was asked, **STOP and report** — do NOT search broadly, do NOT invent workarounds.

- **Missing Paths**: If a documented path does not exist, HALT.
- **No Broad Grep**: Never grep `$HOME` or `/` to find source repos or documents. Use `.agents/INDEX.md` for discovery.
- **Tool Failures**: If a tool doesn't work as documented, report the failure — do not invent alternatives.
- **Ambiguity**: If instructions conflict or are ambiguous, ask for clarification.

## Overview
ZotMCP is an MCP (Model Context Protocol) server providing semantic search and literature review capabilities for a shared Zotero academic library ("prosocial" group library) combined with discovery features through the OpenAlex API (240M+ papers).

The system uses:
- **FastMCP** for the server framework.
- **Buttermilk** for the vectorization pipeline.
- **Google gemini-embedding-001** (3072 dimensions) for semantic embeddings.
- **ChromaDB** (`prosocial_zot` collection) for storing vectorized chunks.
- **OpenAlex** for fetching citation data, references, and external works.

## Core Setup & Requirements
- **Python**: `>=3.12, <3.14`. Dependency management is handled exclusively by **`uv`**.
- **System Dependencies**: The vectorization pipeline requires `poppler-utils` (e.g., `sudo apt-get install poppler-utils`) for PDF text extraction.
- **Authentication**: Requires Google credentials (`gcloud auth application-default login`) for accessing Cloud resources (ChromaDB vectors).
- **Vector DB Initialization**: Download existing vectors via `uvx --from git+https://github.com/nicsuzor/zotmcp.git zotmcp-download` (~8GB).

## Available MCP Tools
Agents interacting with this server have access to 13 specialized tools:

### Zotero Library Search & Retrieval (Internal)
- `search`: Semantic search across the internal Zotero library (primary tool).
- `search_by_citation_key`: Find specific library item by its citation key.
- `search_by_doi`: Find library item by DOI.
- `search_library_by_author`: Find all works by a specific author in the Zotero library.
- `get_item`: Retrieve full text and metadata by Zotero key.
- `get_similar_items`: Find related works within the library using embedding similarity.

### OpenAlex Discovery (External)
- `search_papers`: Search the OpenAlex database for papers beyond the internal library.
- `get_paper_details`: Get full metadata and details for a specific OpenAlex paper ID.
- `get_paper_citations`: Retrieve forward citations for a paper from OpenAlex.
- `get_referenced_works`: Retrieve backward references (works cited by) for a paper from OpenAlex.
- `search_openalex_author`: Discover papers by a specific author in OpenAlex.

### System & Server Info
- `get_collection_info`: Retrieve library statistics and metadata.
- `get_version_info`: Server version information.

## Repository Structure
- `src/zotmcp/`: Main application code, MCP server definitions, processing modules.
  - `conf/`: YAML configurations (`mcp.yaml`, `zotero.yaml`, `vectorize.yaml`, `reprocess.yaml`).
- `src/tests/`: Test suite utilizing `pytest`. Contains fixtures and test cases.
- `scripts/`: Utility scripts for operations and maintenance (e.g., `build.sh`, `process_single_doc.py`, `remove_corrupt_docs.py`, `clear_caches.py`).
- `deploy/`: Docker deployment files (`Dockerfile`, `entrypoint.sh`).
- `docs/`: API and process documentation (e.g., `lib/openalex-api.md`).

## Development & Testing Workflow
- **Commands**: Always use `uv run <command>` for Python execution.
- **Testing**: Run tests with `uv run pytest`. Testing methodology strictly follows TDD using **live data and live APIs only (no mocks)**.
- **Configuration**: Configuration uses hierarchical YAML via Buttermilk/Pydantic, located in `src/zotmcp/conf/`.
- **Docker**: Build via `bash scripts/build.sh`. The Docker image comes with `poppler-utils` pre-installed.

## Data Processing & Corruption Recovery Workflow
The ingestion pipeline automatically downloads PDFs from Zotero, extracts text, chunks it semantically (~1000 tokens with 250 overlap), and generates LLM-based citations.

When documents are corrupted, agents should follow the Reprocessing Workflow:
1. **Remove**: Clear corrupted document vectors from ChromaDB via `scripts/remove_corrupt_docs.py` (use `--execute` to apply).
2. **Clear Caches**: Remove associated cached PDFs and records using `scripts/clear_caches.py` (use `--execute`).
3. **Reprocess**: Process the documents through the complete pipeline with `scripts/process_single_doc.py <ZOTERO_ID>`.
4. **Quality Threshold**: Configurable in `conf/vectorize.yaml` (e.g., `corruption_threshold: 80.0`). Documents with >=80% corrupt chunks are discarded automatically.