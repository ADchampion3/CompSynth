"""CompSynth logging configuration.

Provides a single ``configure()`` entry point that:
1. Sets up loguru sinks (console + app file + error file)
2. Bridges standard library ``logging`` into loguru via InterceptHandler
3. Silences noisy third-party loggers (Crawlee, httpx, Playwright, etc.)

Importing this module performs a default ``configure("INFO")`` so that
callers who never call ``configure()`` explicitly still get working logs.
"""

import logging
import os
import sys
from pathlib import Path

from loguru import logger

from comp_synth import config

# Suppress Crawlee's own INFO logs before it initialises.
# Crawlee reads CRAWLEE_LOG_LEVEL from env; set it early so the default
# INFO level is never used.
os.environ.setdefault("CRAWLEE_LOG_LEVEL", "WARNING")

LOG_DIR = Path(config.LOG_DIR)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# 日志格式定义
# =============================================================================

CONSOLE_FMT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<level>{message}</level>"
)

FILE_FMT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}"

ERROR_FMT = FILE_FMT

# =============================================================================
# 第三方库日志级别映射（统一管控）
# =============================================================================

_THIRD_PARTY_LEVELS: dict[str, int] = {
    "crawlee": logging.WARNING,
    "httpx": logging.WARNING,
    "httpcore": logging.WARNING,
    "playwright": logging.WARNING,
    "urllib3": logging.WARNING,
    "uvicorn.access": logging.WARNING,
    "uvicorn.error": logging.INFO,
}

# =============================================================================
# InterceptHandler — 桥接标准 logging → loguru
# =============================================================================


class InterceptHandler(logging.Handler):
    """Route standard library log records into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


# =============================================================================
# configure() — 唯一日志初始化入口
# =============================================================================

def configure(
    console_level: str = "INFO",
    log_dir: Path | None = None,
) -> None:
    """(Re)configure all logging sinks and third-party loggers.

    Args:
        console_level: Minimum level for the console sink (DEBUG/INFO/WARNING/ERROR).
        log_dir: Override the default log directory. Defaults to ``config.LOG_DIR``.
    """
    log_dir = log_dir or LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)

    # ── loguru sinks ──────────────────────────────────────────────────────
    logger.remove()
    logger.add(
        sink=sys.stderr,
        level=console_level,
        format=CONSOLE_FMT,
        colorize=sys.stderr.isatty(),
        diagnose=False,
        backtrace=True,
    )
    logger.add(
        sink=log_dir / "app_{time:YYYYMMDD}.log",
        level="DEBUG",
        format=FILE_FMT,
        encoding="utf-8",
        backtrace=False,
        diagnose=False,
        rotation="00:00",
        retention=config.settings.log_retain_days,
        compression="gz",
    )
    logger.add(
        sink=log_dir / "error_{time:YYYYMMDD}.log",
        level="ERROR",
        format=ERROR_FMT,
        encoding="utf-8",
        backtrace=True,
        diagnose=False,
        rotation="00:00",
        retention="90 days",
        compression="gz",
    )

    # ── bridge stdlib logging → loguru ────────────────────────────────────
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    for name, lvl in _THIRD_PARTY_LEVELS.items():
        lib_logger = logging.getLogger(name)
        lib_logger.handlers.clear()
        lib_logger.setLevel(lvl)
        lib_logger.propagate = False

    # Silence all crawlee sub-loggers (crawlee.*, created after import).
    crawlee_logger = logging.getLogger("crawlee")
    crawlee_logger.handlers.clear()
    crawlee_logger.setLevel(logging.WARNING)
    crawlee_logger.propagate = False
    for name in list(logging.root.manager.loggerDict):
        if name.startswith("crawlee."):
            sub = logging.getLogger(name)
            sub.handlers.clear()
            sub.setLevel(logging.WARNING)
            sub.propagate = False


# =============================================================================
# 模块导入时执行默认配置
# =============================================================================

# =============================================================================
# 日志级别使用规范
# =============================================================================
# DEBUG   - 详细调试信息：变量值、详细执行路径、提取步骤细节
# INFO    - 关键操作节点：采集开始/结束、批次汇总、pipeline 阶段转换
# WARNING - 可恢复的错误：解析失败、回退方案、网络超时重试
# ERROR   - 不可恢复的错误：LLM 调用失败、文件写入失败、致命异常
# =============================================================================

configure("INFO")
