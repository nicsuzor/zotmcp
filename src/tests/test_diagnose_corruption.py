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


def test_classify_severity():
    """Test severity classification based on corruption metrics."""
    from scripts.diagnose_corruption import classify_severity, detect_corruption

    # Clean text - no corruption
    clean_result = detect_corruption("Clean text with no issues.")
    assert classify_severity(clean_result) == "clean"

    # Low corruption (< 5%) - need longer text to dilute percentage
    # (cid:1) is 7 chars, need >140 chars total for <5%
    low_corrupt = detect_corruption("This is a long paragraph with mostly clean content and proper text. " * 3 + "(cid:1)")
    assert classify_severity(low_corrupt) == "low"

    # Medium corruption (5-20%) - multiple artifacts in moderate text
    # 3 x (cid:X) = 21 chars, need 105-420 chars total for 5-20%
    medium_corrupt = detect_corruption("This is some text content that will be analyzed for corruption. " * 2 + "(cid:1)(cid:2)(cid:3)")
    assert classify_severity(medium_corrupt) == "medium"

    # High corruption (> 20%) - heavy artifact density
    high_corrupt = detect_corruption("(cid:1)(cid:2)(cid:3)(cid:4) text")
    assert classify_severity(high_corrupt) == "high"

    # Empty text - complete corruption
    empty_result = detect_corruption("")
    assert classify_severity(empty_result) == "empty"


@pytest.mark.asyncio
async def test_scan_collection_for_corruption(bm_dev):
    """Test complete diagnostic workflow: scan collection and generate report."""
    from scripts.diagnose_corruption import scan_collection_for_corruption

    # Scan a small sample of the collection
    report = await scan_collection_for_corruption(bm_dev, max_documents=100)

    # Verify report structure
    assert "total_scanned" in report
    assert "total_corrupted" in report
    assert "corruption_rate" in report
    assert "severity_breakdown" in report
    assert "sample_corrupted" in report

    # Verify data integrity
    assert report["total_scanned"] == 100
    assert report["total_scanned"] >= report["total_corrupted"]
    assert 0 <= report["corruption_rate"] <= 100

    # Verify severity breakdown
    severity = report["severity_breakdown"]
    assert "clean" in severity
    assert "low" in severity
    assert "medium" in severity
    assert "high" in severity
    assert "empty" in severity

    # Sum of severity counts should equal total scanned
    total_by_severity = sum(severity.values())
    assert total_by_severity == report["total_scanned"]


@pytest.mark.asyncio
async def test_output_flag_creates_json_file(bm_dev, tmp_path):
    """Test that --output flag creates JSON file with all corrupted documents."""
    import json
    from scripts.diagnose_corruption import diagnose_collection

    # Create temporary output file path
    output_file = tmp_path / "corruption_report.json"

    # Run diagnostic with output flag
    await diagnose_collection(verbose=False, output_file=str(output_file))

    # Verify file was created
    assert output_file.exists()

    # Load and verify JSON structure
    with open(output_file) as f:
        data = json.load(f)

    # Verify summary statistics exist
    assert "summary" in data
    summary = data["summary"]
    assert "total_scanned" in summary
    assert "total_corrupted" in summary
    assert "corruption_rate" in summary
    assert "severity_breakdown" in summary

    # Verify corrupted documents list exists
    assert "corrupted_documents" in data
    corrupted_docs = data["corrupted_documents"]
    assert isinstance(corrupted_docs, list)

    # If there are corrupted documents, verify their structure
    if len(corrupted_docs) > 0:
        sample_doc = corrupted_docs[0]
        assert "document_id" in sample_doc
        assert "severity" in sample_doc
        assert "corruption_percentage" in sample_doc
        assert "cid_count" in sample_doc
        assert "text_preview" in sample_doc

    # Verify ALL corrupted documents are included (not just 10 samples)
    # The count in summary should match the length of corrupted_documents list
    assert summary["total_corrupted"] == len(corrupted_docs)


@pytest.mark.asyncio
async def test_limit_option_controls_scan_size(bm_dev):
    """Test that --limit option controls how many documents are scanned."""
    from scripts.diagnose_corruption import diagnose_collection

    # Test custom limit of 50 documents
    report_50 = await diagnose_collection(verbose=False, output_file=None, max_documents=50)
    assert report_50["total_scanned"] == 50

    # Test default behavior (should scan 1000)
    report_default = await diagnose_collection(verbose=False, output_file=None)
    assert report_default["total_scanned"] == 1000


