from comp_synth.utils.logging import logger

# from loguru import logger
#
# logger.remove()
#
# # 1. 控制台输出（INFO及以上，彩色格式）
# logger.add(
#     sys.stdout,
#     level="INFO", # 最低日志级别
#     format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{module}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
# )
#
# # 2. 文件输出（DEBUG及以上，纯文本格式，自动创建文件）默认使用追加模式
# logger.add(
#     sink="../logs/app.log",  # 日志文件路径，目录不存在会自动创建
#     level="DEBUG",
#     format="{time:YYYY HH:mm:ss} | {level: <8} | {module}:{line} - {message}",
#     encoding="utf-8"  # 指定编码，避免中文乱码（必配）
# )
#
# logger.add(
#     sink="../logs/app.log", # 不幂等
#     level="DEBUG",
#     format="{time:YYYY HH:mm:ss} | {level: <8} | {module}:{line} - {message}",
#     encoding="utf-8"
# )
#
# # 过滤1：仅输出来自 user 模块的日志（通配符*匹配子模块）
# logger.add(
#     sys.stdout,
#     format="{time:YYYY HH:mm:ss} | {level: <8} | {module}:{line} - {message}",
#     filter="user.*"  # 仅匹配 logger 名称为 user、user.utils、user.service 等的日志
# )
#
# # 过滤2：仅输出 ERROR 和 CRITICAL 级别日志（字典格式）
# logger.add(
#     "../logs/error.log",
#     format="{time:YYYY HH:mm:ss} | {level: <8} | {module}:{line} - {message}",
#     filter=lambda record: record["level"].name in ["ERROR", "CRITICAL"]
# )
#
# # 生产环境标配：50MB轮转+保留30天+zip压缩+中文防乱码
# logger.add(
#     sink="../logs/app_{time:YYYYMMDD}.log",  # 文件名带日期，便于查找
#     level="DEBUG",
#     format="{time:YYYY HH:mm:ss} | {level: <8} | {module}:{line} - {message}",
#     encoding="utf-8",
#     rotation="50 MB",        # 单个文件50MB，自动轮转
#     retention="30 days",     # 仅保留最近30天的日志文件
#     compression="zip",       # 过期日志自动压缩为zip格式
#     enqueue=True,            # 多进程安全写入（避免多进程下日志乱序/丢失）
#     backtrace=True,          # 捕获异常时，显示完整的堆栈回溯（包括第三方库）
#     diagnose=True            # 捕获异常时，显示变量值等诊断信息（开发/测试环境开启）
# )
#
# logger.debug("调试信息：仅写入文件，控制台不显示")
# logger.info("信息：控制台+文件均显示")
# logger.info("根模块日志：不会被输出")  # 过滤1不匹配，无输出
# logger.error("根模块错误：会写入error.log")  # 过滤2匹配，正常输出
#
# try:
#     # 模拟异常
#     1 / 0
# except ZeroDivisionError:
#     # exc_info=True：自动记录完整的异常堆栈
#     logger.error("除零错误发生，业务执行失败", exc_info=True)
#
#
# # 装饰器方式：捕获函数内所有异常
# @logger.catch  # 关键：添加该装饰器
# def divide(a, b):
#     return a / b
#
#
#
# logger.remove()
# # 格式中添加绑定的字段占位符：{request_id}、{user_id}
# console_fmt = "<green>{time:HH:mm:ss}</green> | {level: <8} | request_id={request_id} | user_id={user_id} | {message}"
# logger.add(sys.stdout, format=console_fmt, level="INFO")
#
# # 1. 基础绑定：绑定固定字段
# logger = logger.bind(request_id="req-123456", user_id=1001)
# logger.info("用户发起登录请求")
# logger.info("用户密码验证通过")
# logger.warning("用户登录次数超过阈值")
#
# # 2. 动态绑定：针对不同请求生成唯一request_id（Web场景标配）
# def handle_request(user_id):
#     # 为每个请求生成唯一request_id
#     req_id = str(uuid.uuid4())[:8]
#     # 动态绑定上下文
#     req_logger = logger.bind(request_id=req_id, user_id=user_id)
#     req_logger.info("请求开始：/api/user/info")
#     req_logger.info("查询用户信息完成")
#     return {"code": 200, "msg": "success"}
#
# # 模拟两个不同请求
# handle_request(1002)
# handle_request(1003)


def test_logger():
    logger.debug("agent调用工具失败")
    logger.info("agent调用add工具中")


@logger.catch(reraise=True)
def divide(a, b):
    return a / b

def test_logger_reraise():
    try:
        divide(1, 0)
    except Exception:
        print("process catch error")
