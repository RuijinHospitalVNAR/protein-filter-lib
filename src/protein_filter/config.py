"""
Configuration classes for protein filter library.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path


@dataclass
class StructureRelaxerConfig:
    """Configuration for structure relaxation."""
    name: str = "pyrosetta"
    pyrosetta_init: Optional[str] = None
    relax_cycles: int = 5


@dataclass
class MetricConfig:
    """Configuration for metric calculation."""
    enabled: List[str] = field(default_factory=lambda: [
        "plddt", "iptm", "pae", "clashes", "interface_dG",
        "interface_dSASA", "interface_packstat", "sap_score"
    ])
    # CDR-specific metrics (for antibodies)
    cdr_positions: Optional[List[int]] = None
    # Hotspot-specific metrics
    hotspot_residues: Optional[List[int]] = None
    # SAP score parameters
    sap_limit_sasa: float = 0.15
    sap_patch_radius: float = 10.0
    sap_avg_sasa_patch_thr: float = 0.4
    # A2binder configuration
    a2binder_config: Optional[Dict[str, Any]] = None
    # IPSAE configuration
    ipsae_include_duplicate_metrics: bool = False  # 是否包含可能与其他指标重合的参数（用于交叉验证）
    ipsae_pae_cutoff: float = 5.0  # IPSAE PAE 截断值
    ipsae_distance_cutoff: float = 5.0  # IPSAE 距离截断值


@dataclass
class FilterConfig:
    """
    Main configuration for protein filter system.
    
    Attributes:
        structure_relaxer: Structure relaxer configuration (set name="none" to skip)
        metrics: Metric calculation configuration
        filters: Filter thresholds and operators
        output_dir: Output directory for results
        temp_dir: Temporary directory for intermediate files
        iglm_config: IgLM configuration (for antibody sequences)
    
    Note: Structure prediction is handled externally. This library accepts
    predicted structures and their metrics via the Design object.
    """
    structure_relaxer: StructureRelaxerConfig = field(
        default_factory=StructureRelaxerConfig
    )
    metrics: MetricConfig = field(default_factory=MetricConfig)
    filters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    output_dir: str = "./filter_results"
    temp_dir: Optional[str] = None
    iglm_config: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Create output directory if it doesn't exist."""
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        if self.temp_dir is None:
            from tempfile import gettempdir
            self.temp_dir = gettempdir()

