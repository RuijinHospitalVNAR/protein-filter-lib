"""
Design data structures for protein filter library.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class Design:
    """
    Represents a protein design for filtering.
    
    Attributes:
        sequence: Binder protein sequence
        pdb_path: Path to predicted PDB or mmCIF structure file (from external prediction)
        target_chain: Target chain identifier(s) (e.g., "A" or "A,B")
        binder_chain: Binder chain identifier (e.g., "B")
        target_sequence: Optional target sequence(s)
        design_name: Name identifier for this design
        cdr_positions: Optional CDR positions for antibody designs
        hotspot_residues: Optional hotspot residue positions
        prediction_metrics: Optional prediction metrics from structure prediction
            (e.g., {"plddt": 0.8, "ptm": 0.7, "iptm": 0.6, "pae_matrix": ...})
        metadata: Additional metadata dictionary
    """
    sequence: str
    pdb_path: str
    target_chain: str
    binder_chain: str
    target_sequence: Optional[List[str]] = None
    design_name: str = "design"
    cdr_positions: Optional[List[int]] = None
    hotspot_residues: Optional[List[int]] = None
    prediction_metrics: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate design data and optionally auto-extract prediction metrics."""
        if not Path(self.pdb_path).exists():
            raise FileNotFoundError(f"Structure file not found: {self.pdb_path}")
        
        if not self.sequence:
            raise ValueError("Sequence cannot be empty")
        
        # Auto-extract prediction metrics from AF3 output if not provided
        if self.prediction_metrics is None:
            try:
                from .utils.af3_utils import auto_extract_af3_metrics
                extracted_metrics = auto_extract_af3_metrics(self.pdb_path)
                if extracted_metrics:
                    self.prediction_metrics = extracted_metrics
                    logger.info(f"Auto-extracted prediction metrics from AF3 output: {list(extracted_metrics.keys())}")
            except Exception as e:
                # Silently fail - user can provide metrics manually
                logger.debug(f"Could not auto-extract metrics: {e}")


@dataclass
class FilterResult:
    """
    Result of filtering a design.
    
    Attributes:
        metrics: Dictionary of calculated metrics
        filter_results: Dictionary mapping filter names to pass/fail booleans
        passed: True if all filters passed
        relaxed_pdb_path: Path to relaxed structure (if relaxation was performed)
        structure_pdb_path: Path to predicted structure
        warnings: List of warning messages
    """
    metrics: Dict[str, Any]
    filter_results: Dict[str, bool]
    passed: bool
    relaxed_pdb_path: Optional[str] = None
    structure_pdb_path: Optional[str] = None
    warnings: Optional[List[str]] = None
    
    def __post_init__(self):
        """Initialize warnings if None."""
        if self.warnings is None:
            self.warnings = []

