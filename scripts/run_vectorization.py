#!/usr/bin/env python
"""Run the Zotero vectorization pipeline.

Usage:
    python scripts/run_vectorization.py
    python scripts/run_vectorization.py pipeline.max_records=10
"""
import asyncio
import sys

import hydra
from omegaconf import DictConfig

from buttermilk import logger, init_async


async def run_pipeline(cfg: DictConfig) -> None:
    """Run the vectorization pipeline."""

    # Initialize Buttermilk infrastructure
    bm = await init_async(config=cfg)
    logger.info("Buttermilk initialized")

    # Get pipeline from config (already instantiated by init_async)
    pipeline = bm.cfg.pipeline
    logger.info(
        f"Pipeline '{pipeline.pipeline_name}' ready",
        max_records=pipeline.max_records,
        concurrency=pipeline.concurrency
    )

    # Run the pipeline
    processed = 0
    try:
        async for record in pipeline():
            processed += 1
            if processed % 10 == 0:
                logger.info(f"Processed {processed} records so far...")

        logger.info(f"✅ Pipeline complete! Processed {processed} records total")

    except KeyboardInterrupt:
        logger.warning(f"⚠️ Pipeline interrupted. Processed {processed} records before stopping.")
    except Exception as e:
        logger.error(f"❌ Pipeline failed after {processed} records", error=str(e))
        raise
    finally:
        await bm.graceful_shutdown()


@hydra.main(version_base="1.3", config_path="../conf", config_name="vectorize")
def main(cfg: DictConfig) -> None:
    """Entry point - loads config and runs async pipeline."""
    asyncio.run(run_pipeline(cfg))


if __name__ == "__main__":
    main()
