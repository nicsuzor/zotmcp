from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Callable
import pytest

from fastmcp import Client, FastMCP
from main import (
    mcp as local_mcp,
)  # ensure src/ is on PYTHONPATH or use your package import


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
def mcp_docker_cfg():
    """MCP configuration for connecting to the Docker container."""
    gcloud_config = str(Path.home() / ".config" / "gcloud")
    return {
        "mcpServers": {
            "zotmcp": {
                "command": "docker",
                "args": [
                    "run",
                    "-i",
                    "--rm",
                    "-v",
                    f"{gcloud_config}:/root/.config/gcloud:ro",
                    "us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest",
                ],
            }
        }
    }


@pytest.fixture(scope="session")
def mcp_server_local() -> FastMCP[Any]:
    # If you need buttermilk init side-effects, do them here (sync or async as needed)
    # from buttermilk import init
    # conf_dir = str(Path(__file__).parent.parent.parent / "conf")
    # init(config_dir=conf_dir, config_name="zotero", job="testing")
    return local_mcp


# @pytest.fixture(scope="session")
# def mcp_server_docker(mcp_docker_cfg):
#     # Name must match the key in mcpServers
#     return FastMCP.as_proxy(mcp_docker_cfg, name="zotmcp")


@pytest.fixture(
    scope="session",
    params=[
        pytest.param("local", id="local-server"),
        pytest.param("docker", marks=pytest.mark.slow, id="docker-e2e"),
    ],
)
def mcp_server(request, mcp_server_local, mcp_docker_cfg):
    """Parametrized fixture that runs tests against both local and Docker servers.

    - local: runs with in-process server (fast)
    - docker: runs with Docker container (slow, only when -m slow is used)
    """
    if request.param == "local":
        return mcp_server_local
    else:
        return mcp_docker_cfg
