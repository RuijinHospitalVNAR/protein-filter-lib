"""
Basic usage example for protein_filter_lib.

This library analyzes predicted structures and filters them based on quality metrics.
Structure prediction should be done externally (e.g., using AlphaFold3, Chai-1, etc.).
"""

from protein_filter import ProteinFilter, FilterConfig, Design
import numpy as np

# Create configuration
config = FilterConfig(
    structure_relaxer=FilterConfig.StructureRelaxerConfig(
        name="pyrosetta",  # Use "none" to skip relaxation
    ),
    metrics=FilterConfig.MetricConfig(
        enabled=[
            "plddt", "iptm", "pae", "clashes",
            "interface_dG", "interface_dSASA", "interface_packstat",
            "sap_score",
        ],
    ),
    filters={
        "external_plddt": {"threshold": 0.7, "operator": ">="},
        "external_iptm": {"threshold": 0.6, "operator": ">="},
        "clashes": {"threshold": 1, "operator": "<"},
        "interface_dG": {"threshold": -10.0, "operator": "<"},
    },
    output_dir="./filter_results",
)

# Create filter system
filter_system = ProteinFilter(config)

# Create design with predicted structure and metrics
# Note: pdb_path should point to the predicted structure from external prediction
design = Design(
    sequence="MKLLVLGCTAGCTTTCCGGA...",  # Your binder sequence
    pdb_path="predicted_design.pdb",  # Path to predicted PDB from external prediction
    target_chain="A",
    binder_chain="B",
    target_sequence=["MKLLVL..."],  # Optional target sequence
    design_name="design_001",
    # Optional: Provide prediction metrics from external prediction
    prediction_metrics={
        "plddt": 0.85,  # Average pLDDT score
        "ptm": 0.75,   # Predicted TM-score
        "iptm": 0.70,  # Interface predicted TM-score
        "pae": 5.2,    # Average PAE
        # Optional: PAE matrix for pDockQ2 and LIS calculations
        # "pae_matrix": np.array(...),  # Shape: (n_residues, n_residues)
    },
)

# Filter design
result = filter_system.filter(design)

# Check results
if result.passed:
    print(f"✅ Design passed all filters!")
    print(f"   pLDDT: {result.metrics.get('external_plddt', 'N/A')}")
    print(f"   iPTM: {result.metrics.get('external_iptm', 'N/A')}")
    print(f"   Clashes: {result.metrics.get('clashes', 'N/A')}")
    print(f"   Interface dG: {result.metrics.get('interface_dG', 'N/A')}")
else:
    print(f"❌ Design failed filters:")
    for filter_name, passed in result.filter_results.items():
        status = "✅" if passed else "❌"
        print(f"   {status} {filter_name}")

