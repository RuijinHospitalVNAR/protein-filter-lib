## AMBER Part3（31 结构，8 GPU）流程总览（try5 版本）

本文件梳理当前使用的 **AMBER Part3 工作流**：结构来源 → 脚本调用链 → MD 参数 → MM/PBSA 情况 → CPU/GPU 与 `htop` 现象，方便后续复盘和交接。

---

### 1. 结构来源与整体目标

- **目标**：对 Part2/relax 选出的前 30 个候选结构 + 1 个 WT，在 AMBER 中跑 **100 ns 生产模拟**（NPT, 300 K, ff14SB/TIP3P），为后续能量与构象分析提供一致的 AMBER 轨迹。
- **结构来源**：
  - 前 30 个结构：来自 CSV 中的 `pdb_path` 列（相对路径会按 CSV 所在目录补成绝对路径），通常是 **relaxed 后的复合物 PDB/CIF**。
  - WT 结构：默认从 **GROMACS Part3 输出**拷贝  
    `...part3_100ns_relaxed_nvt310_ff14sb/WT_original_gpu0/WT_original_model/Protein.pdb`，可通过 `PART3_WT_STRUCTURE` 环境变量覆盖。

> 运行目录由配置或环境变量 `PART3_OUTPUT_BASE` / `PART3_AMBER_OUTPUT_BASE` 指定（示例：`$PART3_OUTPUT_BASE`）。

---

### 2. 脚本调用链与命令路径

整体是一条自上而下的三层链路：

1. **顶层：8 GPU 调度脚本**  
   `protein_filter_lib/run_amber_31_8gpu.sh`
2. **中层：单 GPU driver（分配结构列表）**  
   `protein_filter_lib/scripts/run_amber_31_driver.py`
3. **底层：单结构 AMBER MD 流程**  
   `protein_filter_lib/AMBER/run_single.sh`

#### 2.1 顶层：run_amber_31_8gpu.sh

- **输入/输出配置（可通过环境变量覆盖）**：
  - `PART3_INPUT_CSV`：Part2 输出的 relaxed top-N CSV 路径（示例：`$REPO_ROOT/path/to/part3_relaxed_top30.csv`）。
  - `PART3_AMBER_OUTPUT_BASE` 或 `PART3_OUTPUT_BASE`：Part3 AMBER 输出根目录（示例：`$PART3_OUTPUT_BASE`）。
  - `PART3_OUTPUT_BASE`：GROMACS Part3 输出基路径，用于推导 WT 结构。
  - `PART3_WT_STRUCTURE`：可显式指定 WT PDB。
  - `NTOMP=8`：每个 GPU 任务对应的“允许使用的 CPU 逻辑核数”（详见 4.2）。

- **环境**：
  - `source /home/supervisor/anaconda3/etc/profile.d/conda.sh`
  - `conda activate amber22_py310`

- **核心调用（每个 GPU 启动一个 driver 进程）**：

  ```bash
  # 伪代码示意（实际在 for 循环中）
  export CUDA_VISIBLE_DEVICES=$GPU_ID
  taskset -c ${CPU_START}-${CPU_END} \
    python3 "${SCRIPT_DIR}/scripts/run_amber_31_driver.py" \
      --input_csv "$INPUT_CSV" \
      --output_dir "$GPU_DIR" \
      --gpu_id "$GPU_ID" \
      --n_gpu 8 \
      --top_n 30 \
      --wt_structure "$WT_STRUCTURE" \
      --resume
  ```

- **GPU/CPU 分配（ntomp=8）**（见 `docs/PART3_AMBER_8GPU.md`）：

  | GPU   | 结构索引（0–29 中） | 结构数 | CPU 逻辑核范围 |
  | ----- | ------------------- | ------ | -------------- |
  | gpu0  | 0–3                 | 4      | 0–7            |
  | gpu1  | 4–7                 | 4      | 8–15           |
  | gpu2  | 8–11                | 4      | 16–23          |
  | gpu3  | 12–15               | 4      | 24–31          |
  | gpu4  | 16–19               | 4      | 32–39          |
  | gpu5  | 20–23               | 4      | 40–47          |
  | gpu6  | 24–27               | 4      | 48–55          |
  | gpu7  | 28–29 + WT          | 2 + 1  | 56–63          |

