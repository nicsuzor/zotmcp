"""Tests for corruption detection against curated test data.

Validates is_document_corrupt() function against ground-truth labeled test data
files in tests/data/. Each JSON file contains document chunks and an expected
corruption label that serves as the golden reference.

Test data format:
{
    "id": "DOCUMENT_ID",
    "corrupt": bool,  # Ground truth label
    "chunks": List[str],
    "chunk_ids": List[str],
    "metadata": dict
}

Also includes comparison tests that extract fresh text from PDFs and compare
corruption rates between stored ChromaDB chunks and fresh extractions.
"""

import json
from pathlib import Path
from typing import List, Tuple

import pytest
from buttermilk._core.types import BaseRecord
from buttermilk.data.vector import SemanticSplitter

from text_quality import is_document_corrupt


def load_test_documents() -> List[Tuple[str, List[str], bool]]:
    """Load all test documents from tests/data/ directory.

    Returns:
        List of tuples: (document_id, chunks, expected_corrupt_flag)
    """
    test_data_dir = Path(__file__).parent.parent.parent / "tests" / "data"

    if not test_data_dir.exists():
        pytest.skip(f"Test data directory not found: {test_data_dir}")

    test_cases = []

    # Load all JSON files in tests/data/
    for json_file in sorted(test_data_dir.glob("*.json")):
        with open(json_file, "r") as f:
            data = json.load(f)

        doc_id = data["id"]
        chunks = data["chunks"]
        expected_corrupt = data["corrupt"]

        test_cases.append((doc_id, chunks, expected_corrupt))

    if not test_cases:
        pytest.skip(f"No test data files found in {test_data_dir}")

    return test_cases


@pytest.fixture
def test_documents():
    """Fixture that provides test document data."""
    return load_test_documents()


@pytest.mark.parametrize("doc_id,chunks,expected_corrupt", load_test_documents())
def test_corruption_detection_against_test_data(
    doc_id: str, chunks: List[str], expected_corrupt: bool
):
    """Validate corruption detection matches ground truth labels.

    This test ensures is_document_corrupt() correctly identifies corruption
    in real documents that have been manually reviewed and labeled.

    Args:
        doc_id: Document identifier (e.g., "ULXGASB5")
        chunks: List of text chunks from the document
        expected_corrupt: Ground truth corruption label
    """
    # ARRANGE: Use default threshold of 66.0%
    threshold = 66.0

    # ACT: Run corruption detection
    result = is_document_corrupt(chunks, threshold=threshold)

    # ASSERT: Verify detection matches ground truth
    actual_corrupt = result["is_corrupt"]
    corruption_rate = result["corruption_rate"]
    total_chunks = result["total_chunks"]
    corrupted_chunks = result["corrupted_chunks"]

    # Provide detailed failure message with corruption metrics
    failure_msg = (
        f"Document {doc_id}: Corruption detection mismatch\n"
        f"  Expected: {'CORRUPT' if expected_corrupt else 'CLEAN'}\n"
        f"  Actual:   {'CORRUPT' if actual_corrupt else 'CLEAN'}\n"
        f"  Corruption rate: {corruption_rate:.1f}% "
        f"({corrupted_chunks}/{total_chunks} chunks)\n"
        f"  Threshold: {threshold}%\n"
        f"  Decision: {'FAIL' if actual_corrupt != expected_corrupt else 'PASS'}"
    )

    assert actual_corrupt == expected_corrupt, failure_msg


def test_corruption_detection_threshold_sensitivity(test_documents):
    """Verify corruption detection responds to threshold changes.

    Tests that adjusting the corruption threshold appropriately changes
    corruption detection outcomes across multiple test documents.
    """
    if not test_documents:
        pytest.skip("No test documents available")

    # Test with different thresholds
    thresholds = [50.0, 66.0, 80.0]
    results_by_threshold = {}

    for threshold in thresholds:
        corrupt_count = 0
        for doc_id, chunks, _ in test_documents:
            result = is_document_corrupt(chunks, threshold=threshold)
            if result["is_corrupt"]:
                corrupt_count += 1
        results_by_threshold[threshold] = corrupt_count

    # Lower thresholds should flag more documents (or equal)
    assert (
        results_by_threshold[50.0] >= results_by_threshold[66.0]
    ), "Lower threshold should flag >= documents"
    assert (
        results_by_threshold[66.0] >= results_by_threshold[80.0]
    ), "Lower threshold should flag >= documents"


def test_corruption_detection_chunk_analysis(test_documents):
    """Verify chunk-level corruption details are provided.

    Ensures is_document_corrupt() returns detailed per-chunk analysis
    that can be used for debugging and understanding corruption patterns.
    """
    if not test_documents:
        pytest.skip("No test documents available")

    # Test first document
    doc_id, chunks, _ = test_documents[0]
    result = is_document_corrupt(chunks, threshold=66.0)

    # Verify structure
    assert "chunk_details" in result, "Result should include chunk_details"
    assert len(result["chunk_details"]) == len(
        chunks
    ), "Should have one detail entry per chunk"

    # Verify each chunk detail has required fields
    for chunk_detail in result["chunk_details"]:
        assert "is_corrupted" in chunk_detail
        assert "corruption_percentage" in chunk_detail
        assert "cid_count" in chunk_detail
        assert "newline_ratio" in chunk_detail
        assert "avg_line_length" in chunk_detail
        assert "detected_language" in chunk_detail


# ===== Fresh PDF Extraction Comparison Tests =====


def get_test_data_dir() -> Path:
    """Get path to tests/data directory."""
    return Path(__file__).parent.parent.parent / "tests" / "data"


