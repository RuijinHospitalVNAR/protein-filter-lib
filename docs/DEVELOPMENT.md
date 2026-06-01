# 开发文档

本文档记录从 Germinal 项目提取代码和迁移的详细信息。

## 项目状态

### ✅ 已完成的功能

#### 1. 工具函数模块 (`utils/pdb_utils.py`)

从 `germinal/utils/utils.py` 提取：
- ✅ `get_sequence_from_pdb()` - 从 PDB 提取序列
- ✅ `clean_pdb()` - 清理 PDB 文件
- ✅ `calculate_clash_score()` - 碰撞检测（使用 cKDTree）
- ✅ `hotspot_residues()` - 热点残基识别

#### 2. 指标计算器

**ClashCalculator** (`metrics/calculators.py`)
- ✅ 使用 `scipy.spatial.cKDTree` 高效查找碰撞
- ✅ 支持全原子和 CA-only 两种模式
- ✅ 返回 `clashes` 和 `clashes_ca` 两个指标

**InterfaceCalculator** (`metrics/calculators.py`)
- ✅ 完整的界面分析（InterfaceAnalyzerMover）
- ✅ 界面残基识别
- ✅ 界面氨基酸组成统计
- ✅ 疏水性计算（界面和表面）
- ✅ 形状互补性（SC）计算
- ✅ Loop 形状互补性计算
- ✅ 氢键统计（包括未饱和氢键）
- ✅ 返回 16 个界面指标

**SAPCalculator** (`metrics/calculators.py`)
- ✅ SAP 评分计算
- ✅ CDR SAP 计算
- ✅ 疏水斑块检测

**SecondaryStructureCalculator** (`metrics/calculators.py`)
- ✅ 二级结构百分比计算
- ✅ 界面二级结构分析

**PDockQCalculator** (`metrics/calculators.py`)
- ✅ pDockQ 计算
- ✅ pDockQ2 计算（需要 PAE 矩阵）
- ✅ LIS 系列指标计算

**A2binderCalculator** (`metrics/a2binder_calculator.py`)
- ✅ A2binder 亲和力预测
- ✅ 支持 nanobody 专用模型

#### 3. 结构松弛器

**PyRosettaRelaxer** (`implementations/relaxers.py`)
- ✅ FastRelax 实现
- ✅ 链对齐
- ✅ B-factor 保留

#### 4. 工具模块

**pDockQ 工具** (`utils/pdockq_utils.py`)
- ✅ pDockQ 计算函数
- ✅ pDockQ2 计算函数
- ✅ LIS 计算函数

**AF3 工具** (`utils/af3_utils.py`)
- ✅ 从 AF3 JSON 提取指标
- ✅ 从 PDB 提取 pLDDT
- ✅ 自动提取功能

### ⚠️ 已移除的功能

- **结构预测器**: 已移除，结构预测由外部脚本完成
- **AF3Predictor**: 已删除（仅保留占位符代码，不再使用）
- **ChaiPredictor**: 已删除（仅保留占位符代码，不再使用）

## 代码提取说明

### 提取流程

1. **识别需要提取的函数**: 查找所有 TODO 和 warning
2. **在 Germinal 中找到对应实现**: 定位原始实现代码
3. **提取并适配代码**: 移除 Germinal 特定依赖，适配新框架
4. **测试和验证**: 确保功能正常

### 提取来源

| 功能 | 来源文件 | 状态 |
|------|---------|------|
| 碰撞检测 | `germinal/utils/utils.py:calculate_clash_score()` | ✅ 完成 |
| 界面分析 | `germinal/filters/pyrosetta_utils.py:score_interface()` | ✅ 完成 |
| 结构松弛 | `germinal/filters/pyrosetta_utils.py:pr_relax()` | ✅ 完成 |
| SAP 评分 | `germinal/filters/pyrosetta_utils.py:get_sap_score()` | ✅ 完成 |
| pDockQ | `germinal/filters/pDockQ.py` | ✅ 完成 |
| 二级结构 | `germinal/utils/utils.py:calc_ss_percentage()` | ✅ 完成 |

## 架构变更

### 主要变更

1. **移除结构预测**: 库现在专注于分析和过滤，不包含预测功能
2. **自动提取指标**: 支持从 AF3 输出自动提取预测指标
3. **两阶段筛选**: 支持快速筛选 + 详细分析的两阶段流程

### 接口设计

- **清晰的抽象**: 使用接口定义（`StructureRelaxer`, `MetricCalculator`）
- **配置驱动**: 通过 `FilterConfig` 统一管理配置
- **易于扩展**: 添加新指标计算器只需实现接口

## 代码统计

- **总代码行数**: ~3000+ 行
- **指标计算器**: 8 个
- **支持指标**: 30+ 个
- **工具函数**: 10+ 个

## 参考

- 原始项目: Germinal
- 代码提取说明: 见各模块的代码注释
