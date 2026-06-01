# Part 3 快速上手速查（Quick Start）

详细使用与续跑见 [PART3_使用与续跑说明.md](PART3_使用与续跑说明.md)。

只看“怎么用”的一页速查，默认你已经在 `amber22_py310` 等已安装 GROMACS/gmx_MMPBSA/pdb2pqr/obabel 的环境中。

---

## 1. 单 GPU（调试 / 小批量）

### 从 Part 2 CSV 跑前 N 个结构

```bash
cd $REPO_ROOT

python3 scripts/run_md_mmgbsa_rmsd.py \
  --input_csv /path/to/rosetta_static_0.csv \
  --output_dir /path/to/part3_output \
  --target_chain A \
  --binder_chain B \
  --top_n 10 \
  --production_ns 10 \
  --npt_ns 1 \
  --tmp 298.15 \
  --ph 7.4 \
  --conc 0.154 \
  --gpu_id 0 \
  --interval 5 \
  --ntomp 6 \
  --forcefield amber99sb
```

**推荐参数：**
- `--top_n 10~30`：先跑一小批看分布。
- `--production_ns 10`：快速评估。
- `--ntomp 4~6`：避免 CPU 过载。

---

## 2. 多 GPU 并行（推荐入口）

> 用多块 GPU 跑 **前 N 个结构**，每个结构 **100 ns Production**。推荐使用配置驱动入口。

```bash
cd $REPO_ROOT
python3 scripts/run_part3.py --config config/part3_100ns.yaml --n_gpu 8
```

或使用 Optimizing 模式一键流程（Part2 + Part3 + 后处理 + MMGBSA）：

```bash
bash scripts/run_optimization_pipeline.sh
```

配置与路径见 `config/part3_100ns.yaml`、`config/optimizing_default.yaml` 及 README「关键环境变量」小节。

**查看运行状态：**

```bash
tail -f $PART3_OUTPUT_BASE/gpu0/run_*.log
watch -n 5 nvidia-smi
```

---

## 3. 单结构 Shell 调试（看具体问题）

> 用来检查某个结构的 MD / MM/PBSA 是否能跑通。

```bash
cd $REPO_ROOT

./YZC_MD_SCRIPT/run_part3_md_single.sh \
  --structure /path/to/complex.pdb \
  --output_dir /path/to/run_dir \
  --target_chain A \
  --binder_chain B \
  --production_ns 10 \
  --npt_ns 1 \
  --tmp 298.15 \
  --ph 7.4 \
  --conc 0.154 \
  --gpu_id 0 \
  --interval 5 \
  --ntomp 6 \
  --forcefield amber99sb
```

看结果：

```bash
cd /path/to/run_dir

cat mmgbsa_summary.csv          # 单结构汇总
cat FINAL_RESULTS_MMPBSA.dat    # 详细能量分解
cat rmsd.xvg                    # RMSD 曲线（x: 时间, y: nm）
```

---

## 4. 最常看的结果文件路径

- **8 GPU 100 ns 并行：**
  - 汇总 CSV：`$PART3_OUTPUT_BASE/gpu*/part3_results.csv` 或 MMGBSA 收集脚本输出的 CSV
  - 单结构结果：
    - `gpuX/<pdb_name>/mmgbsa_summary.csv`
    - `gpuX/<pdb_name>/FINAL_RESULTS_MMPBSA.dat`
    - `gpuX/<pdb_name>/rmsd.xvg`

- **单 GPU / 调试输出：**
  - `--output_dir` 下同名结构子目录。

如果忘记细节，直接看完整说明：`docs/PART3_MD.md`；使用与续跑（unified、就地续跑、故障排查等）见 `docs/PART3_使用与续跑说明.md`。