def load_chromadb_chunks(item_key: str) -> list[str]:
    """Load stored ChromaDB chunks from JSON test data.

    Args:
        item_key: Zotero item key (e.g., 'ULXGASB5')

    Returns:
        List of text chunks from ChromaDB
    """
    json_path = get_test_data_dir() / f"{item_key}.json"
    with open(json_path) as f:
        data = json.load(f)
    return data["chunks"]


async def extract_fresh_text(item_key: str) -> str:
    """Extract fresh text from PDF using pdftotext (same as pipeline).

    Args:
        item_key: Zotero item key (e.g., 'ULXGASB5')

    Returns:
        Extracted text content
    """
    import subprocess

    pdf_path = get_test_data_dir() / f"{item_key}.pdf"

    # Use pdftotext to extract text (same as PDFToTextProcessor does)
    # This is the same extraction method used by the pipeline
    result = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout


async def chunk_text(text: str) -> list[str]:
    """Chunk text using SemanticSplitter with same config as pipeline.

    Args:
        text: Full text to chunk

    Returns:
        List of text chunks
    """
    # Use same chunking config as vectorize.yaml
    splitter = SemanticSplitter(chunk_size=500, chunk_overlap=200)

    # Create a BaseRecord with the text content
    record = BaseRecord(record_id="temp", content=text)

    # Process and collect chunks
    # SemanticSplitter yields one record with all chunks attached as ChunkedDocument objects
    chunks = []
    async for chunk_record in splitter.process(record):
        # The SemanticSplitter attaches chunks to the record
        if hasattr(chunk_record, "chunks") and chunk_record.chunks:
            # Extract text from each ChunkedDocument
            for chunk in chunk_record.chunks:
                # ChunkedDocument has chunk_text attribute
                if hasattr(chunk, "chunk_text"):
                    chunks.append(chunk.chunk_text)

    return chunks


@pytest.mark.parametrize(
    "item_key",
    [
        "ULXGASB5",  # Start with the one we have
    ],
)
async def test_compare_chromadb_vs_fresh_extraction(item_key: str):
    """Compare corruption rates between ChromaDB chunks and fresh PDF extraction.

    This test determines if our current PDF extraction produces cleaner text
    than what's stored in ChromaDB.

    Args:
        item_key: Zotero item key to test
    """
    # 1. Load stored ChromaDB chunks
    chromadb_chunks = load_chromadb_chunks(item_key)

    # 2. Extract fresh text from PDF
    fresh_text = await extract_fresh_text(item_key)

    # 3. Chunk the fresh text the same way
    fresh_chunks = await chunk_text(fresh_text)

    # 4. Run corruption detection on both versions
    chromadb_result = is_document_corrupt(chromadb_chunks, threshold=66.0)
    fresh_result = is_document_corrupt(fresh_chunks, threshold=66.0)

    # 5. Calculate improvement
    improvement = chromadb_result["corruption_rate"] - fresh_result["corruption_rate"]

    # Determine verdict
    if improvement > 5.0:
        verdict = "Improved"
    elif improvement < -5.0:
        verdict = "Worse"
    else:
        verdict = "Same"

    # Print comparison results
    print(f"\n{'=' * 70}")
    print(f"Corruption Comparison: {item_key}")
    print(f"{'=' * 70}")
    print(f"Document ID:                     {item_key}")
    print(f"ChromaDB corruption rate:        {chromadb_result['corruption_rate']:.1f}%")
    print(
        f"  - Corrupted chunks:            {chromadb_result['corrupted_chunks']}/{chromadb_result['total_chunks']}"
    )
    print(f"Fresh extraction corruption rate: {fresh_result['corruption_rate']:.1f}%")
    print(
        f"  - Corrupted chunks:            {fresh_result['corrupted_chunks']}/{fresh_result['total_chunks']}"
    )
    print(f"Difference:                      {improvement:+.1f}%")
    print(f"Verdict:                         {verdict}")
    print(f"{'=' * 70}\n")

    # Detailed chunk-by-chunk analysis
    print("Chunk-by-Chunk Details:")
    print(f"{'-' * 70}")

    # Show first 5 corrupted chunks from each version for debugging
    chromadb_corrupted = [
        i
        for i, detail in enumerate(chromadb_result["chunk_details"])
        if detail["is_corrupted"]
    ]
    fresh_corrupted = [
        i
        for i, detail in enumerate(fresh_result["chunk_details"])
        if detail["is_corrupted"]
    ]

    print(f"ChromaDB corrupted chunk indices: {chromadb_corrupted[:5]}")
    if chromadb_corrupted:
        first_idx = chromadb_corrupted[0]
        detail = chromadb_result["chunk_details"][first_idx]
        print(f"  Chunk {first_idx} corruption details:")
        print(f"    - cid_count: {detail['cid_count']}")
        print(f"    - newline_ratio: {detail['newline_ratio']:.1f}%")
        print(f"    - avg_line_length: {detail['avg_line_length']:.1f}")
        print(f"    - Text preview: {chromadb_chunks[first_idx][:100]}...")

    print(f"\nFresh extraction corrupted chunk indices: {fresh_corrupted[:5]}")
    if fresh_corrupted:
        first_idx = fresh_corrupted[0]
        detail = fresh_result["chunk_details"][first_idx]
        print(f"  Chunk {first_idx} corruption details:")
        print(f"    - cid_count: {detail['cid_count']}")
        print(f"    - newline_ratio: {detail['newline_ratio']:.1f}%")
        print(f"    - avg_line_length: {detail['avg_line_length']:.1f}")
        print(f"    - Text preview: {fresh_chunks[first_idx][:100]}...")

    print(f"{'-' * 70}\n")

    # Store results for reporting (test always passes - we just want to see the data)
    # In a real scenario, we might assert improvement, but for now we just report
    assert True, "Test complete - see output for comparison results"
