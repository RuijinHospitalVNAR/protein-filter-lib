"""
Two-stage filtering example for large-scale design screening.

This example demonstrates how to efficiently filter 100,000+ designs using
a two-stage approach:
1. Fast screening: Use quick metrics (pLDDT, clashes, pDockQ, etc.)
2. Detailed analysis: Use expensive metrics (interface analysis, A2binder) on top candidates

This can significantly reduce computation time for large-scale screening.
"""

from protein_filter import ProteinFilter, FilterConfig, Design
from typing import List, Tuple
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fast_screen(
    designs: List[Design],
    top_n: int = 1000,
    output_dir: str = "./fast_screen_results"
) -> List[Tuple[Design, dict]]:
    """
    Stage 1: Fast screening using computationally cheap metrics.
    
    Fast metrics (no PyRosetta, no model inference):
    - Structure prediction confidence (pLDDT, PTM, iPTM) - from AF3 output
    - Structure quality (clashes) - scipy cKDTree
    - pDockQ series - numerical calculations
    - Secondary structure - PyRosetta Dssp (relatively fast)
    
    Args:
        designs: List of designs to screen
        top_n: Number of top candidates to return
        output_dir: Output directory for results
        
    Returns:
        List of (design, metrics) tuples for top candidates
    """
    logger.info(f"Stage 1: Fast screening {len(designs)} designs...")
    
    # Configure for fast metrics only
    fast_config = FilterConfig(
        structure_relaxer=FilterConfig.StructureRelaxerConfig(name="none"),  # Skip relaxation
        metrics=FilterConfig.MetricConfig(
            enabled=[
                # Fast metrics - no PyRosetta heavy calculations
                "plddt",  # From PDB B-factor
                "clashes",  # Fast clash detection
                "pdockq",  # Basic pDockQ (fast)
                # Optional: pDockQ2 and LIS if PAE matrix is available (still fast)
                "pdockq2", "lis", "lia",
                # Secondary structure (relatively fast, uses Dssp)
                "alpha_all", "beta_all",
            ]
        ),
        filters={
            # Fast filters
            "external_plddt": {"threshold": 0.7, "operator": ">="},
            "clashes": {"threshold": 5, "operator": "<"},  # Allow some clashes in fast stage
            "pdockq": {"threshold": 0.2, "operator": ">="},  # Lower threshold for fast stage
        },
        output_dir=output_dir,
    )
    
    filter_system = ProteinFilter(fast_config)
    
    # Score all designs
    scored_designs = []
    for i, design in enumerate(designs):
        if (i + 1) % 1000 == 0:
            logger.info(f"  Processed {i + 1}/{len(designs)} designs...")
        
        try:
            result = filter_system.filter(design)
            
            # Calculate composite score for ranking
            # You can customize this scoring function
            score = calculate_fast_score(result.metrics)
            
            scored_designs.append((design, result.metrics, score))
        except Exception as e:
            logger.warning(f"Error filtering {design.design_name}: {e}")
            continue
    
    # Sort by composite score and return top N
    scored_designs.sort(key=lambda x: x[2], reverse=True)
    top_candidates = scored_designs[:top_n]
    
    logger.info(f"Stage 1 complete: Selected top {len(top_candidates)} candidates")
    
    return [(design, metrics) for design, metrics, score in top_candidates]


def calculate_fast_score(metrics: dict) -> float:
    """
    Calculate composite score for fast screening.
    
    Customize this function based on your priorities.
    Higher score = better candidate.
    """
    score = 0.0
    
    # Weighted combination of fast metrics
    weights = {
        "external_plddt": 0.3,  # High weight on confidence
        "external_iptm": 0.2,   # Interface confidence
        "pdockq": 0.2,          # Docking quality
        "clashes": -0.1,        # Penalize clashes (negative weight)
    }
    
    for metric_name, weight in weights.items():
        value = metrics.get(metric_name, 0.0)
        if isinstance(value, (int, float)):
            score += weight * value
    
    # Bonus for pDockQ2 if available
    if "pdockq2" in metrics:
        score += 0.1 * metrics["pdockq2"]
    
    return score


