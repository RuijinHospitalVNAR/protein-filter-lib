# protein_filter_lib 增强版优化计划（可执行细划）

> **For Hermes:** 使用 `subagent-driven-development` skill 逐任务实施。推荐模型：**Kimi For Coding**。
> 本计划融合了原「PROJECT_OPTIMIZATION_PLAN.md」中的 MD 稳定性与使用便捷性目标，并补充了关键的**性能优化**、**架构治理**和**测试先行**维度。

**目标:** 将库从原型状态升级为生产级、高性能、稳定可靠的生物信息学筛选库，具备开源质量。

**架构思路:**
- **测试先行**：任何功能增强/重构前先建立安全网
- **缓存优化**：统一结构缓存消除重复 PDB 解析，持久化指标缓存支持秒级重跑
- **稳定性增强**：MD 崩溃自动恢复、MMPBSA 链检测增强、配置驱动化
- **架构治理**：将脚本中的业务逻辑下沉到 `src/`，统一 CLI 入口

**技术栈:** Python 3.10+, pytest, pandas, pyarrow, BioPython, cKDTree, joblib, YAML

---

## 项目现状快照

| 维度 | 现状 | 影响 |
|------|------|--------|
| 测试 | 无 `tests/` 目录 | 优化/重构风险极高 |
| I/O | 每个 calculator 独立 `PDBParser.get_structure()` | 同一文件解析 3-10 次 |
| 并行 | `multiprocessing` 散见于各脚本 | 缺乏统一抽象 |
| MD 稳定性 | 体系崩溃无自动回退 | 生产环境隔夜跑常见失败 |
| MMPBSA | `chain_detection.py` 已有基础，但 Part3 集成不完善 | 链归属报错导致 MM/GBSA 计算中断 |
| 脚本架构 | `sed` 修改子脚本、`sys.path.insert` 横行 | 维护困难 |

---

## Phase 0: 地基工程（测试 + 基准）

> 原则：没有测试的优化是盲飞。所有后续任务依赖此阶段建立的安全网。

---

### Task 0.1: 创建 `tests/` 目录结构并配置 pytest

**目标:** 建立测试基础设施和共享 fixtures

**文件:**
- 创建: `tests/__init__.py`
- 创建: `tests/conftest.py`
- 修改: `pyproject.toml` (如需补充依赖)

**Step 1:** 创建目录

```bash
mkdir -p tests/unit/{utils,metrics,pipeline,md} tests/integration tests/benchmarks tests/data
```

**Step 2:** 写入 `tests/conftest.py`

```python
import pytest
from pathlib import Path

@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).parent.parent.resolve()

@pytest.fixture(scope="session")
def example_dir(project_root: Path) -> Path:
    p = project_root / "examples" / "affinity_maturation_example"
    if not p.exists():
        pytest.skip("affinity_maturation_example not found")
    return p

@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path
```

**Step 3:** 确认 pytest 运行正常

Run: `pytest tests -v`
Expected: `collected 0 items / no tests` 或类似，无错误退出

**Step 4:** Commit

```bash
git add tests/ pyproject.toml
git commit -m "test: initialize test infrastructure with pytest"
```

---

### Task 0.2: 为 `utils/chain_detection.py` 编写单元测试

**目标:** 为最关键的 MMPBSA 前置模块建立回归测试

**文件:**
- 创建: `tests/unit/utils/test_chain_detection.py`
- 创建: `tests/data/minimal_complex.pdb` (最小复合物)

**Step 1:** 创建最小复合物 PDB（只需要几十个原子）

```python
# tests/data/minimal_complex.pdb
REMARK  minimal test complex: chain A (4 res) + chain B (3 res)
ATOM    1  N   ALA A   1      0.000   0.000   0.000  1.00 90.00           N
ATOM    2  CA  ALA A   1      1.458   0.000   0.000  1.00 90.00           C
ATOM    3  C   ALA A   1      2.009   1.420   0.000  1.00 90.00           C
ATOM    4  O   ALA A   1      1.314   2.430   0.000  1.00 90.00           O
ATOM    5  N   ALA A   2      3.316   1.528   0.000  1.00 90.00           N
ATOM    6  CA  ALA A   2      3.991   2.786   0.000  1.00 90.00           C
ATOM    7  C   ALA A   2      5.488   2.641   0.000  1.00 90.00           C
ATOM    8  O   ALA A   2      6.113   1.600   0.000  1.00 90.00           O
ATOM    9  N   ALA A   3      6.081   3.748   0.000  1.00 90.00           N
ATOM   10  CA  ALA A   3      7.542   3.791   0.000  1.00 90.00           C
ATOM   11  C   ALA A   3      8.120   5.168   0.000  1.00 90.00           C
ATOM   12  O   ALA A   3      7.488   6.194   0.000  1.00 90.00           O
ATOM   13  N   ALA A   4      9.384   5.209   0.000  1.00 90.00           N
ATOM   14  CA  ALA A   4     10.020   6.510   0.000  1.00 90.00           C
ATOM   15  C   ALA A   4     11.519   6.450   0.000  1.00 90.00           C
ATOM   16  O   ALA A   4     12.121   5.385   0.000  1.00 90.00           O
ATOM   17  N   ALA B   1     15.000   0.000   0.000  1.00 85.00           N
ATOM   18  CA  ALA B   1     16.458   0.000   0.000  1.00 85.00           C
ATOM   19  C   ALA B   1     17.009   1.420   0.000  1.00 85.00           C
ATOM   20  O   ALA B   1     16.314   2.430   0.000  1.00 85.00           O
ATOM   21  N   ALA B   2     18.316   1.528   0.000  1.00 85.00           N
ATOM   22  CA  ALA B   2     18.991   2.786   0.000  1.00 85.00           C
ATOM   23  C   ALA B   2     20.488   2.641   0.000  1.00 85.00           C
ATOM   24  O   ALA B   2     21.113   1.600   0.000  1.00 85.00           O
ATOM   25  N   ALA B   3     21.081   3.748   0.000  1.00 85.00           N
ATOM   26  CA  ALA B   3     22.542   3.791   0.000  1.00 85.00           C
ATOM   27  C   ALA B   3     23.120   5.168   0.000  1.00 85.00           C
ATOM   28  O   ALA B   3     22.488   6.194   0.000  1.00 85.00           O
END
```

