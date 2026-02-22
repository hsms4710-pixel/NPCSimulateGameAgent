# -*- coding: utf-8 -*-
"""
世界事件系统
处理世界事件的触发和传播

使用统一的 Event 类型，确保事件在系统中的一致性。
"""

import logging
import math
from typing import Dict, List, Any, Callable
from datetime import datetime

# 从统一类型模块导入
from core_types.event_types import (
    Event,
    EventType,
    EventSeverity,
    EventPriority,
    PropagationMethod,
)

logger = logging.getLogger(__name__)


# ==================== 事件传播系统 ====================

class EventPropagation:
    """事件传播系统"""

    def __init__(self, spatial_system=None):
        self.spatial_system = spatial_system
        self.propagation_queue: List[Dict[str, Any]] = []

    def calculate_distance(self, loc1: str, loc2: str) -> float:
        """计算两个位置之间的距离"""
        if self.spatial_system:
            pos1 = self.spatial_system.get_location_position(loc1)
            pos2 = self.spatial_system.get_location_position(loc2)
            if pos1 and pos2:
                return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
        # 默认距离估算
        return 50.0

    def calculate_propagation_delay(self, event: Event, npc_location: str) -> float:
        """计算事件传播到NPC位置的延迟（游戏小时）"""
        distance = self.calculate_distance(event.location, npc_location)

        method = event.propagation_method
        # 处理字符串或枚举
        if isinstance(method, PropagationMethod):
            method = method.value

        if method == "immediate":
            if distance <= 20:
                return 0
            return float('inf')  # 超出范围不传播

        elif method == "gradual":
            speed = event.propagation_speed
            return distance / (speed * 10)

        elif method == "gossip":
            # 口口相传更慢，但可以传播更远
            speed = event.propagation_speed
            return distance / (speed * 5) + 0.5

        elif method == "announcement":
            return 0.1  # 公告几乎立即传播

        return distance / 10

    def should_npc_know(self, event: Event, npc_location: str,
                        hours_since_event: float) -> bool:
        """判断NPC是否应该知道这个事件"""
        delay = self.calculate_propagation_delay(event, npc_location)
        return hours_since_event >= delay

    def get_event_awareness_level(self, event: Event, npc_location: str,
                                   hours_since_event: float) -> float:
        """获取NPC对事件的了解程度 (0-1)"""
        if not self.should_npc_know(event, npc_location, hours_since_event):
            return 0.0

        delay = self.calculate_propagation_delay(event, npc_location)
        time_since_knew = hours_since_event - delay

        # 越早知道，了解越详细
        if time_since_knew <= 0:
            return 0.0
        elif time_since_knew < 1:
            return 0.3  # 刚听说
        elif time_since_knew < 3:
            return 0.6  # 有一定了解
        else:
            return 0.9  # 详细了解


# ==================== 世界事件触发器 ====================

