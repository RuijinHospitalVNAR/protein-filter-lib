# Protein Filter Library 全面优化计划

> **For Hermes:** 使用 `subagent-driven-development` skill 按任务逐步实施。推荐模型：**Kimi For Coding**。

**目标:** 将 `protein_filter_lib` 从当前原型状态优化为生产级、高性能、可维护的生物信息学筛选库，重点解决 I/O 重复解析、缺乏测试、脚本/库边界混乱三大瓶颈。

**架构思路:**
- 引入 **统一结构缓存层 (StructureCache)**，消除 BioPython 重复解析
- 引入 **指标缓存 (MetricsCache)**，以 Parquet/JSON 持久化避免重复计算
- 建立 **批量并行执行器 (BatchExecutor)**，统一 Part1/Part2 的多进程调度
- 提取脚本中的业务逻辑下沉到 `src/`，脚本仅保留 CLI 入口职责

**技术栈:** Python 3.10+, pytest, pandas, pyarrow, multiprocessing, joblib, BioPython, cKDTree

---

## 项目现状评估

| 维度 | 现状 | 风险/机会 |
|------|------|-----------|
| 代码规模 | `src/` 约 7,432 行 Python | 中等规模，可控 |
| 测试覆盖 | **无 `tests/` 目录** | 重构风险极高，必须优先补测试 |
| I/O 模式 | 每个 calculator/script 独立 `open()` / `PDBParser.get_structure()` | **最大性能瓶颈**，同一 PDB 被解析 3-10 次 |
| 并行化 | `multiprocessing` 散见于 `stages.py`、`part2_run_pyrosetta_static_relax_interface.py` | 缺乏统一抽象，难以调优 |
| 脚本架构 | 大量 `sys.path.insert(0, ...)` 和 `sed` 修改脚本配置 | 维护噩梦，需下沉为库调用 |
| 性能监控 | `part1_analyze_af3_three_stage.py` 有 psutil 监控 | 未成体系，需统一为可插拔 profiler |

**模型建议：** 使用 **Kimi For Coding**。本项目优化以工程重构、I/O 改造、并行化、测试驱动为主，非纯算法推导；Kimi For Coding 对 Python 代码结构、性能陷阱、工程最佳实践最敏感，且 7.4k 行代码完全在其长上下文覆盖范围内。

---

## Phase 1: 地基工程（测试 + 性能基线）

> 原则：没有测试和 benchmark 的优化是盲飞。先建立安全网和度量尺。

---

### Task 1.1: 创建 `tests/` 目录并配置 pytest

**目标:** 建立测试基础设施

**文件:**
- 创建: `tests/__init__.py`
- 创建: `tests/conftest.py`
- 修改: `pyproject.toml`（确认 pytest 配置已存在）

**Step 1:** 创建测试目录和 conftest

```bash
mkdir -p tests/unit tests/integration tests/benchmarks
```

在 `tests/conftest.py` 写入共享 fixture：

```python
import pytest
from pathlib import Path

@pytest.fixture
def sample_data_dir() -> Path:
    return Path(__file__).parent.parent / "examples" / "affinity_maturation_example"

@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path
```

**Step 2:** 运行 pytest 确认空测试通过

Run: `pytest tests -v`
Expected: `collected 0 items / 1 error`（如果没有错误则应为 0 items 通过）

**Step 3:** Commit

```bash
git add tests/ pyproject.toml
git commit -m "test: initialize test infrastructure with pytest fixtures"
```

---

### Task 1.2: 为 `utils/pdb_utils.py` 编写单元测试

**目标:** 为最常用的 I/O 工具函数建立回归测试

**文件:**
- 创建: `tests/unit/test_pdb_utils.py`

**Step 1:** 找到 example PDB 文件

Run: `find /data/wcf/protein_filter_lib/examples -name '*.pdb' | head -5`
Expected: 至少返回一个路径（如 `.../affinity_maturation_example/.../model.pdb`）

**Step 2:** 编写测试

```python
import pytest
from pathlib import Path
from protein_filter.utils.pdb_utils import get_sequence_from_pdb, calculate_clash_score, _is_cif_file

def test_is_cif_file():
    assert _is_cif_file("model.cif") is True
    assert _is_cif_file("model.pdb") is False

def test_calculate_clash_score_on_example(example_pdb: Path):
    # 使用 example 目录下的真实 PDB
    score = calculate_clash_score(str(example_pdb))
    assert isinstance(score, int)
    assert score >= 0
```

