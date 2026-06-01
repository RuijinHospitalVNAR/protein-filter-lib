# AMBER Part3：31 结构 8 GPU 分配与使用说明

## 一、分配表（防重叠）

本机 64 物理核 / 128 逻辑核，**默认 ntomp=8**：8 任务 × 8 线程 = 64 逻辑核，无超配；64–127 预留。

| GPU   | 结构索引（30 个中） | 结构数 | CPU 逻辑核（ntomp=8，默认） |
| ----- | ------------------- | ------ | --------------------------- |
| gpu0  | 0–3                 | 4      | 0–7                         |
| gpu1  | 4–7                 | 4      | 8–15                        |
| gpu2  | 8–11                | 4      | 16–23                       |
| gpu3  | 12–15               | 4      | 24–31                       |
| gpu4  | 16–19               | 4      | 32–39                       |
| gpu5  | 20–23               | 4      | 40–47                       |
| gpu6  | 24–27               | 4      | 48–55                       |
| gpu7  | 28–29 + WT          | 2+1    | 56–63                       |

- **GPU 隔离**：每进程 `CUDA_VISIBLE_DEVICES=$GPU_ID`（0–7），pmemd.cuda 仅见一块 GPU。
- **CPU 隔离**：每进程 `taskset -c <start>-<end>` 绑到上表对应逻辑核，不重叠。

## 二、脚本与用法

### 停止 GROMACS part3 并存档

```bash
cd /data/wcf/protein_filter_lib

# 停止当前 GROMACS part3 任务
./stop_part3_gromacs.sh

# 存档已有进展（打包为 tar.gz）
./archive_part3_gromacs.sh

# 或仅原地复制备份
./archive_part3_gromacs.sh --copy
```

### 运行 AMBER Part3（31 结构，8 GPU）

```bash
cd /data/wcf/protein_filter_lib

source /home/supervisor/anaconda3/etc/profile.d/conda.sh
conda activate amber22_py310

export PART3_AMBER_OUTPUT_BASE="/data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_part3_100ns_amber"
export PART3_INPUT_CSV="/data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_part3_relaxed_top30.csv"

./run_amber_31_8gpu.sh
```

- **WT 结构**：默认使用 `PART3_OUTPUT_BASE/WT_original_gpu0/WT_original_model/Protein.pdb`（GROMACS part3 输出）；可覆盖：`export PART3_WT_STRUCTURE=/path/to/WT.pdb`。
- **续跑**：脚本内已带 `--resume`，会跳过已有 `md_1.rst` 的结构。

## 三、单结构脚本

- **AMBER/run_single.sh**：单结构流程 tleap → min1 → min2 → heat → pressure → equil → md（100ns），支持 `--resume`。
- **scripts/run_amber_31_driver.py**：读 CSV、按块分配、顺序调用 run_single.sh；gpu7 在跑完 28、29 后跑 WT。

## 四、与 GROMACS part3 的协调

- **仅跑 AMBER**：默认 ntomp=8，绑 0–63，64–127 空闲。
- **同机先停 GROMACS 再跑 AMBER**：先执行 `./stop_part3_gromacs.sh` 与 `./archive_part3_gromacs.sh`，再执行 `./run_amber_31_8gpu.sh`。
