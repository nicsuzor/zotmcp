import pytest
import json
from pydantic import BaseModel, ConfigDict
from buttermilk._core.processing_context import ProcessingContext
from buttermilk._core.types import Record
from zotmcp.prepend_processor import PrependProcessor, RestoreTextProcessor


def make_context(record: Record) -> ProcessingContext:
    return ProcessingContext(session_id="test", record=record)

class MockChunk(BaseModel):
    model_config = ConfigDict(extra="ignore")
    chunk_index: int = 0
    chunk_id: str = "test_0"
    chunk_text: str = ""
    metadata: dict = {}

@pytest.mark.asyncio
async def test_correct_prepend_full_metadata():
    processor = PrependProcessor(min_chunk_size=1)
    
    record = Record(
        record_id="doc1",
        content="Abstract\nThis is the abstract.\n\nHere is paragraph 1. It is very long and has lots of words so it passes the min_chunk_size.",
        metadata={
            "zotero_data": json.dumps({
                "title": "Test Title", 
                "date": "2023-05-01", 
                "creators": [{"creatorType": "author", "firstName": "Jane", "lastName": "Doe"}]
            })
        },
        chunks=[MockChunk(chunk_text="Here is paragraph 1. It is very long and has lots of words so it passes the min_chunk_size.")]
    )
    
    generator = processor.process(make_context(record))
    result = await generator.__anext__()
    
    # Abstract chunk and regular chunk
    assert len(result.chunks) == 2
    
    abs_chunk = result.chunks[0]
    assert abs_chunk.metadata["raw_text"] == "This is the abstract."
    assert abs_chunk.chunk_text == "Test Title — Jane Doe — 2023\nABSTRACT\n\nThis is the abstract."
    
    chunk1 = result.chunks[1]
    assert chunk1.metadata["raw_text"] == "Here is paragraph 1. It is very long and has lots of words so it passes the min_chunk_size."
    assert chunk1.chunk_text == "Test Title — Jane Doe — 2023\n\nHere is paragraph 1. It is very long and has lots of words so it passes the min_chunk_size."

@pytest.mark.asyncio
async def test_correct_prepend_missing_year():
    processor = PrependProcessor(min_chunk_size=1)
    
    record = Record(
        record_id="doc2",
        content="Some content",
        metadata={
            "zotero_data": json.dumps({
                "title": "No Year Title", 
                "creators": [{"creatorType": "author", "lastName": "Smith"}]
            })
        },
        chunks=[MockChunk(chunk_text="Chunk text that is quite long enough to be preserved without abstract.")]
    )
    
    generator = processor.process(make_context(record))
    result = await generator.__anext__()
    
    assert len(result.chunks) == 1
    chunk = result.chunks[0]
    assert chunk.chunk_text == "No Year Title — Smith\n\nChunk text that is quite long enough to be preserved without abstract."

@pytest.mark.asyncio
async def test_failure_missing_zotero_data():
    processor = PrependProcessor(min_chunk_size=1)
    record = Record(
        record_id="doc3",
        content="Some content",
        metadata={},
        chunks=[MockChunk(chunk_text="Some text")]
    )
    
    with pytest.raises(ValueError, match="missing zotero_data"):
        generator = processor.process(make_context(record))
        await generator.__anext__()

@pytest.mark.asyncio
async def test_restore_text_processor():
    processor = RestoreTextProcessor()
    
    chunk = MockChunk(chunk_text="Prepended Text\n\nRaw text")
    chunk.metadata = {"raw_text": "Raw text", "other": "value"}
    record = Record(
        record_id="doc4",
        content="Non-empty content so validation passes.",
        metadata={},
        chunks=[chunk]
    )
    
    generator = processor.process(make_context(record))
    result = await generator.__anext__()
    
    restored_chunk = result.chunks[0]
    assert restored_chunk.chunk_text == "Raw text"
    assert "raw_text" not in restored_chunk.metadata
    assert restored_chunk.metadata["other"] == "value"
