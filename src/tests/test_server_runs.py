from fastmcp import Client
import pytest
from pathlib import Path
import os
import anyio

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
    mcp_docker_config, conf_timeout_startup, conf_timeout_call, conf_loglevel
):
    # The client will infer to create a FastMCPProxy for this config
    try:
        with anyio.fail_after(conf_timeout_startup):
            async with Client(mcp_docker_config) as client:
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
    except TimeoutError:
        pytest.fail(
            f"Server failed to start within {conf_timeout_startup}s. "
            "Run with: pytest -s -vv -k test_docker_server to see client logs, "
            "or run the image manually to inspect startup output."
        )

    assert "collection_name" in result.data
    assert result.data["total_chunks"] > 0
