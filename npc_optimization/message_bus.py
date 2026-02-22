"""
多NPC消息总线系统
实现NPC之间的事件传播、通信和协作

继承自 BaseEventSystem，实现统一的事件接口协议。
"""

import logging
import threading
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Set
from queue import Queue, Empty

# 从统一类型模块导入
from core_types import MessageType, MessagePriority

# 从接口模块导入
from interfaces import BaseEventSystem

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """消息数据类"""
    id: str
    message_type: MessageType
    sender_id: str                       # 发送者NPC ID（系统消息为"system"）
    content: str                         # 消息内容
    timestamp: datetime
    priority: MessagePriority = MessagePriority.NORMAL

    # 传播范围
    target_ids: List[str] = field(default_factory=list)  # 特定目标（空表示广播）
    zone: Optional[str] = None           # 限定区域（None表示全局）
    radius: float = 0.0                  # 传播半径（0表示无限）

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 状态
    processed_by: Set[str] = field(default_factory=set)  # 已处理的NPC ID

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]


@dataclass
class Subscription:
    """订阅信息"""
    subscriber_id: str                   # 订阅者NPC ID
    message_types: List[MessageType]     # 订阅的消息类型
    callback: Callable[[Message], None]  # 回调函数
    filter_zone: Optional[str] = None    # 过滤特定区域
    active: bool = True


