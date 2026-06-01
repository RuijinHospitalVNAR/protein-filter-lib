"""
pDockQ utilities for protein-protein docking quality metrics.

Extracted from germinal/filters/pDockQ.py

Attribution:
Bryant, P., Pozzati, G. & Elofsson, A. Improved prediction of protein-protein interactions using AlphaFold2.
Nat Commun 13, 1265 (2022). https://doi.org/10.1038/s41467-022-28865-w
"""

import numpy as np
import pandas as pd
from collections import defaultdict, OrderedDict
from typing import Dict, List, Tuple
from scipy.spatial.distance import pdist, squareform
from Bio.PDB.PDBParser import PDBParser
from Bio.PDB.MMCIFParser import MMCIFParser
from pathlib import Path

# mdtraj 是可选的（用于某些高级功能）
try:
    import mdtraj as md
    MDTRAJ_AVAILABLE = True
except ImportError:
    MDTRAJ_AVAILABLE = False


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


def parse_atm_record(line: str) -> Dict:
    """Parse ATOM record from PDB line."""
    record = defaultdict()
    record["name"] = line[0:6].strip()
    record["atm_no"] = int(line[6:11])
    record["atm_name"] = line[12:16].strip()
    record["atm_alt"] = line[17]
    record["res_name"] = line[17:20].strip()
    record["chain"] = line[21]
    record["res_no"] = int(line[22:26])
    record["insert"] = line[26].strip()
    record["resid"] = line[22:29]
    record["x"] = float(line[30:38])
    record["y"] = float(line[38:46])
    record["z"] = float(line[46:54])
    record["occ"] = float(line[54:60])
    record["B"] = float(line[60:66])
    return record


def pdb_2_coords(pdb: str, is_cif: bool = False) -> Tuple[Dict[str, List], np.ndarray]:
    """
    Read a PDB or mmCIF file predicted with AF and extract coordinates and pLDDT values.
    
    Extracted from germinal/filters/pDockQ.py:pdb_2_coords()
    Extended to support mmCIF format.
    
    Args:
        pdb: PDB file content as string, or path to mmCIF file
        is_cif: If True, treat input as mmCIF file path; if False, treat as PDB string
    
    Returns:
        Tuple of (chain_coords dict, plddt array)
    """
    chain_coords = defaultdict(list)
    plddt_dict = OrderedDict()

    if is_cif:
        # For CIF files, parse using BioPython
        parser = MMCIFParser(QUIET=True)
        structure = parser.get_structure("protein", pdb)
        
        for model in structure:
            for chain in model:
                for residue in chain:
                    # Get CB or CA for GLY
                    atom_name = "CB" if residue.has_id("CB") else "CA"
                    if residue.has_id(atom_name):
                        atom = residue[atom_name]
                        chain_coords[chain.id].append(list(atom.coord))
                        
                        # Get B-factor (pLDDT) from atom
                        bfactor = atom.get_bfactor()
                        res_id = chain.id + str(residue.id[1])
                        if res_id in plddt_dict:
                            plddt_dict[res_id].append(bfactor)
                        else:
                            plddt_dict[res_id] = [bfactor]
    else:
        # Original PDB parsing logic
        for line in pdb.split("\n"):
            if not line.startswith("ATOM"):
                continue
            record = parse_atm_record(line)

            # Get CB - CA for GLY
            if record["atm_name"] == "CB" or (
                record["atm_name"] == "CA" and record["res_name"] == "GLY"
            ):
                chain_coords[record["chain"]].append(
                    [record["x"], record["y"], record["z"]]
                )
                res_id = record["chain"] + str(record["res_no"])
                if res_id in plddt_dict.keys():
                    plddt_dict[record["chain"] + str(record["res_no"])].append(record["B"])
                else:
                    plddt_dict[record["chain"] + str(record["res_no"])] = [record["B"]]

    plddt = np.array([np.mean(plddts) for plddts in plddt_dict.values()])

    return chain_coords, plddt


