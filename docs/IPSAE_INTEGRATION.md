# IPSAE 集成说明

## 概述

IPSAE (Scoring function for interprotein interactions in AlphaFold2 and AlphaFold3) 已集成到 protein_filter_lib 中。

IPSAE 改进了 AlphaFold 的 ipTM 分数，专注于高置信度的界面区域，避免无序或非相互作用部分的干扰，从而更准确地评估复杂或全长蛋白质输入中的相互作用。

## 安装

IPSAE 不是 pip 包，需要从 GitHub 下载脚本：

```bash
# 下载 ipsae.py 脚本
wget https://raw.githubusercontent.com/DunbrackLab/IPSAE/main/ipsae.py

# 或使用 curl
curl -O https://raw.githubusercontent.com/DunbrackLab/IPSAE/main/ipsae.py

# 推荐：将脚本放在 scripts/ 目录（与项目其他脚本一起）
mv ipsae.py scripts/

# 或者放在项目根目录
# mv ipsae.py ./
```

**推荐位置**：
- ✅ `scripts/ipsae.py` - **推荐**（与项目其他脚本一起管理）
- ✅ 项目根目录 `ipsae.py`
- ✅ `tools/ipsae.py` 或 `external/ipsae.py`（如果创建了这些目录）

**不推荐**：
- ❌ `src/utils/` - 这是库的源代码目录，不应包含外部脚本

**依赖**：
```bash
pip install numpy
```

## 使用方法

### 基本使用

```python
from protein_filter import ProteinFilter, FilterConfig, Design

config = FilterConfig(
    metrics=FilterConfig.MetricConfig(
        enabled=["ipsae", "plddt", "iptm"]  # 启用 IPSAE
    ),
    filters={
        "ipsae": {"threshold": 0.5, "operator": ">="}  # 设置 IPSAE 阈值
    }
)

filter_system = ProteinFilter(config)

design = Design(
    sequence="MKLLVL...",
    pdb_path="af3_output/design_001.pdb",
    target_chain="A",
    binder_chain="B",
    # prediction_metrics 会自动提取，包含 PAE 矩阵
)

result = filter_system.filter(design)
print(f"IPSAE score: {result.metrics.get('ipsae')}")
```

### 要求

IPSAE 计算需要：
1. **PAE 矩阵**：从 AlphaFold3 的 JSON 输出中自动提取
2. **结构文件**：PDB 或 CIF 格式
3. **链信息**：目标链和结合子链标识

## 实现说明

### 当前实现状态

IPSAE 计算器已完整实现：
- ✅ `IPSAECalculator` 类已创建
- ✅ `ipsae_utils.py` 工具函数已实现
- ✅ 已集成到 `MetricAggregator`
- ✅ 已添加到 `__init__.py` 导出
- ✅ **完整实现**：通过调用 `ipsae.py` 脚本计算 IPSAE

### 实现方式

IPSAE 通过调用 GitHub 仓库中的 `ipsae.py` 脚本实现：

1. **自动查找脚本**：系统会在以下位置查找 `ipsae.py`：
   - 项目根目录
   - `utils/` 目录
   - `scripts/` 目录
   - 用户主目录的 `.local/bin/`

2. **调用方式**：
   ```python
   python ipsae.py <json_file> <pdb_file> <pae_cutoff> <dist_cutoff>
   ```

3. **输出解析**：自动解析脚本输出，提取以下指标：
   - `ipsae`: IPSAE 分数
   - `ipsae_d0chn`: IPSAE (d0 = chain lengths)
   - `ipsae_d0dom`: IPSAE (d0 = domain residues)
   - `ipsae_iptm_af`: AlphaFold ipTM
   - `ipsae_pdockq`: pDockQ 分数
   - `ipsae_pdockq2`: pDockQ2 分数
   - `ipsae_lis`: Local Interaction Score

## 配置选项

### 距离截断值

可以通过修改 `IPSAECalculator` 的初始化参数调整距离截断值：