def test_cli_limit_option_exists():
    """Test that CLI accepts --limit option."""
    from scripts import diagnose_corruption

    runner = CliRunner()
    result = runner.invoke(diagnose_corruption.main, ["--help"])

    assert result.exit_code == 0
    assert "--limit" in result.output


@pytest.mark.asyncio
async def test_corrupted_documents_include_document_id_from_metadata(bm_dev):
    """Test that corrupted documents include actual document_id from ChromaDB metadata.

    BUG FIX TEST: The diagnostic script was using metadata.get("item_key", "unknown")
    but the actual field in ChromaDB is "document_id". This test verifies that
    corrupted documents in the scan results contain real document_id values.
    """
    from scripts.diagnose_corruption import scan_collection_for_corruption

    # Scan larger sample to ensure we find some corrupted documents
    report = await scan_collection_for_corruption(bm_dev, max_documents=1000)

    # We should find at least one corrupted document in 1000 samples
    assert report["total_corrupted"] > 0, \
        "Expected to find at least one corrupted document in sample of 1000"

    assert len(report["sample_corrupted"]) > 0, \
        "sample_corrupted list should not be empty when corrupted documents exist"

    first_corrupted = report["sample_corrupted"][0]

    # The field should be named "document_id" (not "item_key")
    assert "document_id" in first_corrupted, \
        "Corrupted document should have 'document_id' field from metadata"

    # The document_id should be a real Zotero key, not "unknown"
    document_id = first_corrupted["document_id"]
    assert document_id != "unknown", \
        f"document_id should be actual Zotero key from metadata, not 'unknown'. Got: {document_id}"

    # Zotero keys are typically 8 alphanumeric characters
    assert len(document_id) > 0, "document_id should not be empty"


def test_detect_corruption_with_language_detection():
    """Test that language-based corruption detection identifies non-English artifacts.

    EXPERIMENTAL FEATURE: This test validates langdetect integration to catch
    corruption patterns that don't have (cid:XX) markers but are still corrupted
    (e.g., 'o o o o o...', 't u o S . S . U...').

    Language detection supplements CID pattern matching and may be refined/replaced
    in future iterations based on false positive rates and detection accuracy.
    """
    from scripts.diagnose_corruption import detect_corruption

    # Clean English text - should NOT be detected as corrupted
    clean_text = "This is a normal document with regular text content and proper English sentences."
    corruption = detect_corruption(clean_text)
    assert corruption["is_corrupted"] is False
    assert "detected_language" in corruption
    assert corruption["detected_language"] == "en"  # English

    # Pattern: 'o o o o o...' - detected as Portuguese by langdetect
    # This is a known corruption pattern from document RJU3NH8P
    o_pattern_text = "o o o o o o o o o o o o o o o o o o o o o o o o o o o o o o"
    corruption = detect_corruption(o_pattern_text)
    assert corruption["is_corrupted"] is True
    assert "detected_language" in corruption
    assert corruption["detected_language"] != "en"  # Should detect as non-English

    # Pattern: 't u o S . S . U...' - detected as Croatian/Welsh by langdetect
    # This is a known corruption pattern from document MBGHP5HR
    t_pattern_text = "t u o S . S . U t u o S . S . U t u o S . S . U t u o S . S . U"
    corruption = detect_corruption(t_pattern_text)
    assert corruption["is_corrupted"] is True
    assert "detected_language" in corruption
    assert corruption["detected_language"] != "en"  # Should detect as non-English

    # CID pattern - should still be detected (backward compatibility)
    cid_text = "(cid:62)(cid:146)(cid:209)(cid:176)(cid:197)(cid:160) some text (cid:123)"
    corruption = detect_corruption(cid_text)
    assert corruption["is_corrupted"] is True
    assert corruption["cid_count"] > 0
    # CID patterns often detect as Spanish/other languages
    assert "detected_language" in corruption

    # Mixed corruption: English text with CID patterns
    mixed_text = "This is mostly clean text but has (cid:42) one artifact here."
    corruption = detect_corruption(mixed_text)
    assert corruption["is_corrupted"] is True  # CID pattern triggers corruption
    assert corruption["cid_count"] == 1
    # Should detect as English despite CID (majority of text is English)
    assert "detected_language" in corruption
