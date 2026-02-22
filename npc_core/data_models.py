"""
NPC 数据模型定义

包含 NPC 系统使用的所有数据类：
- Memory: 记忆数据类
- Goal: 目标数据类
- Relationship: 人际关系数据类
- NeedState: 需求状态数据类
"""

from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class Memory:
    """记忆数据类"""
    content: str
    emotional_impact: int  # -10 到 +10
    importance: int  # 1-10
    timestamp: datetime
    tags: List[str] = field(default_factory=list)
    related_npcs: List[str] = field(default_factory=list)


@dataclass
class Goal:
    """目标数据类"""
    description: str
    priority: int  # 1-10
    deadline: Optional[datetime] = None
    progress: float = 0.0  # 0.0-1.0
    sub_goals: List[str] = field(default_factory=list)
    status: str = "active"  # active, completed, failed, paused


@dataclass
class Relationship:
    """人际关系数据类"""
    npc_name: str
    affection: int  # -100 到 +100
    trust: int  # 0-100
    interactions_count: int = 0
    last_interaction: Optional[datetime] = None
    relationship_type: str = "acquaintance"  # friend, family, enemy, etc.


@dataclass
class NeedState:
    """需求状态数据类"""
    hunger: float = 0.0  # 饥饿程度 0-1
    fatigue: float = 0.0  # 疲劳程度 0-1
    social: float = 0.0  # 社交需求 0-1
    security: float = 0.0  # 安全需求 0-1
    achievement: float = 0.0  # 成就需求 0-1
    last_updated: datetime = field(default_factory=datetime.now)
