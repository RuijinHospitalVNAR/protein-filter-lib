"""
IPSAE utilities for interprotein interaction scoring.

IPSAE (Scoring function for interprotein interactions in AlphaFold2 and AlphaFold3)
improves upon AlphaFold's ipTM score by focusing on high-confidence interface regions.

Key insight: ipsae.py writes results to FILES, not stdout.
Output file format: {pdb_stem}_{pae_cutoff}_{dist_cutoff}.txt

Source: https://github.com/DunbrackLab/IPSAE/
"""

import json
import logging
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import subprocess
import tempfile
import os
import shutil

logger = logging.getLogger(__name__)


def calculate_ipsae_from_script(
    json_path: str,
    pdb_path: str,
    pae_cutoff: float = 5.0,
    dist_cutoff: float = 5.0,
    ipsae_script_path: Optional[str] = None,
    use_cached: bool = True,
) -> Dict[str, Any]:
    """
    Calculate IPSAE using the ipsae.py script.
    
    IMPORTANT: ipsae.py writes results to files in the same directory as the PDB/CIF file.
    Output filename format: {pdb_stem}_{pae_cutoff:02d}_{dist_cutoff:02d}.txt
    
    Args:
        json_path: Path to AlphaFold JSON file (containing PAE matrix)
        pdb_path: Path to PDB/CIF structure file
        pae_cutoff: PAE cutoff value (default: 5.0)
        dist_cutoff: Distance cutoff for CA-CA contacts (default: 5.0)
        ipsae_script_path: Path to ipsae.py script (if None, searches in common locations)
        use_cached: If True, use existing output file if available (skip recalculation)
    
    Returns:
        Dictionary with IPSAE scores and related metrics
    """
    pdb_path_obj = Path(pdb_path)
    json_path_obj = Path(json_path)
    
    if not pdb_path_obj.exists():
        logger.debug(f"PDB/CIF file not found: {pdb_path}")
        return {}
    
    if not json_path_obj.exists():
        logger.debug(f"JSON file not found: {json_path}")
        return {}
    
    # Determine output file path
    # ipsae.py naming convention: {pdb_stem}_{pae:02d}_{dist:02d}.txt
    pae_str = f"{int(pae_cutoff):02d}" if pae_cutoff < 10 else str(int(pae_cutoff))
    dist_str = f"{int(dist_cutoff):02d}" if dist_cutoff < 10 else str(int(dist_cutoff))
    
    pdb_stem = pdb_path_obj.stem
    output_file = pdb_path_obj.parent / f"{pdb_stem}_{pae_str}_{dist_str}.txt"
    
    # Optimization: Check if output file already exists (cached result)
    if use_cached and output_file.exists():
        logger.debug(f"Using cached IPSAE result: {output_file}")
        return _parse_ipsae_output_file(str(output_file))
    
    # Find ipsae.py script
    if ipsae_script_path is None:
        ipsae_script_path = get_ipsae_script_path()
        
    if ipsae_script_path is None or not Path(ipsae_script_path).exists():
        logger.debug("ipsae.py script not found")
        return {}
    
    try:
        # Run ipsae.py
        result = subprocess.run(
            [
                "python",
                ipsae_script_path,
                str(json_path_obj),
                str(pdb_path_obj),
                str(pae_cutoff),
                str(dist_cutoff),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(pdb_path_obj.parent),  # Run in the PDB directory
        )
        
        if result.returncode != 0:
            logger.debug(f"ipsae.py returned non-zero: {result.stderr[:200]}")
        
        # Read results from output file (NOT stdout!)
        if output_file.exists():
            return _parse_ipsae_output_file(str(output_file))
        else:
            # Try alternative naming patterns
            for pattern in [
                f"{pdb_stem}_{pae_str}_{dist_str}.txt",
                f"{pdb_stem}_0{int(pae_cutoff)}_0{int(dist_cutoff)}.txt",
            ]:
                alt_path = pdb_path_obj.parent / pattern
                if alt_path.exists():
                    return _parse_ipsae_output_file(str(alt_path))
            
            logger.debug(f"IPSAE output file not found: {output_file}")
            return {}
    
    except subprocess.TimeoutExpired:
        logger.debug(f"ipsae.py timed out for {pdb_path}")
        return {}
    except Exception as e:
        logger.debug(f"Error calculating IPSAE: {e}")
        return {}


def _parse_ipsae_output_file(file_path: str) -> Dict[str, Any]:
    """
    Parse IPSAE output file to extract metrics.
    
    File format (tab-separated):
    Chn1 Chn2 PAE Dist Type ipSAE ipSAE_d0chn ipSAE_d0dom ipTM_af pDockQ pDockQ2 LIS ...
    
    We prefer the "max" type row (symmetric maximum) if available.
    
    For antigen-antibody interactions:
    - Use "ipSAE" (max type) as the primary metric (0-1, higher is better)
    - "ipSAE_d0chn" (chain-length normalized) is useful for comparing different antibody sizes
    - "ipSAE_d0dom" (domain normalized) is for multi-domain complexes
    
    See docs/IPSAE_METRICS_GUIDE.md for detailed guidance.
    """
    metrics = {}
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith("Chn1"):  # Skip header
                continue
            
            parts = line.split()
            if len(parts) < 10:
                continue
            
            try:
                chn1, chn2 = parts[0], parts[1]
                pae_val, dist_val = parts[2], parts[3]
                score_type = parts[4]
                ipsae = float(parts[5])
                ipsae_d0chn = float(parts[6])
                ipsae_d0dom = float(parts[7])
                iptm_af = float(parts[8])
                pdockq = float(parts[9]) if len(parts) > 9 else None
                pdockq2 = float(parts[10]) if len(parts) > 10 else None
                lis = float(parts[11]) if len(parts) > 11 else None
                
                # Prefer "max" type (symmetric maximum), otherwise use first valid row
                if score_type == "max" or "ipsae" not in metrics:
                    metrics["ipsae"] = ipsae
                    metrics["ipsae_d0chn"] = ipsae_d0chn
                    metrics["ipsae_d0dom"] = ipsae_d0dom
                    metrics["ipsae_iptm_af"] = iptm_af
                    if pdockq is not None:
                        metrics["ipsae_pdockq"] = pdockq
                    if pdockq2 is not None:
                        metrics["ipsae_pdockq2"] = pdockq2
                    if lis is not None:
                        metrics["ipsae_lis"] = lis
                    
                    # For "max" type, we have the best value, stop parsing
                    if score_type == "max":
                        break
                        
            except (ValueError, IndexError) as e:
                logger.debug(f"Error parsing line: {line[:50]}..., error: {e}")
                continue
        
        return metrics
    
    except Exception as e:
        logger.debug(f"Error reading IPSAE file {file_path}: {e}")
        return {}


def calculate_ipsae_native(
    json_path: str,
    pdb_path: str,
    pae_cutoff: float = 5.0,
    dist_cutoff: float = 5.0,
) -> Dict[str, Any]:
    """
    Calculate IPSAE natively in Python (without calling external script).
    
    This implements the core ipSAE algorithm directly.
    
    Args:
        json_path: Path to AlphaFold JSON file (containing PAE matrix)
        pdb_path: Path to PDB/CIF structure file
        pae_cutoff: PAE cutoff value (default: 5.0)
        dist_cutoff: Distance cutoff for CA-CA contacts (default: 5.0)
    
    Returns:
        Dictionary with IPSAE scores
    """
    try:
        from Bio.PDB import PDBParser, MMCIFParser
        from scipy.spatial.distance import cdist
        
        pdb_path_obj = Path(pdb_path)
        json_path_obj = Path(json_path)
        
        # Load PAE matrix from JSON
        with open(json_path_obj, 'r') as f:
            data = json.load(f)
        
        pae_matrix = None
        if 'pae' in data:
            pae_matrix = np.array(data['pae'])
        elif 'predicted_aligned_error' in data:
            pae_matrix = np.array(data['predicted_aligned_error'])
        
        if pae_matrix is None:
            logger.warning(f"No PAE matrix found in {json_path}")
            return {}
        
        # Parse structure to get CA coordinates and chain information
        is_cif = pdb_path_obj.suffix.lower() in ['.cif', '.mmcif']
        parser = MMCIFParser(QUIET=True) if is_cif else PDBParser(QUIET=True)
        structure = parser.get_structure("protein", str(pdb_path_obj))
        
        # Extract CA coordinates with chain and residue info
        residues_info = []  # List of (chain_id, res_id, coord)
        for model in structure:
            for chain in model:
                for residue in chain:
                    if residue.has_id("CA"):
                        residues_info.append({
                            'chain_id': chain.id,
                            'res_id': residue.id[1],
                            'coord': residue["CA"].coord
                        })
        
        if len(residues_info) == 0:
            logger.warning(f"No CA atoms found in {pdb_path}")
            return {}
        
        # Get unique chains
        chains = list(set(r['chain_id'] for r in residues_info))
        if len(chains) < 2:
            logger.debug(f"Only {len(chains)} chain(s) found, need at least 2 for interface")
            return {"ipsae": 0.0}
        
        # Calculate distance matrix
        coords = np.array([r['coord'] for r in residues_info])
        dist_matrix = cdist(coords, coords)
        
        # Map residue indices to chains
        chain_of_res = [r['chain_id'] for r in residues_info]
        n_res = len(residues_info)
        
        # Find interface contacts: different chains, dist < dist_cutoff, PAE < pae_cutoff
        interface_scores = []
        
        for i in range(n_res):
            for j in range(n_res):
                if i >= j:  # Avoid double counting
                    continue
                if chain_of_res[i] == chain_of_res[j]:  # Same chain
                    continue
                if dist_matrix[i, j] > dist_cutoff:  # Too far
                    continue
                if i < pae_matrix.shape[0] and j < pae_matrix.shape[1]:
                    pae_ij = pae_matrix[i, j]
                    pae_ji = pae_matrix[j, i]
                    if pae_ij < pae_cutoff and pae_ji < pae_cutoff:
                        # Calculate PTM-like score for this contact
                        d0 = 1.0  # Simplified d0
                        score = 1.0 / (1.0 + (min(pae_ij, pae_ji) / d0) ** 2)
                        interface_scores.append(score)
        
        if len(interface_scores) == 0:
            return {"ipsae": 0.0}
        
        # Average interface score (simplified ipSAE)
        ipsae = float(np.mean(interface_scores))
        
        return {
            "ipsae": ipsae,
            "ipsae_n_contacts": len(interface_scores),
        }
    
    except ImportError as e:
        logger.warning(f"Missing dependency for native IPSAE: {e}")
        return {}
    except Exception as e:
        logger.debug(f"Error in native IPSAE calculation: {e}")
        return {}


def get_ipsae_script_path() -> Optional[str]:
    """
    Try to find ipsae.py script in common locations.
    """
    project_root = Path(__file__).parent.parent.parent.parent
    
    possible_paths = [
        project_root / "scripts" / "ipsae.py",  # 优先使用新版本（v4，修复了 AF3 bug）
        project_root / "ipsae.py",
        # 注意：IPSAE-main/ipsae.py 是旧版本（v3），有 IndexError bug，不推荐使用
        # project_root / "IPSAE-main" / "ipsae.py",
        project_root / "tools" / "ipsae.py",
        project_root / "external" / "ipsae.py",
        Path("ipsae.py"),
        Path("scripts/ipsae.py"),
    ]
    
    for path in possible_paths:
        if path.exists():
            return str(path)
    
    return None