**Step 2:** 编写测试

```python
from pathlib import Path
from protein_filter.utils.chain_detection import (
    parse_chains_from_pdb,
    auto_detect_chains,
    calculate_interface_area,
)

def test_parse_chains_from_pdb():
    pdb = Path(__file__).parent.parent.parent / "data" / "minimal_complex.pdb"
    chains = parse_chains_from_pdb(str(pdb))
    assert set(chains.keys()) == {"A", "B"}
    assert chains["A"]["length"] == 4
    assert chains["B"]["length"] == 3

def test_auto_detect_chains_by_length():
    pdb = Path(__file__).parent.parent.parent / "data" / "minimal_complex.pdb"
    target, binder = auto_detect_chains(str(pdb), strategy="by_length")
    assert target == "A"
    assert binder == "B"

def test_calculate_interface_area():
    pdb = Path(__file__).parent.parent.parent / "data" / "minimal_complex.pdb"
    area = calculate_interface_area(str(pdb), "A", "B", cutoff=8.0)
    assert isinstance(area, float)
    assert area >= 0
```

**Step 3:** 运行测试

Run: `pytest tests/unit/utils/test_chain_detection.py -v`
Expected: 3 passed

**Step 4:** Commit

```bash
git add tests/
git commit -m "test: add unit tests for chain_detection with minimal fixture PDB"
```

---

### Task 0.3: 为 `utils/pdb_utils.py` 编写回归测试

**目标:** 保障最常用的 I/O 工具函数

**文件:**
- 创建: `tests/unit/utils/test_pdb_utils.py`

**Step 1:** 编写测试

```python
from pathlib import Path
from protein_filter.utils.pdb_utils import (
    get_sequence_from_pdb,
    calculate_clash_score,
    _is_cif_file,
    clean_pdb,
)

def test_is_cif_file():
    assert _is_cif_file("model.cif") is True
    assert _is_cif_file("model.pdb") is False

def test_get_sequence_from_pdb():
    pdb = Path(__file__).parent.parent.parent / "data" / "minimal_complex.pdb"
    seqs = get_sequence_from_pdb(str(pdb))
    assert seqs["A"] == "AAAA"
    assert seqs["B"] == "AAA"

def test_calculate_clash_score():
    pdb = Path(__file__).parent.parent.parent / "data" / "minimal_complex.pdb"
    score = calculate_clash_score(str(pdb))
    assert isinstance(score, int)
    assert score >= 0
```

**Step 2:** 运行

Run: `pytest tests/unit/utils/test_pdb_utils.py -v`
Expected: 3-4 passed

**Step 3:** Commit

```bash
git add tests/
git commit -m "test: add unit tests for pdb_utils"
```

---

### Task 0.4: 建立性能基准脚本

**目标:** 为 Stage1 指标计算建立可重复的性能基准

**文件:**
- 创建: `tests/benchmarks/bench_stage1_metrics.py`

**Step 1:** 编写 benchmark

```python
"""Benchmark Stage1 metric calculation on a small sample."""
import time
import sys
from pathlib import Path

from protein_filter.utils.pdb_utils import calculate_clash_score
from protein_filter.utils.pdockq_utils import get_pdockq
from protein_filter.utils.af3_utils import auto_extract_af3_metrics

def bench_single(pdb_path: str, iterations: int = 10):
    print(f"Benchmarking on {pdb_path} ({iterations} iterations)")
    
    t0 = time.perf_counter()
    for _ in range(iterations):
        calculate_clash_score(pdb_path)
    t1 = time.perf_counter()
    print(f"  calculate_clash_score: {(t1-t0)/iterations:.4f}s/it")
    
    t0 = time.perf_counter()
    for _ in range(iterations):
        get_pdockq(pdb_path)
    t1 = time.perf_counter()
    print(f"  get_pdockq: {(t1-t0)/iterations:.4f}s/it")

if __name__ == "__main__":
    pdb = sys.argv[1]
    iters = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    bench_single(pdb, iters)
```

