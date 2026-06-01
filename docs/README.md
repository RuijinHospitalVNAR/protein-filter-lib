# Protein Filter Library 文档中心

本目录为 **protein_filter_lib** 的文档索引。按主题分类，便于查找与跳转。

---

## 一、Pipeline 与流程

| 文档 | 说明 |
|------|------|
| [PIPELINE_OVERVIEW](PIPELINE_OVERVIEW.md) | **Pipeline 总览**：Part 1 → Part 2 → Part 3，三部分架构与使用顺序 |
| [PART1_AF3_AND_CLUSTERING](PART1_AF3_AND_CLUSTERING.md) | **Part 1**：AF3 预测指标与互作分析（代码与功能整理） |
| [PART2_PYROSETTA](PART2_PYROSETTA.md) | **Part 2**：PyRosetta 静态物理分析（界面能量、Relax） |
| [PART3_MD](PART3_MD.md) | **Part 3**：MD 计算（MM/GBSA、RMSD） |
| [PART3_使用与续跑说明](PART3_使用与续跑说明.md) | **Part 3**：统一入口、续跑、故障排查与测试 |
| [README_THREE_STAGE](README_THREE_STAGE.md) | **三阶段流程**：Stage 1 评分筛选 → Stage 2 Foldseek 粗聚类 → Stage 3 精细聚类 |
| [RESUME_FROM_STAGE_GUIDE](RESUME_FROM_STAGE_GUIDE.md) | 断点续跑：从指定阶段继续运行 |
| [TWO_STAGE_FILTERING](TWO_STAGE_FILTERING.md) | 两阶段筛选策略与示例 |
| [METRICS_COMPUTATION_SEPARATION](METRICS_COMPUTATION_SEPARATION.md) | 指标计算与筛选分离架构 |

---

## 二、快速开始

| 文档 | 说明 |
|------|------|
| [主 README](../README.md) | 项目主文档、安装与使用概览 |
| [ENVIRONMENT_SETUP](ENVIRONMENT_SETUP.md) | 环境设置指南 |
| [INSTALLATION_METHODS](INSTALLATION_METHODS.md) | 安装方式说明 |
| [INSTALLATION_TROUBLESHOOTING](INSTALLATION_TROUBLESHOOTING.md) | 安装问题排查 |
| [AF3_ENVIRONMENT_COMPATIBILITY](AF3_ENVIRONMENT_COMPATIBILITY.md) | 在 AlphaFold3 环境中使用 |
| [environments/](environments/README.md) | Conda、PF 环境检查等（子目录） |

---

## 三、功能与指标

| 文档 | 说明 |
|------|------|
| [API](API.md) | API 参考（ProteinFilter、Design、FilterConfig 等） |
| [A2BINDER_GUIDE](A2BINDER_GUIDE.md) | A2binder 亲和力预测集成与使用 |
| [PDOCKQ_MODULE_ADDED](PDOCKQ_MODULE_ADDED.md) | pDockQ 系列指标说明 |
| [PDOCKQ2_LIS_DEPENDENCIES](PDOCKQ2_LIS_DEPENDENCIES.md) | pDockQ2、LIS 依赖与用法 |
| [CIF_SUPPORT](CIF_SUPPORT.md) | mmCIF 支持说明 |
| [CLUSTERING_FILTER](CLUSTERING_FILTER.md) | 聚类筛选功能 |
| [CLUSTER_FILENAME_GUIDE](CLUSTER_FILENAME_GUIDE.md) | 聚类结果文件名约定 |
| [HOW_TO_READ_PARQUET](HOW_TO_READ_PARQUET.md) | 如何读取 Parquet 指标输出 |

### ipSAE 相关

| 文档 | 说明 |
|------|------|
| [IPSAE_INTEGRATION](IPSAE_INTEGRATION.md) | ipSAE 集成说明 |
| [IPSAE_METRICS_GUIDE](IPSAE_METRICS_GUIDE.md) | ipSAE 指标说明 |
| [IPSAE_PARAMETERS](IPSAE_PARAMETERS.md) | ipSAE 参数 |
| [IPSAE_METRICS_COMPARISON](IPSAE_METRICS_COMPARISON.md) | ipSAE 与其它指标对比 |
| [IPSAE_CALCULATION_ANALYSIS](IPSAE_CALCULATION_ANALYSIS.md) | ipSAE 计算分析 |
| [IPSAE_CODE_COMPARISON](IPSAE_CODE_COMPARISON.md) | ipSAE 代码对比 |
| [IPSAE_SCRIPT_ANALYSIS](IPSAE_SCRIPT_ANALYSIS.md) | ipSAE 脚本分析 |

