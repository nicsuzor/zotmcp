# Available Documentation

- **`README.md`**: Project overview — MCP server for semantic search and literature review over a shared Zotero library; features, tools, setup
- **`CLAUDE.md`**: Repo entry point — imports `.agents/CORE.md`
- **`.agents/CORE.md`**: Developer & agent reference — path discovery, fail-fast/HALT rules, architecture, MCP tool catalogue, setup, dev/testing workflow, corruption-recovery workflow
- **`src/zotmcp/`**: Main application code — MCP server definitions and processing modules
- **`src/zotmcp/conf/`**: Hierarchical YAML configuration (`mcp.yaml`, `zotero.yaml`, `vectorize.yaml`, `reprocess.yaml`)
- **`src/tests/`**: pytest suite (TDD, live data/APIs, no mocks)
- **`scripts/`**: Operations/maintenance utilities (`build.sh`, `process_single_doc.py`, `remove_corrupt_docs.py`, `clear_caches.py`)
- **`scripts/README.md`**: Scripts documentation
- **`deploy/`**: Docker deployment files (`Dockerfile`, `entrypoint.sh`)
- **`docs/`**: API and process documentation (e.g. `lib/openalex-api.md`)
