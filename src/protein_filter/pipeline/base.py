"""
Base classes for the modular pipeline framework.

Provides:
- PipelineStage: Abstract base class for pipeline stages
- Pipeline: Orchestrates stage execution with checkpoint/resume
- PipelineData: Typed data container for inter-stage communication
- StageResult: Result container with status and metrics
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Generic
import json
import logging
import time
import psutil
import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class PerformanceMetrics:
    """Performance metrics for a pipeline stage or overall run."""
    
    wall_clock_time_seconds: float = 0.0
    cpu_time_user_seconds: float = 0.0
    cpu_time_system_seconds: float = 0.0
    peak_memory_rss_mb: float = 0.0
    peak_memory_vms_mb: float = 0.0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    
    @property
    def wall_clock_time_formatted(self) -> str:
        """Format wall clock time as 'Xh Ym Zs'."""
        t = self.wall_clock_time_seconds
        hours = int(t // 3600)
        minutes = int((t % 3600) // 60)
        seconds = t % 60
        return f"{hours}h {minutes}m {seconds:.1f}s"
    
    @property
    def cpu_utilization_percent(self) -> float:
        """Calculate CPU utilization percentage."""
        if self.wall_clock_time_seconds <= 0:
            return 0.0
        total_cpu = self.cpu_time_user_seconds + self.cpu_time_system_seconds
        return (total_cpu / self.wall_clock_time_seconds) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "wall_clock_time_seconds": self.wall_clock_time_seconds,
            "wall_clock_time_formatted": self.wall_clock_time_formatted,
            "cpu_time_user_seconds": self.cpu_time_user_seconds,
            "cpu_time_system_seconds": self.cpu_time_system_seconds,
            "cpu_utilization_percent": self.cpu_utilization_percent,
            "peak_memory_rss_mb": self.peak_memory_rss_mb,
            "peak_memory_vms_mb": self.peak_memory_vms_mb,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


@dataclass
class StructureMetrics:
    """Metrics for a single predicted structure."""
    
    file_path: str
    plddt: Optional[float] = None
    iptm: Optional[float] = None
    ptm: Optional[float] = None
    ipsae: Optional[float] = None
    pdockq: Optional[float] = None
    pdockq2: Optional[float] = None
    clashes: Optional[int] = None
    ranking_confidence: Optional[float] = None
    
    # Additional ipSAE variants
    ipsae_d0chn: Optional[float] = None
    ipsae_d0dom: Optional[float] = None
    
    # Raw metrics dictionary for extensibility
    raw_metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "file_path": self.file_path,
            "plddt": self.plddt,
            "iptm": self.iptm,
            "ptm": self.ptm,
            "ipsae": self.ipsae,
            "pdockq": self.pdockq,
            "pdockq2": self.pdockq2,
            "clashes": self.clashes,
            "ranking_confidence": self.ranking_confidence,
        }
        # Add non-None optional fields
        if self.ipsae_d0chn is not None:
            result["ipsae_d0chn"] = self.ipsae_d0chn
        if self.ipsae_d0dom is not None:
            result["ipsae_d0dom"] = self.ipsae_d0dom
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructureMetrics":
        """Create from dictionary."""
        return cls(
            file_path=data.get("file_path", ""),
            plddt=data.get("plddt"),
            iptm=data.get("iptm"),
            ptm=data.get("ptm"),
            ipsae=data.get("ipsae"),
            pdockq=data.get("pdockq"),
            pdockq2=data.get("pdockq2"),
            clashes=data.get("clashes"),
            ranking_confidence=data.get("ranking_confidence"),
            ipsae_d0chn=data.get("ipsae_d0chn"),
            ipsae_d0dom=data.get("ipsae_d0dom"),
            raw_metrics=data.get("raw_metrics", {}),
        )


@dataclass
class ClusterInfo:
    """Information about a cluster of structures."""
    
    cluster_id: int
    file_names: List[str]
    representative: Optional[str] = None
    method: str = "unknown"
    
    @property
    def size(self) -> int:
        return len(self.file_names)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "file_names": self.file_names,
            "representative": self.representative,
            "method": self.method,
            "size": self.size,
        }


@dataclass
class PipelineData:
    """
    Typed data container for inter-stage communication.
    
    Carries all data between pipeline stages, including:
    - Input configuration
    - Intermediate results
    - Metrics and statistics
    """
    
    stage: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Input data
    pdb_dir: Optional[Path] = None
    chain_a: str = "H"
    antigen_chains: List[str] = field(default_factory=lambda: ["A"])
    
    # Stage 1 results
    all_structure_metrics: Dict[str, StructureMetrics] = field(default_factory=dict)
    filtered_files: List[str] = field(default_factory=list)
    filter_stats: Dict[str, int] = field(default_factory=dict)
    
    # Stage 2 results
    coarse_clusters: Dict[int, ClusterInfo] = field(default_factory=dict)
    
    # Stage 3 results
    fine_clusters: Dict[int, ClusterInfo] = field(default_factory=dict)
    fine_labels: Optional[np.ndarray] = None
    
    # Performance tracking
    stage_performance: Dict[str, PerformanceMetrics] = field(default_factory=dict)
    
    # Arbitrary metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        def _to_json_safe(obj):
            if isinstance(obj, dict):
                return {k: _to_json_safe(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_to_json_safe(x) for x in obj]
            if isinstance(obj, (np.integer, np.int64, np.int32)):
                return int(obj)
            if isinstance(obj, (np.floating, np.float64, np.float32)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return _to_json_safe(obj.tolist())
            if isinstance(obj, Path):
                return str(obj)
            if isinstance(obj, (StructureMetrics, ClusterInfo, PerformanceMetrics)):
                return obj.to_dict()
            return obj
        
        return _to_json_safe({
            "stage": self.stage,
            "timestamp": self.timestamp,
            "pdb_dir": str(self.pdb_dir) if self.pdb_dir else None,
            "chain_a": self.chain_a,
            "antigen_chains": self.antigen_chains,
            "filtered_files": self.filtered_files,
            "filter_stats": self.filter_stats,
            "coarse_clusters": {
                str(k): v.to_dict() if isinstance(v, ClusterInfo) else v
                for k, v in self.coarse_clusters.items()
            },
            "fine_clusters": {
                str(k): v.to_dict() if isinstance(v, ClusterInfo) else v
                for k, v in self.fine_clusters.items()
            },
            "fine_labels": self.fine_labels.tolist() if self.fine_labels is not None else None,
            "stage_performance": {
                k: v.to_dict() if isinstance(v, PerformanceMetrics) else v
                for k, v in self.stage_performance.items()
            },
            "metadata": self.metadata,
        })


@dataclass
class StageResult:
    """Result container for a pipeline stage."""
    
    success: bool
    data: PipelineData
    performance: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data.to_dict(),
            "performance": self.performance.to_dict(),
            "error_message": self.error_message,
        }


# ============================================================================
# Abstract Base Classes
# ============================================================================

class PipelineStage(ABC):
    """
    Abstract base class for pipeline stages.
    
    Each stage must implement:
    - name: Unique identifier for the stage
    - process(): Core processing logic
    
    Provides:
    - Performance monitoring
    - Logging
    - Checkpoint save/load
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize stage with optional configuration.
        
        Args:
            config: Stage-specific configuration dictionary
        """
        self._config = config or {}
        self._logger = logging.getLogger(f"{__name__}.{self.name}")
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this stage."""
        pass
    
    @abstractmethod
    def process(self, data: PipelineData) -> StageResult:
        """
        Execute the stage's core processing logic.
        
        Args:
            data: Input data from previous stage
            
        Returns:
            StageResult containing updated data and performance metrics
        """
        pass
    
    @property
    def config(self) -> Dict[str, Any]:
        """Get stage configuration."""
        return self._config
    
    def log_start(self, data: PipelineData) -> None:
        """Log stage start."""
        self._logger.info(f"=" * 60)
        self._logger.info(f"Stage: {self.name}")
        self._logger.info(f"=" * 60)
    
    def log_end(self, result: StageResult) -> None:
        """Log stage completion with performance summary."""
        perf = result.performance
        status = "SUCCESS" if result.success else "FAILED"
        self._logger.info(f"Stage {self.name} {status}")
        self._logger.info(f"  Wall time: {perf.wall_clock_time_formatted}")
        self._logger.info(f"  CPU util: {perf.cpu_utilization_percent:.1f}%")
        self._logger.info(f"  Peak memory: {perf.peak_memory_rss_mb:.1f} MB")
    
    def log_error(self, error: Exception, data: PipelineData) -> None:
        """Log stage error."""
        self._logger.error(f"Stage {self.name} failed: {error}", exc_info=True)
    
    def run(self, data: PipelineData) -> StageResult:
        """
        Execute stage with performance monitoring.
        
        This method wraps process() with:
        - Performance monitoring
        - Error handling
        - Logging
        
        Args:
            data: Input data from previous stage
            
        Returns:
            StageResult with performance metrics
        """
        self.log_start(data)
        
        # Start performance monitoring
        process = psutil.Process()
        start_time = time.time()
        start_cpu = process.cpu_times()
        start_mem = process.memory_info()
        
        try:
            result = self.process(data)
            
            # Capture end performance
            end_time = time.time()
            end_cpu = process.cpu_times()
            end_mem = process.memory_info()
            
            # Calculate metrics
            result.performance = PerformanceMetrics(
                wall_clock_time_seconds=end_time - start_time,
                cpu_time_user_seconds=end_cpu.user - start_cpu.user,
                cpu_time_system_seconds=end_cpu.system - start_cpu.system,
                peak_memory_rss_mb=end_mem.rss / 1024 / 1024,
                peak_memory_vms_mb=end_mem.vms / 1024 / 1024,
                start_time=datetime.fromtimestamp(start_time).isoformat(),
                end_time=datetime.fromtimestamp(end_time).isoformat(),
            )
            
            # Update data with performance
            result.data.stage_performance[self.name] = result.performance
            
            self.log_end(result)
            return result
            
        except Exception as e:
            self.log_error(e, data)
            
            # Capture performance even on failure
            end_time = time.time()
            end_mem = process.memory_info()
            
            perf = PerformanceMetrics(
                wall_clock_time_seconds=end_time - start_time,
                peak_memory_rss_mb=end_mem.rss / 1024 / 1024,
                start_time=datetime.fromtimestamp(start_time).isoformat(),
                end_time=datetime.fromtimestamp(end_time).isoformat(),
            )
            
            return StageResult(
                success=False,
                data=data,
                performance=perf,
                error_message=str(e),
            )
    
    def save_checkpoint(self, data: PipelineData, output_dir: Path) -> Path:
        """
        Save stage checkpoint for resume capability.
        
        Args:
            data: Current pipeline data
            output_dir: Directory to save checkpoint
            
        Returns:
            Path to saved checkpoint file
        """
        checkpoint_path = output_dir / f"{self.name}_checkpoint.json"
        with open(checkpoint_path, 'w') as f:
            json.dump(data.to_dict(), f, indent=2)
        self._logger.info(f"Saved checkpoint: {checkpoint_path}")
        return checkpoint_path
    
    def load_checkpoint(self, output_dir: Path) -> Optional[PipelineData]:
        """
        Load stage checkpoint if exists.
        
        Args:
            output_dir: Directory containing checkpoint
            
        Returns:
            PipelineData if checkpoint exists, None otherwise
        """
        checkpoint_path = output_dir / f"{self.name}_checkpoint.json"
        if not checkpoint_path.exists():
            return None
        
        try:
            with open(checkpoint_path, 'r') as f:
                data_dict = json.load(f)
            self._logger.info(f"Loaded checkpoint: {checkpoint_path}")
            # TODO: Implement full deserialization
            return None  # Placeholder - needs proper deserialization
        except Exception as e:
            self._logger.warning(f"Failed to load checkpoint: {e}")
            return None