如果 example 目录 PDB 不足，可以在 `tests/data/` 下放一个最小 PDB（如 2 条链 10 个残基）。

**Step 3:** 运行测试

Run: `pytest tests/unit/test_pdb_utils.py -v`
Expected: 全部 PASS

**Step 4:** Commit

```bash
git add tests/
git commit -m "test: add unit tests for pdb_utils"
```

---

### Task 1.3: 建立性能基准 (Benchmark)

**目标:** 为 Part1 指标计算建立可重复的性能基准脚本

**文件:**
- 创建: `tests/benchmarks/bench_stage1_metrics.py`

**Step 1:** 编写 benchmark 脚本

```python
"""Benchmark Stage1 metric calculation on a small sample."""
import time
import sys
from pathlib import Path

# Use library properly (ensure installed in env)
from protein_filter.utils.af3_utils import auto_extract_af3_metrics
from protein_filter.utils.pdb_utils import calculate_clash_score
from protein_filter.utils.pdockq_utils import get_pdockq

def bench_single(pdb_path: str, iterations: int = 10):
    t0 = time.perf_counter()
    for _ in range(iterations):
        calculate_clash_score(pdb_path)
    t1 = time.perf_counter()
    print(f"clash_score: {(t1-t0)/iterations:.4f}s/it")

if __name__ == "__main__":
    pdb = sys.argv[1]
    bench_single(pdb, iterations=int(sys.argv[2]) if len(sys.argv) > 2 else 10)
```

**Step 2:** 运行基准

Run: `python tests/benchmarks/bench_stage1_metrics.py $(find examples -name '*.pdb' | head -1) 5`
Expected: 输出各指标平均耗时

**Step 3:** 将结果保存到 `tests/benchmarks/baseline_results.json`

```bash
git add tests/benchmarks/
git commit -m "test: add stage1 performance benchmark"
```

---

## Phase 2: I/O 与缓存优化（最大收益区）

> 原则：消除重复 PDB 解析和 AF3 JSON 扫描，预期收益 **30-60%** 整体加速。

---

### Task 2.1: 实现统一结构缓存 `StructureCache`

**目标:** 缓存 BioPython Structure 对象，避免同一文件被重复解析

**文件:**
- 创建: `src/protein_filter/utils/structure_cache.py`
- 修改: `src/protein_filter/utils/pdb_utils.py`
- 修改: `src/protein_filter/utils/pdockq_utils.py`

**Step 1:** 创建缓存模块

```python
"""Unified BioPython structure cache with LRU eviction."""
from functools import lru_cache
from Bio.PDB import PDBParser, MMCIFParser
from Bio.PDB.Structure import Structure
from pathlib import Path

def _get_structure(path: str) -> Structure:
    p = Path(path)
    if p.suffix.lower() in ('.cif', '.mmcif'):
        parser = MMCIFParser(QUIET=True)
    else:
        parser = PDBParser(QUIET=True)
    return parser.get_structure(p.stem, path)

@lru_cache(maxsize=128)
def get_cached_structure(path: str) -> Structure:
    """Load and cache a BioPython Structure object."""
    return _get_structure(path)

def invalidate_structure_cache(path: str | None = None):
    if path is None:
        get_cached_structure.cache_clear()
    else:
        # lru_cache doesn't support single-key eviction easily;
        # for now we document that cache is per-process and short-lived.
        get_cached_structure.cache_clear()
```

**Step 2:** 修改 `pdb_utils.py` 中的 `get_sequence_from_pdb`、`calculate_clash_score`、`hotspot_residues`

将每处 `parser.get_structure(...)` 替换为：

```python
from .structure_cache import get_cached_structure
structure = get_cached_structure(pdb_path)
```

**Step 3:** 修改 `pdockq_utils.py`

检查 `pdb_2_coords` 和 `get_pdockq` 中是否也重复解析，如有则同样替换。

**Step 4:** 运行 pdb_utils 测试确保行为不变

Run: `pytest tests/unit/test_pdb_utils.py -v`
Expected: PASS

**Step 5:** 重新跑 benchmark，记录加速比

Run: `python tests/benchmarks/bench_stage1_metrics.py ...`
Expected:  clash_score 耗时应有明显下降（尤其连续调用同一 PDB 时）

