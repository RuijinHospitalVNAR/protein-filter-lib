"""
Core filtering logic for protein filter library.
"""

from typing import Dict, Any, List, Tuple
from pathlib import Path
import logging

from .design import Design, FilterResult
from .config import FilterConfig
from .implementations import get_relaxer
from .metrics import MetricAggregator

logger = logging.getLogger(__name__)


class ProteinFilter:
    """
    Main protein filter system.
    
    Analyzes predicted structures, performs relaxation, calculates metrics,
    and evaluates filters.
    
    Note: Structure prediction is handled externally. This library accepts
    predicted structures and their metrics as input.
    """
    
    def __init__(self, config: FilterConfig):
        """
        Initialize protein filter system.
        
        Args:
            config: Filter configuration
        """
        self.config = config
        self.relaxer = get_relaxer(config.structure_relaxer)
        self.metric_aggregator = MetricAggregator(config.metrics)
        
        # Validate components (skip validation for "none" relaxer)
        if config.structure_relaxer.name.lower() != "none" and not self.relaxer.is_available():
            raise RuntimeError(
                f"Structure relaxer '{config.structure_relaxer.name}' is not available"
            )
    
    def filter(self, design: Design) -> FilterResult:
        """
        Filter a protein design.
        
        Pipeline:
        1. Relax predicted structure (if relaxation is enabled)
        2. Calculate all metrics
        3. Evaluate filters
        4. Return result
        
        Args:
            design: Design to filter, containing:
                - pdb_path: Path to predicted structure file
                - prediction_metrics: Optional metrics from prediction (plddt, ptm, iptm, pae_matrix, etc.)
        
        Returns:
            FilterResult with metrics and filter evaluation
        """
        logger.info(f"Filtering design: {design.design_name}")
        
        warnings = []
        
        try:
            # Get prediction metrics from design or use empty dict
            prediction_metrics = design.prediction_metrics or {}
            
            # Step 1: Structure relaxation
            structure_pdb = design.pdb_path
            relaxed_pdb = structure_pdb
            
            if self.config.structure_relaxer.name.lower() != "none":
                logger.info("Step 1: Relaxing structure...")
                relaxed_pdb = self.relaxer.relax(
                    structure_pdb,
                    str(Path(self.config.output_dir) / f"{design.design_name}_relaxed.pdb"),
                    design.target_chain,
                    design.binder_chain,
                )
            else:
                logger.info("Step 1: Skipping structure relaxation")
            
            # Step 2: Calculate metrics
            logger.info("Step 2: Calculating metrics...")
            all_metrics = self.metric_aggregator.calculate_all(
                relaxed_pdb,
                structure_pdb,
                design,
                prediction_metrics,
            )
            
            # Step 3: Evaluate filters
            logger.info("Step 3: Evaluating filters...")
            filter_results, passed = self._evaluate_filters(all_metrics)
            
            logger.info(
                f"Design {design.design_name}: {'PASSED' if passed else 'FAILED'}"
            )
            
            return FilterResult(
                metrics=all_metrics,
                filter_results=filter_results,
                passed=passed,
                relaxed_pdb_path=relaxed_pdb if relaxed_pdb != structure_pdb else None,
                structure_pdb_path=structure_pdb,
                warnings=warnings,
            )
        
        except Exception as e:
            logger.exception("Error filtering design %s: %s", design.design_name, e)
            warnings.append(f"Error during filtering: {str(e)}")
            
            # Return failed result
            return FilterResult(
                metrics={},
                filter_results={},
                passed=False,
                warnings=warnings,
            )
    
    def _evaluate_filters(
        self,
        metrics: Dict[str, Any]
    ) -> Tuple[Dict[str, bool], bool]:
        """
        Evaluate metrics against filter thresholds.
        
        Args:
            metrics: Dictionary of calculated metrics
        
        Returns:
            Tuple of (filter_results_dict, all_passed_bool)
        """
        filter_results = {}
        
        if not self.config.filters:
            # No filters defined, all pass
            return {}, True
        
        for filter_name, filter_config in self.config.filters.items():
            if filter_name not in metrics:
                logger.warning(
                    f"Filter '{filter_name}' not found in metrics, skipping"
                )
                filter_results[f"{filter_name}_filter"] = False
                continue
            
            metric_value = metrics[filter_name]
            threshold = filter_config.get("threshold") or filter_config.get("value")
            operator = filter_config.get("operator", ">=")
            
            # Evaluate based on operator
            passed = self._evaluate_operator(metric_value, threshold, operator)
            filter_results[f"{filter_name}_filter"] = passed
        
        # All filters must pass
        all_passed = all(filter_results.values())
        
        return filter_results, all_passed
    
    @staticmethod
    def _evaluate_operator(value: Any, threshold: Any, operator: str) -> bool:
        """Evaluate a single filter condition."""
        try:
            if operator == "<":
                return value < threshold
            elif operator == "<=":
                return value <= threshold
            elif operator == ">":
                return value > threshold
            elif operator == ">=":
                return value >= threshold
            elif operator in ("==", "="):
                return value == threshold
            else:
                logger.warning(f"Unknown operator '{operator}', defaulting to False")
                return False
        except (TypeError, ValueError) as e:
            logger.warning(
                f"Error evaluating filter: {value} {operator} {threshold}: {e}"
            )
            return False

