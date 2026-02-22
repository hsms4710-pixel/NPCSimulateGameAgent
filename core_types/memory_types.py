# -*- coding: utf-8 -*-
"""
统一记忆类型定义
===============

集中管理所有记忆系统相关的数据类，解决以下问题：
1. Memory 在多处定义结构不同
2. add_memory 接口签名不统一
3. 记忆检索方法命名不一致

类型说明：
- UnifiedMemory: 统一的记忆数据类
- UnifiedGoal: 统一的目标数据类
- UnifiedRelationship: 统一的人际关系数据类
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid


@dataclass
class UnifiedMemory:
    """
    统一的记忆数据类

    合并了:
    - npc_core/data_models.py 中的 Memory
    - npc_persistence.py 中的 memories 结构
    - rag_memory.py 中的记忆格式

    属性说明：
    - importance: 重要性 1-10 (整数)
    - emotional_impact: 情感影响 -10 到 +10
    """
    # 基础标识
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    content: str = ""

    # 时间信息
    timestamp: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    # 记忆属性
    memory_type: str = "一般"     # 对应 MemoryType.value
    importance: int = 5           # 1-10
    emotional_impact: int = 0     # -10 到 +10

    # 标签和关联
    tags: List[str] = field(default_factory=list)
    related_npcs: List[str] = field(default_factory=list)
    related_events: List[str] = field(default_factory=list)
    related_locations: List[str] = field(default_factory=list)

    # 访问统计
    access_count: int = 0
    last_accessed: Optional[datetime] = None

    # 向量嵌入（用于RAG检索）
    embedding: Optional[List[float]] = None

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理"""
        # 确保重要性在有效范围
        self.importance = max(1, min(10, self.importance))
        # 确保情感影响在有效范围
        self.emotional_impact = max(-10, min(10, self.emotional_impact))

    def access(self):
        """记录一次访问"""
        self.access_count += 1
        self.last_accessed = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（不含embedding以节省空间）"""
        return {
            'id': self.id,
            'content': self.content,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'memory_type': self.memory_type,
            'importance': self.importance,
            'emotional_impact': self.emotional_impact,
            'tags': self.tags,
            'related_npcs': self.related_npcs,
            'related_events': self.related_events,
            'related_locations': self.related_locations,
            'access_count': self.access_count,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'metadata': self.metadata
        }

    def to_dict_full(self) -> Dict[str, Any]:
        """转换为完整字典（含embedding）"""
        data = self.to_dict()
        data['embedding'] = self.embedding
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedMemory':
        """从字典创建"""
        # 处理时间字段
        for field_name in ['timestamp', 'created_at', 'last_accessed']:
            if field_name in data and isinstance(data[field_name], str):
                try:
                    data[field_name] = datetime.fromisoformat(data[field_name])
                except (ValueError, TypeError):
                    data[field_name] = datetime.now() if field_name != 'last_accessed' else None
        return cls(**data)

    def get_summary(self, max_length: int = 100) -> str:
        """获取记忆摘要"""
        content = self.content[:max_length] + "..." if len(self.content) > max_length else self.content
        return f"[{self.memory_type}] {content} (重要性: {self.importance})"

    @property
    def is_significant(self) -> bool:
        """判断是否为重要记忆"""
        return self.importance >= 7 or abs(self.emotional_impact) >= 5

    @property
    def type(self) -> str:
        """兼容旧代码的类型属性"""
        return self.memory_type

    @type.setter
    def type(self, value: str):
        self.memory_type = value


@dataclass
class UnifiedGoal:
    """
    统一的目标数据类

    合并了 npc_core/data_models.py 中的 Goal
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    priority: int = 5              # 1-10
    status: str = "进行中"         # 进行中, 已完成, 失败, 已暂停, 已取消
    progress: float = 0.0          # 0.0-1.0
    created_at: datetime = field(default_factory=datetime.now)
    deadline: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    sub_goals: List[str] = field(default_factory=list)
    related_memories: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.priority = max(1, min(10, self.priority))
        self.progress = max(0.0, min(1.0, self.progress))

    def update_progress(self, new_progress: float):
        """更新进度"""
        self.progress = max(0.0, min(1.0, new_progress))
        if self.progress >= 1.0:
            self.status = "已完成"
            self.completed_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'description': self.description,
            'priority': self.priority,
            'status': self.status,
            'progress': self.progress,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'sub_goals': self.sub_goals,
            'related_memories': self.related_memories,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedGoal':
        for field_name in ['created_at', 'deadline', 'completed_at']:
            if field_name in data and isinstance(data[field_name], str):
                try:
                    data[field_name] = datetime.fromisoformat(data[field_name])
                except (ValueError, TypeError):
                    data[field_name] = None if field_name != 'created_at' else datetime.now()
        return cls(**data)