**Step 2:** 运行并保存基准

Run:
```bash
python tests/benchmarks/bench_stage1_metrics.py tests/data/minimal_complex.pdb 20
```

将输出保存为 `tests/benchmarks/baseline_results.json`。

**Step 3:** Commit

```bash
git add tests/benchmarks/
git commit -m "test: add stage1 performance benchmark baseline"
```

---

## Phase 1: I/O 与性能优化（最大 ROI）

> 原则：消除重复 PDB 解析和 AF3 JSON 扫描，预期整体加速 **30-60%**。

---

### Task 1.1: 实现统一结构缓存 `StructureCache`

**目标:** 缓存 BioPython Structure 对象，避免同一文件被重复解析

**文件:**
- 创建: `src/protein_filter/utils/structure_cache.py`
- 修改: `src/protein_filter/utils/pdb_utils.py`

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
    """Clear cache. If path is None, clears all."""
    # lru_cache does not support single-key eviction easily
    get_cached_structure.cache_clear()
```

**Step 2:** 修改 `pdb_utils.py` 使用缓存

在 `get_sequence_from_pdb`、`calculate_clash_score`、`hotspot_residues`、`clean_pdb` 中，将 `parser.get_structure(...)` 替换为：

```python
from .structure_cache import get_cached_structure
structure = get_cached_structure(pdb_path)
```

注意 `clean_pdb` 原逻辑是直接读取文本，未用 BioPython，可不改。

**Step 3:** 运行测试确保无回退

Run: `pytest tests/unit/utils/test_pdb_utils.py tests/unit/utils/test_chain_detection.py -v`
Expected: 全部 PASS

**Step 4:** 重新跑 benchmark，记录加速

Run: `python tests/benchmarks/bench_stage1_metrics.py tests/data/minimal_complex.pdb 20`
Expected: 有明显下降（连续调用同一 PDB 时）

**Step 5:** Commit

```bash
git add src/protein_filter/utils/structure_cache.py src/protein_filter/utils/pdb_utils.py tests/benchmarks/
git commit -m "perf: add StructureCache to eliminate repeated PDB parsing"
```

---

### Task 1.2: 向量化 `chain_detection.calculate_interface_area`

**目标:** 将当前 O(N×M) Python 循环替换为 cKDTree 批量查询

**文件:**
- 修改: `src/protein_filter/utils/chain_detection.py`
- 修改: `tests/unit/utils/test_chain_detection.py`

**Step 1:** 重构函数

将现有循环（约 line 134-138）替换为：

```python
from scipy.spatial import cKDTree

def calculate_interface_area(pdb_path: str, chain1: str, chain2: str, cutoff: float = 8.0) -> float:
    from ..utils.structure_cache import get_cached_structure
    structure = get_cached_structure(pdb_path)
    
    coords1 = []
    coords2 = []
    for res in structure[0][chain1].get_residues():
        if res.resname.strip() in SOLVENT_RESIDUES or res.resname.strip() in ION_RESIDUES:
            continue
        for atom in res.get_atoms():
            if atom.name == "CA":
                coords1.append(atom.coord)
    
    for res in structure[0][chain2].get_residues():
        if res.resname.strip() in SOLVENT_RESIDUES or res.resname.strip() in ION_RESIDUES:
            continue
        for atom in res.get_atoms():
            if atom.name == "CA":
                coords2.append(atom.coord)
    
    if not coords1 or not coords2:
        return 0.0
    
    tree = cKDTree(coords2)
    neighbors = tree.query_ball_tree(cKDTree(coords1), cutoff)
    return float(sum(len(nbr) for nbr in neighbors))
```

**Step 2:** 运行测试

Run: `pytest tests/unit/utils/test_chain_detection.py -v`
Expected: PASS

**Step 3:** Commit

```bash
git add src/protein_filter/utils/chain_detection.py
git commit -m "perf: vectorize calculate_interface_area with cKDTree"
```

---

### Task 1.3: 实现指标缓存 `MetricsCache`

**目标:** 按 PDB 路径哈希持久化计算结果，支持秒级过滤重跑

**文件:**
- 创建: `src/protein_filter/utils/metrics_cache.py`
- 修改: `src/protein_filter/metrics/aggregator.py`
- 创建: `tests/unit/utils/test_metrics_cache.py`

**Step 1:** 创建缓存模块

```python
"""Persistent metric cache keyed by file hash + config fingerprint."""
import hashlib
import json
from pathlib import Path
from typing import Dict, Any

def _file_fingerprint(path: str) -> str:
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

**Step 2:** 在 `MetricAggregator.calculate_all` 中插入缓存读写