**Step 6:** Commit

```bash
git add src/protein_filter/utils/structure_cache.py src/protein_filter/utils/pdb_utils.py ...
git commit -m "perf: add unified BioPython StructureCache to eliminate repeated PDB parsing"
```

---

### Task 2.2: 实现指标缓存 `MetricsCache`

**目标:** 将指标计算结果按 PDB 路径哈希持久化到 Parquet/JSON，支持秒级重跑

**文件:**
- 创建: `src/protein_filter/utils/metrics_cache.py`
- 修改: `src/protein_filter/metrics/aggregator.py`

**Step 1:** 设计缓存模块

```python
"""Persistent metric cache keyed by file hash + config fingerprint."""
import hashlib
import json
from pathlib import Path
from typing import Dict, Any
import pandas as pd

def _file_fingerprint(path: str) -> str:
    """Fast fingerprint using mtime + size (avoids full-file hash for large PDBs)."""
    p = Path(path)
    stat = p.stat()
    return hashlib.md5(f"{stat.st_mtime}:{stat.st_size}".encode()).hexdigest()[:16]

def _config_fingerprint(config_dict: Dict[str, Any]) -> str:
    return hashlib.md5(json.dumps(config_dict, sort_keys=True).encode()).hexdigest()[:16]

class MetricsCache:
    def __init__(self, cache_dir: str = ".protein_filter_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, file_path: str, config: Dict[str, Any]) -> Path:
        fp = _file_fingerprint(file_path)
        cfg = _config_fingerprint(config)
        return self.cache_dir / f"{fp}_{cfg}.json"

    def get(self, file_path: str, config: Dict[str, Any]) -> Dict[str, Any] | None:
        cp = self._cache_path(file_path, config)
        if cp.exists():
            return json.loads(cp.read_text())
        return None

    def put(self, file_path: str, config: Dict[str, Any], metrics: Dict[str, Any]) -> None:
        cp = self._cache_path(file_path, config)
        cp.write_text(json.dumps(metrics, indent=2, default=str))
```

**Step 2:** 在 `MetricAggregator.calculate_all` 首尾加入缓存读写

```python
def calculate_all(...):
    from ..utils.metrics_cache import MetricsCache
    cache = MetricsCache()
    cache_key = {"enabled": self.config.enabled, "relaxer": str(self.config)}
    cached = cache.get(structure_pdb, cache_key)
    if cached is not None:
        logger.info("Metrics cache hit for %s", structure_pdb)
        return cached
    # ... existing calculation ...
    cache.put(structure_pdb, cache_key, all_metrics)
    return all_metrics
```

**Step 3:** 编写缓存单元测试

创建 `tests/unit/test_metrics_cache.py`：

```python
from protein_filter.utils.metrics_cache import MetricsCache, _file_fingerprint

def test_cache_roundtrip(temp_dir):
    cache = MetricsCache(str(temp_dir / "cache"))
    cache.put("/fake/path.pdb", {"enabled": ["clashes"]}, {"clashes": 3})
    assert cache.get("/fake/path.pdb", {"enabled": ["clashes"]}) == {"clashes": 3}
```

**Step 4:** 运行测试

Run: `pytest tests/unit/test_metrics_cache.py -v`
Expected: PASS

**Step 5:** Commit

```bash
git add src/protein_filter/utils/metrics_cache.py tests/unit/test_metrics_cache.py src/protein_filter/metrics/aggregator.py
git commit -m "perf: add persistent MetricsCache for sub-second filter re-runs"
```

---

### Task 2.3: 优化 `af3_utils.py` 的 JSON/文件发现逻辑

**目标:** 减少 `glob()` 和重复 JSON 解析

**文件:**
- 修改: `src/protein_filter/utils/af3_utils.py`

**Step 1:** 审计现有代码

`extract_metrics_from_af3_output` 中：
- 每次调用都执行 `list(output_path.glob("*.cif"))`、`list(output_path.glob("*.pdb"))`
- 如果批量处理 10,000 个设计，glob 会被调用数万次

**Step 2:** 重构为显式文件名模式

修改 `extract_metrics_from_af3_output` 的签名，增加 `expect_filenames: Dict[str, str] | None = None` 参数，允许调用方直接传入文件名，跳过 glob：

