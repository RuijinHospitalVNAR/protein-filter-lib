# Protein Filter Library

一个独立的蛋白质设计过滤和质量评估库，服务于单域抗体设计。

## 特性

- 🔌 **接口抽象** - 清晰的接口设计，易于扩展
- 📊 **丰富指标** - 30+ 种质量评估指标
- 🛠️ **工具支持** - 支持 PyRosetta 结构松弛
- 📝 **易于使用** - 简洁的 API 设计
- 🔄 **专注分析** - 专注于对预测结果的分析和过滤
- 🧬 **聚类筛选** - Stage1阶段支持抗原-抗体互作位置聚类分析

## 说明

本库专注于对**已预测结构**的分析和过滤。结构预测应由外部脚本完成（如 AlphaFold3、Chai-1 等），本库接收预测结果进行分析。

**自动提取功能**：本库可以自动从 AlphaFold3 的预测结果中提取 pLDDT、PTM、iPTM、PAE 矩阵等置信度指标，无需手动提供。

### 使用模式一览

| 模式 | 入口脚本 | 适用场景 |
|------|----------|----------|
| **De novo** | `run_denovo_design.sh` | 大量 AF3 预测，Part1→Part2→Part3 全流程筛选 |
| **Optimizing** | `run_optimization_pipeline.sh` | 已有候选结构，Part2+Part3 亲和力优化 |

各 Part 与主入口脚本的对应关系见 [docs/CLEANUP_SUMMARY.md](docs/CLEANUP_SUMMARY.md)。详情见下方 Quickstart 与 [docs/PLAN_TWO_MODES_THREE_PARTS.md](docs/PLAN_TWO_MODES_THREE_PARTS.md)。

## Quickstart（快速开始）

### De novo 设计（大规模筛选）

适合从大量 AF3 预测结果中自动筛选出首批高置信度候选。

```bash
# 在仓库根目录
# 使用默认配置 config/full_pipeline.yaml，一次性跑完整三段（Part1+Part2+按需 Part3）
bash scripts/run_denovo_design.sh

# 或指定自己的 YAML（见 config/ 目录）
CONFIG=config/my_pipeline.yaml bash scripts/run_denovo_design.sh
```

默认会运行 Part3 MD；若只想做 AF3 + PyRosetta 打分（不跑 MD），可在调用时加：

```bash
RUN_PART3=0 bash scripts/run_denovo_design.sh
```

### 优化 / 亲和力成熟模式（optimizing）

适合在已有 lead 结构或少量突变体上做局部优化，只跑 Part2+Part3：

```bash
# 推荐：编辑 config/optimizing_default.yaml 中的 af3_dir、top_n 等，然后直接运行
bash scripts/run_optimization_pipeline.sh

# 或通过环境变量覆盖（优先级高于 YAML）
AF3_DIR=/path/to/af3_output TOP_N=10 PRODUCTION_NS=1 N_GPU=4 \
bash scripts/run_optimization_pipeline.sh

# 使用自定义配置文件
CONFIG=config/my_optimizing.yaml bash scripts/run_optimization_pipeline.sh
```

更多场景和参数说明见：

- `scripts/README.md` 中“两种模式的主入口”章节  
- `docs/PLAN_TWO_MODES_THREE_PARTS.md` 中的流程与配置示例  
- `docs/DE_NOVO_QUICK_COOKBOOK.md`（De novo 设计 cookbook）  
- `docs/OPTIMIZING_QUICK_COOKBOOK.md`（优化/亲和力成熟 cookbook）

### Pipeline 三部分

本库作为蛋白质设计流程的筛选组件，将评估分为三部分，最终获得最佳设计蛋白：

- **Part 1**：AF3 预测指标与互作分析（`scripts/part1/part1_analyze_af3_three_stage.py`：评分筛选 → Foldseek 粗聚类 → 簇内 H–A 接触精细聚类）
- **Part 2**：PyRosetta 静态物理分析（`scripts/part2/part2_run_pyrosetta_static_relax_interface.py`：界面能量 interface_dG、可选 Relax；整合外部工具如 germinal、PPIFlow，见 [PART2_PYROSETTA](docs/PART2_PYROSETTA.md)）
- **Part 3**：MD 计算（主入口 `scripts/run_part3.py` 配置驱动；底层 `scripts/part3/part3_run_amber_md_mmgbsa_rmsd.py`；MM/GBSA、RMSD）

