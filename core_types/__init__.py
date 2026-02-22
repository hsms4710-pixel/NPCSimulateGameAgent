# -*- coding: utf-8 -*-
"""
统一类型定义模块
===============

集中管理项目中所有核心类型定义，避免重复定义和接口不一致。

模块结构：
- enums.py: 所有枚举类型
- npc_types.py: NPC相关数据类
- memory_types.py: 记忆系统相关数据类
- event_types.py: 事件系统相关数据类

使用方式：
    from core_types import NPCAction, Emotion, UnifiedNPCState, UnifiedMemory

或者：
    from core_types.enums import NPCAction, Emotion
    from core_types.npc_types import UnifiedNPCState
"""

from .enums import (
    # NPC行为枚举
    NPCAction,
    NPCActivity,  # 兼容别名
    # 情感枚举
    Emotion,
    # 推理模式枚举
    ReasoningMode,
    # Agent状态枚举
    AgentState,
    # 消息类型枚举
    MessageType,
    # 消息优先级枚举
    MessagePriority,
    # 事件优先级枚举
    EventPriority,
    # NPC角色枚举
    NPCRole,
    # 记忆类型枚举
    MemoryType,
    # 任务状态枚举
    TaskStatus,
    # 常量
    ACTIVITY_INERTIA,
    ACTIVITY_PRIORITY_CRITICAL,
    ACTIVITY_PRIORITY_IMPORTANT,
    ACTIVITY_PRIORITY_NORMAL,
    ACTIVITY_PRIORITY_LOW,
    ACTIVITY_PRIORITY_SLEEP,
    ENERGY_CRITICAL_THRESHOLD,
    HUNGER_CRITICAL_THRESHOLD,
    FATIGUE_CRITICAL_THRESHOLD,
    SLEEP_FORCED_THRESHOLD,
    TASK_MIN_PROGRESS_STEP,
    TASK_PROGRESS_CHECK_INTERVAL,
    TASK_LLM_RECHECK_THRESHOLD,
)

from .npc_types import (
    UnifiedNPCState,
    UnifiedNeedState,
    NPCScheduleEntry,
    NPCTask,
    # 兼容别名
    NPCState,
    NeedState,
)

from .memory_types import (
    UnifiedMemory,
    UnifiedGoal,
    UnifiedRelationship,
    # 兼容别名
    Memory,
    Goal,
    Relationship,
)

from .event_types import (
    # 核心事件类
    Event,
    EventAnalysis,
    NPCEventResponse,
    # 事件枚举
    EventType,
    EventSeverity,
    EventPriority as EventPriorityEnum,  # 避免与 enums.py 冲突
    PropagationMethod,
    NPCRole as EventNPCRole,  # 避免与 enums.py 冲突
    # 兼容别名
    UnifiedEvent,
    WorldEvent,
    NPCEvent,
    SpatialMessage,
    GossipMessage,
    Message,
)

__all__ = [
    # 枚举
    'NPCAction',
    'NPCActivity',
    'Emotion',
    'ReasoningMode',
    'AgentState',
    'MessageType',
    'MessagePriority',
    'EventPriority',
    'NPCRole',
    'MemoryType',
    'TaskStatus',
    # NPC类型
    'UnifiedNPCState',
    'UnifiedNeedState',
    'NPCScheduleEntry',
    'NPCTask',
    'NPCState',
    'NeedState',
    # 记忆类型
    'UnifiedMemory',
    'UnifiedGoal',
    'UnifiedRelationship',
    'Memory',
    'Goal',
    'Relationship',
    # 事件类型 - 核心
    'Event',
    'EventAnalysis',
    'NPCEventResponse',
    # 事件类型 - 枚举
    'EventType',
    'EventSeverity',
    'EventPriorityEnum',
    'PropagationMethod',
    'EventNPCRole',
    # 事件类型 - 兼容别名
    'UnifiedEvent',
    'WorldEvent',
    'NPCEvent',
    'SpatialMessage',
    'GossipMessage',
    'Message',
    # 常量
    'ACTIVITY_INERTIA',
    'ACTIVITY_PRIORITY_CRITICAL',
    'ACTIVITY_PRIORITY_IMPORTANT',
    'ACTIVITY_PRIORITY_NORMAL',
    'ACTIVITY_PRIORITY_LOW',
    'ACTIVITY_PRIORITY_SLEEP',
    'ENERGY_CRITICAL_THRESHOLD',
    'HUNGER_CRITICAL_THRESHOLD',
    'FATIGUE_CRITICAL_THRESHOLD',
    'SLEEP_FORCED_THRESHOLD',
    'TASK_MIN_PROGRESS_STEP',
    'TASK_PROGRESS_CHECK_INTERVAL',
    'TASK_LLM_RECHECK_THRESHOLD',
]
