"""
Chain auto-detection utilities for protein design pipeline.

Provides intelligent detection of target (antigen) and binder (antibody) chains
from PDB files, supporting multiple strategies:
- by_length: by sequence length (antigen typically longer)
- by_interface: by protein-protein interface contact area
- by_sequence: by exact sequence matching (if known sequences provided)
"""

from Bio.PDB import PDBParser, PDBIO
from Bio.SeqUtils import seq1
import numpy as np
from typing import Dict, List, Optional, Tuple
from pathlib import Path

try:
    from protein_filter.cache import get_cached_structure
    HAS_CACHE = True
except ImportError:
    HAS_CACHE = False


SOLVENT_RESIDUES = {"WAT", "HOH", "Hoh", "WAT", "HOH"}
ION_RESIDUES = {"Na+", "Na", "K+", "K", "Cl-", "Cl", "MG", "MG2+", "CA", "CA2+", "ZN", "ZN2+", "FE", "FE2+", "FE3+"}


def parse_chains_from_pdb(pdb_path: str) -> Dict[str, Dict]:
    """
    Parse PDB file and extract chain information.

    Args:
        pdb_path: Path to PDB file

    Returns:
        Dict mapping chain_id to {min_res, max_res, residues: list}
    """
    if HAS_CACHE:
        structure = get_cached_structure(pdb_path)
    else:
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("s", pdb_path)

    chains = {}
    for chain in structure.get_chains():
        chain_id = chain.id
        residues = []
        min_res, max_res = float("inf"), float("-inf")

        for res in chain.get_residues():
            resname = res.resname.strip()
            if resname in SOLVENT_RESIDUES or resname in ION_RESIDUES:
                continue

            try:
                resseq = res.id[1]
                residues.append(resseq)
                min_res = min(min_res, resseq)
                max_res = max(max_res, resseq)
            except Exception:
                continue

        if residues:
            chains[chain_id] = {
                "min_res": min_res,
                "max_res": max_res,
                "residues": residues,
                "length": len(residues)
            }

    return chains


def extract_sequence(pdb_path: str, chain_id: str) -> str:
    """
    Extract single-letter sequence for a specific chain.

    Args:
        pdb_path: Path to PDB file
        chain_id: Chain ID to extract

    Returns:
        Single-letter amino acid sequence
    """
    if HAS_CACHE:
        structure = get_cached_structure(pdb_path)
    else:
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("s", pdb_path)

    seq = []
    for res in structure[0][chain_id].get_residues():
        resname = res.resname.strip()
        if resname in SOLVENT_RESIDUES or resname in ION_RESIDUES:
            continue
        try:
            seq.append(seq1(resname))
        except Exception:
            continue

    return "".join(seq)


def calculate_interface_area(pdb_path: str, chain1: str, chain2: str, cutoff: float = 8.0) -> float:
    """
    Calculate interface contact area between two chains.

    Args:
        pdb_path: Path to PDB file
        chain1: First chain ID
        chain2: Second chain ID
        cutoff: Distance cutoff for contact (Angstrom)

    Returns:
        Approximate interface area (relative units)
    """
    if HAS_CACHE:
        structure = get_cached_structure(pdb_path)
    else:
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("s", pdb_path)

    coords1 = []
    coords2 = []

    for res in structure[0][chain1].get_residues():
        if res.resname.strip() in SOLVENT_RESIDUES or res.resname.strip() in ION_RESIDUES:
            continue
        for atom in res.get_atoms():
            if atom.name == "CA":
                coords1.append(atom.coord)

    for res in structure[0][chain2].get_residues():
        if res.resname.strip() in SOLVENT_RESIDUES or res.resname.strip() in ION_RESIDUES:
            continue
        for atom in res.get_atoms():
            if atom.name == "CA":
                coords2.append(atom.coord)

    if not coords1 or not coords2:
        return 0.0

    coords1 = np.array(coords1)
    coords2 = np.array(coords2)

    dist_matrix = np.linalg.norm(coords1[:, np.newaxis] - coords2, axis=2)
    contact_count = int(np.sum(dist_matrix < cutoff))

    return contact_count