#### 2.2 中层：run_amber_31_driver.py

路径：`protein_filter_lib/scripts/run_amber_31_driver.py`

- 读取 `--input_csv`，要求至少有 `pdb_path` 列；如存在 `interface_score`，会按该列排序取前 `top_n`（默认 30）。
- 将相对 `pdb_path` 补成绝对路径，过滤出真实存在的文件。
- 对 30 个结构按“块分配”方式分给 8 个 GPU（连续切片，而非轮询）。
- 为本 GPU 分配到的每个结构创建子目录：

  ```text
  <PART3_AMBER_OUTPUT_BASE>/gpuX/<pdb_name 或 文件名stem>/
  ```

- 调用底层脚本：

  ```bash
  bash AMBER/run_single.sh \
    --structure <pdb_or_cif> \
    --output_dir <gpuX>/<结构名> \
    --gpu_id 0 \
    --resume
  ```

- `--resume` 逻辑：若 `<结构目录>/md_1.rst` 已存在，则视为已完成，直接跳过该结构。
- 对于 **gpu7**：在前 30 跑完后，若设置了 `--wt_structure` 且文件存在，则额外跑 WT，输出到：
  `.../WT_original_gpu7/WT_original_model/`。

#### 2.3 底层：AMBER/run_single.sh（单结构 MD）

路径：`protein_filter_lib/AMBER/run_single.sh`

**输入参数**：

- `--structure <pdb|cif>`：原始结构文件。
- `--output_dir <dir>`：单结构输出目录。
- `--gpu_id N`：逻辑 GPU 编号（在本脚本中仅作信息，不再设置 CUDA 设备）。
- `--resume`：根据已有 `*.rst` 文件从中间步骤续跑。

**主要步骤**：

1. **结构准备**：
   - 若为 `.cif/.mmcif`：
     - 如果文件内容本身已是 PDB 格式（前几行有 `HEADER|ATOM|HETATM|REMARK|CRYST1`），直接复制为 `system.pdb`。
     - 否则优先用 `obabel -icif -opdb` 转换；失败时降级到 BioPython `MMCIFParser` + `PDBIO`。
   - 若为 `.pdb`：直接复制/软链为 `system.pdb`。
   - 使用 `pdb4amber --add-missing-atoms` 对 `system.pdb` 做规范化（重命名端基、补缺失原子等），但**不**使用 `--reduce` 避免不兼容氢命名。
   - 用 `awk` 删除所有氢原子行（通过 PDB 元素列判断），让后续 `tleap` 按 ff14SB 规则重建氢。
   - 检查 PDB 中必须存在 `ATOM/HETATM` 记录，否则报错退出。

2. **tleap 构建拓扑与坐标**：
   - 模板：`AMBER/tleap.in.template`：

     ```text
     source leaprc.protein.ff14SB
     source leaprc.water.tip3p
     COM = loadpdb STRUCTURE_PDB
     solvateoct COM TIP3PBOX 8.0
     charge COM
     addions2 COM Na+ 0
     addions2 COM Cl- 0
     saveAmberParm COM system.prmtop system.inpcrd
     savepdb COM system.pdb
     quit
     ```

   - Resume 模式下，如果 `system.prmtop` 或 `system.inpcrd` 任一不存在，会重新跑一次 `tleap`。

3. **准备 MD 输入文件**：
   - 把 `AMBER/` 目录中的 `min1.in, min2.in, heat.in, pressure.in, equil.in, md.in` 复制到结构目录（若结构目录中不存在）。

