"""
PDB and mmCIF file processing utilities.

Extracted from germinal/utils/utils.py
Extended to support mmCIF format (used by AlphaFold3).
"""

from Bio.PDB import PDBParser, MMCIFParser, PDBIO
from Bio.SeqUtils import seq1
from scipy.spatial import cKDTree
import numpy as np
from typing import Dict, List, Tuple, Optional
from pathlib import Path

try:
    from protein_filter.cache import get_cached_structure
    HAS_CACHE = True
except ImportError:
    HAS_CACHE = False


# Three-letter to one-letter amino acid code mapping
THREE_TO_ONE_MAP = {
    "ALA": "A", "CYS": "C", "ASP": "D", "GLU": "E", "PHE": "F",
    "GLY": "G", "HIS": "H", "ILE": "I", "LYS": "K", "LEU": "L",
    "MET": "M", "ASN": "N", "PRO": "P", "GLN": "Q", "ARG": "R",
    "SER": "S", "THR": "T", "VAL": "V", "TRP": "W", "TYR": "Y",
}


def _is_cif_file(file_path: str) -> bool:
    """
    Check if file is a mmCIF file based on extension.
    
    Args:
        file_path: Path to structure file
        
    Returns:
        True if file is CIF format, False if PDB format
    """
    path = Path(file_path)
    return path.suffix.lower() in ['.cif', '.mmcif']


def _get_parser(file_path: str):
    """
    Get appropriate parser for structure file (PDB or mmCIF).
    
    Args:
        file_path: Path to structure file
        
    Returns:
        PDBParser or MMCIFParser instance
    """
    if _is_cif_file(file_path):
        return MMCIFParser(QUIET=True)
    else:
        return PDBParser(QUIET=True)


def get_sequence_from_pdb(pdb_path: str) -> Dict[str, str]:
    """
    Extract protein sequences from PDB or mmCIF file organized by chain.
    
    Extracted from germinal/utils/utils.py:get_sequence_from_pdb()
    Extended to support mmCIF format.
    
    Args:
        pdb_path: Path to the PDB or mmCIF file to process
        
    Returns:
        Dictionary mapping chain identifiers to their amino acid sequences
        in single-letter code format
    """
    if HAS_CACHE:
        structure = get_cached_structure(pdb_path)
    else:
        parser = _get_parser(pdb_path)
        structure = parser.get_structure("protein", pdb_path)
    chains = {
        chain.id: seq1("".join(residue.resname for residue in chain))
        for chain in structure.get_chains()
    }
    return chains


def clean_pdb(pdb_file: str):
    """
    Clean PDB file by removing unnecessary information.
    
    Extracted from germinal/utils/utils.py:clean_pdb()
    
    Filters PDB files to retain only essential structural information by
    keeping ATOM, HETATM, MODEL, TER, and END records while removing
    Rosetta-specific annotations and other metadata.
    
    Note: This function only works for PDB format. mmCIF files are not modified.
    
    Args:
        pdb_file: Path to the PDB file to clean (modified in place)
    """
    # Skip CIF files - they have different format
    if _is_cif_file(pdb_file):
        return
    
    # Read the pdb file and filter relevant lines
    with open(pdb_file, "r") as f_in:
        relevant_lines = [
            line
            for line in f_in
            if line.startswith(("ATOM", "HETATM", "MODEL", "TER", "END"))
        ]
    
    # Write the cleaned lines back to the original pdb file
    with open(pdb_file, "w") as f_out:
        f_out.writelines(relevant_lines)


