"""Prepend Processor for adding metadata to chunks before embedding."""

import json
import re
import copy
from typing import AsyncGenerator, Dict, Any

from pydantic import BaseModel, Field
from buttermilk import logger
from buttermilk._core.processing_context import ProcessingContext
from buttermilk._core.types import Record

def _count_tokens(text: str) -> int:
    """Approximate token count (1 token ≈ 4 chars)."""
    return len(text) // 4

class PrependProcessor(BaseModel):
    """Adds document metadata prepend to chunks and extracts abstract."""
    
    min_chunk_size: int = Field(default=80)
    
    async def process(self, context: ProcessingContext) -> AsyncGenerator[Record, None]:
        """Adds document metadata prepend to chunks and extracts abstract."""
        record = context.record
        if not hasattr(record, "chunks") or not record.chunks:
            yield record
            return
            
        # Get metadata
        metadata = record.metadata or {}
        zotero_data_str = metadata.get("zotero_data")
        if not zotero_data_str:
            raise ValueError(f"Record {record.record_id} missing zotero_data")
            
        try:
            zotero_data = json.loads(zotero_data_str) if isinstance(zotero_data_str, str) else zotero_data_str
        except Exception:
            raise ValueError(f"Record {record.record_id} has invalid zotero_data")
            
        title = zotero_data.get("title") or record.record_id
        
        # Format authors
        creators = zotero_data.get("creators", [])
        authors_list = []
        for c in creators:
            if c.get("creatorType") in ["author", "contributor", "editor"]:
                if "lastName" in c and "firstName" in c:
                    authors_list.append(f"{c['firstName']} {c['lastName']}")
                elif "lastName" in c:
                    authors_list.append(c['lastName'])
                elif "name" in c:
                    authors_list.append(c['name'])
                    
        if len(authors_list) > 3:
            # Last names only for >3 authors
            authors_list = []
            for c in creators:
                if c.get("creatorType") in ["author", "contributor", "editor"]:
                    if "lastName" in c:
                        authors_list.append(c['lastName'])
                    elif "name" in c:
                        authors_list.append(c['name'])
        
        authors = ", ".join(authors_list)
        
        # Year
        date = zotero_data.get("date", "")
        year = date[:4] if date else ""
        
        prepend_lines = [title]
        if authors:
            prepend_lines.append(authors)
        if year:
            prepend_lines.append(year)
        prepend_header = " — ".join(prepend_lines)
        
        # Extract abstract
        content = str(record.content) if hasattr(record, "content") and record.content else ""
        abstract_text = ""
        
        if content:
            # Search first 10% or 2000 chars
            search_scope = content[:max(len(content)//10, 2000)]
            match = re.search(r'(?im)^abstract\s*$', search_scope)
            if match:
                start_idx = match.end()
                next_break = re.search(r'\n\s*\n', content[start_idx:])
                if next_break:
                    end_idx = start_idx + next_break.start()
                else:
                    end_idx = start_idx + 1500
                abstract_text = content[start_idx:end_idx].strip()
                
        # Merge small chunks from SemanticSplitter
        merged_chunks = []
        current_chunk_text = ""
        
        for chunk in record.chunks:
            text = chunk.chunk_text if hasattr(chunk, "chunk_text") else chunk.get("chunk_text", "")
            
            # Avoid duplicating abstract if it ended up in a chunk
            if abstract_text and text.strip() in abstract_text:
                continue
                
            if current_chunk_text:
                current_chunk_text += "\n" + text
            else:
                current_chunk_text = text
                
            if _count_tokens(current_chunk_text) >= self.min_chunk_size:
                merged_chunks.append(current_chunk_text)
                current_chunk_text = ""
                
        if current_chunk_text:
            if merged_chunks:
                merged_chunks[-1] += "\n" + current_chunk_text
            else:
                merged_chunks.append(current_chunk_text)
                
        # Build new chunks
        new_chunks = []
        chunk_idx = 0
        
        # 1. Abstract chunk
        if abstract_text:
            abs_chunk = record.chunks[0].model_copy(deep=True) if hasattr(record.chunks[0], "model_copy") else copy.deepcopy(record.chunks[0])
            prepended_abstract = f"{prepend_header}\nABSTRACT\n\n{abstract_text}"
            
            if hasattr(abs_chunk, "chunk_text"):
                abs_chunk.chunk_index = chunk_idx
                abs_chunk.chunk_id = f"{record.record_id}_{chunk_idx}"
                abs_chunk.metadata = abs_chunk.metadata.copy() if abs_chunk.metadata else {}
                abs_chunk.metadata["raw_text"] = abstract_text
                abs_chunk.chunk_text = prepended_abstract
            else:
                abs_chunk["chunk_index"] = chunk_idx
                abs_chunk["chunk_id"] = f"{record.record_id}_{chunk_idx}"
                if "metadata" not in abs_chunk: abs_chunk["metadata"] = {}
                abs_chunk["metadata"]["raw_text"] = abstract_text
                abs_chunk["chunk_text"] = prepended_abstract
            new_chunks.append(abs_chunk)
            chunk_idx += 1
            
        # 2. Regular chunks
        for text in merged_chunks:
            if abstract_text and abstract_text in text:
                text = text.replace(abstract_text, "").strip()
                if not text:
                    continue
                    
            c = record.chunks[0].model_copy(deep=True) if hasattr(record.chunks[0], "model_copy") else copy.deepcopy(record.chunks[0])
            raw_text = text
            prepended = f"{prepend_header}\n\n{text}"
            
            if hasattr(c, "chunk_text"):
                c.chunk_index = chunk_idx
                c.chunk_id = f"{record.record_id}_{chunk_idx}"
                c.metadata = c.metadata.copy() if c.metadata else {}
                c.metadata["raw_text"] = raw_text
                c.chunk_text = prepended
            else:
                c["chunk_index"] = chunk_idx
                c["chunk_id"] = f"{record.record_id}_{chunk_idx}"
                if "metadata" not in c: c["metadata"] = {}
                c["metadata"]["raw_text"] = raw_text
                c["chunk_text"] = prepended
            new_chunks.append(c)
            chunk_idx += 1
            
        if not new_chunks:
            logger.warning(f"Record {record.record_id} has no chunks after processing")
            return
            
        processed_record = record.model_copy(update={"chunks": new_chunks})
        yield processed_record

class RestoreTextProcessor(BaseModel):
    """Restores the original chunk text from metadata after embedding."""
    
    async def process(self, context: ProcessingContext) -> AsyncGenerator[Record, None]:
        """Restores the original chunk text from metadata after embedding."""
        record = context.record
        if not hasattr(record, "chunks") or not record.chunks:
            yield record
            return
            
        restored_chunks = []
        for chunk in record.chunks:
            c = chunk.model_copy(deep=True) if hasattr(chunk, "model_copy") else copy.deepcopy(chunk)
            if hasattr(c, "chunk_text"):
                raw_text = c.metadata.get("raw_text") if c.metadata else None
                if raw_text:
                    c.chunk_text = raw_text
                    # We can remove raw_text from metadata to avoid duplication
                    c.metadata.pop("raw_text", None)
            else:
                metadata = c.get("metadata", {})
                raw_text = metadata.get("raw_text")
                if raw_text:
                    c["chunk_text"] = raw_text
                    metadata.pop("raw_text", None)
            restored_chunks.append(c)
            
        processed_record = record.model_copy(update={"chunks": restored_chunks})
        yield processed_record
