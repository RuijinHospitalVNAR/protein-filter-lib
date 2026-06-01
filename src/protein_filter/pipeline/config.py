"""
Configuration classes for the pipeline framework.

Provides typed, validated configuration for all pipeline stages.
Supports loading from YAML/JSON files.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)

# Try to import yaml, fall back gracefully
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class Stage1Config:
    """Configuration for Stage 1: AF3 Score Filtering."""
    
    # Thresholds
    plddt_threshold: float = 0.7
    clashes_threshold: int = 5
    pdockq_threshold: float = 0.2
    iptm_threshold: float = 0.6
    ranking_confidence_threshold: float = 0.7
    ipsae_threshold: float = 0.6
    
    # Processing options
    n_jobs: int = 8
    compute_ipsae: bool = True
    ipsae_pae_cutoff: float = 5.0
    ipsae_dist_cutoff: float = 5.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plddt_threshold": self.plddt_threshold,
            "clashes_threshold": self.clashes_threshold,
            "pdockq_threshold": self.pdockq_threshold,
            "iptm_threshold": self.iptm_threshold,
            "ranking_confidence_threshold": self.ranking_confidence_threshold,
            "ipsae_threshold": self.ipsae_threshold,
            "n_jobs": self.n_jobs,
            "compute_ipsae": self.compute_ipsae,
            "ipsae_pae_cutoff": self.ipsae_pae_cutoff,
            "ipsae_dist_cutoff": self.ipsae_dist_cutoff,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Stage1Config":
        return cls(
            plddt_threshold=data.get("plddt_threshold", 0.7),
            clashes_threshold=data.get("clashes_threshold", 5),
            pdockq_threshold=data.get("pdockq_threshold", 0.2),
            iptm_threshold=data.get("iptm_threshold", 0.6),
            ranking_confidence_threshold=data.get("ranking_confidence_threshold", 0.7),
            ipsae_threshold=data.get("ipsae_threshold", 0.6),
            n_jobs=data.get("n_jobs", 8),
            compute_ipsae=data.get("compute_ipsae", True),
            ipsae_pae_cutoff=data.get("ipsae_pae_cutoff", 5.0),
            ipsae_dist_cutoff=data.get("ipsae_dist_cutoff", 5.0),
        )


@dataclass
class Stage2Config:
    """Configuration for Stage 2: Foldseek Coarse Clustering."""
    
    # Foldseek parameters
    foldseek_path: str = "/mnt/share/public/foldseek/bin/foldseek"
    sensitivity: float = 7.5
    coverage: float = 0.0
    min_seq_id: float = 0.0
    
    # Processing options
    n_jobs: int = 8
    skip_foldseek: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "foldseek_path": self.foldseek_path,
            "sensitivity": self.sensitivity,
            "coverage": self.coverage,
            "min_seq_id": self.min_seq_id,
            "n_jobs": self.n_jobs,
            "skip_foldseek": self.skip_foldseek,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Stage2Config":
        return cls(
            foldseek_path=data.get("foldseek_path", "/mnt/share/public/foldseek/bin/foldseek"),
            sensitivity=data.get("sensitivity", 7.5),
            coverage=data.get("coverage", 0.0),
            min_seq_id=data.get("min_seq_id", 0.0),
            n_jobs=data.get("n_jobs", 8),
            skip_foldseek=data.get("skip_foldseek", False),
        )


@dataclass
class Stage3Config:
    """Configuration for Stage 3: Fine Contact-based Clustering."""
    
    # Contact analysis parameters
    contact_cutoff: float = 5.0
    interface_cutoff: float = 8.0
    
    # Clustering parameters
    clustering_method: str = "kmeans"  # "kmeans", "hdbscan", "dbscan"
    min_cluster_size_for_fine: int = 5
    max_fine_clusters: int = 10
    
    # Processing options
    n_jobs: int = 4
    
    # Output options
    export_clusters: bool = True
    max_representatives_per_cluster: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "contact_cutoff": self.contact_cutoff,
            "interface_cutoff": self.interface_cutoff,
            "clustering_method": self.clustering_method,
            "min_cluster_size_for_fine": self.min_cluster_size_for_fine,
            "max_fine_clusters": self.max_fine_clusters,
            "n_jobs": self.n_jobs,
            "export_clusters": self.export_clusters,
            "max_representatives_per_cluster": self.max_representatives_per_cluster,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Stage3Config":
        return cls(
            contact_cutoff=data.get("contact_cutoff", 5.0),
            interface_cutoff=data.get("interface_cutoff", 8.0),
            clustering_method=data.get("clustering_method", "kmeans"),
            min_cluster_size_for_fine=data.get("min_cluster_size_for_fine", 5),
            max_fine_clusters=data.get("max_fine_clusters", 10),
            n_jobs=data.get("n_jobs", 4),
            export_clusters=data.get("export_clusters", True),
            max_representatives_per_cluster=data.get("max_representatives_per_cluster", 3),
        )


@dataclass
class PipelineConfig:
    """
    Complete pipeline configuration.
    
    Example YAML config:
    
    ```yaml
    input:
      pdb_dir: /path/to/af3/outputs
      chain_a: H
      antigen_chains: [A]
    
    output:
      output_dir: /path/to/results
      log_level: INFO
    
    stage1:
      plddt_threshold: 0.7
      ipsae_threshold: 0.6
      compute_ipsae: true
    
    stage2:
      skip_foldseek: false
      sensitivity: 7.5
    
    stage3:
      clustering_method: kmeans
      export_clusters: true
    ```
    """
    
    # Input configuration
    pdb_dir: Optional[Path] = None
    chain_a: str = "H"
    antigen_chains: List[str] = field(default_factory=lambda: ["A"])
    
    # Output configuration
    output_dir: Optional[Path] = None
    log_level: str = "INFO"
    
    # Stage configurations
    stage1: Stage1Config = field(default_factory=Stage1Config)
    stage2: Stage2Config = field(default_factory=Stage2Config)
    stage3: Stage3Config = field(default_factory=Stage3Config)
    
    # Pipeline options
    start_from_stage: int = 1
    resume_from_checkpoint: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "input": {
                "pdb_dir": str(self.pdb_dir) if self.pdb_dir else None,
                "chain_a": self.chain_a,
                "antigen_chains": self.antigen_chains,
            },
            "output": {
                "output_dir": str(self.output_dir) if self.output_dir else None,
                "log_level": self.log_level,
            },
            "stage1": self.stage1.to_dict(),
            "stage2": self.stage2.to_dict(),
            "stage3": self.stage3.to_dict(),
            "pipeline": {
                "start_from_stage": self.start_from_stage,
                "resume_from_checkpoint": self.resume_from_checkpoint,
            },
        }
    
    def to_yaml(self, path: Path) -> None:
        """Save configuration to YAML file."""
        if not HAS_YAML:
            raise ImportError("PyYAML not installed. Use to_json() instead.")
        with open(path, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
        logger.info(f"Saved config to: {path}")
    
    def to_json(self, path: Path) -> None:
        """Save configuration to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Saved config to: {path}")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineConfig":
        """Create configuration from dictionary."""
        input_cfg = data.get("input", {})
        output_cfg = data.get("output", {})
        pipeline_cfg = data.get("pipeline", {})
        
        return cls(
            pdb_dir=Path(input_cfg["pdb_dir"]) if input_cfg.get("pdb_dir") else None,
            chain_a=input_cfg.get("chain_a", "H"),
            antigen_chains=input_cfg.get("antigen_chains", ["A"]),
            output_dir=Path(output_cfg["output_dir"]) if output_cfg.get("output_dir") else None,
            log_level=output_cfg.get("log_level", "INFO"),
            stage1=Stage1Config.from_dict(data.get("stage1", {})),
            stage2=Stage2Config.from_dict(data.get("stage2", {})),
            stage3=Stage3Config.from_dict(data.get("stage3", {})),
            start_from_stage=pipeline_cfg.get("start_from_stage", 1),
            resume_from_checkpoint=pipeline_cfg.get("resume_from_checkpoint", False),
        )
    
    @classmethod
    def from_yaml(cls, path: Path) -> "PipelineConfig":
        """Load configuration from YAML file."""
        if not HAS_YAML:
            raise ImportError("PyYAML not installed. Use from_json() instead.")
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        logger.info(f"Loaded config from: {path}")
        return cls.from_dict(data)
    
    @classmethod
    def from_json(cls, path: Path) -> "PipelineConfig":
        """Load configuration from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)
        logger.info(f"Loaded config from: {path}")
        return cls.from_dict(data)
    
    def validate(self) -> List[str]:
        """
        Validate configuration and return list of errors.
        
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # Validate input
        if self.pdb_dir and not self.pdb_dir.exists():
            errors.append(f"Input directory does not exist: {self.pdb_dir}")
        
        # Validate thresholds
        if not 0 <= self.stage1.plddt_threshold <= 1:
            errors.append(f"plddt_threshold must be 0-1, got: {self.stage1.plddt_threshold}")
        
        if not 0 <= self.stage1.iptm_threshold <= 1:
            errors.append(f"iptm_threshold must be 0-1, got: {self.stage1.iptm_threshold}")
        
        if not 0 <= self.stage1.ipsae_threshold <= 1:
            errors.append(f"ipsae_threshold must be 0-1, got: {self.stage1.ipsae_threshold}")
        
        if self.stage1.clashes_threshold < 0:
            errors.append(f"clashes_threshold must be >= 0, got: {self.stage1.clashes_threshold}")
        
        # Validate clustering method
        valid_methods = ["kmeans", "hdbscan", "dbscan"]
        if self.stage3.clustering_method not in valid_methods:
            errors.append(f"clustering_method must be one of {valid_methods}, got: {self.stage3.clustering_method}")
        
        # Validate stage number
        if self.start_from_stage not in [1, 2, 3]:
            errors.append(f"start_from_stage must be 1, 2, or 3, got: {self.start_from_stage}")
        
        return errors


