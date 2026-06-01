# protein_filter_lib 代码评审报告

基于 **code-review-expert** 技能对仓库进行的结构化评审（SOLID、架构、安全与代码质量）。  
*说明：algorithmic-art、brand-guidelines 适用于生成艺术与品牌视觉物料，本仓库为蛋白质设计过滤库，未涉及相关场景，本次未引用。*

---

## Code Review Summary

**评审范围**：当前工作区变更 + 核心活跃代码（`src/protein_filter/`、`scripts/`、`config/`、`AMBER_MMPBSA/`）；排除 `.cursor/skills/` 与 `archive/` 内第三方/历史脚本。  
**涉及文件**：约 40+ 活跃 Python/Shell/YAML 文件，核心库约 38 个 Python 模块。  
**Overall assessment**: **APPROVE**（P1/P2 项已按本报告完成修复，见下方「修复记录」）

---

## Findings

### P0 - Critical

（无）

- 未发现硬编码密钥、SQL/命令注入、SSRF 等可直接利用的安全漏洞。
- `subprocess` 调用均使用列表参数且未使用 `shell=True`（活跃脚本），命令注入风险低。
- **注意**：`archive/` 内部分脚本含 `eval(input(...))`、`exec(...)`、`shell=True`，仅作历史保留时建议在文档中标注「勿对不可信输入运行」。

### P1 - High

1. **scripts/part1/part1_analyze_af3_three_stage.py:1316** 裸 `except: pass`  
   - 创建 `latest_log` 符号链接时吞掉所有异常，在无权限或非 Unix 环境下会静默失败，不利于排障。  
   - **建议**：改为 `except OSError as e:` 并至少 `logger.warning("无法创建 latest 日志链接: %s", e)`，必要时在非 Linux 上跳过 symlink 或改用复制。

2. **错误处理过于宽泛导致静默失败**（多处）  
   - `src/protein_filter/core.py:112`、`pipeline/base.py:374`、各 CLI 入口等使用 `except Exception` 后返回失败结果或退出码，但不记录 traceback，调试困难。  
   - **建议**：在关键路径（如 pipeline stage、CLI main）使用 `logger.exception(...)` 或在开发/调试模式下 `raise`，便于定位逻辑错误与环境问题。

3. **入口与文档不一致风险**  
   - README 以 `run_denovo_design.sh` / `run_optimization_pipeline.sh` 为主入口，CLEANUP_SUMMARY 以 `analyze_af3_three_stage.py`、`run_full_pipeline.sh`、`run_part3.py` 等为主；两处描述一致但侧重点不同，新用户可能混淆「先跑哪个」。  
   - **建议**：在 README Quickstart 增加一句「完整入口与各 Part 对应关系见 docs/CLEANUP_SUMMARY.md」，并在 CLEANUP 开头注明「与 README Quickstart 一致，此处为脚本级清单」。

### P2 - Medium

4. **src/protein_filter/pipeline/stages.py:709–711** 复制失败被静默忽略  
   - `shutil.copy2` 失败时 `except Exception: pass`，可能掩盖磁盘满、权限等问题。  
   - **建议**：至少记录 `self._logger.warning("复制失败，已跳过 %s -> %s: %s", src, dst, e)`，或对关键文件重新抛出。

5. **scripts/utils/load_config_env.py 与 `eval` 配合使用**  
   - 文档建议 `eval "$(python3 scripts/utils/load_config_env.py)"`，若 YAML 或环境变量被篡改，可能向 shell 注入恶意内容；当前有 `_bash_escape` 缓解。  
   - **建议**：在脚本注释或 docs 中说明「仅加载可信配置；勿对不可信 YAML 或 env 使用 eval 方式」。

6. **Part3 脚本中 CUDA_VISIBLE_DEVICES 解析**（part3_run_amber_md_mmgbsa_rmsd.py:402–405）  
   - 使用 `except Exception` 后设 `visible_count = 1`，实际可能仅需处理 `ValueError` 或解析错误。  
   - **建议**：捕获更具体异常类型，避免掩盖其他错误。

7. **重试装饰器默认捕获 Exception**（src/protein_filter/pipeline/retry.py）  
   - `exceptions=(Exception,)` 会重试包括 `KeyboardInterrupt`、`SystemExit` 在内的所有异常（若被上层捕获）。  
   - **建议**：默认排除 `BaseException` 子类中的非可重试类型，或在文档中明确「仅用于 I/O/子进程等瞬时失败」。

