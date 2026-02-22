# -*- coding: utf-8 -*-
"""
统一事件类型定义
===============

简化的事件系统，支持灵活的事件类型和LLM驱动的事件处理。

设计原则：
1. 灵活性：event_type 使用字符串，支持任意事件类型
2. 简洁性：核心字段最小化，扩展数据放在 data 字典
3. 一致性：所有模块使用统一的 Event 类
4. LLM友好：结构简单，便于LLM理解和生成

主要类型：
- Event: 统一的事件数据类（核心）
- EventAnalysis: 事件分析结果（LLM输出）
- NPCEventResponse: NPC事件响应（LLM输出）
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from typing import Dict, List, Any, Optional, Tuple, Union
import uuid


# ==================== 辅助枚举（可选使用） ====================

class EventType(Enum):
    """
    预定义事件类型枚举（可选使用）

    注意：Event.event_type 可以是任意字符串，不限于这些枚举值。
    这些枚举仅作为常用类型的快捷方式。
    """
    # 世界事件
    CRIME = "crime"
    ACCIDENT = "accident"
    NATURAL = "natural"
    SOCIAL = "social"
    ECONOMIC = "economic"
    POLITICAL = "political"

    # NPC事件
    DIALOGUE = "dialogue"
    ACTION = "action"
    STATE_CHANGE = "state_change"
    INTERACTION = "interaction"

    # 系统事件
    TIME_CHANGE = "time_change"
    WEATHER_CHANGE = "weather_change"

    # 通用
    GENERAL = "general"
    CUSTOM = "custom"


class EventSeverity(IntEnum):
    """事件严重程度"""
    TRIVIAL = 1      # 琐事
    MINOR = 2        # 小事
    MODERATE = 3     # 中等
    MAJOR = 4        # 重大
    CRITICAL = 5     # 危急


class EventPriority(IntEnum):
    """事件优先级"""
    LOW = 1          # 低优先级
    MEDIUM = 2       # 中等优先级
    HIGH = 3         # 高优先级
    CRITICAL = 4     # 危急


class PropagationMethod(Enum):
    """事件传播方式"""
    IMMEDIATE = "immediate"      # 附近立即感知
    GRADUAL = "gradual"          # 按距离渐进传播
    GOSSIP = "gossip"            # 通过社交传播
    ANNOUNCEMENT = "announcement" # 全域公告


class NPCRole(Enum):
    """NPC在事件中的角色"""
    RESCUER = "rescuer"         # 救援者
    HELPER = "helper"           # 帮助者
    ALERTER = "alerter"         # 通知者
    OBSERVER = "observer"       # 观察者
    EVACUEE = "evacuee"         # 撤离者
    VICTIM = "victim"           # 受害者
    PARTICIPANT = "participant" # 参与者
    UNAFFECTED = "unaffected"   # 不受影响


# ==================== 核心事件类 ====================

@dataclass
class Event:
    """
    统一事件类（简化版）

    这是系统中所有事件的标准表示形式。
    设计理念：核心字段最小化，扩展数据放在 data 字典。

    核心字段：
    - id: 唯一标识
    - content: 事件内容（核心：发生了什么）
    - event_type: 事件类型（字符串，支持任意类型）
    - source: 事件来源（NPC名称、"world"、"player"等）
    - location: 事件位置
    - targets: 目标列表（受影响的NPC或实体）
    - importance: 重要程度（0-100）
    - timestamp: 时间戳
    - data: 扩展数据字典（任意额外信息）
    """

    # ===== 核心标识 =====
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.now)

    # ===== 核心内容 =====
    content: str = ""                  # 事件内容（必填）
    event_type: str = "general"        # 事件类型（字符串，灵活）

    # ===== 来源与目标 =====
    source: str = ""                   # 来源（NPC名称、"world"、"player"）
    location: str = ""                 # 位置
    targets: List[str] = field(default_factory=list)  # 目标列表

    # ===== 重要程度 =====
    importance: int = 50               # 0-100

    # ===== 扩展数据 =====
    data: Dict[str, Any] = field(default_factory=dict)

    # ===== 兼容性字段（保留以支持现有代码） =====
    title: str = ""                    # 标题（可选）
    description: str = ""              # 描述（可选）
    is_active: bool = True             # 是否活跃

    # ===== A2：扩展字段（事件树 / 感知 / 经济 / 阶段） =====
    parent_event_id: str = ""
    child_event_ids: List[str] = field(default_factory=list)
    aware_npcs: List[str] = field(default_factory=list)
    reacted_npcs: List[str] = field(default_factory=list)
    gossip_chain: List[str] = field(default_factory=list)
    economic_data: Dict[str, Any] = field(default_factory=dict)
    phase: str = "initial"
    phase_start_time: str = ""
    npc_directives: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理"""
        # 规范化 event_type
        if isinstance(self.event_type, EventType):
            self.event_type = self.event_type.value
        elif isinstance(self.event_type, str):
            self.event_type = self.event_type.lower()

        # 确保 importance 在有效范围
        self.importance = max(0, min(100, self.importance))

        # 如果没有 title，使用 content 的前50个字符
        if not self.title and self.content:
            self.title = self.content[:50] + ("..." if len(self.content) > 50 else "")

    # ===== 快捷访问器 =====

    @property
    def source_npc(self) -> str:
        """兼容：获取来源NPC"""
        return self.source if self.source not in ["world", "player", "system"] else ""

    @property
    def affected_npcs(self) -> List[str]:
        """兼容：获取受影响的NPC列表"""
        return self.targets

    @property
    def notified_npcs(self) -> List[str]:
        """兼容：获取已通知的NPC列表"""
        return self.data.get("notified_npcs", [])

    @property
    def severity(self) -> int:
        """兼容：获取严重程度（从importance映射）"""
        if self.importance >= 80:
            return EventSeverity.CRITICAL
        elif self.importance >= 60:
            return EventSeverity.MAJOR
        elif self.importance >= 40:
            return EventSeverity.MODERATE
        elif self.importance >= 20:
            return EventSeverity.MINOR
        return EventSeverity.TRIVIAL

    @property
    def priority(self) -> int:
        """兼容：获取优先级"""
        return self.data.get("priority", EventPriority.MEDIUM)

    @property
    def propagation_method(self) -> str:
        """兼容：获取传播方式"""
        return self.data.get("propagation_method", "gradual")

    @property
    def propagation_speed(self) -> float:
        """兼容：获取传播速度"""
        return self.data.get("propagation_speed", 1.0)

    @property
    def spatial_range(self) -> float:
        """兼容：获取空间范围"""
        return self.data.get("spatial_range", 50.0)

    @property
    def origin_position(self) -> Tuple[float, float]:
        """兼容：获取原点位置"""
        return tuple(self.data.get("position", (0.0, 0.0)))

    @property
    def impact_score(self) -> int:
        """兼容：获取影响分数"""
        return self.importance

    @property
    def resolved(self) -> bool:
        """兼容：是否已解决"""
        return self.data.get("resolved", False)

    @property
    def metadata(self) -> Dict[str, Any]:
        """兼容：获取元数据"""
        return self.data

    @property
    def analysis(self) -> Dict[str, Any]:
        """兼容：获取分析结果"""
        return self.data.get("analysis", {})

    @property
    def response(self) -> str:
        """兼容：获取响应"""
        return self.data.get("response", "")

    # ===== 状态管理 =====

    def resolve(self, resolution: str = ""):
        """标记事件已解决"""
        self.data["resolved"] = True
        self.is_active = False
        self.data["ended_at"] = datetime.now().isoformat()
        if resolution:
            self.data["resolution"] = resolution

    def deactivate(self):
        """停用事件"""
        self.is_active = False
        self.data["ended_at"] = datetime.now().isoformat()

    def add_notified_npc(self, npc_name: str):
        """添加已通知的NPC"""
        if "notified_npcs" not in self.data:
            self.data["notified_npcs"] = []
        if npc_name not in self.data["notified_npcs"]:
            self.data["notified_npcs"].append(npc_name)

    def add_target(self, target: str):
        """添加目标"""
        if target not in self.targets:
            self.targets.append(target)

    # ===== 兼容方法 =====

    def add_affected_npc(self, npc_name: str):
        """兼容：添加受影响的NPC"""
        self.add_target(npc_name)

    def is_npc_notified(self, npc_name: str) -> bool:
        """检查NPC是否已被通知"""
        return npc_name in self.notified_npcs

    def is_npc_affected(self, npc_name: str) -> bool:
        """检查NPC是否受影响"""
        return npc_name in self.targets

    def is_expired(self) -> bool:
        """检查事件是否过期"""
        expires_at = self.data.get("expires_at")
        if not expires_at:
            return False
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        return datetime.now() > expires_at

    def get_event_type_value(self) -> str:
        """获取事件类型字符串"""
        return self.event_type

    def get_severity_value(self) -> int:
        """获取严重程度值"""
        return int(self.severity)

    def get_priority_value(self) -> int:
        """获取优先级值"""
        return int(self.priority)

    def get_summary(self, max_length: int = 100) -> str:
        """获取事件摘要"""
        text = self.title or self.content
        if len(text) > max_length:
            text = text[:max_length] + "..."
        status = "已解决" if self.resolved else ("进行中" if self.is_active else "已结束")
        return f"[{self.event_type}] {text} (重要度: {self.importance}, {status})"

    def distance_to_position(self, position: Tuple[float, float]) -> float:
        """计算到某位置的距离"""
        origin = self.origin_position
        dx = position[0] - origin[0]
        dy = position[1] - origin[1]
        return (dx**2 + dy**2)**0.5

    def is_position_in_range(self, position: Tuple[float, float]) -> bool:
        """检查位置是否在事件影响范围内"""
        return self.distance_to_position(position) <= self.spatial_range

    # ===== 序列化 =====

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            "content": self.content,
            "event_type": self.event_type,
            "source": self.source,
            "location": self.location,
            "targets": self.targets,
            "importance": self.importance,
            "data": self.data,
            "title": self.title,
            "description": self.description,
            "is_active": self.is_active,
        }

        # 添加兼容字段到输出
        result.update({
            "source_npc": self.source_npc,
            "affected_npcs": self.affected_npcs,
            "notified_npcs": self.notified_npcs,
            "severity": self.get_severity_value(),
            "priority": self.get_priority_value(),
            "impact_score": self.importance,
            "propagation_method": self.propagation_method,
            "resolved": self.resolved,
        })

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """从字典创建Event实例"""
        data = data.copy()

        # 处理时间戳
        if "timestamp" in data and isinstance(data["timestamp"], str):
            try:
                data["timestamp"] = datetime.fromisoformat(data["timestamp"])
            except (ValueError, TypeError):
                data["timestamp"] = datetime.now()

        # 映射旧字段到新结构
        if "source_npc" in data and not data.get("source"):
            data["source"] = data.pop("source_npc")

        if "affected_npcs" in data and not data.get("targets"):
            data["targets"] = data.pop("affected_npcs")

        # 处理 importance / severity 映射
        if "severity" in data and "importance" not in data:
            severity = data.pop("severity")
            if isinstance(severity, int):
                data["importance"] = severity * 20  # 1-5 -> 20-100
            elif isinstance(severity, str):
                severity_map = {"trivial": 10, "minor": 30, "moderate": 50, "major": 70, "critical": 90}
                data["importance"] = severity_map.get(severity.lower(), 50)

        if "impact_score" in data and "importance" not in data:
            data["importance"] = data.pop("impact_score")

        # 将额外字段放入 data
        core_fields = {"id", "timestamp", "content", "event_type", "source", "location",
                       "targets", "importance", "data", "title", "description", "is_active"}
        extra_data = data.get("data", {})
        for key in list(data.keys()):
            if key not in core_fields:
                extra_data[key] = data.pop(key)
        data["data"] = extra_data

        # 过滤有效字段
        valid_fields = {"id", "timestamp", "content", "event_type", "source", "location",
                       "targets", "importance", "data", "title", "description", "is_active"}
        filtered = {k: v for k, v in data.items() if k in valid_fields}

        return cls(**filtered)

    # ===== 工厂方法 =====

    @classmethod
    def create(
        cls,
        content: str,
        event_type: str = "general",
        source: str = "",
        location: str = "",
        targets: List[str] = None,
        importance: int = 50,
        **extra_data
    ) -> 'Event':
        """创建事件的通用方法"""
        return cls(
            content=content,
            event_type=event_type,
            source=source,
            location=location,
            targets=targets or [],
            importance=importance,
            data=extra_data
        )

    @classmethod
    def create_world_event(
        cls,
        content: str,
        location: str,
        event_type: str = "world",
        importance: int = 60,
        **extra_data
    ) -> 'Event':
        """创建世界事件"""
        extra_data.setdefault("propagation_method", "gradual")
        return cls.create(
            content=content,
            event_type=event_type,
            source="world",
            location=location,
            importance=importance,
            **extra_data
        )

    @classmethod
    def create_npc_event(
        cls,
        source_npc: str,
        content: str,
        location: str,
        event_type: str = "action",
        importance: int = 30,
        targets: List[str] = None,
        **extra_data
    ) -> 'Event':
        """创建NPC事件"""
        extra_data.setdefault("propagation_method", "immediate")
        return cls.create(
            content=content,
            event_type=event_type,
            source=source_npc,
            location=location,
            targets=targets,
            importance=importance,
            **extra_data
        )

    @classmethod
    def create_dialogue_event(
        cls,
        source_npc: str,
        content: str,
        location: str,
        target_npcs: List[str] = None,
        importance: int = 20,
        **extra_data
    ) -> 'Event':
        """创建对话事件"""
        extra_data.setdefault("propagation_method", "immediate")
        extra_data.setdefault("spatial_range", 20.0)
        return cls.create(
            content=content,
            event_type="dialogue",
            source=source_npc,
            location=location,
            targets=target_npcs,
            importance=importance,
            **extra_data
        )

    @classmethod
    def create_player_event(
        cls,
        content: str,
        location: str,
        targets: List[str] = None,
        event_type: str = "interaction",
        importance: int = 50,
        **extra_data
    ) -> 'Event':
        """创建玩家事件"""
        return cls.create(
            content=content,
            event_type=event_type,
            source="player",
            location=location,
            targets=targets,
            importance=importance,
            **extra_data
        )

    # ===== 兼容旧API =====

    @property
    def affected_zones(self) -> List[str]:
        """兼容：获取受影响区域"""
        return self.data.get("affected_zones", [self.location] if self.location else [])

    @property
    def max_propagation_radius(self) -> float:
        """兼容：获取最大传播半径"""
        return self.data.get("max_propagation_radius", 100.0)

    @property
    def started_at(self) -> datetime:
        """兼容：获取开始时间"""
        return self.timestamp

    @property
    def ended_at(self) -> Optional[datetime]:
        """兼容：获取结束时间"""
        ended = self.data.get("ended_at")
        if ended and isinstance(ended, str):
            return datetime.fromisoformat(ended)
        return ended

    @property
    def expires_at(self) -> Optional[datetime]:
        """兼容：获取过期时间"""
        expires = self.data.get("expires_at")
        if expires and isinstance(expires, str):
            return datetime.fromisoformat(expires)
        return expires

    def add_child_event(self, event_id: str):
        """兼容：添加子事件（同时写入 dataclass 字段）"""
        if event_id not in self.child_event_ids:
            self.child_event_ids.append(event_id)

    @property
    def related_event_ids(self) -> List[str]:
        """兼容：获取关联事件ID"""
        return self.data.get("related_event_ids", [])

    @property
    def state_before(self) -> Dict[str, Any]:
        """兼容：获取之前状态"""
        return self.data.get("state_before", {})

    @property
    def state_after(self) -> Dict[str, Any]:
        """兼容：获取之后状态"""
        return self.data.get("state_after", {})