def detailed_analysis(
    candidates: List[Tuple[Design, dict]],
    output_dir: str = "./detailed_analysis_results"
) -> List[Tuple[Design, dict, bool]]:
    """
    Stage 2: Detailed analysis using computationally expensive metrics.
    
    Expensive metrics:
    - Interface analysis (16 metrics) - PyRosetta InterfaceAnalyzer (slow)
    - SAP scores - PyRosetta (moderate)
    - A2binder affinity - Model inference (slow)
    
    Args:
        candidates: List of (design, fast_metrics) from stage 1
        output_dir: Output directory for results
        
    Returns:
        List of (design, all_metrics, passed) tuples
    """
    logger.info(f"Stage 2: Detailed analysis of {len(candidates)} candidates...")
    
    # Configure for all metrics including expensive ones
    detailed_config = FilterConfig(
        structure_relaxer=FilterConfig.StructureRelaxerConfig(name="pyrosetta"),  # Enable relaxation
        metrics=FilterConfig.MetricConfig(
            enabled=[
                # All fast metrics
                "plddt", "clashes", "pdockq", "pdockq2", "lis", "lia",
                "alpha_all", "beta_all",
                # Expensive metrics
                "interface_dG", "interface_dSASA", "interface_packstat",
                "interface_sc", "interface_hbonds",
                "sap_score",
                # Optional: A2binder (requires model)
                # "a2binder_affinity",
            ],
            # A2binder configuration (if enabled)
            # a2binder_config={
            #     "model_path": "...",
            #     "heavy_model_dir": "...",
            #     ...
            # }
        ),
        filters={
            # Stricter filters for final selection
            "external_plddt": {"threshold": 0.75, "operator": ">="},
            "external_iptm": {"threshold": 0.6, "operator": ">="},
            "clashes": {"threshold": 1, "operator": "<"},
            "interface_dG": {"threshold": -10.0, "operator": "<"},
            "interface_packstat": {"threshold": 0.6, "operator": ">="},
            "pdockq": {"threshold": 0.23, "operator": ">="},
            "sap_score": {"threshold": 100, "operator": "<"},
        },
        output_dir=output_dir,
    )
    
    filter_system = ProteinFilter(detailed_config)
    
    results = []
    for i, (design, fast_metrics) in enumerate(candidates):
        if (i + 1) % 100 == 0:
            logger.info(f"  Analyzed {i + 1}/{len(candidates)} candidates...")
        
        try:
            result = filter_system.filter(design)
            results.append((design, result.metrics, result.passed))
        except Exception as e:
            logger.warning(f"Error in detailed analysis of {design.design_name}: {e}")
            results.append((design, fast_metrics, False))
    
    passed_count = sum(1 for _, _, passed in results if passed)
    logger.info(f"Stage 2 complete: {passed_count}/{len(results)} candidates passed all filters")
    
    return results


def two_stage_filtering_pipeline(
    designs: List[Design],
    top_n: int = 1000,
    fast_output_dir: str = "./fast_screen_results",
    detailed_output_dir: str = "./detailed_analysis_results"
) -> List[Tuple[Design, dict, bool]]:
    """
    Complete two-stage filtering pipeline.
    
    Args:
        designs: List of all designs to filter
        top_n: Number of candidates to carry to stage 2
        fast_output_dir: Output directory for stage 1
        detailed_output_dir: Output directory for stage 2
        
    Returns:
        List of (design, all_metrics, passed) for final candidates
    """
    # Stage 1: Fast screening
    top_candidates = fast_screen(designs, top_n=top_n, output_dir=fast_output_dir)
    
    # Stage 2: Detailed analysis
    final_results = detailed_analysis(top_candidates, output_dir=detailed_output_dir)
    
    return final_results


# Example usage
if __name__ == "__main__":
    # Example: Load designs from AF3 output directory
    # In practice, you would load from your actual prediction results
    
    designs = []
    af3_output_dir = Path("./af3_predictions")
    
    # Assume you have 20,000 sequences × 5 seeds = 100,000 designs
    # Each design has: sequence_001_seed_0.pdb, sequence_001_seed_0_scores.json, etc.
    
    for seq_id in range(1, 20001):  # 20,000 sequences
        for seed in range(5):  # 5 seeds
            pdb_path = af3_output_dir / f"sequence_{seq_id:05d}_seed_{seed}.pdb"
            
            if not pdb_path.exists():
                continue
            
            design = Design(
                sequence="MKLLVL...",  # Your actual sequence
                pdb_path=str(pdb_path),
                target_chain="A",
                binder_chain="B",
                design_name=f"seq_{seq_id:05d}_seed_{seed}",
                # Metrics will be auto-extracted from PDB and JSON
            )
            designs.append(design)
    
    logger.info(f"Loaded {len(designs)} designs")
    
    # Run two-stage filtering
    # Stage 1: Fast screen 100,000 designs → top 1,000
    # Stage 2: Detailed analysis of 1,000 → final candidates
    results = two_stage_filtering_pipeline(
        designs,
        top_n=1000,  # Keep top 1% for detailed analysis
        fast_output_dir="./fast_screen_results",
        detailed_output_dir="./detailed_analysis_results"
    )
    
    # Save results
    passed_designs = [(d, m) for d, m, passed in results if passed]
    logger.info(f"Final results: {len(passed_designs)} designs passed all filters")
    
    # Save top candidates
    import json
    with open("final_candidates.json", "w") as f:
        json.dump([
            {
                "design_name": design.design_name,
                "pdb_path": design.pdb_path,
                "metrics": metrics
            }
            for design, metrics in passed_designs
        ], f, indent=2)
    
    logger.info("Results saved to final_candidates.json")
