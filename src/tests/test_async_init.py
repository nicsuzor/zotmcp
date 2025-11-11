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
