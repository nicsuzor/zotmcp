#!/usr/bin/env python3
"""Update test files to use mcp_server directly instead of wrapping in Client.

This script is part of the zotmcp project to optimize Docker E2E tests.
"""

import re
from pathlib import Path


def update_file(filepath: Path) -> int:
    """Update a test file to remove Client context managers.

    Returns:
        Number of replacements made
    """
    content = filepath.read_text()
    lines = content.split("\n")
    result = []
    replacements = 0

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if line contains Client context manager
        match = re.match(r"(\s*)async with Client\(mcp_server\) as (\w+):\s*$", line)
        if match:
            original_indent = len(match.group(1))
            client_var = match.group(2)
            replacements += 1

            # Skip this line, process the indented block
            i += 1

            # Collect and dedent the block lines
            while i < len(lines):
                block_line = lines[i]

                if block_line.strip():  # Non-empty line
                    line_indent = len(block_line) - len(block_line.lstrip())

                    # Back to original indent level or less, block ended
                    if line_indent <= original_indent:
                        break

                    # Remove 4 spaces of indentation
                    if block_line.startswith("    "):
                        dedented = block_line[4:]
                    else:
                        dedented = block_line

                    # Replace client variable with mcp_server
                    dedented = dedented.replace(client_var, "mcp_server")
                    result.append(dedented)
                else:
                    # Empty line - keep as is
                    result.append(block_line)

                i += 1
            continue

        result.append(line)
        i += 1

    # Write back
    filepath.write_text("\n".join(result))
    return replacements


def main():
    """Update all test files."""
    base_dir = Path(__file__).parent.parent / "src" / "tests"

    test_files = [
        base_dir / "test_integration.py",
        base_dir / "test_search_tool.py",
    ]

    total = 0
    for filepath in test_files:
        if filepath.exists():
            count = update_file(filepath)
            print(f"✓ {filepath.name}: {count} replacements")
            total += count
        else:
            print(f"✗ {filepath.name}: not found")

    print(f"\nTotal: {total} replacements across {len(test_files)} files")


if __name__ == "__main__":
    main()