在方法开头添加：

```python
from ..utils.metrics_cache import MetricsCache

cache = MetricsCache()
cache_key = {"enabled": sorted(self.config.enabled)}
cached = cache.get(structure_pdb, cache_key)
if cached is not None:
    logger.info("Metrics cache hit for %s", structure_pdb)
    return cached
```

在 `return all_metrics` 之前添加：

```python
cache.put(structure_pdb, cache_key, all_metrics)
```

**Step 3:** 编写缓存测试

```python
from protein_filter.utils.metrics_cache import MetricsCache

def test_cache_roundtrip(temp_dir):
    cache = MetricsCache(str(temp_dir / "cache"))
    cache.put("/fake/path.pdb", {"enabled": ["clashes"]}, {"clashes": 3})
    assert cache.get("/fake/path.pdb", {"enabled": ["clashes"]}) == {"clashes": 3}
```

Run: `pytest tests/unit/utils/test_metrics_cache.py -v`
Expected: PASS

**Step 4:** Commit

```bash
git add src/protein_filter/utils/metrics_cache.py tests/unit/utils/test_metrics_cache.py src/protein_filter/metrics/aggregator.py
git commit -m "perf: add persistent MetricsCache for sub-second filter re-runs"
```

---

## Phase 2: MD 稳定性与 MMPBSA 增强

> 原则：解决生产环境中最痛的两个问题：MD 崩溃没有自动恢复，MMPBSA 链归属错误中断。

---

### Task 2.1: 定义统一异常体层次

**目标:** 为 MD 和 MMPBSA 错误建立可识别的异常类

**文件:**
- 创建: `src/protein_filter/exceptions.py`

**Step 1:** 创建异常体模块

```python
"""Unified exception hierarchy for protein_filter_lib."""

class ProteinFilterError(Exception):
    """Base exception for all library errors."""
    pass

class MDCrashError(ProteinFilterError):
    """Raised when MD simulation crashes and cannot be recovered."""
    def __init__(self, message: str, structure_path: str = "", attempt: int = 0, params: dict | None = None):
        super().__init__(message)
        self.structure_path = structure_path
        self.attempt = attempt
        self.params = params or {}

class MMPBSAChainError(ProteinFilterError):
    """Raised when MMPBSA chain assignment fails."""
    def __init__(self, message: str, pdb_path: str = "", detected_chains: list | None = None):
        super().__init__(message)
        self.pdb_path = pdb_path
        self.detected_chains = detected_chains or []

class ConfigurationError(ProteinFilterError):
    """Raised when configuration validation fails."""
    pass
```

**Step 2:** Commit

```bash
git add src/protein_filter/exceptions.py
git commit -m "feat: add unified exception hierarchy for MD and MMPBSA errors"
```

---

### Task 2.2: 增强 MMPBSA 链检测与诊断

**目标:** 完善 `chain_detection.py` 在 Part3 MMPBSA 中的集成，添加显式 mask 覆盖和诊断输出

**文件:**
- 修改: `src/protein_filter/utils/chain_detection.py`
- 修改: `tests/unit/utils/test_chain_detection.py`
- 修改: `config/part3.yaml`
- 修改: `AMBER_MMPBSA/run_mmpbsa_single.sh`

**Step 1:** 在 `chain_detection.py` 中添加 `validate_chain_consistency`

```python
def validate_chain_consistency(
    pdb_path: str,
    prmtop_path: str,
    target_chain: str,
    binder_chain: str,
) -> dict:
    """
    Validate that PDB chain assignment matches prmtop residue counts.
    Returns diagnostics dict.
    """
    from Bio.PDB import PDBParser
    structure = PDBParser(QUIET=True).get_structure("s", pdb_path)
    
    pdb_residue_counts = {}
    for chain in structure.get_chains():
        count = sum(1 for res in chain.get_residues() if res.resname.strip() not in SOLVENT_RESIDUES)
        pdb_residue_counts[chain.id] = count
    
    # Basic check: both target and binder chains exist in PDB
    missing = []
    if target_chain not in pdb_residue_counts:
        missing.append(target_chain)
    if binder_chain not in pdb_residue_counts:
        missing.append(binder_chain)
    
    if missing:
        raise MMPBSAChainError(
            f"Chains {missing} not found in PDB",
            pdb_path=pdb_path,
            detected_chains=list(pdb_residue_counts.keys()),
        )
    
    return {
        "target_chain": target_chain,
        "target_residues": pdb_residue_counts.get(target_chain, 0),
        "binder_chain": binder_chain,
        "binder_residues": pdb_residue_counts.get(binder_chain, 0),
        "pdb_total_residues": sum(pdb_residue_counts.values()),
    }
```

**Step 2:** 更新 `config/part3.yaml` 增加 `mmpbsa` 配置节点

在文件末尾添加：

```yaml
mmpbsa:
  auto_detect: true
  strategy: "by_length"
  target_sequence: ""
  binder_sequence: ""
  # 显式 mask 覆盖（优先级最高）
  receptor_mask: ""
  ligand_mask: ""
  # 诊断输出
  verbose: true
```

