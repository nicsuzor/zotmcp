"""Tests for ChromaDB corruption diagnostic script."""

import pytest
from click.testing import CliRunner


def test_cli_runs_with_help_flag():
    """Test that the CLI script can be invoked and shows help."""
    from scripts import diagnose_corruption

    runner = CliRunner()
    result = runner.invoke(diagnose_corruption.main, ["--help"])

    assert result.exit_code == 0
    assert "diagnostic" in result.output.lower()
    assert "chromadb" in result.output.lower()
