"""
Utilities for extracting metrics from AlphaFold3 prediction results.

AlphaFold3 typically outputs:
- PDB or mmCIF file with pLDDT in B-factor field
- JSON file with metrics (PTM, iPTM, PAE matrix, etc.)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


def extract_metrics_from_af3_json(json_path: str) -> Dict[str, Any]:
    """
    Extract prediction metrics from AlphaFold3 JSON output file.
    
    AlphaFold3 typically outputs a JSON file containing:
    - plddt: per-residue pLDDT scores
    - ptm: predicted TM-score
    - iptm: interface predicted TM-score
    - pae: predicted aligned error matrix
    - confidence: overall confidence score
    
    Args:
        json_path: Path to AF3 JSON output file
        
    Returns:
        Dictionary of extracted metrics, including:
        - plddt: average pLDDT (0-1)
        - ptm: predicted TM-score (0-1)
        - iptm: interface predicted TM-score (0-1)
        - pae: average PAE (Å)
        - pae_matrix: PAE matrix (numpy array, if available)
    """
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        metrics = {}
        
        # Extract pLDDT
        if 'plddt' in data:
            plddt_array = np.array(data['plddt'])
            # pLDDT is typically 0-100, normalize to 0-1
            if plddt_array.max() > 1.0:
                plddt_array = plddt_array / 100.0
            metrics['plddt'] = float(np.mean(plddt_array))
        
        # Extract PTM (predicted TM-score)
        if 'ptm' in data:
            metrics['ptm'] = float(data['ptm'])
        
        # Extract iPTM (interface predicted TM-score)
        if 'iptm' in data:
            metrics['iptm'] = float(data['iptm'])
        elif 'i_ptm' in data:
            metrics['iptm'] = float(data['i_ptm'])
        
        # Extract PAE (predicted aligned error)
        if 'pae' in data:
            pae_matrix = np.array(data['pae'])
            metrics['pae'] = float(np.mean(pae_matrix))
            metrics['pae_matrix'] = pae_matrix
        elif 'predicted_aligned_error' in data:
            pae_matrix = np.array(data['predicted_aligned_error'])
            metrics['pae'] = float(np.mean(pae_matrix))
            metrics['pae_matrix'] = pae_matrix
        
        # Extract confidence score if available
        if 'confidence' in data:
            metrics['confidence'] = float(data['confidence'])
        
        # Extract max PAE if available
        if 'pae_matrix' in metrics:
            metrics['pae_max'] = float(np.max(metrics['pae_matrix']))
        
        return metrics
    
    except FileNotFoundError:
        logger.warning(f"AF3 JSON file not found: {json_path}")
        return {}
    except json.JSONDecodeError as e:
        logger.warning(f"Error parsing AF3 JSON file {json_path}: {e}")
        return {}
    except Exception as e:
        logger.warning(f"Error extracting metrics from {json_path}: {e}")
        return {}


def extract_metrics_from_af3_output(
    output_dir: str,
    pdb_filename: Optional[str] = None,
    json_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract all metrics from AlphaFold3 output directory.
    
    This function looks for:
    1. PDB or mmCIF file (for pLDDT from B-factor)
    2. JSON file (for PTM, iPTM, PAE matrix)
    
    Args:
        output_dir: Directory containing AF3 output files
        pdb_filename: Name of structure file (default: looks for *.pdb or *.cif)
        json_filename: Name of JSON file (default: looks for *.json or *_scores.json)
        
    Returns:
        Dictionary of all extracted metrics
    """
    output_path = Path(output_dir)
    if not output_path.exists():
        logger.warning(f"AF3 output directory not found: {output_dir}")
        return {}
    
    metrics = {}
    
    # Find structure file (PDB or CIF)
    if pdb_filename:
        struct_path = output_path / pdb_filename
    else:
        # Look for CIF files first (AF3 default), then PDB files
        cif_files = list(output_path.glob("*.cif"))
        if cif_files:
            struct_path = cif_files[0]
        else:
            pdb_files = list(output_path.glob("*.pdb"))
            if pdb_files:
                struct_path = pdb_files[0]
            else:
                struct_path = None
    
    # Extract pLDDT from structure file if available
    if struct_path and struct_path.exists():
        try:
            from .pdockq_utils import pdb_2_coords, _is_cif_file
            is_cif = _is_cif_file(str(struct_path))
            chain_coords, plddt_array = pdb_2_coords(str(struct_path), is_cif=is_cif)
            if len(plddt_array) > 0:
                plddt_normalized = plddt_array / 100.0
                metrics['plddt'] = float(np.mean(plddt_normalized))
        except Exception as e:
            logger.warning(f"Error extracting pLDDT from {struct_path}: {e}")
    
    # Find and parse JSON file
    if json_filename:
        json_path = output_path / json_filename
    else:
        # Look for JSON files (common names: *_scores.json, result.json, etc.)
        json_files = list(output_path.glob("*_scores.json"))
        if not json_files:
            json_files = list(output_path.glob("*.json"))
        if json_files:
            json_path = json_files[0]
        else:
            json_path = None
    
    # Extract metrics from JSON
    if json_path and json_path.exists():
        json_metrics = extract_metrics_from_af3_json(str(json_path))
        metrics.update(json_metrics)
    
    return metrics


