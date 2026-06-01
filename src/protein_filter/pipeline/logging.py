"""
统一日志：按配置设置 level、控制台与可选的按 Part 输出到文件。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

# 默认格式
DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    log_format: str = DEFAULT_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
) -> None:
    """
    配置根 logger：控制台 + 可选文件。

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)。
        log_file: 若提供，同时写入该文件（追加）。
        log_format: 格式串。
        date_format: 时间格式。
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(log_format, datefmt=date_format)

    # 控制台
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(formatter)
        root.addHandler(console)

    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """返回已配置的 logger（在 setup_logging 之后使用）。"""
    return logging.getLogger(name)