```python
def extract_metrics_from_af3_output(
    output_dir: str,
    struct_filename: str | None = None,
    json_filename: str | None = None,
) -> Dict[str, Any]:
    ...
    if struct_filename:
        struct_path = output_path / struct_filename
    else:
        # fallback to single glob with early exit
        ...
```

**Step 3:** 在调用方（如 `stages.py`、CLI）中传入已知文件名

**Step 4:** 运行任何现有的 af3_utils 调用测试（如果没有，至少手动运行 `python -c "from protein_filter.utils.af3_utils import auto_extract_af3_metrics; ..."`）

**Step 5:** Commit

```bash
git add src/protein_filter/utils/af3_utils.py
git commit -m "perf: allow explicit filenames in af3_utils to avoid repeated glob scans"
```

---

## Phase 3: 计算层优化（向量化 + 并行化）

> 原则：把 Python 循环换成 NumPy/SciPy，把串行 for 循环换成批量并行。

---

### Task 3.1: 向量化 `chain_detection.calculate_interface_area`

**目标:** 将当前 O(N*M) Python 循环替换为 cKDTree 批量查询

**文件:**
- 修改: `src/protein_filter/utils/chain_detection.py`
- 创建: `tests/unit/test_chain_detection.py`

**Step 1:** 重构函数

当前代码（约 line 135）使用 `for c1 in coords1: distances = np.linalg.norm(...)`，应改为：

```python
from scipy.spatial import cKDTree

def calculate_interface_area(pdb_path: str, chain1: str, chain2: str, cutoff: float = 8.0) -> float:
    from ..utils.structure_cache import get_cached_structure
    structure = get_cached_structure(pdb_path)
    # ... extract CA coords for chain1 and chain2 ...
    if not coords1 or not coords2:
        return 0.0
    tree = cKDTree(coords2)
    neighbors = tree.query_ball_tree(cKDTree(coords1), cutoff)
    contact_count = sum(len(nbr) for nbr in neighbors)
    return float(contact_count)
```

**Step 2:** 编写测试确保数值等价

```python
from protein_filter.utils.chain_detection import calculate_interface_area

def test_interface_area_on_example(example_pdb):
    area = calculate_interface_area(str(example_pdb), "A", "B")
    assert area >= 0
```

**Step 3:** 运行测试

Run: `pytest tests/unit/test_chain_detection.py -v`
Expected: PASS

**Step 4:** Commit

```bash
git add src/protein_filter/utils/chain_detection.py tests/unit/test_chain_detection.py
git commit -m "perf: vectorize calculate_interface_area with cKDTree"
```

---

### Task 3.2: 并行化 Stage1 批量指标计算

**目标:** 将 `part1_analyze_af3_three_stage.py` 中的 `_extract_metrics_worker` 升级为统一批量并行执行器

**文件:**
- 创建: `src/protein_filter/pipeline/batch_executor.py`
- 修改: `src/protein_filter/pipeline/stages.py`
- 修改: `scripts/part1/part1_analyze_af3_three_stage.py`

**Step 1:** 设计 `BatchExecutor`

```python
"""Uniform batch executor for CPU-bound metric calculation."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable, Iterable, Any
import os

def execute_batch(
    worker: Callable[[Any], Any],
    items: Iterable[Any],
    max_workers: int | None = None,
    chunksize: int = 1,
):
    if max_workers is None:
        max_workers = os.cpu_count() or 1
    with ProcessPoolExecutor(max_workers=max_workers) as exe:
        futures = {exe.submit(worker, item): item for item in items}
        for future in as_completed(futures):
            yield futures[future], future.result()
```

**Step 2:** 在 `stages.py` 的 `AF3ScoreFilteringStage.process` 中使用 `execute_batch` 替换现有的 `multiprocessing.Pool` 调用（如有），或统一包装当前逻辑

**Step 3:** 在 `part1_analyze_af3_three_stage.py` 中，将 `_extract_metrics_worker` 的调用改为使用 `BatchExecutor`

**Step 4:** 验证并行后输出与串行一致

可通过将 `max_workers=1` 和 `max_workers=4` 跑同一批 example 数据，对比输出 parquet/csv 的 md5：

Run:
```bash
python scripts/part1/part1_analyze_af3_three_stage.py --input examples/... --output /tmp/test_serial --workers 1
python scripts/part1/part1_analyze_af3_three_stage.py --input examples/... --output /tmp/test_para --workers 4
diff /tmp/test_serial/stage1_metrics.parquet /tmp/test_para/stage1_metrics.parquet
```
Expected: 无差异

