"""
Individual metric calculators.
"""

from typing import Dict, Any, List, Optional
import logging
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

from ..design import Design
from ..config import MetricConfig

logger = logging.getLogger(__name__)


class ClashCalculator:
    """Calculate clash scores."""
    
    def calculate(self, pdb_path: str, design: Design) -> Dict[str, Any]:
        """
        Calculate clash scores.
        
        Extracted from germinal/utils/utils.py:calculate_clash_score()
        """
        from ..utils.pdb_utils import calculate_clash_score
        
        # Calculate clashes for all heavy atoms
        clashes_all = calculate_clash_score(pdb_path, threshold=2.4, only_ca=False)
        
        # Also calculate CA-only clashes for comparison
        clashes_ca = calculate_clash_score(pdb_path, threshold=2.4, only_ca=True)
        
        return {
            "clashes": clashes_all,
            "clashes_ca": clashes_ca,
        }
    
    def get_metric_names(self) -> List[str]:
        return ["clashes", "clashes_ca"]


class InterfaceCalculator:
    """Calculate interface metrics using PyRosetta."""
    
    def calculate(self, pdb_path: str, design: Design) -> Dict[str, Any]:
        """
        Calculate interface metrics.
        
        Extracted from germinal/filters/pyrosetta_utils.py:score_interface()
        """
        try:
            import pyrosetta as pr
            from pyrosetta.rosetta.protocols.analysis import InterfaceAnalyzerMover
            from pyrosetta.rosetta.core.select.residue_selector import ChainSelector
            from pyrosetta.rosetta.core.select.residue_selector import (
                SecondaryStructureSelector,
                AndResidueSelector,
            )
            from pyrosetta.rosetta.core.scoring.sc import ShapeComplementarityCalculator
            from pyrosetta.rosetta.core.scoring.dssp import Dssp
            from pyrosetta.rosetta.protocols.rosetta_scripts import XmlObjects
            from ..utils.pdb_utils import hotspot_residues
            
            # Load pose
            pose = pr.pose_from_pdb(pdb_path)
            
            # Setup InterfaceAnalyzer
            iam = InterfaceAnalyzerMover()
            # Set interface based on chains
            target_chains = design.target_chain.split(",")
            binder_chains = design.binder_chain.split(",")
            interface_str = "_".join(sorted(set(target_chains + binder_chains)))
            iam.set_interface(interface_str)
            
            scorefxn = pr.get_fa_scorefxn()
            iam.set_scorefunction(scorefxn)
            iam.set_compute_packstat(True)
            iam.set_compute_interface_energy(True)
            iam.set_calc_dSASA(True)
            iam.set_calc_hbond_sasaE(True)
            iam.set_compute_interface_sc(True)
            iam.set_pack_separated(True)
            iam.apply(pose)
            
            # Initialize dictionary with all amino acids
            interface_AA = {aa: 0 for aa in "ACDEFGHIKLMNPQRSTVWY"}
            
            # Get interface residues
            interface_residues_set = hotspot_residues(
                pdb_path, design.binder_chain, target_chain=design.target_chain
            )
            interface_residues_pdb_ids = []
            
            # Iterate over the interface residues
            for pdb_res_num, aa_type in interface_residues_set.items():
                interface_AA[aa_type] += 1
                interface_residues_pdb_ids.append(f"{design.binder_chain}{pdb_res_num}")
            
            interface_nres = len(interface_residues_pdb_ids)
            interface_residues_pdb_ids_str = ",".join(interface_residues_pdb_ids)
            
            # Calculate hydrophobic percentage
            hydrophobic_aa = set("ACFILMPVWY")
            hydrophobic_count = sum(interface_AA[aa] for aa in hydrophobic_aa)
            if interface_nres != 0:
                interface_hydrophobicity = (hydrophobic_count / interface_nres) * 100
            else:
                interface_hydrophobicity = 0
            
            # Retrieve statistics
            interfacescore = iam.get_all_data()
            interface_sc = interfacescore.sc_value  # shape complementarity
            
            # Calculate loop shape complementarity
            interface_loop_sc, interface_loop_sc_area = self._calculate_loop_sc(
                pose, design.binder_chain, design.target_chain
            )
            
            interface_interface_hbonds = interfacescore.interface_hbonds
            interface_dG = iam.get_interface_dG()
            interface_dSASA = iam.get_interface_delta_sasa()
            interface_packstat = iam.get_interface_packstat()
            interface_dG_SASA_ratio = interfacescore.dG_dSASA_ratio * 100
            
            # Calculate buried unsatisfied hydrogen bonds
            buns_filter = XmlObjects.static_get_filter(
                '<BuriedUnsatHbonds report_all_heavy_atom_unsats="true" scorefxn="scorefxn" '
                'ignore_surface_res="false" use_ddG_style="true" dalphaball_sasa="1" '
                'probe_radius="1.1" burial_cutoff_apo="0.2" confidence="0" />'
            )
            interface_delta_unsat_hbonds = buns_filter.report_sm(pose)
            
            if interface_nres != 0:
                interface_hbond_percentage = (interface_interface_hbonds / interface_nres) * 100
                interface_bunsch_percentage = (interface_delta_unsat_hbonds / interface_nres) * 100
            else:
                interface_hbond_percentage = None
                interface_bunsch_percentage = None
            
            # Calculate binder energy score
            chain_design = ChainSelector(design.binder_chain)
            tem = pr.rosetta.core.simple_metrics.metrics.TotalEnergyMetric()
            tem.set_scorefunction(scorefxn)
            tem.set_residue_selector(chain_design)
            binder_score = tem.calculate(pose)
            
            # Calculate binder SASA fraction
            bsasa = pr.rosetta.core.simple_metrics.metrics.SasaMetric()
            bsasa.set_residue_selector(chain_design)
            binder_sasa = bsasa.calculate(pose)
            
            if binder_sasa > 0:
                interface_binder_fraction = (interface_dSASA / binder_sasa) * 100
            else:
                interface_binder_fraction = 0
            
            # Calculate surface hydrophobicity
            binder_pose = {
                pose.pdb_info().chain(pose.conformation().chain_begin(i)): p
                for i, p in zip(range(1, pose.num_chains() + 1), pose.split_by_chain())
            }[design.binder_chain]
            
            layer_sel = pr.rosetta.core.select.residue_selector.LayerSelector()
            layer_sel.set_layers(pick_core=False, pick_boundary=False, pick_surface=True)
            surface_res = layer_sel.apply(binder_pose)
            
            exp_apol_count = 0
            total_count = 0
            
            # Count apolar and aromatic residues at the surface
            for i in range(1, len(surface_res) + 1):
                if surface_res[i] == True:
                    res = binder_pose.residue(i)
                    if (
                        res.is_apolar() == True
                        or res.name() == "PHE"
                        or res.name() == "TRP"
                        or res.name() == "TYR"
                    ):
                        exp_apol_count += 1
                    total_count += 1
            
            surface_hydrophobicity = exp_apol_count / total_count if total_count > 0 else 0
            
            # Build metrics dictionary
            metrics = {
                "binder_score": binder_score,
                "surface_hydrophobicity": surface_hydrophobicity,
                "interface_sc": interface_sc,
                "interface_loop_sc": interface_loop_sc,
                "interface_loop_sc_area": interface_loop_sc_area,
                "interface_packstat": interface_packstat,
                "interface_dG": interface_dG,
                "interface_dSASA": interface_dSASA,
                "interface_dG_SASA_ratio": interface_dG_SASA_ratio,
                "interface_fraction": interface_binder_fraction,
                "interface_hydrophobicity": interface_hydrophobicity,
                "interface_nres": interface_nres,
                "interface_hbonds": interface_interface_hbonds,
                "interface_hbond_percentage": interface_hbond_percentage,
                "interface_delta_unsat_hbonds": interface_delta_unsat_hbonds,
                "interface_delta_unsat_hbonds_percentage": interface_bunsch_percentage,
                "interface_AA": interface_AA,
                "interface_residues": interface_residues_pdb_ids_str,
            }
            
            # Round float values to 2 decimal places
            metrics = {
                k: round(v, 2) if isinstance(v, float) else v
                for k, v in metrics.items()
            }
            
            return metrics
        
        except ImportError:
            logger.warning("PyRosetta not available for interface calculation")
            return {}
        except Exception as e:
            logger.error(f"Error calculating interface metrics: {e}")
            return {}
    
    @staticmethod
    def _calculate_loop_sc(pose, binder_chain="B", target_chain="A"):
        """
        Calculate shape complementarity between loop residues.
        
        Extracted from germinal/filters/pyrosetta_utils.py:calculate_loop_sc()
        """
        import pyrosetta as pr
        from pyrosetta.rosetta.core.scoring.dssp import Dssp
        from pyrosetta.rosetta.core.select.residue_selector import (
            SecondaryStructureSelector,
            ChainSelector,
            AndResidueSelector,
        )
        from pyrosetta.rosetta.core.scoring.sc import ShapeComplementarityCalculator
        
        # Run DSSP to get secondary structure assignment
        dssp = Dssp(pose)
        dssp.insert_ss_into_pose(pose)
        
        # Select residues in binder chain with loop secondary structure
        ss_selector = SecondaryStructureSelector()
        ss_selector.set_selected_ss("L")
        chain_selector = ChainSelector(binder_chain)
        loop_selector = AndResidueSelector(ss_selector, chain_selector)
        residue_mask = loop_selector.apply(pose)
        loop_residues = []
        for i, selected in enumerate(residue_mask, 1):
            if selected:
                loop_residues.append(i)
        
        # Create calculator instance
        sc_calc = ShapeComplementarityCalculator()
        sc_calc.Init()
        
        # Add loop residues from binder chain
        for res_id in loop_residues:
            residue = pose.residue(res_id)
            sc_calc.AddResidue(1, residue)  # 1 = first molecule in comparison
        
        # Add all residues from target chain
        target_chain_list = target_chain.split(",") if isinstance(target_chain, str) else target_chain
        for res_id in range(1, pose.total_residue() + 1):
            if pose.chain(res_id) in target_chain_list:
                residue = pose.residue(res_id)
                sc_calc.AddResidue(2, residue)  # 2 = second molecule in comparison
        
        # Calculate the shape complementarity
        sc_calc.Calc()
        
        # Get results
        results = sc_calc.GetResults()
        sc_score = results.sc
        sc_area = results.area
        
        return sc_score, sc_area
    
    def get_metric_names(self) -> List[str]:
        return [
            "binder_score",
            "surface_hydrophobicity",
            "interface_sc",
            "interface_loop_sc",
            "interface_loop_sc_area",
            "interface_packstat",
            "interface_dG",
            "interface_dSASA",
            "interface_dG_SASA_ratio",
            "interface_fraction",
            "interface_hydrophobicity",
            "interface_nres",
            "interface_hbonds",
            "interface_hbond_percentage",
            "interface_delta_unsat_hbonds",
            "interface_delta_unsat_hbonds_percentage",
        ]


