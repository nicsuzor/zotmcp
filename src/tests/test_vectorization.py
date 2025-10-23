#!/usr/bin/env python3
"""Integration tests for the Zotero vectorization pipeline.

Tests the complete pipeline from Zotero API fetch through text splitting
and embedding generation to verify proper record handling.
"""
import asyncio
import json
import pytest
from pathlib import Path
import sys
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from buttermilk import init_async, logger
from buttermilk.libs.zotero import ZoteroSource
from hydra.utils import instantiate


pytestmark = pytest.mark.anyio


class TestButtermilkBugs:
    """Test cases that reproduce bugs in the buttermilk library."""

    async def test_semantic_splitter_missing_title_attribute(self):
        """Reproduce bug: SemanticSplitter assumes all records have 'title' attribute.

        Bug location: buttermilk/data/vector.py:215
        Error: 'BaseRecord' object has no attribute 'title'

        The SemanticSplitter's process() method accesses doc.title without checking
        if the attribute exists. Some Zotero item types may not have titles.
        """
        from buttermilk.data.vector import SemanticSplitter
        from buttermilk._core.types import BaseRecord

        # Create a minimal record without a title attribute
        record = BaseRecord(
            record_id="TEST123",
            content="This is some test content that should be split into chunks.",
            metadata={"test": "metadata"}
        )

        # Verify the record doesn't have a title attribute
        assert not hasattr(record, "title"), "Test record shouldn't have title attribute"

        # Create semantic splitter
        splitter = SemanticSplitter(chunk_size=20, chunk_overlap=5)

        # This should fail with AttributeError: 'BaseRecord' object has no attribute 'title'
        # But buttermilk catches the exception and logs it, so we get 0 chunks
        chunks = []
        async for chunked_record in splitter.process(record):
            chunks.append(chunked_record)

        # Bug manifests as no chunks being generated (exception was caught and logged)
        if len(chunks) == 0:
            pytest.fail(
                "BUG REPRODUCED: SemanticSplitter failed to process record\n"
                "Root cause: 'BaseRecord' object has no attribute 'title'\n"
                "Location: buttermilk/data/vector.py:215\n"
                "Fix: Use getattr(doc, 'title', doc.record_id) instead of doc.title"
            )

        # If we get here, the bug is fixed!
        assert len(chunks) > 0, "Should have generated at least one chunk"


