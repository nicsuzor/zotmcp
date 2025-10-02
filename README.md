# ZotMCP

MCP server for semantic search and literature review across a shared Zotero academic library.

## Features

- **Semantic Search** - Vector-based search across library items
- **Citation Retrieval** - Get properly formatted academic citations
- **Similar Items** - Find related works by similarity
- **Author Search** - Find all works by specific authors
- **7 Specialized Tools** - Search, retrieve, and analyze academic literature

## Quick Start

### Option A: Docker (Recommended for Distribution)

```bash
# 1. Pull the image
docker pull us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest

# 2. Configure your MCP client (see examples/claude_desktop_config_docker.json)

# 3. Restart your MCP client - done!
```

See [DOCKER.md](DOCKER.md) for full Docker deployment guide.

### Option B: Local Development

```bash
# 1. Install dependencies
uv sync

# 2. Download Zotero library database
./scripts/package_for_distribution.sh download

# 3. Test the server
python src/main.py
```

Then configure your MCP client (see below).

## MCP Client Configuration

### Docker (Recommended)

```json
{
  "mcpServers": {
    "zotero": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest"]
    }
  }
}
```

### Local Development

```json
{
  "mcpServers": {
    "zotero": {
      "command": "uv",
      "args": ["--directory", "/FULL/PATH/TO/zotmcp", "run", "python", "-m", "src.main"]
    }
  }
}
```

**Config locations:**
- Claude Desktop: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows)
- Claude Code: Use `/mcp` command
- See `examples/` for more templates

## Available Tools

1. **`search`** - Semantic search across library (primary tool)
2. **`get_item`** - Retrieve full text and metadata by Zotero key
3. **`get_similar_items`** - Find works similar to a given item
4. **`search_by_author`** - Find all works by an author
5. **`get_collection_info`** - Library statistics and metadata
6. **`assisted_search`** - LLM-assisted literature review (experimental)

## Example Queries

```
Search for papers about applying human rights standards to tech companies and social media governance
Find items by Ariadna Matamoros-Fernandez
What do transparency reports do?
Get similar items to zotero:ABC123
What's in the library collection?
```

## Project Structure

```
zotmcp/
├── src/main.py         # MCP server with 7 tools
├── src/models.py       # Pydantic models (ZoteroReference, ResearchResult)
├── conf/zotero.yaml    # Configuration
├── .cache/             # ChromaDB database (downloaded)
└── examples/           # MCP client configs
```

## Docker Deployment

### Building the Image

```bash
# Build locally
cd containers/deploy
./build.sh

# Build and push to registry
./build.sh --push
```

### Testing the Image

```bash
# Test in HTTP mode
docker run --rm -e MODE=http -p 8024:8024 us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest

# Test tools
curl http://localhost:8024/tools/get_collection_info
```

### Distribution

The Docker image includes:
- ✅ All dependencies (FastMCP, ChromaDB, Pydantic)
- ✅ ChromaDB vectors (baked in, ~3GB)
- ✅ No local Python setup required

Colleagues just need to:
1. Install Docker Desktop
2. Pull image: `docker pull us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest`
3. Configure MCP client (see above)
4. Restart client

## Troubleshooting

**Docker: "Cannot connect to daemon"**: Start Docker Desktop
**Docker: "Image not found"**: Authenticate with `gcloud auth configure-docker us-central1-docker.pkg.dev`
**Local: ChromaDB not found**: Run `./scripts/package_for_distribution.sh download`
**Local: Module errors**: Run `uv sync`
**MCP connection fails**: Check path in config (or use Docker deployment)


## Architecture

ZotMCP is an MCP (Model Context Protocol) server that provides semantic search and literature review capabilities for a shared Zotero academic library. It mirrors the architecture of the OSB ChatMCP project but is tailored for academic research workflows.


### MCP Server (`src/main.py`)

Provides 7 tools:

1. **search** - Primary semantic search across library
2. **get_item** - Retrieve full text by Zotero key
3. **get_similar_items** - Find related works
4. **search_by_author** - Author-based search
5. **get_collection_info** - Library statistics
6. **assisted_search** - LLM-assisted synthesis (experimental)

### Data Source

- **Zotero Library**: `prosocial` group library
- **ChromaDB Collection**: `prosocial_zot`
- **Embedding Model**: Google gemini-embedding-001 (3072 dimensions)
- **DB Location**: `gs://prosocial-dev/data/zotero-prosocial-fulltext/files`

The ChromaDB is created by the Buttermilk vectorization pipeline (see `projects/buttermilk`).

- Full text sourced from Zotero group first
- Where full text is not available, we extract full text from source PDF
- Each source is chunked using a semantic splitter into approximately 1000 tokens, with overlap of 250 tokens.
- Citations are generated by a LLM based on the first page of full text in the format: `Authors (Year). Title. Outlet`

### Data Models (`src/models.py`)

- **ZoteroReference** - Academic citation with DOI/URI
- **ResearchResult** - Synthesized response with literature list

### Templates (`templates/`)

- `rag.jinja2` - Research synthesis with citations
- `ra.jinja2` - Simple research assistant

### Metadata Handling

Zotero items have rich metadata. We extract:

**Bibliographic Fields:**

- creators (authors)
- title
- date/year
- publicationTitle (journal)
- publisher
- DOI
- url
- itemType
- abstractNote

**Technical Fields:**

- item_key (Zotero identifier)
- document_id
- chunk_index
- embedding_model

### Future Enhancements

1. **LLM Integration** - Use templates for synthesis
2. **Advanced Filters** - Filter by date range, item type, tags
3. **Citation Export** - Export results in BibTeX/RIS format
4. **Annotation Search** - Search across Zotero annotations
5. **Collection Browsing** - Browse by Zotero collections/tags


### Known Limitations

1. **Author search** is currently inefficient (scans all metadata)
   - Future: Create author index or use metadata filters
2. **assisted_search** doesn't actually use LLM yet
   - Currently just returns structured references
   - Future: Integrate with Buttermilk's RAG agent
3. **No tag/collection browsing** yet
4. **ChromaDB size** (~2-3GB for full library)
   - May be slow to download on poor connections
   - Consider compressed/chunked distribution

### Testing Checklist

Before distribution:

- [ ] Test `search` with various queries
- [ ] Test `get_item` with valid Zotero key
- [ ] Test `get_similar_items` functionality
- [ ] Test `search_by_author` with known authors
- [ ] Test `get_collection_info` returns correct stats
- [ ] Verify ChromaDB download works
- [ ] Verify MCP client configs work (Claude Desktop, Code, Gemini)
- [ ] Check error handling for missing ChromaDB
- [ ] Verify citation formatting is correct

## References

- **Related Project**: `projects/osbchatmcp` (template for this project)
- **Data Pipeline**: `projects/buttermilk/buttermilk/conf/flows/zot.yaml`
- **RAG Agent**: `projects/buttermilk/buttermilk/agents/rag/rag_zotero.py`
- **Storage Config**: `projects/buttermilk/buttermilk/conf/storage/zot.yaml`
