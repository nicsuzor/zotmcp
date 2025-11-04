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


@pytest.mark.asyncio
async def test_get_collection_stats(bm_dev):
    """Test that script can connect to ChromaDB and retrieve collection stats."""
    from scripts.diagnose_corruption import get_collection_stats

    stats = await get_collection_stats(bm_dev)

    assert "total_documents" in stats
    assert "collection_name" in stats
    assert stats["total_documents"] > 0  # Should have documents in dev collection
    assert stats["collection_name"] == "prosocial_zot"