def calculate_clash_score(
    pdb_file: str,
    threshold: float = 2.4,
    only_ca: bool = False
) -> int:
    """
    Calculate structural clash score for protein structure validation.
    
    Extracted from germinal/utils/utils.py:calculate_clash_score()
    Extended to support mmCIF format.
    
    Analyzes a protein structure to identify and count atomic clashes based on
    distance thresholds. Provides options for CA-only analysis or full atomic
    clash detection with proper exclusions for bonded and sequential residues.
    
    Args:
        pdb_file: Path to the PDB or mmCIF file to analyze
        threshold: Distance threshold (Å) below which atoms are considered clashing.
            Defaults to 2.4.
        only_ca: If True, only analyze CA-CA distances.
            If False, analyze all heavy atoms. Defaults to False.
            
    Returns:
        Number of clashing atom pairs found in the structure
    """
    parser = _get_parser(pdb_file)
    structure = parser.get_structure("protein", pdb_file)
    
    atoms = []
    atom_info = []  # Detailed atom info for debugging and processing
    
    for model in structure:
        for chain in model:
            for residue in chain:
                for atom in residue:
                    if atom.element == "H":  # Skip hydrogen atoms
                        continue
                    if only_ca and atom.get_name() != "CA":
                        continue
                    atoms.append(atom.coord)
                    atom_info.append(
                        (chain.id, residue.id[1], atom.get_name(), atom.coord)
                    )
    
    if len(atoms) == 0:
        return 0
    
    tree = cKDTree(atoms)
    pairs = tree.query_pairs(threshold)
    
    valid_pairs = set()
    for i, j in pairs:
        chain_i, res_i, name_i, coord_i = atom_info[i]
        chain_j, res_j, name_j, coord_j = atom_info[j]
        
        # Exclude clashes within the same residue
        if chain_i == chain_j and res_i == res_j:
            continue
        
        # Exclude directly sequential residues in the same chain for all atoms
        if chain_i == chain_j and abs(res_i - res_j) == 1:
            continue
        
        # If calculating sidechain clashes, only consider clashes between different chains
        if not only_ca and chain_i == chain_j:
            continue
        
        valid_pairs.add((i, j))
    
    return len(valid_pairs)


def hotspot_residues(
    trajectory_pdb: str,
    binder_chain: str = "B",
    atom_distance_cutoff: float = 4.0,
    target_chain: str = "A"
) -> Dict[int, str]:
    """
    Identify interface hotspot residues between binder and target.
    
    Extracted from germinal/utils/utils.py:hotspot_residues()
    Extended to support mmCIF format.
    
    Analyzes a protein complex structure to identify binder residues that
    are in close contact with the target protein, defining the binding interface.
    Uses spatial proximity analysis with KD-trees for efficient computation.
    
    Args:
        trajectory_pdb: Path to the PDB or mmCIF file containing the protein complex
        binder_chain: Chain identifier for the binder protein. Defaults to 'B'.
        atom_distance_cutoff: Maximum distance (Å) for interface contacts. Defaults to 4.0.
        target_chain: Chain identifier for the target protein. Defaults to 'A'.
        
    Returns:
        Dictionary mapping binder residue numbers to single-letter amino acid codes
        for all residues with atoms within the distance cutoff of the target
    """
    from Bio.PDB import Selection
    
    # Parse the structure file (PDB or mmCIF)
    target_chain_list = target_chain.split(",") if isinstance(target_chain, str) else target_chain
    parser = _get_parser(trajectory_pdb)
    structure = parser.get_structure("complex", trajectory_pdb)
    
    # AFM generates a single target chain even for multichain targets so need to rename binder as "B"
    model = next(structure.get_models())
    chains = list(model.get_chains())
    if len(chains) == 2:
        binder_chain = 'B'
    
    # Get the specified chain
    binder_atoms = Selection.unfold_entities(structure[0][binder_chain], "A")
    binder_coords = np.array([atom.coord for atom in binder_atoms])
    
    # Get atoms and coords for the target chain
    target_atoms = []
    for chain_id in target_chain_list:
        target_atoms.extend(Selection.unfold_entities(structure[0][chain_id], "A"))
    target_coords = np.array([atom.coord for atom in target_atoms])
    
    if len(binder_coords) == 0 or len(target_coords) == 0:
        return {}
    
    # Build KD trees for both chains
    binder_tree = cKDTree(binder_coords)
    target_tree = cKDTree(target_coords)
    
    # Prepare to collect interacting residues
    interacting_residues = {}
    
    # Query the tree for pairs of atoms within the distance cutoff
    pairs = binder_tree.query_ball_tree(target_tree, atom_distance_cutoff)
    
    # Process each binder atom's interactions
    for binder_idx, close_indices in enumerate(pairs):
        if len(close_indices) == 0:
            continue
        binder_residue = binder_atoms[binder_idx].get_parent()
        binder_resname = binder_residue.get_resname()
        
        # Convert three-letter code to single-letter code
        if binder_resname in THREE_TO_ONE_MAP:
            aa_single_letter = THREE_TO_ONE_MAP[binder_resname]
            interacting_residues[binder_residue.id[1]] = aa_single_letter
    
    return interacting_residues