**Step 3:** 修改 `AMBER_MMPBSA/run_mmpbsa_single.sh`

在脚本中插入调用 `validate_chain_consistency` 的逻辑（通过 Python one-liner 或导入库）。假设 `run_mmpbsa_single.sh` 已有链检测逻辑，此处增加：
- 如果配置中有 `receptor_mask` 和 `ligand_mask`，优先使用
- 如果 `auto_detect=true`、且无显式 mask，调用 `auto_detect_chains`
- 检测完成后输出诊断信息到 `mmpbsa_diagnostics.json`

**Step 4:** 编写测试

在 `test_chain_detection.py` 中添加：

```python
from protein_filter.utils.chain_detection import validate_chain_consistency

def test_validate_chain_consistency():
    pdb = Path(__file__).parent.parent.parent / "data" / "minimal_complex.pdb"
    diag = validate_chain_consistency(str(pdb), "/fake/prmtop", "A", "B")
    assert diag["target_residues"] == 4
    assert diag["binder_residues"] == 3
```

Run: `pytest tests/unit/utils/test_chain_detection.py -v`
Expected: PASS

**Step 5:** Commit

```bash
git add src/protein_filter/utils/chain_detection.py tests/unit/utils/test_chain_detection.py config/part3.yaml AMBER_MMPBSA/run_mmpbsa_single.sh
git commit -m "feat: enhance MMPBSA chain detection with explicit masks and diagnostics"
```

---

### Task 2.3: 实现 MD 崩溃自动恢复机制

**目标:** 建立 MD 运行的渐进式参数回退和错误诊断

**文件:**
- 创建: `src/protein_filter/md/runner.py`
- 修改: `scripts/part3/part3_run_amber_md_mmgbsa_rmsd.py`
- 修改: `config/part3.yaml`
- 创建: `tests/unit/md/test_md_runner.py`

**Step 1:** 创建 `src/protein_filter/md/__init__.py` 和 `runner.py`

```python
"""MD runner with crash recovery and fallback parameters."""
import json
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List
from ..exceptions import MDCrashError

logger = logging.getLogger(__name__)

DEFAULT_MD_PARAMS = {
    "timestep_fs": 2,
    "constraints": "h-bonds",
    "npt_pressure_coupling": "parrinello-rahman",
}

FALLBACK_SEQUENCE: List[Dict[str, Any]] = [
    {"timestep_fs": 1, "constraints": "h-bonds"},
    {"timestep_fs": 0.5, "constraints": "all-bonds"},
    {"timestep_fs": 0.5, "constraints": "all-bonds", "npt_pressure_coupling": "berendsen"},
]

def build_md_cmd(
    md_script: Path,
    structure_path: str,
    output_dir: str,
    target_chain: str,
    binder_chain: str,
    params: Dict[str, Any],
    **kwargs
) -> List[str]:
    """Build shell command for MD run."""
    cmd = [
        "bash", str(md_script),
        "--structure", structure_path,
        "--output_dir", output_dir,
        "--target_chain", target_chain,
        "--binder_chain", binder_chain,
        "--production_ns", str(kwargs.get("production_ns", 100)),
        "--npt_ns", str(kwargs.get("npt_ns", 1)),
        "--tmp", str(kwargs.get("tmp", 298.15)),
        "--gpu_id", str(kwargs.get("gpu_id", 0)),
    ]
    return cmd

def run_md_with_recovery(
    md_script: Path,
    structure_path: str,
    output_dir: str,
    target_chain: str,
    binder_chain: str,
    max_attempts: int = 3,
    fallback_params: List[Dict[str, Any]] | None = None,
    **kwargs
) -> Dict[str, Any]:
    """Run MD with progressive fallback on crash."""
    params = DEFAULT_MD_PARAMS.copy()
    fallback_params = fallback_params or FALLBACK_SEQUENCE[:max(0, max_attempts - 1)]
    
    diagnostics = {
        "structure_path": structure_path,
        "attempts": [],
        "final_status": "unknown",
    }
    
    for attempt in range(max_attempts):
        if attempt > 0 and attempt - 1 < len(fallback_params):
            params.update(fallback_params[attempt - 1])
        
        logger.info("MD attempt %d/%d with params: %s", attempt + 1, max_attempts, params)
        
        cmd = build_md_cmd(md_script, structure_path, output_dir, target_chain, binder_chain, params, **kwargs)
        
        attempt_diag = {
            "attempt": attempt + 1,
            "params": params.copy(),
            "success": False,
        }
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=output_dir)
            attempt_diag["success"] = True
            attempt_diag["stdout"] = result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout
            diagnostics["attempts"].append(attempt_diag)
            diagnostics["final_status"] = "success"
            return diagnostics
        except subprocess.CalledProcessError as e:
            attempt_diag["returncode"] = e.returncode
            attempt_diag["stderr"] = e.stderr[-2000:] if len(e.stderr) > 2000 else e.stderr
            diagnostics["attempts"].append(attempt_diag)
            logger.warning("MD attempt %d failed, rc=%d", attempt + 1, e.returncode)
    
    # Save diagnostics
    diag_path = Path(output_dir) / "md_crash_diagnostics.json"
    diag_path.write_text(json.dumps(diagnostics, indent=2, default=str))
    
    raise MDCrashError(
        f"MD failed after {max_attempts} attempts",
        structure_path=structure_path,
        attempt=max_attempts,
        params=params,
    )
```

