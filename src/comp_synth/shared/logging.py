import sys
from pathlib import Path

from loguru import logger

from comp_synth.app import config

LOG_DIR = Path(config.LOG_DIR)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 定义日志格式
# 控制台彩色格式（含上下文绑定字段：request_id/user_id）
CONSOLE_FMT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{module}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)
# 文件纯文本格式（含进程/线程ID，便于多进程调试）
FILE_FMT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | " "{level: <8} | " "{module}:{line} | " "{message}"
# 错误日志格式（含异常堆栈）
ERROR_FMT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | " "{level: <8} | " "{module}:{line} | " "{message}"

logger.remove()

logger.add(
    sink=sys.stderr,
    level="DEBUG",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
           "<level>{message}</level>",
    colorize=True,
    diagnose=True,
    backtrace=True
)


logger.add(
    sink=LOG_DIR / "app_{time:YYYYMMDD}.log",
    level="DEBUG",
    format=FILE_FMT,
    encoding="utf-8",
    enqueue=True,
    backtrace=False,
    diagnose=False,
)

logger.add(
    sink=LOG_DIR / "error_{time:YYYYMMDD}.log",
    level="ERROR",
    format=ERROR_FMT,
    encoding="utf-8",
    enqueue=True,
    backtrace=True,
    diagnose=False,
)