**Step 5:** Commit

```bash
git add src/protein_filter/pipeline/batch_executor.py src/protein_filter/pipeline/stages.py scripts/part1/part1_analyze_af3_three_stage.py
git commit -m "perf: parallelize stage1 metric extraction with BatchExecutor"
```

---

### Task 3.3: 优化 `calculators.py` 中的串行 hotspot 计算

**目标:** `InterfaceCalculator.calculate()` 中调用 `hotspot_residues()` 获取界面残基，而 `hotspot_residues()` 每次都会重新解析 PDB 并构建 KDTree。通过 StructureCache 消除重复解析。

**文件:**
- 修改: `src/protein_filter/utils/pdb_utils.py`（`hotspot_residues`）
- 修改: `src/protein_filter/metrics/calculators.py`

**Step 1:** 修改 `hotspot_residues` 使用 `get_cached_structure`

```python
from ..utils.structure_cache import get_cached_structure
structure = get_cached_structure(trajectory_pdb)
```

**Step 2:** 运行相关测试

Run: `pytest tests/unit/test_pdb_utils.py -v`
Expected: PASS

**Step 3:** Commit

```bash
git add src/protein_filter/utils/pdb_utils.py src/protein_filter/metrics/calculators.py
git commit -m "perf: cache structure parsing in hotspot_residues for faster interface calc"
```

---

## Phase 4: 架构与脚本治理

> 原则：脚本只应负责 CLI 参数解析和调用库；业务逻辑全部下沉到 `src/`。

---

### Task 4.1: 创建 `load_config_env.py` 的统一配置加载器

**目标:** 消除 `run_full_pipeline.sh` 中 `sed` 修改子脚本配置的 hack

**文件:**
- 修改: `scripts/utils/load_config_env.py`
- 修改: `scripts/run_full_pipeline.sh`

**Step 1:** 审计现有 `load_config_env.py`

Run: `cat scripts/utils/load_config_env.py`

**Step 2:** 实现基于 YAML/JSON 的统一配置加载

将 `run_full_pipeline.sh` 顶部的 bash 变量导出为 YAML（如 `config/pipeline.yaml`），然后所有子脚本通过 `load_config_env.py` 读取并导出环境变量或直接返回 dict。

示例：

```python
# scripts/utils/load_config_env.py
import yaml, os, sys
from pathlib import Path

def load_config(path: str) -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f)
    for k, v in cfg.items():
        os.environ.setdefault(k, str(v))
    return cfg

if __name__ == "__main__":
    load_config(sys.argv[1])
```

**Step 3:** 修改 `run_full_pipeline.sh`，移除 `sync_config_to_script` 函数，改为：

```bash
python scripts/utils/load_config_env.py config/full_pipeline.yaml
```

**Step 4:** 运行脚本 dry-run（如果不破坏现有行为）

Run: `bash -n scripts/run_full_pipeline.sh`
Expected: 语法检查通过

**Step 5:** Commit

```bash
git add scripts/utils/load_config_env.py scripts/run_full_pipeline.sh
git commit -m "refactor: replace sed-based config sync with unified YAML config loader"
```

---

### Task 4.2: 下沉 Part1 三段式分析逻辑到 `src/protein_filter/pipeline/`

**目标:** 将 `scripts/part1/part1_analyze_af3_three_stage.py` 中 1600+ 行的业务逻辑提取为库代码

**文件:**
- 创建: `src/protein_filter/pipeline/part1_three_stage.py`
- 修改: `scripts/part1/part1_analyze_af3_three_stage.py`

**Step 1:** 识别三段式流程中的三个核心类/函数：
- `stage1_score_filtering()`
- `stage2_foldseek_clustering()`
- `stage3_contact_clustering()`

**Step 2:** 将每个 stage 提取为库函数（保留性能监控作为可选参数）

```python
def run_stage1_score_filtering(input_dir, output_dir, thresholds, n_workers=None): ...
def run_stage2_foldseek_clustering(input_dir, output_dir, n_workers=None): ...
def run_stage3_contact_clustering(cluster_dirs, output_dir, thresholds): ...
```

**Step 3:** 修改原脚本为薄包装层

原脚本只负责：
1. 解析 argparse
2. 调用上述函数
3. 写日志