class NPCMessageBus(BaseEventSystem):
    """
    NPC消息总线

    继承自 BaseEventSystem，实现统一的事件接口协议。
    支持发布-订阅模式的NPC间通信。
    """

    def __init__(self, async_mode: bool = True):
        """
        初始化消息总线

        Args:
            async_mode: 是否启用异步消息处理
        """
        super().__init__()  # 初始化基类
        self.subscribers: Dict[str, Subscription] = {}
        self.message_queue: Queue = Queue()
        self.message_history: List[Message] = []
        self.max_history_size: int = 1000

        self.lock = threading.RLock()
        self.async_mode = async_mode
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None

        # NPC位置追踪（用于距离过滤）
        self.npc_locations: Dict[str, Dict[str, Any]] = {}

        # 统计信息
        self.stats = {
            "messages_published": 0,
            "messages_delivered": 0,
            "messages_dropped": 0
        }

        # 事件处理回调（EventInterface 兼容）
        self._event_handlers: Dict[str, List[tuple]] = {}  # event_type -> [(priority, handler)]
        self._subscriptions_map: Dict[str, tuple] = {}  # subscription_id -> (event_type, handler)

    def start(self):
        """启动消息总线"""
        if self.async_mode and not self.running:
            self.running = True
            self.worker_thread = threading.Thread(
                target=self._message_worker,
                daemon=True
            )
            self.worker_thread.start()
            logger.info("消息总线已启动（异步模式）")

    def stop(self):
        """停止消息总线"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2)
            logger.info("消息总线已停止")

    def subscribe(self,
                  subscriber_id: str,
                  message_types: List[MessageType],
                  callback: Callable[[Message], None],
                  filter_zone: Optional[str] = None) -> str:
        """
        订阅消息

        Args:
            subscriber_id: 订阅者NPC ID
            message_types: 要订阅的消息类型列表
            callback: 消息回调函数
            filter_zone: 可选的区域过滤

        Returns:
            订阅ID
        """
        with self.lock:
            subscription = Subscription(
                subscriber_id=subscriber_id,
                message_types=message_types,
                callback=callback,
                filter_zone=filter_zone
            )
            self.subscribers[subscriber_id] = subscription
            logger.debug(f"NPC {subscriber_id} 订阅了 {[t.value for t in message_types]}")
            return subscriber_id

    def unsubscribe(self, subscriber_id: str) -> bool:
        """
        取消订阅 (实现 EventInterface)

        Args:
            subscriber_id: 订阅ID

        Returns:
            bool: 是否取消成功
        """
        with self.lock:
            if subscriber_id in self.subscribers:
                del self.subscribers[subscriber_id]
                logger.debug(f"NPC {subscriber_id} 取消订阅")
                return True

            # 也检查事件处理器订阅
            if subscriber_id in self._subscriptions_map:
                event_type, handler = self._subscriptions_map[subscriber_id]
                if event_type in self._event_handlers:
                    self._event_handlers[event_type] = [
                        (p, h) for p, h in self._event_handlers[event_type]
                        if h != handler
                    ]
                del self._subscriptions_map[subscriber_id]
                return True

            return False

    # ========================================================================
    # 接口标准方法实现 (EventInterface)
    # ========================================================================

    def publish(
        self,
        event_type: str,
        data: Dict[str, Any],
        source: Optional[str] = None,
        priority: int = 5,
        propagate: bool = True
    ) -> str:
        """
        发布事件 (实现 EventInterface)

        Args:
            event_type: 事件类型
            data: 事件数据
            source: 事件来源 (通常是NPC ID)
            priority: 优先级 1-10
            propagate: 是否传播给附近NPC

        Returns:
            str: 事件ID
        """
        # 转换为 Message 对象
        try:
            msg_type = MessageType(event_type)
        except ValueError:
            msg_type = MessageType.SYSTEM

        # 映射优先级
        if priority <= 3:
            msg_priority = MessagePriority.LOW
        elif priority <= 6:
            msg_priority = MessagePriority.NORMAL
        elif priority <= 8:
            msg_priority = MessagePriority.HIGH
        else:
            msg_priority = MessagePriority.URGENT

        message = Message(
            id=str(uuid.uuid4())[:8],
            message_type=msg_type,
            sender_id=source or "system",
            content=data.get("content", str(data)),
            timestamp=datetime.now(),
            priority=msg_priority,
            target_ids=data.get("target_ids", []),
            zone=data.get("zone"),
            metadata=data
        )

        self.publish_message(message)

        # 同时触发事件处理器
        event_data = {
            "event_id": message.id,
            "event_type": event_type,
            "source": source,
            "data": data,
            "timestamp": message.timestamp.isoformat(),
            "priority": priority
        }
        self._dispatch_event(event_type, event_data)

        return message.id

    def subscribe_event(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any]], bool],
        priority: int = 5
    ) -> str:
        """
        订阅事件类型 (EventInterface 兼容)

        Args:
            event_type: 事件类型
            handler: 处理函数
            priority: 处理优先级

        Returns:
            str: 订阅ID
        """
        subscription_id = str(uuid.uuid4())[:8]

        with self.lock:
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []

            self._event_handlers[event_type].append((priority, handler))
            self._event_handlers[event_type].sort(key=lambda x: x[0])
            self._subscriptions_map[subscription_id] = (event_type, handler)

        return subscription_id

    def get_pending_events(
        self,
        event_types: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取待处理事件 (实现 EventInterface)

        Args:
            event_types: 限定事件类型
            limit: 返回数量限制

        Returns:
            List[Dict]: 待处理事件列表
        """
        with self.lock:
            messages = self.message_history.copy()

        # 过滤
        if event_types:
            messages = [m for m in messages if m.message_type.value in event_types]

        # 按时间倒序
        messages.sort(key=lambda m: m.timestamp, reverse=True)

        # 转换为字典格式
        result = []
        for msg in messages[:limit]:
            result.append({
                "event_id": msg.id,
                "event_type": msg.message_type.value,
                "source": msg.sender_id,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "priority": msg.priority.value,
                "zone": msg.zone,
                "metadata": msg.metadata
            })

        return result

    def clear_events(
        self,
        event_types: Optional[List[str]] = None,
        before: Optional[datetime] = None
    ) -> int:
        """
        清理事件 (实现 EventInterface)

        Args:
            event_types: 限定事件类型
            before: 清理此时间之前的事件

        Returns:
            int: 清理的事件数量
        """
        with self.lock:
            original_count = len(self.message_history)

            if event_types is None and before is None:
                # 清空所有
                self.message_history.clear()
            else:
                # 过滤保留
                new_history = []
                for msg in self.message_history:
                    keep = True

                    if event_types and msg.message_type.value in event_types:
                        keep = False

                    if before and msg.timestamp < before:
                        keep = False

                    if keep:
                        new_history.append(msg)

                self.message_history = new_history

            return original_count - len(self.message_history)

    # ========================================================================
    # 原有方法 (保持向后兼容)
    # ========================================================================

    def publish_message(self, message: Message):
        """
        发布消息

        Args:
            message: 要发布的消息
        """
        with self.lock:
            self.stats["messages_published"] += 1

            # 添加到历史
            self.message_history.append(message)
            if len(self.message_history) > self.max_history_size:
                self.message_history.pop(0)

        if self.async_mode:
            self.message_queue.put(message)
        else:
            self._deliver_message(message)

    def publish_event(self,
                      sender_id: str,
                      message_type: MessageType,
                      content: str,
                      zone: Optional[str] = None,
                      target_ids: List[str] = None,
                      priority: MessagePriority = MessagePriority.NORMAL,
                      metadata: Dict[str, Any] = None) -> Message:
        """
        便捷方法：发布事件

        Returns:
            创建的消息对象
        """
        message = Message(
            id=str(uuid.uuid4())[:8],
            message_type=message_type,
            sender_id=sender_id,
            content=content,
            timestamp=datetime.now(),
            priority=priority,
            target_ids=target_ids or [],
            zone=zone,
            metadata=metadata or {}
        )
        self.publish_message(message)
        return message

    def update_npc_location(self, npc_id: str, zone: str, x: float = 0, y: float = 0):
        """更新NPC位置（用于距离过滤）"""
        with self.lock:
            self.npc_locations[npc_id] = {
                "zone": zone,
                "x": x,
                "y": y,
                "updated_at": datetime.now()
            }

    def _message_worker(self):
        """异步消息处理工作线程"""
        while self.running:
            try:
                message = self.message_queue.get(timeout=0.1)
                self._deliver_message(message)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"消息处理错误: {e}")

    def _deliver_message(self, message: Message):
        """投递消息给订阅者"""
        with self.lock:
            subscribers_copy = list(self.subscribers.values())

        for subscription in subscribers_copy:
            if not subscription.active:
                continue

            # 检查消息类型匹配
            if message.message_type not in subscription.message_types:
                continue

            # 检查是否是发送者自己（不发送给自己）
            if subscription.subscriber_id == message.sender_id:
                continue

            # 检查目标过滤
            if message.target_ids and subscription.subscriber_id not in message.target_ids:
                continue

            # 检查区域过滤
            if message.zone and subscription.filter_zone:
                if message.zone != subscription.filter_zone:
                    continue

            # 检查距离过滤
            if message.radius > 0 and message.sender_id in self.npc_locations:
                if not self._is_in_range(message.sender_id, subscription.subscriber_id, message.radius):
                    continue

            # 投递消息
            try:
                subscription.callback(message)
                message.processed_by.add(subscription.subscriber_id)
                self.stats["messages_delivered"] += 1
            except Exception as e:
                logger.error(f"消息投递到 {subscription.subscriber_id} 失败: {e}")
                self.stats["messages_dropped"] += 1

    def _is_in_range(self, sender_id: str, receiver_id: str, radius: float) -> bool:
        """检查两个NPC是否在通信范围内"""
        sender_loc = self.npc_locations.get(sender_id)
        receiver_loc = self.npc_locations.get(receiver_id)

        if not sender_loc or not receiver_loc:
            return True  # 如果没有位置信息，默认在范围内

        # 不同区域，超出范围
        if sender_loc["zone"] != receiver_loc["zone"]:
            return False

        # 计算距离
        dx = sender_loc["x"] - receiver_loc["x"]
        dy = sender_loc["y"] - receiver_loc["y"]
        distance = (dx ** 2 + dy ** 2) ** 0.5

        return distance <= radius

    def get_recent_messages(self,
                           message_types: List[MessageType] = None,
                           zone: Optional[str] = None,
                           limit: int = 10) -> List[Message]:
        """获取最近的消息"""
        with self.lock:
            messages = self.message_history.copy()

        # 过滤
        if message_types:
            messages = [m for m in messages if m.message_type in message_types]
        if zone:
            messages = [m for m in messages if m.zone == zone or m.zone is None]

        # 按时间倒序
        messages.sort(key=lambda m: m.timestamp, reverse=True)

        return messages[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            return {
                **self.stats,
                "active_subscribers": len(self.subscribers),
                "pending_messages": self.message_queue.qsize(),
                "history_size": len(self.message_history)
            }


# 全局消息总线实例
_global_message_bus: Optional[NPCMessageBus] = None


def get_message_bus() -> NPCMessageBus:
    """获取全局消息总线实例"""
    global _global_message_bus
    if _global_message_bus is None:
        _global_message_bus = NPCMessageBus(async_mode=True)
        _global_message_bus.start()
    return _global_message_bus


def reset_message_bus():
    """重置全局消息总线"""
    global _global_message_bus
    if _global_message_bus:
        _global_message_bus.stop()
    _global_message_bus = None