def calc_pdockq(
    chain_coords: Dict[str, List],
    plddt: np.ndarray,
    contact_cutoff: float = 8.0
) -> Tuple[float, float, int]:
    """
    Calculate pDockQ score.
    
    Extracted from germinal/filters/pDockQ.py:calc_pdockq()
    
    N-chain pDockQ:
      - Builds a full distance matrix across all chains
      - Uses only cross-chain contacts (< contact_cutoff Å)
      - Averages plDDT over unique interface residues
      - Counts unique contacts (upper-triangular, cross-chain)
    
    Args:
        chain_coords: Dictionary mapping chain IDs to coordinate lists
        plddt: Array of pLDDT values
        contact_cutoff: Distance cutoff for contacts (default: 8.0 Å)
    
    Returns:
        Tuple of (pdockq, avg_if_plddt, n_if_contacts)
    """
    # Concatenate coords in key order and track chain index per residue
    chains = list(chain_coords.keys())
    coords_list = []
    chain_idx = []
    for ci, ch in enumerate(chains):
        arr = np.asarray(chain_coords[ch], dtype=float)
        coords_list.append(arr)
        chain_idx.append(np.full(arr.shape[0], ci, dtype=int))
    coords = np.vstack(coords_list)
    chain_idx = np.concatenate(chain_idx)

    # Sanity check on lengths
    if coords.shape[0] != plddt.shape[0]:
        raise ValueError(
            f"Length mismatch: total residues from coords={coords.shape[0]} vs pLDDT={plddt.shape[0]}"
        )

    # Pairwise distances (N x N)
    diff = coords[:, None, :] - coords[None, :, :]
    dists = np.sqrt(np.sum(diff * diff, axis=-1))

    # Cross-chain mask (exclude same-chain and diagonal)
    same_chain = chain_idx[:, None] == chain_idx[None, :]
    cross_chain = ~same_chain
    np.fill_diagonal(cross_chain, False)

    # Contact mask: cross-chain & within cutoff
    contact_mask = (dists <= contact_cutoff) & cross_chain

    # Count unique contacts (upper triangle to avoid double counting)
    n_if_contacts = int(np.count_nonzero(np.triu(contact_mask, 1)))

    if n_if_contacts == 0:
        return 0.0, 0.0, 0

    # Interface residues = unique residues participating in any cross-chain contact
    sym_mask = contact_mask | contact_mask.T
    interface_res = np.where(sym_mask.any(axis=1))[0]

    # Average interface pLDDT
    avg_if_plddt = float(np.mean(plddt[interface_res]))

    # pDockQ formula
    x = avg_if_plddt * np.log10(n_if_contacts + 1)  # +1 to avoid log10(0)
    pdockq = 0.724 / (1.0 + np.exp(-0.052 * (x - 152.611))) + 0.018

    return float(pdockq), avg_if_plddt, n_if_contacts


def compute_pdockq(pdb: str) -> Tuple[float, float, int, float]:
    """
    Compute pDockQ from PDB string.
    
    Extracted from germinal/filters/pDockQ.py:compute_pdockq()
    
    Returns:
        Tuple of (pdockq, avg_if_plddt, n_if_contacts, mean_plddt)
    """
    chain_coords, plddt = pdb_2_coords(pdb)
    pdockq, avg_if_plddt, n_if_contacts = calc_pdockq(chain_coords, plddt)
    return pdockq, avg_if_plddt, n_if_contacts, plddt.mean()


def get_pdockq(pdb_path: str) -> float:
    """
    Get pDockQ score from PDB or mmCIF file.
    
    Extracted from germinal/filters/pDockQ.py:get_pdockq()
    Extended to support mmCIF format.
    
    Args:
        pdb_path: Path to PDB or mmCIF file
    
    Returns:
        pDockQ score
    """
    if _is_cif_file(pdb_path):
        # For CIF files, use structure parser
        chain_coords, plddt = pdb_2_coords(pdb_path, is_cif=True)
        pdockq, _, _ = calc_pdockq(chain_coords, plddt)
        return pdockq
    else:
        # For PDB files, use original string-based parsing
        with open(pdb_path, "r") as fh:
            pdb = fh.read()
            pdockq, _, _, _ = compute_pdockq(pdb)
        return pdockq


def retrieve_IFplddt(structure, chain1: str, chain2_lst: List[str], max_dist: float):
    """
    Retrieve interface pLDDT values.
    
    Extracted from germinal/filters/pDockQ.py:retrieve_IFplddt()
    """
    chain_lst = list(chain1) + chain2_lst

    ifplddt = []
    contact_chain_lst = []
    for res1 in structure[0][chain1]:
        for chain2 in chain2_lst:
            count = 0
            for res2 in structure[0][chain2]:
                if res1.has_id("CA") and res2.has_id("CA"):
                    dis = abs(res1["CA"] - res2["CA"])
                    if dis <= max_dist:
                        ifplddt.append(res1["CA"].get_bfactor())
                        count += 1
                elif res1.has_id("CB") and res2.has_id("CB"):
                    dis = abs(res1["CB"] - res2["CB"])
                    if dis <= max_dist:
                        ifplddt.append(res1["CB"].get_bfactor())
                        count += 1
            if count > 0:
                contact_chain_lst.append(chain2)
    contact_chain_lst = sorted(list(set(contact_chain_lst)))

    if len(ifplddt) > 0:
        IF_plddt_avg = np.mean(ifplddt)
    else:
        IF_plddt_avg = 0

    return IF_plddt_avg, contact_chain_lst


