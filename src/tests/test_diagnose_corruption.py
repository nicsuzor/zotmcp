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


def test_detect_corruption_patterns():
    """Test detection of (cid:XX) PDF encoding artifacts."""
    from scripts.diagnose_corruption import detect_corruption

    # Clean text - no corruption
    clean_text = "This is a normal document with regular text content."
    corruption = detect_corruption(clean_text)
    assert corruption["is_corrupted"] is False
    assert corruption["corruption_percentage"] == 0.0
    assert corruption["cid_count"] == 0

    # Heavily corrupted text with (cid:XX) patterns
    corrupted_text = "(cid:62)(cid:146)(cid:209)(cid:176)(cid:197)(cid:160) some text (cid:123)"
    corruption = detect_corruption(corrupted_text)
    assert corruption["is_corrupted"] is True
    assert corruption["corruption_percentage"] > 0
    assert corruption["cid_count"] == 7  # 7 (cid:XX) patterns

    # Partial corruption
    partial_text = "This is mostly clean text but has (cid:42) one artifact here."
    corruption = detect_corruption(partial_text)
    assert corruption["is_corrupted"] is True
    assert corruption["corruption_percentage"] > 0
    assert corruption["cid_count"] == 1

    # Empty or missing text
    empty_text = ""
    corruption = detect_corruption(empty_text)
    assert corruption["is_corrupted"] is True  # Empty is a form of corruption
    assert corruption["corruption_percentage"] == 100.0  # Completely missing
    assert corruption["cid_count"] == 0
