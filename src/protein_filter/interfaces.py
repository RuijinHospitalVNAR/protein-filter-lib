"""
Abstract interfaces for protein filter components.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from .design import Design


class StructureRelaxer(ABC):
    """
    Abstract interface for structure relaxation.
    
    Implementations: PyRosettaRelaxer
    """
    
    @abstractmethod
    def relax(
        self,
        pdb_path: str,
        output_path: str,
        target_chain: str,
        binder_chain: str,
    ) -> str:
        """
        Relax protein structure.
        
        Args:
            pdb_path: Path to input PDB file
            output_path: Path to save relaxed structure
            target_chain: Target chain identifier
            binder_chain: Binder chain identifier
        
        Returns:
            Path to relaxed PDB file
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if relaxer is available and configured."""
        pass


class MetricCalculator(ABC):
    """
    Abstract interface for metric calculation.
    
    Implementations: ClashCalculator, InterfaceCalculator, etc.
    """
    
    @abstractmethod
    def calculate(
        self,
        pdb_path: str,
        design: Design,
    ) -> Dict[str, Any]:
        """
        Calculate metrics for a design.
        
        Args:
            pdb_path: Path to PDB structure file
            design: Design object
        
        Returns:
            Dictionary of calculated metrics
        """
        pass
    
    @abstractmethod
    def get_metric_names(self) -> List[str]:
        """Return list of metric names this calculator produces."""
        pass

