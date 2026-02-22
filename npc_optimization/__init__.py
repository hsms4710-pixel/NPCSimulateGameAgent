"""
NPC系统优化模块
包含上下文压缩、行为决策树、记忆管理等优化功能
"""

from .context_compressor import ContextCompressor
from .behavior_decision_tree import BehaviorDecisionTree
from .prompt_templates import PromptTemplates
from .memory_manager import MemoryManager, MemorySummarizer, Episode, CompressedMemory
from .react_tools import NPCToolRegistry, ReActAgent, NPCActionTool
from .rag_memory import RAGMemorySystem, SimpleVectorStore

# 新增的高级功能模块
from .memory_layers import (
    MemoryLayerManager,
    HotMemory,
    WarmMemory,
    ColdMemory,
    NPCEventEnhanced,
    Insight,
    Episode as MemoryEpisode
)
from .four_level_decisions import (
    FourLevelDecisionMaker,
    L1RoutineDecision,
    L2FastFilter,
    L3StrategyPlanning,
    L4ToTReactReasoning,
    DecisionLevel
)
from .persona_world_integration import (
    PersonaCard,
    WorldCardView,
    PersonaWorldIntegrator,
    PersonalCharacterMigrationTask,
    DynamicPersonaUpdateManager
)
from .world_event_manager import (
    WorldEventManager,
    SpatialMessage,
    GossipMessage,
    NPCToolRegistry_SocialExtension,
    MessageType
)
from .reflection_flow import (
    ReflectionFlowManager,
    ReflectionEngine,
    ReflectionTask,
    ReflectionResult,
    ReflectionType
)

# P2新增：消息总线和空间系统
from .message_bus import (
    NPCMessageBus,
    Message,
    MessageType as BusMessageType,
    MessagePriority,
    Subscription,
    get_message_bus,
    reset_message_bus
)
from .spatial_system import (
    SpatialSystem,
    Location,
    NPCPosition,
    ZoneType,
    get_spatial_system,
    reset_spatial_system
)

# P2新增：事件协调器（主Agent）
from .event_coordinator import (
    EventCoordinator,
    EventAnalysis,
    NPCEventResponse,
    NPCRole,
    EventPriority,
    get_event_coordinator,
    set_coordinator_llm_client
)

# P2新增：统一工具系统
from .unified_tools import (
    UnifiedTool,
    UnifiedToolRegistry,
    ToolCategory,
    UNIFIED_TOOLS,
    get_unified_tools_prompt,
    parse_tool_call
)

# P3新增：LLM事件处理器
from .llm_event_processor import (
    LLMEventProcessor,
    MemoryFeedback,
    EventProcessingResult,
    process_event_with_llm
)

# P3新增：事件推进系统
from .event_progression import (
    EventProgressionSystem,
    EventPhase,
    EventState,
    EventProgression
)

# P3新增：动态世界管理
from .dynamic_world import (
    DynamicWorldManager,
    DynamicNPC,
    NPCStatus,
    EventOutcome,
    EventJudgment,
    get_world_manager,
    reset_world_manager
)

# P3新增：三方交互系统（世界-NPC-玩家）
from .tripartite_interaction import (
    InteractionManager,
    TripartiteMemory,
    InstantiationJudge,
    UninstantiatedEntity,
    InteractionType,
    MemoryEntry,
    EntityType,
)

__all__ = [
    'ContextCompressor',
    'BehaviorDecisionTree',
    'PromptTemplates',
    'MemoryManager',
    'MemorySummarizer',
    'Episode',
    'CompressedMemory',
    'NPCToolRegistry',
    'ReActAgent',
    'NPCActionTool',
    'RAGMemorySystem',
    'SimpleVectorStore',
    # 分层记忆
    'MemoryLayerManager',
    'HotMemory',
    'WarmMemory',
    'ColdMemory',
    'NPCEventEnhanced',
    'Insight',
    'MemoryEpisode',
    # 四级决策
    'FourLevelDecisionMaker',
    'L1RoutineDecision',
    'L2FastFilter',
    'L3StrategyPlanning',
    'L4ToTReactReasoning',
    'DecisionLevel',
    # 人物卡与世界卡
    'PersonaCard',
    'WorldCardView',
    'PersonaWorldIntegrator',
    'PersonalCharacterMigrationTask',
    'DynamicPersonaUpdateManager',
    # 世界事件系统
    'WorldEventManager',
    'SpatialMessage',
    'GossipMessage',
    'NPCToolRegistry_SocialExtension',
    'MessageType',
    # 反思流程
    'ReflectionFlowManager',
    'ReflectionEngine',
    'ReflectionTask',
    'ReflectionResult',
    'ReflectionType',
    # P2: 消息总线
    'NPCMessageBus',
    'Message',
    'BusMessageType',
    'MessagePriority',
    'Subscription',
    'get_message_bus',
    'reset_message_bus',
    # P2: 空间系统
    'SpatialSystem',
    'Location',
    'NPCPosition',
    'ZoneType',
    'get_spatial_system',
    'reset_spatial_system',
    # P2: 事件协调器
    'EventCoordinator',
    'EventAnalysis',
    'NPCEventResponse',
    'NPCRole',
    'EventPriority',
    'get_event_coordinator',
    'set_coordinator_llm_client',
    # P2: 统一工具系统
    'UnifiedTool',
    'UnifiedToolRegistry',
    'ToolCategory',
    'UNIFIED_TOOLS',
    'get_unified_tools_prompt',
    'parse_tool_call',
    # P3: LLM事件处理器
    'LLMEventProcessor',
    'MemoryFeedback',
    'EventProcessingResult',
    'process_event_with_llm',
    # P3: 事件推进系统
    'EventProgressionSystem',
    'EventPhase',
    'EventState',
    'EventProgression',
    # P3: 动态世界管理
    'DynamicWorldManager',
    'DynamicNPC',
    'NPCStatus',
    'EventOutcome',
    'EventJudgment',
    'get_world_manager',
    'reset_world_manager',
    # P3: 三方交互系统
    'InteractionManager',
    'TripartiteMemory',
    'InstantiationJudge',
    'UninstantiatedEntity',
    'InteractionType',
    'MemoryEntry',
    'EntityType',
]
