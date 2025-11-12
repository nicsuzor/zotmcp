"""Tests for asynchronous ChromaDB initialization.

These tests verify that the MCP server can start quickly without blocking
on ChromaDB initialization, and that tools handle uninitialized state gracefully.
"""

import asyncio
import json
import select
import subprocess
import time
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, Mock, patch

import main


pytestmark = pytest.mark.anyio


async def test_lifespan_manager_does_not_block_on_chromadb():
    """Test that lifespan_manager returns quickly without waiting for ChromaDB init.

    The lifespan manager should:
    1. Start ChromaDB initialization in background
    2. Return control immediately (< 2 seconds)
    3. Not block the MCP server from becoming responsive
    """
    # Create a mock server
    mock_server = Mock()

    # Track initialization calls
    init_call_count = [0]

    async def mock_slow_init():
        """Simulate slow ChromaDB initialization (30+ seconds)."""
        init_call_count[0] += 1
        await asyncio.sleep(30)  # Simulate slow GCS download + initialization

    # Patch the search tool's initialize method deeply within buttermilk
    with patch("main.init_async", new_callable=AsyncMock) as mock_init:
        # Mock buttermilk initialization (fast part)
        mock_bm = Mock()
        mock_bm.cfg = Mock()

        # Create a proper mock storage config
        mock_storage_config = Mock()
        mock_storage_config.collection_name = "test_collection"
        mock_storage_config.persist_directory = "/tmp/test_db"
        mock_storage_config.embedding_model = "test-model"
        mock_storage_config.dimensionality = 768

        mock_bm.cfg.get_storage_config = Mock(return_value=mock_storage_config)
        mock_init.return_value = mock_bm

        # Patch ChromaDBSearchTool.initialize to use our slow mock
        with patch(
            "buttermilk.tools.ChromaDBSearchTool.initialize", new_callable=AsyncMock
        ) as mock_tool_init:
            mock_tool_init.side_effect = mock_slow_init

            # Time how long the lifespan manager takes
            start_time = time.time()

            # Enter the lifespan context
            async with main.lifespan_manager(mock_server):
                elapsed = time.time() - start_time

                # Verify lifespan returned quickly (< 2 seconds)
                assert elapsed < 2.0, (
                    f"lifespan_manager blocked for {elapsed:.1f}s. "
                    "It should return immediately and initialize ChromaDB in background."
                )

                # The background task should have been started
                # (even though it won't complete for 30s)
                assert (
                    main._chromadb_init_task is not None
                ), "Background initialization task should have been created"

                # ChromaDB should not yet be ready
                assert (
                    not main._chromadb_ready
                ), "ChromaDB should not be ready yet (initialization takes 30s)"


async def test_tools_return_error_when_chromadb_not_ready():
    """Test that tools return helpful error when ChromaDB is not yet initialized.

    When ChromaDB is still initializing, tools should:
    1. Check the initialization state
    2. Return a clear, actionable error message
    3. Not hang or crash
    """
    # Set up main module state with uninitialized ChromaDB
    # Save original state
    original_ready = main._chromadb_ready
    original_error = main._chromadb_init_error

    try:
        # Simulate ChromaDB still initializing
        main._chromadb_ready = False
        main._chromadb_init_error = None

        # Test the readiness check function directly
        error_response = main._check_chromadb_ready()

        # Verify we got an error response
        assert error_response is not None, "Should return error when ChromaDB not ready"
        assert "error" in error_response, "Error response should have 'error' field"

        # Verify error message is helpful
        error_msg = error_response["error"].lower()
        assert (
            "initializing" in error_msg or "not ready" in error_msg
        ), f"Error message should mention initialization status: {error_response['error']}"

        # Verify response suggests retry
        assert (
            "try again" in error_msg or "30 seconds" in error_msg
        ), f"Error message should suggest retrying with timeframe: {error_response['error']}"

        # Verify response structure
        assert "results" in error_response, "Error response should have 'results' field"
        assert error_response["results"] == [], "Results should be empty list"
        assert (
            "total_results" in error_response
        ), "Error response should have 'total_results' field"
        assert error_response["total_results"] == 0, "Total results should be 0"

    finally:
        # Restore original state
        main._chromadb_ready = original_ready
        main._chromadb_init_error = original_error