class TestVectorizationPipeline:
    """Test vectorization pipeline with potentially problematic records."""

    @pytest.fixture(scope="class")
    async def buttermilk_instance(self):
        """Initialize Buttermilk with vectorize config."""
        conf_dir = str(Path(__file__).parent.parent.parent / "conf")
        bm = await init_async(config_dir=conf_dir, config_name="vectorize", overrides=["db=upstream"])
        yield bm
        await bm.graceful_shutdown()

    @pytest.fixture(scope="class")
    async def zotero_source(self, buttermilk_instance):
        """Create a ZoteroSource instance for fetching items."""
        library_id = buttermilk_instance.cfg.pipeline.source.library_id
        save_dir = str(Path.home() / ".cache" / "buttermilk" / "zotero" / "state")
        return ZoteroSource(library_id=library_id, save_dir=save_dir)

    @pytest.mark.parametrize(
        "item_key,expected_type,description",
        [
            pytest.param(
                "B7ZX9ISZ",
                None,  # We'll accept any type
                "Record that caused 'BaseRecord' object has no attribute 'title' error",
                id="B7ZX9ISZ-title-error",
            ),
            # Add more problematic records here as they're discovered
            # pytest.param(
            #     "XXXXXXXX",
            #     "journalArticle",
            #     "Another problematic record",
            #     id="XXXXXXXX-description",
            # ),
        ],
    )
    async def test_record_conversion_through_pipeline(
        self,
        buttermilk_instance,
        zotero_source,
        item_key,
        expected_type,
        description,
    ):
        """Test that a Zotero record can be fetched and processed through the pipeline.

        Args:
            buttermilk_instance: Initialized Buttermilk instance
            zotero_source: ZoteroSource for fetching items
            item_key: Zotero item key to test
            expected_type: Expected Zotero itemType (or None to skip check)
            description: Description of why this record is being tested
        """
        # Step 1: Fetch the item from Zotero API
        zot = zotero_source.zot
        try:
            item = zot.item(item_key)
            logger.info(f"✓ Successfully fetched item {item_key} from Zotero API")
        except Exception as e:
            pytest.fail(f"Failed to fetch item {item_key} from Zotero API: {e}")

        # Step 2: Verify basic structure
        assert "data" in item, f"Item {item_key} missing 'data' field"
        item_data = item["data"]

        # Log item type for debugging
        item_type = item_data.get("itemType", "unknown")
        logger.info(f"Item type: {item_type}")

        if expected_type is not None:
            assert item_type == expected_type, f"Expected type {expected_type}, got {item_type}"

        # Step 3: Create a minimal pipeline with just the problematic processors
        # This tests the conversion from Zotero format to Buttermilk's internal format
        from buttermilk.libs.zotero import ZoteroDownloadProcessor
        from buttermilk.data.vector import SemanticSplitter

        # Create download processor
        download_processor = instantiate(
            buttermilk_instance.cfg.pipeline.processors[0]
        )

        # Create semantic splitter (this is where the error occurred)
        semantic_splitter = SemanticSplitter(chunk_size=500, chunk_overlap=200)

        # Step 4: Test ZoteroDownloadProcessor conversion
        # The ZoteroDownloadProcessor should convert Zotero items to BaseRecord format
        try:
            # Simulate what the pipeline does - create a record from the raw Zotero item
            from buttermilk.libs.zotero import ZoteroRecord

            # ZoteroSource converts items to ZoteroRecord objects
            # The record should have all necessary attributes
            record = ZoteroRecord(
                record_id=item_key,
                data=item_data,
                metadata={
                    "item_key": item_key,
                    "item_type": item_type,
                    "version": item.get("version"),
                },
            )

            logger.info(f"✓ Created ZoteroRecord for {item_key}")
            logger.info(f"Record attributes: {dir(record)}")

            # Check that the record has expected attributes
            assert hasattr(record, "record_id"), "Record missing 'record_id' attribute"

            # The BaseRecord or ZoteroRecord should have a way to get text
            # Let's check what attributes it has
            if hasattr(record, "title"):
                logger.info(f"Record has 'title' attribute: {record.title}")
            if hasattr(record, "text"):
                logger.info(f"Record has 'text' attribute (length: {len(record.text) if record.text else 0})")
            if hasattr(record, "content"):
                logger.info(f"Record has 'content' attribute (length: {len(record.content) if record.content else 0})")

        except AttributeError as e:
            pytest.fail(
                f"AttributeError during record creation for {item_key}: {e}\n"
                f"This is the error we're trying to fix. The record object is missing an expected attribute.\n"
                f"Item data: {item_data}"
            )
        except Exception as e:
            pytest.fail(f"Unexpected error during record creation for {item_key}: {e}")

        # Step 5: Test that SemanticSplitter can handle the record
        # The SemanticSplitter is where the original error occurred
        try:
            # Process through download processor first
            async def mock_generator():
                yield record

            processed_records = []
            async for processed in download_processor(mock_generator()):
                processed_records.append(processed)

            assert len(processed_records) > 0, "Download processor returned no records"
            logger.info(f"✓ Download processor returned {len(processed_records)} record(s)")

            # Now try to split the text
            for proc_record in processed_records:
                logger.info(f"Processing record type: {type(proc_record)}")
                logger.info(f"Record attributes: {dir(proc_record)}")

                # Check for the 'title' attribute that caused the original error
                if not hasattr(proc_record, "title"):
                    pytest.fail(
                        f"Processed record for {item_key} missing 'title' attribute.\n"
                        f"This is the root cause of the original error.\n"
                        f"Record type: {type(proc_record)}\n"
                        f"Available attributes: {dir(proc_record)}"
                    )

                # Try to run semantic splitter
                split_records = []
                async def single_record_gen():
                    yield proc_record

                async for split_record in semantic_splitter(single_record_gen()):
                    split_records.append(split_record)

                assert len(split_records) > 0, f"SemanticSplitter returned no chunks for {item_key}"
                logger.info(f"✓ SemanticSplitter created {len(split_records)} chunks")

        except AttributeError as e:
            pytest.fail(
                f"AttributeError during text splitting for {item_key}: {e}\n"
                f"This is the original error. The SemanticSplitter expects a 'title' attribute.\n"
                f"Record type after download processor: {type(processed_records[0]) if processed_records else 'no records'}\n"
                f"Item type from Zotero: {item_type}"
            )
        except Exception as e:
            pytest.fail(f"Unexpected error during text splitting for {item_key}: {e}")

        logger.info(f"✓ Successfully processed {item_key} through pipeline")

    async def test_fetch_item_from_zotero(self, zotero_source):
        """Basic test to verify we can fetch an item from Zotero."""
        zot = zotero_source.zot

        # Fetch the problematic item
        item_key = "B7ZX9ISZ"
        item = zot.item(item_key)

        # Basic assertions
        assert item is not None
        assert "data" in item
        assert "key" in item["data"]
        assert item["data"]["key"] == item_key

        logger.info(f"Item type: {item['data'].get('itemType')}")
        logger.info(f"Item has title: {'title' in item['data']}")

        # Check what fields the item has
        logger.info(f"Available fields: {list(item['data'].keys())}")


