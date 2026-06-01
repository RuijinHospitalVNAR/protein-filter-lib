# 架构设计说明

## 为什么需要多层设计？

本库采用多层架构设计，主要基于以下原则：

### 1. **关注点分离（Separation of Concerns）**

不同层次的代码负责不同的职责：

```
src/protein_filter/
├── core.py              # 核心业务流程编排
├── config.py            # 配置管理
├── design.py            # 数据结构定义
├── interfaces.py        # 抽象接口定义
├── implementations/     # 具体实现（可替换）
│   └── relaxers.py
├── metrics/             # 指标计算（独立模块）
│   ├── calculators.py   # 各种指标计算器
│   └── aggregator.py    # 指标聚合器
└── utils/               # 工具函数（可复用）
    ├── pdb_utils.py
    ├── pdockq_utils.py
    └── af3_utils.py
```

**好处**：
- 每个模块职责单一，易于理解
- 修改一个模块不影响其他模块
- 代码组织清晰，便于维护

### 2. **接口抽象（Interface Abstraction）**

通过 `interfaces.py` 定义抽象接口，`implementations/` 提供具体实现：

```python
# interfaces.py - 定义接口
class StructureRelaxer(ABC):
    @abstractmethod
    def relax(self, pdb_path: str, ...) -> str:
        pass

# implementations/relaxers.py - 具体实现
class PyRosettaRelaxer(StructureRelaxer):
    def relax(self, pdb_path: str, ...) -> str:
        # PyRosetta 实现
        pass

class NoOpRelaxer(StructureRelaxer):
    def relax(self, pdb_path: str, ...) -> str:
        # 跳过松弛的实现
        return pdb_path
```

**好处**：
- **可替换性**：可以轻松替换实现（如从 PyRosetta 切换到其他工具）
- **可测试性**：可以创建 Mock 实现进行单元测试
- **灵活性**：支持多种实现方式（如 `NoOpRelaxer` 跳过松弛）

### 3. **易于扩展（Extensibility）**

添加新功能只需在对应层次添加代码：

**添加新的指标计算器**：
```python
# metrics/calculators.py
class NewMetricCalculator(MetricCalculator):
    def calculate(self, pdb_path: str, design: Design) -> Dict[str, Any]:
        # 新指标的计算逻辑
        return {"new_metric": value}
    
    def get_metric_names(self) -> List[str]:
        return ["new_metric"]

# metrics/aggregator.py - 自动集成
if "new_metric" in config.enabled:
    self.calculators.append(NewMetricCalculator())
```

**添加新的松弛器**：
```python
# implementations/relaxers.py
class NewRelaxer(StructureRelaxer):
    def relax(self, pdb_path: str, ...) -> str:
        # 新的松弛实现
        pass

# implementations/__init__.py
def get_relaxer(config):
    if config.name == "new_relaxer":
        return NewRelaxer(config)
    # ...
```

**好处**：
- 不需要修改核心代码（`core.py`）
- 新功能独立，不影响现有功能
- 符合开闭原则（对扩展开放，对修改关闭）

### 4. **代码复用（Code Reuse）**

工具函数放在 `utils/` 中，可以被多个模块复用：

```python
# utils/pdb_utils.py - 被多个计算器使用
def get_sequence_from_pdb(pdb_path: str) -> str:
    # 从 PDB 提取序列
    pass

# metrics/calculators.py - ClashCalculator 使用
from ..utils import get_sequence_from_pdb

# metrics/a2binder_calculator.py - A2binderCalculator 使用
from ..utils import get_sequence_from_pdb
```

**好处**：
- 避免代码重复
- 统一的功能实现
- 修改一处，所有使用的地方都更新

### 5. **可维护性（Maintainability）**

清晰的层次结构使代码易于维护：

- **定位问题**：知道问题在哪个层次，快速定位
- **修改影响**：修改某个层次，影响范围明确
- **代码审查**：审查时按层次进行，更高效

### 6. **可测试性（Testability）**

每个层次可以独立测试：

```python
# 测试工具函数
def test_get_sequence_from_pdb():
    seq = get_sequence_from_pdb("test.pdb")
    assert len(seq) > 0

# 测试指标计算器
def test_clash_calculator():
    calculator = ClashCalculator()
    metrics = calculator.calculate("test.pdb", design)
    assert "clashes" in metrics

# 测试核心流程
def test_protein_filter():
    filter_system = ProteinFilter(config)
    result = filter_system.filter(design)
    assert isinstance(result, FilterResult)
```

## 架构层次说明

### 顶层（API 层）
- `__init__.py`: 导出用户使用的 API
- `core.py`: 核心业务流程
- `config.py`: 配置管理
- `design.py`: 数据结构

### 接口层
- `interfaces.py`: 定义抽象接口

### 实现层
- `implementations/`: 具体实现（可替换）

### 功能层
- `metrics/`: 指标计算模块
- `utils/`: 工具函数模块

## 设计模式

本架构使用了以下设计模式：

1. **策略模式（Strategy Pattern）**
   - `StructureRelaxer` 接口 + 多种实现（PyRosettaRelaxer, NoOpRelaxer）
   - `MetricCalculator` 接口 + 多种计算器

2. **工厂模式（Factory Pattern）**
   - `get_relaxer()` 根据配置创建对应的松弛器

3. **聚合器模式（Aggregator Pattern）**
   - `MetricAggregator` 聚合多个计算器的结果

## 总结

多层设计虽然看起来复杂，但带来了：

- ✅ **清晰的职责划分**
- ✅ **易于扩展和维护**
- ✅ **代码复用和测试友好**
- ✅ **符合软件工程最佳实践**

对于一个小型库，这种设计可能看起来"过度设计"，但对于一个需要支持 30+ 指标、多种实现方式、持续扩展的库来说，这种设计是必要的。