---

## 四、Foldseek 与聚类

| 文档 | 说明 |
|------|------|
| [FOLDSEEK_AND_FINE_CLUSTERING](FOLDSEEK_AND_FINE_CLUSTERING.md) | Foldseek 与精细聚类 |
| [Foldseek集成优化指南](Foldseek集成优化指南.md) | Foldseek 集成与优化 |
| [Foldseek_CIF优化说明](Foldseek_CIF优化说明.md) | Foldseek CIF 优化 |
| [Foldseek优化方案](Foldseek优化方案.md) | Foldseek 优化方案 |
| [FOLDSEEK_VS_OUR_SCRIPT](FOLDSEEK_VS_OUR_SCRIPT.md) | Foldseek 与自研脚本对比 |
| [STAGE1_CLUSTERING_OPTIMIZATION](STAGE1_CLUSTERING_OPTIMIZATION.md) | Stage 1 聚类优化 |
| [STAGE1_RELAXED_THRESHOLDS](STAGE1_RELAXED_THRESHOLDS.md) | Stage 1 宽松阈值说明 |

---

## 五、PyRosetta

| 文档 | 说明 |
|------|------|
| [PART2_PYROSETTA](PART2_PYROSETTA.md) | Part 2 脚本用法与 germinal/PPIFlow 整合 |
| [pyrosetta/](pyrosetta/README.md) | PyRosetta 配置、检查、Germinal 分析等（子目录） |

---

## 六、脚本与运行

| 文档 | 说明 |
|------|------|
| [scripts/README](../scripts/README.md) | 脚本快速开始（项目 `scripts/`） |
| [scripts/](scripts/README.md) | Stage 2 等脚本详细说明（本目录 `docs/scripts/`） |
| [分析任务监控指南](分析任务监控指南.md) | 分析任务监控与日志 |

---

## 七、开发与架构

| 文档 | 说明 |
|------|------|
| [ARCHITECTURE](ARCHITECTURE.md) | 系统架构 |
| [DEVELOPMENT](DEVELOPMENT.md) | 开发说明（提取、迁移、扩展） |
| [JSON_FILE_DETECTION](JSON_FILE_DETECTION.md) | AF3 JSON 检测与解析 |
| [内存优化修复说明](内存优化修复说明.md) | 内存优化与修复记录 |
| [文档整理说明](文档整理说明.md) | 文档结构与分类说明 |

---

## 按场景导航

| 场景 | 建议阅读 |
|------|----------|
| **新手入门** | [主 README](../README.md) → [ENVIRONMENT_SETUP](ENVIRONMENT_SETUP.md) → [API](API.md) |
| **跑通三阶段流程** | [PIPELINE_OVERVIEW](PIPELINE_OVERVIEW.md) → [README_THREE_STAGE](README_THREE_STAGE.md) → [RESUME_FROM_STAGE_GUIDE](RESUME_FROM_STAGE_GUIDE.md) |
| **做 PyRosetta 界面分析** | [PART2_PYROSETTA](PART2_PYROSETTA.md) → [pyrosetta/](pyrosetta/README.md) |
| **理解指标与筛选** | [METRICS_COMPUTATION_SEPARATION](METRICS_COMPUTATION_SEPARATION.md) → [TWO_STAGE_FILTERING](TWO_STAGE_FILTERING.md) → [IPSAE_INTEGRATION](IPSAE_INTEGRATION.md) |
| **配置环境 / 排错** | [ENVIRONMENT_SETUP](ENVIRONMENT_SETUP.md) → [AF3_ENVIRONMENT_COMPATIBILITY](AF3_ENVIRONMENT_COMPATIBILITY.md) → [environments/](environments/README.md) → [INSTALLATION_TROUBLESHOOTING](INSTALLATION_TROUBLESHOOTING.md) |
| **参与开发** | [ARCHITECTURE](ARCHITECTURE.md) → [DEVELOPMENT](DEVELOPMENT.md) |

---

**历史与归档**：已废弃的 Part3 入口脚本见根目录 [archive/scripts/](../archive/scripts/)；一次性状态/总结类说明见本目录 [archive/](archive/)。

*文档随项目持续更新，如有问题或建议欢迎反馈。*
