# -*- coding: utf-8 -*-
"""
世界模拟器模块
整合玩家系统、NPC系统、世界事件系统、经济系统、任务系统
"""

from .player_system import (
    PlayerCharacter,
    PlayerAction,
    PlayerPreset,
    PlayerNeeds,
    Gender,
    Personality,
    Profession,
    get_available_presets,
    PLAYER_PRESETS
)
from .world_manager import WorldManager, WorldTime, TimeOfDay, WORLD_LOCATIONS
from .event_system import (
    WorldEventTrigger,
    EventPropagation,
    Event,
    WorldEvent,
    EventType,
    EventSeverity,
    EventPriority,
    PropagationMethod,
    EVENT_TEMPLATES
)
from .npc_lifecycle import (
    NPCLifecycleManager,
    NPCState,
    NPCSchedule,
    NPCActivity,
    get_npc_schedules,
    clear_schedules_cache
)
from .parallel_npc_system import (
    GameTime,
    AgentState,
    ScheduledEvent,
    SimulationClock,
    EventScheduler,
    NPCAgent,
    WorldSimulator,
    create_world_simulator,
    run_simple_simulation
)
from .economy_system import (
    # 货币相关
    CurrencyManager,
    CurrencyType,
    Transaction,
    CURRENCY_RATES,
    # 物品相关
    ItemRegistry,
    Item,
    ItemCategory,
    ItemRarity,
    InventoryItem,
    # 市场相关
    MarketSystem,
    # 库存相关
    InventoryManager,
    # 整合类
    EconomySystem
)
from .quest_system import (
    # 任务目标
    QuestObjective,
    ObjectiveType,
    # 任务奖励
    QuestReward,
    # 任务
    Quest,
    QuestStatus,
    QuestType,
    QuestDifficulty,
    # 任务触发器
    QuestTrigger,
    # 任务管理器
    QuestManager,
    # 模板
    QUEST_TEMPLATES
)

# 世界时钟和世界观模块
from .world_clock import WorldClock, get_world_clock, reset_world_clock
from .world_lore import WORLD_LORE, NPC_TEMPLATES, ENVIRONMENTAL_EVENTS

# 世界生成器
from .world_generator import (
    WorldGenerator,
    WorldConfig,
    LocationConfig,
    NPCTemplate,
    WorldTheme,
    THEME_TEMPLATES,
    create_world
)

__all__ = [
    # 玩家系统
    'PlayerCharacter',
    'PlayerAction',
    'PlayerPreset',
    'PlayerNeeds',
    'Gender',
    'Personality',
    'Profession',
    'get_available_presets',
    'PLAYER_PRESETS',

    # 世界管理
    'WorldManager',
    'WorldTime',
    'TimeOfDay',
    'WORLD_LOCATIONS',

    # 事件系统
    'WorldEventTrigger',
    'EventPropagation',
    'Event',
    'WorldEvent',
    'EventType',
    'EventSeverity',
    'EventPriority',
    'PropagationMethod',
    'EVENT_TEMPLATES',

    # NPC生命周期
    'NPCLifecycleManager',
    'NPCState',
    'NPCSchedule',
    'NPCActivity',
    'get_npc_schedules',
    'clear_schedules_cache',

    # 多NPC并行系统
    'GameTime',
    'AgentState',
    'ScheduledEvent',
    'SimulationClock',
    'EventScheduler',
    'NPCAgent',
    'WorldSimulator',
    'create_world_simulator',
    'run_simple_simulation',

    # 经济系统 - 货币
    'CurrencyManager',
    'CurrencyType',
    'Transaction',
    'CURRENCY_RATES',

    # 经济系统 - 物品
    'ItemRegistry',
    'Item',
    'ItemCategory',
    'ItemRarity',
    'InventoryItem',

    # 经济系统 - 市场
    'MarketSystem',

    # 经济系统 - 库存
    'InventoryManager',

    # 经济系统 - 整合
    'EconomySystem',

    # 任务系统 - 目标
    'QuestObjective',
    'ObjectiveType',

    # 任务系统 - 奖励
    'QuestReward',

    # 任务系统 - 任务
    'Quest',
    'QuestStatus',
    'QuestType',
    'QuestDifficulty',

    # 任务系统 - 触发器
    'QuestTrigger',

    # 任务系统 - 管理器
    'QuestManager',

    # 任务系统 - 模板
    'QUEST_TEMPLATES',

    # 世界时钟
    'WorldClock',
    'get_world_clock',
    'reset_world_clock',

    # 世界观
    'WORLD_LORE',
    'NPC_TEMPLATES',
    'ENVIRONMENTAL_EVENTS',

    # 世界生成器
    'WorldGenerator',
    'WorldConfig',
    'LocationConfig',
    'NPCTemplate',
    'WorldTheme',
    'THEME_TEMPLATES',
    'create_world',
]