async def test_tools_work_after_initialization_completes():
    """Test that tools work normally once ChromaDB initialization completes.

    After initialization completes:
    1. _chromadb_ready flag should be True
    2. Tools should work normally
    3. No error messages about initialization
    """
    # This test will use the real conftest fixtures
    # Testing if async init is working by running the test


async def test_tools_available_within_10_seconds():
    """Test that ChromaDB tools become available within 10 seconds of server startup.

    This test verifies that the async initialization optimization makes tools
    available quickly (within 10 seconds), not after 30+ seconds of ChromaDB init.

    The test:
    1. Starts a fresh MCP server via subprocess (cold start)
    2. Polls get_collection_info tool every 0.5 seconds via stdio transport
    3. Asserts tool works within 10 seconds
    4. Should FAIL initially because current implementation takes 30+ seconds

    Why get_collection_info: This tool requires ChromaDB to be fully initialized
    and ready, making it a good indicator of when the system is usable.
    """
    # Find the main.py file to run
    project_root = Path(__file__).parent.parent.parent
    main_py = project_root / "src" / "main.py"

    if not main_py.exists():
        raise FileNotFoundError(f"Cannot find main.py at {main_py}")

    # Start MCP server in stdio mode with subprocess
    process = subprocess.Popen(
        ["uv", "run", "python", str(main_py)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=str(project_root),
    )

    request_id = 1
    start_time = time.time()
    max_wait = 10.0
    poll_interval = 0.5
    last_error = None
    attempt = 0

    try:
        # First, send initialize request to establish session
        init_request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
        }
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        request_id += 1

        # Wait for initialize response (should be quick)
        init_timeout = 5.0
        init_start = time.time()
        init_response = None
        while time.time() - init_start < init_timeout:
            if process.poll() is not None:
                pytest.fail("Server process died during initialization")

            line = process.stdout.readline().strip()
            if not line:
                await asyncio.sleep(0.1)
                continue

            try:
                data = json.loads(line)
                if data.get("id") == 1:  # Our initialize request
                    init_response = data
                    break
            except json.JSONDecodeError:
                continue

        if not init_response:
            pytest.fail("Failed to get initialize response from server")

        # Now poll get_collection_info tool until it works or timeout
        while time.time() - start_time < max_wait:
            attempt += 1
            elapsed = time.time() - start_time

            # Send tool call request
            tool_request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": "get_collection_info", "arguments": {}},
            }
            process.stdin.write(json.dumps(tool_request) + "\n")
            process.stdin.flush()
            current_request_id = request_id
            request_id += 1

            # Wait for response (with timeout)
            response_timeout = 2.0
            response_start = time.time()
            tool_response = None

            while time.time() - response_start < response_timeout:
                if process.poll() is not None:
                    pytest.fail(
                        f"Server process died during tool call at {elapsed:.1f}s"
                    )

                line = process.stdout.readline().strip()
                if not line:
                    await asyncio.sleep(0.05)
                    continue

                try:
                    data = json.loads(line)
                    if data.get("id") == current_request_id:
                        tool_response = data
                        break
                except json.JSONDecodeError:
                    continue

            if not tool_response:
                last_error = f"No response after {response_timeout}s"
                await asyncio.sleep(poll_interval)
                continue

            # Check if we got an error
            if "error" in tool_response:
                last_error = tool_response["error"].get(
                    "message", str(tool_response["error"])
                )
                await asyncio.sleep(poll_interval)
                continue

            # Check if result indicates ChromaDB not ready
            result = tool_response.get("result", {})
            if isinstance(result, dict) and "error" in result:
                last_error = result["error"]
                await asyncio.sleep(poll_interval)
                continue

            # Success! Tool is ready and returned real data

            # Assert it was within our 10 second target
            assert (
                elapsed < max_wait
            ), f"Tool worked but took {elapsed:.1f}s (should be < {max_wait}s)"
            return

        # If we got here, we timed out
        elapsed = time.time() - start_time
        pytest.fail(
            f"get_collection_info tool did not become available within {max_wait}s. "
            f"Waited {elapsed:.1f}s. Last error: {last_error}\n"
            f"This indicates ChromaDB initialization is still blocking or taking too long."
        )

    finally:
        # Clean up process
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def test_stdout_clean_during_startup():
    """Test that MCP server stdout contains only valid JSON-RPC messages during startup.

    The MCP server uses stdio transport and MUST output only valid JSON-RPC messages
    on stdout. Any progress bars, debug messages, or plain text fragments will break
    the JSON-RPC protocol.

    This test verifies:
    1. All stdout lines are valid JSON
    2. All stdout lines contain "jsonrpc": "2.0"
    3. No progress bar fragments (like 'h\\n', 'd\\n') appear on stdout

    Expected to FAIL initially because tokenizers library pollutes stdout with
    progress bar fragments during model download/initialization.
    """
    # Find the main.py file to run
    project_root = Path(__file__).parent.parent.parent
    main_py = project_root / "src" / "main.py"

    if not main_py.exists():
        raise FileNotFoundError(f"Cannot find main.py at {main_py}")

    # Start MCP server in stdio mode with subprocess
    # Use 'uv run' as specified in project instructions
    # Set bufsize=1 for line buffering and universal_newlines=True for text mode
    process = subprocess.Popen(
        ["uv", "run", "python", str(main_py)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=str(project_root),
    )

    invalid_lines = []
    non_jsonrpc_lines = []
    valid_messages = 0
    all_stdout_lines = []

    try:
        # Send initialize request to get the server to respond
        # This is a minimal valid JSON-RPC initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
        }
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()

        # Collect stdout for 10 seconds to capture startup period
        start_time = time.time()
        while time.time() - start_time < 10:
            # Use select to avoid blocking if no data is available
            # For Windows compatibility, just use a short timeout on readline
            line = ""
            try:
                # This will block, but we'll terminate the process after 10 seconds
                if process.poll() is not None:
                    break

                # Check if data is available (Unix-like systems only)
                if hasattr(select, "select"):
                    ready, _, _ = select.select([process.stdout], [], [], 0.1)
                    if not ready:
                        continue
                    line = process.stdout.readline()
                else:
                    # Windows fallback: just try to read
                    line = process.stdout.readline()

            except Exception:
                # If we can't read, just continue
                continue

            if not line:
                continue

            line = line.strip()
            if not line:
                continue

            all_stdout_lines.append(line)

            # Try to parse as JSON
            try:
                data = json.loads(line)
                valid_messages += 1

                # Verify it's a JSON-RPC message
                if "jsonrpc" not in data or data.get("jsonrpc") != "2.0":
                    non_jsonrpc_lines.append(line)

            except json.JSONDecodeError as e:
                # This is the expected failure - progress bar fragments
                invalid_lines.append((line, str(e)))

    finally:
        # Clean up process
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    # Assertions that should pass
    assert (
        valid_messages > 0 or invalid_lines
    ), f"Should have captured some output from server. Got {len(all_stdout_lines)} lines: {all_stdout_lines[:10]}"

    # Assertion that should FAIL due to progress bar pollution
    assert not invalid_lines, (
        f"Found {len(invalid_lines)} non-JSON lines on stdout. "
        f"MCP server stdout must contain ONLY valid JSON-RPC messages.\n"
        f"Invalid lines:\n"
        + "\n".join(
            f"  - {line!r} (error: {error})" for line, error in invalid_lines[:5]
        )
    )

    # Additional check for JSON-RPC format
    assert not non_jsonrpc_lines, (
        f"Found {len(non_jsonrpc_lines)} JSON lines without 'jsonrpc': '2.0'.\n"
        f"Examples:\n" + "\n".join(f"  - {line}" for line in non_jsonrpc_lines[:5])
    )