class TestZoteroRecordTypes:
    """Test different Zotero item types to understand their structure."""

    @pytest.fixture(scope="class")
    async def zotero_source(self):
        """Create a ZoteroSource instance."""
        from buttermilk import init_async

        conf_dir = str(Path(__file__).parent.parent.parent / "conf")
        bm = await init_async(config_dir=conf_dir, config_name="vectorize", overrides=["db=upstream"])
        library_id = bm.cfg.pipeline.source.library_id
        save_dir = str(Path.home() / ".cache" / "buttermilk" / "zotero" / "state")
        zs = ZoteroSource(library_id=library_id, save_dir=save_dir)
        yield zs
        await bm.graceful_shutdown()

    async def test_analyze_item_structure(self, zotero_source):
        """Analyze the structure of item B7ZX9ISZ to understand why it fails."""
        zot = zotero_source.zot
        item_key = "B7ZX9ISZ"

        item = zot.item(item_key)
        item_data = item["data"]

        logger.info(f"Item Key: {item_key}")
        logger.info(f"Item Type: {item_data.get('itemType')}")
        logger.info(f"Has 'title' field: {'title' in item_data}")
        logger.info(f"All fields: {sorted(item_data.keys())}")

        # Log relevant text fields
        for field in ["title", "abstractNote", "extra", "note"]:
            if field in item_data:
                value = item_data[field]
                logger.info(f"{field}: {value[:100] if value else 'empty'}...")

        # Check children
        children = zot.children(item_key)
        logger.info(f"Number of children: {len(children)}")
        for child in children:
            child_type = child["data"].get("itemType", "unknown")
            logger.info(f"  Child type: {child_type}")