def retrieve_IFPAEinter(structure, pae: np.ndarray, remain_contact_lst: List[List[str]], distance: float = 10.0) -> List[float]:
    """
    Retrieve interface PAE values.
    
    Extracted from germinal/filters/pDockQ.py:retrieve_IFPAEinter()
    
    Args:
        structure: BioPython structure object
        pae: PAE matrix (numpy array)
        remain_contact_lst: List of contacting chains for each chain
        distance: Distance cutoff for interface (default: 10.0 Å)
    
    Returns:
        List of average interface PAE values for each chain
    """
    chains = []
    for chain in structure[0]:
        chains.append(chain.id)
    
    # Get chain boundaries
    chain_lengths = {}
    cum_length = 0
    for ch in chains:
        chain_lengths[ch] = (cum_length, cum_length + len(structure[0][ch]))
        cum_length += len(structure[0][ch])
    
    avgif_pae = []
    for idx in range(len(chains)):
        chain2_lst = remain_contact_lst[idx]
        if len(chain2_lst) == 0:
            avgif_pae.append(0.0)
            continue
        
        # Extract PAE values for interface residues
        pae_values = []
        chain1 = chains[idx]
        start1, end1 = chain_lengths[chain1]
        
        for res1_idx, res1 in enumerate(structure[0][chain1]):
            for chain2 in chain2_lst:
                start2, end2 = chain_lengths[chain2]
                for res2_idx, res2 in enumerate(structure[0][chain2]):
                    if res1.has_id("CA") and res2.has_id("CA"):
                        dis = abs(res1["CA"] - res2["CA"])
                        if dis <= distance:
                            # Get PAE value from matrix
                            pae_val = pae[start1 + res1_idx, start2 + res2_idx]
                            pae_values.append(pae_val)
                    elif res1.has_id("CB") and res2.has_id("CB"):
                        dis = abs(res1["CB"] - res2["CB"])
                        if dis <= distance:
                            pae_val = pae[start1 + res1_idx, start2 + res2_idx]
                            pae_values.append(pae_val)
        
        if len(pae_values) > 0:
            # Normalize PAE values (as in original Germinal implementation)
            # Formula: mean(1 / (1 + (PAE / d)^2)) where d = distance
            d = distance
            norm_if_interpae = np.mean(1 / (1 + (np.array(pae_values) / d) ** 2))
            avgif_pae.append(norm_if_interpae)
        else:
            avgif_pae.append(0.0)
    
    return avgif_pae


def sigmoid(x: np.ndarray, L: float, x0: float, k: float, b: float) -> np.ndarray:
    """
    Sigmoid function.
    
    Extracted from germinal/filters/pDockQ.py:sigmoid()
    """
    y = L / (1 + np.exp(-k * (x - x0))) + b
    return y


def calc_pmidockq(ifpae_norm: List[float], ifplddt: List[float]) -> pd.DataFrame:
    """
    Calculate pmiDockQ (pDockQ2).
    
    Extracted from germinal/filters/pDockQ.py:calc_pmidockq()
    """
    df = pd.DataFrame()
    df["ifpae_norm"] = ifpae_norm
    df["ifplddt"] = ifplddt
    df["prot"] = df.ifpae_norm * df.ifplddt
    fitpopt = [
        1.31034849e00,
        8.47326241e01,
        7.47157696e-02,
        5.01886443e-03,
    ]  # from original fit function
    df["pmidockq"] = sigmoid(df.prot.values, *fitpopt)
    return df


