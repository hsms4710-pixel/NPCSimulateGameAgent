# -*- coding: utf-8 -*-
"""
事件系统接口协议
===============

定义事件系统的标准接口，解决以下问题：
1. 事件发布/订阅方法不一致
2. 事件处理器注册方式不统一
3. 事件优先级和传播机制不一致

接口方法：
- EventInterface: 事件发布和管理
- EventHandlerInterface: 事件处理器
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Protocol, runtime_checkable, Callable, TypeVar, Generic
from enum import Enum

# 事件类型变量
E = TypeVar('E')


@runtime_checkable
class EventHandlerInterface(Protocol):
    """
    事件处理器接口协议

    所有事件处理器都应实现此接口
    """

    def handle(self, event: Dict[str, Any]) -> bool:
        """
        处理事件

        Args:
            event: 事件数据

        Returns:
            bool: 是否成功处理
        """
        ...

    @property
    def event_types(self) -> List[str]:
        """
        支持的事件类型列表

        Returns:
            List[str]: 事件类型列表
        """
        ...

    @property
    def priority(self) -> int:
        """
        处理器优先级 (数字越小优先级越高)

        Returns:
            int: 优先级
        """
        ...


@runtime_checkable
class EventInterface(Protocol):
    """
    事件系统接口协议

    定义事件发布、订阅、管理的标准方法
    """

    def publish(
        self,
        event_type: str,
        data: Dict[str, Any],
        source: Optional[str] = None,
        priority: int = 5,
        propagate: bool = True
    ) -> str:
        """
        发布事件

        Args:
            event_type: 事件类型
            data: 事件数据
            source: 事件来源 (通常是NPC ID)
            priority: 优先级 1-10
            propagate: 是否传播给附近NPC

        Returns:
            str: 事件ID
        """
        ...

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any]], bool],
        priority: int = 5
    ) -> str:
        """
        订阅事件

        Args:
            event_type: 事件类型
            handler: 处理函数
            priority: 处理优先级

        Returns:
            str: 订阅ID
        """
        ...

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        取消订阅

        Args:
            subscription_id: 订阅ID

        Returns:
            bool: 是否取消成功
        """
        ...

    def get_pending_events(
        self,
        event_types: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取待处理事件

        Args:
            event_types: 限定事件类型
            limit: 返回数量限制

        Returns:
            List[Dict]: 待处理事件列表
        """
        ...

    def clear_events(
        self,
        event_types: Optional[List[str]] = None,
        before: Optional[datetime] = None
    ) -> int:
        """
        清理事件

        Args:
            event_types: 限定事件类型
            before: 清理此时间之前的事件

        Returns:
            int: 清理的事件数量
        """
        ...


class BaseEventSystem(ABC):
    """
    事件系统抽象基类

    提供事件系统的默认实现骨架
    """

    def __init__(self):
        self._handlers: Dict[str, List[tuple]] = {}  # event_type -> [(priority, handler)]
        self._subscriptions: Dict[str, tuple] = {}  # subscription_id -> (event_type, handler)

    @abstractmethod
    def publish(
        self,
        event_type: str,
        data: Dict[str, Any],
        source: Optional[str] = None,
        priority: int = 5,
        propagate: bool = True
    ) -> str:
        """发布事件"""
        pass

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any]], bool],
        priority: int = 5
    ) -> str:
        """订阅事件 - 默认实现"""
        import uuid
        subscription_id = str(uuid.uuid4())

        if event_type not in self._handlers:
            self._handlers[event_type] = []

        self._handlers[event_type].append((priority, handler))
        # 按优先级排序
        self._handlers[event_type].sort(key=lambda x: x[0])

        self._subscriptions[subscription_id] = (event_type, handler)
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """取消订阅 - 默认实现"""
        if subscription_id not in self._subscriptions:
            return False

        event_type, handler = self._subscriptions[subscription_id]
        if event_type in self._handlers:
            self._handlers[event_type] = [
                (p, h) for p, h in self._handlers[event_type]
                if h != handler
            ]

        del self._subscriptions[subscription_id]
        return True

    def get_pending_events(
        self,
        event_types: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取待处理事件 - 默认实现返回空"""
        return []

    def clear_events(
        self,
        event_types: Optional[List[str]] = None,
        before: Optional[datetime] = None
    ) -> int:
        """清理事件 - 默认实现返回0"""
        return 0

    def _dispatch_event(self, event_type: str, event_data: Dict[str, Any]) -> int:
        """
        分发事件给所有订阅者

        Args:
            event_type: 事件类型
            event_data: 事件数据

        Returns:
            int: 成功处理的处理器数量
        """
        handled_count = 0

        # 精确匹配
        if event_type in self._handlers:
            for priority, handler in self._handlers[event_type]:
                try:
                    if handler(event_data):
                        handled_count += 1
                except Exception as e:
                    # 记录错误但不中断
                    pass

        # 通配符匹配 "*"
        if "*" in self._handlers:
            for priority, handler in self._handlers["*"]:
                try:
                    if handler(event_data):
                        handled_count += 1
                except Exception:
                    pass

        return handled_count

    # ==================== 兼容性方法别名 ====================

    def emit(self, *args, **kwargs) -> str:
        """别名: publish"""
        return self.publish(*args, **kwargs)

    def trigger(self, *args, **kwargs) -> str:
        """别名: publish"""
        return self.publish(*args, **kwargs)

    def fire(self, *args, **kwargs) -> str:
        """别名: publish"""
        return self.publish(*args, **kwargs)

    def dispatch(self, *args, **kwargs) -> str:
        """别名: publish"""
        return self.publish(*args, **kwargs)

    def on(self, event_type: str, handler: Callable, priority: int = 5) -> str:
        """别名: subscribe"""
        return self.subscribe(event_type, handler, priority)

    def listen(self, event_type: str, handler: Callable, priority: int = 5) -> str:
        """别名: subscribe"""
        return self.subscribe(event_type, handler, priority)

    def register_handler(self, event_type: str, handler: Callable, priority: int = 5) -> str:
        """别名: subscribe"""
        return self.subscribe(event_type, handler, priority)

    def off(self, subscription_id: str) -> bool:
        """别名: unsubscribe"""
        return self.unsubscribe(subscription_id)

    def remove_handler(self, subscription_id: str) -> bool:
        """别名: unsubscribe"""
        return self.unsubscribe(subscription_id)
