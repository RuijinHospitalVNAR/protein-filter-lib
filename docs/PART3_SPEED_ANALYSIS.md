# Part3 速度慢与 CPU 占用分析

## 一、当前配置与资源分配

- CPU: AMD EPYC 7543, 64 物理核 / 128 逻辑核
- 8 个 GPU 任务，每个 mdrun 使用 -ntomp 12 -pin on -pinoffset (gpu_id*12)
- gpu0 用核 0-11, gpu1 用 12-23, ..., gpu7 用 84-95。合计 96 核，无重叠。96-127 未分配。

结论: 8 个 mdrun 之间 CPU 绑核无矛盾。

## 二、速度慢的主要原因: MMPBSA(sander) 无 CPU 绑核

- MD 阶段: 所有 gmx mdrun 带 -pin on -pinoffset，绑核正确。
- MMPBSA 阶段: gmx_MMPBSA 及其内部 sander 未做任何 CPU 绑核或 OMP 限制。
- sander 为 CPU 密集(约 100% 单核)，可被调度到任意核(包括 0-95)。
- 当某一结构跑完 Production 进入 MMPBSA 时，sander 若落在 12-95，会与其它 7 个 mdrun 争用同一物理核，导致整体变慢。

结论: 任务中存在的 CPU 占用矛盾是 MMPBSA 与 mdrun 争用 0-95 核。

## 三、其它可能因素

- GPU 0 与桌面(Xorg)争用: 建议 CUDA_VISIBLE_DEVICES=0 并 nvidia-smi 确认。
- WT 在 gpu7 上使用 pinoffset 84，与 gpu7 的 mdrun 核区重叠，若与 MMPBSA 时间重叠会加重争用。
- 8 路同时写盘可能造成 I/O 瓶颈。

## 四、建议措施

1. 推荐（已实现）: 在 run_part3_md_single.sh 中调用 gmx_MMPBSA 时使用 taskset 将进程绑到 96-127（默认），避免与 8 个 mdrun 的 0-95 核冲突。若机器逻辑核数少于 128，可设置 MMPBSA_CPUS="" 禁用绑核；或设为可用核范围如 64-79。
2. 确认 gpu0 用 GPU: CUDA_VISIBLE_DEVICES=0 启动，nvidia-smi 查看 gmx 是否占用 GPU 0。
3. 监控: top/htop 看是否有高 CPU 的 sander 与多个 12 核 mdrun 重叠；nvidia-smi 看各 GPU 占用。

## 五、小结

- 8 个 mdrun 之间 CPU 无冲突。
- MMPBSA(sander) 未绑核，与 mdrun 争用 0-95 核，是 part3 整体变慢的主因。
- 推荐修复: 运行 gmx_MMPBSA 时用 taskset 绑到 96-127，避免与 8 个 mdrun 的 0-95 核冲突。
