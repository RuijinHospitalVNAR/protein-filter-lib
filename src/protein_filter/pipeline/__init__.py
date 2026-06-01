"""
Modular pipeline framework for protein structure analysis.

This module provides a flexible, extensible pipeline architecture following
best practices for computational protein drug design:

- **Pipeline composition**: Chain stages for complex workflows
- **Checkpoint/resume**: Automatic state persistence and recovery
- **Configuration-driven**: YAML/JSON config with validation
- **Model-agnostic**: Abstract interfaces for tool integration

Example:
    >>> from protein_filter.pipeline import Pipeline, PipelineConfig
    >>> from protein_filter.pipeline.stages import (
    ...     AF3ScoreFilteringStage,
    ...     FoldseekClusteringStage,
    ...     FineContactClusteringStage,
    ... )
    >>> 
    >>> config = PipelineConfig.from_yaml("config.yaml")
    >>> pipeline = Pipeline([
    ...     AF3ScoreFilteringStage(config.stage1),
    ...     FoldseekClusteringStage(config.stage2),
    ...     FineContactClusteringStage(config.stage3),
    ... ])
    >>> result = pipeline.run(input_data)
"""

from .base import (
    PipelineStage,
    Pipeline,
    PipelineData,
    StageResult,
)
from .config import (
    PipelineConfig,
    Stage1Config,
    Stage2Config,
    Stage3Config,
    FullPipelineConfig,
    Part2RunConfig,
    Part3RunConfig,
)
from .state import (
    PipelineRunState,
    Part2Checkpoint,
    load_pipeline_state,
    save_pipeline_state,
)
from .retry import retry, with_retry
from . import stage1
from . import stage2

__all__ = [
    # Base classes
    "PipelineStage",
    "Pipeline",
    "PipelineData",
    "StageResult",
    # Config classes
    "PipelineConfig",
    "Stage1Config",
    "Stage2Config",
    "Stage3Config",
    "FullPipelineConfig",
    "Part2RunConfig",
    "Part3RunConfig",
    # State
    "PipelineRunState",
    "Part2Checkpoint",
    "load_pipeline_state",
    "save_pipeline_state",
    # Retry
    "retry",
    "with_retry",
    "stage1",
    "stage2",
]