class ConfidenceCalculator:
    """Calculate confidence metrics from structure prediction."""
    
    def calculate(self, pdb_path: str, design: Design) -> Dict[str, Any]:
        """
        Extract confidence metrics from PDB B-factors (pLDDT).
        
        Extracts pLDDT values from PDB B-factor field.
        AlphaFold3 and other prediction tools store pLDDT in the B-factor column.
        
        Args:
            pdb_path: Path to PDB file
            design: Design object
        
        Returns:
            Dictionary with pLDDT metrics (empty if extraction fails)
        """
        try:
            from ..utils.pdockq_utils import pdb_2_coords
            
            # Read PDB file
            with open(pdb_path, 'r') as f:
                pdb_content = f.read()
            
            # Extract coordinates and pLDDT
            chain_coords, plddt_array = pdb_2_coords(pdb_content)
            
            if len(plddt_array) == 0:
                logger.warning(f"No pLDDT values found in {pdb_path}")
                return {}
            
            # pLDDT is stored as B-factor (0-100), normalize to 0-1
            plddt_normalized = plddt_array / 100.0
            
            # Calculate statistics
            metrics = {
                "plddt": float(np.mean(plddt_normalized)),
                "plddt_min": float(np.min(plddt_normalized)),
                "plddt_max": float(np.max(plddt_normalized)),
                "plddt_std": float(np.std(plddt_normalized)),
            }
            
            # Calculate chain-specific pLDDT if multiple chains
            if len(chain_coords) > 1:
                # Extract pLDDT per chain
                chain_plddt = {}
                cum_idx = 0
                for chain_id, coords in chain_coords.items():
                    chain_len = len(coords)
                    chain_plddt_values = plddt_normalized[cum_idx:cum_idx + chain_len]
                    chain_plddt[f"plddt_{chain_id}"] = float(np.mean(chain_plddt_values))
                    cum_idx += chain_len
                metrics.update(chain_plddt)
            
            return metrics
        
        except Exception as e:
            logger.warning(f"Error extracting pLDDT from {pdb_path}: {e}")
            return {}
    
    def get_metric_names(self) -> List[str]:
        return ["plddt", "plddt_min", "plddt_max", "plddt_std"]


