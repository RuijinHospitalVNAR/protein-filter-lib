"""
重试机制：对瞬时失败（子进程超时、I/O、网络）进行有限次重试与退避。

仅用于 I/O、子进程等瞬时失败；KeyboardInterrupt、SystemExit 等 BaseException
非 Exception 子类，不会被重试。exceptions 建议仅传入 Exception 子类
（如 OSError、subprocess.CalledProcessError），避免重试不可恢复错误。
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Callable, TypeVar, Tuple, Type

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)
T = TypeVar("T")


def retry(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """
    装饰器：失败时重试，间隔 delay_seconds * (backoff ** attempt)。

    Args:
        max_attempts: 最大尝试次数（含首次）。
        delay_seconds: 首次重试前等待秒数。
        backoff: 每次重试间隔乘数。
        exceptions: 捕获这些异常并重试；其它异常（含 KeyboardInterrupt）直接抛出。
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            wait = delay_seconds
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt == max_attempts:
                        logger.warning(
                            "Retry exhausted after %d attempts for %s: %s",
                            max_attempts, func.__name__, e,
                        )
                        raise
                    logger.info(
                        "Attempt %d/%d failed for %s: %s; retry in %.1fs",
                        attempt, max_attempts, func.__name__, e, wait,
                    )
                    time.sleep(wait)
                    wait *= backoff
            raise last_exc  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator


def with_retry(
    func: Callable[[], T],
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> T:
    """
    对无参可调用对象执行重试（非装饰器用法）。
    仅重试 exceptions 中的异常；KeyboardInterrupt/SystemExit 不会重试。

    Example:
        result = with_retry(lambda: subprocess.run(...), max_attempts=2)
    """
    last_exc = None
    wait = delay_seconds
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except exceptions as e:
            last_exc = e
            if attempt == max_attempts:
                raise
            logger.info("Attempt %d/%d failed: %s; retry in %.1fs", attempt, max_attempts, e, wait)
            time.sleep(wait)
            wait *= backoff
    raise last_exc  # type: ignore[misc]
