# core/logger.py

import logging
import sys

def setup_logger(name: str = "chat_server", log_level: int = logging.INFO) -> logging.Logger:
    """
    设置并返回一个格式化的 logger 实例。
    日志格式与原始 server.py 的 print("[LOG] ...") 完全一致。
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # 避免重复添加 handler
    if not logger.handlers:
        # 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)

        # 定义与原始 print 语句完全相同的格式
        formatter = logging.Formatter('[LOG] %(message)s')
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

    return logger

# 创建一个全局 logger 实例，供整个应用使用
logger = setup_logger()