class SAPCalculator:
    """Calculate SAP (Spatial Aggregation Propensity) scores."""
    
    def __init__(self, config: MetricConfig):
        self.config = config
    
    def calculate(self, pdb_path: str, design: Design) -> Dict[str, Any]:
        """
        Calculate SAP scores.
        
        Extracted from germinal/filters/pyrosetta_utils.py:get_sap_score()
        """
        try:
            import numpy as np
            import pyrosetta as pr
            from pyrosetta.rosetta.core.pack.guidance_scoreterms.sap import (
                calculate_per_res_sap
            )
            from pyrosetta.rosetta.core.select.residue_selector import (
                TrueResidueSelector,
                ChainSelector,
            )
            from pyrosetta.rosetta.core.select.residue_selector import (
                ResidueIndexSelector,
                NeighborhoodResidueSelector,
            )
            from pyrosetta.rosetta.core.pose import Pose
            
            pose_ = pr.pose_from_pdb(pdb_path)
            
            selector = TrueResidueSelector()
            if design.binder_chain is not None and True:  # only_binder=True
                idxs = {"A": 1, "B": 2, "C": 3, "D": 4}
                pose = Pose()
                pose = pose_.split_by_chain(idxs[design.binder_chain])
            else:
                pose = pose_
                if design.binder_chain is not None:
                    selector = ChainSelector(design.binder_chain)
            
            num_residues = pose.total_residue()
            
            # Hydrophobic amino acids
            hydrophobic_aa = ["LEU", "ILE", "PHE", "TRP", "VAL", "MET", "TYR", "ALA"]
            
            # Calculate SAP scores
            sap_score = calculate_per_res_sap(
                pose=pose, score_sel=selector, sap_calculate_sel=selector, sasa_sel=selector
            )
            
            # Helper functions
            def avg_sap_hydrophobic_patch(sap_score, residues):
                avg_sap = 0
                for r in residues:
                    avg_sap += sap_score[r[0]]
                avg_sap = avg_sap / len(residues) if len(residues) > 0 else 0
                return avg_sap
            
            def patch_exists(hydrophobic_patches, nearby_res):
                if len(hydrophobic_patches) < 1:
                    return False
                else:
                    nrb = set(nearby_res)
                    for hp in hydrophobic_patches:
                        prev = set(hp[1])
                        if len(nrb - prev) <= len(nrb) - 2:
                            return True
                    return False
            
            def get_nearby_residues(pose, target_residue_number, distance=8.0):
                """Get all residues within a specified distance of a target residue."""
                target_selector = ResidueIndexSelector(target_residue_number)
                neighbor_selector = NeighborhoodResidueSelector()
                neighbor_selector.set_focus_selector(target_selector)
                neighbor_selector.set_distance(distance)
                
                nearby_residues = []
                for i in range(1, pose.total_residue() + 1):
                    if neighbor_selector.apply(pose)[i]:
                        nearby_residues.append((i, pose.residue(i).name3()))
                
                return nearby_residues
            
            # Find exposed hydrophobic patches
            exposed_hydrophobic_aa = []
            hydrophobic_patches = []
            
            limit_sasa = self.config.sap_limit_sasa
            patch_radius = self.config.sap_patch_radius
            avg_sasa_patch_thr = self.config.sap_avg_sasa_patch_thr
            
            for i in range(1, num_residues + 1):
                aa_type = pose.residue(i).name3()
                if design.binder_chain is not None and pose.pdb_info().chain(i) != design.binder_chain:
                    continue
                if aa_type in hydrophobic_aa and (sap_score[i]) >= limit_sasa:
                    exposed_hydrophobic_aa.append((i, aa_type))
                    nearby_res = get_nearby_residues(pose, i, distance=patch_radius)
                    avg_sap_patch = avg_sap_hydrophobic_patch(sap_score, nearby_res)
                    
                    if avg_sap_patch >= avg_sasa_patch_thr:
                        if not patch_exists(hydrophobic_patches, nearby_res):
                            hydrophobic_patches.append((avg_sap_patch, nearby_res))
            
            # Calculate CDR SAP if CDR positions are provided
            cdr_sap = np.array(sap_score)
            if design.cdr_positions is not None and len(design.cdr_positions) > 0:
                # Convert CDR positions to 1-based indices if needed
                cdr_indices = [pos + 1 if pos < len(cdr_sap) else pos for pos in design.cdr_positions]
                cdr_sap = sum([cdr_sap[i] for i in cdr_indices if i <= len(cdr_sap)])
            else:
                cdr_sap = sum(cdr_sap)
            
            total_sap = sum(sap_score)
            
            return {
                "sap_score": float(total_sap),
                "cdr_sap": float(cdr_sap),
                "hydrophobic_patches_binder": len(hydrophobic_patches),
            }
        
        except ImportError:
            logger.warning("PyRosetta not available for SAP calculation")
            return {}
        except Exception as e:
            logger.error(f"Error calculating SAP scores: {e}")
            return {}
    
    def get_metric_names(self) -> List[str]:
        return ["sap_score", "cdr_sap", "hydrophobic_patches_binder"]