详见 [docs/PIPELINE_OVERVIEW.md](docs/PIPELINE_OVERVIEW.md)、[Part 1](docs/PART1_AF3_AND_CLUSTERING.md)、[Part 2](docs/PART2_PYROSETTA.md)、[Part 3](docs/PART3_MD.md)。

### 两种使用模式：De novo 设计 & 优化

- **De novo 模式**：从大量 AF3 预测结构出发，依次经过  
  `Part 1（AF3 置信度 + 聚类）→ Part 2（PyRosetta 静态物理打分）→ Part 3（MD/AMBER 动态物理 + MM/GBSA）`，  
  在每一层用不同类型的指标（AF3 置信度、界面能量、MD 稳定性与结合自由能）逐步收窄候选集合，得到首批高质量设计。

- **优化 / 亲和力成熟模式（optimizing）**：从已有 lead 结构或少量突变体出发，可以弱化甚至跳过 Part 1，重点使用  
  `Part 2（PyRosetta 静态物理）+ Part 3（MD 动态物理）` 构成一个外部优化循环：  
  “提出点突变 →（可选少量 AF3 重预测）→ PyRosetta 界面能量与界面特征 → MD / MMGBSA 评估稳定性和结合能”，  
  用于精细调优亲和力与稳定性。

这两种模式共享同一套三层打分体系：**AF3 置信度层 + PyRosetta 静态物理层 + MD 动态物理层**。  
整体计划与 CLI 映射见 [docs/PLAN_TWO_MODES_THREE_PARTS.md](docs/PLAN_TWO_MODES_THREE_PARTS.md)。

### 命令行工具（CLI）

安装后可使用以下入口（与脚本等价，推荐在自动化流程中使用）：

| 命令 | 作用 |
|------|------|
| `pf-part1-compute-metrics` | Part1 快速指标计算，输出 stage1_metrics.parquet |
| `pf-part1-filter` | 基于 stage1 parquet 筛选，输出 stage1_passed.parquet |
| `pf-part2-compute-metrics` | Part2 PyRosetta 指标计算，输出 stage2_metrics.parquet |
| `pf-part2-filter` | 基于 stage2 parquet 筛选，输出 stage2_passed.parquet |
| `pf-part3-collect-mmgbsa` | 收集 Part3 MM/GBSA 结果，输出 ΔG_bind CSV |

示例（Part1 计算 + 筛选）：

```bash
pip install -e .   # 或 pip install protein-filter-lib
pf-part1-compute-metrics -i /path/to/af3_output -o ./stage1_metrics
pf-part1-filter -m ./stage1_metrics/stage1_metrics.parquet -o ./stage1_filtered -f '{"plddt":{"threshold":0.7,"operator":">="},"clashes":{"threshold":5,"operator":"<"}}' --top_n 100
```

**Part3 示例（10+WT 共 11 个结构）**：使用已有 31 个 Part3 结构中的 10 个突变体 + WT 跑一次 MM/GBSA 结果汇总：

```bash
python3 examples/part3_example_11/setup_11_links.py   # 生成 11 个结构的符号链接
pf-part3-collect-mmgbsa -i examples/part3_example_11/amber_11 -o examples/part3_example_11/mmgbsa_11.csv
```

详见 [examples/part3_example_11/README.md](examples/part3_example_11/README.md)。

**Part3 结果可视化**（RMSD + MMGBSA ΔG_bind 出图）：见 [examples/part3_analysis/README.md](examples/part3_analysis/README.md)。

**亲和力成熟模式示例**（AF3 → Part2 选 10 → Part3 AMBER 1ns）：见 [examples/affinity_maturation_example/README.md](examples/affinity_maturation_example/README.md)。

## 使用方式

本库提供两种使用方式：

### 方式 1: 作为 Python 库使用（推荐用于脚本集成）