def create_default_config(
    pdb_dir: Path,
    output_dir: Optional[Path] = None,
    preset: str = "balanced",
) -> PipelineConfig:
    """
    Create a default configuration with sensible presets.
    
    Args:
        pdb_dir: Path to AF3 output directory
        output_dir: Path for outputs (default: <pdb_dir>_clustering)
        preset: Configuration preset:
            - "strict": High-confidence structures only
            - "balanced": Default balanced thresholds
            - "relaxed": More permissive thresholds
    
    Returns:
        PipelineConfig with preset values
    """
    presets = {
        "strict": {
            "stage1": {
                "plddt_threshold": 0.8,
                "iptm_threshold": 0.7,
                "ipsae_threshold": 0.7,
                "clashes_threshold": 3,
                "pdockq_threshold": 0.3,
            },
        },
        "balanced": {
            "stage1": {
                "plddt_threshold": 0.7,
                "iptm_threshold": 0.6,
                "ipsae_threshold": 0.6,
                "clashes_threshold": 5,
                "pdockq_threshold": 0.2,
            },
        },
        "relaxed": {
            "stage1": {
                "plddt_threshold": 0.6,
                "iptm_threshold": 0.5,
                "ipsae_threshold": 0.45,
                "clashes_threshold": 12,
                "pdockq_threshold": 0.12,
            },
        },
    }
    
    if preset not in presets:
        raise ValueError(f"Unknown preset: {preset}. Choose from: {list(presets.keys())}")
    
    preset_config = presets[preset]
    
    if output_dir is None:
        output_dir = pdb_dir.parent / f"{pdb_dir.name}_clustering"
    
    config = PipelineConfig(
        pdb_dir=pdb_dir,
        output_dir=output_dir,
        stage1=Stage1Config.from_dict(preset_config.get("stage1", {})),
    )
    
    return config


