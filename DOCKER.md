# Docker Deployment for ZotMCP

ZotMCP can be deployed as a Docker container, making it easy to distribute to colleagues without requiring local Python setup.

## Quick Start (Docker)

### 1. Pull the image

```bash
docker pull us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest
```

### 2. Configure MCP client

**Claude Desktop** - Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "zotero": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest"
      ]
    }
  }
}
```

**Claude Code** - Use `/mcp` command and add:

```json
{
  "zotero": {
    "command": "docker",
    "args": [
      "run",
      "--rm",
      "-i",
      "us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest"
    ]
  }
}
```

### 3. Restart your MCP client

That's it! The ChromaDB is baked into the image, so no additional downloads needed.

## Architecture

The Docker image:
- **Base**: Buttermilk dev container (`us-central1-docker.pkg.dev/prosocial-443205/reg/buttermilk:dev`)
- **Dependencies**: FastMCP, ChromaDB, Pydantic (installed via uv)
- **ChromaDB**: Baked into image at `.cache/zotero-prosocial-fulltext/files`
- **Size**: ~3-4GB (includes ChromaDB vectors)

## Building the Image

### Local build

```bash
cd containers/deploy
./build.sh
```

### Build and push to registry

```bash
./build.sh --push
```

### Custom tag

```bash
TAG=v0.2.0 ./build.sh --push
```

## Running Modes

### stdio mode (default - for MCP)

```bash
docker run --rm -i us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest
```

### HTTP mode (for testing)

```bash
docker run --rm -e MODE=http -p 8024:8024 us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest
```

Then test:
```bash
curl http://localhost:8024/tools/get_collection_info
```

### With custom ChromaDB (advanced)

To use a different ChromaDB than the baked-in one:

```bash
docker run --rm -i \
  -v /path/to/chromadb:/app/zotmcp/.cache/zotero-prosocial-fulltext/files:ro \
  us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest
```

## Distribution to Colleagues

### Option 1: Use Registry (Recommended)

Share these instructions:

1. Install Docker Desktop
2. Pull image: `docker pull us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest`
3. Configure MCP client (see examples above)
4. Restart client

### Option 2: Export Image File

For colleagues without registry access:

```bash
# Export image
docker save us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest | gzip > zotmcp-docker.tar.gz

# Share zotmcp-docker.tar.gz

# They load it:
docker load < zotmcp-docker.tar.gz
```

## Updating the Image

When the Zotero library is updated:

1. **Update ChromaDB** (via Buttermilk pipeline)
2. **Download to project**: `./scripts/package_for_distribution.sh download`
3. **Rebuild image**: `./containers/deploy/build.sh --push`
4. **Notify users**: They pull the new image with `docker pull ...`

## Dockerfile Structure

```dockerfile
# Stage 1: Base (Buttermilk container with heavy deps)
FROM us-central1-docker.pkg.dev/prosocial-443205/reg/buttermilk:dev

# Stage 2: Builder (Install ZotMCP dependencies)
# - Extracts deps from pyproject.toml
# - Creates venv with uv

# Stage 3: Final (Runtime)
# - Copies venv and app code
# - Includes ChromaDB at .cache/
# - Runs FastMCP in stdio mode
```

## Troubleshooting

**"Cannot connect to Docker daemon"**
→ Start Docker Desktop

**"Image not found"**
→ Authenticate: `gcloud auth configure-docker us-central1-docker.pkg.dev`

**"ChromaDB collection not found"**
→ The image should include ChromaDB. Rebuild with: `./build.sh`

**Performance issues**
→ Increase Docker memory limit in Docker Desktop settings (recommend 4GB+)

## Registry Access

The image is hosted in Google Artifact Registry:
- **Registry**: `us-central1-docker.pkg.dev`
- **Project**: `prosocial-443205`
- **Repository**: `reg`
- **Image**: `zotmcp`

To grant access to colleagues:
```bash
gcloud artifacts repositories add-iam-policy-binding reg \
  --location=us-central1 \
  --member=user:colleague@example.com \
  --role=roles/artifactregistry.reader
```

## Advantages of Docker Deployment

✅ **No Python setup** - Everything bundled
✅ **No ChromaDB download** - Included in image
✅ **Consistent environment** - Same for everyone
✅ **Easy updates** - Just pull new image
✅ **Works anywhere** - macOS, Windows, Linux

## Comparison: Docker vs Local

| Feature | Docker | Local Install |
|---------|--------|---------------|
| **Setup** | Pull image (~3GB) | Install Python + deps + ChromaDB (~2.5GB) |
| **Dependencies** | None (bundled) | Python 3.10+, uv |
| **ChromaDB** | Included | Separate download |
| **Updates** | `docker pull` | `git pull` + download |
| **Portability** | High | Medium |
| **Performance** | Good (~5-10% slower) | Native |
| **Size** | ~3-4GB | ~2.5GB |
