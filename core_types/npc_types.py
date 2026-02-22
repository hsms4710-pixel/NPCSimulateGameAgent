# -*- coding: utf-8 -*-
"""
统一NPC类型定义
==============

集中管理所有NPC相关的数据类，解决以下问题：
1. NPCState 在多处定义结构不同
2. 需求状态访问方式不统一
3. 能量/饥饿/疲劳值范围不统一

类型说明：
- UnifiedNPCState: 统一的NPC状态类
- UnifiedNeedState: 统一的需求状态类
- NPCScheduleEntry: 日程条目类
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid

# 使用相对导入以避免循环依赖问题
# 在实际使用中，请确保 types 模块已正确加载


class NPCActionMixin:
    """NPCAction 的占位符，避免循环导入"""
    pass


@dataclass
class UnifiedNeedState:
    """
    统一的需求状态数据类

    所有数值范围统一为 0.0-1.0：
    - 0.0 表示完全满足
    - 1.0 表示极度需要

    例如：hunger=0.0 表示不饿，hunger=1.0 表示极度饥饿
    """
    hunger: float = 0.0       # 饥饿程度 0.0-1.0
    fatigue: float = 0.0      # 疲劳程度 0.0-1.0
    social: float = 0.0       # 社交需求 0.0-1.0
    security: float = 0.0     # 安全需求 0.0-1.0
    achievement: float = 0.0  # 成就需求 0.0-1.0
    last_updated: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """确保所有值在有效范围内"""
        self.hunger = max(0.0, min(1.0, self.hunger))
        self.fatigue = max(0.0, min(1.0, self.fatigue))
        self.social = max(0.0, min(1.0, self.social))
        self.security = max(0.0, min(1.0, self.security))
        self.achievement = max(0.0, min(1.0, self.achievement))

    def is_critical(self, need_type: str, threshold: float = 0.9) -> bool:
        """检查某个需求是否达到临界值"""
        value = getattr(self, need_type, 0.0)
        return value >= threshold

    def get_most_urgent_need(self) -> tuple:
        """获取最紧急的需求"""
        needs = {
            'hunger': self.hunger,
            'fatigue': self.fatigue,
            'social': self.social,
            'security': self.security,
            'achievement': self.achievement
        }
        most_urgent = max(needs.items(), key=lambda x: x[1])
        return most_urgent  # (need_name, value)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'hunger': self.hunger,
            'fatigue': self.fatigue,
            'social': self.social,
            'security': self.security,
            'achievement': self.achievement,
            'last_updated': self.last_updated.isoformat() if isinstance(self.last_updated, datetime) else self.last_updated
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedNeedState':
        """从字典创建"""
        if 'last_updated' in data and isinstance(data['last_updated'], str):
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        return cls(**data)


@dataclass
class UnifiedNPCState:
    """
    统一的NPC状态类

    合并了:
    - npc_persistence.py 中的 NPCState
    - npc_lifecycle.py 中的 NPCState
    - backend/npc_agent.py 中的 NPCState

    属性说明：
    - 基础属性使用中文值，便于显示
    - 能量值统一为 0.0-1.0 浮点数
    """
    # 基础标识
    name: str
    npc_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # 位置信息
    location: str = "未知"

    # 当前活动（字符串，对应 NPCAction.value）
    current_activity: str = "空闲"

    # 需求状态
    needs: UnifiedNeedState = field(default_factory=UnifiedNeedState)

    # 情感状态（字符串，对应 Emotion.value）
    emotion: str = "平静"
    mood: str = "平静"

    # 能量值 (0.0-1.0，1.0为满能量)
    energy: float = 1.0

    # 警觉度 (0.0-1.0)
    alertness: float = 0.5

    # 状态标志
    is_busy: bool = False
    is_sleeping: bool = False

    # 任务相关
    current_task_id: Optional[str] = None
    current_task_description: Optional[str] = None

    # 时间戳
    last_update: datetime = field(default_factory=datetime.now)
    last_activity_change: Optional[datetime] = None

    # 连续状态计数
    consecutive_rest_hours: int = 0

    # 已知事件
    known_events: List[str] = field(default_factory=list)

    # ===== 经济状态（A1：绑在NPC实体上）=====
    gold: int = 0
    silver: int = 0
    copper: int = 0
    inventory: List[Dict[str, Any]] = field(default_factory=list)
    # [{"item_id": str, "qty": int, "durability": Optional[float]}]

    # ===== 关系状态（A1）=====
    relationships: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # {"人名": {"affection": 50, "trust": 60, "type": "friend", "interactions": 3}}

    # ===== 住宿状态（A1）=====
    home_location: str = ""
    current_lodging: str = ""
    rent_paid_until: str = ""   # 世界时间 ISO 字符串

    # ===== 工作状态（A1）=====
    employer: str = ""
    work_location: str = ""
    daily_wage: int = 0
    work_shift_start: int = 8
    work_shift_end: int = 18

    # ===== 任务状态（A1）=====
    active_tasks: List[Dict[str, Any]] = field(default_factory=list)
    # [{"id", "desc", "type", "parent_event_id", "status", "sub_tasks": [...], "rewards": {...}}]

    def __post_init__(self):
        """初始化后处理"""
        # 确保能量在有效范围
        self.energy = max(0.0, min(1.0, self.energy))
        self.alertness = max(0.0, min(1.0, self.alertness))

        # 确保 needs 是 UnifiedNeedState 类型
        if isinstance(self.needs, dict):
            self.needs = UnifiedNeedState(**self.needs)

    # ==================== 方法 ====================

    def update_activity(self, new_activity: str):
        """更新当前活动"""
        self.current_activity = new_activity
        self.last_activity_change = datetime.now()
        self.is_sleeping = (new_activity == "睡觉")

    def add_known_event(self, event_id: str):
        """添加已知事件"""
        if event_id not in self.known_events:
            self.known_events.append(event_id)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'npc_id': self.npc_id,
            'location': self.location,
            'current_activity': self.current_activity,
            'needs': self.needs.to_dict(),
            'emotion': self.emotion,
            'mood': self.mood,
            'energy': self.energy,
            'alertness': self.alertness,
            'is_busy': self.is_busy,
            'is_sleeping': self.is_sleeping,
            'current_task_id': self.current_task_id,
            'current_task_description': self.current_task_description,
            'last_update': self.last_update.isoformat() if isinstance(self.last_update, datetime) else self.last_update,
            'last_activity_change': self.last_activity_change.isoformat() if self.last_activity_change else None,
            'consecutive_rest_hours': self.consecutive_rest_hours,
            'known_events': self.known_events,
            # 经济状态
            'gold': self.gold,
            'silver': self.silver,
            'copper': self.copper,
            'inventory': self.inventory,
            # 关系状态
            'relationships': self.relationships,
            # 住宿状态
            'home_location': self.home_location,
            'current_lodging': self.current_lodging,
            'rent_paid_until': self.rent_paid_until,
            # 工作状态
            'employer': self.employer,
            'work_location': self.work_location,
            'daily_wage': self.daily_wage,
            'work_shift_start': self.work_shift_start,
            'work_shift_end': self.work_shift_end,
            # 任务状态
            'active_tasks': self.active_tasks,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedNPCState':
        """从字典创建"""
        # 处理时间字段
        if 'last_update' in data and isinstance(data['last_update'], str):
            data['last_update'] = datetime.fromisoformat(data['last_update'])
        if 'last_activity_change' in data and isinstance(data['last_activity_change'], str):
            data['last_activity_change'] = datetime.fromisoformat(data['last_activity_change'])
        # 处理 needs 字段
        if 'needs' in data and isinstance(data['needs'], dict):
            data['needs'] = UnifiedNeedState.from_dict(data['needs'])
        return cls(**data)

    def get_summary(self) -> str:
        """获取状态摘要（用于LLM提示）"""
        return (
            f"姓名: {self.name}\n"
            f"位置: {self.location}\n"
            f"当前活动: {self.current_activity}\n"
            f"情绪: {self.emotion}\n"
            f"能量: {int(self.energy * 100)}%\n"
            f"饥饿: {int(self.needs.hunger * 100)}%\n"
            f"疲劳: {int(self.needs.fatigue * 100)}%\n"
            f"状态: {'忙碌' if self.is_busy else '空闲'}"
        )


@dataclass
class NPCScheduleEntry:
    """
    NPC日程条目

    用于定义NPC在特定时间段的计划活动和位置
    """
    time_slot: str           # 时间段标识，如 "dawn", "morning", "noon"
    activity: str            # 活动，对应 NPCAction.value
    location: str            # 位置
    priority: int = 50       # 优先级 (0-100)
    is_mandatory: bool = False  # 是否强制执行

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NPCTask:
    """
    统一的NPC任务类

    合并了不同模块中的任务定义
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    task_type: str = "short_term"  # short_term, long_term, event_response
    priority: int = 50             # 0-100
    status: str = "pending"        # pending, active, completed, failed, paused, cancelled
    created_at: datetime = field(default_factory=datetime.now)
    deadline: Optional[datetime] = None
    progress: float = 0.0          # 0.0-1.0
    related_events: List[str] = field(default_factory=list)
    related_npcs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'description': self.description,
            'task_type': self.task_type,
            'priority': self.priority,
            'status': self.status,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'progress': self.progress,
            'related_events': self.related_events,
            'related_npcs': self.related_npcs,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NPCTask':
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'deadline' in data and isinstance(data['deadline'], str):
            data['deadline'] = datetime.fromisoformat(data['deadline'])
        return cls(**data)


# ==================== 类型别名（向后兼容） ====================

# 旧名称别名
NeedState = UnifiedNeedState
NPCState = UnifiedNPCState
