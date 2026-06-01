"""
Topology consistency checking utilities for MD/MMPBSA workflows.

This module provides functions to validate that PDB structures, topology files (prmtop),
and trajectories are consistent before running MD simulations or MMPBSA calculations.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TopologyError(Exception):
    """Base exception for topology-related errors."""
    pass


class ResidueCountMismatchError(TopologyError):
    """Raised when residue counts don't match between files."""
    pass


class ChainOrderError(TopologyError):
    """Raised when chain order is incorrect."""
    pass


def read_prmtop_residue_count(prmtop_path: str) -> int:
    """
    Read residue count from AMBER prmtop file.

    Args:
        prmtop_path: Path to prmtop file

    Returns:
        Number of residues in the topology
    """
    if not os.path.exists(prmtop_path):
        raise FileNotFoundError(f"prmtop file not found: {prmtop_path}")

    try:
        import parmed as pmd
        structure = pmd.load_file(prmtop_path)
        solvent = {"WAT", "HOH", "Na+", "Na", "K+", "K", "Cl-", "Cl", "Cl-", "Na+", "Mg", "Mg2+", "Ca", "Ca2+"}
        protein_residues = [r for r in structure.residues if r.name not in solvent]
        return len(set(r.number for r in protein_residues))
    except ImportError:
        pass

    residue_count = 0
    with open(prmtop_path, 'r') as f:
        for line in f:
            if line.startswith("%FLAG POINTERS") or "POINTERS" in line:
                break

    with open(prmtop_path, 'r') as f:
        content = f.read()

    for key in ["NATOM", "NRES", "NUMRES"]:
        if key in content:
            start = content.find(key)
            if start != -1:
                line_start = content.rfind("\n", 0, start)
                line_end = content.find("\n", start)
                if line_start != -1 and line_end != -1:
                    line = content[line_start:line_end]
                    for part in line.split():
                        try:
                            if int(part) > 100:
                                return int(part)
                        except ValueError:
                            continue

    for line in open(prmtop_path, 'r'):
        if "ATOM" in line and len(line.split()) > 5:
            try:
                last_res = int(line.split()[4])
                if last_res > residue_count:
                    residue_count = last_res
            except (ValueError, IndexError):
                continue

    return residue_count if residue_count > 0 else 1


def read_pdb_residue_count(pdb_path: str) -> int:
    """
    Read unique residue count from PDB file.

    Args:
        pdb_path: Path to PDB file

    Returns:
        Number of unique residues in the PDB
    """
    from Bio.PDB import PDBParser

    if not os.path.exists(pdb_path):
        raise FileNotFoundError(f"PDB file not found: {pdb_path}")

    parser = PDBParser(QUIET=True)
    try:
        structure = parser.get_structure("s", pdb_path)
    except Exception as e:
        raise TopologyError(f"Failed to parse PDB {pdb_path}: {e}") from e

    residues = set()
    solvent_residues = {"WAT", "HOH", "WAT", "HOH", "Na+", "Na", "K+", "K", "Cl-", "Cl"}

    for chain in structure.get_chains():
        for res in chain.get_residues():
            if res.resname.strip() not in solvent_residues:
                residues.add(res.id[1])

    return len(residues)


def check_prmtop_pdb_consistency(prmtop_path: str, pdb_path: str,
                                  tolerance: int = 5) -> Dict:
    """
    Check if prmtop and PDB have consistent residue counts.

    Args:
        prmtop_path: Path to prmtop file
        pdb_path: Path to reference PDB file
        tolerance: Acceptable difference in residue count

    Returns:
        Dict with consistency check results:
        {
            "consistent": bool,
            "prmtop_residues": int,
            "pdb_residues": int,
            "difference": int,
            "message": str
        }
    """
    try:
        prmtop_residues = read_prmtop_residue_count(prmtop_path)
    except Exception as e:
        logger.warning(f"Could not read prmtop residue count: {e}")
        prmtop_residues = -1

    try:
        pdb_residues = read_pdb_residue_count(pdb_path)
    except Exception as e:
        logger.warning(f"Could not read PDB residue count: {e}")
        pdb_residues = -1

    difference = abs(prmtop_residues - pdb_residues)
    consistent = difference <= tolerance and prmtop_residues > 0 and pdb_residues > 0

    return {
        "consistent": consistent,
        "prmtop_residues": prmtop_residues,
        "pdb_residues": pdb_residues,
        "difference": difference,
        "message": "Topology and structure are consistent" if consistent
                   else f"Difference of {difference} residues (tolerance: {tolerance})"
    }