class WorldEventTrigger:
    """世界事件触发器"""

    def __init__(self, spatial_system=None):
        self.events: Dict[str, Event] = {}
        self.event_history: List[Event] = []
        self.propagation = EventPropagation(spatial_system)
        self.event_callbacks: List[Callable] = []
        self._event_counter = 0

    def _generate_event_id(self) -> str:
        self._event_counter += 1
        return f"evt_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self._event_counter}"

    def trigger_event(
        self,
        title: str,
        description: str,
        location: str,
        event_type: str = "general",
        severity: int = 50,  # 现在使用 importance (0-100)
        propagation_method: str = "gradual",
        affected_npcs: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Event:
        """触发世界事件"""
        # 处理 EventType 枚举
        if isinstance(event_type, EventType):
            event_type = event_type.value

        # 处理 EventSeverity 枚举 -> importance 映射
        if isinstance(severity, EventSeverity):
            severity = severity.value * 20  # 1-5 -> 20-100
        elif isinstance(severity, int) and severity <= 5:
            severity = severity * 20  # 兼容旧的 1-5 范围

        # 处理 PropagationMethod 枚举
        if isinstance(propagation_method, PropagationMethod):
            propagation_method = propagation_method.value

        # 使用新的简化 Event 创建
        event = Event.create_world_event(
            content=description,
            location=location,
            event_type=event_type,
            importance=severity,
            title=title,
            propagation_method=propagation_method,
        )

        # 设置自定义 ID
        event.id = self._generate_event_id()

        # 添加目标和元数据
        if affected_npcs:
            event.targets.extend(affected_npcs)
        if metadata:
            event.data.update(metadata)

        self.events[event.id] = event
        self.event_history.append(event)

        logger.info(f"世界事件触发: [{event.event_type}] {event.title} @ {location}")

        # 触发回调
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"事件回调执行失败: {e}")

        return event

    def trigger_crime_event(
        self,
        crime_type: str,
        location: str,
        perpetrator: str = "未知",
        victim: str = None,
        severity: int = 70  # 相当于 MAJOR
    ) -> Event:
        """触发犯罪事件"""
        description = f"{crime_type}发生在{location}"
        if perpetrator != "未知":
            description += f"，肇事者是{perpetrator}"
        if victim:
            description += f"，受害者是{victim}"

        # 处理 EventSeverity 枚举
        if isinstance(severity, EventSeverity):
            severity = severity.value * 20

        return self.trigger_event(
            title=f"{location}发生{crime_type}",
            description=description,
            location=location,
            event_type="crime",
            severity=severity,
            propagation_method="gradual",
            affected_npcs=[victim] if victim else [],
            metadata={
                "crime_type": crime_type,
                "perpetrator": perpetrator,
                "victim": victim
            }
        )

    def trigger_accident_event(
        self,
        accident_type: str,
        location: str,
        severity: int = 70  # 相当于 MAJOR
    ) -> Event:
        """触发事故事件"""
        # 处理 EventSeverity 枚举
        if isinstance(severity, EventSeverity):
            severity = severity.value * 20

        return self.trigger_event(
            title=f"{location}发生{accident_type}",
            description=f"{accident_type}在{location}发生了",
            location=location,
            event_type="accident",
            severity=severity,
            propagation_method="immediate"
        )

    def get_active_events(self) -> List[Event]:
        """获取所有活跃事件"""
        return [e for e in self.events.values() if e.is_active]

    def get_events_for_npc(
        self,
        npc_name: str,
        npc_location: str,
        current_time: datetime
    ) -> List[Dict[str, Any]]:
        """获取NPC应该知道的事件"""
        known_events = []

        for event in self.get_active_events():
            hours_since = (current_time - event.timestamp).total_seconds() / 3600

            if self.propagation.should_npc_know(event, npc_location, hours_since):
                awareness = self.propagation.get_event_awareness_level(
                    event, npc_location, hours_since
                )
                known_events.append({
                    "event": event.to_dict(),
                    "awareness_level": awareness,
                    "hours_since_event": hours_since
                })

                # 记录已通知
                event.add_notified_npc(npc_name)

        return known_events

    def deactivate_event(self, event_id: str):
        """停用事件"""
        if event_id in self.events:
            self.events[event_id].deactivate()

    def register_callback(self, callback: Callable):
        """注册事件回调"""
        self.event_callbacks.append(callback)

    def get_event_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取事件历史"""
        return [e.to_dict() for e in self.event_history[-limit:]]


# ==================== 预定义事件模板 ====================

EVENT_TEMPLATES = {
    "thief_break_in": {
        "title_template": "{location}遭到小偷入侵",
        "description_template": "有小偷闯入了{location}，正在偷窃财物",
        "event_type": "crime",
        "importance": 70,
        "propagation_method": "gradual"
    },
    "fire": {
        "title_template": "{location}发生火灾",
        "description_template": "{location}着火了！浓烟滚滚",
        "event_type": "accident",
        "importance": 90,
        "propagation_method": "immediate"
    },
    "festival": {
        "title_template": "节日庆典",
        "description_template": "镇上正在举办节日庆典，大家都很开心",
        "event_type": "social",
        "importance": 30,
        "propagation_method": "announcement"
    },
    "stranger_arrival": {
        "title_template": "陌生人到来",
        "description_template": "一个陌生人来到了{location}",
        "event_type": "social",
        "importance": 20,
        "propagation_method": "gossip"
    }
}


# ==================== 向后兼容别名 ====================

# WorldEvent 现在是 Event 的别名
WorldEvent = Event

__all__ = [
    'Event',
    'WorldEvent',
    'EventType',
    'EventSeverity',
    'EventPriority',
    'PropagationMethod',
    'EventPropagation',
    'WorldEventTrigger',
    'EVENT_TEMPLATES',
]
