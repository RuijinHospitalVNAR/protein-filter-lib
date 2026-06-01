# Part3 使用与续跑说明

本文档合并了 Part3 入口、就地续跑、GPU 续跑与修复、WT 续跑、GPU0 缓慢诊断及 1ns 测试的说明。

**推荐入口**：日常请使用 `scripts/run_part3.py`（配置驱动）或 `scripts/run_optimization_pipeline.sh`（Optimizing 模式）。历史脚本见 `archive/legacy_part3/` 与 [CLEANUP_SUMMARY.md](CLEANUP_SUMMARY.md)。

---

## 1. 推荐入口

### 1.1 配置驱动（run_part3.py）

从 Part2 筛选结果跑 Part3（前 N + WT），使用 YAML 配置与 GPU 分配：

```bash
python3 scripts/run_part3.py --config config/part3_100ns.yaml --n_gpu 8
```

输入 CSV、输出目录等由 `config/part3_100ns.yaml` 或环境变量（如 `PART3_INPUT_CSV`、`PART3_OUTPUT_BASE`）指定。

### 1.2 Optimizing 模式（run_optimization_pipeline.sh）

亲和力成熟流程：Part2 → 准备 Part3 CSV → Part3 AMBER → 后处理 → MMGBSA。配置见 `config/optimizing_default.yaml`，环境变量可覆盖。

```bash
bash scripts/run_optimization_pipeline.sh
```

### 1.3 De novo 模式中的 Part3

由 `run_denovo_design.sh` 内部通过 FullPipelineConfig 调用 Part3；是否运行由配置或 `RUN_PART3=0` 控制。

---

## 2. 用法（续跑与 scan-existing）

在仓库根目录下，使用推荐入口时：

- **run_part3.py**：支持 `--resume`、配置中的 `resume.enabled` 等，从 checkpoint 续跑。
- **run_optimization_pipeline.sh**：内部 Part3 步骤带 `--resume`，未完成结构会续跑。

输出目录由配置或环境变量指定（如 `$PART3_OUTPUT_BASE`）；各 GPU 子目录下会有 `run_*.log`。

---

## 3. 监控与日志

使用推荐入口时，各 GPU 子目录（如 `$PART3_OUTPUT_BASE/gpu0` 等）下会有 `run_*.log`。监控示例：

```bash
# 查看所有 GPU 的日志（将 PART3_OUTPUT_BASE 换为你的 Part3 输出根目录）
tail -f $PART3_OUTPUT_BASE/gpu{0..7}/run_*.log

# 检查运行状态
ps aux | grep "run_md_mmgbsa_rmsd.py"
nvidia-smi
```

历史兼容脚本（resume_part3_gpu1-7.sh、resume_gpu0_and_wt.sh、finish_top30_in_place.sh）见 `archive/`。

---

## 4. 故障排查

### 4.1 GPU0 进展缓慢（实际在用 CPU）

**现象**：gpu0 上某个结构的 Production 极慢（约 3–6 ns/day），而其它 GPU 或同机曾达约 700+ ns/day。

**根本原因**：GPU 0 未被 Part3 的 MD 进程占用。`nvidia-smi` 显示 GPU 0 上仅有 Xorg/xfwm4，没有 GROMACS 或 `run_md_mmgbsa_rmsd.py` 子进程，因此该任务实际在用 **CPU** 跑。

**处理建议**：

1. **用 GPU 隔离重跑 gpu0 上的任务**  
   终止当前未用 GPU 的进程，用 **`CUDA_VISIBLE_DEVICES=0`** 启动 gpu0 的 Part3 任务，使该进程只看到 GPU 0，例如：  
   `CUDA_VISIBLE_DEVICES=0 python3 scripts/run_md_mmgbsa_rmsd.py ... --gpu_id 0 ...`  
   这样 GROMACS 会使用唯一的“设备 0”即物理 GPU 0，速度可恢复至约 700+ ns/day。

2. **从 checkpoint 续跑**  
   若已停掉当前任务，可用 `run_part3_md_single.sh --resume` 在该结构目录下从 `Production.cpt` 继续（需在调用链中传入 `--resume`，或直接对单结构目录调用带 `--resume` 的 MD 脚本）。

3. **日常检查**  
   ```bash
   nvidia-smi
   # 确认 GPU 0 上除 Xorg 外，是否有 gmx 或 python 进程占用显存
   ```

### 4.2 GPU 1–7：Device ID 错误（已修复）

**问题**：错误信息 `Device ID X did not correspond to any of the 1 detected device(s)`。

