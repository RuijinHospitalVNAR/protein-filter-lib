# PyRosetta 可用性检查报告

**检查时间**: 2026-01-16  
**检查目标**: 验证 PyRosetta 是否可以被 `compute_stage2_metrics.sh` 正常调用

---

## 执行摘要

❌ **PyRosetta 当前不可用**

- PyRosetta 模块未安装
- 需要安装 PyRosetta 才能使用 SAP 和二级结构指标
- `compute_stage2_metrics.sh` 脚本文件不存在（可能已被删除）

---

## 1. PyRosetta 安装状态

### 1.1 模块导入测试

**结果**: ❌ 失败

```
ModuleNotFoundError: No module named 'pyrosetta'
```

**说明**: 
- PyRosetta 未在当前 Python 环境中安装
- 需要单独安装 PyRosetta（需要许可证）

### 1.2 环境信息

- **Python 版本**: 3.13.5
- **Python 路径**: `/home/supervisor/anaconda3/bin/python3`
- **当前环境**: 系统默认环境（未激活特定 conda 环境）

---

## 2. compute_stage2_metrics.sh 脚本状态

### 2.1 文件存在性检查

**结果**: ❌ 文件不存在

脚本文件 `scripts/compute_stage2_metrics.sh` 不存在。

**可能原因**:
- 文件已被删除
- 文件路径不同
- 需要重新创建

### 2.2 相关文件

找到的相关文件：
- ✅ `scripts/filter_stage2.sh` - Stage 2 筛选脚本（存在）
- ✅ `scripts/run_full_pipeline.sh` - 完整流程脚本（引用 compute_stage2_metrics.sh）

---

## 3. 依赖关系分析

### 3.1 PyRosetta 依赖的指标

以下指标**需要 PyRosetta**：

1. **SAP 指标**:
   - `sap_score` - SAP 总分
   - `cdr_sap` - CDR 区域 SAP
   - `hydrophobic_patches_binder` - 疏水斑块数量

2. **二级结构指标**:
   - `alpha_all` - 全部螺旋百分比
   - `beta_all` - 全部折叠百分比
   - `loops_all` - 全部环区百分比
   - `alpha_interface` - 界面螺旋百分比
   - `beta_interface` - 界面折叠百分比
   - `loops_interface` - 界面环区百分比

3. **界面分析指标**（部分）:
   - `interface_dG` - 界面结合自由能
   - `interface_dSASA` - 界面可及表面积变化
   - `interface_packstat` - 界面包装统计
   - 以及其他界面相关指标（共 16 个）

### 3.2 代码中的 PyRosetta 使用

在 `src/protein_filter/metrics/calculators.py` 中：

- **SAPCalculator** (第 365-494 行):
  ```python
  import pyrosetta as pr
  from pyrosetta.rosetta.core.pack.guidance_scoreterms.sap import (
      calculate_per_res_sap
  )
  ```

- **SecondaryStructureCalculator** (第 498-587 行):
  ```python
  import pyrosetta as pr
  from pyrosetta.rosetta.core.scoring.dssp import Dssp
  ```

- **InterfaceCalculator** (第 43-216 行):
  ```python
  import pyrosetta as pr
  from pyrosetta.rosetta.protocols.analysis import InterfaceAnalyzerMover
  ```

---

## 4. 影响分析

### 4.1 如果 PyRosetta 不可用

**Stage 2 指标计算将受到影响**：

1. ✅ **可以计算**（不依赖 PyRosetta）:
   - 所有 Stage 1 指标（pLDDT、clashes、pDockQ 等）
   - A2binder 亲和力预测（如果配置）

2. ❌ **无法计算**（需要 PyRosetta）:
   - SAP 指标（`sap_score`, `cdr_sap`, `hydrophobic_patches_binder`）
   - 二级结构指标（`alpha_all`, `beta_all`, `loops_all` 等）
   - 界面分析指标（`interface_dG`, `interface_dSASA`, `interface_packstat` 等）

### 4.2 错误处理机制

代码中已有错误处理：

