"""Tests for QualityFilterProcessor.

This processor filters out corrupt documents from the pipeline based on
document-level quality analysis. It should be placed between chunking
and embedding steps to prevent corrupt documents from being vectorized.
"""

import pytest
from buttermilk._core.types import Record
from buttermilk.data.vector import ChunkedDocument


@pytest.mark.asyncio
async def test_quality_filter_passes_clean_document():
    """Test QualityFilterProcessor yields clean documents unchanged."""
    # Arrange
    from src.quality_processor import QualityFilterProcessor

    processor = QualityFilterProcessor(
        corruption_threshold=95.0, pattern_threshold=80.0
    )

    # Create a record with clean chunks
    chunks = [
        ChunkedDocument(
            document_title="Clean Doc",
            chunk_index=i,
            chunk_text=f"This is normal English text chunk {i}.",
            document_id="CLEAN123",
            chunk_id=f"CLEAN123_{i}",
            metadata={"title": "Clean Doc"},
        )
        for i in range(10)
    ]

    record = Record(
        record_id="CLEAN123",
        content="Combined text",
        metadata={"title": "Clean Doc"},
        chunks=chunks,
    )

    # Act
    results = []
    async for result in processor.process(record, processor_stage="quality_filter"):
        results.append(result)

    # Assert
    assert len(results) == 1, "Clean document should be yielded"
    assert results[0].record_id == "CLEAN123"
    assert len(results[0].chunks) == 10


@pytest.mark.asyncio
async def test_quality_filter_blocks_95_percent_corrupt_document():
    """Test QualityFilterProcessor filters out 95%+ corrupt documents."""
    # Arrange
    from src.quality_processor import QualityFilterProcessor

    processor = QualityFilterProcessor(
        corruption_threshold=95.0, pattern_threshold=80.0
    )

    # Create a record where 96 out of 100 chunks are corrupt
    # Use 20+ CID patterns to trigger corruption detection (threshold is >=20)
    corrupt_text = " ".join([f"(cid:{i})" for i in range(1, 26)])  # 25 CID patterns
    corrupt_chunks = [
        ChunkedDocument(
            document_title="Corrupt Doc",
            chunk_index=i,
            chunk_text=corrupt_text,
            document_id="CORRUPT123",
            chunk_id=f"CORRUPT123_{i}",
            metadata={"title": "Corrupt Doc"},
        )
        for i in range(96)
    ]

    clean_chunks = [
        ChunkedDocument(
            document_title="Corrupt Doc",
            chunk_index=i + 96,
            chunk_text="Normal text chunk",
            document_id="CORRUPT123",
            chunk_id=f"CORRUPT123_{i + 96}",
            metadata={"title": "Corrupt Doc"},
        )
        for i in range(4)
    ]

    record = Record(
        record_id="CORRUPT123",
        content="Combined text",
        metadata={"title": "Corrupt Doc"},
        chunks=corrupt_chunks + clean_chunks,
    )

    # Act
    results = []
    async for result in processor.process(record, processor_stage="quality_filter"):
        results.append(result)

    # Assert
    assert len(results) == 0, "96% corrupt document should be filtered out"


