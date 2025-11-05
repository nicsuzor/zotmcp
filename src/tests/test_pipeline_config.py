"""Tests for pipeline configuration loading.

Verifies that the vectorize.yaml pipeline configuration loads correctly
and includes the QualityFilterProcessor in the right position.
"""
import pytest
from hydra import compose, initialize_config_dir
from pathlib import Path


def test_vectorize_config_loads_successfully():
    """Test that vectorize.yaml loads without errors."""
    # Arrange
    config_dir = Path(__file__).parent.parent.parent / "conf"
    assert config_dir.exists(), f"Config directory not found: {config_dir}"

    # Act & Assert - should not raise any exceptions
    with initialize_config_dir(config_dir=str(config_dir.absolute()), version_base=None):
        cfg = compose(config_name="vectorize")

        # Verify basic structure
        assert "pipeline" in cfg
        assert "processors" in cfg.pipeline
        assert len(cfg.pipeline.processors) > 0


def test_quality_filter_processor_in_pipeline():
    """Test that QualityFilterProcessor is configured in the pipeline."""
    # Arrange
    config_dir = Path(__file__).parent.parent.parent / "conf"

    # Act
    with initialize_config_dir(config_dir=str(config_dir.absolute()), version_base=None):
        cfg = compose(config_name="vectorize")

        # Assert - find QualityFilterProcessor in processors
        processor_targets = [p._target_ for p in cfg.pipeline.processors]

        assert "src.quality_processor.QualityFilterProcessor" in processor_targets, \
            "QualityFilterProcessor not found in pipeline processors"


def test_quality_filter_processor_position():
    """Test that QualityFilterProcessor is positioned between chunking and embedding."""
    # Arrange
    config_dir = Path(__file__).parent.parent.parent / "conf"

    # Act
    with initialize_config_dir(config_dir=str(config_dir.absolute()), version_base=None):
        cfg = compose(config_name="vectorize")

        processor_targets = [p._target_ for p in cfg.pipeline.processors]

        # Find positions
        chunker_idx = None
        quality_idx = None
        embedding_idx = None

        for i, target in enumerate(processor_targets):
            if "SemanticSplitter" in target:
                chunker_idx = i
            elif "QualityFilterProcessor" in target:
                quality_idx = i
            elif "EmbeddingGenerator" in target:
                embedding_idx = i

        # Assert - quality filter should be after chunking and before embedding
        assert chunker_idx is not None, "SemanticSplitter not found"
        assert quality_idx is not None, "QualityFilterProcessor not found"
        assert embedding_idx is not None, "EmbeddingGenerator not found"

        assert chunker_idx < quality_idx, \
            f"QualityFilterProcessor (idx {quality_idx}) must come after SemanticSplitter (idx {chunker_idx})"

        assert quality_idx < embedding_idx, \
            f"QualityFilterProcessor (idx {quality_idx}) must come before EmbeddingGenerator (idx {embedding_idx})"


def test_quality_filter_processor_configuration():
    """Test that QualityFilterProcessor has correct threshold configuration."""
    # Arrange
    config_dir = Path(__file__).parent.parent.parent / "conf"

    # Act
    with initialize_config_dir(config_dir=str(config_dir.absolute()), version_base=None):
        cfg = compose(config_name="vectorize")

        # Find QualityFilterProcessor config
        quality_processor = None
        for p in cfg.pipeline.processors:
            if "QualityFilterProcessor" in p._target_:
                quality_processor = p
                break

        # Assert
        assert quality_processor is not None, "QualityFilterProcessor not found"
        assert hasattr(quality_processor, "corruption_threshold"), \
            "QualityFilterProcessor missing corruption_threshold"
        assert 1 <= quality_processor.corruption_threshold <= 100, \
            f"corruption_threshold must be in range 1-100, got {quality_processor.corruption_threshold}"
        assert hasattr(quality_processor, "pattern_threshold"), \
            "QualityFilterProcessor missing pattern_threshold"
        assert 1 <= quality_processor.pattern_threshold <= 100, \
            f"pattern_threshold must be in range 1-100, got {quality_processor.pattern_threshold}"
