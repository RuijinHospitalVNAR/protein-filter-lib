"""
Metric aggregator that coordinates all metric calculations.
"""

from typing import Dict, Any, List
import logging

from ..design import Design
from ..config import MetricConfig
from .calculators import (
    ClashCalculator,
    InterfaceCalculator,
    ConfidenceCalculator,
    SAPCalculator,
    SecondaryStructureCalculator,
    PDockQCalculator,
    IPSAECalculator,
    IgLMCalculator,
)
# A2binderCalculator is imported lazily to avoid requiring torch when not using A2binder

logger = logging.getLogger(__name__)


class MetricAggregator:
    """
    Aggregates metrics from multiple calculators.
    
    Coordinates metric calculation and aggregates results.
    """
    
    def __init__(self, config: MetricConfig):
        self.config = config
        
        # Initialize calculators
        self.calculators = []
        
        if "clashes" in config.enabled:
            self.calculators.append(ClashCalculator())
        
        if any(m in config.enabled for m in [
            "interface_dG", "interface_dSASA", "interface_packstat",
            "binder_score", "surface_hydrophobicity", "interface_sc",
            "interface_hbonds", "interface_hydrophobicity"
        ]):
            self.calculators.append(InterfaceCalculator())
        
        if any(m in config.enabled for m in ["external_plddt", "external_ptm", "external_iptm"]):
            self.calculators.append(ConfidenceCalculator())
        
        if "sap_score" in config.enabled:
            self.calculators.append(SAPCalculator(config))
        
        if any(m in config.enabled for m in ["alpha_all", "beta_all", "alpha_interface", "beta_interface"]):
            self.calculators.append(SecondaryStructureCalculator())
        
        if any(m in config.enabled for m in ["pdockq", "pdockq2", "lis", "lia", "i_plddt", "i_pae"]):
            self.calculators.append(PDockQCalculator())
        
        if "ipsae" in config.enabled:
            self.calculators.append(IPSAECalculator(
                pae_cutoff=getattr(config, 'ipsae_pae_cutoff', 5.0),
                distance_cutoff=getattr(config, 'ipsae_distance_cutoff', 5.0),
                ipsae_script_path=None,  # 自动检测（优先查找 scripts/ipsae.py）
                include_duplicate_metrics=getattr(config, 'ipsae_include_duplicate_metrics', False)
            ))
        
        if "iglm_ll" in config.enabled:
            self.calculators.append(IgLMCalculator())
        
        if "a2binder_affinity" in config.enabled:
            if config.a2binder_config is None:
                logger.warning("A2binder enabled but no configuration provided, skipping")
            else:
                # Lazy import to avoid requiring torch when not using A2binder
                from .a2binder_calculator import A2binderCalculator
                self.calculators.append(A2binderCalculator(**config.a2binder_config))
    
    def calculate_all(
        self,
        relaxed_pdb: str,
        structure_pdb: str,
        design: Design,
        prediction_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calculate all enabled metrics.
        
        Args:
            relaxed_pdb: Path to relaxed structure
            structure_pdb: Path to predicted structure
            design: Design object
            prediction_metrics: Metrics from structure prediction (may include PAE matrix)
        
        Returns:
            Dictionary of all calculated metrics
        
        Note:
            PDockQCalculator requires PAE matrix from prediction_metrics for pDockQ2 and LIS.
            If PAE is available, it will be used; otherwise only basic pDockQ is calculated.
        """
        all_metrics = {}
        
        # Add prediction metrics (with external_ prefix)
        for key, value in prediction_metrics.items():
            all_metrics[f"external_{key}"] = value
        
        # Extract PAE matrix if available
        pae_matrix = prediction_metrics.get("pae_matrix") or prediction_metrics.get("pae")
        
        # Calculate metrics from calculators
        for calculator in self.calculators:
            try:
                # Special handling for calculators that need additional parameters
                if isinstance(calculator, PDockQCalculator):
                    # First calculate basic pDockQ
                    basic_metrics = calculator.calculate(structure_pdb, design)
                    all_metrics.update(basic_metrics)
                    
                    # If PAE matrix is available, calculate pDockQ2 and LIS
                    if pae_matrix is not None:
                        try:
                            import numpy as np
                            if isinstance(pae_matrix, np.ndarray):
                                pae_metrics = calculator.calculate_with_pae(
                                    structure_pdb,
                                    pae_matrix,
                                    design.binder_chain,
                                )
                                all_metrics.update(pae_metrics)
                        except Exception as e:
                            logger.warning(f"Could not calculate pDockQ2/LIS metrics: {e}")
                elif isinstance(calculator, IPSAECalculator):
                    # IPSAECalculator needs prediction_metrics (for PAE matrix)
                    metrics = calculator.calculate(relaxed_pdb, design, prediction_metrics)
                    all_metrics.update(metrics)
                elif calculator.__class__.__name__ == "A2binderCalculator":
                    # A2binderCalculator needs target sequence
                    # Use __class__.__name__ to avoid importing A2binderCalculator when not needed
                    metrics = calculator.calculate(relaxed_pdb, design)
                    all_metrics.update(metrics)
                else:
                    # Standard calculator
                    metrics = calculator.calculate(relaxed_pdb, design)
                    all_metrics.update(metrics)
            except Exception as e:
                logger.warning(f"Error calculating metrics with {calculator.__class__.__name__}: {e}")
        
        # Round float values
        all_metrics = {
            k: round(v, 4) if isinstance(v, float) else v
            for k, v in all_metrics.items()
        }
        
        return all_metrics

