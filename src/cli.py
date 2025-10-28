"""ZotMCP CLI - Command-line entry point with full Hydra override support.

This module provides a CLI interface for running ZotMCP with Hydra configuration
overrides. Unlike main.py (which is used by FastMCP), this accepts command-line
arguments for configuration.

Usage:
    uv run python src/cli.py +db=dev
    uv run python src/cli.py storage.zotero_vectors.persist_directory=/custom/path
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from main import mcp


if __name__ == "__main__":
    # Import lifespan manager that uses sys.argv for overrides
    import asyncio
    from contextlib import asynccontextmanager

    from buttermilk import init_async, logger
    from main import get_search_tool

    # Global buttermilk instance
    bm = None
    search_tool = None

    @asynccontextmanager
    async def cli_lifespan_manager(server):
        """Initialize buttermilk with Hydra overrides from command line."""
        global bm, search_tool

        # Load zotero config - use absolute path from project root
        conf_dir = str(Path(__file__).parent.parent / "conf")

        # Parse sys.argv for Hydra overrides (everything after script name)
        overrides = sys.argv[1:] if len(sys.argv) > 1 else []
        logger.info(f"CLI mode - Initializing with overrides: {overrides}")

        bm = await init_async(config_dir=conf_dir, config_name="zotero", overrides=overrides)

        # Update global bm in main module so tools can access it
        import main
        main.bm = bm

        search_tool = get_search_tool()
        await search_tool.ensure_cache_initialized()

        # Update global search_tool in main module
        main.search_tool = search_tool

        logger.info("Buttermilk initialized via CLI")

        yield

        logger.info("Shutting down ZotMCP CLI")

    # Create new FastMCP instance with CLI lifespan manager
    from fastmcp import FastMCP
    cli_mcp = FastMCP("ZotMCP - Academic Literature Search", lifespan=cli_lifespan_manager)

    # Copy all tool registrations from main.mcp
    cli_mcp._tools = mcp._tools
    cli_mcp._prompts = mcp._prompts

    # Default to stdio for MCP; allow opting into HTTP via env for local debugging
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport == "stdio":
        cli_mcp.run()
    else:
        cli_mcp.run(
            transport="streamable-http",
            host=os.getenv("MCP_HTTP_HOST", "0.0.0.0"),
            port=int(os.getenv("MCP_HTTP_PORT", "8024")),
        )
