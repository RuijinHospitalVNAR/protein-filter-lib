# Stage 1 适度宽松筛选阈值说明

## 背景

默认严格阈值下，部分批次仅约 **0.54%** 通过，结构过少。  
现将 Stage 1 筛选参数适度放宽，可通过 `analyze_af3_three_stage.py` 的 CLI 参数或 `scripts/run_full_pipeline.sh` 配置使用。

## 阈值对照

| 指标 | 原严格值 | 适度宽松值 | 说明 |
|------|----------|------------|------|
| **pLDDT** | ≥ 0.7 | ≥ **0.6** | 略放宽 |
| **clashes** | < 5 | < **12** | 提高碰撞容忍 |
| **pDockQ** | ≥ 0.2 | ≥ **0.12** | 显著放宽（主要卡点） |
| **iPTM** | ≥ 0.6 | ≥ **0.5** | 放宽 |
| **ranking_confidence** | ≥ 0.7 | ≥ **0.6** | 放宽 |
| **ipSAE** | ≥ 0.6 | ≥ **0.45** | 放宽（高 ipSAE=高界面置信度；>0.6 常用作可能结合） |

## 使用方式

- **完整流程（宽松阈值）**：使用 `analyze_af3_three_stage.py` 并传入下方参数，或使用 `scripts/run_full_pipeline.sh` 在脚本内设置对应阈值。
- **仅从 Stage 2 续跑**：使用 `analyze_af3_three_stage.py --start-from-stage 2`，依赖已有 `stage1_filtering_result.json`。详见 [RESUME_FROM_STAGE_GUIDE.md](RESUME_FROM_STAGE_GUIDE.md)。

## 自定义阈值

若需自行调整，可在调用 `analyze_af3_three_stage.py` 时传参，或在 `scripts/run_full_pipeline.sh` 等脚本中设置，例如：

```bash
PLDDT_THRESHOLD=0.6
CLASHES_THRESHOLD=12
PDOCKQ_THRESHOLD=0.12
IPTM_THRESHOLD=0.5
RANKING_CONFIDENCE_THRESHOLD=0.6
IPSAE_THRESHOLD=0.45
```

或通过命令行传参：

```bash
python3 analyze_af3_three_stage.py <pdb_dir> \
  --plddt-threshold 0.6 \
  --clashes-threshold 12 \
  --pdockq-threshold 0.12 \
  --iptm-threshold 0.5 \
  --ranking-confidence-threshold 0.6 \
  --ipsae-threshold 0.45 \
  ...
```