def pDockQ2(pdb_path: str, pae: np.ndarray, distance: float = 10.0) -> Tuple[pd.DataFrame, Dict]:
    """
    Calculate pDockQ2 score.
    
    Extracted from germinal/filters/pDockQ.py:pDockQ2()
    Extended to support mmCIF format.
    
    Args:
        pdb_path: Path to PDB or mmCIF file
        pae: PAE matrix (numpy array)
        distance: Distance cutoff for interface definition (default: 10.0 Å)
    
    Returns:
        Tuple of (pDockQ2 DataFrame, chain_specific_pdockq2 dict)
    """
    pdbp = _get_parser(pdb_path)
    structure = pdbp.get_structure("", pdb_path)
    chains = []
    for chain in structure[0]:
        chains.append(chain.id)

    remain_contact_lst = []
    # Retrieve interface plDDT at chain-level
    plddt_lst = []
    for idx in range(len(chains)):
        chain2_lst = list(set(chains) - {chains[idx]})
        IF_plddt, contact_lst = retrieve_IFplddt(
            structure, chains[idx], chain2_lst, distance
        )
        plddt_lst.append(IF_plddt)
        remain_contact_lst.append(contact_lst)

    avgif_pae = retrieve_IFPAEinter(structure, pae, remain_contact_lst, distance)
    # Calculate pmiDockQ
    res = calc_pmidockq(avgif_pae, plddt_lst)
    pdock_scores = np.array(res.get("pmidockq"))
    chains_result = {
        ''.join(k): (v1, v2, v3) 
        for k, v1, v2, v3 in zip(remain_contact_lst, plddt_lst, avgif_pae, pdock_scores)
    }
    
    return res, chains_result


def _transform_pae_matrix(pae_matrix: np.ndarray, pae_cutoff: float = 12.0) -> np.ndarray:
    """
    Transform PAE matrix to LIS scores.
    
    Extracted from germinal/filters/pDockQ.py:_transform_pae_matrix()
    """
    transformed_pae = np.zeros_like(pae_matrix)
    within_cutoff = pae_matrix < pae_cutoff
    transformed_pae[within_cutoff] = 1 - (pae_matrix[within_cutoff] / pae_cutoff)
    return transformed_pae


def _get_chain_lengths(pdb_path: str) -> Dict[str, int]:
    """
    Get chain lengths from PDB or mmCIF file.
    
    Extracted from germinal/filters/pDockQ.py:_get_chain_lengths()
    Extended to support mmCIF format.
    """
    parser = _get_parser(pdb_path)
    structure = parser.get_structure("", pdb_path)
    chain_lengths: Dict[str, int] = {}
    for chain in structure[0]:
        chain_lengths[chain.id] = len(chain)
    return chain_lengths


def _calculate_contact_map(pdb_path: str, distance_threshold: float = 8.0) -> np.ndarray:
    """
    Calculate contact map from PDB coordinates.
    
    Extracted from germinal/filters/pDockQ.py:_calculate_contact_map()
    
    Note: Requires mdtraj. If not available, falls back to BioPython-based method.
    """
    if not MDTRAJ_AVAILABLE:
        # Fallback: use BioPython parser instead
        parser = _get_parser(pdb_path)
        structure = parser.get_structure("", pdb_path)
        
        # Extract CB coordinates (or CA for Glycine)
        coords = []
        for model in structure:
            for chain in model:
                for residue in chain:
                    if residue.has_id("CB"):
                        coords.append(residue["CB"].coord)
                    elif residue.resname == "GLY" and residue.has_id("CA"):
                        coords.append(residue["CA"].coord)
        
        if len(coords) == 0:
            return np.array([])
        
        coords = np.array(coords)
        distances = squareform(pdist(coords))
        contact_map = (distances < distance_threshold).astype(int)
        return contact_map
    
    # Use mdtraj if available (more efficient)
    traj = md.load_pdb(pdb_path)
    
    # Select C-beta atoms (and C-alpha for Glycine)
    cb_selection = traj.topology.select("name CB or (resname GLY and name CA)")
    
    if cb_selection.size == 0:
        return np.array([])
    
    # Get coordinates of selected atoms
    coords = traj.xyz[0, cb_selection, :]
    
    # Calculate pairwise distances and contact map
    distances = squareform(pdist(coords))
    contact_map = (distances < distance_threshold).astype(int)
    
    return contact_map


def _calculate_mean_lis(
    transformed_pae: np.ndarray,
    subunit_sizes: List[int]
) -> np.ndarray:
    """
    Calculate mean LIS for each subunit pair.
    
    Extracted from germinal/filters/pDockQ.py:_calculate_mean_lis()
    """
    cum_lengths = np.cumsum(subunit_sizes)
    start_indices = np.concatenate(([0], cum_lengths[:-1]))
    
    mean_lis_matrix = np.zeros((len(subunit_sizes), len(subunit_sizes)))
    
    for i in range(len(subunit_sizes)):
        for j in range(len(subunit_sizes)):
            start_i, end_i = start_indices[i], cum_lengths[i]
            start_j, end_j = start_indices[j], cum_lengths[j]
            
            submatrix = transformed_pae[start_i:end_i, start_j:end_j]
            mean_lis = submatrix[submatrix > 0].mean()
            mean_lis_matrix[i, j] = mean_lis if not np.isnan(mean_lis) else 0
    
    return mean_lis_matrix