class SecondaryStructureCalculator:
    """Calculate secondary structure content."""
    
    def calculate(self, pdb_path: str, design: Design) -> Dict[str, Any]:
        """
        Calculate secondary structure percentages.
        
        Extracted from germinal/utils/utils.py:calc_ss_percentage()
        Uses PyRosetta Dssp for secondary structure assignment.
        """
        try:
            import pyrosetta as pr
            from pyrosetta.rosetta.core.scoring.dssp import Dssp
            from ..utils.pdb_utils import hotspot_residues
            
            pose = pr.pose_from_pdb(pdb_path)
            dssp = Dssp(pose)
            dssp.insert_ss_into_pose(pose)
            
            # Count secondary structure types for all residues
            ss_counts = {"H": 0, "E": 0, "L": 0}  # Helix, Sheet, Loop
            ss_interface_counts = {"H": 0, "E": 0, "L": 0}
            
            # Get interface residues
            interface_residues_set = set(
                hotspot_residues(
                    pdb_path, design.binder_chain, target_chain=design.target_chain
                ).keys()
            )
            
            # Count SS types
            for i in range(1, pose.total_residue() + 1):
                ss = pose.secstruct(i)
                chain_id = pose.pdb_info().chain(i)
                
                # Only count binder chain
                if chain_id == design.binder_chain:
                    if ss == "H":
                        ss_counts["H"] += 1
                    elif ss == "E":
                        ss_counts["E"] += 1
                    else:
                        ss_counts["L"] += 1
                    
                    # Check if residue is at interface
                    pdb_res_num = pose.pdb_info().number(i)
                    if pdb_res_num in interface_residues_set:
                        if ss == "H":
                            ss_interface_counts["H"] += 1
                        elif ss == "E":
                            ss_interface_counts["E"] += 1
                        else:
                            ss_interface_counts["L"] += 1
            
            total = sum(ss_counts.values())
            total_interface = sum(ss_interface_counts.values())
            
            # Calculate percentages
            metrics = {
                "alpha_all": ss_counts["H"] / total if total > 0 else 0,
                "beta_all": ss_counts["E"] / total if total > 0 else 0,
                "loops_all": ss_counts["L"] / total if total > 0 else 0,
            }
            
            if total_interface > 0:
                metrics.update({
                    "alpha_interface": ss_interface_counts["H"] / total_interface,
                    "beta_interface": ss_interface_counts["E"] / total_interface,
                    "loops_interface": ss_interface_counts["L"] / total_interface,
                })
            else:
                metrics.update({
                    "alpha_interface": 0,
                    "beta_interface": 0,
                    "loops_interface": 0,
                })
            
            return metrics
        
        except ImportError:
            logger.warning("PyRosetta not available for SS calculation")
            return {}
        except Exception as e:
            logger.error(f"Error calculating secondary structure: {e}")
            return {}
    
    def get_metric_names(self) -> List[str]:
        return [
            "alpha_all",
            "beta_all",
            "loops_all",
            "alpha_interface",
            "beta_interface",
            "loops_interface",
        ]