class TestZoteroSyncDiagnostics:
    """Diagnostic tests to understand sync issues."""

    @pytest.fixture(scope="class")
    async def buttermilk_instance(self):
        """Initialize Buttermilk with vectorize config."""
        conf_dir = str(Path(__file__).parent.parent.parent / "conf")
        bm = await init_async(config_dir=conf_dir, config_name="vectorize", overrides=["db=upstream"])
        yield bm
        await bm.graceful_shutdown()

    async def test_check_recent_items_in_chromadb(self, buttermilk_instance):
        """Check if recently modified items from Zotero are in ChromaDB."""
        from buttermilk.libs.zotero import ZoteroSource
        from buttermilk.tools import ChromaDBSearchTool

        # Get Zotero source
        cfg = buttermilk_instance.cfg
        pipeline = cfg["pipeline"] if isinstance(cfg, dict) else cfg.pipeline
        source_cfg = pipeline["source"] if isinstance(pipeline, dict) else pipeline.source

        library_id = source_cfg["library_id"] if isinstance(source_cfg, dict) else source_cfg.library_id
        zotero_source = ZoteroSource(library_id=library_id, save_dir=str(Path.home() / ".cache/buttermilk/zotero/state"))
        zot = zotero_source.zot

        # Fetch 10 most recent items from Zotero
        recent_items = zot.items(limit=10, sort="dateModified", direction="desc")

        # Initialize ChromaDB search tool
        cfg = buttermilk_instance.cfg
        if hasattr(cfg, "storage"):
            storage = cfg.storage
        else:
            storage = cfg["storage"]

        if hasattr(storage, "zotero_vectors"):
            storage_config = storage.zotero_vectors
        else:
            storage_config = storage["zotero_vectors"]

        # Access config values
        if hasattr(storage_config, "collection_name"):
            collection_name = storage_config.collection_name
            persist_directory = storage_config.persist_directory
            embedding_model = storage_config.embedding_model
            dimensionality = storage_config.dimensionality
        else:
            collection_name = storage_config["collection_name"]
            persist_directory = storage_config["persist_directory"]
            embedding_model = storage_config["embedding_model"]
            dimensionality = storage_config["dimensionality"]

        search_tool = ChromaDBSearchTool(
            type="chromadb",
            collection_name=collection_name,
            persist_directory=persist_directory,
            embedding_model=embedding_model,
            dimensionality=dimensionality,
        )

        await search_tool.ensure_cache_initialized()
        collection = search_tool.collection

        logger.info("\n" + "="*80)
        logger.info("CHECKING RECENT ZOTERO ITEMS IN CHROMADB")
        logger.info("="*80 + "\n")

        for i, item in enumerate(recent_items, 1):
            item_data = item["data"]
            item_key = item_data["key"]
            item_version = item_data.get("version")
            item_modified = item_data.get("dateModified")
            item_type = item_data.get("itemType")

            # Check if this item exists in ChromaDB
            results = collection.get(
                where={"item_key": {"$eq": item_key}},
                include=["metadatas"]
            )

            in_chromadb = len(results["ids"]) > 0
            num_chunks = len(results["ids"]) if in_chromadb else 0

            logger.info(f"{i}. Item {item_key} (v{item_version})")
            logger.info(f"   Type: {item_type}")
            logger.info(f"   Modified: {item_modified}")
            logger.info(f"   In ChromaDB: {'YES' if in_chromadb else 'NO'}")
            if in_chromadb:
                logger.info(f"   Chunks in DB: {num_chunks}")
                # Check version in metadata
                if results["metadatas"]:
                    db_version = results["metadatas"][0].get("version")
                    logger.info(f"   DB version: {db_version}")

                # Get actual document content to see if it has fulltext
                content_results = collection.get(
                    where={"item_key": {"$eq": item_key}},
                    include=["documents", "metadatas"],
                    limit=3  # Just get first 3 chunks
                )

                if content_results["documents"]:
                    for idx, (doc, meta) in enumerate(zip(content_results["documents"], content_results["metadatas"])):
                        doc_preview = doc[:100] if doc else "(empty)"
                        logger.info(f"   Chunk {idx+1} preview: {doc_preview}...")
                        logger.info(f"   Chunk {idx+1} length: {len(doc) if doc else 0} chars")
                        # Check if it looks like actual fulltext or just metadata
                        has_content = doc and len(doc) > 100
                        logger.info(f"   Chunk {idx+1} has substantial content: {has_content}")
                else:
                    logger.info(f"   WARNING: In ChromaDB but no documents found!")
            logger.info("")

        logger.info("="*80 + "\n")

    async def test_check_if_recent_items_should_have_fulltext(self, buttermilk_instance):
        """Check if recent items from Zotero actually have attachments/PDFs that should be processed."""
        from buttermilk.libs.zotero import ZoteroSource

        # Get Zotero source
        cfg = buttermilk_instance.cfg
        pipeline = cfg["pipeline"] if isinstance(cfg, dict) else cfg.pipeline
        source_cfg = pipeline["source"] if isinstance(pipeline, dict) else pipeline.source

        library_id = source_cfg["library_id"] if isinstance(source_cfg, dict) else source_cfg.library_id
        zotero_source = ZoteroSource(library_id=library_id, save_dir=str(Path.home() / ".cache/buttermilk/zotero/state"))
        zot = zotero_source.zot

        # Fetch 10 most recent items from Zotero
        recent_items = zot.items(limit=10, sort="dateModified", direction="desc")

        logger.info("\n" + "="*80)
        logger.info("CHECKING IF RECENT ITEMS SHOULD HAVE FULLTEXT")
        logger.info("="*80 + "\n")

        for i, item in enumerate(recent_items, 1):
            item_data = item["data"]
            item_key = item_data["key"]
            item_version = item_data.get("version")
            item_type = item_data.get("itemType")
            title = item_data.get("title", "(no title)")

            logger.info(f"{i}. {item_key} (v{item_version}) - {item_type}")
            logger.info(f"   Title: {title[:80]}{'...' if len(title) > 80 else ''}")

            # Check for children (attachments, notes)
            children = zot.children(item_key)
            logger.info(f"   Children: {len(children)}")

            has_pdf = False
            has_snapshot = False
            has_fulltext_potential = False

            for child in children:
                child_data = child["data"]
                child_type = child_data.get("itemType")
                content_type = child_data.get("contentType", "")
                link_mode = child_data.get("linkMode", "")

                logger.info(f"     - {child_type}: {child_data.get('title', 'untitled')}")
                logger.info(f"       contentType: {content_type}, linkMode: {link_mode}")

                if child_type == "attachment":
                    if "pdf" in content_type.lower() or child_data.get("title", "").lower().endswith(".pdf"):
                        has_pdf = True
                        logger.info(f"       ✓ PDF attachment found!")
                    elif "snapshot" in child_data.get("title", "").lower():
                        has_snapshot = True
                        logger.info(f"       ✓ Snapshot found")

            # Check if the main item itself might have fulltext
            # Journal articles, conference papers, etc. might have abstracts
            abstract = item_data.get("abstractNote", "")
            extra = item_data.get("extra", "")

            if abstract and len(abstract) > 100:
                logger.info(f"   Has abstract: YES ({len(abstract)} chars)")
                has_fulltext_potential = True
            else:
                logger.info(f"   Has abstract: NO")

            # Determine if this SHOULD be in ChromaDB
            should_have_fulltext = has_pdf or (has_fulltext_potential and item_type in ["journalArticle", "conferencePaper", "book"])

            logger.info(f"   Has PDF: {has_pdf}")
            logger.info(f"   Has snapshot: {has_snapshot}")
            logger.info(f"   SHOULD have fulltext vectors: {should_have_fulltext}")

            if not should_have_fulltext:
                logger.info(f"   → CORRECT that this is NOT in ChromaDB (no fulltext available)")
            else:
                logger.info(f"   → SHOULD BE in ChromaDB but isn't!")

            logger.info("")

        logger.info("="*80 + "\n")