4. **MD 流程（完整跑）**：

   顺序：`min1 → min2 → heat → pressure → equil → md (100 ns)`，全部使用 `pmemd.cuda`：

   - `min1`（初始最小化）：

     ```bash
     pmemd.cuda -O -i min1.in -o min1.out -p system.prmtop -c system.inpcrd -r min1.rst -ref system.inpcrd
     ```

   - `min2`（更彻底的最小化）：

     ```bash
     pmemd.cuda -O -i min2.in -o min2.out -p system.prmtop -c min1.rst -r min2.rst
     ```

   - `heat`（升温阶段）：

     ```bash
     pmemd.cuda -O -i heat.in -o heat.out -p system.prmtop -c min2.rst -r heat.rst -x heat.mdcrd -ref min2.rst -e heat.mden
     ```

   - `pressure`（等压预平衡）：

     ```bash
     pmemd.cuda -O -i pressure.in -o pressure.out -p system.prmtop -c heat.rst -r pres.rst -x pres.mdcrd -ref heat.rst -e pres.mden
     ```

   - `equil`（正式平衡阶段）：

     ```bash
     pmemd.cuda -O -i equil.in -o equil.out -p system.prmtop -c pres.rst -r equil.rst -x equil.mdcrd -ref pres.rst -e equil.mden
     ```

   - `md`（生产 100 ns）：

     ```bash
     pmemd.cuda -O -i md.in -o md_1.out -p system.prmtop -c equil.rst -r md_1.rst -x md_1.nc -ref equil.rst -e md_1.mden
     ```

5. **续跑逻辑（--resume）**：
   - 若已存在 `md_1.rst`：视为生产阶段已完成，直接退出。
   - 若存在 `equil.rst` 但无 `md_1.rst`：从 `equil.rst` 重新跑 `md`。
   - 若只到 `pres.rst/heat.rst/min2.rst/min1.rst`，会按缺失阶段逐步补全后进入 `md`。

---

### 3. MD 参数与模拟设定（amber.in 文件）

这里只列出最关键的几个 `.in` 文件要点。

#### 3.1 生产阶段 md.in（100 ns）

路径：`AMBER/md.in`

```text
Production 100ns
 &cntrl
  imin=0,irest=1,ntx=5,
  nstlim=50000000,dt=0.002,
  ntc=2,ntf=2,
  cut=8.0, ntb=2, ntp=1, taup=2.0,
  ntpr=1000, ntwx=1000,
  ntwr=1000, ntwe=1000,
  ntt=3, gamma_ln=2.0,
  tempi=300.0, temp0=300.0, ig=-1,
  iwrap=1
 &end
```

- **时间长度**：`nstlim=50,000,000` × `dt=0.002 ps` = 100,000 ps = **100 ns**。
- **系综**：NPT（`ntb=2, ntp=1`），Langevin thermostat（`ntt=3`）。
- **温度**：300 K。
- **约束**：`ntc=2, ntf=2`（SHAKE 约束 H-键）。

#### 3.2 equil.in / pressure.in

- `equil.in`：50,000 步 × 0.002 ps = 100 ps，NPT + Langevin（与 md.in 类似，只是时间更短）。
- `pressure.in`：也是 50,000 步；对非水/离子原子施加位置约束（`ntr=1`，`restraintmask='!:WAT,Cl-,K+,Na+ & !@H='`），用于温和“压实”体系。

---

### 4. 目前的 MM/PBSA 情况与 GROMACS 工作流对比

#### 4.1 当前 AMBER Part3（try5）：**仅进行 MD，不执行 MM/PBSA**

- `run_amber_31_8gpu.sh → run_amber_31_driver.py → AMBER/run_single.sh` 这条链路中，**没有**任何 `gmx_MMPBSA`、`MMPBSA.py` 或 `pbsa` 调用。
- 输出主要包括：
  - `leap.log`、`system.prmtop`、`system.inpcrd`、`system.pdb`
  - 各阶段的 `*.out`、`*.rst`、`*.mdcrd`/`*.mden`
  - 生产轨迹 `md_1.nc` 与重启 `md_1.rst`
