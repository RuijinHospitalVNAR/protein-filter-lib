"""MD crash detection and recovery module.

This module provides functionality to:
- Detect different types of MD simulation crashes
- Parse MD log files from various simulation engines (AMBER, GROMACS)
- Provide recovery suggestions based on crash type
- Generate crash diagnostic reports
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class CrashType(Enum):
    """Types of MD simulation crashes."""
    ENERGY_EXPLOSION = "energy_explosion"
    LINCS_FAILURE = "lincs_failure"
    SEGFAULT = "segfault"
    NAN = "nan"
    TIMEOUT = "timeout"
    DISK_SPACE = "disk_space"
    UNKNOWN = "unknown"
    SUCCESS = "success"


class MDCrashError(Exception):
    """Base exception for MD crash errors."""
    pass


CRASH_PATTERNS = {
    CrashType.ENERGY_EXPLOSION: [
        r"energy\s+explosion",
        r"energy\s+is\s+nan",
        r"non-finite\s+energy",
        r"energy\s+>\s*\d+\.\d+",
        r"bonded\s+atom\s+energy\s+exploded",
    ],
    CrashType.LINCS_FAILURE: [
        r"lincs\s+warning",
        r"lincs\s+failure",
        r"constraint\s+violation",
        r"rigid\s+bond\s+warning",
        r"too\ many\ iterations",
    ],
    CrashType.SEGFAULT: [
        r"segmentation\s+fault",
        r"segfault",
        r"core\s+dumped",
        r"signal\s+11",
        r"bus\s+error",
    ],
    CrashType.NAN: [
        r"nan",
        r"not\s+a\s+number",
        r"inf",
        r"infinity",
        r"floating\s+point\s+error",
    ],
    CrashType.TIMEOUT: [
        r"timeout",
        r"time\s+limit",
        r"exceeded",
        r"walltime",
    ],
    CrashType.DISK_SPACE: [
        r"no\s+space\s+left",
        r"disk\s+full",
        r"quota\s+exceeded",
        r"cannot\s+write",
    ],
}


def parse_md_log(log_path: str) -> Dict:
    """
    Parse MD simulation log file and extract key information.

    Args:
        log_path: Path to MD log file

    Returns:
        Dict containing:
        {
            "exists": bool,
            "size": int,
            "final_energy": Optional[float],
            "final_step": int,
            "warnings": List[str],
            "errors": List[str],
            "completed": bool
        }
    """
    result = {
        "exists": False,
        "size": 0,
        "final_energy": None,
        "final_step": 0,
        "warnings": [],
        "errors": [],
        "completed": False,
    }

    if not os.path.exists(log_path):
        logger.warning(f"Log file not found: {log_path}")
        return result

    result["exists"] = True
    result["size"] = os.path.getsize(log_path)

    energy_pattern = re.compile(r"ENERGY\s*=\s*([-\d.]+)", re.IGNORECASE)
    step_pattern = re.compile(r"Step\s+(\d+)", re.IGNORECASE)

    with open(log_path, 'r') as f:
        content = f.read()
        lines = content.split('\n')

        for line in lines:
            line_lower = line.lower()

            for crash_type, patterns in CRASH_PATTERNS.items():
                if crash_type == CrashType.SUCCESS:
                    continue
                for pattern in patterns:
                    if re.search(pattern, line_lower):
                        if crash_type not in [CrashType.SUCCESS]:
                            if line not in result["errors"]:
                                result["errors"].append(line.strip()[:100])

            energy_match = energy_pattern.search(line)
            if energy_match:
                try:
                    result["final_energy"] = float(energy_match.group(1))
                except ValueError:
                    pass

            step_match = step_pattern.search(line)
            if step_match:
                try:
                    step = int(step_match.group(1))
                    if step > result["final_step"]:
                        result["final_step"] = step
                except ValueError:
                    pass

            if "warning" in line_lower:
                if line.strip() not in result["warnings"]:
                    result["warnings"].append(line.strip()[:100])

    final_keywords = ["normal termination", "finished", "complete", "success"]
    for keyword in final_keywords:
        if keyword in content.lower():
            result["completed"] = True
            break

    return result


def detect_crash_type(log_path: str) -> Tuple[CrashType, str]:
    """
    Detect the type of MD crash from log file.

    Args:
        log_path: Path to MD log file

    Returns:
        Tuple of (CrashType, description)
    """
    if not os.path.exists(log_path):
        return CrashType.UNKNOWN, "Log file not found"

    log_info = parse_md_log(log_path)

    if log_info["completed"]:
        return CrashType.SUCCESS, "Simulation completed successfully"

    for line in log_info["errors"]:
        line_lower = line.lower()

        for crash_type, patterns in CRASH_PATTERNS.items():
            if crash_type == CrashType.SUCCESS:
                continue
            for pattern in patterns:
                if re.search(pattern, line_lower):
                    return crash_type, f"Detected from log: {line[:80]}"

    if log_info["final_energy"] is not None:
        if abs(log_info["final_energy"]) > 1e10 or str(log_info["final_energy"]) == "nan":
            return CrashType.ENERGY_EXPLOSION, f"Extreme energy value: {log_info['final_energy']}"

    if log_info["final_step"] > 0 and log_info["size"] < 10000:
        return CrashType.TIMEOUT, f"Stopped early at step {log_info['final_step']}"

    if log_info["errors"]:
        return CrashType.UNKNOWN, f"Errors found but type unknown: {log_info['errors'][0][:60]}"

    return CrashType.UNKNOWN, "No crash indicators found in log"


def get_crash_suggestion(crash_type: CrashType) -> Dict:
    """
    Get recovery suggestion for a crash type.

    Args:
        crash_type: Type of crash

    Returns:
        Dict with recovery suggestions:
        {
            "recovery_possible": bool,
            "suggestions": List[str],
            "params_to_adjust": Dict
        }
    """
    suggestions_map = {
        CrashType.ENERGY_EXPLOSION: {
            "recovery_possible": True,
            "suggestions": [
                "Reduce timestep (2fs -> 1fs or 0.5fs)",
                "Use constrains on bonds (constraints = h-bonds)",
                "Check system minimization was sufficient",
                "Check periodic box size is adequate",
                "Consider adding restraint on backbone",
            ],
            "params_to_adjust": {
                "timestep": 1,
                "constraints": "h-bonds",
                "restraint_wt": 5.0,
            }
        },
        CrashType.LINCS_FAILURE: {
            "recovery_possible": True,
            "suggestions": [
                "Reduce timestep (2fs -> 1fs)",
                "Switch to LINCS for constraints",
                "Increase LINCS iterations (lincs_iter = 4)",
                "Check for bad contacts or overlaps",
                "Run short minimization with strong restraints",
            ],
            "params_to_adjust": {
                "timestep": 1,
                "lincs_iter": 4,
                "constraints": "all-bonds",
            }
        },
        CrashType.SEGFAULT: {
            "recovery_possible": False,
            "suggestions": [
                "Check for corrupted input files",
                "Verify AMBER/GROMACS installation",
                "Check memory availability",
                "Try with smaller system or fewer processors",
                "May require manual intervention",
            ],
            "params_to_adjust": {}
        },
        CrashType.NAN: {
            "recovery_possible": True,
            "suggestions": [
                "Check system is neutralized (correct ions)",
                "Verify coordinates are reasonable",
                "Run longer minimization",
                "Check for conflicts in input structure",
                "Use gradual heating protocol",
            ],
            "params_to_adjust": {
                "minimize_steps": 5000,
                "heating_steps": 10000,
            }
        },
        CrashType.TIMEOUT: {
            "recovery_possible": True,
            "suggestions": [
                "Reduce production time (100ns -> 50ns)",
                "Use checkpointing for longer runs",
                "Split into multiple shorter runs",
                "Increase walltime limit if possible",
            ],
            "params_to_adjust": {
                "production_ns": 50,
                "use_checkpoint": True,
            }
        },
        CrashType.DISK_SPACE: {
            "recovery_possible": True,
            "suggestions": [
                "Clean up old trajectory files",
                "Reduce trajectory write frequency",
                "Use less verbose output",
                "Check disk quota",
            ],
            "params_to_adjust": {
                "ntpr": 1000,
                "ntwx": 5000,
            }
        },
        CrashType.UNKNOWN: {
            "recovery_possible": False,
            "suggestions": [
                "Review log file for details",
                "Check system preparation steps",
                "Try with test system first",
                "Contact support if issue persists",
            ],
            "params_to_adjust": {}
        },
        CrashType.SUCCESS: {
            "recovery_possible": True,
            "suggestions": ["No recovery needed - simulation completed"],
            "params_to_adjust": {}
        },
    }

    return suggestions_map.get(crash_type, suggestions_map[CrashType.UNKNOWN])


def generate_crash_report(structure_dir: str, log_file: str = "md.log") -> Dict:
    """
    Generate a crash diagnostic report for an MD simulation.

    Args:
        structure_dir: Path to structure directory
        log_file: Name of log file to check

    Returns:
        Dict with crash report:
        {
            "structure_dir": str,
            "log_file": str,
            "crash_type": str,
            "description": str,
            "recovery_possible": bool,
            "suggestions": List[str],
            "params_to_adjust": Dict
        }
    """
    log_path = os.path.join(structure_dir, log_file)

    crash_type, description = detect_crash_type(log_path)
    suggestion = get_crash_suggestion(crash_type)

    return {
        "structure_dir": structure_dir,
        "log_file": log_file,
        "crash_type": crash_type.value,
        "description": description,
        "recovery_possible": suggestion["recovery_possible"],
        "suggestions": suggestion["suggestions"],
        "params_to_adjust": suggestion["params_to_adjust"],
    }


def save_crash_report(report: Dict, output_path: str) -> None:
    """
    Save crash report to JSON file.

    Args:
        report: Crash report dict
        output_path: Path to output JSON file
    """
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    logger.info(f"Crash report saved to {output_path}")


def apply_recovery_params(original_config: Dict, recovery_params: Dict) -> Dict:
    """
    Apply recovery parameters to MD config.

    Args:
        original_config: Original MD configuration dict
        recovery_params: Recovery parameters from get_crash_suggestion

    Returns:
        Updated configuration dict
    """
    adjusted = original_config.copy()

    if "params_to_adjust" in recovery_params:
        params = recovery_params["params_to_adjust"]

        if "timestep" in params:
            adjusted["md"]["timestep_fs"] = params["timestep"]

        if "constraints" in params:
            adjusted["md"]["constraints"] = params["constraints"]

        if "production_ns" in params:
            adjusted["md"]["production_ns"] = params["production_ns"]

        if "restraint_wt" in params:
            if "restraints" not in adjusted["md"]:
                adjusted["md"]["restraints"] = {}
            adjusted["md"]["restraints"]["weight"] = params["restraint_wt"]

    return adjusted