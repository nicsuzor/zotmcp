from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any
import pytest
from pytest_lazy_fixtures import lf

from contextlib import asynccontextmanager
from fastmcp import FastMCP
from buttermilk import init_async, logger
import main


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
    """MCP configuration for connecting to the Docker container.

    Auto-detects whether to use 'docker' or 'podman' based on what's available.
    """
    import subprocess

    # Auto-detect container runtime by trying common locations
    container_cmd = None
    candidates = [
        "docker",  # Try PATH first
        "/usr/bin/docker",
        "/usr/local/bin/docker",
        "podman",
        "/usr/bin/podman",
        "/usr/local/bin/podman",
    ]

    for cmd in candidates:
        try:
            # Try to run --version to check if command exists and works
            result = subprocess.run(
                [cmd, "--version"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                container_cmd = cmd
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    if not container_cmd:
        raise RuntimeError(
            "Neither 'docker' nor 'podman' command found or working. "
            "Tried: docker, /usr/bin/docker, /usr/local/bin/docker, "
            "podman, /usr/bin/podman, /usr/local/bin/podman"
        )

    gcloud_config = str(Path.home() / ".config" / "gcloud")
    return {
        "mcpServers": {
            "zotmcp": {
                "command": container_cmd,
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
async def mcp_client_docker_session(mcp_docker_cfg):
    """Session-scoped Docker client - container stays running for all docker tests.

    This ensures the Docker container is started ONCE per test session and reused
    across all tests, avoiding the 60+ second ChromaDB initialization for each test.
    """
    from fastmcp import Client

    async with Client(mcp_docker_cfg) as client:
        # Wait for basic server responsiveness (not ChromaDB)
        # This ensures the server is ready before tests start
        await client.list_tools()
        logger.info("Docker container started and ready for tests")
        yield client
        logger.info("Docker container stopping at session end")


@asynccontextmanager
async def test_lifespan_manager(server: FastMCP):
    """Test-specific lifespan that initializes buttermilk with db=dev."""
    # Load zotero config with dev database override for tests
    conf_dir = str(Path(__file__).parent.parent.parent / "conf")

    main.search_tool = main.get_search_tool()
    await main.search_tool.ensure_cache_initialized()

    logger.info("Buttermilk initialized for tests")

    yield

    logger.info("Shutting down ZotMCP test server")

@pytest.fixture(scope="session")
async def bm_vectorize():
    """Get Zotero configuration."""
    from buttermilk import init_async

    conf_dir = str(Path(__file__).parent.parent.parent / "conf")
    bm = await init_async(config_dir=conf_dir, config_name="vectorize", overrides=[])
    yield bm

    await bm.graceful_shutdown()



@pytest.fixture(scope="session")
async def bm_dev():
    """Buttermilk instance with dev database for tests."""
    from buttermilk import init_async

    conf_dir = str(Path(__file__).parent.parent.parent / "conf")
    bm = await init_async(
        config_dir=conf_dir, config_name="zotero", overrides=["db=dev"]
    )
    yield bm
    await bm.graceful_shutdown()

@pytest.fixture(scope="session")
def mcp_server_local(bm_dev) -> FastMCP[Any]:
    main.bm = bm_dev
    main.conf = bm_dev.cfg
    # Use the main MCP instance but replace its lifespan manager for tests
    # This ensures all the tools/prompts from main.py are available
    return main.mcp


@pytest.fixture(scope="function")
async def mcp_client_local_function(mcp_server_local):
    """Function-scoped client for local server tests.

    Each test gets a fresh connection to the in-process server.
    """
    from fastmcp import Client

    async with Client(mcp_server_local) as client:
        yield client


@pytest.fixture(scope="session")
def mcp_server_docker(mcp_docker_cfg):
    """Docker MCP server as a proxy - only initialized when tests request it."""
    # Name must match the key in mcpServers
    return FastMCP.as_proxy(mcp_docker_cfg, name="zotmcp")


@pytest.fixture(
    scope="session",
    params=[
        pytest.param("local", id="local-server"),
        pytest.param("docker", marks=pytest.mark.slow, id="docker-e2e"),
    ],
)
def mcp_server(request, mcp_server_local, mcp_server_docker):
    """Parametrized fixture that returns FastMCP server for both local and Docker.

    - local: in-process server (fast, always available)
    - docker: Docker container server (slow, only when -m slow is used)

    Tests should create their own Client with:
        async with Client(mcp_server) as client:
            ...

    This pattern ensures:
    1. Docker fixture only initialized when actually requested
    2. Tests work with both server types identically
    3. No async generator hanging issues
    """
    if request.param == "local":
        return mcp_server_local
    else:
        return mcp_server_docker
