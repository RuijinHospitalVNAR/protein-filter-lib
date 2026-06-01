## 优化 / 亲和力成熟 quick cookbook

面向场景：已有 **lead 结构或少量突变体**，希望通过 PyRosetta 静态物理 + MD/AMBER 动态物理进一步优化亲和力和稳定性。

假设：
- 已有 AF3 预测输出目录（或其它来源的复合物结构集合），例如：`/data/.../af3_predictions/`；
- 已按照 `docs/ENVIRONMENT_SETUP.md` 创建并激活 **VNAR_OP**（Part2）和 **amber22_py310**（Part3）环境；
- GPU 数量 ≥ 1。

### 步骤 0：激活环境并进入仓库

```bash
cd /path/to/protein_filter_lib
```

脚本内部会在需要时分别 `conda activate VNAR_OP` 和 `conda activate amber22_py310`。

### 步骤 1：配置参数（YAML 或环境变量）

**推荐**：编辑 `config/optimizing_default.yaml`，修改以下字段：

| 字段 | 含义 | 示例 |
|------|------|------|
| `af3_dir` | AF3 预测输出目录（含 PDB/JSON） | `/path/to/af3_outputs` |
| `example_base` | 项目输出根目录；`null` 表示使用 `examples/affinity_maturation_example` | `null` 或 `/path/to/project` |
| `top_n` | Part2 选出前 N 个候选进入 Part3 | `10` |
| `production_ns` | Part3 AMBER MD 时长（ns） | `1` 或 `100` |
| `ntomp` | 多 GPU 时每进程 CPU 核数 | `8` |
| `n_gpu` | `null`/`auto`=自动检测；整数=固定 GPU 数 | `null` |

**或**通过环境变量覆盖（优先级高于 YAML）：

```bash
export AF3_DIR=/path/to/your_af3_outputs
export EXAMPLE_BASE=/path/to/your_project
```

使用自定义配置文件：`CONFIG=config/my_optimizing.yaml bash scripts/run_optimization_pipeline.sh`

### 步骤 2：运行优化流水线

完成步骤 1 的配置后，直接运行。脚本会自动检测 GPU 数量（`n_gpu` 为 `null`/`auto` 时）；亦可手动指定 `N_GPU`：

```bash
# 使用 YAML 中的配置（含自动 GPU 检测）
bash scripts/run_optimization_pipeline.sh

# 手动指定 4 块 GPU
N_GPU=4 bash scripts/run_optimization_pipeline.sh
```

流水线内部步骤：

1. **Part2**：在 VNAR_OP 环境下运行 PyRosetta 静态打分，输出 `PART2_OUT/rosetta_static_0.csv`；
2. **准备 Part3 CSV**：按 `top_n` 选择候选并写出 CSV；
3. **Part3 AMBER MD**：在 amber22_py310 环境下按 `N_GPU` 并行、`production_ns` 运行 MD；
4. **后处理 + MMGBSA**：等待 MD 完成后调用后处理脚本和 MMPBSA，最终生成 ΔG_bind 汇总 CSV。

### 步骤 3：查看结果与排序

在 `EXAMPLE_BASE` 下，你将看到类似结构：

- `part2_out/rosetta_static_0.csv`：PyRosetta 静态评分；
- `part3_amber_out/gpu*/...`：每个候选的 AMBER 运行目录与轨迹；
- `AMBER_MMPBSA/mmpbsa_binding_*.csv` 或自定义输出 CSV：MMGBSA 结合自由能汇总。

可按以下思路综合排序：

1. 先用 `rosetta_static_0.csv` 过滤掉静态界面能量很差的候选；
2. 再用 MMGBSA 中的 ΔG_bind 排序，挑选结合能更优的突变体；
3. 如果需要，配合 RMSD/二级结构分析，排除结构不稳定的轨迹。

更多细节参考：

- `examples/affinity_maturation_example/README.md`
- `docs/PART2_PYROSETTA.md`
- `docs/PART3_MD.md`