class PDockQCalculator:
    """Calculate pDockQ, pDockQ2, and LIS metrics."""
    
    def calculate(self, pdb_path: str, design: Design) -> Dict[str, Any]:
        """
        Calculate pDockQ metrics.
        
        Extracted from germinal/filters/pDockQ.py and filter_utils.py:compute_pdockq_and_lis()
        
        Note: Requires PAE matrix from prediction metrics.
        """
        from ..utils.pdockq_utils import get_pdockq, pDockQ2, calculate_lis
        
        metrics = {}
        
        # Calculate basic pDockQ (only needs PDB)
        try:
            pdockq = get_pdockq(pdb_path)
            metrics["pdockq"] = float(pdockq)
        except Exception as e:
            logger.warning(f"Could not calculate pDockQ: {e}")
            metrics["pdockq"] = 0.0
        
        # pDockQ2 and LIS require PAE matrix
        # These will be calculated in aggregator if PAE is available
        # from prediction_metrics
        
        return metrics
    
    def calculate_with_pae(
        self,
        pdb_path: str,
        pae_matrix: np.ndarray,
        binder_chain: str,
        distance: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Calculate pDockQ2 and LIS metrics using PAE matrix.
        
        Args:
            pdb_path: Path to PDB file
            pae_matrix: PAE matrix from structure prediction
            binder_chain: Binder chain ID
            distance: Distance cutoff for interface (default: 10.0 Å)
        
        Returns:
            Dictionary with pDockQ2 and LIS metrics
        """
        import numpy as np
        from ..utils.pdockq_utils import pDockQ2, calculate_lis
        
        metrics = {}
        
        try:
            # Calculate pDockQ2
            pDockQ2_out, chain_specific_pdockq2 = pDockQ2(pdb_path, pae_matrix, distance)
            
            # Extract pDockQ2 for binder chain
            pdockq2_values = []
            for chain_key in chain_specific_pdockq2.keys():
                if binder_chain in chain_key:
                    pdockq2_values.append(chain_specific_pdockq2[chain_key][-1])
            
            if len(pdockq2_values) > 0:
                metrics["pdockq2"] = float(np.mean(pdockq2_values))
                metrics["i_plddt"] = float(pDockQ2_out["ifplddt"].mean() / 100)
                metrics["i_pae"] = float(pDockQ2_out["ifpae_norm"].mean())
            else:
                metrics["pdockq2"] = 0.0
                metrics["i_plddt"] = 0.0
                metrics["i_pae"] = 0.0
            
            # Calculate LIS metrics
            raw_lis_metrics = calculate_lis(pdb_path, pae_matrix)
            
            # Average LIS and LIA for binder-target interface
            # Assuming two-chain complex (binder and target)
            if raw_lis_metrics["LIS"].shape[0] >= 2:
                metrics["lis"] = float(np.mean([
                    raw_lis_metrics["LIS"][0, 1],
                    raw_lis_metrics["LIS"][1, 0]
                ]))
                metrics["lia"] = float(np.mean([
                    raw_lis_metrics["LIA"][0, 1],
                    raw_lis_metrics["LIA"][1, 0]
                ]))
                metrics["clis"] = float(np.mean([
                    raw_lis_metrics["cLIS"][0, 1],
                    raw_lis_metrics["cLIS"][1, 0]
                ]))
                metrics["ilis"] = float(np.mean([
                    raw_lis_metrics["iLIS"][0, 1],
                    raw_lis_metrics["iLIS"][1, 0]
                ]))
            else:
                metrics["lis"] = 0.0
                metrics["lia"] = 0.0
                metrics["clis"] = 0.0
                metrics["ilis"] = 0.0
        
        except Exception as e:
            logger.error(f"Error calculating pDockQ2/LIS metrics: {e}")
            metrics.update({
                "pdockq2": 0.0,
                "i_plddt": 0.0,
                "i_pae": 0.0,
                "lis": 0.0,
                "lia": 0.0,
                "clis": 0.0,
                "ilis": 0.0,
            })
        
        return metrics
    
    def get_metric_names(self) -> List[str]:
        return [
            "pdockq",
            "pdockq2",
            "i_plddt",
            "i_pae",
            "lis",
            "lia",
            "clis",
            "ilis",
        ]


class IPSAECalculator:
    """
    Calculate IPSAE (Scoring function for interprotein interactions in AlphaFold2 and AlphaFold3).
    
    IPSAE improves upon AlphaFold's ipTM score by focusing on high-confidence interface regions,
    avoiding interference from disordered or non-interacting parts.
    
    Source: https://github.com/DunbrackLab/IPSAE/
    
    Requires: Download ipsae.py from https://github.com/DunbrackLab/IPSAE/
    """
    
    def __init__(
        self,
        pae_cutoff: float = 5.0,
        distance_cutoff: float = 5.0,
        ipsae_script_path: Optional[str] = None,
        include_duplicate_metrics: bool = False,
    ):
        """
        Initialize IPSAE calculator.
        
        Args:
            pae_cutoff: PAE cutoff value (default: 5.0)
            distance_cutoff: Distance cutoff in Angstroms for CA-CA contacts (default: 5.0)
            ipsae_script_path: Path to ipsae.py script (if None, searches automatically)
            include_duplicate_metrics: Whether to include metrics that may duplicate existing ones
                (e.g., ipsae_pdockq, ipsae_lis). Set to True for cross-validation.
        """
        self.pae_cutoff = pae_cutoff
        self.distance_cutoff = distance_cutoff
        self.ipsae_script_path = ipsae_script_path
        self.include_duplicate_metrics = include_duplicate_metrics
        self._available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if ipsae.py script is available."""
        from ..utils.ipsae_utils import get_ipsae_script_path
        
        if self.ipsae_script_path:
            return Path(self.ipsae_script_path).exists()
        
        script_path = get_ipsae_script_path()
        if script_path:
            self.ipsae_script_path = script_path
            return True
        
        logger.warning(
            "ipsae.py script not found. Please download from "
            "https://github.com/DunbrackLab/IPSAE/ and place it in the project directory."
        )
        return False
    
    def calculate(
        self,
        pdb_path: str,
        design: Design,
        prediction_metrics: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Calculate IPSAE score using ipsae.py script.
        
        Args:
            pdb_path: Path to PDB structure file
            design: Design object
            prediction_metrics: Optional prediction metrics (should contain PAE matrix or JSON path)
        
        Returns:
            Dictionary with IPSAE score and related metrics
        """
        if not self._available:
            return {}
        
        if prediction_metrics is None:
            prediction_metrics = {}
        
        try:
            from ..utils.ipsae_utils import calculate_ipsae_from_script
            from pathlib import Path
            import tempfile
            import json
            
            # IPSAE requires a JSON file with PAE matrix
            # Try to find or create JSON file from prediction_metrics
            json_path = None
            
            # Option 1: Check if prediction_metrics contains a JSON file path
            if "json_path" in prediction_metrics:
                json_path = prediction_metrics["json_path"]
            elif "json_file" in prediction_metrics:
                json_path = prediction_metrics["json_file"]
            
            # Option 2: Look for JSON file in same directory as PDB
            if json_path is None or not Path(json_path).exists():
                pdb_file = Path(pdb_path)
                json_candidates = [
                    pdb_file.parent / f"{pdb_file.stem}_scores.json",
                    pdb_file.parent / f"{pdb_file.stem}.json",
                    pdb_file.parent / "scores.json",
                ]
                
                for candidate in json_candidates:
                    if candidate.exists():
                        json_path = str(candidate)
                        break
            
            # Option 3: Create temporary JSON file from PAE matrix
            if json_path is None or not Path(json_path).exists():
                pae_matrix = prediction_metrics.get("pae_matrix") or prediction_metrics.get("pae")
                if pae_matrix is not None:
                    # Create temporary JSON file
                    import numpy as np
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                        json_data = {
                            "pae": pae_matrix.tolist() if isinstance(pae_matrix, np.ndarray) else pae_matrix
                        }
                        json.dump(json_data, f)
                        json_path = f.name
                else:
                    logger.warning(
                        "IPSAE calculation requires JSON file or PAE matrix. "
                        "Neither found in prediction_metrics or PDB directory."
                    )
                    return {}
            
            # Calculate IPSAE using the script
            all_metrics = calculate_ipsae_from_script(
                json_path=json_path,
                pdb_path=pdb_path,
                pae_cutoff=self.pae_cutoff,
                dist_cutoff=self.distance_cutoff,
                ipsae_script_path=self.ipsae_script_path,
            )
            
            # Filter metrics based on include_duplicate_metrics setting
            metrics = {}
            # Always include core IPSAE metrics
            if "ipsae" in all_metrics:
                metrics["ipsae"] = all_metrics["ipsae"]
            if "ipsae_d0chn" in all_metrics:
                metrics["ipsae_d0chn"] = all_metrics["ipsae_d0chn"]
            if "ipsae_d0dom" in all_metrics:
                metrics["ipsae_d0dom"] = all_metrics["ipsae_d0dom"]
            
            # Conditionally include duplicate metrics
            if self.include_duplicate_metrics:
                for key in ["ipsae_iptm_af", "ipsae_pdockq", "ipsae_pdockq2", "ipsae_lis"]:
                    if key in all_metrics:
                        metrics[key] = all_metrics[key]
            
            # Clean up temporary file if created
            if json_path.startswith(tempfile.gettempdir()):
                try:
                    os.unlink(json_path)
                except:
                    pass
            
            return metrics
        
        except Exception as e:
            logger.error(f"Error in IPSAE calculation: {e}")
            return {}
    
    def get_metric_names(self) -> List[str]:
        """
        Return list of metric names produced by IPSAE calculator.
        
        Note: 
        - Core IPSAE metrics are always returned
        - Duplicate metrics (ipsae_iptm_af, ipsae_pdockq, etc.) are only returned
          if include_duplicate_metrics=True
        """
        core_metrics = [
            "ipsae",              # IPSAE 核心分数
            "ipsae_d0chn",        # IPSAE (d0 = chain lengths)
            "ipsae_d0dom",        # IPSAE (d0 = domain residues)
        ]
        
        if self.include_duplicate_metrics:
            core_metrics.extend([
                "ipsae_iptm_af",      # AlphaFold ipTM (可能与 external_iptm 相同)
                "ipsae_pdockq",       # pDockQ from IPSAE (可能与 pdockq 相同，但实现可能不同)
                "ipsae_pdockq2",      # pDockQ2 from IPSAE (可能与 pdockq2 相同，但实现可能不同)
                "ipsae_lis",          # LIS from IPSAE (可能与 lis 相同，但实现可能不同)
            ])
        
        return core_metrics


class IgLMCalculator:
    """Calculate IgLM log-likelihood for antibody sequences."""
    
    def calculate(self, pdb_path: str, design: Design) -> Dict[str, Any]:
        """
        Calculate IgLM log-likelihood.
        
        Adapt from germinal/filters/filter_utils.py:get_iglm_ll
        """
        try:
            from iglm import IgLM
            
            model = IgLM()
            
            # Calculate log-likelihood
            # This depends on antibody type (nanobody vs scFv)
            # Adapt based on design metadata
            
            ll = model.log_likelihood(
                design.sequence,
                "[HEAVY]",  # or "[LIGHT]" for nanobodies
                "[CAMEL]",  # or "[HUMAN]"
            )
            
            return {
                "iglm_ll": ll,
            }
        
        except ImportError:
            logger.warning("IgLM not available")
            return {}
    
    def get_metric_names(self) -> List[str]:
        return ["iglm_ll"]