class Pipeline:
    """
    Orchestrates execution of multiple pipeline stages.
    
    Features:
    - Sequential stage execution
    - Checkpoint/resume support
    - Performance aggregation
    - Error handling with partial results
    """
    
    def __init__(
        self,
        stages: List[PipelineStage],
        output_dir: Optional[Path] = None,
        resume: bool = False,
    ):
        """
        Initialize pipeline with stages.
        
        Args:
            stages: List of PipelineStage instances to execute
            output_dir: Directory for outputs and checkpoints
            resume: Whether to resume from last checkpoint
        """
        self.stages = stages
        self.output_dir = output_dir
        self.resume = resume
        self._logger = logging.getLogger(__name__)
    
    def run(self, input_data: PipelineData) -> StageResult:
        """
        Execute all stages in sequence.
        
        Args:
            input_data: Initial pipeline data
            
        Returns:
            Final StageResult with aggregated performance
        """
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        
        data = input_data
        start_idx = 0
        
        # Resume from checkpoint if requested
        if self.resume and self.output_dir:
            for i, stage in enumerate(self.stages):
                checkpoint_data = stage.load_checkpoint(self.output_dir)
                if checkpoint_data:
                    data = checkpoint_data
                    start_idx = i + 1
                    self._logger.info(f"Resuming from stage {i + 1}: {stage.name}")
        
        # Execute stages
        overall_start = time.time()
        
        for i, stage in enumerate(self.stages[start_idx:], start=start_idx):
            self._logger.info(f"Running stage {i + 1}/{len(self.stages)}: {stage.name}")
            
            result = stage.run(data)
            
            if not result.success:
                self._logger.error(f"Pipeline failed at stage {stage.name}")
                return result
            
            data = result.data
            
            # Save checkpoint after each successful stage
            if self.output_dir:
                stage.save_checkpoint(data, self.output_dir)
        
        # Calculate overall performance
        overall_time = time.time() - overall_start
        overall_perf = PerformanceMetrics(
            wall_clock_time_seconds=overall_time,
            start_time=datetime.fromtimestamp(overall_start).isoformat(),
            end_time=datetime.now().isoformat(),
        )
        
        # Aggregate stage performances
        if data.stage_performance:
            total_cpu_user = sum(p.cpu_time_user_seconds for p in data.stage_performance.values())
            total_cpu_sys = sum(p.cpu_time_system_seconds for p in data.stage_performance.values())
            max_mem = max(p.peak_memory_rss_mb for p in data.stage_performance.values())
            
            overall_perf.cpu_time_user_seconds = total_cpu_user
            overall_perf.cpu_time_system_seconds = total_cpu_sys
            overall_perf.peak_memory_rss_mb = max_mem
        
        return StageResult(
            success=True,
            data=data,
            performance=overall_perf,
        )
    
    def get_stage_by_name(self, name: str) -> Optional[PipelineStage]:
        """Get a stage by its name."""
        for stage in self.stages:
            if stage.name == name:
                return stage
        return None
