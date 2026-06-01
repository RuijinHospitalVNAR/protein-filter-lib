"""
Structure relaxation implementations.
"""

import logging
from pathlib import Path
from typing import Optional

from ..interfaces import StructureRelaxer
from ..config import StructureRelaxerConfig

logger = logging.getLogger(__name__)


class PyRosettaRelaxer(StructureRelaxer):
    """PyRosetta structure relaxer."""
    
    def __init__(self, config: StructureRelaxerConfig):
        self.config = config
        self._available = self._check_availability()
        if self._available:
            self._init_pyrosetta()
    
    def _check_availability(self) -> bool:
        """Check if PyRosetta is available."""
        try:
            import pyrosetta
            return True
        except ImportError:
            logger.warning("PyRosetta not available")
            return False
    
    def _init_pyrosetta(self):
        """Initialize PyRosetta."""
        import pyrosetta
        if self.config.pyrosetta_init:
            pyrosetta.init(self.config.pyrosetta_init)
        else:
            pyrosetta.init()
    
    def is_available(self) -> bool:
        return self._available
    
    def relax(
        self,
        pdb_path: str,
        output_path: str,
        target_chain: str,
        binder_chain: str,
    ) -> str:
        """
        Relax structure using PyRosetta FastRelax.
        
        Extracted from germinal/filters/pyrosetta_utils.py:pr_relax()
        """
        import os
        import pyrosetta as pr
        from pyrosetta.rosetta.protocols.relax import FastRelax
        from pyrosetta.rosetta.core.kinematics import MoveMap
        from pyrosetta.rosetta.protocols.simple_moves import AlignChainMover
        from ..utils.pdb_utils import clean_pdb
        
        if not os.path.exists(output_path):
            # Generate pose
            pose = pr.pose_from_pdb(pdb_path)
            start_pose = pose.clone()
            
            # Generate movemaps
            mmf = MoveMap()
            mmf.set_chi(True)  # enable sidechain movement
            mmf.set_bb(True)  # enable backbone movement
            mmf.set_jump(False)  # disable whole chain movement
            
            # Run FastRelax
            fastrelax = FastRelax()
            scorefxn = pr.get_fa_scorefxn()
            fastrelax.set_scorefxn(scorefxn)
            fastrelax.set_movemap(mmf)
            fastrelax.max_iter(200)  # default iterations is 2500
            fastrelax.min_type("lbfgs_armijo_nonmonotone")
            fastrelax.constrain_relax_to_start_coords(True)
            fastrelax.apply(pose)
            
            # Align relaxed structure to original trajectory
            align = AlignChainMover()
            align.source_chain(0)
            align.target_chain(0)
            align.pose(start_pose)
            align.apply(pose)
            
            # Copy B factors from start_pose to pose
            for resid in range(1, pose.total_residue() + 1):
                if pose.residue(resid).is_protein():
                    # Get the B factor of the first heavy atom in the residue
                    bfactor = start_pose.pdb_info().bfactor(resid, 1)
                    for atom_id in range(1, pose.residue(resid).natoms() + 1):
                        pose.pdb_info().bfactor(resid, atom_id, bfactor)
            
            # Output relaxed and aligned PDB
            pose.dump_pdb(output_path)
            clean_pdb(output_path)
        
        logger.info(f"Relaxed structure saved to: {output_path}")
        
        return output_path


class NoOpRelaxer(StructureRelaxer):
    """No-op relaxer that returns the input structure unchanged."""
    
    def __init__(self):
        self._available = True
    
    def is_available(self) -> bool:
        return self._available
    
    def relax(
        self,
        pdb_path: str,
        output_path: str,
        target_chain: str,
        binder_chain: str,
    ) -> str:
        """
        Return input structure unchanged (no relaxation).
        
        Args:
            pdb_path: Path to input PDB file
            output_path: Not used (returns input path)
            target_chain: Not used
            binder_chain: Not used
        
        Returns:
            Path to input PDB file (unchanged)
        """
        logger.info("Skipping structure relaxation (NoOpRelaxer)")
        return pdb_path
