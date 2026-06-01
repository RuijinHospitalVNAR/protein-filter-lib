#!/usr/bin/env python3
"""
从 optimizing YAML 配置加载参数并输出 bash export 语句，供 run_optimization_pipeline.sh 使用。

仅加载可信配置；勿对不可信 YAML 或环境变量使用 eval 方式，以免注入风险。
环境变量（AF3_DIR、TOP_N 等）优先于 YAML 中的值。
用法：
    eval "$(python3 scripts/utils/load_config_env.py)"
    或
    source <(python3 scripts/utils/load_config_env.py)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# YAML key -> env var name
OPTIMIZING_MAP = {
    "af3_dir": "AF3_DIR",
    "example_base": "EXAMPLE_BASE",
    "top_n": "TOP_N",
    "production_ns": "PRODUCTION_NS",
    "ntomp": "NTOMP",
    "postprocess_workers": "POSTPROCESS_WORKERS",
    "mmpbsa_workers": "MMPBSA_WORKERS",
    "skip_mmgbsa": "SKIP_MMGBSA",
    "n_gpu": "N_GPU",
}


def _bash_escape(val: str) -> str:
    """对 bash 单引号内的字符串做转义（单引号替换为 '\''）"""
    return str(val).replace("'", "'\"'\"'")


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    config_path = os.environ.get("CONFIG")
    if not config_path:
        config_path = str(repo_root / "config" / "optimizing_default.yaml")
    config_path = Path(config_path)
    if not config_path.is_absolute():
        config_path = repo_root / config_path

    if not config_path.exists():
        print(f"# 警告: 配置文件不存在 {config_path}，使用环境变量或脚本默认值", file=sys.stderr)
        fallback = {
            "EXAMPLE_BASE": os.environ.get("EXAMPLE_BASE") or str(repo_root / "examples" / "affinity_maturation_example"),
            "AF3_DIR": os.environ.get("AF3_DIR", ""),
            "TOP_N": os.environ.get("TOP_N", "10"),
            "PRODUCTION_NS": os.environ.get("PRODUCTION_NS", "1"),
            "NTOMP": os.environ.get("NTOMP", "8"),
            "POSTPROCESS_WORKERS": os.environ.get("POSTPROCESS_WORKERS", "12"),
            "MMPBSA_WORKERS": os.environ.get("MMPBSA_WORKERS", "12"),
            "SKIP_MMGBSA": os.environ.get("SKIP_MMGBSA", "0"),
        }
        for k, v in fallback.items():
            print(f"export {k}='{_bash_escape(v)}'")
        return 0

    try:
        import yaml
    except ImportError:
        print("# 警告: PyYAML 未安装，跳过 YAML 解析", file=sys.stderr)
        return 1

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    exports = []
    for yaml_key, env_name in OPTIMIZING_MAP.items():
        env_val = os.environ.get(env_name)
        if env_val is not None and env_val != "":
            val = env_val
        else:
            raw = cfg.get(yaml_key)
            if raw is None and yaml_key == "example_base":
                val = str(repo_root / "examples" / "affinity_maturation_example")
            elif raw is not None:
                val = str(raw)
            else:
                continue
        exports.append(f"export {env_name}='{_bash_escape(val)}'")

    for line in exports:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
