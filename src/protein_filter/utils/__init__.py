"""
Utility functions for protein filter library.
"""

from .pdb_utils import (
    get_sequence_from_pdb,
    clean_pdb,
    calculate_clash_score,
    hotspot_residues,
)
from .pdockq_utils import (
    get_pdockq,
    compute_pdockq,
    pDockQ2,
    calculate_lis,
)
from .af3_utils import (
    extract_metrics_from_af3_json,
    extract_metrics_from_af3_output,
    auto_extract_af3_metrics,
    save_extracted_metrics,
    load_extracted_metrics,
)
from .ipsae_utils import (
    calculate_ipsae_from_script,
    calculate_ipsae_native,
    get_ipsae_script_path,
)

calculate_ipsae_from_data = calculate_ipsae_native


def __getattr__(name):
    if name in ("save_metrics_to_parquet", "load_metrics_from_parquet", 
                "save_metrics_to_json", "load_metrics_from_json", "merge_metrics_files"):
        try:
            from .metrics_io import (save_metrics_to_parquet, load_metrics_from_parquet,
                save_metrics_to_json, load_metrics_from_json, merge_metrics_files)
            globals()[name] = locals()[name]
            return locals()[name]
        except ImportError:
            raise AttributeError(f"requires pandas/pyarrow for {name}")
    raise AttributeError(f"module has no attribute {name}")

__all__ = [
    "get_sequence_from_pdb",
    "clean_pdb",
    "calculate_clash_score",
    "hotspot_residues",
    "get_pdockq",
    "compute_pdockq",
    "pDockQ2",
    "calculate_lis",
    "extract_metrics_from_af3_json",
    "extract_metrics_from_af3_output",
    "auto_extract_af3_metrics",
    "save_extracted_metrics",
    "load_extracted_metrics",
    "calculate_ipsae_from_script",
    "calculate_ipsae_from_data",
    "get_ipsae_script_path",
    "save_metrics_to_parquet",
    "load_metrics_from_parquet",
    "save_metrics_to_json",
    "load_metrics_from_json",
    "merge_metrics_files",
]
