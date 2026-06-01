# A2binder 完整指南

## 概述

A2binder 是一个基于 BERT 的抗体-抗原结合亲和力预测模型，来自 PALM 项目。本指南提供 A2binder 在 protein_filter_lib 中的完整使用说明。

## 功能特性

- **亲和力预测**: 使用 A2binder 模型预测抗体-抗原结合亲和力
- **排序支持**: 可作为排序指标，亲和力分数越高表示结合能力越强
- **过滤支持**: 可设置阈值进行过滤
- **灵活配置**: 支持 nanobody/VNAR（无轻链）和传统抗体（有轻链）
- **Nanobody 专用模型**: 支持使用专门在 nanobody 数据上微调的模型

## 快速开始

### 1. 安装要求

1. **PALM 项目**: 需要安装 PALM 项目及其依赖
   ```bash
   cd PALM-main
   pip install -r requirements.txt
   ```

2. **下载模型**: 从 Zenodo 下载 A2binder 模型
   - 访问: https://zenodo.org/records/17090473
   - 下载 nanobody 专用模型（推荐用于 VNAR）
   - 或下载通用模型

3. **ESM2 模型**: 自动从 HuggingFace 下载（首次使用时）

### 2. 基本配置

```python
from protein_filter import ProteinFilter, FilterConfig, Design

config = FilterConfig(
    metrics=FilterConfig.MetricConfig(
        enabled=["a2binder_affinity"],
        a2binder_config={
            "model_path": "/path/to/model_best.pth",
            "heavy_model_dir": "/path/to/Heavy_roformer",
            "light_model_dir": "/path/to/Light_roformer",
            "antibody_tokenizer_dir": "/path/to/Heavy_roformer",
            "device": "cuda",
            "use_light_chain": False,  # False for VNAR/nanobodies
            "nanobody_model": True,  # 如果使用 nanobody 专用模型
        }
    ),
    filters={
        "a2binder_affinity": {"threshold": 0.5, "operator": ">="}
    }
)

filter_system = ProteinFilter(config)
```

### 3. 使用示例

```python
design = Design(
    sequence="MKLLVL...",  # VNAR 序列
    pdb_path="design.pdb",
    target_chain="A",
    binder_chain="B",
    target_sequence=["MKTAY..."],  # 抗原序列
)

result = filter_system.filter(design)
print(f"A2binder affinity: {result.metrics.get('a2binder_affinity')}")
```

## 模型文件说明

### 模型结构

从 Zenodo 下载的模型通常包含：

```
PALM-main/
└── Model/
    ├── model_best.pth                    # 完整的模型检查点（推荐使用）
    └── Model_Zenodo/
        ├── Heavy_roformer/               # 预训练的重链模型（必需）
        │   ├── config.json
        │   ├── pytorch_model.bin
        │   └── tokenizer_config.json
        ├── Light_roformer/               # 预训练的轻链模型（必需）
        │   ├── config.json
        │   └── pytorch_model.bin
        └── A2binder_affinity/            # 分离的模型组件（可选）
            ├── heavymodel/
            ├── lightmodel/
            └── antigenmodel/
```

### 重要说明

⚠️ **关键点**：
- `model_best.pth` **不包含**预训练模型的完整架构，仍需要 HeavyRoformer 和 LightRoformer 目录
- HeavyRoformer 和 LightRoformer **不能**从 HuggingFace 自动下载，必须从 Zenodo 下载
- 预训练模型目录用于初始化模型架构，`model_best.pth` 包含微调后的参数

### 模型参数加载流程

1. **初始化阶段**: 从预训练模型目录加载架构
   - HeavyModel: 从 `heavy_model_dir` 加载
   - LightModel: 从 `light_model_dir` 加载
   - AntigenModel: 从 ESM2 (HuggingFace) 加载

2. **参数加载**: 从 `model_best.pth` 加载微调后的参数

3. **推理**: 使用加载的模型进行亲和力预测

## 配置参数

### 必需参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `model_path` | str | A2binder 模型检查点路径 (.pth 文件) |
| `heavy_model_dir` | str | HeavyRoformer 预训练模型目录 |
| `light_model_dir` | str | LightRoformer 预训练模型目录 |
| `antibody_tokenizer_dir` | str | 抗体 tokenizer 目录（通常与 heavy_model_dir 相同） |

### 可选参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `antibody_vocab_dir` | str | None | 抗体词汇表文件路径 |
| `tokenizer_name` | str | "common" | Tokenizer 名称 |
| `token_length_list` | str | "2,3" | Token 长度列表 |
| `heavy_max_len` | int | 140 | 重链最大长度 |
| `light_max_len` | int | 140 | 轻链最大长度 |
| `antigen_max_len` | int | 300 | 抗原最大长度 |
| `device` | str | "cuda" | 运行设备 ("cuda" 或 "cpu") |
| `use_light_chain` | bool | True | 是否使用轻链（False for nanobodies） |
| `model_type` | str | "BERTBinding_AbDab_cnn" | 模型架构类型 |
| `nanobody_model` | bool | False | 是否使用 nanobody 专用模型 |

## Nanobody/VNAR 专用模型

Zenodo 提供了专门在 nanobody/sdAb 数据上微调的模型，推荐用于 VNAR 设计：

### 优势

- **更好的准确性**: 在 nanobody 数据上微调，预测更准确
- **专门优化**: 针对单域抗体的特点进行了优化
- **无需特殊处理**: 模型已适应无轻链的情况

