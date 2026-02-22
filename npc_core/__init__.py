"""
NPC Core 模块

这个模块将原来的 npc_system.py 拆分为多个更小的模块，提供更好的代码组织和可维护性。

模块结构：
- data_models.py: 数据类定义 (Memory, Goal, Relationship, NeedState)
- environment.py: 环境感知和需求管理 (EnvironmentPerception, NeedSystem)
- npc_base.py: NPC 基础类和初始化
- npc_autonomous.py: 自主行为循环相关方法
- npc_events.py: 事件处理相关方法
- npc_dialogue.py: 对话和记忆相关方法

使用方式：
    from npc_core import (
        NPCBehaviorSystem,
        Memory,
        Goal,
        Relationship,
        NeedState,
        EnvironmentPerception,
        NeedSystem
    )
"""

# 导入数据模型
from .data_models import (
    Memory,
    Goal,
    Relationship,
    NeedState
)

# 导入环境感知系统
from .environment import (
    EnvironmentPerception,
    NeedSystem
)

# 导入基础类
from .npc_base import NPCBehaviorSystemBase

# 导入混入类
from .npc_autonomous import NPCAutonomousMixin
from .npc_events import NPCEventsMixin
from .npc_dialogue import NPCDialogueMixin

# 导入持久化模块
from .npc_persistence import NPCPersistence, NPCTask, NPCEvent

# 导入NPC注册表
from .npc_registry import (
    NPCRegistry,
    NPCRegistryEntry,
    NPCLifecycleStatus,
    NPCType,
    get_npc_registry,
    reset_npc_registry
)

# 导入所需的类型
from typing import Dict, Any
from backend.deepseek_client import DeepSeekClient


class NPCBehaviorSystem(
    NPCBehaviorSystemBase,
    NPCAutonomousMixin,
    NPCEventsMixin,
    NPCDialogueMixin
):
    """
    NPC复杂行为系统 - 基于持久化的事件驱动架构

    这个类通过多重继承组合了多个混入类的功能：
    - NPCBehaviorSystemBase: 核心初始化和基础方法
    - NPCAutonomousMixin: 自主行为循环相关方法
    - NPCEventsMixin: 事件处理相关方法
    - NPCDialogueMixin: 对话和记忆相关方法

    使用方式：
        from npc_core import NPCBehaviorSystem
        npc = NPCBehaviorSystem(npc_config, deepseek_client)
    """

    def __init__(self, npc_config: Dict[str, Any], deepseek_client: DeepSeekClient):
        """
        初始化 NPC 行为系统

        Args:
            npc_config: NPC 配置字典
            deepseek_client: DeepSeek LLM 客户端
        """
        # 调用基础类的初始化方法
        super().__init__(npc_config, deepseek_client)


# 导出所有公共类
__all__ = [
    # 主类
    'NPCBehaviorSystem',

    # 数据模型
    'Memory',
    'Goal',
    'Relationship',
    'NeedState',

    # 环境系统
    'EnvironmentPerception',
    'NeedSystem',

    # 基础类和混入类（用于扩展）
    'NPCBehaviorSystemBase',
    'NPCAutonomousMixin',
    'NPCEventsMixin',
    'NPCDialogueMixin',

    # 持久化
    'NPCPersistence',
    'NPCTask',
    'NPCEvent',

    # NPC注册表
    'NPCRegistry',
    'NPCRegistryEntry',
    'NPCLifecycleStatus',
    'NPCType',
    'get_npc_registry',
    'reset_npc_registry',
]