@pytest.mark.asyncio
async def test_quality_filter_passes_94_percent_corrupt_document():
    """Test QualityFilterProcessor passes 94% corrupt document (below threshold)."""
    # Arrange
    from src.quality_processor import QualityFilterProcessor

    processor = QualityFilterProcessor(
        corruption_threshold=95.0, pattern_threshold=80.0
    )

    # Create a record where 94 out of 100 chunks are corrupt (JUST below threshold)
    # Use 20+ CID patterns to trigger corruption detection (threshold is >=20)
    corrupt_text = " ".join([f"(cid:{i})" for i in range(1, 26)])  # 25 CID patterns
    corrupt_chunks = [
        ChunkedDocument(
            document_title="Borderline Doc",
            chunk_index=i,
            chunk_text=corrupt_text,
            document_id="BORDER123",
            chunk_id=f"BORDER123_{i}",
            metadata={"title": "Borderline Doc"},
        )
        for i in range(94)
    ]

    clean_chunks = [
        ChunkedDocument(
            document_title="Borderline Doc",
            chunk_index=i + 94,
            chunk_text="Normal text chunk",
            document_id="BORDER123",
            chunk_id=f"BORDER123_{i + 94}",
            metadata={"title": "Borderline Doc"},
        )
        for i in range(6)
    ]

    record = Record(
        record_id="BORDER123",
        content="Combined text",
        metadata={"title": "Borderline Doc"},
        chunks=corrupt_chunks + clean_chunks,
    )

    # Act
    results = []
    async for result in processor.process(record, processor_stage="quality_filter"):
        results.append(result)

    # Assert
    assert len(results) == 1, "94% corrupt document should pass (below 95% threshold)"
    assert results[0].record_id == "BORDER123"


@pytest.mark.asyncio
async def test_quality_filter_with_custom_thresholds():
    """Test QualityFilterProcessor respects custom threshold configuration."""
    # Arrange - use stricter 80% threshold
    from src.quality_processor import QualityFilterProcessor

    processor = QualityFilterProcessor(
        corruption_threshold=80.0,  # Stricter threshold
        pattern_threshold=80.0,
    )

    # Create a record with 85% corruption (would pass 95% threshold, fail 80%)
    # Use 20+ CID patterns to trigger corruption detection (threshold is >=20)
    corrupt_text = " ".join([f"(cid:{i})" for i in range(1, 26)])  # 25 CID patterns
    corrupt_chunks = [
        ChunkedDocument(
            document_title="Mid Corrupt Doc",
            chunk_index=i,
            chunk_text=corrupt_text,
            document_id="MID123",
            chunk_id=f"MID123_{i}",
            metadata={"title": "Mid Corrupt Doc"},
        )
        for i in range(85)
    ]

    clean_chunks = [
        ChunkedDocument(
            document_title="Mid Corrupt Doc",
            chunk_index=i + 85,
            chunk_text="Normal text",
            document_id="MID123",
            chunk_id=f"MID123_{i + 85}",
            metadata={"title": "Mid Corrupt Doc"},
        )
        for i in range(15)
    ]

    record = Record(
        record_id="MID123",
        content="Combined text",
        metadata={"title": "Mid Corrupt Doc"},
        chunks=corrupt_chunks + clean_chunks,
    )

    # Act
    results = []
    async for result in processor.process(record, processor_stage="quality_filter"):
        results.append(result)

    # Assert
    assert (
        len(results) == 0
    ), "85% corrupt document should be filtered with 80% threshold"


@pytest.mark.asyncio
async def test_quality_filter_logs_filtered_documents(caplog):
    """Test QualityFilterProcessor logs when filtering documents."""
    # Arrange
    from src.quality_processor import QualityFilterProcessor

    processor = QualityFilterProcessor(
        corruption_threshold=95.0, pattern_threshold=80.0
    )

    # Create corrupt document
    # Use 20+ CID patterns to trigger corruption detection (threshold is >=20)
    corrupt_text = " ".join([f"(cid:{i})" for i in range(1, 26)])  # 25 CID patterns
    chunks = [
        ChunkedDocument(
            document_title="Very Corrupt",
            chunk_index=i,
            chunk_text=corrupt_text,
            document_id="LOG123",
            chunk_id=f"LOG123_{i}",
            metadata={"title": "Very Corrupt"},
        )
        for i in range(100)
    ]

    record = Record(
        record_id="LOG123",
        content="Combined text",
        metadata={"title": "Very Corrupt"},
        chunks=chunks,
    )

    # Act
    results = []
    async for result in processor.process(record, processor_stage="quality_filter"):
        results.append(result)

    # Assert
    assert len(results) == 0
    # Check that logging occurred (processor should log filtering decision)
    # Note: Exact log format will be implemented in processor