def _calculate_count_metrics(
    transformed_pae: np.ndarray,
    combined_map: np.ndarray,
    subunit_sizes: List[int]
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate count-based metrics (LIA, LIR, cLIA, cLIR).
    
    Extracted from germinal/filters/pDockQ.py:_calculate_count_metrics()
    """
    n_subunits = len(subunit_sizes)
    lia_matrix = np.zeros((n_subunits, n_subunits), dtype=int)
    lir_matrix = np.zeros((n_subunits, n_subunits), dtype=int)
    clia_matrix = np.zeros((n_subunits, n_subunits), dtype=int)
    clir_matrix = np.zeros((n_subunits, n_subunits), dtype=int)
    
    cum_lengths = np.cumsum(subunit_sizes)
    starts = np.concatenate(([0], cum_lengths[:-1]))
    
    for i in range(n_subunits):
        for j in range(n_subunits):
            start_i, end_i = starts[i], cum_lengths[i]
            start_j, end_j = starts[j], cum_lengths[j]
            
            # LIA and LIR
            lia_submatrix = (transformed_pae[start_i:end_i, start_j:end_j] > 0).astype(int)
            lia_matrix[i, j] = np.count_nonzero(lia_submatrix)
            residues_i = np.unique(np.where(lia_submatrix > 0)[0]) + 1
            residues_j = np.unique(np.where(lia_submatrix > 0)[1]) + 1
            lir_matrix[i, j] = len(residues_i) + len(residues_j)
            
            # cLIA and cLIR
            clia_submatrix = (combined_map[start_i:end_i, start_j:end_j] > 0).astype(int)
            clia_matrix[i, j] = np.count_nonzero(clia_submatrix)
            residues_i = np.unique(np.where(clia_submatrix > 0)[0]) + 1
            residues_j = np.unique(np.where(clia_submatrix > 0)[1]) + 1
            clir_matrix[i, j] = len(residues_i) + len(residues_j)
    
    return lia_matrix, lir_matrix, clia_matrix, clir_matrix


def calculate_lis(
    pdb_path: str,
    pae_matrix: np.ndarray,
    pae_cutoff: float = 12.0,
    distance_cutoff: float = 8.0,
) -> Dict[str, np.ndarray]:
    """
    Calculate Local Interaction Score (LIS) for protein complexes.
    
    Extracted from germinal/filters/pDockQ.py:calculate_lis()
    
    Args:
        pdb_path: Path to PDB file
        pae_matrix: PAE matrix (numpy array)
        pae_cutoff: PAE threshold for LIS calculation (default: 12)
        distance_cutoff: Distance threshold for contacts (default: 8Å)
    
    Returns:
        dict: Contains LIS, cLIS, iLIS, LIA, cLIA, LIR, cLIR scores
    """
    # Transform PAE matrix to LIS
    transformed_pae = _transform_pae_matrix(pae_matrix, pae_cutoff)
    
    # Get chain boundaries
    chain_lengths = _get_chain_lengths(pdb_path)
    subunit_sizes = list(chain_lengths.values())
    
    # Calculate contact map
    contact_map = _calculate_contact_map(pdb_path, distance_cutoff)
    
    # Calculate LIS matrix
    mean_lis_matrix = _calculate_mean_lis(transformed_pae, subunit_sizes)
    
    # Calculate cLIS (contact-based LIS)
    combined_map = np.where(
        (transformed_pae > 0) & (contact_map == 1), transformed_pae, 0
    )
    mean_clis_matrix = _calculate_mean_lis(combined_map, subunit_sizes)
    
    # Calculate iLIS = sqrt(LIS * cLIS)
    ilis_matrix = np.sqrt(mean_lis_matrix * mean_clis_matrix)
    
    # Calculate count-based metrics
    lia_matrix, lir_matrix, clia_matrix, clir_matrix = _calculate_count_metrics(
        transformed_pae, combined_map, subunit_sizes
    )
    
    return {
        "LIS": mean_lis_matrix,
        "cLIS": mean_clis_matrix,
        "iLIS": ilis_matrix,
        "LIA": lia_matrix,
        "cLIA": clia_matrix,
        "LIR": lir_matrix,
        "cLIR": clir_matrix,
    }

