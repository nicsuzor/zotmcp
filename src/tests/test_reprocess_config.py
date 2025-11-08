"""Tests for reprocess pipeline configuration.

Verifies that the reprocess.yaml configuration loads correctly
and uses ZoteroItemSource with the same processors as vectorize.yaml.
"""

from hydra import compose, initialize_config_dir
from pathlib import Path


def test_reprocess_config_loads_successfully():
    """Test that reprocess.yaml loads without errors."""
    # Arrange
    config_dir = Path(__file__).parent.parent.parent / "conf"
    assert config_dir.exists(), f"Config directory not found: {config_dir}"

    # Act & Assert - should not raise any exceptions
    with initialize_config_dir(
        config_dir=str(config_dir.absolute()), version_base=None
    ):
        cfg = compose(config_name="reprocess")

        # Verify basic structure
        assert "pipeline" in cfg
        assert "processors" in cfg.pipeline
        assert len(cfg.pipeline.processors) > 0


def test_reprocess_uses_zotero_item_source():
    """Test that reprocess.yaml uses ZoteroItemSource."""
    # Arrange
    config_dir = Path(__file__).parent.parent.parent / "conf"

    # Act
    with initialize_config_dir(
        config_dir=str(config_dir.absolute()), version_base=None
    ):
        cfg = compose(config_name="reprocess")

        # Assert
        assert cfg.pipeline.source._target_ == "src.zotero_items.ZoteroItemSource", (
            f"Expected ZoteroItemSource, got {cfg.pipeline.source._target_}"
        )

        assert hasattr(cfg.pipeline.source, "item_keys_file"), (
            "ZoteroItemSource missing item_keys_file parameter"
        )


def test_reprocess_has_same_processors_as_vectorize():
    """Test that reprocess.yaml has identical processors to vectorize.yaml."""
    # Arrange
    config_dir = Path(__file__).parent.parent.parent / "conf"

    # Act
    with initialize_config_dir(
        config_dir=str(config_dir.absolute()), version_base=None
    ):
        vectorize_cfg = compose(config_name="vectorize")
        reprocess_cfg = compose(config_name="reprocess")

        vectorize_targets = [p._target_ for p in vectorize_cfg.pipeline.processors]
        reprocess_targets = [p._target_ for p in reprocess_cfg.pipeline.processors]

        # Assert - same processors in same order
        assert vectorize_targets == reprocess_targets, (
            f"Processor mismatch:\nVectorize: {vectorize_targets}\nReprocess: {reprocess_targets}"
        )


def test_reprocess_quality_filter_configuration():
    """Test that reprocess.yaml has correct QualityFilterProcessor threshold."""
    # Arrange
    config_dir = Path(__file__).parent.parent.parent / "conf"

    # Act
    with initialize_config_dir(
        config_dir=str(config_dir.absolute()), version_base=None
    ):
        cfg = compose(config_name="reprocess")

        # Find QualityFilterProcessor config
        quality_processor = None
        for p in cfg.pipeline.processors:
            if "QualityFilterProcessor" in p._target_:
                quality_processor = p
                break

        # Assert
        assert quality_processor is not None, "QualityFilterProcessor not found"
        assert quality_processor.corruption_threshold == 80.0, (
            f"Expected corruption_threshold=80.0, got {quality_processor.corruption_threshold}"
        )
        assert quality_processor.pattern_threshold == 80.0, (
            f"Expected pattern_threshold=80.0, got {quality_processor.pattern_threshold}"
        )