**Step 2:** 更新 `config/part3.yaml`

在 `md:` 节点下添加：

```yaml
md:
  production_ns: 100
  npt_ns: 1
  interval: 5
  crash_recovery:
    enabled: true
    max_attempts: 3
    fallback_params:
      - timestep_fs: 1
        constraints: "h-bonds"
      - timestep_fs: 0.5
        constraints: "all-bonds"
```

**Step 3:** 修改 `part3_run_amber_md_mmgbsa_rmsd.py`

在 `_run_single` 函数中，将 `subprocess.run(cmd, check=True, cwd=str(out))` 替换为调用 `run_md_with_recovery`：

```python
from protein_filter.md.runner import run_md_with_recovery
from pathlib import Path

# 修改前先确保导入位置正确
md_script = Path(__file__).resolve().parent.parent / "YZC_MD_SCRIPT" / "run_part3_md_single.sh"

diagnostics = run_md_with_recovery(
    md_script=md_script,
    structure_path=pdb_for_md,
    output_dir=str(out),
    target_chain=target_chain,
    binder_chain=binder_chain,
    max_attempts=3,
    production_ns=production_ns,
    npt_ns=npt_ns,
    tmp=tmp,
    gpu_id=gpu_id,
)
```

注意：`runner.py` 中的 `build_md_cmd` 需要与 `run_part3_md_single.sh` 的参数编码一致。如果参数不全，请补充。

**Step 4:** 编写单元测试

```python
from protein_filter.md.runner import build_md_cmd, FALLBACK_SEQUENCE
from pathlib import Path

def test_fallback_sequence_nonempty():
    assert len(FALLBACK_SEQUENCE) > 0

def test_build_md_cmd_basic():
    cmd = build_md_cmd(
        Path("/fake/md.sh"),
        "/fake/protein.pdb",
        "/fake/out",
        "A", "B",
        {"timestep_fs": 2},
        production_ns=10,
        gpu_id=1,
    )
    assert "bash" in cmd
    assert "A" in cmd
    assert "B" in cmd
```

Run: `pytest tests/unit/md/test_md_runner.py -v`
Expected: PASS

**Step 5:** Commit

```bash
git add src/protein_filter/md/ tests/unit/md/ scripts/part3/part3_run_amber_md_mmgbsa_rmsd.py config/part3.yaml
git commit -m "feat: add MD crash recovery with progressive parameter fallback"
```

---

### Task 2.4: MD 预检查（简化版）

**目标:** 在 MD 正式运行前检查结构文件的合理性

**文件:**
- 创建: `src/protein_filter/md/precheck.py`
- 修改: `src/protein_filter/md/runner.py`
- 创建: `tests/unit/md/test_precheck.py`

**Step 1:** 创建预检查模块

```python
"""Pre-checks for MD input structures."""
import logging
from pathlib import Path
from ..utils.pdb_utils import calculate_clash_score
from ..exceptions import ProteinFilterError

logger = logging.getLogger(__name__)

def run_precheck(pdb_path: str, clash_threshold: int = 50) -> dict:
    """
    Run lightweight pre-checks before MD.
    
    Returns diagnostics dict.
    Raises ProteinFilterError if structure looks suspicious.
    """
    path = Path(pdb_path)
    if not path.exists():
        raise ProteinFilterError(f"PDB not found: {pdb_path}")
    
    # Clash check
    clashes = calculate_clash_score(pdb_path)
    if clashes > clash_threshold:
        logger.warning("High clash score detected (%d > %d): %s", clashes, clash_threshold, pdb_path)
    
    return {
        "pdb_path": pdb_path,
        "clash_score": clashes,
        "clash_warning": clashes > clash_threshold,
    }
```

**Step 2:** 在 `runner.py` 中集成预检查

在 `run_md_with_recovery` 开始时添加：

```python
from .precheck import run_precheck

# Pre-check
try:
    precheck_diag = run_precheck(structure_path)
    diagnostics["precheck"] = precheck_diag
except ProteinFilterError as e:
    diagnostics["precheck_error"] = str(e)
    logger.error("Pre-check failed for %s: %s", structure_path, e)
```

**Step 3:** 编写测试

```python
from protein_filter.md.precheck import run_precheck
from pathlib import Path

def test_precheck_on_minimal():
    pdb = Path(__file__).parent.parent.parent / "data" / "minimal_complex.pdb"
    diag = run_precheck(str(pdb), clash_threshold=100)
    assert "clash_score" in diag
```