# =============================================================================
# Full pipeline config (Part1 + Part2 + Part3, two modes)
# =============================================================================

@dataclass
class Part2RunConfig:
    """Part2 (PyRosetta) 配置：输入 CSV、输出目录、Relax 等。"""
    csv_path: Optional[Path] = None
    output_dir: Optional[Path] = None
    relax: bool = True
    n_jobs: int = 0
    batch_idx: int = 0
    dump_top_n: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "csv_path": str(self.csv_path) if self.csv_path else None,
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "relax": self.relax,
            "n_jobs": self.n_jobs,
            "batch_idx": self.batch_idx,
            "dump_top_n": self.dump_top_n,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Part2RunConfig":
        return cls(
            csv_path=Path(data["csv_path"]) if data.get("csv_path") else None,
            output_dir=Path(data["output_dir"]) if data.get("output_dir") else None,
            relax=data.get("relax", True),
            n_jobs=data.get("n_jobs", 0),
            batch_idx=data.get("batch_idx", 0),
            dump_top_n=data.get("dump_top_n", 0),
        )


@dataclass
class Part3RunConfig:
    """Part3 (GROMACS MD + MM/PBSA) 配置。"""
    md_script: Optional[Path] = None
    n_gpu: int = 8
    production_ns: int = 100
    npt_ns: float = 1.0
    tmp: float = 310.0
    forcefield: str = "amber14sb_parmbsc1"
    base_output_dir: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "md_script": str(self.md_script) if self.md_script else None,
            "n_gpu": self.n_gpu,
            "production_ns": self.production_ns,
            "npt_ns": self.npt_ns,
            "tmp": self.tmp,
            "forcefield": self.forcefield,
            "base_output_dir": str(self.base_output_dir) if self.base_output_dir else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Part3RunConfig":
        return cls(
            md_script=Path(data["md_script"]) if data.get("md_script") else None,
            n_gpu=data.get("n_gpu", 8),
            production_ns=data.get("production_ns", 100),
            npt_ns=data.get("npt_ns", 1.0),
            tmp=data.get("tmp", 310.0),
            forcefield=data.get("forcefield", "amber14sb_parmbsc1"),
            base_output_dir=Path(data["base_output_dir"]) if data.get("base_output_dir") else None,
        )