def check_chain_order(pdb_path: str, expected_first: Optional[str] = None,
                      expected_second: Optional[str] = None) -> Dict:
    """
    Check if chain order in PDB matches expected order.

    Args:
        pdb_path: Path to PDB file
        expected_first: Expected first chain (target/antigen)
        expected_second: Expected second chain (binder/antibody)

    Returns:
        Dict with chain order check results:
        {
            "chains": List[str],
            "order_correct": bool,
            "message": str
        }
    """
    from Bio.PDB import PDBParser

    if not os.path.exists(pdb_path):
        raise FileNotFoundError(f"PDB file not found: {pdb_path}")

    parser = PDBParser(QUIET=True)
    try:
        structure = parser.get_structure("s", pdb_path)
    except Exception as e:
        raise TopologyError(f"Failed to parse PDB {pdb_path}: {e}") from e

    chains = [chain.id for chain in structure.get_chains()]

    if len(chains) < 2:
        return {
            "chains": chains,
            "order_correct": True,
            "message": "Less than 2 chains found, skipping order check"
        }

    if expected_first is None and expected_second is None:
        return {
            "chains": chains,
            "order_correct": True,
            "message": f"Chain order: {chains}"
        }

    order_correct = True
    if expected_first and chains[0] != expected_first:
        order_correct = False
    if expected_second and len(chains) > 1 and chains[1] != expected_second:
        order_correct = False

    return {
        "chains": chains,
        "order_correct": order_correct,
        "message": "Chain order matches expected" if order_correct
                   else f"Expected [{expected_first}, {expected_second}], got {chains}"
    }


def generate_diagnostic_report(structure_dir: str) -> Dict:
    """
    Generate a diagnostic report for a structure directory.

    Args:
        structure_dir: Path to structure directory

    Returns:
        Dict containing diagnostic information
    """
    structure_path = Path(structure_dir)
    if not structure_path.exists():
        raise FileNotFoundError(f"Structure directory not found: {structure_dir}")

    report = {
        "directory": str(structure_path),
        "files": {},
        "issues": [],
        "warnings": []
    }

    pdb_files = list(structure_path.glob("*.pdb"))
    if pdb_files:
        report["files"]["pdb"] = [str(f) for f in pdb_files]
    else:
        report["issues"].append("No PDB files found")

    prmtop_files = list(structure_path.glob("*.prmtop")) + list(structure_path.glob("*.top"))
    if prmtop_files:
        report["files"]["prmtop"] = [str(f) for f in prmtop_files]
    else:
        report["warnings"].append("No prmtop files found")

    trajectory_files = (list(structure_path.glob("*.nc")) +
                        list(structure_path.glob("*.trj")) +
                        list(structure_path.glob("*.xtc")) +
                        list(structure_path.glob("*.pdb")))
    if trajectory_files:
        report["files"]["trajectory"] = [str(f) for f in trajectory_files[:5]]
        if len(trajectory_files) > 5:
            report["files"]["trajectory_extra"] = len(trajectory_files) - 5

    for pdb_file in pdb_files:
        try:
            chain_info = check_chain_order(str(pdb_file))
            report[f"chain_order_{pdb_file.stem}"] = chain_info
        except Exception as e:
            report["warnings"].append(f"Could not check chain order for {pdb_file.name}: {e}")

    return report


def validate_mmpbsa_inputs(prmtop_path: str, trajectory_path: str,
                            pdb_path: Optional[str] = None) -> Dict:
    """
    Validate inputs before running MMPBSA calculation.

    Args:
        prmtop_path: Path to prmtop file
        trajectory_path: Path to trajectory file
        pdb_path: Optional reference PDB file

    Returns:
        Dict with validation results:
        {
            "valid": bool,
            "checks": Dict,
            "errors": List[str],
            "warnings": List[str]
        }
    """
    result = {
        "valid": True,
        "checks": {},
        "errors": [],
        "warnings": []
    }

    if not os.path.exists(prmtop_path):
        result["valid"] = False
        result["errors"].append(f"prmtop file not found: {prmtop_path}")
        return result

    if not os.path.exists(trajectory_path):
        result["valid"] = False
        result["errors"].append(f"trajectory file not found: {trajectory_path}")
        return result

    if pdb_path and os.path.exists(pdb_path):
        consistency_check = check_prmtop_pdb_consistency(prmtop_path, pdb_path)
        result["checks"]["consistency"] = consistency_check
        if not consistency_check["consistent"]:
            result["warnings"].append(consistency_check["message"])

    result["checks"]["prmtop_exists"] = True
    result["checks"]["trajectory_exists"] = True

    return result