- 因此，AMBER Part3 当前是一个 **“只做 AMBER MD、先把 100 ns 轨迹和重启文件跑齐”** 的阶段，MM/PBSA 暂未接入。

#### 4.2 之前 GROMACS Part3 使用的 MM/PBSA：gmx_MMPBSA（PB 模型）

脚本：`YZC_MD_SCRIPT/run_part3_md_single.sh`。

- 在 GROMACS 100 ns `Production` 结束后：
  - 用 `trjconv` 做中心化与 PBC 处理，得到 `ProductionPBSA.xtc`。
  - 用 `make_ndx` 基于残基号分出 `ChainA (1–105)` 和 `ChainB (106–211)`。
  - 自动生成 `mmpbsa.in`，关键设置包括：
    - `forcefields = "leaprc.protein.ff14SB"`
    - PB 模型：`&pb ipb=2, indi=1.0, exdi=80.0`，`istrng` 由脚本注入（通常 ~0.15 M）。
    - `&decomposition idecomp=2, print_res="within 6"`（残基分解，仅输出 6 Å 内残基）。
  - 调用 `gmx_MMPBSA`：

    ```bash
    gmx_MMPBSA -O -i mmpbsa.in -cs Production.tpr -ci index_mmpbsa.ndx \
      -cg <ChainA组号> <ChainB组号> \
      -ct ProductionPBSA.xtc -cp topol.top -nogui
    ```

- 为避免与 8 个 `mdrun` 抢 CPU，`gmx_MMPBSA`（内部 `sander`）在脚本中通过 `taskset` 绑到了 96–127 逻辑核。

---

### 5. CPU/GPU 分配与 `htop` 中“单核占用”现象说明

#### 5.1 现有 CPU/GPU 策略

- **GPU 隔离**：顶层脚本对每个 driver 进程设置 `CUDA_VISIBLE_DEVICES=$GPU_ID`，使进程内部只看到一块 GPU，且该 GPU 逻辑编号为 0。
- **CPU 亲和性**：使用

  ```bash
  taskset -c <start>-<end> python3 run_amber_31_driver.py ...
  ```

  将每个 GPU 任务“允许运行的 CPU 逻辑核范围”限制在一个 **不重叠** 的 8 核区间（0–63）。

#### 5.2 为何 `htop` 看起来“像单核在跑”？

- `taskset` 的作用是限制 **“可用核的集合”**，并不会“强制把这几个核全部吃满”。
- `pmemd.cuda` 是 **GPU 主导型** 程序：
  - 绝大部分浮点计算在 GPU 上完成。
  - CPU 端主要承担任务调度、数据搬运和少量控制逻辑。
  - 常见表现是：**一个主线程在某个逻辑核上使用率较高（接近 100%）**，其它辅助线程占用很小。
- 因此，即便你允许 `pmemd.cuda` 在 8 个逻辑核范围内运行，在 `htop` 里通常看到的也是“每个进程主要压一颗核”，而不是像纯 CPU 多线程 MD 那样“8 核平均 70–90%”。

> 换句话说：当前 AMBER try5 里 `htop` 显示“单核高占用”是 **正常且预期的**，并不代表绑核或脚本有问题；吞吐主要看 GPU 利用率与 `md_1.out` 中的 ns/day。

---

### 6. 后续是否可以在 AMBER MD 结束后做 MM/PBSA？

**可以**，并且有两种主要路线：