@dataclass
class FullPipelineConfig:
    """
    端到端流水线配置：支持两种模式。
    - de_novo: AF3 → Part1(Stage1+可选Stage3) → Part2 → Part3
    - affinity_maturation: Part2 → Part3（跳过 Part1，Part2 输入 CSV 由用户提供）
    """
    pipeline_mode: str = "de_novo"  # "de_novo" | "affinity_maturation"
    part1: Optional[PipelineConfig] = None
    part2: Part2RunConfig = field(default_factory=Part2RunConfig)
    part3: Part3RunConfig = field(default_factory=Part3RunConfig)
    output_dir: Optional[Path] = None
    resume: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_mode": self.pipeline_mode,
            "part1": self.part1.to_dict() if self.part1 else None,
            "part2": self.part2.to_dict(),
            "part3": self.part3.to_dict(),
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "resume": self.resume,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FullPipelineConfig":
        part1_data = data.get("part1")
        return cls(
            pipeline_mode=data.get("pipeline_mode", "de_novo"),
            part1=PipelineConfig.from_dict(part1_data) if part1_data else None,
            part2=Part2RunConfig.from_dict(data.get("part2", {})),
            part3=Part3RunConfig.from_dict(data.get("part3", {})),
            output_dir=Path(data["output_dir"]) if data.get("output_dir") else None,
            resume=data.get("resume", False),
        )

    def validate(self) -> List[str]:
        errors = []
        if self.pipeline_mode not in ("de_novo", "affinity_maturation"):
            errors.append(f"pipeline_mode must be de_novo or affinity_maturation, got: {self.pipeline_mode}")
        if self.pipeline_mode == "de_novo" and not self.part1:
            errors.append("de_novo mode requires part1 config")
        if self.pipeline_mode == "affinity_maturation" and not self.part2.csv_path:
            errors.append("affinity_maturation mode requires part2.csv_path")
        if self.part2.output_dir and not self.part2.output_dir.parent.exists():
            errors.append(f"part2 output_dir parent does not exist: {self.part2.output_dir}")
        return errors
