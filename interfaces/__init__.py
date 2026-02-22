# -*- coding: utf-8 -*-
"""
接口协议定义模块
===============

定义系统中各组件的标准接口协议，确保接口一致性。

模块结构：
- memory_interface.py: 记忆系统接口
- npc_interface.py: NPC注册和管理接口
- event_interface.py: 事件系统接口

使用方式：
    from interfaces import MemoryInterface, NPCRegistryInterface, EventInterface

    class MyMemorySystem(MemoryInterface):
        def add_memory(self, content: str, ...) -> str:
            ...
"""

from .memory_interface import (
    MemoryInterface,
    MemorySearchResult,
    BaseMemorySystem,
)

from .npc_interface import (
    NPCRegistryInterface,
    NPCStateInterface,
    BaseNPCRegistry,
    Position,
)

from .event_interface import (
    EventInterface,
    EventHandlerInterface,
    BaseEventSystem,
)

__all__ = [
    # 记忆接口
    'MemoryInterface',
    'MemorySearchResult',
    'BaseMemorySystem',
    # NPC接口
    'NPCRegistryInterface',
    'NPCStateInterface',
    'BaseNPCRegistry',
    'Position',
    # 事件接口
    'EventInterface',
    'EventHandlerInterface',
    'BaseEventSystem',
]
