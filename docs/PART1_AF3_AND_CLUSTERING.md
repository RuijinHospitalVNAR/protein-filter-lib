# Part 1: AF3 预测指标与互作分析 — 代码与功能整理

Part 1 负责 **AF3 相关预测指标计算** 和 **互作分析（聚类）**，对应三阶段流程：评分筛选 → Foldseek 粗聚类 → 簇内 H–A 接触精细聚类。

## 1. 功能概览

| 阶段 | 功能 | 输入 | 输出 |
|------|------|------|------|
| **Stage 1** | AF3 评分筛选 | AF3 输出的 CIF + JSON 目录 | 通过筛选的结构列表、`stage1_filtering_result.json` |
| **Stage 2** | Foldseek 整体结构粗聚类 | Stage 1 通过的结构 | 粗簇 `{cluster_id: [files]}`, `stage2_foldseek_clustering.json` |
| **Stage 3** | 簇内 H–A 接触精细聚类 | 各粗簇内结构 | 精细簇、`stage3_fine_clustering.json`、`fine_clusters/` |

## 2. 代码与模块结构

### 2.1 入口脚本

- **`scripts/part1/part1_analyze_af3_three_stage.py`**  
  - 三阶段流程主入口，支持 `--start-from-stage`、`--skip-foldseek` 等。
  - 内部实现：`stage1_af3_score_filtering`、`stage2_foldseek_coarse_clustering`、`stage3_fine_contact_clustering`、`_export_fine_clusters`。
  - 调用 `_extract_metrics_worker` 做单结构指标提取（可多进程）。

### 2.2 推荐入口

- **主入口**：直接运行 `scripts/part1/part1_analyze_af3_three_stage.py`（见下方使用说明），或使用 `scripts/run_full_pipeline.sh` 一键执行完整两阶段流程（指标计算与筛选分离）。
- 上述旧版 shell 封装（如 `run_three_stage_*`、`run_from_stage2.sh`）已移除，请勿再引用。

### 2.3 工具与指标模块（`src/protein_filter/`）

| 模块 | 路径 | 职责 |
|------|------|------|
| **AF3 指标提取** | `utils/af3_utils.py` | `extract_metrics_from_af3_output`, `auto_extract_af3_metrics`：从 AF3 JSON 提取 PTM、iPTM、PAE 等 |
| **pDockQ** | `utils/pdockq_utils.py` | `get_pdockq`, `pDockQ2`, `pdb_2_coords`：pDockQ 系列与坐标/B-factor 读取 |
| **ipSAE** | `utils/ipsae_utils.py` | `calculate_ipsae_from_script`：调用 `scripts/ipsae.py` 计算 ipSAE |
| **碰撞** | `utils/pdb_utils.py` | `calculate_clash_score`：clashes 计算；`hotspot_residues` 等 |
| **聚类** | `clustering/` | `backend.analyzer.AF3ClusterAnalyzer`：H–A 接触集、Jaccard 距离、kmeans/hdbscan/dbscan/spectral |

### 2.4 Stage 1 指标来源与筛选逻辑

- **指标**：pLDDT（B-factor）、clashes、pDockQ、iPTM、PTM、ranking_confidence（0.8×ipTM + 0.2×pTM）、ipSAE（若有）。
- **筛选**：全部满足配置阈值才通过（如 pLDDT ≥ 0.7、clashes < 5、pDockQ ≥ 0.2、iPTM ≥ 0.6、ranking_confidence ≥ 0.7、ipSAE ≥ 0.6 等）。
- **实现**：`stage1_af3_score_filtering` 内并行调用 `_extract_metrics_worker`，再按 `filter_stats` 统计。

### 2.5 Stage 2 / Stage 3

- **Stage 2**：调用 Foldseek `createdb` + `cluster`，解析 `createtsv` 输出，得到粗簇。
- **Stage 3**：在每个粗簇内用 `AF3ClusterAnalyzer` 做基于 H–A 接触的精细聚类，支持 `compare_algorithms`、`auto_select_best`。

## 3. 数据流简图

```
AF3 输出目录 (CIF + JSON)
        │
        ▼
  _extract_metrics_worker (并行)
        │
        ▼
  stage1_af3_score_filtering  →  stage1_filtering_result.json, filtered_files
        │
        ▼
  stage2_foldseek_coarse_clustering  →  stage2_foldseek_clustering.json, coarse_clusters
        │
        ▼
  stage3_fine_contact_clustering     →  stage3_fine_clustering.json
        │
        ▼
  _export_fine_clusters              →  fine_clusters/
```

## 4. 使用与扩展

- 运行流程：见 [README_THREE_STAGE.md](README_THREE_STAGE.md)，断点续跑见 [RESUME_FROM_STAGE_GUIDE.md](RESUME_FROM_STAGE_GUIDE.md)。
- 修改阈值：改启动脚本中的 `PLDDT_THRESHOLD`、`IPSAE_THRESHOLD` 等，或 `analyze_af3_three_stage.py` 的 CLI 参数。
- 扩展指标：在 `_extract_metrics_worker` 中增加计算项，并在 `stage1_af3_score_filtering` 的筛选逻辑里使用。

Part 1 的输出（如 `filtered_files`、`fine_clusters` 下结构）可作为 **Part 2 PyRosetta 静态分析** 的输入。
