"""
MD Runner module for protein_filter_lib.

This module provides high-level MD simulation execution with automatic
crash detection and parameter fallback recovery.
"""

import os
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from protein_filter.md.crash_detector import (
    CrashType,
    detect_crash_type,
    get_crash_suggestion,
    generate_crash_report,
    apply_recovery_params,
    save_crash_report,
)

logger = logging.getLogger(__name__)


class MDRunner:
    """
    MD simulation runner with crash recovery.
    
    Supports AMBER and GROMACS simulations with automatic
    parameter adjustment on crash.
    """
    
    SUPPORTED_ENGINES = ["amber", "gromacs"]
    
    def __init__(
        self,
        engine: str = "amber",
        config: Optional[Dict] = None,
        max_attempts: int = 3,
        work_dir: str = ".",
    ):
        """
        Initialize MD Runner.
        
        Args:
            engine: MD engine ("amber" or "gromacs")
            config: MD configuration dict
            max_attempts: Maximum retry attempts
            work_dir: Working directory for simulations
        """
        if engine not in self.SUPPORTED_ENGINES:
            raise ValueError(f"Unsupported engine: {engine}")
        
        self.engine = engine
        self.config = config or {}
        self.max_attempts = max_attempts
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        self._attempt = 0
        self._crash_history: List[Dict] = []
    
    def run(
        self,
        structure_file: str,
        output_name: str = "md",
        extra_args: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Run MD simulation with crash recovery.
        
        Args:
            structure_file: Input structure file (PDB/prmtop)
            output_name: Base name for output files
            extra_args: Additional command line arguments
            
        Returns:
            Dict with execution results:
            {
                "success": bool,
                "output_files": List[str],
                "attempts": int,
                "crash_reports": List[Dict],
                "final_config": Dict
            }
        """
        self._attempt = 0
        self._crash_history = []
        
        current_config = self.config.copy()
        output_files = []
        
        while self._attempt < self.max_attempts:
            self._attempt += 1
            logger.info(f"MD attempt {self._attempt}/{self.max_attempts}")
            
            result = self._run_single(
                structure_file,
                output_name,
                current_config,
                extra_args,
            )
            
            if result["success"]:
                output_files = result.get("output_files", [])
                logger.info(f"MD completed successfully on attempt {self._attempt}")
                return {
                    "success": True,
                    "output_files": output_files,
                    "attempts": self._attempt,
                    "crash_reports": self._crash_history,
                    "final_config": current_config,
                }
            
            crash_info = result.get("crash_info")
            if crash_info:
                self._crash_history.append(crash_info)
                
                crash_type = CrashType(crash_info["crash_type"])
                suggestion = get_crash_suggestion(crash_type)
                
                if not suggestion["recovery_possible"]:
                    logger.error("Crash not recoverable, stopping")
                    break
                
                current_config = apply_recovery_params(current_config, suggestion)
                logger.info(f"Adjusted config: {current_config.get('md', {})}")
                
                self._save_crash_report(crash_info, output_name)
        
        return {
            "success": False,
            "output_files": output_files,
            "attempts": self._attempt,
            "crash_reports": self._crash_history,
            "final_config": current_config,
            "error": "Max attempts reached" if not output_files else None,
        }
    
    def _run_single(
        self,
        structure_file: str,
        output_name: str,
        config: Dict,
        extra_args: Optional[List[str]],
    ) -> Dict[str, Any]:
        """Run single MD attempt."""
        
        log_file = self.work_dir / f"{output_name}.log"
        
        if self.engine == "amber":
            return self._run_amber(structure_file, output_name, config, extra_args, log_file)
        else:
            return self._run_gromacs(structure_file, output_name, config, extra_args, log_file)
    
    def _run_amber(
        self,
        structure_file: str,
        output_name: str,
        config: Dict,
        extra_args: Optional[List[str]],
        log_file: Path,
    ) -> Dict[str, Any]:
        """Run AMBER MD simulation."""
        
        md_config = config.get("md", {})
        timestep = md_config.get("timestep_fs", 2.0)
        production_ns = md_config.get("production_ns", 100)
        
        cmd = [
            "sander",
            "-i", str(self._get_amber_input(timestep, production_ns)),
            "-p", structure_file,
            "-c", structure_file,
            "-o", str(log_file),
        ]
        
        if extra_args:
            cmd.extend(extra_args)
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.work_dir,
                capture_output=True,
                timeout=md_config.get("timeout", 86400),
            )
            
            if result.returncode != 0:
                return self._check_crash(log_file)
            
            return {
                "success": True,
                "output_files": [
                    str(self.work_dir / f"{output_name}.nc"),
                    str(self.work_dir / f"{output_name}.rst"),
                ],
            }
        except subprocess.TimeoutExpired:
            crash_info = self._create_crash_info(log_file, "timeout")
            return {"success": False, "crash_info": crash_info}
        except Exception as e:
            logger.error(f"MD execution failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _run_gromacs(
        self,
        structure_file: str,
        output_name: str,
        config: Dict,
        extra_args: Optional[List[str]],
        log_file: Path,
    ) -> Dict[str, Any]:
        """Run GROMACS MD simulation."""
        
        md_config = config.get("md", {})
        nsteps = md_config.get("nsteps", 500000)
        
        cmd = [
            "gmx_mpi", "mdrun",
            "-s", structure_file,
            "-o", str(self.work_dir / f"{output_name}.trr"),
            "-e", str(self.work_dir / f"{output_name}.edr"),
            "-g", str(log_file),
            "-nsteps", str(nsteps),
        ]
        
        if extra_args:
            cmd.extend(extra_args)
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.work_dir,
                capture_output=True,
                timeout=md_config.get("timeout", 86400),
            )
            
            if result.returncode != 0:
                return self._check_crash(log_file)
            
            return {
                "success": True,
                "output_files": [
                    str(self.work_dir / f"{output_name}.trr"),
                    str(self.work_dir / f"{output_name}.xtc"),
                ],
            }
        except subprocess.TimeoutExpired:
            crash_info = self._create_crash_info(log_file, "timeout")
            return {"success": False, "crash_info": crash_info}
        except Exception as e:
            logger.error(f"MD execution failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _check_crash(self, log_file: Path) -> Dict[str, Any]:
        """Check log file for crash indicators."""
        
        if not log_file.exists():
            return {"success": False, "error": "Log file not found"}
        
        crash_type, description = detect_crash_type(str(log_file))
        
        if crash_type == CrashType.SUCCESS:
            return {"success": True}
        
        crash_info = self._create_crash_info(log_file, crash_type.value, description)
        return {"success": False, "crash_info": crash_info}
    
    def _create_crash_info(
        self,
        log_file: Path,
        crash_type: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """Create crash info dict."""
        
        return {
            "attempt": self._attempt,
            "log_file": str(log_file),
            "crash_type": crash_type,
            "description": description,
        }
    
    def _save_crash_report(self, crash_info: Dict, output_name: str):
        """Save crash report to JSON."""
        
        report = generate_crash_report(str(self.work_dir), f"{output_name}.log")
        report_path = self.work_dir / f"{output_name}_crash_{self._attempt}.json"
        save_crash_report(report, str(report_path))
    
    def _get_amber_input(self, timestep: float, production_ns: int) -> Path:
        """Get or create AMBER input file."""
        
        input_file = self.work_dir / "md.in"
        
        dt = timestep / 1000.0
        nstlim = int(production_ns * 1000 / timestep)
        
        input_content = f"""
&cntrl
  imin = 0,
  nstlim = {nstlim},
  dt = {dt},
  ntx = 1,
  irest = 0,
  ntpr = 1000,
  ntwr = 10000,
  ntwx = 5000,
  cut = 10.0,
  ntb = 1,
  ntp = 0,
  tautp = 1.0,
  tempi = 300.0,
  temp0 = 300.0,
  tautp = 1.0,
/
"""
        
        input_file.write_text(input_content)
        return input_file


def run_md_with_recovery(
    structure_file: str,
    config: Dict,
    output_dir: str = ".",
    engine: str = "amber",
    max_attempts: int = 3,
) -> Dict[str, Any]:
    """
    Convenience function to run MD with crash recovery.
    
    Args:
        structure_file: Input structure file
        config: MD configuration
        output_dir: Output directory
        engine: MD engine
        max_attempts: Maximum retry attempts
        
    Returns:
        Execution result dict
    """
    runner = MDRunner(
        engine=engine,
        config=config,
        max_attempts=max_attempts,
        work_dir=output_dir,
    )
    
    return runner.run(structure_file)