class TestZoteroSyncState:
    """Test Zotero sync state to verify cache freshness."""

    @pytest.fixture(scope="class")
    async def zotero_config(self):
        """Get Zotero configuration."""
        from buttermilk import init_async

        conf_dir = str(Path(__file__).parent.parent.parent / "conf")
        bm = await init_async(config_dir=conf_dir, config_name="vectorize", overrides=["db=upstream"])

        # Access config - it might be a dict or DictConfig
        cfg = bm.cfg
        if hasattr(cfg, "pipeline"):
            pipeline = cfg.pipeline
        else:
            pipeline = cfg["pipeline"]

        if hasattr(pipeline, "source"):
            library_id = pipeline.source.library_id
            save_dir = Path(pipeline.source.save_dir)
        else:
            library_id = pipeline["source"]["library_id"]
            save_dir = Path(pipeline["source"]["save_dir"])

        yield {"library_id": library_id, "save_dir": save_dir}
        await bm.graceful_shutdown()

    @pytest.fixture(scope="class")
    async def zotero_source(self, zotero_config):
        """Create a ZoteroSource instance."""
        return ZoteroSource(
            library_id=zotero_config["library_id"],
            save_dir=str(zotero_config["save_dir"]),
        )

    async def test_sync_state_freshness(self, zotero_config, zotero_source):
        """Compare local sync state cache with live Zotero API to check freshness.

        This test helps identify if the local sync cache is out of date.
        """
        # Get the sync state file path
        save_dir = zotero_config["save_dir"]
        library_id = zotero_config["library_id"]
        # Try both possible filenames
        sync_state_file = save_dir / ".zotero_sync_state.json"
        if not sync_state_file.exists():
            sync_state_file = save_dir / f"{library_id}_sync_state.json"

        logger.info(f"Sync state file: {sync_state_file}")

        # Read local sync state
        local_state = None
        local_exists = sync_state_file.exists()

        if local_exists:
            with open(sync_state_file, "r") as f:
                local_state = json.load(f)
            logger.info(f"Local sync state: {json.dumps(local_state, indent=2)}")
        else:
            logger.warning(f"Sync state file does not exist: {sync_state_file}")

        # Get live API state
        zot = zotero_source.zot

        # Get the library version from the API
        # The library version is returned in the Last-Modified-Version header
        # We can get it by fetching items with a limit of 1
        try:
            # Fetch just 1 item to get the current library version
            items = zot.items(limit=1, sort="dateModified", direction="desc")

            # The pyzotero library stores the last API response headers
            # We can access the library version from there
            current_version = zot.request.headers.get("Last-Modified-Version")

            if current_version:
                current_version = int(current_version)
                logger.info(f"Current library version from API: {current_version}")
            else:
                logger.warning("Could not get current library version from API")
                current_version = None

            # Get the most recently modified item
            if items:
                most_recent_item = items[0]
                most_recent_modified = most_recent_item["data"].get("dateModified")
                logger.info(f"Most recent item modified date: {most_recent_modified}")
                logger.info(f"Most recent item key: {most_recent_item['data']['key']}")
                logger.info(f"Most recent item type: {most_recent_item['data'].get('itemType')}")

                # Parse the modification date
                if most_recent_modified:
                    api_modified_dt = datetime.fromisoformat(most_recent_modified.replace("Z", "+00:00"))
                    logger.info(f"Most recent modification (parsed): {api_modified_dt}")

        except Exception as e:
            logger.error(f"Error fetching current API state: {e}")
            current_version = None
            most_recent_modified = None

        # Compare local and remote state
        if local_state and current_version is not None:
            local_version = local_state.get("last_version")
            local_timestamp = local_state.get("last_sync_timestamp")

            logger.info(f"\n{'='*80}")
            logger.info(f"SYNC STATE COMPARISON")
            logger.info(f"{'='*80}")
            logger.info(f"Local version:   {local_version}")
            logger.info(f"Current version: {current_version}")
            logger.info(f"Version diff:    {current_version - local_version if local_version else 'N/A'}")

            if local_timestamp:
                local_dt = datetime.fromisoformat(local_timestamp)
                now = datetime.now(timezone.utc)
                time_since_sync = now - local_dt

                logger.info(f"\nLocal sync time: {local_timestamp}")
                logger.info(f"Current time:    {now.isoformat()}")
                logger.info(f"Time since sync: {time_since_sync}")
                logger.info(f"Days since sync: {time_since_sync.days}")
                logger.info(f"Hours since sync: {time_since_sync.total_seconds() / 3600:.1f}")

            if most_recent_modified:
                logger.info(f"\nMost recent API modification: {most_recent_modified}")

            logger.info(f"{'='*80}\n")

            # Assertions to make the test fail if out of date
            if local_version != current_version:
                version_diff = current_version - local_version
                pytest.fail(
                    f"Local sync state is OUT OF DATE!\n"
                    f"Local version: {local_version}\n"
                    f"Current version: {current_version}\n"
                    f"Missing {version_diff} versions\n"
                    f"Last sync: {local_timestamp}\n"
                    f"Time since sync: {time_since_sync if local_timestamp else 'N/A'}"
                )
        elif not local_exists:
            pytest.fail(f"Sync state file does not exist at: {sync_state_file}")
        else:
            pytest.fail("Could not determine current API version")

    async def test_list_recent_modifications(self, zotero_source):
        """List the 10 most recently modified items from Zotero API."""
        zot = zotero_source.zot

        logger.info("\n" + "="*80)
        logger.info("RECENT MODIFICATIONS FROM ZOTERO API")
        logger.info("="*80 + "\n")

        # Fetch recent items
        items = zot.items(limit=10, sort="dateModified", direction="desc")

        for i, item in enumerate(items, 1):
            item_data = item["data"]
            logger.info(f"{i}. Key: {item_data['key']}")
            logger.info(f"   Type: {item_data.get('itemType', 'unknown')}")
            logger.info(f"   Modified: {item_data.get('dateModified', 'unknown')}")
            logger.info(f"   Version: {item_data.get('version', 'unknown')}")

            # Show title if available
            title = item_data.get("title", "")
            if title:
                logger.info(f"   Title: {title[:80]}{'...' if len(title) > 80 else ''}")
            logger.info("")

        logger.info("="*80 + "\n")

    async def test_check_sync_state_file_location(self, zotero_config):
        """Verify the sync state file location and contents."""
        save_dir = zotero_config["save_dir"]
        library_id = zotero_config["library_id"]

        logger.info(f"\nLibrary ID: {library_id}")
        logger.info(f"Save directory: {save_dir}")
        logger.info(f"Directory exists: {save_dir.exists()}")

        if save_dir.exists():
            logger.info(f"Directory contents:")
            for file in save_dir.iterdir():
                file_size = file.stat().st_size if file.is_file() else "dir"
                file_mtime = datetime.fromtimestamp(file.stat().st_mtime, tz=timezone.utc)
                logger.info(f"  - {file.name} ({file_size} bytes, modified: {file_mtime})")

        # Try both possible filenames
        sync_state_file = save_dir / ".zotero_sync_state.json"
        if not sync_state_file.exists():
            sync_state_file = save_dir / f"{library_id}_sync_state.json"

        logger.info(f"\nSync state file path: {sync_state_file}")
        logger.info(f"Sync state file exists: {sync_state_file.exists()}")

        if sync_state_file.exists():
            with open(sync_state_file, "r") as f:
                state = json.load(f)
            logger.info(f"Sync state contents:\n{json.dumps(state, indent=2)}")
