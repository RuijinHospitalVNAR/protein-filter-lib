# Part3 AMBER 后处理（31 结构）

MD 跑满 100 ns 后，对 31 个结构目录做统一后处理：合并轨迹、RMSD、去水、10 ns 抽帧、最后帧、平均结构。

## 1. 单结构后处理

- **脚本**：`protein_filter_lib/AMBER/postprocess_single_cpptraj.sh`
- **用法**：`bash postprocess_single_cpptraj.sh <结构目录>`
- **要求**：目录内需有 `system.prmtop` 和至少一个 `md_*.nc`（如 `md_1.nc`、`md_2.nc`）。
- **输出**（均在结构目录内）：
  - `md_total.nc`：总 0–100 ns 轨迹；**多段**（md_1 + md_2 + …）时做合并，**单段**（仅 md_1）时直接复制为 md_total.nc，不合并
  - `rmsd_bb.dat`：蛋白 backbone（@CA,C,N）相对第一帧的 RMSD 时间序列
  - `md_protein_nowat.nc`：去水/离子后的蛋白轨迹
  - `protein_10ns.pdb`：每 10 ns 一帧的代表构象（**多模型 PDB，共 10 个 MODEL**：MODEL 1 = 0 ns，MODEL 2 = 10 ns，…，MODEL 10 = 90 ns；在 PyMOL/VMD 中需按多帧/轨迹加载才能看到 20–90 ns）
  - `last_frame.pdb`：最后一帧结构
  - `avg_structure.pdb`：时间平均结构
  - `postprocess_cpptraj.log`：cpptraj 运行日志

## 2. 批量 31 结构

- **脚本**：`protein_filter_lib/scripts/run_postprocess_31_amber.py`
- **用法**：
  ```bash
  cd protein_filter_lib
  python3 scripts/run_postprocess_31_amber.py --base_dir /path/to/part3_100ns_amber_try5
  ```
- **base_dir**：你的 Part3 AMBER 输出根目录（如 `$PART3_OUTPUT_BASE` 或 `config` 中配置的路径）。
- **可选**：`--dry_run` 只列出将处理的目录，不执行。
- **环境**：需能调用 `cpptraj`（如 `PATH` 中有 Amber22 的 bin，或设置 `CPPTRAJ=/path/to/cpptraj`）。

## 3. 后台运行与监控

每个结构约 2–4 分钟，31 个合计约 1–2 小时。可后台运行并查看日志：

```bash
cd protein_filter_lib
nohup python3 -u scripts/run_postprocess_31_amber.py \
  --base_dir "$PART3_OUTPUT_BASE" \
  >> "$PART3_OUTPUT_BASE/postprocess_31.log" 2>&1 &

# 监控（将 PART3_OUTPUT_BASE 换为你的 Part3 输出根目录）
tail -f "$PART3_OUTPUT_BASE/postprocess_31.log"
```

## 4. 后续用途

- **MM/PBSA（总轨迹）**：对 **总 100 ns 轨迹** 做结合自由能时，使用后处理得到的 `md_total.nc`。  
  - 单结构：在结构目录下执行 `bash AMBER_MMPBSA/run_mmpbsa_single.sh --amber_dir <dir>` 时，脚本会**优先使用 `md_total.nc`**（若存在），否则用 `md_1.nc`。  
  - 批量：`python3 AMBER_MMPBSA/run_mmpbsa_batch.py --amber_root <try5>` 会**自动选用各目录下的 `md_total.nc`**（若存在），即对 31 个结构做总轨迹 MM/PBSA。
- **RMSD 图**：用 `rmsd_bb.dat` 画 RMSD vs time，检查平衡。
- **机制/图示**：用 `protein_10ns.pdb`、`last_frame.pdb`、`avg_structure.pdb` 做结构分析与作图。