```python
try:
    import pyrosetta as pr
    # ... 计算指标 ...
except ImportError:
    logger.warning("PyRosetta not available for SAP calculation")
    return {}
```

**说明**: 
- 如果 PyRosetta 不可用，相关指标会返回空字典
- 不会导致程序崩溃，但指标值会缺失
- 会在日志中记录警告信息

---

## 5. 解决方案

### 5.1 安装 PyRosetta

**步骤**:

1. **获取许可证**:
   - 访问 https://www.pyrosetta.org/
   - 注册并获取学术/商业许可证

2. **下载并安装**:
   ```bash
   # 下载 PyRosetta（根据 Python 版本选择）
   # 例如：PyRosetta-4.x.x.linux.release-xxx.tar.bz2
   
   # 解压
   tar -xjf PyRosetta-*.tar.bz2
   
   # 安装
   cd PyRosetta-*
   python setup.py install
   ```

3. **验证安装**:
   ```bash
   python3 -c "import pyrosetta; pyrosetta.init(); print('PyRosetta installed successfully')"
   ```

### 5.2 使用 conda 环境（推荐）

如果使用 conda 环境，可以在环境中安装：

```bash
# 创建新环境
conda create -n protein-filter-lib python=3.10 -y
conda activate protein-filter-lib

# 安装依赖
pip install numpy scipy biopython pandas

# 安装 PyRosetta（需要先下载）
# ... 按照上述步骤安装 PyRosetta ...

# 安装 protein_filter_lib
cd /data/Tools/protein_filter_lib
pip install --user .
```

### 5.3 禁用需要 PyRosetta 的指标

如果不需要这些指标，可以在配置中禁用：

在 `compute_stage2_metrics.sh` 中设置：
```bash
ENABLE_SAP=false
ENABLE_SECONDARY_STRUCTURE=false
ENABLE_INTERFACE=false  # 如果不需要界面分析
```

---

## 6. 测试脚本


**使用方法**:
```bash
cd /data/Tools/protein_filter_lib
# 测试PyRosetta环境
python -c "import pyrosetta; pyrosetta.init(); print('PyRosetta可用')"
```

**测试内容**:
1. PyRosetta 模块导入
2. PyRosetta 初始化
3. PyRosetta 基本功能（创建 pose、Dssp、SAP）
4. Calculator 类实例化

---

## 7. 建议

### 优先级 1: 必须处理

1. **安装 PyRosetta**（如果需要 SAP 和二级结构指标）
   - 获取许可证
   - 按照官方文档安装
   - 验证安装成功

2. **创建/恢复 compute_stage2_metrics.sh**
   - 如果文件被删除，需要重新创建
   - 参考 `scripts/compute_stage1_metrics.sh` 的结构

### 优先级 2: 建议处理

3. **使用独立 conda 环境**
   - 避免与系统 Python 环境冲突
   - 便于管理依赖

4. **配置错误处理**
   - 确保脚本在 PyRosetta 不可用时能优雅降级
   - 记录清晰的警告信息

---

## 8. 总结

### 当前状态

- ❌ PyRosetta 未安装
- ❌ `compute_stage2_metrics.sh` 文件不存在
- ✅ 代码中有错误处理机制（不会崩溃）
- ✅ 测试脚本已创建

### 下一步行动

1. **如果需要 PyRosetta 功能**:
   - 安装 PyRosetta
   - 验证安装
   - 运行测试脚本确认

2. **如果不需要 PyRosetta 功能**:
   - 在配置中禁用相关指标
   - 使用不依赖 PyRosetta 的指标

3. **恢复脚本**:
   - 重新创建 `compute_stage2_metrics.sh`
   - 或从备份恢复

---

## 附录

### 相关文件

- 代码位置: `src/protein_filter/metrics/calculators.py`
- 配置文件: `scripts/compute_stage2_metrics.sh` (不存在)

### 参考链接

- PyRosetta 官网: https://www.pyrosetta.org/
- PyRosetta 文档: https://www.pyrosetta.org/documentation
- 安装指南: https://www.pyrosetta.org/downloads