类似于 PyRosetta 的函数调用方式，可以在 Python 脚本中导入并使用：

```python
from protein_filter import ProteinFilter, FilterConfig, Design

# 创建配置
config = FilterConfig(
    structure_relaxer=FilterConfig.StructureRelaxerConfig(name="pyrosetta"),
    metrics=FilterConfig.MetricConfig(
        enabled=["plddt", "iptm", "clashes", "interface_dG"]
    ),
    filters={
        "external_plddt": {"threshold": 0.7, "operator": ">="},
        "clashes": {"threshold": 1, "operator": "<"},
    }
)

# 创建过滤系统
filter_system = ProteinFilter(config)

# 创建设计对象（包含预测结果）
design = Design(
    sequence="MKLLVL...",
    pdb_path="predicted_design.pdb",  # 外部预测得到的 PDB 文件
    target_chain="A",
    binder_chain="B",
    # 可选：提供预测指标
    prediction_metrics={
        "plddt": 0.85,
        "ptm": 0.75,
        "iptm": 0.70,
    }
)

# 分析和过滤
result = filter_system.filter(design)

if result.passed:
    print(f"设计通过！pLDDT: {result.metrics['external_plddt']}")
else:
    print(f"设计未通过: {result.filter_results}")
```

**适用场景**：
- 在 Python 脚本中集成过滤功能
- 需要自定义过滤逻辑
- 与其他 Python 工具链集成

### 方式 2: 作为命令行工具使用（推荐用于批量处理）

#### 新架构：指标计算与筛选分离（推荐）

**推荐使用新的分离架构**，实现指标计算和筛选的完全分离，支持快速阈值调整而无需重新计算指标。

**优势**：
- ⚡ **快速迭代**：调整阈值秒级完成，无需重新计算指标
- 💾 **数据持久化**：所有指标保存为 parquet 文件，可重复使用
- 🔄 **灵活筛选**：可以尝试不同的阈值组合，进行敏感性分析