**Step 4:** 运行脚本确保输出不变

用 example 数据跑前后对比（md5sum）

**Step 5:** Commit

```bash
git add src/protein_filter/pipeline/part1_three_stage.py scripts/part1/part1_analyze_af3_three_stage.py
git commit -m "refactor: extract Part1 three-stage logic from script into pipeline library"
```

---

### Task 4.3: 建立统一的 CLI 入口 `pf-run-pipeline`

**目标:** 用 Python Click/Typer 或 stdlib argparse 建立统一 CLI，逐步替代分散的 shell 脚本

**文件:**
- 创建: `src/protein_filter/cli/run_pipeline.py`
- 修改: `pyproject.toml`（添加 entry point）

**Step 1:** 实现最小可用 CLI

```python
import argparse
from protein_filter.pipeline.part1_three_stage import run_full_part1_pipeline

def main():
    parser = argparse.ArgumentParser("pf-run-pipeline")
    parser.add_argument("--config", required=True)
    parser.add_argument("--mode", choices=["denovo", "optimizing"], default="denovo")
    args = parser.parse_args()
    run_full_part1_pipeline(args.config, mode=args.mode)
```

**Step 2:** 添加到 `pyproject.toml`

```toml
[project.scripts]
pf-run-pipeline = "protein_filter.cli.run_pipeline:main"
```

**Step 3:** 本地安装并测试

Run:
```bash
pip install -e .
pf-run-pipeline --help
```
Expected: 显示 help 信息

**Step 4:** Commit

```bash
git add src/protein_filter/cli/run_pipeline.py pyproject.toml
git commit -m "feat: add unified pf-run-pipeline CLI entry point"
```

---

## Phase 5: 验证与收尾

---

### Task 5.1: 运行全量单元测试

**目标:** 确保所有优化未破坏现有行为

Run: `pytest tests/ -v --tb=short`
Expected: 全部 PASS

Commit: `git commit --allow-empty -m "ci: all unit tests passing after optimization phase"`

---

### Task 5.2: 运行回归 benchmark 并撰写优化报告

**目标:** 量化优化收益

**文件:**
- 创建: `docs/OPTIMIZATION_REPORT.md`

Run:
```bash
python tests/benchmarks/bench_stage1_metrics.py <example_pdb> 20 > tests/benchmarks/optimized_results.json
```

报告中至少包含：
- `clash_score` 优化前后对比
- `interface_area` 优化前后对比
- Stage1 整体批量处理吞吐量（structures/min）对比

Commit: `git add docs/OPTIMIZATION_REPORT.md tests/benchmarks/ && git commit -m "docs: add optimization report with benchmark results"`

---

## 实施建议

1. **严格按 Phase 执行**，不要跳步。Phase 1 的测试是后续重构的安全网。
2. **每个 Task 独立为一个 subagent**，通过 `delegate_task` 派发，确保上下文干净。
3. **TDD 原则**：任何修改 `src/` 的 Task，优先写/改测试，再改实现。
4. **频繁 commit**：每个 Task 一个 commit，便于 bisect 和问题回滚。
5. **遇到 Part3 (AMBER/MD) 相关代码**，本计划暂不涉及；Part3 的性能瓶颈主要在 GPU 分子动力学本身，Python 层优化空间有限。

---

## 快速参考：文件改动地图

| 模块 | 改动文件 | 优化点 |
|------|----------|--------|
| 缓存 | `utils/structure_cache.py` (新) | 消除重复 PDB 解析 |
| 缓存 | `utils/metrics_cache.py` (新) | 秒级重跑过滤 |
| I/O | `utils/af3_utils.py` | 避免 glob 扫描 |
| I/O | `utils/pdb_utils.py` | StructureCache 接入 |
| 计算 | `utils/chain_detection.py` | cKDTree 向量化 |
| 计算 | `metrics/calculators.py` | 减少 hotspot 重算 |
| 并行 | `pipeline/batch_executor.py` (新) | 统一多进程执行器 |
| 并行 | `pipeline/stages.py` | 批量并行 Stage1 |
| 架构 | `pipeline/part1_three_stage.py` (新) | 脚本逻辑下沉 |
| CLI | `cli/run_pipeline.py` (新) | 统一入口 |
| 测试 | `tests/unit/` (新) | 回归测试 |
| 基准 | `tests/benchmarks/` (新) | 性能度量 |