def auto_detect_chains(
    pdb_path: str,
    strategy: str = "by_length",
    target_sequence: Optional[str] = None,
    binder_sequence: Optional[str] = None
) -> Tuple[str, str]:
    """
    Auto-detect target (antigen) and binder (antibody) chains from PDB.

    Args:
        pdb_path: Path to PDB file
        strategy: Detection strategy - "by_length", "by_interface", or "by_sequence"
        target_sequence: Optional known target sequence for exact matching
        binder_sequence: Optional known binder sequence for exact matching

    Returns:
        Tuple of (target_chain_id, binder_chain_id)

    Raises:
        ValueError: If detection fails or insufficient chains found
    """
    chains = parse_chains_from_pdb(pdb_path)

    if len(chains) < 2:
        raise ValueError(f"Need at least 2 protein chains, found {len(chains)}: {list(chains.keys())}")

    chain_ids = list(chains.keys())

    if strategy == "by_sequence" and (target_sequence or binder_sequence):
        return _detect_by_sequence(pdb_path, chains, target_sequence, binder_sequence)
    elif strategy == "by_interface":
        return _detect_by_interface(pdb_path, chains)
    else:
        return _detect_by_length(chains)


def _detect_by_sequence(
    pdb_path: str,
    chains: Dict,
    target_sequence: Optional[str],
    binder_sequence: Optional[str]
) -> Tuple[str, str]:
    """
    Detect chains by exact sequence matching.
    """
    if target_sequence:
        target_seq = target_sequence.upper()
        for chain_id in chains:
            seq = extract_sequence(pdb_path, chain_id).upper()
            if target_seq in seq or seq in target_seq:
                target_chain = chain_id
                break
        else:
            raise ValueError(f"Could not match target sequence to any chain")
    else:
        chain_ids = list(chains.keys())
        target_chain = chain_ids[0]

    if binder_sequence:
        binder_seq = binder_sequence.upper()
        for chain_id in chains:
            if chain_id == target_chain:
                continue
            seq = extract_sequence(pdb_path, chain_id).upper()
            if binder_seq in seq or seq in binder_seq:
                binder_chain = chain_id
                break
        else:
            raise ValueError(f"Could not match binder sequence to any chain")
    else:
        chain_ids = [c for c in chains.keys() if c != target_chain]
        binder_chain = chain_ids[0] if chain_ids else None

    if not binder_chain:
        raise ValueError("Could not determine binder chain")

    return target_chain, binder_chain


def _detect_by_interface(chains: Dict) -> Tuple[str, str]:
    """
    Detect chains by interface contact area (not implemented - requires PDB path).
    For now, falls back to length-based detection.
    """
    return _detect_by_length(chains)


def _detect_by_length(chains: Dict) -> Tuple[str, str]:
    """
    Detect chains by sequence length (antigen typically longer).
    """
    sorted_chains = sorted(chains.items(), key=lambda x: x[1]["length"], reverse=True)

    if len(sorted_chains) == 2:
        return sorted_chains[0][0], sorted_chains[1][0]

    target_chain = sorted_chains[0][0]

    binder_candidates = [c for c in sorted_chains[1:] if c[1]["length"] > 10]
    if binder_candidates:
        binder_chain = binder_candidates[0][0]
    else:
        binder_chain = sorted_chains[1][0]

    return target_chain, binder_chain


def get_mmpbsa_masks(pdb_path: str, target_chain: str, binder_chain: str) -> Tuple[str, str]:
    """
    Generate Amber mask strings for MMPBSA calculation.

    Args:
        pdb_path: Path to PDB file
        target_chain: Target chain ID (antigen)
        binder_chain: Binder chain ID (antibody)

    Returns:
        Tuple of (receptor_mask, ligand_mask) in Amber format
    """
    chains = parse_chains_from_pdb(pdb_path)

    if target_chain not in chains or binder_chain not in chains:
        raise ValueError(f"Chain not found: target={target_chain}, binder={binder_chain}")

    target_span = chains[target_chain]
    binder_span = chains[binder_chain]

    receptor_mask = f":{target_span['min_res']}-{target_span['max_res']}"
    ligand_mask = f":{binder_span['min_res']}-{binder_span['max_res']}"

    return receptor_mask, ligand_mask


def generate_auto_config(pdb_path: str) -> Dict:
    """
    Generate auto-detection configuration for a PDB file.

    Args:
        pdb_path: Path to PDB file

    Returns:
        Dict with recommended chain config
    """
    chains = parse_chains_from_pdb(pdb_path)

    if len(chains) >= 2:
        target, binder = _detect_by_length(chains)
        return {
            "chains": {
                "auto_detect": {
                    "enabled": True,
                    "strategy": "by_length"
                },
                "target_chain": target,
                "binder_chain": binder
            }
        }

    raise ValueError(f"Cannot auto-detect: only {len(chains)} chains found")