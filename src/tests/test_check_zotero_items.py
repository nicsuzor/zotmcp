"""Tests for check_zotero_items utility script.

This test file verifies that the script properly uses buttermilk infrastructure
to check if Zotero items exist in the library.

Testing approach:
- Uses real buttermilk config (bm_dev fixture)
- Tests against real Zotero API (integration test pattern)
- No mocking of internal code (only external API calls if needed)
"""

import pytest
from pathlib import Path
from pyzotero.zotero_errors import ResourceNotFoundError

# Import the module we're testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
import check_zotero_item


class TestCheckZoteroItems:
    """Test suite for check_zotero_item script using buttermilk infrastructure."""

    async def test_get_zotero_client_from_buttermilk(self, bm_dev):
        """Test that we can initialize Zotero client using buttermilk credentials.

        This verifies:
        - buttermilk config loads successfully
        - ZOTERO_LIBRARY_ID is available from environment
        - ZOTERO_API_KEY is available from buttermilk credentials
        - Zotero client can be created with these credentials
        """
        # Get library_id from environment (how vectorize.yaml does it)
        import os
        library_id = os.environ.get("ZOTERO_LIBRARY_ID")
        assert library_id is not None, "ZOTERO_LIBRARY_ID must be set in environment"

        # Get API key from buttermilk credentials
        api_key = bm_dev.credentials.get("ZOTERO_API_KEY")
        assert api_key is not None, "ZOTERO_API_KEY must be available in buttermilk credentials"

        # Create Zotero client using buttermilk credentials
        from pyzotero import zotero
        zot = zotero.Zotero(
            library_id=library_id,
            library_type="group",
            api_key=api_key
        )

        # Verify client is initialized
        assert zot is not None
        assert zot.library_id == library_id

    async def test_check_item_exists(self, bm_dev):
        """Test checking a Zotero item that exists.

        Uses a known item from the Zotero library to verify the check_item
        function works correctly with real API.

        NOTE: This test requires an actual Zotero item to exist. If this test
        fails, it might be because the test item was deleted from Zotero.
        """
        import os
        from pyzotero import zotero

        # Get credentials from buttermilk
        library_id = os.environ.get("ZOTERO_LIBRARY_ID")
        api_key = bm_dev.credentials.get("ZOTERO_API_KEY")

        # Create client
        zot = zotero.Zotero(
            library_id=library_id,
            library_type="group",
            api_key=api_key
        )

        # Get a real item from the library to test with
        # We'll fetch one item and use its key for the test
        items = zot.items(limit=1)
        if not items:
            pytest.skip("No items in Zotero library to test with")

        test_item_key = items[0]["key"]

        # Now test check_item function
        result = check_zotero_item.check_item(zot, test_item_key)

        # Verify result structure
        assert result["exists"] is True
        assert "item_type" in result
        assert "title" in result
        assert "has_pdf" in result
        assert "error" not in result

    async def test_check_item_not_found(self, bm_dev):
        """Test checking a Zotero item that does NOT exist (404).

        Uses a fake item ID to verify the check_item function correctly
        handles items that don't exist.
        """
        import os
        from pyzotero import zotero

        # Get credentials from buttermilk
        library_id = os.environ.get("ZOTERO_LIBRARY_ID")
        api_key = bm_dev.credentials.get("ZOTERO_API_KEY")

        # Create client
        zot = zotero.Zotero(
            library_id=library_id,
            library_type="group",
            api_key=api_key
        )

        # Use a fake item ID that definitely doesn't exist
        fake_item_key = "FAKEFAKE"

        # Test check_item function
        result = check_zotero_item.check_item(zot, fake_item_key)

        # Verify result structure for non-existent item
        assert result["exists"] is False
        assert "error" in result
        assert "404" in result["error"] or "does not exist" in result["error"].lower()

    async def test_read_item_ids_from_file(self, tmp_path):
        """Test reading item IDs from a file.

        Verifies that the read_item_ids_from_file function correctly:
        - Reads item IDs from a text file (one per line)
        - Strips whitespace
        - Filters out empty lines
        """
        # Create a temporary test file
        test_file = tmp_path / "test_items.txt"
        test_file.write_text("""
ITEM001
ITEM002

ITEM003
        ITEM004

""")

        # Read item IDs
        item_ids = check_zotero_item.read_item_ids_from_file(str(test_file))

        # Verify results
        assert len(item_ids) == 4
        assert item_ids == ["ITEM001", "ITEM002", "ITEM003", "ITEM004"]