Run: `pytest tests/unit/md/test_precheck.py -v`
Expected: PASS

**Step 4:** Commit

```bash
git add src/protein_filter/md/precheck.py tests/unit/md/test_precheck.py src/protein_filter/md/runner.py
git commit -m "feat: add lightweight MD pre-check for clash scores"
```

---

## Phase 3: 架构与 CLI 治理

> 原则：脚本只应负责参数解析和调用库；业务逻辑全部下沉到 `src/`。

---

### Task 3.1: 配置驱动化与验证

**目标:** 用 YAML 统一配置加载器替代 `sed` 修改子脚本

**文件:**
- 修改: `scripts/utils/load_config_env.py`
- 修改: `scripts/run_full_pipeline.sh`
- 创建: `tests/unit/test_config_loader.py`

**Step 1:** 重写 `load_config_env.py`

```python
"""Unified configuration loader for pipeline scripts."""
import yaml
import os
import sys
from pathlib import Path
from typing import Dict, Any

def load_config(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}

def flatten_config(data: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
    """Flatten nested dict to env-style flat keys."""
    items = {}
    for k, v in data.items():
        new_key = f"{prefix}{k}" if not prefix else f"{prefix}_{k}"
        if isinstance(v, dict):
            items.update(flatten_config(v, new_key.upper()))
        else:
            items[new_key.upper()] = str(v)
    return items

def export_env(config_path: str):
    cfg = load_config(config_path)
    flat = flatten_config(cfg)
    for k, v in flat.items():
        os.environ[k] = v

if __name__ == "__main__":
    export_env(sys.argv[1])
```

**Step 2:** 修改 `scripts/run_full_pipeline.sh`

移除顶部的 `sync_config_to_script` 函数和 `sed` 修改逻辑，改为：

```bash
# Load unified config
python3 "${SCRIPT_DIR}/utils/load_config_env.py" "${SCRIPT_DIR}/../config/full_pipeline.yaml"
```

**Step 3:** 编写测试

```python
from scripts.utils.load_config_env import load_config, flatten_config
import tempfile
from pathlib import Path

def test_load_and_flatten():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("md:\n  timestep_fs: 2\n  crash_recovery:\n    enabled: true\n")
        f.flush()
        cfg = load_config(f.name)
        assert cfg["md"]["timestep_fs"] == 2
        flat = flatten_config(cfg)
        assert flat["MD_TIMESTEP_FS"] == "2"
        assert flat["MD_CRASH_RECOVERY_ENABLED"] == "True"
```

Run: `pytest tests/unit/test_config_loader.py -v`
Expected: PASS

**Step 4:** Commit

```bash
git add scripts/utils/load_config_env.py scripts/run_full_pipeline.sh tests/unit/test_config_loader.py
git commit -m "refactor: replace sed-based config sync with unified YAML config loader"
```

---

### Task 3.2: 下沉 Part1 三段式分析逻辑

**目标:** 将 `scripts/part1/part1_analyze_af3_three_stage.py` 中的业务核心下沉为库

**文件:**
- 创建: `src/protein_filter/pipeline/part1_three_stage.py`
- 修改: `scripts/part1/part1_analyze_af3_three_stage.py`

**Step 1:** 提取三个 stage 函数

从 `part1_analyze_af3_three_stage.py` 中提取：
- `_extract_metrics_worker` → `metrics_worker`
- Stage 1 评分筛选逻辑 → `run_stage1_score_filtering`
- Stage 2 Foldseek 粗聚类 → `run_stage2_foldseek_clustering`
- Stage 3 接触精细聚类 → `run_stage3_contact_clustering`

注意不需要拆解所有 1600 行，只需抽象出上述 4 个入口函数即可。具体细节可保留在原文件中，但用新模块的函数调用。

**Step 2:** 重构原脚本

将原脚本改为薄包装层：

```python
"""Thin CLI wrapper for Part1 three-stage analysis."""
import argparse
from protein_filter.pipeline.part1_three_stage import run_full_part1_pipeline

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--config", default="config/part1.yaml")
    args = parser.parse_args()
    run_full_part1_pipeline(args.input, args.output, args.config)

if __name__ == "__main__":
    main()
```

**Step 3:** Commit

```bash
git add src/protein_filter/pipeline/part1_three_stage.py scripts/part1/part1_analyze_af3_three_stage.py
git commit -m "refactor: extract Part1 three-stage core logic into pipeline library"
```

---

### Task 3.3: 建立统一 CLI 入口 `pf-run-pipeline`

**目标:** 添加统一的命令行入口

**文件:**
- 创建: `src/protein_filter/cli/run_pipeline.py`
- 修改: `pyproject.toml`

**Step 1:** 实现 CLI

