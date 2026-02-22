"""
日志管理系统
提供结构化日志记录、模型输出追踪和实时日志推送
"""
import logging
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from collections import deque
from enum import Enum
from dataclasses import dataclass, asdict
import threading
import json


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    MODEL = "model"  # 特殊级别：模型输出


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: str
    level: str
    source: str
    message: str
    data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        return asdict(self)


class LogManager:
    """
    集中式日志管理器

    功能：
    1. 结构化日志记录
    2. 模型输出专门追踪
    3. 日志缓存和查询
    4. 实时日志推送支持
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_logs: int = 1000, max_model_outputs: int = 200):
        if self._initialized:
            return

        self.max_logs = max_logs
        self.max_model_outputs = max_model_outputs

        # 日志存储
        self.logs: deque = deque(maxlen=max_logs)
        self.model_outputs: deque = deque(maxlen=max_model_outputs)

        # 日志回调（用于实时推送）
        self.log_callbacks: List[Callable[[LogEntry], None]] = []

        # 配置标准 logging
        self._setup_logging()

        self._initialized = True

    def _setup_logging(self):
        """配置 Python logging"""
        # 创建根记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # 清除现有处理器
        root_logger.handlers.clear()

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)

        # 自定义处理器 - 捕获到 LogManager
        capture_handler = LogCaptureHandler(self)
        capture_handler.setLevel(logging.DEBUG)

        root_logger.addHandler(console_handler)
        root_logger.addHandler(capture_handler)

    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的 logger"""
        return logging.getLogger(name)

    def log(self, level: LogLevel, source: str, message: str,
            data: Optional[Dict[str, Any]] = None):
        """
        记录日志

        Args:
            level: 日志级别
            source: 日志来源模块
            message: 日志消息
            data: 附加数据
        """
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level.value,
            source=source,
            message=message,
            data=data
        )

        self.logs.append(entry.to_dict())

        # 如果是模型输出，额外保存
        if level == LogLevel.MODEL:
            self.model_outputs.append(entry.to_dict())

        # 触发回调
        for callback in self.log_callbacks:
            try:
                callback(entry)
            except Exception:
                pass

    def log_model_output(self, source: str, prompt: str, response: str,
                         tokens_used: Optional[Dict[str, int]] = None,
                         latency_ms: Optional[float] = None):
        """
        记录模型输出

        Args:
            source: 调用来源
            prompt: 输入提示
            response: 模型响应
            tokens_used: Token 使用统计
            latency_ms: 响应延迟（毫秒）
        """
        data = {
            "prompt": prompt[:500] if len(prompt) > 500 else prompt,  # 截断长提示
            "prompt_length": len(prompt),
            "response": response,
            "response_length": len(response),
        }

        if tokens_used:
            data["tokens"] = tokens_used

        if latency_ms:
            data["latency_ms"] = latency_ms

        self.log(LogLevel.MODEL, source, f"模型调用完成", data)

    def get_logs(self, level: Optional[LogLevel] = None,
                 source: Optional[str] = None,
                 limit: int = 100) -> List[Dict]:
        """
        获取日志

        Args:
            level: 过滤日志级别
            source: 过滤来源
            limit: 返回数量限制
        """
        logs = list(self.logs)

        if level:
            logs = [log for log in logs if log["level"] == level.value]

        if source:
            logs = [log for log in logs if source.lower() in log["source"].lower()]

        # 返回最新的日志
        return logs[-limit:]

    def get_model_outputs(self, limit: int = 50) -> List[Dict]:
        """获取模型输出日志"""
        return list(self.model_outputs)[-limit:]

    def clear_logs(self):
        """清空日志"""
        self.logs.clear()
        self.model_outputs.clear()

    def add_callback(self, callback: Callable[[LogEntry], None]):
        """添加日志回调"""
        self.log_callbacks.append(callback)

    def remove_callback(self, callback: Callable[[LogEntry], None]):
        """移除日志回调"""
        if callback in self.log_callbacks:
            self.log_callbacks.remove(callback)

    def export_logs(self, filepath: str):
        """导出日志到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(list(self.logs), f, ensure_ascii=False, indent=2)

    def get_stats(self) -> Dict[str, Any]:
        """获取日志统计"""
        level_counts = {}
        for log in self.logs:
            level = log["level"]
            level_counts[level] = level_counts.get(level, 0) + 1

        return {
            "total_logs": len(self.logs),
            "model_outputs": len(self.model_outputs),
            "level_counts": level_counts,
            "max_capacity": self.max_logs
        }


class LogCaptureHandler(logging.Handler):
    """自定义日志处理器 - 捕获日志到 LogManager"""

    def __init__(self, log_manager: LogManager):
        super().__init__()
        self.log_manager = log_manager

    def emit(self, record: logging.LogRecord):
        try:
            level_map = {
                logging.DEBUG: LogLevel.DEBUG,
                logging.INFO: LogLevel.INFO,
                logging.WARNING: LogLevel.WARNING,
                logging.ERROR: LogLevel.ERROR,
                logging.CRITICAL: LogLevel.CRITICAL,
            }

            level = level_map.get(record.levelno, LogLevel.INFO)
            message = self.format(record)

            # 不重复记录已经格式化的消息，只取原始消息
            self.log_manager.log(
                level=level,
                source=record.name,
                message=record.getMessage()
            )
        except Exception:
            pass


class ModelOutputTracker:
    """
    模型输出追踪器

    用于装饰 LLM 调用函数，自动记录输入输出
    """

    def __init__(self, log_manager: LogManager):
        self.log_manager = log_manager

    def track(self, source: str):
        """装饰器：追踪模型调用"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                import time
                start_time = time.time()

                # 提取 prompt
                prompt = ""
                if args:
                    prompt = str(args[0])[:500]
                elif "prompt" in kwargs:
                    prompt = str(kwargs["prompt"])[:500]
                elif "messages" in kwargs:
                    messages = kwargs["messages"]
                    if isinstance(messages, list) and messages:
                        prompt = str(messages[-1].get("content", ""))[:500]

                try:
                    result = func(*args, **kwargs)
                    latency = (time.time() - start_time) * 1000

                    response = str(result) if result else ""

                    self.log_manager.log_model_output(
                        source=source,
                        prompt=prompt,
                        response=response,
                        latency_ms=latency
                    )

                    return result
                except Exception as e:
                    self.log_manager.log(
                        LogLevel.ERROR,
                        source,
                        f"模型调用失败: {str(e)}"
                    )
                    raise

            return wrapper
        return decorator