### 使用方法

```python
config = FilterConfig(
    metrics=FilterConfig.MetricConfig(
        enabled=["a2binder_affinity"],
        a2binder_config={
            "model_path": "/path/to/nanobody_model_best.pth",
            "heavy_model_dir": "/path/to/Heavy_roformer",
            "light_model_dir": "/path/to/Light_roformer",
            "antibody_tokenizer_dir": "/path/to/Heavy_roformer",
            "device": "cuda",
            "use_light_chain": False,  # Nanobody 没有轻链
            "nanobody_model": True,  # 使用 nanobody 专用模型
        }
    )
)
```

## 配置示例

### 示例 1: 使用 model_best.pth（推荐）

```python
from pathlib import Path
from protein_filter import FilterConfig, MetricConfig

PALM_DIR = Path("/path/to/PALM-main")
MODEL_PATH = str(PALM_DIR / "Model" / "model_best.pth")
HEAVY_MODEL_DIR = str(PALM_DIR / "Model" / "Model_Zenodo" / "Heavy_roformer")
LIGHT_MODEL_DIR = str(PALM_DIR / "Model" / "Model_Zenodo" / "Light_roformer")
TOKENIZER_DIR = str(PALM_DIR / "Model" / "Model_Zenodo" / "Heavy_roformer")

config = FilterConfig(
    metrics=MetricConfig(
        enabled=["a2binder_affinity"],
        a2binder_config={
            "model_path": MODEL_PATH,
            "heavy_model_dir": HEAVY_MODEL_DIR,
            "light_model_dir": LIGHT_MODEL_DIR,
            "antibody_tokenizer_dir": TOKENIZER_DIR,
            "device": "cuda",
            "use_light_chain": False,
            "nanobody_model": True,
        }
    )
)
```

### 示例 2: 作为排序指标

```python
# 过滤多个设计并按亲和力排序
designs = [design1, design2, design3, ...]
results = []

for design in designs:
    result = filter_system.filter(design)
    if result.passed:
        affinity = result.metrics.get('a2binder_affinity', 0.0)
        results.append((design.design_name, affinity))

# 按亲和力排序（越高越好）
results.sort(key=lambda x: x[1], reverse=True)

for name, affinity in results:
    print(f"{name}: {affinity:.4f}")
```

## 输出指标

- **`a2binder_affinity`**: 预测的结合亲和力分数（0-1之间，越高越好）

## 路径验证

在使用前，请确认以下文件/目录存在：

- [ ] `Model/model_best.pth` 存在
- [ ] `Model/Model_Zenodo/Heavy_roformer/` 目录存在
- [ ] `Model/Model_Zenodo/Light_roformer/` 目录存在
- [ ] `Model/Model_Zenodo/Heavy_roformer/config.json` 存在
- [ ] `Model/Model_Zenodo/Heavy_roformer/tokenizer_config.json` 存在

## 故障排除

### 问题 1: 模型加载失败

**症状**: 错误信息提示找不到模型文件或路径错误

**解决方案**:
- 检查所有路径是否正确（使用绝对路径更安全）
- 确保 PALM 代码目录在 Python 路径中
- 检查 CUDA 是否可用（如果使用 GPU）
- 查看日志获取详细错误信息

### 问题 2: Tokenizer 错误

**症状**: Tokenizer 初始化失败

**解决方案**:
- 确保 `antibody_tokenizer_dir` 指向正确的目录
- 检查词汇表文件是否存在
- 验证 tokenizer 配置参数

### 问题 3: 序列长度超限

**症状**: 序列长度超过模型限制

**解决方案**:
- 增加 `heavy_max_len`、`light_max_len` 或 `antigen_max_len`
- 或预处理序列，截断过长的序列

### 问题 4: 预训练模型目录错误

**症状**: 模型架构初始化失败

**解决方案**:
- 确保 `heavy_model_dir` 和 `light_model_dir` 指向正确的预训练模型目录
- 检查目录中是否包含 `config.json` 和 `pytorch_model.bin`
- 这些目录不能从 HuggingFace 下载，必须从 Zenodo 获取

## 注意事项

1. **模型路径**: 使用绝对路径更安全，避免相对路径问题

2. **轻链处理**: 
   - 对于 nanobody/VNAR，设置 `use_light_chain=False`
   - **强烈推荐**: 使用 Zenodo 上的 nanobody 专用模型 (`nanobody_model=True`)

3. **序列提取**: 
   - 优先从 PDB 文件提取序列
   - 如果 PDB 中没有，使用 `Design.sequence` 和 `Design.target_sequence`

4. **性能**: 
   - 首次加载模型需要时间（几秒到几十秒）
   - 后续预测会更快（模型会缓存）
   - 建议使用 GPU (`device="cuda"`)

5. **错误处理**: 
   - 如果模型加载失败，会返回亲和力分数 0.0
   - 检查日志以获取详细错误信息

## 参考资源

- **PALM 项目**: https://github.com/TencentAILabHealthcare/PALM
- **A2binder 模型（Zenodo）**: https://zenodo.org/records/17090473
- **ESM2 模型**: https://huggingface.co/facebook/esm2_t30_150M_UR50D

## 完整示例

参见 `examples/a2binder_example.py` 和 `examples/a2binder_nanobody_example.py` 获取完整的使用示例。
