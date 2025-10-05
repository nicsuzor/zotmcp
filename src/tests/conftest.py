from __future__ import annotations

import inspect
from typing import Any
import pytest

from pathlib import Path

from fastmcp import Client, FastMCP
from main import mcp

# Ensure async tests get the anyio marker automatically,
# while sync tests run normally without any interference.
def pytest_collection_modifyitems(items):
    for item in items:
        # Check if the test function is async
        if inspect.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.anyio)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="session")
def mcp_server() -> FastMCP[Any]:
    from buttermilk import init

    # Load zotero config - use absolute path from project root
    conf_dir = str(Path(__file__).parent.parent.parent / "conf")
    bm = init(config_dir=conf_dir, config_name="zotero", job="testing")
    return mcp


@pytest.fixture(scope="session")
def mcp_docker_config():
    """MCP configuration for connecting to the Docker container."""
    return {
        "mcpServers": {
            "zotmcp": {
                "command": "docker",
                "args": [
                    "run",
                    "-i",
                    "--rm",
                    "us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest",
                ],
            }
        }
    }
