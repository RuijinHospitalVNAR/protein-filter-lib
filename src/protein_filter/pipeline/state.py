"""
统一状态管理：流水线阶段、Part2 批处理进度、断点续跑。

- PipelineRunState: 记录当前运行到哪一 Part/Stage，用于编排器 resume。
- Part2Checkpoint: Part2 (run_pyrosetta_static) 已完成的 pdb 路径集合，支持增量续跑。
- Part3 单结构状态由 run_part3_md_single.sh 通过文件存在性判断，本模块仅可选记录「某结构已提交/已完成」供编排器查询。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline-level state (for orchestrator resume)
# ---------------------------------------------------------------------------

@dataclass
class PipelineRunState:
    """
    流水线运行状态：当前 Part、Stage，以及各 Part 的完成情况。
    持久化到 output_dir / pipeline_state.json。
    """
    current_part: str = "part1"   # part1 | part2 | part3
    current_stage: str = ""      # 如 stage1_af3_filtering, part2_pyrosetta, part3_md
    completed_parts: List[str] = field(default_factory=list)  # ["part1", "part2"]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_part": self.current_part,
            "current_stage": self.current_stage,
            "completed_parts": list(self.completed_parts),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineRunState":
        return cls(
            current_part=data.get("current_part", "part1"),
            current_stage=data.get("current_stage", ""),
            completed_parts=list(data.get("completed_parts", [])),
            metadata=dict(data.get("metadata", {})),
        )

    def save(self, output_dir: Path) -> Path:
        path = output_dir / "pipeline_state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.debug("Saved pipeline state: %s", path)
        return path

    @classmethod
    def load(cls, output_dir: Path) -> Optional["PipelineRunState"]:
        path = output_dir / "pipeline_state.json"
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return cls.from_dict(json.load(f))
        except Exception as e:
            logger.warning("Failed to load pipeline state from %s: %s", path, e)
            return None


# ---------------------------------------------------------------------------
# Part2 checkpoint (run_pyrosetta_static resume)
# ---------------------------------------------------------------------------

@dataclass
class Part2Checkpoint:
    """
    Part2 批处理断点：已完成的 pdb 路径集合 + 已写入 CSV 的行数/路径。
    持久化到 output_dir / part2_checkpoint.json。
    """
    completed_pdb_paths: Set[str] = field(default_factory=set)
    output_csv: str = ""
    last_updated: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "completed_pdb_paths": list(self.completed_pdb_paths),
            "output_csv": self.output_csv,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Part2Checkpoint":
        return cls(
            completed_pdb_paths=set(data.get("completed_pdb_paths", [])),
            output_csv=data.get("output_csv", ""),
            last_updated=data.get("last_updated", ""),
        )

    def save(self, output_dir: Path) -> Path:
        from datetime import datetime
        self.last_updated = datetime.now().isoformat()
        path = output_dir / "part2_checkpoint.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return path

    @classmethod
    def load(cls, output_dir: Path) -> Optional["Part2Checkpoint"]:
        path = output_dir / "part2_checkpoint.json"
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return cls.from_dict(json.load(f))
        except Exception as e:
            logger.warning("Failed to load Part2 checkpoint from %s: %s", path, e)
            return None

    def is_done(self, pdb_path: str) -> bool:
        try:
            canonical = str(Path(pdb_path).resolve())
            return any(
                Path(p).resolve() == Path(canonical).resolve()
                for p in self.completed_pdb_paths
            )
        except Exception:
            return pdb_path in self.completed_pdb_paths

    def mark_done(self, pdb_path: str) -> None:
        self.completed_pdb_paths.add(str(Path(pdb_path).resolve()))


# ---------------------------------------------------------------------------
# Part3 structure status (optional: for orchestrator to track which structures are done)
# ---------------------------------------------------------------------------

@dataclass
class Part3StructureState:
    """
    单结构 Part3 状态（可选）。实际是否完成由 run_part3_md_single.sh 输出目录内
    Production.gro / MM/PBSA 等文件决定；此处仅用于编排器记录「已提交/已完成」列表。
    """
    structure_id: str = ""   # 如 pdb 相对路径或 model 名
    output_dir: str = ""
    status: str = "pending"  # pending | running | done | failed
    last_updated: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "structure_id": self.structure_id,
            "output_dir": self.output_dir,
            "status": self.status,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Part3StructureState":
        return cls(
            structure_id=data.get("structure_id", ""),
            output_dir=data.get("output_dir", ""),
            status=data.get("status", "pending"),
            last_updated=data.get("last_updated", ""),
        )


def load_pipeline_state(output_dir: Path) -> Optional[PipelineRunState]:
    """便捷：从 output_dir 加载 PipelineRunState。"""
    return PipelineRunState.load(output_dir)


def save_pipeline_state(state: PipelineRunState, output_dir: Path) -> Path:
    """便捷：将 PipelineRunState 写入 output_dir。"""
    return state.save(output_dir)