```python
# 在 aggregator.py 中
if "ipsae" in config.enabled:
    distance_cutoff = getattr(config, 'ipsae_distance_cutoff', 5.0)
    self.calculators.append(IPSAECalculator(distance_cutoff=distance_cutoff))
```

或在 `MetricConfig` 中添加配置：

```python
@dataclass
class MetricConfig:
    # ... 其他配置 ...
    ipsae_distance_cutoff: float = 5.0  # IPSAE 距离截断值（Å）
```

## 输出指标

- **`ipsae`**: IPSAE 评分（数值范围取决于 ipsae 包实现，通常越高越好）

## 与其他指标的关系

IPSAE 与以下指标相关：
- **`external_iptm`**: AlphaFold 的原始 ipTM 分数
- **`pdockq2`**: 基于 PAE 的 pDockQ2 分数
- **`i_pae`**: 界面平均 PAE

IPSAE 的优势在于它专注于高置信度的界面区域，对于包含无序区域或非相互作用附属结构域的蛋白质，评估更准确。

## 故障排除

### 问题 1: ipsae.py 脚本未找到

**错误信息**：`ipsae.py script not found`

**解决方案**：
```bash
# 下载 ipsae.py 脚本
wget https://raw.githubusercontent.com/DunbrackLab/IPSAE/main/ipsae.py

# 或手动指定脚本路径
config = FilterConfig(
    metrics=FilterConfig.MetricConfig(
        enabled=["ipsae"],
        ipsae_script_path="/path/to/ipsae.py"  # 手动指定路径
    )
)
```

### 问题 2: PAE 矩阵缺失

**错误信息**：`IPSAE calculation requires PAE matrix`

**解决方案**：
- 确保 AF3 预测结果包含 JSON 文件（`*_scores.json`）
- 库会自动从 JSON 提取 PAE 矩阵
- 如果自动提取失败，可以手动提供 `prediction_metrics`

### 问题 3: 脚本执行错误

**错误信息**：`Error running ipsae.py: ...`

**解决方案**：
- 检查 Python 环境是否正确
- 确保 `numpy` 已安装：`pip install numpy`
- 检查 JSON 和 PDB 文件路径是否正确
- 查看脚本输出的错误信息

## 参考

- IPSAE GitHub 仓库：https://github.com/DunbrackLab/IPSAE/
- IPSAE 脚本下载：https://raw.githubusercontent.com/DunbrackLab/IPSAE/main/ipsae.py
- IPSAE 论文/文档：https://levitate.bio/fixing-the-flaws-in-alphafolds-interface-scoring-meet-dunbracks-ipsae/

## 使用示例

### 完整示例

```python
from protein_filter import ProteinFilter, FilterConfig, Design

# 配置 IPSAE（会自动查找 ipsae.py 脚本）
config = FilterConfig(
    metrics=FilterConfig.MetricConfig(
        enabled=["ipsae", "plddt", "iptm", "pdockq"]
    ),
    filters={
        "ipsae": {"threshold": 0.5, "operator": ">="},
        "external_plddt": {"threshold": 0.7, "operator": ">="},
    }
)

filter_system = ProteinFilter(config)

# 创建设计（会自动提取 PAE 矩阵）
design = Design(
    sequence="MKLLVL...",
    pdb_path="af3_output/design_001.pdb",
    target_chain="A",
    binder_chain="B",
    # prediction_metrics 会自动从 AF3 JSON 提取
)

# 过滤
result = filter_system.filter(design)

# 查看 IPSAE 相关指标
print(f"IPSAE: {result.metrics.get('ipsae')}")
print(f"IPSAE (d0chn): {result.metrics.get('ipsae_d0chn')}")
print(f"IPSAE (d0dom): {result.metrics.get('ipsae_d0dom')}")
print(f"ipTM (AF): {result.metrics.get('ipsae_iptm_af')}")
```

## 下一步

1. ✅ 下载 `ipsae.py` 脚本到项目目录
2. ✅ 使用实际数据测试集成
3. ✅ 根据需要调整 PAE 和距离截断值