1. **使用 AmberTools 的经典 MMPBSA.py，对 AMBER 轨迹做 MM/PBSA**（推荐与本 AMBER MD 流程配套）：
   - 直接使用当前每个结构目录下的：
     - `system.prmtop`
     - `md_1.nc`（或转换成 `md_1.mdcrd`）
   - 并根据纳米抗体-抗原复合物的链划分，构造 `complex.prmtop / receptor.prmtop / ligand.prmtop` 或使用 mask（例如 `:1-105` vs `:106-211`）在 `MMPBSA.py` 的 `-use_sander` 模式下运行。
   - 相比 GROMACS + gmx_MMPBSA，这样可以 **完全在 AMBER 格式内闭环**，避免 GROMACS→AMBER 的拓扑转换。

2. **继续使用 gmx_MMPBSA，但改为喂 AMBER 轨迹 / AMBER 拓扑**（技术上可行，但不如上面路线干净）：
   - gmx_MMPBSA 本身也支持 AMBER 拓扑，不过需要额外小心 TOP/TRAJ 格式与索引的一致性。
   - 鉴于你已经用 gmx_MMPBSA 完成了一部分 GROMACS Part3 的分析，如果希望 **结果风格完全一致**，可以考虑这条路线，但实现上会更绕。

现阶段 AMBER Part3 脚本没有自动集成任一条 MM/PBSA 路线，主要是先确保 **31 个结构的 AMBER 100 ns 模拟稳定跑通**。  
若后续需要，可以在每个结构目录下增加一个独立的 `run_mmpbsa_amber.sh` 或统一 driver 脚本，封装 AmberTools `MMPBSA.py` 的调用（含 mask、PB 设定、并行策略与 CPU 绑核），使其与现有 GROMACS + gmx_MMPBSA 的配置在物理模型上尽量对齐。

---

### 7. AMBER PB MMPBSA 批量流程（已实现的后处理子模块）

在 AMBER Part3 try5 上，我们已经实现了一套 **基于 AmberTools MMPBSA.py 的 PB 模型批量打分模块**，路径位于 `AMBER_MMPBSA/`。

#### 7.1 单结构脚本：`AMBER_MMPBSA/run_mmpbsa_single.sh`

- **作用**：对单个 AMBER MD 结构目录（如 `.../amber_try5/gpu1/Y84A_S86G_model/`）执行 PB 模型 MM/PBSA。
- **依赖**：结构目录内已有：
  - `system.prmtop`
  - `md_1.nc`
  - `system.pdb`
- **功能要点**：
  - 自动从 `system.pdb` 中按 **链 ID** 解析复合物：第一条蛋白链视为 receptor，其余链合并为 ligand，转成 Amber 掩膜（例如 `:1-105` vs `:106-211`，或更一般的 `:A` vs `:B`）。
  - 或者通过环境变量手动指定：
    - `MMPBSA_RECEPTOR_MASK=':A'`
    - `MMPBSA_LIGAND_MASK=':B'`
  - 使用模板 `AMBER_MMPBSA/mmpbsa_pb.in.template` 生成 `mmpbsa_amber_pb.in`，PB 设定与 gmx_MMPBSA 保持一致（`indi=1.0, exdi=80.0, istrng=0.154` 等）。
  - 调用 AmberTools `MMPBSA.py`，输出 `FINAL_RESULTS_MMPBSA_AMBER.dat`。

#### 7.2 批量运行：`AMBER_MMPBSA/run_mmpbsa_batch.py`

- **作用**：在 AMBER Part3 根目录（如 try5）下，自动发现所有已完成 MD 的结构，并并行调用 `run_mmpbsa_single.sh`。
- **推荐时机**：在 **全部 31 个结构的 Production 结束后** 一次性运行。
- **示例（对 try5 目录批量跑 PB MMPBSA）**：

cd $REPO_ROOT
source /home/supervisor/anaconda3/etc/profile.d/conda.sh
conda activate amber22_py310

# 可选：将 PB 计算绑到高位 CPU 核，避免与其它作业抢 0–63
export MMPBSA_CPUS="96-127"

python3 AMBER_MMPBSA/run_mmpbsa_batch.py \
  --amber_root "$PART3_OUTPUT_BASE" \
  --max_workers 4
