import sys
from pathlib import Path

from loguru import logger

from comp_synth import config

LOG_DIR = Path(config.LOG_DIR)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# 日志格式定义
# =============================================================================

# 控制台彩色格式
#   - {time:YYYY-MM-DD HH:mm:ss}     时间（精确到秒）
#   - {level: <8}                    日志级别（左对齐，宽度8）
#   - {name}:{function}:{line}        调用位置（模块:函数:行号）
#   - {message}                       日志消息
CONSOLE_FMT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

# 文件纯文本格式（追加毫秒，便于多进程调试）
FILE_FMT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}"

# 错误日志格式（与文件格式一致，由 Loguru 自动附加异常堆栈）
ERROR_FMT = FILE_FMT

# =============================================================================
# 日志级别使用规范
# =============================================================================
# DEBUG   - 详细调试信息：变量值、详细执行路径
# INFO    - 一般操作信息：采集进度、分组结果、文件写入
# WARNING - 可恢复的错误：解析失败、回退方案、网络超时重试
# ERROR   - 不可恢复的错误：LLM 调用失败、文件写入失败、致命异常
# =============================================================================

logger.remove()

logger.add(
    sink=sys.stderr,
    level="DEBUG",
    format=CONSOLE_FMT,
    colorize=True,
    diagnose=True,
    backtrace=True,
)


logger.add(
    sink=LOG_DIR / "app_{time:YYYYMMDD}.log",
    level="DEBUG",
    format=FILE_FMT,
    encoding="utf-8",
    backtrace=False,
    diagnose=False,
)

logger.add(
    sink=LOG_DIR / "error_{time:YYYYMMDD}.log",
    level="ERROR",
    format=ERROR_FMT,
    encoding="utf-8",
    backtrace=True,
    diagnose=True,
)