def auto_extract_af3_metrics(pdb_path: str) -> Dict[str, Any]:
    """
    Automatically extract metrics from AF3 prediction results.
    
    This function tries to find AF3 output files in the same directory as the structure file.
    
    Args:
        pdb_path: Path to AF3 predicted PDB or mmCIF file
        
    Returns:
        Dictionary of extracted metrics
    """
    struct_file = Path(pdb_path)
    if not struct_file.exists():
        logger.warning(f"Structure file not found: {pdb_path}")
        return {}
    
    output_dir = struct_file.parent
    
    # Try to extract from output directory
    metrics = extract_metrics_from_af3_output(str(output_dir))
    
    # If no JSON found, at least extract pLDDT from structure file
    if 'plddt' not in metrics:
        try:
            from .pdockq_utils import pdb_2_coords, _is_cif_file
            is_cif = _is_cif_file(pdb_path)
            chain_coords, plddt_array = pdb_2_coords(pdb_path, is_cif=is_cif)
            if len(plddt_array) > 0:
                plddt_normalized = plddt_array / 100.0
                metrics['plddt'] = float(np.mean(plddt_normalized))
        except Exception as e:
            logger.warning(f"Error extracting pLDDT from {pdb_path}: {e}")
    
    return metrics


def save_extracted_metrics(
    metrics: Dict[str, Any],
    output_path: str,
    include_pae_matrix: bool = False,
) -> str:
    """
    Save extracted metrics to a JSON file.
    
    This is useful for caching extracted metrics to avoid re-extraction
    in subsequent runs, especially for batch processing.
    
    Args:
        metrics: Dictionary of extracted metrics
        output_path: Path to save JSON file
        include_pae_matrix: Whether to include PAE matrix in saved file
            (default: False, as PAE matrix can be large)
    
    Returns:
        Path to saved file
    
    Example:
        >>> metrics = auto_extract_af3_metrics("design_001.pdb")
        >>> save_extracted_metrics(metrics, "design_001_metrics.json")
        'design_001_metrics.json'
    """
    output_file = Path(output_path)
    
    # Prepare metrics for JSON serialization
    saved_metrics = {}
    for key, value in metrics.items():
        if key == "pae_matrix":
            if include_pae_matrix:
                # Convert numpy array to list for JSON serialization
                saved_metrics[key] = value.tolist() if isinstance(value, np.ndarray) else value
            else:
                # Skip PAE matrix by default (can be large)
                saved_metrics["pae_matrix_shape"] = list(value.shape) if isinstance(value, np.ndarray) else None
                saved_metrics["pae_matrix_dtype"] = str(value.dtype) if isinstance(value, np.ndarray) else None
        elif isinstance(value, np.ndarray):
            # Convert other numpy arrays to lists
            saved_metrics[key] = value.tolist()
        elif isinstance(value, (np.integer, np.floating)):
            # Convert numpy scalars to Python types
            saved_metrics[key] = float(value) if isinstance(value, np.floating) else int(value)
        else:
            saved_metrics[key] = value
    
    # Save to JSON
    with open(output_file, 'w') as f:
        json.dump(saved_metrics, f, indent=2)
    
    logger.info(f"Saved extracted metrics to: {output_file}")
    return str(output_file)


def load_extracted_metrics(metrics_path: str) -> Dict[str, Any]:
    """
    Load previously saved extracted metrics from JSON file.
    
    This is useful for loading cached metrics to avoid re-extraction.
    
    Args:
        metrics_path: Path to saved metrics JSON file
    
    Returns:
        Dictionary of loaded metrics
    
    Example:
        >>> metrics = load_extracted_metrics("design_001_metrics.json")
        >>> design = Design(..., prediction_metrics=metrics)
    """
    metrics_file = Path(metrics_path)
    if not metrics_file.exists():
        logger.warning(f"Metrics file not found: {metrics_path}")
        return {}
    
    try:
        with open(metrics_file, 'r') as f:
            metrics = json.load(f)
        
        # Convert lists back to numpy arrays if needed
        if "pae_matrix" in metrics and isinstance(metrics["pae_matrix"], list):
            metrics["pae_matrix"] = np.array(metrics["pae_matrix"])
        
        logger.info(f"Loaded extracted metrics from: {metrics_path}")
        return metrics
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing metrics file {metrics_path}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error loading metrics from {metrics_path}: {e}")
        return {}