### P3 - Low

8. **类型注解与兼容性**  
   - 部分脚本仍用 `list`/`dict` 而非 `List`/`Dict`（或 3.9+ 内置），若需支持 3.8 或统一风格，可逐步补充/统一。

9. **日志级别使用**  
   - 个别处用 `logger.info` 记录本应为 `debug` 的详细步骤，在高负载或生产日志中可能噪音较多，可按需调整为 `logger.debug`。

10. **archive 与第三方脚本**  
    - `archive/YZC_MD_SCRIPT`、`archive/2STEP` 等存在大量裸 `except:` 或 `except Exception`，属历史代码；若未来不再使用，可考虑进一步归档或标注「不维护」，避免被误用。

---

## Removal/Iteration Plan

| 类别 | 建议 | 优先级 |
|------|------|--------|
| **可安全删除** | 无；当前未发现明确未使用且无引用的活跃代码块。 | - |
| **建议收敛** | `archive/` 下脚本若确认不再被任何文档或入口引用，可在 CLEANUP 中列为「仅历史参考」，并避免在 README 中指向。 | 低 |
| **后续迭代** | （1）为 Part1/Part2/Part3 主入口增加集成/冒烟测试；（2）将「仅环境变量 + YAML」的配置方式逐步与 `pipeline/config.py` 等统一，减少两套配置来源。 | 中 |

---

## 架构与 SOLID 简评

- **SRP**：`ProteinFilter`、各 Stage、MetricCalculator/StructureRelaxer 接口职责清晰；Part1 大脚本 `part1_analyze_af3_three_stage.py` 体积较大，后续可考虑拆分为「配置 + 编排 + 各阶段小模块」以更好满足 SRP。  
- **OCP/扩展点**：通过 `interfaces.py` 的抽象与 `get_relaxer`、metric 注册方式扩展实现，扩展性良好。  
- **DIP**：核心依赖抽象（Relaxer、MetricCalculator），符合依赖倒置。  
- **安全与可靠性**：无密钥泄露；subprocess 用法安全；主要风险在异常被过度捕获导致静默失败与可观测性不足。

---

## Additional Suggestions

1. **测试**：为 `src/protein_filter` 核心路径（filter、pipeline、metrics）增加单元测试或小规模集成测试，便于重构与回归。  
2. **文档**：在 README 或 PIPELINE_OVERVIEW 中增加一页「故障排查」（如：Part1 无输出、Part3 GPU 不可见、YAML 覆盖规则），与当前日志与异常处理改进配合。  
3. **配置**：`load_config_env.py` 与 YAML 的键与 `config/` 下 schema 若能在文档或代码中统一列举，可减少配置错误。

---

## 修复记录（已全部落实）

| 编号 | 修改内容 |
|------|----------|
| P1-1 | `part1_analyze_af3_three_stage.py`：裸 `except` 改为 `except OSError as e` + `logger.warning` |
| P1-2 | `core.py`：`logger.error` 改为 `logger.exception`；pipeline/base 已有 `log_error(..., exc_info=True)`；CLI 已使用 `logging.exception` |
| P1-3 | README Quickstart 增加对 CLEANUP_SUMMARY 的引用；CLEANUP 开头注明「与 README Quickstart 一致，此处为脚本级清单」 |
| P2-4 | `stages.py`：`shutil.copy2` 失败时记录 `self._logger.warning`，不再静默忽略 |
| P2-5 | `load_config_env.py`：模块 docstring 增加「仅加载可信配置；勿对不可信 YAML 或环境变量使用 eval 方式」 |
| P2-6 | `part3_run_amber_md_mmgbsa_rmsd.py`：CUDA 解析改为捕获 `(TypeError, AttributeError, ValueError)` |
| P2-7 | `retry.py`：模块与函数 docstring 明确「仅用于 I/O/子进程等瞬时失败」「KeyboardInterrupt/SystemExit 不会重试」 |

---

## Next Steps

本次共标出 **P0: 0，P1: 3，P2: 4，P3: 3**；**P1/P2 已全部修复**。  
P3（类型注解、日志级别、archive 标注）为可选改进，可按需在后续迭代处理。
