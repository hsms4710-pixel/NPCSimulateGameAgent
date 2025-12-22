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
    'ReflectionType'
]