**修复**：确保各进程使用 **GPU 隔离**（例如每个进程设置不同的 `CUDA_VISIBLE_DEVICES`），或按当前推荐脚本的并行方式启动，使每个进程只看到一块 GPU。`run_part3.py` 与 `run_optimization_pipeline.sh` 已按此方式启动。

---

## 5. 就地续跑与历史脚本对照

### 5.1 就地续跑（不重头跑、不换目录）

使用 **run_part3.py** 或 **run_optimization_pipeline.sh** 时，通过 `--resume` 或配置中的 `resume.enabled` 即可在已有输出目录内续跑未完成结构。

### 5.2 历史脚本与推荐入口对照

| 历史脚本 | 推荐替代 |
|----------|----------|
| run_part3_unified.sh、run_part3_unified_relaxed.sh | `scripts/run_part3.py` 或 `scripts/run_optimization_pipeline.sh` |
| run_part3_8gpu_100ns.sh | `scripts/run_part3.py --config config/part3_100ns.yaml --n_gpu 8` |
| resume_part3_gpu1-7.sh、resume_gpu0_and_wt.sh、finish_top30_in_place.sh | 见 `archive/`，功能已由上述推荐入口覆盖 |

详见 [CLEANUP_SUMMARY.md](CLEANUP_SUMMARY.md)。

---

## 6. 使用 Relax 结构跑 Part3

若使用 Rosetta Relax 后的结构跑 Part3（前 N + WT），请：

1. 完成 Part2 的 dump_pdb 输出（得到 `relax_*.cif` 等）。
2. 按项目 Part3 配置准备输入 CSV 与 WT 结构（如执行 `scripts/finish_relaxed_part3_setup.sh`）。
3. 使用 `scripts/run_part3.py` 并指定对应配置，或通过 De novo 流程（`run_denovo_design.sh`）的 FullPipelineConfig 启用 Part3。

详细步骤见：  
`AF3_prediction/IgGM_2d4d2_sh3_op_260126_part3_100ns_relaxed/README_RELAXED_PART3.md`（或当前项目内对应 Relax Part3 输出目录下的 README）。

---

## 7. WT 单独续跑（不推荐，推荐用 unified 一次跑完）

若确需在 GPU 0 上单独续跑 WT（例如从 NPT 之后继续），可在 `protein_filter_lib` 下：

```bash
source /home/supervisor/anaconda3/etc/profile.d/conda.sh
conda activate amber22_py310

WT_OUT="$PART3_OUTPUT_BASE/WT_original_gpu0/WT_original_model"   # 请替换为你的 Part3 输出根目录
WT_PDB="${WT_OUT}/Protein.pdb"

CUDA_VISIBLE_DEVICES=0 bash $REPO_ROOT/YZC_MD_SCRIPT/run_part3_md_single.sh \
  --structure "$WT_PDB" \
  --output_dir "$WT_OUT" \
  --target_chain A \
  --binder_chain B \
  --production_ns 100 \
  --npt_ns 1 \
  --tmp 298.15 \
  --ph 7.4 \
  --conc 0.154 \
  --gpu_id 0 \
  --interval 5 \
  --ntomp 6 \
  --forcefield amber99sb \
  --resume
```

使用 `--resume` 会跳过已完成的 EM_steep、EM_cg、NPT，直接生成 Production.tpr 并运行 100ns Production，然后做 trjconv、MM/PBSA 等。**推荐日常用 `scripts/run_part3.py` 或 `scripts/run_optimization_pipeline.sh` 一次跑完前 N + WT。**

---

## 8. 测试与验收（1ns 多 GPU 测试）

Part3 多 GPU 1ns 测试用于验证：GPU 隔离（CUDA_VISIBLE_DEVICES）、逻辑/物理 GPU 映射、结构分配与监控。

- **结构数量**：8 个（每 GPU 1 个）
- **Production**：1ns（快速测试）
- **预计时间**：每结构约 10–20 分钟（含 MD 与 MM/PBSA）

**运行测试**（在 `protein_filter_lib` 下）：

```bash
./test_part3_multi_gpu_1ns.sh
```

**监控**：可设置 `PART3_MONITOR_DIR` 指向测试输出目录，使用 `scripts/monitor_part3.sh` 或 `watch -n 5 ./scripts/monitor_part3.sh` 查看状态。

**验证要点**：  
1）各 GPU 日志中 CUDA_VISIBLE_DEVICES 正确（0–7）；  
2）无 “Device ID X did not correspond” 等错误；  
3）每个 GPU 处理到分配的结构；  
4）所有结构完成后有对应结果文件。

更详细的 1ns 测试步骤、监控命令与故障排查见原 TEST_PART3_1NS_README（内容已合并到本节）。
