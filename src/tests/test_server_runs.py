from fastmcp import Client
import pytest
from pathlib import Path
import os
import anyio
import time

pytestmark = [pytest.mark.anyio, pytest.mark.slow]


# Allow tweaking via env for CI/local runs
@pytest.fixture
def conf_timeout_startup() -> int:
    startup_timeout_s = int(os.getenv("MCP_STARTUP_TIMEOUT", "45"))
    return startup_timeout_s


@pytest.fixture
def conf_timeout_call() -> int:
    call_timeout_s = int(os.getenv("MCP_CALL_TIMEOUT", "20"))
    return call_timeout_s


@pytest.fixture
def conf_loglevel() -> str:
    server_log_level = os.getenv("MCP_SERVER_LOG_LEVEL", "DEBUG")
    return server_log_level


# Test that our complete docker image runs and is accessible
async def test_docker_server(
    mcp_client_docker_session, conf_timeout_call
):
    # Use the session-scoped docker client (container already started)
    client = mcp_client_docker_session

    # Check version info first
    try:
        with anyio.fail_after(conf_timeout_call):
            version_result = await client.call_tool("get_version_info")
    except TimeoutError:
        pytest.fail(
            f"Timed out waiting for get_version_info tool after {conf_timeout_call}s. "
        )

    # Check buttermilk version (should be from git)
    buttermilk_version = version_result.data.get("buttermilk", "")
    assert buttermilk_version != "not installed", "buttermilk should be installed"
    # Git installs often have version like "0.5.1+g2e70442" where g<commit> is the git hash
    # Just verify it's present and has some version info
    assert len(buttermilk_version) > 0, f"buttermilk version should not be empty: {buttermilk_version}"

    # Now test actual functionality
    try:
        with anyio.fail_after(conf_timeout_call):
            result = await client.call_tool("get_collection_info")
    except TimeoutError:
        pytest.fail(
            f"Timed out waiting for get_collection_info tool after {conf_timeout_call}s. "
        )

    assert "collection_name" in result.data
    assert result.data["total_chunks"] > 0


async def test_handshake_completes_within_20_seconds(mcp_docker_cfg):
    """Verify MCP server cold-start handshake completes within 20 seconds.

    This test creates a fresh Docker container and measures time to complete
    the initial MCP handshake (initialize + list_tools). The server should
    respond quickly even while ChromaDB initializes in the background.

    Requirement: Server must be responsive within 20s for MCP clients with
    30s default timeouts.
    """
    from fastmcp import Client

    start_time = time.perf_counter()

    # Create a fresh client connection (cold start)
    async with Client(mcp_docker_cfg) as client:
        # The Client context manager handles initialize() automatically
        # Now make a simple call to verify responsiveness
        await client.list_tools()

        elapsed = time.perf_counter() - start_time

        # Assert handshake completed within 20 seconds
        assert elapsed < 20.0, (
            f"Cold-start handshake took {elapsed:.2f}s, expected < 20s. "
            f"This will cause timeouts with MCP clients (typically 30s default). "
            f"Server must be responsive before ChromaDB finishes initializing."
        )
