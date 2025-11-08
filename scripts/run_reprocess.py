#!/usr/bin/env python3
"""Run the reprocessing pipeline for specific Zotero items.

This script runs the full vectorization pipeline on specific items
loaded from documents_to_remove_ids.txt.

Usage:
    uv run python scripts/run_reprocess.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from buttermilk import init_async, logger
from hydra import initialize_config_dir, compose


async def run_reprocessing_pipeline():
    """Run the reprocessing pipeline using conf/reprocess.yaml."""
    # Initialize Hydra config
    conf_dir = str(Path(__file__).parent.parent / "conf")

    # Initialize Hydra with absolute config path
    with initialize_config_dir(version_base="1.3", config_dir=conf_dir):
        # Load reprocess config
        cfg = compose(config_name="reprocess", overrides=["db=dev"])

        # Initialize Buttermilk infrastructure
        bm = await init_async(config=cfg)

        try:
            logger.info("Starting reprocessing pipeline for specific items")

            # Get pipeline orchestrator from config
            from hydra.utils import instantiate

            pipeline = instantiate(cfg.pipeline)

            # Run the pipeline (iterate over all results)
            count = 0
            async for record in pipeline():
                count += 1
                logger.info(f"Processed record {count}: {record.record_id}")

            logger.info(
                f"✅ Reprocessing pipeline completed successfully ({count} records processed)"
            )

        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}")
            raise

        finally:
            await bm.graceful_shutdown()


if __name__ == "__main__":
    asyncio.run(run_reprocessing_pipeline())