**设计理念**（类似 [BoltzGen](https://github.com/HannesStark/boltzgen)）：
与 BoltzGen 等先进工具类似，本库采用**指标计算与筛选分离**的架构，支持在无需重新计算指标的情况下灵活调整筛选参数，这对于大规模设计筛选（100,000+）至关重要。

**使用方法**：

所有脚本的配置都在脚本文件顶部的"配置变量"部分，修改后直接运行即可。

**方式 A: 分步运行（推荐用于阈值调整阶段）**

```bash
# 1. 编辑 scripts/part1/part1_compute_stage1_metrics.sh，设置 INPUT_DIR 等配置
#    推荐：启用聚类筛选（ENABLE_CLUSTERING=true）以先筛选符合目的结合界面的结构
# 2. 运行：计算 Stage 1 快速指标（一次性，耗时）
./scripts/part1/part1_compute_stage1_metrics.sh

# 3. 编辑 scripts/part1/part1_filter_stage1_metrics.sh，设置阈值（PLDDT_THRESHOLD, TOP_N 等）
# 4. 运行：筛选 Stage 1（可反复调整阈值，秒级完成）
./scripts/part1/part1_filter_stage1_metrics.sh

# 5. 编辑 scripts/part1/part1_compute_stage2_metrics.sh，设置配置
# 6. 运行：计算 Stage 2 精细指标（只对 Stage 1 通过的设计）
./scripts/part1/part1_compute_stage2_metrics.sh

# 7. 编辑 scripts/part1/part1_filter_stage2_metrics.sh，设置阈值
# 8. 运行：筛选 Stage 2（可反复调整阈值，秒级完成）
./scripts/part1/part1_filter_stage2_metrics.sh
```

**方式 B: 一键运行完整流程（推荐用于阈值已确定）**

```bash
# 1. 编辑 scripts/run_full_pipeline.sh，设置所有配置和阈值
# 2. 运行：自动执行完整两阶段流程
./scripts/run_full_pipeline.sh
```


**详细文档**：
- [指标计算与筛选分离架构](docs/METRICS_COMPUTATION_SEPARATION.md)
- [脚本使用说明](scripts/README.md)
- [Stage1聚类分析优化说明](docs/STAGE1_CLUSTERING_OPTIMIZATION.md) - **新增：抗原-抗体互作位置聚类功能**
- [AF3环境兼容性说明](docs/AF3_ENVIRONMENT_COMPATIBILITY.md)

## 安装

### 推荐环境：VNAR_OP（Part2 PyRosetta + Part3 全流程）

**当前推荐**：使用 **VNAR_OP** 环境运行 Part2（PyRosetta）与 Part3（MD），以及完整 pipeline。环境定义见 [environment_VNAR_OP.yml](environment_VNAR_OP.yml)。

#### 快速安装（一键脚本）

```bash
cd protein_filter_lib
chmod +x setup_VNAR_OP.sh
./setup_VNAR_OP.sh
```

脚本会创建/更新 conda 环境 `VNAR_OP`，并安装 PyRosetta 与依赖。安装后运行 Part2：`bash scripts/part2/part2_run_pyrosetta_batch.sh`（或 `bash scripts/run_pyrosetta_batch.sh`）；Part3：`python3 scripts/run_part3.py --config config/part3_100ns.yaml --n_gpu 8`。

#### 关键环境变量与配置

以下可由对应 YAML 或脚本默认提供，仅需在覆盖或 CI 时设置：

| 变量 | 含义 | 默认/示例 |
|------|------|-----------|
| `CONFIG` | De novo：full_pipeline YAML 路径；Optimizing：optimizing_default YAML 路径 | De novo: `config/full_pipeline.yaml`；Optimizing: `config/optimizing_default.yaml` |
| `AF3_DIR` | AF3 预测输出目录 | 示例: `/path/to/af3_output` |
| `EXAMPLE_BASE` | Optimizing 模式项目输出根目录 | 默认: `$REPO_ROOT/examples/affinity_maturation_example` |
| `TOP_N` | Optimizing：Part2 选出进入 Part3 的候选数 | 默认: `10` |
| `PRODUCTION_NS` | Part3 AMBER MD 时长（ns） | 示例: `1` 或 `100` |
| `N_GPU` | Part3 使用的 GPU 数（0/auto=自动检测） | 示例: `4` |
| `NTOMP` | 多 GPU 时每进程 CPU 核数 | 默认: `8` |
| `RUN_PART3` | De novo：是否运行 Part3（0=不跑） | 默认: `1` |

更多 Optimizing 变量见 [config/optimizing_default.yaml](config/optimizing_default.yaml)。

#### 使用 conda 环境文件

```bash
cd protein_filter_lib
conda env create -f environment_VNAR_OP.yml
conda activate VNAR_OP
```

#### 手动创建环境

```bash
# 1. 创建环境
conda create -n protein-filter-lib python=3.10 -y
conda activate protein-filter-lib

# 2. 安装依赖
conda install -y -c conda-forge numpy scipy biopython pandas
# 或使用 pip
pip install numpy scipy biopython pandas

# 3. 安装库本身
cd protein_filter_lib

# 方式 A：普通安装（推荐，不需要写权限）
pip install --user .

# 方式 B：可编辑安装（仅开发时需要）
pip install -e .
```

**重要**：
- **普通安装**（`pip install .`）：适合大多数用户，不需要源目录写权限 ✅
- **可编辑安装**（`pip install -e .`）：仅开发时需要，修改代码后立即生效
- 所有脚本会自动使用当前激活的 Python 环境，**无需修改脚本**

详细说明请参阅：
- [环境设置指南](docs/ENVIRONMENT_SETUP.md)
- [安装方法对比](docs/INSTALLATION_METHODS.md)

### 方式 2：仅 Part1（AF3 聚类）或在其他环境中安装

若只运行 **Part1**（AF3 预测指标与聚类），可在已有 Python 环境中安装依赖后直接运行 `analyze_af3_three_stage.py` 或 `scripts/run_full_pipeline.sh`。Part2/Part3 推荐使用 **VNAR_OP** 环境。

```bash
# 在现有环境中安装 Part1 依赖并运行
pip install biopython pandas scikit-learn hdbscan  # 可选：matplotlib, psutil
cd protein_filter_lib
python3 scripts/part1/part1_analyze_af3_three_stage.py <pdb_dir> --chainA B --antigen-chains A
# 或分步/一键：./scripts/run_full_pipeline.sh、scripts/part1/part1_* 等，见 scripts/README.md
```

**验证安装**：`python scripts/check_environment.py`。更多见 [环境设置指南](docs/ENVIRONMENT_SETUP.md)、[AF3 环境兼容性](docs/AF3_ENVIRONMENT_COMPATIBILITY.md)。

## Filter 评估系统

### 评估内容

本库支持 30+ 种质量评估指标，涵盖结构质量、界面特性、结合亲和力等多个方面。所有指标都可以作为过滤器使用。以下为概要；各指标详细说明与公式见文档。

- **结构预测置信度**：pLDDT、PTM、iPTM、PAE 等，可从 AF3 PDB/JSON 自动提取。
- **结构质量**：`clashes`、`clashes_ca` 等碰撞指标。
- **界面分析**：`interface_dG`、`interface_dSASA`、`interface_packstat` 等（PyRosetta），详见 [PART2_PYROSETTA](docs/PART2_PYROSETTA.md)、[SASA_METRICS_EXPLANATION](docs/SASA_METRICS_EXPLANATION.md)。
- **pDockQ 系列**：pDockQ、pDockQ2、LIS 等对接质量指标（部分需 PAE 矩阵），详见 [PDOCKQ2_LIS_DEPENDENCIES](docs/PDOCKQ2_LIS_DEPENDENCIES.md)。
- **SAP**：聚集倾向（`sap_score`、`cdr_sap` 等），详见 [SASA_METRICS_EXPLANATION](docs/SASA_METRICS_EXPLANATION.md)。
- **二级结构**：螺旋/折叠/环区比例（`alpha_all`、`beta_interface` 等）。
- **IPSAE**：界面相互作用评分（改进 ipTM），详见 [IPSAE_PARAMETERS](docs/IPSAE_PARAMETERS.md)、[IPSAE_INTEGRATION](docs/IPSAE_INTEGRATION.md)。
- **亲和力预测**：A2binder、IgLM 等。

更多指标列表与用法见 [文档中心](docs/README.md)。

### 从 AF3 结果自动提取指标

本库**自动**从 AlphaFold3 的预测结果中提取指标，无需任何手动操作。在创建 `Design` 对象时，如果未提供 `prediction_metrics`，库会自动从 PDB 文件和同目录下的 JSON 文件提取所有可用指标。

**自动提取机制**：

```python
from protein_filter import ProteinFilter, FilterConfig, Design

# 创建 Design 对象时，自动提取指标（无需手动操作）
design = Design(
    sequence="MKLLVL...",
    pdb_path="af3_output/design_001.pdb",  # AF3 预测的 PDB
    target_chain="A",
    binder_chain="B",
    # prediction_metrics 参数可选：
    # - 如果未提供，会自动从 PDB 和 JSON 文件提取
    # - 如果已提供，则直接使用（跳过自动提取）
)

# 提取的指标会自动存储在 design.prediction_metrics 中
# 后续的 filter 计算会直接使用这些指标，无需重复提取
result = filter_system.filter(design)
```

**批量处理优势**：

- ✅ **零配置**：无需手动提取，创建 `Design` 对象即自动完成
- ✅ **高效**：每个设计只需提取一次，提取的指标直接用于后续 filter 计算
- ✅ **适合大规模筛选**：自动提取机制专为批量处理优化，适合处理 100,000+ 设计

**AF3 输出文件结构**：

```
af3_output/
├── design_001.pdb              # PDB 文件（包含 pLDDT 在 B-factor）
├── design_001_scores.json      # JSON 文件（包含 PTM、iPTM、PAE 矩阵）
├── design_002.pdb
├── design_002_scores.json
└── ...
```

**自动提取的指标**：

- **pLDDT**：从 PDB 文件的 B-factor 字段提取（总是可用）
- **PTM、iPTM**：从 JSON 文件的 `ptm` 和 `iptm` 字段提取（如果 JSON 存在）
- **PAE 矩阵**：从 JSON 文件的 `pae` 或 `predicted_aligned_error` 字段提取（用于 pDockQ2 和 LIS 计算）
- **其他指标**：如 `confidence` 等（如果 JSON 中包含）

**支持的 JSON 字段名称**：

- `plddt`: 每个残基的 pLDDT 数组
- `ptm`: 预测 TM-score
- `iptm` 或 `i_ptm`: 界面预测 TM-score
- `pae` 或 `predicted_aligned_error`: PAE 矩阵
- `confidence`: 整体置信度分数

**批量处理示例**：

```python
from pathlib import Path
from protein_filter import ProteinFilter, FilterConfig, Design
from protein_filter.utils import get_sequence_from_pdb

# 批量处理所有 AF3 预测结果
af3_output_dir = Path("af3_predictions")
pdb_files = list(af3_output_dir.glob("*.pdb"))

designs = []
for pdb_file in pdb_files:
    # 每个 Design 对象创建时自动提取指标
    design = Design(
        sequence=get_sequence_from_pdb(pdb_file),  # 从 PDB 提取序列
        pdb_path=str(pdb_file),
        target_chain="A",
        binder_chain="B",
        design_name=pdb_file.stem,
        # prediction_metrics 会自动提取，无需手动指定
    )
    designs.append(design)

# 批量过滤（每个设计的指标已自动提取并缓存）
for design in designs:
    result = filter_system.filter(design)
    # 提取的指标直接用于计算，无需重复读取文件
```

**保存和加载提取的指标**（可选，用于缓存）：

对于大规模批量处理，可以保存提取的指标到 JSON 文件，避免重复提取：

```python
from protein_filter.utils import save_extracted_metrics, load_extracted_metrics
from pathlib import Path

# 方式1：提取后立即保存（用于缓存）
af3_output_dir = Path("af3_predictions")
pdb_files = list(af3_output_dir.glob("*.pdb"))

for pdb_file in pdb_files:
    # 自动提取指标
    design = Design(
        sequence=get_sequence_from_pdb(pdb_file),
        pdb_path=str(pdb_file),
        target_chain="A",
        binder_chain="B",
        design_name=pdb_file.stem,
    )
    
    # 保存提取的指标到 JSON（可选，用于后续快速加载）
    if design.prediction_metrics:
        metrics_file = pdb_file.parent / f"{pdb_file.stem}_metrics.json"
        save_extracted_metrics(
            design.prediction_metrics,
            str(metrics_file),
            include_pae_matrix=False,  # PAE 矩阵较大，默认不保存
        )

# 方式2：从保存的文件加载（用于后续运行）
for pdb_file in pdb_files:
    metrics_file = pdb_file.parent / f"{pdb_file.stem}_metrics.json"
    
    if metrics_file.exists():
        # 从缓存文件加载，跳过自动提取
        cached_metrics = load_extracted_metrics(str(metrics_file))
        design = Design(
            sequence=get_sequence_from_pdb(pdb_file),
            pdb_path=str(pdb_file),
            target_chain="A",
            binder_chain="B",
            design_name=pdb_file.stem,
            prediction_metrics=cached_metrics,  # 使用缓存的指标
        )
    else:
        # 如果缓存不存在，自动提取
        design = Design(
            sequence=get_sequence_from_pdb(pdb_file),
            pdb_path=str(pdb_file),
            target_chain="A",
            binder_chain="B",
            design_name=pdb_file.stem,
        )
```

**保存指标的优势**：

- ✅ **加速后续运行**：避免重复提取，直接从 JSON 加载更快
- ✅ **数据备份**：保存提取的指标作为备份
- ✅ **跨平台使用**：保存的 JSON 文件可以在不同环境中使用
- ✅ **选择性保存**：默认不保存 PAE 矩阵（文件较大），可按需开启

**注意**：保存功能是可选的。对于大多数场景，直接使用自动提取即可，无需手动保存。

### Filter 实现方式

#### 1. 配置过滤器

在 `FilterConfig` 中通过 `filters` 字典配置过滤器：

```python
config = FilterConfig(
    filters={
        # 格式: "指标名称": {"threshold": 阈值, "operator": "操作符"}
        "external_plddt": {"threshold": 0.7, "operator": ">="},
        "clashes": {"threshold": 1, "operator": "<"},
        "interface_dG": {"threshold": -10.0, "operator": "<"},
        "interface_packstat": {"threshold": 0.6, "operator": ">="},
        "pdockq": {"threshold": 0.23, "operator": ">="},
    }
)
```

#### 2. 支持的操作符

- **`>=`**: 大于等于（默认）
- **`>`**: 大于
- **`<=`**: 小于等于
- **`<`**: 小于
- **`==`** 或 **`=`**: 等于

#### 3. 评估逻辑

- **AND 逻辑**：所有过滤器必须通过，设计才会被标记为通过
- **缺失指标处理**：如果某个指标未计算或缺失，对应的过滤器会被标记为失败
- **错误处理**：评估过程中的错误会被记录为警告，不会中断整个流程

#### 4. 评估流程

```
输入: Design 对象（包含预测结构和指标）
    ↓
1. 结构松弛（可选）
    ↓
2. 计算所有启用的指标
    ↓
3. 评估每个过滤器
    - 检查指标是否存在
    - 根据操作符比较指标值与阈值
    - 记录通过/失败状态
    ↓
4. 综合评估
    - 所有过滤器通过 → passed = True
    - 任一过滤器失败 → passed = False
    ↓
输出: FilterResult 对象
```

#### 5. 结果查看

```python
result = filter_system.filter(design)

# 查看所有指标值
print(result.metrics)

# 查看每个过滤器的评估结果
print(result.filter_results)
# 输出: {
#     "external_plddt_filter": True,
#     "clashes_filter": True,
#     "interface_dG_filter": False,
#     ...
# }

# 查看是否通过所有过滤器
print(result.passed)  # True 或 False

# 查看警告信息
print(result.warnings)
```

### 完整示例

```python
from protein_filter import ProteinFilter, FilterConfig, Design

# 配置：启用多个指标，设置多个过滤器
config = FilterConfig(
    structure_relaxer=FilterConfig.StructureRelaxerConfig(name="pyrosetta"),
    metrics=FilterConfig.MetricConfig(
        enabled=[
            # 预测置信度
            "plddt", "iptm", "pae",
            # 结构质量
            "clashes",
            # 界面分析
            "interface_dG", "interface_dSASA", "interface_packstat", 
            "interface_sc", "interface_hbonds",
            # pDockQ
            "pdockq", "pdockq2",
            # SAP
            "sap_score",
        ]
    ),
    filters={
        # 预测质量要求
        "external_plddt": {"threshold": 0.7, "operator": ">="},
        "external_iptm": {"threshold": 0.6, "operator": ">="},
        
        # 结构质量要求
        "clashes": {"threshold": 1, "operator": "<"},
        
        # 界面质量要求
        "interface_dG": {"threshold": -10.0, "operator": "<"},
        "interface_packstat": {"threshold": 0.6, "operator": ">="},
        "interface_sc": {"threshold": 0.6, "operator": ">="},
        
        # 对接质量要求
        "pdockq": {"threshold": 0.23, "operator": ">="},
        
        # 聚集倾向要求
        "sap_score": {"threshold": 100, "operator": "<"},
    },
    output_dir="./filter_results",
)

# 创建过滤系统
filter_system = ProteinFilter(config)

# 创建设计对象
design = Design(
    sequence="MKLLVL...",
    pdb_path="predicted_design.pdb",
    target_chain="A",
    binder_chain="B",
    prediction_metrics={
        "plddt": 0.85,
        "ptm": 0.75,
        "iptm": 0.70,
        "pae": 5.2,
        # 可选：提供 PAE 矩阵以计算 pDockQ2
        # "pae_matrix": np.array(...),
    },
)

# 执行过滤
result = filter_system.filter(design)

# 分析结果
if result.passed:
    print("✅ 设计通过所有过滤器！")
    print(f"   pLDDT: {result.metrics.get('external_plddt', 'N/A')}")
    print(f"   iPTM: {result.metrics.get('external_iptm', 'N/A')}")
    print(f"   Clashes: {result.metrics.get('clashes', 'N/A')}")
    print(f"   Interface dG: {result.metrics.get('interface_dG', 'N/A')} kcal/mol")
    print(f"   pDockQ: {result.metrics.get('pdockq', 'N/A')}")
else:
    print("❌ 设计未通过过滤器：")
    for filter_name, passed in result.filter_results.items():
        status = "✅" if passed else "❌"
        metric_name = filter_name.replace("_filter", "")
        metric_value = result.metrics.get(metric_name, "N/A")
        print(f"   {status} {filter_name}: {metric_value}")
```

### 最佳实践

1. **指标选择**：根据设计目标选择合适的指标组合
   - 基础筛选：`plddt`, `clashes`, `interface_dG`
   - 详细分析：添加 `interface_packstat`, `interface_sc`, `pdockq`
   - 抗体设计：添加 `sap_score`, `a2binder_affinity`

2. **阈值设置**：根据经验或文献设置合理的阈值
   - `external_plddt >= 0.7`: 中等置信度
   - `external_plddt >= 0.8`: 高置信度
   - `interface_dG < -10`: 较强的结合
   - `pdockq >= 0.23`: 可能的高质量对接

3. **性能优化**：只启用需要的指标，避免不必要的计算

4. **错误处理**：检查 `result.warnings` 了解计算过程中的问题

## 一键 pipeline 快速入门

- **指标筛选（Part1+Part2 两阶段）**：
  - 编辑并运行 `[scripts/run_full_pipeline.sh]`，根据脚本顶部配置 `INPUT_DIR`、各阶段输出目录和阈值；
  - 脚本会顺序调用 `scripts/part1/part1_compute_stage1_metrics.sh`、`part1_filter_stage1_metrics.sh`、`part1_compute_stage2_metrics.sh`、`part1_filter_stage2_metrics.sh`，输出最终通过设计列表。
- **De novo design 模式（Part1+Part2+可选 Part3）**：
  - 从仓库根目录执行：`bash scripts/run_denovo_design.sh`；
  - 该入口内部调用 `scripts/part1/part1_run_denovo_orchestrator.py` 与 YAML 配置（默认 `config/full_pipeline.yaml`），完成 Part1 AF3 过滤/聚类 + Part2 PyRosetta 打分，并按配置选择是否运行 Part3 MD；
- **Optimization / 亲和力成熟模式（Part2+Part3）**：
  - 从仓库根目录执行：`bash scripts/run_optimization_pipeline.sh`；
  - 配置优先从 `config/optimizing_default.yaml` 加载，可用 `CONFIG=` 指定其它 YAML；环境变量会覆盖 YAML 中的值；
  - 主脚本自动完成 Part2 → 准备 Part3 CSV → Part3 AMBER MD → 轨迹后处理 → MMGBSA → 结果汇总；
  - **配置方式**：编辑 `config/optimizing_default.yaml` 中的 `af3_dir`、`example_base`、`top_n`、`production_ns`、`ntomp` 等；或通过环境变量覆盖（`AF3_DIR`、`TOP_N`、`N_GPU`、`NTOMP`、`PRODUCTION_NS`、`POSTPROCESS_WORKERS`、`MMPBSA_WORKERS`、`SKIP_MMGBSA`）。

## 大规模筛选优化

对于大规模设计筛选（100,000+ 个预测结果），推荐使用**两阶段筛选策略**：

1. **阶段1（粗筛）**：使用快速指标（pLDDT、clashes、pDockQ）快速筛选，保留 top N 候选
2. **阶段2（精筛）**：对 top N 候选进行详细分析（界面分析、SAP、A2binder）

**性能提升**：可以将筛选时间从数周缩短到数小时。详见 [两阶段筛选指南](docs/TWO_STAGE_FILTERING.md) 和 [示例代码](examples/two_stage_filtering.py)。

## 文档

详细文档请参阅 [文档中心](docs/README.md)，内含 Pipeline 总览、Part 1/2/3、环境配置、指标说明、脚本使用等分类索引。

## 许可证

Apache License 2.0

