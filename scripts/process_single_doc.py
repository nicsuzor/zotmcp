#!/usr/bin/env python3
"""Process a single document through the full vectorization pipeline.

This script runs the complete Zotero vectorization pipeline on a single
document ID, including all processing stages from download to embedding.

Usage:
    python scripts/process_single_doc.py <document_id>

Example:
    python scripts/process_single_doc.py 8ZBKLI6J
    python scripts/process_single_doc.py 7QFG7PW3

Pipeline stages:
1. ZoteroDownloadProcessor - Download PDF from Zotero
2. PDFToTextProcessor - Extract text from PDF
3. Citator - Generate citation using LLM
4. SemanticSplitter - Chunk text semantically
5. QualityFilterProcessor - Filter corrupt documents (80% threshold)
6. EmbeddingGenerator - Generate embeddings
7. ChromaDBEmbeddings - Store in ChromaDB
"""

import asyncio
import sys
from pathlib import Path

import click
from hydra import initialize_config_dir, compose
from hydra.utils import instantiate

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from buttermilk import init_async, logger


async def process_single_document(document_id: str) -> dict:
    """Process a single document through the vectorization pipeline.

    Args:
        document_id: Zotero document ID to process

    Returns:
        dict: Processing results with keys:
        - success: bool
        - document_id: str
        - stages_completed: list of completed stage names
        - error: str (if failed)
        - quality_metrics: dict (if quality check performed)
    """
    # Initialize Hydra config
    conf_dir = str(Path(__file__).parent.parent / "conf")

    # Initialize Hydra with absolute config path
    with initialize_config_dir(version_base="1.3", config_dir=conf_dir):
        # Load vectorize config
        cfg = compose(
            config_name="vectorize",
            overrides=[
                "db=dev",
                "run.limit=1",  # Limit to 1 document
            ],
        )

        # Initialize Buttermilk infrastructure
        bm = await init_async(config=cfg)

        result = {
            "success": False,
            "document_id": document_id,
            "stages_completed": [],
            "error": None,
            "quality_metrics": None,
        }

        try:
            logger.info(f"Starting pipeline for document: {document_id}")

            # Create a minimal record to feed into the pipeline processors
            from buttermilk._core.types import Record

            record = Record(
                record_id=document_id,
                metadata={"document_id": document_id},
            )

            # Instantiate all processors from config
            processors = []
            pipeline_cfg = cfg.pipeline if hasattr(cfg, "pipeline") else cfg["pipeline"]
            processor_configs = (
                pipeline_cfg.processors
                if hasattr(pipeline_cfg, "processors")
                else pipeline_cfg["processors"]
            )

            for processor_config in processor_configs:
                processor = instantiate(processor_config)
                processors.append(processor)

            # Run record through all processors sequentially
            current_records = [record]
            processor_names = [
                "ZoteroDownloadProcessor",
                "PDFToTextProcessor",
                "Citator",
                "SemanticSplitter",
                "QualityFilterProcessor",
                "EmbeddingGenerator",
                "ChromaDBEmbeddings",
            ]

            for idx, processor in enumerate(processors):
                processor_name = (
                    processor_names[idx]
                    if idx < len(processor_names)
                    else f"Processor{idx}"
                )
                logger.info(f"Running {processor_name}...")

                next_records = []
                for rec in current_records:
                    async for processed_rec in processor.process(
                        rec, processor_stage=processor_name
                    ):
                        next_records.append(processed_rec)

                current_records = next_records
                result["stages_completed"].append(processor_name)

                # If no records left, document was filtered
                if not current_records:
                    logger.warning(f"Document filtered at stage: {processor_name}")
                    break

            if current_records:
                result["success"] = True
                final_record = current_records[0]

                # Extract quality metrics if available
                if hasattr(final_record, "chunks"):
                    result["quality_metrics"] = {
                        "chunk_count": len(final_record.chunks),
                    }

                logger.info(
                    f"✅ Document {document_id} processed successfully",
                    document_id=document_id,
                    stages=len(result["stages_completed"]),
                )
            else:
                result["error"] = (
                    "Document filtered by quality check (corruption >= 80%)"
                )
                logger.warning(
                    f"⚠️ Document {document_id} filtered by quality check",
                    document_id=document_id,
                )

        except Exception as e:
            result["error"] = str(e)
            logger.error(
                f"❌ Failed to process document {document_id}",
                document_id=document_id,
                error=str(e),
            )

        finally:
            await bm.graceful_shutdown()

        return result


@click.command()
@click.argument("document_id")
def main(document_id: str):
    """Process a single document through the vectorization pipeline.

    This runs the full pipeline on one document ID:
    - Download PDF from Zotero
    - Extract text
    - Generate citation
    - Semantic chunking
    - Quality filtering (80% threshold)
    - Generate embeddings
    - Store in ChromaDB

    DOCUMENT_ID: Zotero document ID to process (e.g., 8ZBKLI6J)

    Example:
        python scripts/process_single_doc.py 8ZBKLI6J
    """
    click.echo("Single Document Pipeline Processor")
    click.echo("=" * 80)
    click.echo(f"Document ID: {document_id}")
    click.echo()

    # Run processing
    click.echo("Starting pipeline...")
    result = asyncio.run(process_single_document(document_id))

    # Display results
    click.echo("\n" + "=" * 80)
    click.echo("PROCESSING RESULT")
    click.echo("=" * 80)
    click.echo(f"Document ID: {result['document_id']}")
    click.echo(f"Success: {result['success']}")

    if result["success"]:
        click.echo(f"Stages completed: {len(result['stages_completed'])}")

        if result["quality_metrics"]:
            click.echo("\nQuality Metrics:")
            for key, value in result["quality_metrics"].items():
                click.echo(f"  {key}: {value}")

        click.echo("\n✅ Document processed successfully and stored in ChromaDB")

    else:
        click.echo("\n❌ Processing failed")
        if result["error"]:
            click.echo(f"Error: {result['error']}")

        if "filtered by quality check" in (result["error"] or ""):
            click.echo(
                "\nNote: Document was filtered due to high corruption rate (>= 80%)"
            )
            click.echo("This is expected behavior for corrupt documents.")

    click.echo("=" * 80)


if __name__ == "__main__":
    main()
