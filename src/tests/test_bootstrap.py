"""Test simplified bootstrap with ZotMCP."""

from pathlib import Path

from buttermilk import init_async
import pytest


@pytest.mark.anyio
async def test_bootstrap():
    """Test bootstrap."""
    print("Testing simplified bootstrap with ZotMCP config...")
    conf_dir = str(Path(__file__).parent.parent / "zotmcp" / "conf")
    try:
        bm = await init_async(config_dir=conf_dir, config_name="zotero")
    except Exception as e:
        if any(kw in str(e) for kw in ("credential", "GCP", "ZOTERO", "DefaultCredentials")):
            pytest.skip(f"External credentials not available: {e}")
        raise
    print(f"✅ Bootstrap successful!")
    print(f"   Project: {bm.session_info.project_name}")
    print(f"   Job: {bm.session_info.job}")
    print(f"   Session ID: {bm.session_info.session_id}")
    print(f"   Config type: {type(bm.cfg)}")

    # Test storage access
    if hasattr(bm.cfg, "storage") and "zotero_vectors" in bm.cfg.storage:
        storage = bm.cfg.get_storage_config("zotero_vectors")
        print(f"✅ Storage config accessible")
        print(f"   Collection: {storage.collection_name}")
        print(f"   Collection: {storage.persist_directory}")