@dataclass
class UnifiedRelationship:
    """
    统一的人际关系数据类

    合并了 npc_core/data_models.py 中的 Relationship
    """
    # 关系双方
    npc_name: str                 # 关系对象的名称
    relationship_type: str = "熟人"  # 朋友, 家人, 敌人, 熟人, 陌生人, 同事, 恋人

    # 关系数值 (统一为 -100 到 +100)
    affection: int = 0            # 好感度 -100 到 +100
    trust: int = 50               # 信任度 0-100
    respect: int = 50             # 尊重度 0-100
    familiarity: int = 0          # 熟悉度 0-100

    # 互动统计
    interactions_count: int = 0
    positive_interactions: int = 0
    negative_interactions: int = 0
    last_interaction: Optional[datetime] = None

    # 关系历史
    shared_memories: List[str] = field(default_factory=list)  # 共同记忆ID
    relationship_events: List[str] = field(default_factory=list)  # 关系事件

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.affection = max(-100, min(100, self.affection))
        self.trust = max(0, min(100, self.trust))
        self.respect = max(0, min(100, self.respect))
        self.familiarity = max(0, min(100, self.familiarity))

    def record_interaction(self, is_positive: bool = True):
        """记录一次互动"""
        self.interactions_count += 1
        self.last_interaction = datetime.now()
        if is_positive:
            self.positive_interactions += 1
            self.affection = min(100, self.affection + 1)
        else:
            self.negative_interactions += 1
            self.affection = max(-100, self.affection - 1)

    def update_relationship_type(self):
        """根据数值自动更新关系类型"""
        if self.affection >= 80 and self.trust >= 70:
            self.relationship_type = "挚友"
        elif self.affection >= 50:
            self.relationship_type = "朋友"
        elif self.affection <= -50:
            self.relationship_type = "敌人"
        elif self.familiarity >= 30:
            self.relationship_type = "熟人"
        else:
            self.relationship_type = "陌生人"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'npc_name': self.npc_name,
            'relationship_type': self.relationship_type,
            'affection': self.affection,
            'trust': self.trust,
            'respect': self.respect,
            'familiarity': self.familiarity,
            'interactions_count': self.interactions_count,
            'positive_interactions': self.positive_interactions,
            'negative_interactions': self.negative_interactions,
            'last_interaction': self.last_interaction.isoformat() if self.last_interaction else None,
            'shared_memories': self.shared_memories,
            'relationship_events': self.relationship_events,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedRelationship':
        for field_name in ['last_interaction', 'created_at']:
            if field_name in data and isinstance(data[field_name], str):
                try:
                    data[field_name] = datetime.fromisoformat(data[field_name])
                except (ValueError, TypeError):
                    data[field_name] = None if field_name == 'last_interaction' else datetime.now()
        return cls(**data)

    @property
    def relationship_score(self) -> float:
        """计算综合关系分数 (0-100)"""
        # 将好感度从 -100~100 映射到 0~100
        normalized_affection = (self.affection + 100) / 2
        # 加权平均
        return (normalized_affection * 0.4 + self.trust * 0.3 +
                self.respect * 0.15 + self.familiarity * 0.15)


# ==================== 类型别名（向后兼容） ====================

Memory = UnifiedMemory
Goal = UnifiedGoal
Relationship = UnifiedRelationship