# ==================== 事件分析结果（LLM输出） ====================

@dataclass
class EventAnalysis:
    """
    事件分析结果（由LLM生成）

    主Agent分析事件后产生的结构化输出，
    用于协调NPC响应和事件处理。
    """
    event_id: str
    event_content: str
    event_location: str
    event_type: str = "general"

    # 评估结果
    priority: int = EventPriority.MEDIUM
    impact_score: int = 50

    # 影响范围
    affected_zones: List[str] = field(default_factory=list)

    # NPC分配（LLM决定）
    primary_responders: List[str] = field(default_factory=list)
    npc_assignments: Dict[str, str] = field(default_factory=dict)  # NPC名 -> 角色
    suggested_actions: Dict[str, str] = field(default_factory=dict)  # NPC名 -> 建议行动

    # 协调信息
    coordination_notes: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    # 传播相关
    npc_notification_order: List[Dict[str, Any]] = field(default_factory=list)
    propagation_delays: Dict[str, float] = field(default_factory=dict)

    @property
    def affected_npcs(self) -> List[str]:
        """获取所有受影响的NPC"""
        return [
            name for name, role in self.npc_assignments.items()
            if role != "unaffected"
        ]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "event_content": self.event_content,
            "event_location": self.event_location,
            "event_type": self.event_type,
            "priority": self.priority,
            "impact_score": self.impact_score,
            "affected_zones": self.affected_zones,
            "primary_responders": self.primary_responders,
            "npc_assignments": self.npc_assignments,
            "suggested_actions": self.suggested_actions,
            "coordination_notes": self.coordination_notes,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            "npc_notification_order": self.npc_notification_order,
            "propagation_delays": self.propagation_delays
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EventAnalysis':
        """从字典创建实例"""
        data = data.copy()
        if "timestamp" in data and isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class NPCEventResponse:
    """
    NPC事件响应结果（由LLM生成）

    记录NPC对事件的响应，包括思考过程和采取的行动。
    """
    npc_name: str
    role: str                          # 角色（字符串，灵活）
    action_taken: str                  # 采取的行动
    action_type: str = "none"          # 行动类型
    target_location: Optional[str] = None
    speech_content: Optional[str] = None
    thinking_process: str = ""         # LLM的思考过程
    success: bool = True
    error: Optional[str] = None
    execution_time_ms: float = 0

    # 记忆反馈（LLM生成）
    memory_to_store: Optional[str] = None      # 需要存入NPC记忆的内容
    emotion_change: Optional[Dict[str, Any]] = None  # 情感变化
    relationship_change: Optional[Dict[str, Any]] = None  # 关系变化

    @property
    def responded(self) -> bool:
        """是否成功响应"""
        return self.success and self.action_taken not in ["处理失败", "处理超时", "处理异常", ""]

    @property
    def dialogue(self) -> Optional[str]:
        """获取对话内容"""
        return self.speech_content

    @property
    def actions_taken(self) -> List[str]:
        """获取执行的行动列表"""
        if self.action_taken and self.action_taken not in ["处理失败", "处理超时", "处理异常", "未知行动", ""]:
            return [self.action_taken]
        return []

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "npc_name": self.npc_name,
            "role": self.role,
            "action_taken": self.action_taken,
            "action_type": self.action_type,
            "target_location": self.target_location,
            "speech_content": self.speech_content,
            "thinking_process": self.thinking_process,
            "success": self.success,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "memory_to_store": self.memory_to_store,
            "emotion_change": self.emotion_change,
            "relationship_change": self.relationship_change
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NPCEventResponse':
        """从字典创建实例"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ==================== 类型别名（向后兼容） ====================

# 主要别名
UnifiedEvent = Event
WorldEvent = Event
NPCEvent = Event

# 消息类型别名
SpatialMessage = Event
GossipMessage = Event
Message = Event


# ==================== 导出列表 ====================

__all__ = [
    # 枚举类型
    'EventType',
    'EventSeverity',
    'EventPriority',
    'PropagationMethod',
    'NPCRole',

    # 核心类
    'Event',
    'EventAnalysis',
    'NPCEventResponse',

    # 向后兼容别名
    'UnifiedEvent',
    'WorldEvent',
    'NPCEvent',
    'SpatialMessage',
    'GossipMessage',
    'Message',
]
