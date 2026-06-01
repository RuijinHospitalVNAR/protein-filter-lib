# Foldseek 粗聚类与精细聚类说明

## 1. Foldseek 粗聚类是否没用？要不要删除？

### 日志中的情况

`three_stage_analysis_20260122_171911.log` 显示：

- Stage 1 筛选后：**527** 个结构  
- Stage 2 Foldseek：只得到 **1 个粗簇**，且该簇包含 **全部 527 个结构**  
- 即：粗聚类没有对结构做任何分组，等价于「没做」

因此 **在当前这批数据上**，Foldseek 粗聚类没有起到分组作用。

### 设计意图 vs 实际效果

- **设计意图**：结构数量大、且整体结构差异明显时，先用 Foldseek 按整体结构相似性粗分组，再在每个粗簇内做接触精细聚类，从而减小每个簇的规模、降低计算量。  
- **当前数据**：527 个结构在 Foldseek 下被视作「整体相似」，聚成 1 簇，没有细分。

### 是否删除 Stage 2？

- **不建议直接删除** Stage 2。  
- 在其他数据上（例如结构更多、多样性更高），Foldseek 很可能产生多个粗簇，此时粗聚类是有用的。  
- 已改为 **可选**：通过 `--skip-foldseek` 跳过 Foldseek。

### 使用建议

- 若 **已知** 或 **观察** 到 Foldseek 经常只产生 1 个粗簇（如本批数据），可 **跳过** Stage 2，节省约 10 秒左右，并少一次依赖：  
  ```bash
  python3 analyze_af3_three_stage.py <pdb_dir> ... --skip-foldseek
  ```
- 若希望尝试 Foldseek 分组，则不要传 `--skip-foldseek`。

---

## 2. 精细聚类为什么失败？

### 报错信息

```text
粗簇 0 处理失败: KMeans.__init__() got an unexpected keyword argument 'n_jobs'
```

### 原因

- 代码里对 `sklearn.cluster.KMeans` 传入了 `n_jobs` 参数。  
- 新版 scikit-learn（≥1.4）中，`KMeans` 已 **移除** `n_jobs`，因此报错。

### 已做修改

- 在 `src/protein_filter/clustering/backend/analyzer.py` 中，去掉了 `KMeans(..., n_jobs=...)` 的 `n_jobs` 参数。  
- 修复后，精细聚类应能正常跑通（在满足其他依赖与环境的前提下）。

### 若仍报错

- 确认已拉取最新代码并安装当前环境中的 `scikit-learn`。  
- 若为旧版 sklearn（仍有 `n_jobs`），可保留 `n_jobs`；若为 1.4+，则必须去掉。

### 其他修复（与精细聚类相关）

- **`TypeError: Object of type int64 is not JSON serializable`**：Stage 3 结果中含 `numpy.int64`，`json.dump` 无法序列化。已增加 `_to_json_safe()`，在保存 `stage3_fine_clustering.json` 前递归转换为 Python 原生类型。
- **从 Stage 3 续跑时 `KeyError: 'wall_clock_time_seconds'`**：未运行的 Stage 1/2 的 `perf` 为空，访问其 `wall_clock_time_seconds` 报错。已改为使用 `.get(..., 0)` 及 `.get('wall_clock_time_formatted', '0h 0m 0.0s')`，兼容从 Stage 2/3 续跑。

---

## 3. 相关脚本与参数

| 项目 | 说明 |
|------|------|
| `--skip-foldseek` | 跳过 Stage 2 Foldseek，将所有筛选结构当作一个粗簇做精细聚类 |
| `analyze_af3_three_stage.py --start-from-stage 3` | 从 Stage 3 续跑（依赖已有 Stage 1+2 结果），见 [RESUME_FROM_STAGE_GUIDE.md](RESUME_FROM_STAGE_GUIDE.md) |
| `analyzer.py` 中 KMeans | 已移除 `n_jobs`，兼容 sklearn ≥1.4 |

---

## 4. 性能参考（本批日志）

- Stage 1：约 47 分钟  
- Stage 2：约 9 秒（若跳过则 0）  
- Stage 3：约 37 分钟（接触加载 + 精细聚类），峰值内存约 **46.8 GB**  

当 Foldseek 只产生 1 个簇时，Stage 3 仍对全部 527 个结构做接触精细聚类，因此耗时和内存主要花在 Stage 3。
