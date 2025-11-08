from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any
import pytest

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
def docker_http_server():
    """Session-scoped Docker container running in HTTP mode.

    Starts the container once, waits for it to be ready (90s for ChromaDB init),
    and keeps it running for all tests. This avoids the 60+ second ChromaDB
    initialization for each test.
    """
    import subprocess
    import time
    import requests
    from pathlib import Path

    # Auto-detect container runtime
    container_cmd = None
    candidates = [
        "docker",
        "/usr/bin/docker",
        "/usr/local/bin/docker",
        "podman",
        "/usr/bin/podman",
        "/usr/local/bin/podman",
    ]

    for cmd in candidates:
        try:
            result = subprocess.run([cmd, "--version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                container_cmd = cmd
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    if not container_cmd:
        raise RuntimeError("Neither 'docker' nor 'podman' command found or working")

    gcloud_config = Path.home() / ".config" / "gcloud"

    # Build volume mounts - only mount gcloud config if it exists
    volume_mounts = []
    if gcloud_config.exists():
        volume_mounts.extend(["-v", f"{gcloud_config}:/root/.config/gcloud:ro"])
    else:
        logger.warning(
            "No gcloud config found - container will run without GCP credentials"
        )

    # Start container in HTTP mode on port 8024
    logger.info("Starting Docker container in HTTP mode...")

    cmd_args = [
        container_cmd,
        "run",
        "--rm",
        "--network=host",
        *volume_mounts,
        "-e",
        "MODE=http",  # For entrypoint.sh
        "-e",
        "MCP_TRANSPORT=http",  # For main.py
        "-e",
        "MCP_HTTP_HOST=0.0.0.0",
        "-e",
        "MCP_HTTP_PORT=8024",
        "us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest",
    ]

    process = subprocess.Popen(
        cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Combine stderr into stdout for easier logging
    )

    # Wait up to 90 seconds for server to be ready
    logger.info(
        "Waiting for Docker container to initialize (up to 90s for ChromaDB)..."
    )
    server_url = "http://localhost:8024"
    max_wait = 90
    start_time = time.time()

    while time.time() - start_time < max_wait:
        # Check if process has terminated
        if process.poll() is not None:
            # Process died, get output
            stdout, _ = process.communicate()
            logger.error(f"Docker container exited unexpectedly:\n{stdout.decode()}")
            raise RuntimeError("Docker container exited unexpectedly")

        try:
            # Try to connect to the SSE endpoint which FastMCP streamable-http uses
            response = requests.get(f"{server_url}/sse", timeout=2, stream=True)
            # If we get a response (even if it's waiting for SSE), server is up
            if response.status_code in (
                200,
                400,
                404,
            ):  # Any response means server is running
                logger.info(
                    f"Docker container ready after {time.time() - start_time:.1f}s"
                )
                break
        except (requests.ConnectionError, requests.Timeout):
            time.sleep(2)
    else:
        # Timeout - capture output before killing
        process.terminate()
        try:
            stdout, _ = process.communicate(timeout=5)
            logger.error(f"Docker container timeout. Last output:\n{stdout.decode()}")
        except subprocess.TimeoutExpired:
            process.kill()
        raise RuntimeError(f"Docker container failed to start within {max_wait}s")

    yield server_url

    # Cleanup
    logger.info("Stopping Docker container...")
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    logger.info("Docker container stopped")


@asynccontextmanager
async def test_lifespan_manager(server: FastMCP):
    """Test-specific lifespan that initializes buttermilk with db=dev."""
    # Load zotero config with dev database override for tests
    str(Path(__file__).parent.parent.parent / "conf")

    main.search_tool = main.get_search_tool()
    await main.search_tool.ensure_cache_initialized()

    logger.info("Buttermilk initialized for tests")

    yield

    logger.info("Shutting down ZotMCP test server")


@pytest.fixture(scope="session")
async def bm_vectorize():
    """Get Zotero configuration."""

    conf_dir = str(Path(__file__).parent.parent.parent / "conf")
    bm = await init_async(config_dir=conf_dir, config_name="vectorize", overrides=[])
    yield bm

    await bm.graceful_shutdown()


@pytest.fixture(scope="session")
async def bm_dev():
    """Buttermilk instance with dev database for tests.

    Uses mcp.yaml config which has minimal dependencies (no BigQuery)
    to allow tests to run without GCP credentials.
    """
    conf_dir = str(Path(__file__).parent.parent.parent / "conf")
    bm = await init_async(config_dir=conf_dir, config_name="mcp", overrides=["db=dev"])
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
def mcp_server_docker(docker_http_server):
    """Docker MCP server as HTTP endpoint.

    This returns the HTTP server URL that FastMCP Client can connect to.
    """
    # FastMCP streamable-http mode uses /mcp endpoint
    return f"{docker_http_server}/mcp"


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
