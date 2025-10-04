# ZotMCP Testing Guide

## Overview

This project includes comprehensive end-to-end integration tests for the packaged Docker container.

## Test Suite

### Integration Tests (`src/tests/test_integration.py`)

Comprehensive tests that verify the Docker container works end-to-end:

**Test Categories:**

1. **Server Startup** - Verifies the container starts and initializes correctly
   - Connection establishment
   - Tool discovery

2. **Collection Info** - Tests database metadata retrieval
   - Collection statistics
   - Embedding configuration

3. **Search** - Tests the vector search functionality
   - Basic search
   - Result structure validation
   - Parameter handling (n_results, filter_type)
   - Empty query handling

4. **Similar Items** - Tests similarity search
   - Finding related items
   - Reference item exclusion

5. **Author Search** - Tests author-based search
   - Finding items by author name

6. **Error Handling** - Tests edge cases and invalid inputs
   - Parameter validation
   - Graceful error responses

7. **Assisted Search** (marked `@pytest.mark.skip`)
   - Currently returns structured data without LLM integration
   - Skipped until LLM synthesis is implemented

## Running Tests

### Quick Test (local server)

```bash
uv run pytest src/tests/test_integration.py -v
```

### Docker Container Test

```bash
uv run pytest src/tests/test_server_runs.py -v
```

### All Tests

```bash
uv run pytest src/tests/ -v
```

### Single Test

```bash
uv run pytest src/tests/test_integration.py::TestSearch::test_search_returns_results -v
```

## Test Configuration

Configuration is in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["src/tests"]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
]
timeout = 300  # 5 minute timeout for integration tests
addopts = "-v --tb=short"
```

## Prerequisites

### Docker Image

Build the latest Docker image:

```bash
cd /path/to/zotmcp
./deploy/build.sh
```

### ChromaDB

Ensure ChromaDB is available:

```bash
./scripts/package_for_distribution.sh download
```

## Current Status

**Container Build**: ✅ Working
- Successfully builds with Python 3.12-slim base
- No buttermilk dependency for runtime
- Uses uv for dependency management

**Test Suite**: ✅ Working
- Tests are properly structured and comprehensive
- Server initializes successfully
- All core tools tested

## Troubleshooting

### Test Timeouts

If tests timeout during connection:

1. **Check Docker image**: `docker images | grep zotmcp`
2. **Test container manually**:
   ```bash
   docker run -it --rm \
     us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest
   ```

### ChromaDB Issues

If tests fail due to missing ChromaDB:

```bash
./scripts/package_for_distribution.sh download
```

Then rebuild the Docker image:

```bash
./deploy/build.sh
```

## Test Development

### Adding New Tests

1. Add test methods to appropriate class in `test_integration.py`
2. Use the `mcp_client` fixture for MCP connections
3. Mark slow tests with `@pytest.mark.slow`

Example:

```python
class TestMyFeature:
    async def test_my_feature(self, mcp_server):
        async with Client(mcp_server) as mcp_client:
            result = await mcp_client.call_tool("my_tool", param="value")
            assert result.data["status"] == "success"
```

### Test Fixtures

- `mcp_server`: Returns local FastMCP server instance
- `mcp_docker_config`: Returns Docker container configuration
- `anyio_backend`: Configures asyncio backend for async tests

## CI/CD Integration

To integrate with CI/CD:

1. Ensure Docker is available
2. Run: `uv run pytest src/tests/test_integration.py -v`

Example GitHub Actions:

```yaml
- name: Run integration tests
  run: |
    uv run pytest src/tests/test_integration.py -v
```