```python
"""Unified pipeline CLI entry point."""
import argparse
from protein_filter.pipeline.part1_three_stage import run_full_part1_pipeline

def main():
    parser = argparse.ArgumentParser("pf-run-pipeline")
    parser.add_argument("--config", required=True, help="Path to YAML config")
    parser.add_argument("--mode", choices=["denovo", "optimizing"], default="denovo")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and exit")
    args = parser.parse_args()
    
    if args.dry_run:
        print(f"Config OK: {args.config}")
        return
    
    run_full_part1_pipeline(config_path=args.config, mode=args.mode)

if __name__ == "__main__":
    main()
```

**Step 2:** 添加 entry point

在 `pyproject.toml` 的 `[project.scripts]` 中添加：

```toml
pf-run-pipeline = "protein_filter.cli.run_pipeline:main"
```

**Step 3:** 本地安装测试

Run:
```bash
pip install -e .
pf-run-pipeline --help
```
Expected: 显示 help

**Step 4:** Commit

```bash
git add src/protein_filter/cli/run_pipeline.py pyproject.toml
git commit -m "feat: add unified pf-run-pipeline CLI"
```

---

## Phase 4: 验证、文档与收尾

---

### Task 4.1: 全量测试回归

**目标:** 确保所有优化未破坏现有行为

Run: `pytest tests/ -v --tb=short`
Expected: 全部 PASS

若有失败，修复后再运行。

Commit:
```bash
git commit --allow-empty -m "ci: all unit tests passing after optimization phases"
```

---

### Task 4.2: 运行回归 benchmark

**目标:** 量化优化收益

Run:
```bash
python tests/benchmarks/bench_stage1_metrics.py tests/data/minimal_complex.pdb 20
```

记录结果并保存为 `tests/benchmarks/optimized_results.json`。

---

### Task 4.3: 撰写优化报告

**目标:** 明确记录收益和后续工作

**文件:**
- 创建: `docs/OPTIMIZATION_REPORT.md`

内容至少包含：
1. 项目现状概述
2. 各 Phase 主要改进点
3. 性能对比（基准 vs 优化后）
4. 使用便捷性提升（MD 自动恢复、MMPBSA 链检测）
5. 待完成事项

Commit:
```bash
git add docs/OPTIMIZATION_REPORT.md tests/benchmarks/
git commit -m "docs: add optimization report with benchmark comparison"
```

---

### Task 4.4: 完善开源文档

**目标:** 补齐原计划中的开源文档

**文件:**
- 修改: `README.md` 增加 Troubleshooting 章节
- 创建: `CONTRIBUTING.md`
- 创建: `CHANGELOG.md` (若尚不存在)

**Step 1:** 在 `README.md` 末尾添加简短的 Troubleshooting 章节

示例：
```markdown
## Troubleshooting

### MD simulation crashes
Enable `md.crash_recovery.enabled: true` in your config. The runner will automatically fallback to smaller timesteps and stronger constraints.

### MMPBSA chain assignment errors
Set `mmpbsa.auto_detect: true` or explicitly provide `mmpbsa.receptor_mask` and `mmpbsa.ligand_mask`.
```

**Step 2:** 创建 `CONTRIBUTING.md`

```markdown
# Contributing

1. Install in editable mode: `pip install -e ".[dev]"`
2. Run tests: `pytest tests/ -v`
3. Follow existing code style (Black, line-length 88)
4. Add tests for new functionality
```

**Step 3:** Commit

```bash
git add README.md CONTRIBUTING.md CHANGELOG.md
git commit -m "docs: add troubleshooting, contributing, and changelog for open-source readiness"
```

---

## 实施建议

1. **严格按 Phase 顺序执行**。Phase 0 的测试是后续所有重构的安全网。
2. **每个 Task 独立为一个 subagent**，通过 `delegate_task` 派发。
3. **频繁 commit**：每个 Task 一个 commit，便于 bisect。
4. **碰到 Part3 AMBER/shell 脚本**时，首先确保现有脚本仍可正常运行，再逐步用 Python wrapper 替换核心调用。

---

## 快速参考：关键文件改动地图

| 模块 | 改动文件 | 优化点 |
|------|----------|--------|
| 缓存 | `utils/structure_cache.py` (新) | 消除重复 PDB 解析 |
| 缓存 | `utils/metrics_cache.py` (新) | 持久化指标避免重算 |
| 计算 | `utils/chain_detection.py` | cKDTree 向量化 |
| I/O | `utils/pdb_utils.py` | StructureCache 接入 |
| 异常 | `exceptions.py` (新) | 统一错误层次 |
| MD | `md/runner.py` (新) | 崩溃自动恢复 |
| MD | `md/precheck.py` (新) | 运行前检查 |
| MMPBSA | `utils/chain_detection.py` | 链检测增强 |
| 配置 | `utils/load_config_env.py` | YAML 统一加载 |
| 架构 | `pipeline/part1_three_stage.py` (新) | 脚本逻辑下沉 |
| CLI | `cli/run_pipeline.py` (新) | 统一入口 |
| 测试 | `tests/unit/` (新增多个) | 回归测试 |
| 文档 | `OPTIMIZATION_REPORT.md` | 收益量化 |
