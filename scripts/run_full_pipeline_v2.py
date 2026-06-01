#!/usr/bin/env python3
# 兼容包装：主入口仅为 run_denovo_design.sh / run_optimization_pipeline.sh。
# 本脚本转发到 scripts/part1/part1_run_denovo_orchestrator.py
import runpy
from pathlib import Path

_PATH = Path(__file__).resolve().parent / "part1" / "part1_run_denovo_orchestrator.py"
runpy.run_path(str(_PATH), run_name="__main__")
